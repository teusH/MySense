#!/bin/bash

# Contact Teus Hagen MySense@behouddeparel.nl to report improvements and bugs
#
# Copyright (C) 2022, Teus Hagen, the Netherlands
# Open Source Initiative  https://opensource.org/licenses/RPL-1.5
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
# $Id: UpdateValidity.sh,v 1.16 2022/01/21 13:57:32 teus Exp teus $

# example of command: FROM='22-02-02 14:00' OUTPUT=CSVfileName bash UpdateValidity.sh '(test|HadM).*e4'
#                     file name will be extended with date stamp en .csv
# RDBHOST only for use of previous DB tabes on a server
# DBHOST DBPASS DB DBUSER environment var for DB MySQL DB
# OUTPUT dflt /dev/stdout for CSV meta info
# VERBOSE default 1 verbosity
# use 'command dropkit project serial ...'  to delete meta info project serial
#     (serial may be a mysql pattern).

VERBOSE=${VERBOSE:-1}

DB=${DB:-luchtmetingen}
DBHOST=${DBHOST:-localhost}
MYSQL="mysql --login-path=$DB -N -B --silent -h $DBHOST $DB"

# script to invalidate measurements if kit is not at home location

ACTIVE=()  # active measurement kits
KITS=()    # list of measurement tables
OUTPUT=${OUTPUT} # if defined base name of CSV output file
FROM=${FROM}     # date from timetamp so search for not home location (use date cmd format)
                 # if FROM = 0 list only

function VERBOSITY() {
    local OPT=''
    while [ $# -gt 0 -a -z "${1/#-*/}" ]
    do
      OPT+=" $1" ; shift
    done
    if (( $VERBOSE > 0 ))
    then
       echo $OPT  "$@" 1>&2
    fi
}

# cleanup database for expired meta info and measurements data
# arguments: project serial (serial may be a regular exp like '.*12345'
# return 0 if meta info is deleted from Sensors table.
function DropKit() {
    local PROJ=$1 SER ANS TMP INFO PTRN=$2 RTS=1
    declare -a TBL

    # drop measurements data table
    TBL=($($MYSQL -e "SHOW TABLES like '${PROJ}_%'" | grep -P "$PTRN") )
    if (( ${#TBL[@]} > 1 ))
    then
      VERBOSITY "Found more as one in table $TMP: ${TBL[@]}. Improve pattern!"
      return $RTS
    fi
    if [ -n "${TBL[0]}" ]
    then
      SER=${TBL[0]}
      INFO=$($MYSQL -e "SELECT COUNT(*) FROM ${SER}")
      read -p "Delete all measurement data (#${INFO}) table $SER for measurement kit project $PROJ and serial ${SER/*_/}? no|[yes] " ANS
      if [ ${ANS:-yes} = yes ]
      then
        if ! $MYSQL -e "DROP TABLE $SER"
        then VERBOSITY "Failed to delete measurements of table $SER"
        fi
      fi
    else
      VERBOSITY "There are no measurement data records for project $PROJ and serial pattern '${PTRN}'."
    fi

    # delete meta info for this kit from Sensors and TTNtable
    INFO=''
    for TMP in Sensors TTNtable
    do
      TBL=($($MYSQL -e "SELECT serial FROM Sensors WHERE project = '$PROJ'" | grep -P "$PTRN" | sort | uniq) )
      if (( ${#TBL[@]} > 1 ))
      then
        VERBOSITY "Found more as one in table $TMP: ${TBL[@]}. Improve '${PTRN}' pattern!"
        break
      fi
      if [ -n "${TBL[0]}" ]
      then
        if [ $TMP = Sensors ]
        then
          INFO=$($MYSQL -e "SELECT CONCAT('label: ',IF(ISNULL(label),'None',label),', street: ',IF(ISNULL(street),'None',street)) FROM Sensors WHERE project = '$PROJ' AND serial = '$SER' ORDER BY active DESC, datum DESC LIMIT 1")
        fi
        SER=${TBL[0]}
        read -p "Remove all meta info for measurement kit ($INFO) in table $TMP identified by project $PROJ and serial $SER? no|[yes] " ANS
        if [ ${ANS:-yes} = yes ]
        then
          if ! $MYSQL -e "DELETE FROM $TMP WHERE project = '$PROJ' AND serial = '$SER'"
          then VERBOSITY "Failed to delete kit from $TMP"
          elif [ $TMP = Sensors ] ; then RTS=0
          fi
        fi
      fi
    done
    return $RTS
}
# DropKit HadM %2844
# DropKit HadM 0xe%
# DropKit HadM %7688
# DropKit HadM %a8c6

# use RDBHOST is empty when TTN V2 period is not used.
# host with TTN V2 measurements DB, defines invalid measurements start timestamp
RDBHOST=${RDBHOST}
RDBHOST=lunar
# give manual end date of invaliding period a possibility
# from Harrie 22-01-03 email
declare -A EndDate
# SAN
EndDate[ser5731]=21-11-30 # molenstr
# EndDate[ser8a24]= # den akker
EndDate[ser9cd5]=21-12-24 # vloetweg
EndDate[ser571d]=21-12-28 # schapenweg
EndDate[ser5729]=21-12-28 # kerkstr
EndDate[ser8fe9]=21-12-28 # cerespark
EndDate[ser9eb4]=21-12-31 # althof
EndDate[ser8cc4]=22-01-12 # noordkant-3
EndDate[ser6dbc]=21-12-31 # ledeacker
EndDate[ser8ff9]=22-01-01 # zandkand
EndDate[serad0d]=22-01-01 # speklef
EndDate[ser95e9]=22-01-01 # noordkant-2
EndDate[ser76dc]=22-01-01 # koningsl
# EndDate[serb311]= # noordkant 1
# EndDate[ser5cb8]= # mullemse dijk
# EndDate[ser7500]= # boompjesweg
# EndDate[sera6b9]= # bosweg
# HadM
EndDate[ser2a2c]=21-12-30  # de Bisweide
EndDate[ser1934]=21-12-30  # test de Bisweide
# EndDate[ser75e4]= # op de Kamp
# RIVM (3), KIP (9)

# return list of kit location timestamps: not at home till at home kit location
function GetHomePeriods() {
  local TBL=$1 FROM=${2:-0} TO=$3 STRT=0

  # check if geohash is available. If end of period = $FROM
  if ! $MYSQL -e "DESCRIBE $TBL" | grep -q -P '^geohash.*varchar'
  then
    VERBOSITY "WARNING active table $TBL has no geo locations column. It is added."
    $MYSQL -e "ALTER TABLE $TBL ADD COLUMN geohash VARCHAR(12) DEFAULT NULL COMMENT 'kit location'"
    return 1
  fi

  if [ -z "$TO" ] ; then TO=$(date --date=tomorrow +%s) ; fi
  if [ -n "$RDBHOST" ]
  then  # use manual defined period
    STRT=$(echo "$TBL" | sed 's/.*\(....\)$/ser\1/')
    if [ -n "${EndDate[$STRT]}" ]
    then
      TO=$(date --date="${EndDate[$STRT]}" +%s)
    fi
    FROM=$(${MYSQL/$DBHOST/$RDBHOST} -e "SELECT UNIX_TIMESTAMP(datum)+1 FROM $TBL ORDER BY datum DESC LIMIT 1")
    if [ -z "${FROM}" -o -z "${TO}" ] ; then VERBOSITY "ERROR manual period" ;  return 1 ; fi
  fi
  FROM=$(( FROM + 1 ))

  local Distance='python3 lib/MyGPS.py --distance'
  if [ ! -f lib/MyGPS.py ]
  then 
    VERBOSITY 'unable to locate python script lib/MyGPS.py'
    return 1
  fi

  # get home location of the kit
  # st_distance_sphere(point(51.4823,6.08252),point(51.4204702,6.135521)) in meters
  local HLOC=''  # kit home location: as defined in Sensors table +/- 118 meters
  # MySQL Point expects as args: Point(long,lat): HLOC gives "Point(long,lat)"
  HLOC=$($MYSQL -e "SELECT CONCAT('Point(',ST_LongFromGeoHash(geohash),',',ST_LatFromGeoHash(geohash),')') FROM Sensors WHERE project = '${TBL/_*/}' AND serial = '${TBL/*_/}' AND NOT ISNULL(geohash) ORDER BY active DESC, datum DESC LIMIT 1")
  if [ -n "$HLOC" ]
  then   # search for kit not at home location periodes: Date[i] >= not at home < Date[i+1], ...
    local PERIODS
    PERIODS=($($MYSQL -e "SELECT UNIX_TIMESTAMP(datum), ST_Distance_Sphere($HLOC,Point(ST_LongFromGeoHash(geohash),ST_LatFromGeoHash(geohash))) FROM $TBL WHERE UNIX_TIMESTAMP(datum) > $FROM AND UNIX_TIMESTAMP(datum) < $TO AND NOT ISNULL(geohash) ORDER BY datum DESC" | awk --assign rdate=$FROM --assign ldate=$TO 'BEGIN { if ( rdate > 0 ) { print rdate ; } else { rdate = 0; hdate = 0; }} { if ( $2 > 118 ) { if ( rdate == 0 ) { rdate = $1; print rdate ; hdate = 0 ; }} else { if ( hdate == 0 ) { hdate = $1 - 1; rdate = 0; print hdate ; }} } END { if ( rdate > 0 ) { print ldate; }} ') )
    echo $FROM ${PERIODS[@]} $TO
  fi
  return 0
}

# check and correct geo ordinates swap error
function GeoCorrect() {
  local TBL=$1 LON LAT
  declare -a ROW
  ROW=( $($MYSQL -e "SELECT UNIX_TIMESTAMP(id), geohash, ST_LongFromGeoHash(geohash), ST_LatFromGeoHash(geohash) FROM Sensors WHERE project = '${TBL/_*/}' AND serial = '${TBL/*_/}' AND not ISNULL(geohash) ORDER BY active DESC, datum DESC LIMIT 1") )
  if [ -z "${ROW[1]/#u1*/}" ] ; then return 0 ; fi
  VERBOSITY "Correcting geohash: swap lat <-> lon for ${TBL/_/ serial }"
  $MYSQL -e "UPDATE Sensors SET geohash = ST_GeoHash(${ROW[3]},${ROW[2]},12), datum = datum WHERE UNIX_TIMESTAMP(id) = ${ROW[0]}"
  return 1
}

# get list of measurement tables
function GetTables() {
   local TBLS TMP ANS FND=''
   for TMP in $@
   do
     for TBL in $($MYSQL -e "SELECT CONCAT(project,'_',serial) FROM Sensors" | sort | uniq | grep -P "$TMP")
     do
       FND=1
       if ! $MYSQL -e "SHOW TABLES" | grep -q $TBL
       then
         VERBOSITY "Table $TBL has no measurements in database $DB. Check validity is skipped."
       fi
       KITS+=($TBL)
     done
     if [ -z "$FND" ]
     then
       VERBOSITY "No measurement kit(s) with pattern '$TMP' not found." 
       break
     fi
     for TBL in $($MYSQL -e "SELECT CONCAT(project,'_',serial) FROM Sensors WHERE active" | grep -P "$TMP")
     do
       if echo "${KITS[@]}" | grep -q $TBL
       then
         ACTIVE+=($TBL)
       fi
     done
   done
   if [ -n "$1" ] ; then return ; fi
   declare -a TBL
   TBL=$($MYSQL -e 'SHOW tables like "%_%"' | grep -P '[A-Za-z]{3,}_[A-Za-z0-9]{6,}')
   TBLS=$($MYSQL -e 'SELECT CONCAT(project,"_",serial) FROM Sensors' | sort | uniq)
   for TMP in ${TBL}
   do
     if echo "${TBLS}" | grep -q "$TMP"
     then
       KITS+=($TMP)
     else
       VERBOSITY "Table $TMP not in Sensors"
       read -p "Drop this table $TMP? no|[yes] " ANS
       if [ "${ANS:-yes}"  = yes ]
       then
          if $MYSQL -e "DROP TABLE $TMP" ; then echo "Table $TMP removed" ; fi
       fi
     fi
   done
   TBL=$($MYSQL -e 'SELECT CONCAT(project,"_",serial) FROM Sensors WHERE active' )
   for TMP in ${KITS[@]}
   do
     if echo "${TBLS}" | grep -q "$TMP"
     then
       ACTIVE+=($TMP)
     else
       VERBOSITY "Measurement table $TMP is inactive"
       VERBOSITY -n $($MYSQL -e "SELECT count(*) FROM $TMP") "measurements "
       VERBOSITY -n "from " $($MYSQL -e "SELECT datum FROM $TMP ORDER BY datum LIMIT 1")
       VERBOSITY " to " $($MYSQL -e "SELECT datum FROM $TMP ORDER BY datum DESC LIMIT 1")
       read -p "Drop this table $TMP? no|[yes] " ANS
       if [ "${ANS:-yes}"  = yes ]
       then
          if $MYSQL -e "DROP TABLE $TMP" ; then echo "Table $TMP removed" ; fi
       fi
     fi
   done
}

# check if measurements exists and deactivate if needed
function CheckActive() {
   local TBL=$1 TMP

   if ! $MYSQL -e "SHOW TABLES" | grep -q "$TBL" ; then return 1 ; fi
   # check if geohash is available. If end of period = $FROM
   if ! $MYSQL -e "DESCRIBE $TBL" | grep -q -P '^geohash.*varchar'
   then
     VERBOSITY "WARNING active table $TBL has no geo locations column. It is added."
     $MYSQL -e "ALTER TABLE $TBL ADD COLUMN geohash VARCHAR(12) DEFAULT NULL COMMENT 'kit location'"
   fi
   # deactivate this kit if not active anymore
   if echo "${ACTIVE[@]}" | grep -q $TBL  # check only if active: should be active in last 4 months
   then
     TMP=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM $TBL ORDER BY datum DESC LIMIT 1")
     if [ -z "$TMP" ] ; then return 1 ; fi
     VERBOSITY "Last measurement table $TBL is from date $(date --date=@${TMP:-0} +'%y-%m-%d %H:%M')."
     if (( $TMP < $(date --date='3 month ago' +%s) ))
     then
       read -p "Last record from $(date --date=@${TMP:-0} +'%y-%m-%d %H:%M'). Deactivate this active (+website) kit ${TBL/_*/} serial ${TBL/*_/}? no|[yes] " TMP
       if [ "${TMP:-yes}" = yes ]
       then
         TMP=$($MYSQL -e "UPDATE Sensors SET active = 0 WHERE project = '${TBL/_*/}' and serial = '${TBL/*_/}'; SELECT ROW_COUNT()")
         TMP+=$($MYSQL -e "UPDATE TTNtable SET website = 0 WHERE project = '${TBL/_*/}' and serial = '${TBL/*_/}'; SELECT ROW_COUNT()")
         if (( $TMP > 0 ))
         then
           VERBOSITY "Deactivated ${TMP/2/both}."
         else
           VERBOSITY "Website and validity were already invalidated."
         fi
       fi
     fi
   fi
   return 0
}

# get the columns to invalidate
function Valid_Cols() {
    local TBL=$1 VAL=${2:-NULL}
    local COLS
    COLS=$($MYSQL -e "DESCRIBE $TBL" | awk '{ print $1; }' | grep -P '(pm|grain|temp|rv|luchtdruk|gas|aqi).*_valid$' | sed "s/\$/=$VAL/")
    echo $COLS | sed 's/ /,/g'
}
function COLVals() {
    local TBL=$1
    local COLS
    COLS=$($MYSQL -e "DESCRIBE $TBL" | awk '{ print $1; }' | grep -P '(pm|grain|temp|rv|luchtdruk|gas|aqi).*_valid$' | sed 's/.*/ISNULL(&)/')
    echo $COLS | sed 's/ / AND /g'
}

# invalidate measurements in a period of time
function InvalidateVals() {
   local CNT ICOLS
   local FROM=${2:-0} TO=$3 COLS ICOLS LAST

   declare -a TBL="$1"
   TBL=($($MYSQL -e "SHOW TABLES" | grep -P "$TBL") )
   if (( ${#TBL[@]} != 1 ))
   then
     VERBOSITY "Found none or more as one in database: ${TBL[@]}. Improve pattern!"
     return 1
   fi
   if [ "$FROM" = 0 ]
   then 
     VERBOSITY "ERROR Invalidate from date 1970? Skipped"
     return 1
   fi

   if [ -z "$TO" ] ; then TO=$(date --date=tomorrow +%s) ; fi

   ICOLS=$(COLVals $TBL )                  # get condition for all sensors are NULL
   if [ -z "$ICOLS" ] ; then return 1 ; fi # no measurements
   CNT=$($MYSQL -e "SELECT COUNT(*) FROM $TBL WHERE UNIX_TIMESTAMP(datum) >= $FROM AND UNIX_TIMESTAMP(datum) < $TO AND NOT ($ICOLS)")
   if (( ${CNT:-0} > 0 ))
   then                                    # there are sensors in this period to set to NULL
     local ANS
     read -p "Invalidate ${CNT:-0} measurements of table $TBL period $(date --date=@$FROM +'%y-%m-%d %H:%M') up to $(date --date=@$TO +'%y-%m-%d %H:%M')? no|[yes] " ANS
     if [ "${ANS:-yes}" = yes ]
     then                                  # invalidate these sensors to NULL
       # VERBOSITY "Invalidate $CNT measurements table $TBL from $(date --date=@${FROM} +'%y-%m-%d %H:%M') up to $(date --date=@${TO} +'%y-%m-%d %H:%M')"
       COLS=$(Valid_Cols $TBL )
       CNT=0
       CNT=$($MYSQL -e "UPDATE $TBL SET ${COLS}, datum=datum WHERE UNIX_TIMESTAMP(datum) >= $FROM AND UNIX_TIMESTAMP(datum) < $TO;  SELECT ROW_COUNT()")
       if (( $? > 0 ))
       then
         VERBOSITY "ERROR invalidating measurements table $TBL"
         echo 0
         return 1
       else
         VERBOSITY "Invalidated ${CNT:-0} measurement records in datebase table $TBL."
       fi
     else
       VERBOSITY "Rejection: invalidating $CNT measurements of table $TBL"
       CNT=0
     fi
   fi
   CNT=$($MYSQL -e "SELECT COUNT(*) FROM $TBL WHERE UNIX_TIMESTAMP(datum) >= $FROM AND UNIX_TIMESTAMP(datum) < $TO AND $ICOLS")
   if ((  ${CNT:-0} <= 0 )) ; then echo 0 ; return 0 ; fi
   local LAST
   LAST=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM $TBL ORDER BY datum DESC LIMIT 1")
   if (( $TO < ${LAST:-$TO} )) ; then echo ${CNT:-0} ; return 0 ; fi

   # last period, update Sensors valid flag
   local NR=0
   NR=$($MYSQL -e "UPDATE TTNtable SET valid = NULL WHERE project = '${TBL/_*/}' and serial = '${TBL/*_/}';  SELECT ROW_COUNT()")
   if (( $? > 0 ))
   then
     VERBOSITY "ERROR while setting validity to invalid (not at home location) in TTNtable"
   fi
   if (( ${NR:-0} > 0 ))
   then
     VERBOSITY "Set measurements validity to not at home location in TTNtable for ${TBL/_*/} serial ${TBL/*_/}."
   fi
   echo ${CNT:-0}
   return 0
}

# validate measurements in a period of time
# set measurements with valid = NULL (not at home) to valid (correction routine)
function ValidateVals() {
   local CNT ICOLS
   local FROM=${2:-0} TO=$3 COLS ICOLS LAST
   declare -a TBL="$1"
   TBL=($($MYSQL -e "SHOW TABLES" | grep -P "$TBL") )
   if (( ${#TBL[@]} != 1 ))
   then
     VERBOSITY "Found none or more as one in database: ${TBL[@]}. Improve pattern!"
     return 1
   fi
   if ! $MYSQL -e 'SHOW TABLES' | grep -q "$TBL" ; then return 0 ; fi
   if [ -z "$TO" ] ; then TO=$(date --date=tomorrow +%s) ; fi

   ICOLS=$(COLVals $TBL )                  # get condition for all sensors are NULL
   if [ -z "$ICOLS" ] ; then return 1 ; fi # no measurements
   CNT=$($MYSQL -e "SELECT COUNT(*) FROM $TBL WHERE UNIX_TIMESTAMP(datum) > $FROM AND UNIX_TIMESTAMP(datum) <= $TO AND $ICOLS")
   if (( ${CNT:-0} > 0 ))
   then                                    # there are sensors in this period to set to NULL
     local ANS
     read -p "Set (correct) ${CNT:-0} measurements as at home location of table $TBL period $(date --date=@$FROM +'%y-%m-%d %H:%M') up to $(date --date=@$TO +'%y-%m-%d %H:%M')? no|[yes] " ANS
     if [ "${ANS:-yes}" = yes ]
     then                                  # invalidate these sensors to NULL
       # VERBOSITY "Valid reset $CNT measurements table $TBL from $(date --date=@${FROM} +'%y-%m-%d %H:%M') up to $(date --date=@${TO} +'%y-%m-%d %H:%M')"
       COLS=$(Valid_Cols $TBL 1 )
       CNT=0
       CNT=$($MYSQL -e "UPDATE $TBL SET ${COLS}, datum=datum WHERE UNIX_TIMESTAMP(datum) > $FROM AND UNIX_TIMESTAMP(datum) <= $TO;  SELECT ROW_COUNT()")
       if (( $? > 0 ))
       then
         VERBOSITY "ERROR resetting validity of measurements table $TBL"
         echo 0
         return 1
       else
         VERBOSITY "Valid reset of ${CNT:-0} measurement records in datebase table ${TBL}."
       fi
     else
       VERBOSITY "Rejection: validity reset of $CNT measurements of table ${TBL}."
       CNT=0
     fi
   fi
   CNT=$($MYSQL -e "SELECT COUNT(*) FROM $TBL WHERE UNIX_TIMESTAMP(datum) > $FROM AND UNIX_TIMESTAMP(datum) <= $TO AND NOT ($ICOLS)")
   if ((  ${CNT:-0} <= 0 )) ; then echo 0 ; return 0 ; fi
   local LAST
   LAST=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM $TBL ORDER BY datum DESC LIMIT 1")
   if (( $TO < ${LAST:-$TO} )) ; then echo ${CNT:-0} ; return 0 ; fi

   # last period, update Sensors valid flag
   local NR=0
   NR=$($MYSQL -e "UPDATE TTNtable SET valid = 1 WHERE project = '${TBL/_*/}' and serial = '${TBL/*_/}';  SELECT ROW_COUNT()")
   if (( $? > 0 ))
   then
     VERBOSITY "ERROR while setting validity to valid in TTNtable"
   fi
   if (( ${NR:-0} > 0 ))
   then
     VERBOSITY "Set measurements validity to at home location in TTNtable for ${TBL/_*/} serial ${TBL/*_/}."
   fi
   echo ${CNT:-0}
   return 0
}

# update sensors field in Sensors table
function CorrectSensors() {
    local SENSORS
    SENSORS=$($MYSQL -e "SELECT sensors FROM Sensors WHERE project = '${TBL/_*/}' AND serial = '${TBL/*_/}' ORDER BY active DESC, datum DESC LIMIT 1")
    if [ -z "$SENSORS" ] ; then return 0 ; fi

    # lossy check on correcting sensor types 
    # depreciated style temp(C),rv(%),luchtdruk(hPa)... sensor description. Correct it.
    if echo "$SENSORS" | grep -q -P '[a-z][a-z0-9]*\([a-zA-Z0-9%/]{1,}\),'
    then
      VERBOSITY "Sensors table has deprecated sensors description for ${TBL/_/ serial }. Deleted."
      $MYSQL -e "UPDATE Sensors SET sensors = NULL, datum = datum WHERE project = '${TBL/_*/}' AND serial = '${TBL/*_/}'"
    elif echo "$SENSORS" | grep -P -q '(accu|PMS.003.*(SDS|SPS))'
    then   # both is an error, correct it
      VERBOSITY -n "Reset sensors of ${TBL/_*/} serial ${TBL/*_/} from ${SRS} to "
      SENSORS=$(echo "$SENSORS" | sed -e '/PMS.*SDS/s/,PMS.003//' -e '/PMS.*SPS/s/,PMS.003//' -e '/accu/s/\(.*\),accu/ACCU,\1/')
      VERBOSITY "${SENSORS}"
      $MYSQL -e "UPDATE Sensors SET sensors = '$SENSORS', datum = datum WHERE project = '${TBL/_*/}' AND serial = '${TBL/*_/}'"
    fi
    return $?
}

# show kit info with operational status
# optional CSV output on arg2
ListKitHdr=''
function ListKit() {
  local OUTPUT=${2:-/dev/stdout}  # output in CSV format
  
  local TBL=$1 KITinfo="Measurement kit project ${TBL/_*/} serial ${TBL/*_/}"
  # correct geohash long-lat swap
  GeoCorrect $TBL

  ACT="table"
  if echo ${ACTIVE[@]} | grep -q $TBL
  then
    VERBOSITY "$KITinfo is ACTIVE and has DATA table"
  elif echo ${KITS[@]} | grep -q $TBL
  then
    VERBOSITY "$KITinfo is NOT active and has DATA table"
    ACT='table'
    # return
  else
    VERBOSITY "$KITinfo has no DATA table"
    ACT='NO'
    # return
  fi

  # count measurements and last measurement of the table
  local LTMP=';;'
  if $MYSQL -e 'SHOW TABLES' | grep -q "$TBL"
  then # only if  measurements table exists
    local MCNT LAST
    MCNT=$($MYSQL -e "SELECT COUNT(*) FROM $TBL") # get count of all measurements in DB table
    if [ -n "${MCNT/#0/}" ] # get date last measurements from the kit table
    then
      LAST=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM $TBL ORDER BY datum DESC LIMIT 1")
      if [ -n "$LAST" ] ; then LTMP="\"$(date --date=@$LAST +'%y-%m-%d %H:%M')\"" ; fi
    fi
    LTMP=";${MCNT/#0/};$LTMP"
  fi

  # correct sensors field
  CorrectSensors $TBL

  local STMP  # location info
  local QRY


  # check location info
  QRY=$($MYSQL -e "SELECT UNIX_TIMESTAMP(id) FROM Sensors WHERE ISNULL(street) AND project = '${TBL/_*/}' AND serial = '${TBL/*_/}' ORDER BY active DESC, datum DESC LIMIT 1")
  if [ -n "$QRY" ]
  then # has geohash with unknown street correct it
     VERBOSITY "Correcting geohash in Sensors for ${TBL/_*/}/${TBL/*_/} to NULL."
     $MYSQL -e "UPDATE Sensors SET geohash = NULL, datum = datum WHERE UNIX_TIMESTAMP(id) = $QRY"
  fi

  # invalidate measurements if needed and correct meta DB tables Sensors/TTNtable
  local ITMP=';;;;'
  if CheckActive $TBL
  then                 # there are measurements
     # invalidate measurements not at home location in period FROM to 'LAST' date
     declare -a PERIODS
     PERIODS=( $(GetHomePeriods $TBL $FROM $TO) )
     if [ -z "${PERIODS[0]}" ] ; then PERIODS[0]=$(date --date=tomorrow +%s) ; fi
     declare -i I=1 J=2 ICNT=0 VCNT=0
     local LPer Lcnt FPer VPer=${PERIODS[0]}
     while true
     do
       if [ -z "${PERIODS[$I]}" ] ; then break ; fi
       if [ -z "${PERIODS[$J]}" ] ; then break ; fi
       if [ -z "$FPer" ] ; then FPer=${PERIODS[$I]} ; fi
       if (( $VPer < ${PERIODS[$I]} ))
       then  # reset valid for period at home location
         VCNT+=$(ValidateVals $TBL $VPer ${PERIODS[$I]})
       fi
       Lcnt=$(InvalidateVals $TBL ${PERIODS[$I]} ${PERIODS[$J]})
       if [ -n "${Lcnt}" ]
       then
          ICNT+=${Lcnt}
          if (( ${Lcnt} > 0 )) ; then LPer=${PERIODS[$J]} ; fi
       fi
       VPer=${PERIODS[$J]}
       I+=2 ; J+=2
     done
     if (( $VPer < ${PERIODS[-1]} ))
     then  # reset valid for period at home location
       VCNT+=$(ValidateVals $TBL $VPer ${PERIODS[-1]} )
     fi
     if [ -n "$LPer" ] ; then LPer="\"$(date --date=@$LPer +'%y-%m-%d %H:%M')\"" ; fi
     if [ -n "$FPer" ] ; then FPer="\"$(date --date=@$FPer +'%y-%m-%d %H:%M')\"" ; fi
     if (( ${ICNT:-0} > 0 ))
     then
       ITMP=";$FPer;$LPer;${ICNT/#0/};${VCNT/#0/}"
       VERBOSITY "Set for period $FPER up to ${LPER} validity of measurements: $ICNT invalid and $VCNT to valid."
     fi
  fi

  # get meta info from Sensors table
  QRY="SELECT CONCAT(';\"',if(ISNULL(active),'',if(active,'act','no')),'\";\"',if(ISNULL(sensors),'undefined',sensors),'\"',';\"',if(ISNULL(label),'None',label),'\"',';\"',if(ISNULL(street),'None',street),'\"',';\"',if(ISNULL(housenr),'',housenr),'\"',';\"',if( not ISNULL(geohash),round(ST_LongFromGeoHash(geohash),6),''),'\"',';\"',if( not ISNULL(geohash),round(ST_LatFromGeoHash(geohash),6),''),'\"',';\"',if(not ISNULL(geohash),geohash,''),'\"' ) FROM Sensors WHERE project = '${TBL/_*/}' AND serial = '${TBL/*_/}' ORDER BY active DESC, datum DESC LIMIT 1"
  STMP=$($MYSQL -e "$QRY")

  # get meta info from TTNtable
  local TTMP  # TTN info
  QRY="SELECT CONCAT(';\"',if(ISNULL(TTN_app),'None',TTN_app),'\"',';\"',if(ISNULL(TTN_id),'None',TTN_id),'\"',';\"',if(ISNULL(valid),'No',if(valid,'true','false')),'\"',';\"',if(ISNULL(website),'None',if(website,'true','')),'\"',';\"',if(ISNULL(luftdaten),'None',if(not ISNULL(luftdatenID),luftdatenID,serial)),'\"') FROM TTNtable WHERE project = '${TBL/_*/}' AND serial = '${TBL/*_/}' LIMIT 1"
  TTMP=$($MYSQL -e "$QRY")
  if [  -z "$TTMP" ] ; then TTMP=";;;;;" ; fi

  # generate collected info as CSV row
  echo "\"${TBL/_*/}\";\"${TBL/*_/}\";\"$ACT\"${STMP}${TTMP}${LTMP}${ITMP}" >>${OUTPUT}
  return 0
}

ACTIVE=()  # active measurement kits
KITS=()    # list of measurement tables
# optional settings via environment

function UpdateValidity() {
    local ListKitHdr TBL
    #  main routine: OUTPUT defines CSV file iso std out for administrative info
    #  arguments expression to identify measurements tables, dflt all kits in Sensors
    #  and/or has measurmeents (measurement table).
    #  measurement table is looked up in Sensors database table:
    #  is it active, is measurement table existant
    if [ -n  "$OUTPUT" ] ; then OUTPUT+="-$(date +%Y%m%d).csv" ; fi
    # get list of measurement tables

    GetTables  $@  # obtain list of kits: active, not active, has measurements

    # header for CSV file
    if [ -n "${KITS[0]}" -a ! -f "$OUTPUT" ]
    then
      cat <<EOF
Administrative overview of administered measurements eg kit name, location, ...
Attempt has been made in the provided period to measurements when kit is not at home location.
Overview of the MySense kits (DB tables) identified by:
    ${kits[@]:-all registered measurement kits}.
Date of overview: $(date).

EOF
      ListKitHdr='"project";"serial";"data table";"active?";"sensors"'
      ListKitHdr+=';"label";"street";"near nr";"long";"lat";"geohash"'
      ListKitHdr+=';"TTN app";"TTN ID";"at home?";"webpage?";"Sensors.Com ID"'
      ListKitHdr+=';"#measurements"'
      ListKitHdr+=';"last at"'
      if [ "$FROM" = 0 ]
      then  ListKitHdr+=';"";"";"";""'
      else  ListKitHdr+=';"invalidated from";"up to";"#invalids";"#valids"'
      fi
      echo "$ListKitHdr" >>${OUTPUT}
    fi

    # give administrative info, drop unadminsitered measurement tables,
    # update validity of measurements in measurements table and validity in TTNtable
    # DB changes will only be done interactively ([yes]/no).
    # RDBHOST will define host for the search of from which date search for validity
    # will start.
    # if not defined as environment the environment var FROM is used as start timestamp
    # default (FROM is undefined): no validity check is done.
    # FROM maybe Posix sec timestamp or date cmd date format (--date='string').
    for TBL in ${KITS[@]}
    do
      ListKit $TBL ${OUTPUT} # measurements validatity check for one kit
    done
    if [ -n "$OUTPUT" ] ; then VERBOSITY "Info in CVS output on $OUTPUT" ; fi
}

# main part args: 
if [ "${1/--/}" = help ]
then
   cat <<EOF
To drop measurement tables and meta info row in meta tables
Command 'dropit args' (args: project serial ...) serial is reg exp kits to check to delete

To set values in a period as valid: environment var FROM up to TO (default tomorrow)
command 'validate args' (args project_<reg. exp.>)

To set values in a period as invalid: environmenmt FROM up to TO (default tomorrow)
command 'invalidate args' (args project_<reg.exp.>)

To update measurements tables (invalid/valid in a period) and update meta info
command 'args': reg expression for kits to show and check
              (FROM=timestamp) meta kit info

Environment variables:
Period definition either via environment FROM (default no period) up to TO (flt tomorrow)
If RDBHOST is defined use mysql measurement table from this host to define FROM
If FROM nor RDBHOST is defined update will only show meta info for project/serial kits.
EOF
    exit 0
fi
if [ -n "$FROM" ] && ! echo "$FROM" | grep -q -P '^[0-9]{6,}$'
then
    FROM=$(date --date="$FROM" +%s)
    if (( $? > 0 ))
    then
    	echo "From $FROM is not a date!" 1>&2
    	exit 1
    fi
fi
if [ "${1,,}" = dropkit ]
then
   shift
   while [ -n "$1" -a -n "$2" ]
   do
      DropKit "$1" "$2"
      shift ; shift
   done
elif [ "${1,,}" =  validate ]
then
    shift
    if [ -z "$FROM" ]
    then VERBOSITY "ERROR need definition of FROM env. var."
    else
      while [ -n "$1" ]
      do
        ValidateVals "$1" "$FROM" >/dev/null
	shift
      done
    fi
elif [ "${1,,}" =  invalidate ]
then
    shift
    if [ -z "$FROM" ]
    then VERBOSITY "ERROR need definition of FROM env. var."
    else
      while [ -n "$1" ]
      do
        InvalidateVals "$1" "$FROM" >/dev/null
	shift
      done
    fi
else
   UpdateValidity $@
fi
