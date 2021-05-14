#!/bin/bash
#
# $Id: updateAQIwebsite.sh,v 2.1 2021/05/14 18:07:34 teus Exp teus $
# Copyright (C) 2020, Teus Hagen, the Netherlands
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the Reciprocal Public License as published by
# the Open Source Initiative https://opensource.org/licenses/RPL-1.5:
#
#   Unless explicitly acquired and licensed from Licensor under another
#   license, the contents of this file are subject to the Reciprocal Public
#   License ("RPL") Version 1.5, or subsequent versions as allowed by the RPL,
#   and You may not copy or use this file in either source code or executable
#   form, except in compliance with the terms and conditions of the RPL.
#
#   All software distributed under the RPL is provided strictly on an "AS
#   IS" basis, WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESS OR IMPLIED, AND
#   LICENSOR HEREBY DISCLAIMS ALL SUCH WARRANTIES, INCLUDING WITHOUT
#   LIMITATION, ANY WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
#   PURPOSE, QUIET ENJOYMENT, OR NON-INFRINGEMENT. See the RPL for specific
#   language governing rights and limitations under the RPL.
#

# script to update air quality index information in Drupal website MySQL database
# updates markers (style and gps location) on the kit locations map and kit info pages.
# using measurement data from luchtkwaliteit MySQL database.

VERBOSE=${VERBOSE/0/}
VERBOSE=${VERBOSE/off/}
DEBUG=${DEBUG/off/}             # if not off or not empty do not update, show update sql
if [ -n "$DEBUG" ] ; then VERBOSE=ON ; fi
AQIpl="$(dirname $0)/AQI.pl"
AQIpl=${AQIpl/\/usr\/bin/.}  # in case of use of bashdb
CORpl="$(dirname $0)/CorrectSensed.pl"
CORpl=${CORpl/\/usr\/bin/.}  # in case of use of bashdb
if [ ! -f $AQIpl -o ! -f $CORpl ]
then
    echo "FATAL ERROR: depends on AQI.pl and CorrectSensed.pl. Missing $AQIpl or $CORpl" 1>&2
    exit 1
fi

function notice() {
    case "$1" in
    DEBUG)
        if [ -n "$DEBUG" ] ; then echo "$*" 1>&2 ; fi
    ;;
    ERROR|WARNING|ATTENT|FATAL|MESG)
        local TYPE=$1 ; shift
        echo "updateAQIwebsite ${TYPE}: $*" 1>&2
        if [ "$TYPE" = FATAL ] ; then exit 1 ; fi
    ;;
    VERBOSE)
        shift
        if [ -n "$VERBOSE" ] ; then echo "$*" 1>&2 ; fi
    ;;
    *)
        echo "$*" 1>&2
    ;;
    esac
}

# database credentials
DBHOST=${DBHOST:-localhost}
DBUSER=${DBUSER:-$USER}
DBPASS=${DBPASS}
DBWeb=${DBWeb:-parel7}
DBaq=${DBaq:-luchtmetingen}

#if [ -z "$DBPASS" ]
#then
#    read -s -p "Provide password for both databases on host $DBHOST user $DBUSER: " DBPASS
#    echo 1>&2
#fi
#export DBPASS=${DBPASS:-accacadabra}

# how to approach MySQL database. Uses mysql DB configuration in home user
# To Do: speed this up via coroutine implementation
MYSQLWeb="mysql --login-path=${DBWeb:-parel7} -h ${DBHOST:-localhost} -N -B --silent ${DBWeb:-parel7}"
MYSQLMys="mysql --login-path=${DBaq:-luchtmetingen} -h ${DBHOST:-localhost} -N -B --silent ${DB:-luchtmetingen}"
notice DEBUG "Using MySQL CLI command for  Web: $MYSQLWeb"
notice DEBUG "Using MySQL CLI command for airq: $MYSQLMys" 

# configuration items
MEETPROJ=meetkit_project          # Drupal 'vid' page content type
MEETTYPE=meetkit_lokatie          # Drupal view type
AQIS=${AQIS:-AQI LKI CAQI AQHI}   # prioritised row of air quality index types
OMIT='KIP_CECEA5167524'           # omit these kits Posix pattern
PROJECTS='SAN|HadM|KIP|test|RIVM' # project id's used in data tables and taxonomy terms
TMP=/var/tmp                      # temparary files/pipes dir

# clean up on exit
trap 'rm -f $TMP/UpdateAQIs[1-9]* ; exit' EXIT

# send sql to the MySQL database service WEB or MySense
# ToDo startup a parallel process talking with this script via named pipe input
#      this will avoid quite some overhead, but need to cleanup everything on exit
function ToMySQL() {
   local DBTYPE=${1} ; shift
   case "$DBTYPE" in
   WEB|web)
      DBTYPE="$MYSQLWeb"
   ;;
   MySense|mysense|MYSENSE)
      DBTYPE="$MYSQLMys"
   ;;
   *) notice FATAL "in named pipe MySQL DB access command"
   ;;
   esac
   notice DEBUG "DB $0 send: \"$*\""
   if (( $# > 0 ))
   then  $DBTYPE -e "$*" # send all sql to MySQL DB service via named pipe
   else  $DBTYPE
   fi
}

# get all node nr's with type MEETTYPE  (meetkit_lokatie)
function get_meetkits_nids() {
   ToMySQL WEB "SELECT nid, title FROM node WHERE type = '$MEETTYPE' AND status ORDER BY changed DESC;"
   return $?
}

# get vid nr for taxonomy vocabulary with name MEETPROJ (meetkit_project)
function get_vid() {
   ToMySQL WEB "SELECT vid FROM taxonomy_vocabulary WHERE machine_name = '${1:-${MEETPROJ}}' LIMIT 1;"
}

# get active taxonomy name with node nr from meetkit_project
function get_Nid2ProjectId(){
   local NID=$1
   ToMySQL WEB "SELECT t.name from taxonomy_term_data t, field_data_field_project_id pid WHERE pid.entity_id = $NID AND not pid.deleted AND t.tid = pid.field_project_id_tid;"
}

# get serial nr for kit from node nr in bundle MEETTYPE (meetkit_lokatie)
function get_Nid2Serial(){
   local NID=$1
   ToMySQL WEB "SELECT field_serial_kit_value FROM field_data_field_serial_kit WHERE bundle = '$MEETTYPE' AND entity_id = ${NID} AND not deleted;"
}

# get node nid, project_id and serial kit nr for MEETTYPE (meetkit_lokatie) of pages
function Meetkit2NidProjSerial() {
   ToMySQL WEB "SELECT CONCAT(n.nid,'=',t.name,'=',s.field_serial_kit_value) FROM node n, field_data_field_project_id pid,  taxonomy_term_data t, field_data_field_serial_kit s WHERE n.type = '$MEETTYPE' AND pid.entity_id = n.nid AND t.tid = pid.field_project_id_tid AND s.entity_id = n.nid AND s.bundle = '$MEETTYPE' AND NOT s.deleted AND NOT pid.deleted;"
}

# get from proj_serial (measurement DB table id) the Drupal website node nid number
function get_Table2Nid() {
    local PROJ=${1/_*/} SERIAL=${1/*_/}
    if (( $# > 1 )) ; then SERIAL=$2 ; fi
    # may need to check if there is only one
    local RTS=($(ToMySQL WEB "SELECT n.nid FROM node n, taxonomy_term_data t, field_data_field_serial_kit s WHERE n.type = '$MEETTYPE' AND s.field_serial_kit_value = '$SERIAL' AND '$PROJ' = t.name AND s.entity_id = n.nid AND s.bundle = '$MEETTYPE' AND NOT s.deleted;"))
    if (( ${#RTS[@]} > 1 ))
    then
        notice WARNING "There are more as one page nodes for $* found."
    #elif (( ${#RTS[@]} == 0 ))
    #then
    #    notice ATTENT "No node nid found for $*"
    fi
    echo "${RTS[0]}"
}

# get node nid, project id, serial and node title for MEETTYPE pages
# global info of alle meetkit pages present in Drupal database
function ListNidProjSerialTitles() {
   echo -e "proj\tserial nr\tnode\ttitle (regio: straat)"
   echo -e "----\t----------\t----\t---------------------"
   ToMySQL WEB "SELECT t.name,s.field_serial_kit_value,n.nid,n.title FROM node n, field_data_field_project_id pid,  taxonomy_term_data t, field_data_field_serial_kit s WHERE n.type = '$MEETTYPE' AND pid.entity_id = n.nid AND t.tid = pid.field_project_id_tid AND s.entity_id = n.nid AND s.bundle = '$MEETTYPE' AND NOT s.deleted AND NOT pid.deleted;"
}

# Air Quality Index colors EPA USA
COLS_AQI=(
            0x00e400 0xffff00 0xff7e00 0xff0000 0x8f3f97
            0x7e0023
)
# Lucht Kwaliteits Index RIVM
COLS_LKI=(  # 0x0f0f0f
            0x0020c5 0x002bf7 0x006df8 0x009cf9 0x2dcdfb
            0xc4ecfd 0xfffed0 0xfffda4 0xfffd7b 0xfffc4d
            0xf4e645 0xffb255 0xff9845 0xfe7626 0xff0a17
            0xdc0610 0xa21794
)
# Common Air Quality Index colors EU
COLS_CAQI=( 0x79bc6a 0xb9ce45 0xedc100 0xf69208 0xf03667)
# Air Quality Index colors Canada
COLS_AQIH=( # 0xf0f0f0
            0x00ccff 0x0099cc 0x006699 0xffff00 0xffcc00
            0xff9933 0xff6666 0xff0000 0xcc0000 0x990000
            0x660000
)
COLS=( gray black ${COLS_AQI[@]} ${COLS_LKI[@]} ${COLS_CAQI[@]} ${COLS_AQIH[@]} )
# MARKER_COLORS
# AQIgray.png AQIblack.png
# AQI 2 .. 7: 2 + index COLS_AQI
# AQI_0_50.png AQI_50_100.png AQI_100_150.png AQI_150_200.png AQI_200_300.png AQI_300_500.png
# LKI 8 .. 24 8 + index COLS_LKI
# LKI00_05.png LKI05_10.png LKI10_15.png LKI15_20.png LKI20_25.png
# LKI25_30.png LKI30_36.png LKI36_42.png LKI42_48.png LKI48_54.png
# LKI54_60.png LKI60_67.png LKI67_74.png LKI74_80.png LKI80_90.png
# LKI90_100.png LKI90_100.png
# CAQI 25 .. 29
# AQIH 30 .. 40


# get website color marker index from color of lk index: output index integer value to stdout
function get_color_index() {
   if [ ${1:-NULL} = NULL ] ; then echo 0; return 0 ; fi
   if [ ${1} = 0 ] ; then echo 1 ; return 0 ; fi
   for(( I=0 ; I < ${#COLS[@]} ; I++ ))
   do
      if [ ${COLS[${I}]} = $1 ] ; then echo ${I}; return 0 ; fi
   done
   echo 0
}

# require that row exists and remain the value in revison tables
# set all 4 aqi values for node nr
# not using replace! (revision table remains untouched) reminder node_revision table
# generate MySQL sql Drupal website DB
function set_aqis() {
   declare -A VALUES
   local NID=$1 ; shift
   if [ -z "$NID" ] ; then return 1 ; fi
   for (( I=0; I < 4; I++))
   do
      echo "UPDATE field_data_field_lucht_kwaliteits_index SET field_lucht_kwaliteits_index_value = ${1:-NULL} WHERE entity_id = $NID AND delta = $I;"
      shift
   done
}

# not using replace! (revision remains untouched)
# generate MySQL sql for Drupal website: arg: node nid and timestamp eg '1 jan 2020 10:30'
function set_aqi_datum(){
   local NID=$1 DATUM=$2
   echo "UPDATE field_data_field_aqi_datum SET field_aqi_datum = '$DATUM' WHERE entity_id = $NID;"
}

# not using replace! (revision remains untouched)
# generate MySQL sql for Drupal website; args: node nid and color (index value)
function set_marker_color() {
   local NID=$1 IDX=$2
   echo "UPDATE field_data_field_marker_color SET field_marker_color = $IDX WHERE entity_id = $NID AND bundle = '$MEETTYPE' AND delta = 0;"
}

# get node id from project id and serial
# generate nod nid setting in @NID from project id (SAN, HadM, RIVM, test) and serial nr kit
function get_nid(){
  local PROJID=$1 SERIAL=$2
  echo "SET @TID=(SELECT tdat.tid FROM taxonomy_term_data tdat, taxonomy_vocabulary voc WHERE tdat.vid = voc.vid AND tdat.name = '$PROJID' AND voc.machine_name = '$MEETPROJ');"
  echo "SET @NID=(SELECT kit.entity_id FROM field_data_field_serial_kit kit, field_data_field_project_id pid WHERE kit.bundle = '$MEETTYPE' AND not kit.deleted AND pid.field_project_id_tid = @TID AND kit.field_serial_kit_value = '$SERIAL' limit 1);"
}

# get AQ[H]I index: args: [all|index|color|aqi|gom] pol1 value1 ...
# returns array of (aiq,color) pairs for all AQIS (AQI,LKI,CAQI,AQIH)
# generate air qual index details: index=hex_color for 4 air qual indices on std out
function INDEX_AQ()
{
  local A
  for A in ${AQIS[@]}
  do
    perl -e "require '${AQIpl:-./AQI.pl}';" -e "@r = max$A(\"noprint $*\"); " -e "printf(\"%2.1f=0x%6.6x\n\", \$r[0], \$r[1]);"
  done
}

# calculate sensor type per manufacturer correction for pollutants 
# usage: CORRECT {TBL=project_serial|TBL=station} REF=ReferencedSensorType [REG=0.6] SENSOR=SensorType polI[=valueI] ....
# where (Referenced)SensorType is eg SDS011, PMS[xA157]003, SPS30 or Nova, Plantwoer, Sensirion
# and polI is either pm_10,pm10,pm_25,pm25,pm1 and valI the value to be corrected
# value may be a comma separated list. Field separator is automatically detected
# REG is minimal regression factor for selecting correction algorithm. Default 0.6.
# returns corrected values or in case of empty value the correction algorithm
function CORRECT()
{
   local P SENSOR REF ARG REG SEP=' '
   declare -a POLS
   declare -i I
   for ARG in $*
   do
       case "${ARG}" in
       REF=*) REF="${ARG/*=/}" ; REF="${REF^^}"  # reference sensor type, default SPS30
       ;;
       SENSOR=*) SENSOR="${ARG/*=/}" ; SENSOR="${SENSOR^^}" # sensor type of manufacturer eg SPS30
       ;;
       REG=*) REG="${ARG/*=/}"                   # minimal regression selection correction criterium
       ;;
       pm*=*|PM*=*)                              # yet only PM sensors type are supported
           POLS[$I]="${ARG/=*/}=${ARG/*=/}" ; I+=1
           SEP=' '
       ;;
       *)
          if echo "$ARG" | grep -q -P ',[a-zA-Z]' ; then ARG="${ARG//,/ }" ; SEP=',' ; fi
          for P in $ARG
          do
                if ! echo  "$P" | grep -q -P '^[A-Za-z0-9_]+$'
                then
                    echo "ERROR: unsupportant pollutant ${P/=*/}. Skipped." >/dev/stderr
                else
                    POLS[$I]="$P" ; I+=1   # maybe pollutant (e.g. rv) will not get correction
                fi
          done
       ;;
       esac
   done
   if [ -z "$REF" ] || [ -z "$SENSOR" ]
   then
       echo "ERROR in command CORRECT arguments (missing REF or one of TBL/SENSOR) $*" >/dev/stderr
   fi
   ARG=''
   for (( I=0; I < ${#POLS[@]}; I++ ))
   do
       if [ -z "$ARG" ]
       then ARG="${POLS[$I]}"
       else ARG+="${SEP}${POLS[$I]}"
       fi
   done
   if [ "$REF" = "$SENSOR" ] # no correction to be applied
   then
       echo "${ARG}"
       return 0
   fi
   if [ -z "$SENSOR" ]
   then
       echo "ERROR: sensor type not defined! Missing SENSOR or PROJ_SERIAL definition." >/dev/stderr
       return 1
   fi
   SENSOR="\$SENSOR = '$SENSOR';"
   if [ -n "$REG" ]  # minimal regression factor for alg selection
   then SENSOR="$SENSOR \$REG = $REG;"
   fi
   # SENSOR+=" \$debug = 2;"
   ARG="\$REF = '$REF'; $SENSOR print(CORRECT('${ARG}'));"
   perl -e "require '${CORpl:-./CorrectSensed.pl}';" -e "$ARG"
}
# # test examples:
# CORRECT REF=SPS30 SENSOR=PMSX003 pm10=35.5 pm25=25.8 pm1=20.7
# CORRECT SENSOR=SAN_30aea4509eb4 REF=SPS30 "pm10=35.5 pm25=25.8 pm1=20.7"
# CORRECT REF=SPS30 SENSOR=SDS011 pm10,pm25,pm1,rv,luchtdruk,temp
# CORRECT SENSOR=BAM1020 REF=SPS30 pm25 pm10
# CORRECT SENSOR=NL1031 REF=SPS30 "pm25 pm10"

# Air Quality Index details and constants

# unpack and convert output from CORRECT to internal situation
# works only with pollutant names
function ConvertCorrect() {
  local CORR="${1:-XYZ}"; shift
  local POL="${1:-XYZ}"; shift
  local FCT="$1" C;
  if [ -z "${CORR/*,*/}" ]
  then CORR="${CORR//,/ }"
  fi
  for C in $CORR
  do
    if ! echo "$C " | grep -q -P "$POL[^A-Za-z0-9]" ; then continue ; fi
    if [ -n "$FCT" ] ; then C="${C//${POL}/${FCT}($POL)}" ; fi
    echo "$C"
  done
  return 0
}

# get table name (PROJ_serial_hex for meetkit of Drupal website node nr on stdout
function get_table() {
   local NID=$1
   if [ -z "$1" ] ; then return 0 ; fi
   local PROD_ID SERIAL
   PROD_ID=$(get_project_id $NID)
   if [ -z "$PROD_ID" ] ; then notice VERBOSE "Skip $NID node, no prod id." ; return 1; fi
   SERIAL=$(get_serial_kit $NID)
   if [ -z "$SERIAL" ] ; then notice VERBOSE "Skip $NID node, no serial." ; return 1 ; fi;
   echo "${PROD_ID}_${SERIAL}"
}

# get PM values of last 2 hours from table name on stdout
function get_PM() {
   local TBL=$1  COR  # do sensor correction to ref sensor SPS30
   if [ -z "$TBL" ] || [ -n "${TBL/*?_?*/}" ] ; then return 1 ; fi
   declare -a COR
   COR=($(CORRECT SENSOR="$TBL" REF=SPS30 'pm25 pm10'))
   if (( ${#COR[@]} < 2 )) ; then COR=(pm25 pm10) ; fi
   ToMySQL MySense "SELECT CONCAT('pm25=',${COR[0]},' pm10=', ${COR[1]}, ' TIME=', UNIX_TIMESTAMP(datum)) FROM $TBL WHERE datum >= UNIX_TIMESTAMP(now())-2*60*60 AND pm25_valid AND pm10_valid ORDER BY datum DESC LIMIT 1;"
}

# get all table names from all kits in website
function get_tables() {
   local KITS=$(get_meetkits)
   local NID
   local PROD_ID
   local SERIAL
   for NID in $KITS
   do
      notice VERBOSE "Found for node $NID: table $(get_table $NID)"
   done
}

# set current date from UNIX timestamp in website aqi value
function set_AQIdate() {
   local DATE=$1
   if [ -z "$1" ] ; then return 1 ; fi
   date --date=@$DATE '+%-d %b %Y %-H:%M'
}

# get table names with #measurements last 2 hours, last 10 hours and last 24 hours
# returns list of proj_serial=LastHour2=LastHour2-10=LastHours24
function get_kit_tables() {
    ToMySQL MySense 'SHOW TABLES;' | grep -P "($PROJECTS)_[0-9a-fA-F]{12,}$" | grep -v -P "($OMIT)"
}

function get_tbl_PM() {
    local TBLS=$1 TBL
    local T1=2 T2=10 T3=24 # intervals in hours
    local INREPAIR
    for TBL in $*
    do
        # FilterShow.py will also invalidate PM valids
        INREPAIR=$(ToMySQL MySense "SELECT (IF( ISNULL(refresh),UNIX_TIMESTAMP(now())+60,UNIX_TIMESTAMP(refresh))) FROM TTNtable WHERE project = '${TBL/_*/}' AND serial = '${TBL/*_/}' ORDER BY datum DESC LIMIT 1")
        echo "SELECT '$TBL', (SELECT count(*) FROM $TBL WHERE UNIX_TIMESTAMP(datum) >= UNIX_TIMESTAMP(now())-$T1*60*60 AND UNIX_TIMESTAMP(datum) <= ${INREPAIR:-0} AND NOT isnull(pm25) AND NOT isnull(pm10) AND pm25_valid AND PM10_valid), (SELECT count(*) FROM $TBL WHERE UNIX_TIMESTAMP(datum) >= UNIX_TIMESTAMP(now())-$T2*60*60 AND UNIX_TIMESTAMP(datum) < UNIX_TIMESTAMP(now())-$T1*60*60 AND UNIX_TIMESTAMP(datum) <= ${INREPAIR:-0} AND NOT isnull(pm25) AND NOT isnull(pm10) AND pm25_valid AND PM10_valid), (SELECT count(*) FROM $TBL WHERE UNIX_TIMESTAMP(datum) >= UNIX_TIMESTAMP(now())-$T3*60*60 AND UNIX_TIMESTAMP(datum) < UNIX_TIMESTAMP(now())-$T2*60*60 AND UNIX_TIMESTAMP(datum) <= ${INREPAIR:-0} AND NOT isnull(pm25) AND NOT isnull(pm10) AND pm25_valid AND PM10_valid);"
    done | $MYSQLMys | sed 's/\t/=/g'
}

# generate MySQL sql to update node with timestamp, marker color and aqi's to stdout
function update_node() {
    local NODE=$1 PROJ=$2 SERIAL=$3
    if [ -z "$3" ] ; then return 1 ; fi
    # order from AQIS array
    local AQI=${4:-0=gray} LKI=${5:-0=gray} CAQI=${6:-0=gray} AQIH=${7:-0=gray}
    local COLOR=${5/*=/}
    if [ -n "${COLOR/50/}" ]
    then COLOR=$(get_color_index ${COLOR}) # use marker volor of LKI index
    else COLOR=50 ; fi # special case marker style lantern
    AQI=${AQI/=*/} # delete color value
    LKI=${LKI/=*/} # delete color value
    CAQI=${CAQI/=*/} # delete color value
    AQIH=${AQIH/=*/} # delete color value
    local DATUM=${8} NOW=$(date +%s)
    # may need to verify if node exists for this kit first
    # update node changed date/time. Maybe clear cache needed?
    local SQL="UPDATE field_data_field_marker_color SET field_marker_color_value = ${COLOR:-0} WHERE entity_id = $NODE AND bundle = '$MEETTYPE' AND delta = 0;\n"
    if [ -n "$DATUM" ] ; then
      SQL+="UPDATE field_data_field_lucht_kwaliteits_index SET field_lucht_kwaliteits_index_value = ${AQI:-0} WHERE entity_id = $NODE AND bundle = '$MEETTYPE' AND delta = 0;\n"
      SQL+="UPDATE field_data_field_lucht_kwaliteits_index SET field_lucht_kwaliteits_index_value = ${LKI:-0} WHERE entity_id = $NODE AND bundle = '$MEETTYPE' AND delta = 1;\n"
      SQL+="UPDATE field_data_field_lucht_kwaliteits_index SET field_lucht_kwaliteits_index_value = ${CAQI:-0} WHERE entity_id = $NODE AND bundle = '$MEETTYPE' AND delta = 2;\n"
      SQL+="UPDATE field_data_field_lucht_kwaliteits_index SET field_lucht_kwaliteits_index_value = ${AQIH:-0} WHERE entity_id = $NODE AND bundle = '$MEETTYPE' AND delta = 3;\n"
      SQL+="UPDATE field_data_field_aqi_datum SET field_aqi_datum_value = '${DATUM}' WHERE entity_id = $NODE AND bundle = '$MEETTYPE';\n"
      SQL+="UPDATE node SET changed = ${NOW} WHERE nid = $NODE AND type = '$MEETTYPE';\n"
    fi
    echo -e "$SQL"
}

# generate MySQL sql aqi index update instructions for one kit location
# arguments: NODE PROJ SERIAL TABLE 2H=2-10H=10-24H (statistics of last 24 hours #data)
function get_tbl_aqis(){
    local TBL=${4}
    local NODE=${1} PROJ=${2} SERIAL=${3}
    local CHANGED=0
    case "$5" in
    0=0=0)
       notice VERBOSE "$TBL last 24 hours not active."
       update_node  $NODE $PROJ $SERIAL 0= 0= 0= 0=
    ;;
    0=0=*)
       notice VERBOSE "$TBL previous day maybe active, last 10 hours not active."
       update_node  $NODE $PROJ $SERIAL 0=gray 0=gray 0=gray 0=gray
    ;;
    0=*=*)
       notice VERBOSE "$TBL last 2 hours not active."
       update_node  $NODE $PROJ $SERIAL 0=black 0=black 0=black 0=black
    ;;
    *=*=*)
       notice VERBOSE "$TBL last 2 hours active."
       local DATUM COR # correct pm values to ref sensor SPS30
       COR=$(CORRECT SENSOR="$TBL" REF=SPS30 'pm25 pm10')
       if [ -z "$COR" ] ; then COR='pm25 pm10' ; fi
       # get PM2.5 and PM10 averages over last 2 hours of one or more measurements
       # sliding average over 2 hours (ca 8 measurements)
       local PM_VALS=($(ToMySQL MySense "SELECT UNIX_TIMESTAMP(datum) FROM $TBL WHERE UNIX_TIMESTAMP(datum) >= UNIX_TIMESTAMP(now())-2*60*60 AND NOT isnull(pm25) AND NOT isnull(pm10) AND pm25_valid AND PM10_valid AND pm25 > 0 AND PM10 > 0 ORDER BY datum DESC LIMIT 1; SELECT CONCAT('pm25=',$(ConvertCorrect ${COR/ */} pm25 avg),' pm10=',$(ConvertCorrect ${COR/* /} pm10 avg)) FROM $TBL WHERE UNIX_TIMESTAMP(datum) >= UNIX_TIMESTAMP(now())-2*60*60 AND NOT isnull(pm25) AND NOT isnull(pm10) AND pm25 > 0 AND PM10 > 0 AND pm25_valid AND PM10_valid;"))
       if [ -z "${PM_VALS[0]}" ] # no timestamp, so no measurements in the last 2 hours
       then
          update_node  $NODE $PROJ $SERIAL 0=black 0=black 0=black 0=black # black marker
       else # there are measurements calculate AQI/LKI/CAQI/AQIH air quality indices
          local DATUM=$(date --date=@${PM_VALS[0]} '+%-d %b %Y %-H:%M')
          local AQIs=$(INDEX_AQ "${PM_VALS[1]} ${PM_VALS[2]}")
          # MySQL sql to update the website page form linked to by node nid nr
          update_node $NODE $PROJ $SERIAL ${AQIs[@]} "$DATUM"
       fi
    ;;
    *)
       notice ERROR "get_tbl_aqis $*"
    ;;
    esac
}

# generate aqi sql for one node (nid nr) projectID Serial
# output: MySQL update sql instructions. In debug mode to stderr
function update_one_aqi() {
   local NID=$1 PROJ=$2 SN=$3
   notice DEBUG "Try website meetkit: node/projID/SN $*"
   if [ -z $(ToMySQL MySense "SHOW TABLES LIKE '${PROJ}_${SN}';") ] # has a table in DB?
   then
       if [ "$PROJ}" = 'test' ] && [ "$VERBOSE" != /dev/stderr ] ; then continue ; fi
       local TITLE=$(ToMySQL WEB "SELECT title FROM node WHERE nid = ${NID};")
       notice WARNING "Kit with node ${NID} \"$TITLE\", projec id ${PROJ} and serial ${SN} is not in measurement database yet. Skipped."
       return 0
   fi
   local PM_HIST=$(get_tbl_PM ${PROJ}_${SN}) # last 24 hours active?
   # if [ -z "${PM_HIST/*=0=0=0/}" ] ; then return 0 ; fi
   # get website Drupal update instructions for this meetkit
   if [ -n "$DEBUG" ]
   then
       get_tbl_aqis ${NID} ${PROJ} ${SN} ${PM_HIST/=/ } >>$TMP/UpdateAQIs$$
   else
       ToMySQL WEB "$(get_tbl_aqis ${NID} ${PROJ} ${SN} ${PM_HIST/=/ })"
   fi
   return $?
}

# get website DB update instructions for current AQI/LKI values on pages
# output: MySQL update SQL
function update_aqis() {
    local REC
    for REC in $(Meetkit2NidProjSerial) # current meetkits which are on website
    do
        if [ -z "${REC//=/}" ] ; then continue ; fi
        update_one_aqi ${REC//=/ }
    done
}

if [ -z "$1" ]
then # update all meetkit location pages aqi. Default.
    update_aqis
fi

for ARG
do
  case "$ARG" in
    all)
        update_aqis             # update all node pages of meetkit locations with aqi
    ;;
    nodes)
        get_meetkits_nids       # list all node and titles pages of meetkit locations
    ;;
    list)
        ListNidProjSerialTitles # list global info for all meetkit pages
    ;;
    [1-9][0-9]*)                # update node page meetkit location with node nr nid
        PROJ=$(get_Nid2ProjectId $ARG)
        SN=$(get_Nid2Serial $ARG)
        if [ -n "$PROJ" -a -n "$SN" ]
        then
            update_one_aqi $ARG $PROJ $SN
        else
            notice ERROR "Failure for nid $ARG (Project \"$PROJ\" with SN \"$SN\")"
        fi
    ;;
    *_[0-9a-fA-F][0-9a-fA-F]*)
        PROJ=${ARG/_*/}
        SN=${ARG/*_/}
        NID=''
        if [ -n "$PROJ" -a -n "$SN" ]
        then
            NID=$(get_Table2Nid $ARG)
        fi
        if [ -n "$NID" ]
        then
            update_one_aqi $NID $PROJ $SN
        elif [ -n "$VERBOSE" ]
        then
            notice WARNING "No website node nid for DB table ID $ARG (Project \"$PROJ\" with SN \"$SN\")"
        fi
    ;;
    help|*)
        cat 1>&2 <<EOF
Usage: $0 cmd ...
     all         Will search for all website meetkit location pages and do aqi updates Default
     nr          Integer, node nid nr of meetkit location page to be updated its aqi, eg 4770
     table id    proj_serial database table ID of measurements DB, eg test_12345ab78
     nodes       List all node nid's with their title. Order: last changed.
     list        List all global info (nid,project ID, serial and title) of meetkit nodes.
Script will update air quality index on Drupal website meetkit location pages e.g. DB $DBWeb
from measurements in air quality MySQL database eg $DBaq.
MySQL database credentials will be taken from $HOME/.mysql rc file.
EOF
    ;;
    esac
done

if [ -f "$TMP/UpdateAQIs$$" ]
then
    mv $TMP/UpdateAQIs$$ $TMP/UpdateAQIs
    notice ATTENT "Modus: update sql available via: $TMP/UpdateAQIs"
    notice ATTENT "Used MySQL command: $MYSQLMys"
    notice ATTENT "Used MySQL command: $MYSQLWeb"
fi

# end of script, clean up
#for I in $ToMySQLMys $ToMySQLWeb
#do
#    if [ -p ${I:-0} ]
#    then
#        echo quit >${I:-/dev/null}
#        rm -f ${I:-0}
#    fi
#done
if [ -x /homeOLD/teus/.composer/vendor/bin/drush ]
then
    /homeOLD/teus/.composer/vendor/bin/drush @bdp cc all 2>/dev/null 1>&2
    # somehow the cache remained in tack and did not be cleared to show updated markers on map
fi
exit 0
