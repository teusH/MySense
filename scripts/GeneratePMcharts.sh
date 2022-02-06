#!/bin/bash
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
# 
# Copyright (C) 2018, Behoud de Parel, Teus Hagen, the Netherlands
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# $Id: GeneratePMcharts.sh,v 1.14 2020/10/07 06:09:27 teus Exp teus $

if [ "${1/*-h*/help}" == help ]
then
    echo "
    Script to generate measurement PM HighCharts chart HTML page for sensor kits of a project
    Script will notify by email non active sensor kits as well.
    If defined also AQI data will be updated on website page  via updateAQI bash script.
    Destination of HighCharts HTML page part: serialnr.html and PROJECT_Overview.html
    in directory WEBHOST:DIR/[Meetkits/]REGION.
    Script will synchronize official station measurements tables from WEBHOST to DBHOST.

    Environment variables definitions and defaults:
    need DB credentials to access measurement Database DB{USER,HOST,PASS}
          Default: $USER, localhost, ask interactive PASS
    REGION defines region and project, kit serials, avoid kits, last day, etc.
         Default REGION=BdP
    START defines from which date graphs should start. Understands date option.
         Default: START='3 weeks a go'
    LAST defines date of graphs upto LAST. Understands 'date' arguments.
         Default LAST=now
    WDIR working directory. Default /webdata/luchtmetingen/
          Generated files will temporary reside in WDIR/tmp
    DIR directory where webfiles base reside.
         Default /webdata/Drupal/cmsdata/BdP/files/luchtmetingen
    KITsns DB tables to generate graphs for
         Default: scan DB for project REGION tables which kits are active
    UPDATE_AQI Update air quality index values on website.
         Default: no AQI/LKI updates. This needs update script (script depends on AQI.pl).
    VERBOSE=1 be more versatile. Default 0 none.
          0 none, 1 print actrive kit tables, 2 print inactive tables also, 3 print all details
    WEBSITE Only those kits which are published on website. Default: ' AND website'
         enabled in TTNtable DB table. Disable this via 'WEBSITE=false'.
    DEBUG: Debug modus do not copy graphs to destination. Generate full HTML.
    mysql will take passwords from user mysql config file via login-path argument.
    
    run example:
    DBUSER=name DBHOST=localhost DBPASS=acacadabra REGION=BdP WEBHOST=localhost
         GeneratePMcharts.sh  [all|kits|overview]
    default all: all kits in region and overview charts of all kits in region
    in one html page.
    NODRUSH='' If NODRUSH=1 run Drush cache clean on WEBHOST webserver.
" 1>&2
    exit 0
fi
COMMAND=
WEBSITE=${WEBSITE:-' AND website'}  # only those in TTNtable table and published
for C in $*
do
   case "$C" in
      kits) COMMAND+=' KITS'
   ;;
      overview) COMMAND+=' OVERVIEW'
   ;;
   esac
done
if [ -z "$COMMAND" ] ; then COMMAND='KITS OVERVIEW' ; fi

# MySQL database credentials
# will use here mysql --login-path=luchtmetingen as well!
DEBUG=${DEBUG}
if [ -n "$DEBUG" ] ; then DEBUG='-d -v' ; fi  # generate file as browsable HTML
CMD=GeneratePMcharts
export DB=${DB:-luchtmetingen}
export DBUSER=${DBUSER:-$USER}
export DBHOST=${DBHOST:-localhost}
if [ -z "$DBPASS" ]
then
    read -p "Provide password for database $DB on host $DBHOST user $DBUSER: " DBPASS
fi
export DBPASS=${DBPASS:-accacadabra}
# how to approach MySQL database. Uses mysql DB configuration in home user
# needs ~/.my.cnf
MYSQL="mysql --login-path=${DB:-luchtmetingen} -h ${DBHOST:-localhost} -N -B --silent ${DB:-luchtmetingen}"

KITsns=${KITsns}      # GetKits will assign values to array of sensor kits for charts
VERBOSE=${VERBOSE:-0}
if [ -n "$DEBUG" ] ; then VERBOSE=3 ; fi
# AQI update feature
UPDATE_AQI=${AQI}
# REGIONs: BdP (HadM), GLV (Venray), NULL or VW17 (Vuurwerk2017 Venlo)
#REGION=${REGION:-BdP}  # use REGION to be prepended to generated HTML file name
if [ -z "$REGION" ]
then
    read -p 'Choose region to generate PM charts for: ' REGION
fi
WEBHOST=${WEBHOST:-lunar}       # host where webfiles reside
if [ -z "$LAST" ] || ! date --date="$LAST" >/dev/null # last date to show in graphs
then
  LAST=now       # use measurement data up to $LAST
fi
if [ -n "$START" ] && date --date=$START
then
    START="$(date --date='$START' '+%Y/%m/%d %H:%M')"
else
    START="$(date --date='3 weeks ago' '+%Y/%m/%d %H:%M')" # only last 3 weeks from now
fi
#START="$(date --date='494 days ago' '+%Y/%m/%d %H:%M')" # only last 3 weeks from now

WDIR=${WDIR:-/MySense/scripts}    # working directory
TMPWDIR=${WDIR}/tmp                         # temporary dir for generated files
# website target directory
DIR=${DIR:-/webdata/Drupal/cmsdata/BdP/files/luchtmetingen} # webpage files reside here
# avoid table names matching in average regio calculations
AVG_AVOID=xyz

# GENERATOR=${GENERATOR:-${WDIR}/ChartsPM.pl -j} # script to generate webpage with chart
# default arguments for GENERATOR
# FIRST='-f'
MYREGION=''    # name of region for chart
POLLUTANTS='pm10|pm25|pm1,pm25|rv|temp' # pollutants shown in chart
SENSORTYPES='PM,Meteo'              # buttons to select graph
CORRECTION=''           # apply correction to wards a ref sensor XYZ
REFERENCE=''   # reference station, dflt HadM
REMOVE_SPIKES='pm1,pm25,pm10,rv,temp'
SPIKES_CMD=FilterShow.py
#SPIKES_OPT="-q --adjustPM"
SPIKES_OPT="-q"
# default pollutants for chart webpage with overview of all sensor kits 
#POLs=pm25
POLs=pm25,pm10
AVOID=none
AVOID_METEO='avoid these kits for meteo'
MAILTO=teus@lunar.theunis.org         # email address to send inactive sensor kits notices
# send event to slack notification forum
#SLACK='https://hooks.slack.com/services/TGA1TNDDFG7CPH/BG8Z/AOJRkKxdYK1QpNRBwufylWl0'
declare -i CNT=0  # count generated graph pages of stations

function filterPM() {
    local KITS="$1"
    local KIT
    if [ -z "$1" ] ; then return ; fi
    for  KIT in $KITS
    do
        echo "SELECT IF( (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE (COLUMN_NAME = 'pm10' or COLUMN_NAME = 'pm25') and TABLE_NAME = '$KIT') > 0, '$KIT','');"
    done | $MYSQL | tr "\n" " "
}

# get all sensor kits of a project and cache selected kits under an ID
# currently project (and so serial) ID is used to select measurement kits from DB
# however the usage is region oriented. ToDo: support other selection criteria.
# command arguments: ID [pattern] where ID probably is a project id
declare -A Kits4PROJ  # cache kits
function GetKits() {
    local KIT TBL_KITS SENS_KITS
    local PTRN="$2"
    if [ -z "$PTRN" ] ; then PTRN="$1" ; fi
    local TBL=TTNtable
    if [ "$WEBSITE" = 'false' ] ; then TBL=Sensors ; WEBSITE='' ; fi
    local ID="${1:-all}"
    PTRN="${PTRN:-\[A-Za-z\]+}" # all projects
    if [ -n "${PTRN/*_*/}" ]
    then
        PTRN+='_[A-Fa-f0-9]{8,}'   # all serials in selected project
    fi
    if [ -z "${Kits4PROJ[$ID]}" ]
    then
        # need to delete new lines eg via tr command
        # get kits with table data values
        TBL_KITS=$($MYSQL -e "SHOW TABLES LIKE '%\_%'" | grep -P "$PTRN" | tr "\n" " ")
        if [ -n "$TBL_KITS" ]
        then # get kits from Sensors table withg meta definition eg for website graphs
            # seems MySQL distinct is case insensative
            # get kits which are on the website
            SENS_KITS=$($MYSQL -e "SELECT CONCAT ( project,'_',serial ) FROM $TBL WHERE not ISNULL(project) AND serial REGEXP '[0-9a-fA-F]{8,}'$WEBSITE" | sort | uniq | grep -P "$PTRN" | tr "\n" " ")
        fi
        # get common set (thank you python) of usefull measurement kits
        # only <proj>_<serial hex> names, delete (test) kits to be avoided
        Kits4PROJ[$ID]=$(python -c "for x in set('$TBL_KITS'.split()) & set('$SENS_KITS'.split()): print(x)" | grep -P -v "$AVOID" | tr "\n" " ")
        Kits4PROJ[$ID]=$(filterPM "${Kits4PROJ[$ID]}") # only kits with PM10 and/or PM25
        if [ -z "${Kits4PROJ[$ID]}" ]
        then
            echo "$CMD WARNING: unable to find the sensor kits for project $1" 1>&2
            Kits4PROJ[$ID]=' '
        fi
    fi
    echo ${Kits4PROJ[$ID]}
}

# collect tables for active kits last 24 hours with minimal 10 measurements
# optional 1 arg>: LAST (dflt now) minus 24 hours
function GetActiveKits() {
   local TBL
   local DQRY
   local PR=$1 ; shift
   local T="$1"
   if [ -z "$1" ]
   then T=$(date --date="$LAST" '+%Y/%m/%d %H:%M')
   else T=$(date --date="$1" '+%Y/%m/%d %H:%M')
   fi
   if [ -z "$T" ]
   then
        echo "$CMD ERROR: begin-start time \"$1\" definition error" 1>&2
        exit 1
   fi
   if [ -z "$2" ]
   then
       DQRY="datum > date_sub('$T', interval 1 day)"
   else
       DQRY="datum >= '$T'"
       T=$(date --date="$2" '+%Y/%m/%d %H:%M')
       if [ -z "$T" ]
       then
            echo "$CMD ERROR: begin-start time \"$2\" definition error" 1>&2
            exit 1
       fi
       DQRY+=" AND datum <= '$T'"
   fi

   local TBLS=$(GetKits ${PR})
   for TBL in $TBLS
   do
      echo "SELECT IF( (SELECT count(datum) FROM $TBL WHERE ( not isnull(pm10) OR not isnull(pm25) ) AND ${DQRY}) >= 10, '$TBL','');"
   done | $MYSQL | tr "\n" " "
}

# collect tables for inactive kits in last 24 hours with minimal 10 measurements
function GetInactiveKits() {
   local TBL
   local TLAST=$(date --date="$LAST" '+%Y/%m/%d %H:%M')
   for TBL in $(GetKits ${PR})
   do
      echo "SELECT IF( (SELECT count(datum) FROM $TBL WHERE ( not isnull(pm10) OR not isnull(pm25) ) AND datum > date_sub('$TLAST', interval 1 hour)) < 1 , '$TBL', '');"
   done | $MYSQL 2>/dev/null | tr "\n" " "
}

# synchronize DB tables with governmental stations measurements
declare -A LastRecords
function SYNC2DBHOST() {
    local RDBHOST=${1:-$WEBHOST}
    shift
    if [ "$DBHOST" = "$RDBHOST" ] ; then return 0 ; fi
    if ! ping4 -c 1 -W 5 -q $RDBHOST >/dev/null
    then
       echo "ATTENT: host $RDBHOST is not up and running."  1>&2
       return 1
    fi
    local LAST RTS=0
    local TBL CREATE='--no-create-info'
    for TBL in $*
    do
        if [ -n "${LastRecords[$TBL]}" ] ; then continue ; fi
        LastRecords[$TBL]=$($MYSQL -e "SELECT UNIX_TIMESTAMP(id) FROM $TBL ORDER BY id DESC LIMIT 1")
        if (( $? > 0 ))
        then
            echo "ERROR: no table $TBL on $DBHOST" 1>&2
            LastRecords[$TBL]=$(date +%s)  # up to date
	    RTS=1 ; continue
        elif [ -z "${LastRecords[$TBL]}" ]
        then
	    CREATE=''
	    LastRecords[$TBL]=0
	    echo "WARNING: create new table $TBL" 1>&2
        fi
        LAST=$(${MYSQL/$DBHOST/$RDBHOST} -e "SELECT UNIX_TIMESTAMP(datum) FROM $TBL WHERE UNIX_TIMESTAMP(id) > ${LastRecords[$TBL]} ORDER BY id DESC LIMIT 1")
        if (( $? > 0 ))
        then
            echo "ERROR: on table $TBL on host $WEBHOST" 1>&2
            RTS=1 ; continue
        fi
        if [ -z "$LAST" ] ; then continue ; fi
        if (( $LAST <= ${LastRecords[$TBL]} )) ; then continue ; fi
        if ! mysqldump --login-path=${DB:-luchtmetingen} -h ${RDBHOST:-localhost} --no-create-info --column-statistics=0 ${DB:-luchtmetingen} ${TBL} --where="UNIX_TIMESTAMP(id) > ${LastRecords[$TBL]}"  | $MYSQL # >/var/tmp/$RDBHOST-$$.sql
	then
	    echo "ERROR: synchronisation $RDBHOST to $DBHOST for $TBL failed." 1>&2
	    RTS=1
	fi
        LastRecords[$TBL]=$LAST
    done
    return $RTS
}
# SYNC2DBHOST $WEBHOST HadM NL10131 NETT

function SetParameters() {
    local REGIO=${1:-HadM}
    # what to do for different regions and which kits
    # collect details for kits to generate PMcharts per project
    case ${REGIO^^} in
    VENRAY|GLV)    # Gezond Leefmilieu Venray
        # deprecated
        GENERATOR="${WDIR}/ChartsPM.pl -j"   # script to generate webpage with chart
        REGION=GLV
        STATIONS=${STATIONS:-HadM NETT} # add reference stations, HadM is always included 
        PROJ=${PROJ:-GLV}_   # use this as project identifier, may well be a perl reg exp
        AVOID='(f07df1c50[2-57-9]|93d73279dd)'
        MYREGION='-r Venray'
        REFERENCE='-R NL10131'
        CORRECTION=''   # no correction to sensor type
    ;;
    WANROIJ|STANTHONIS|SAN|BWL[vV]C)  # St. Anthonis, Wanroij, etc. (Boxmeer)
        GENERATOR="${WDIR}/ChartsPM.pl -j"   # script to generate webpage with chart
        REGION=SAN
        STATIONS=${STATIONS:-NL10131} # add reference stations, HadM is always included 
        PROJ=${PROJ:-SAN}_   # use this as project identifier, may well be a perl reg exp
        POLLUTANTS='pm10|pm25|pm1,rv|temp|luchtdruk' # pollutants shown in chart
        #AVOID='_(?!30aea45059|f07df1c50|93d73279dc)'  # avoid all but
        #AVOID='_(?!30aea450(59|9e)|3c71bf876dbc|b4e62df55731|f07df1c50|e101f76c60|807d3a93(5cb8|9eb4|76dc))'  # avoid all but
        AVOID='(30aea4505988)'      # avoid old SDS011 kit Tonnie
        AVG_AVOID="(cc50e39c7500|b4e62df49ca5|30aea4509eb4)"  # avoid test kits in avg count
        REFERENCE='-R NL10131'
        UPDATE_AQI=1   # update LKI index for the kits in this region/project
        START="$(date --date='1 July 2020' '+%Y/%m/%d %H:%M')"
        CORRECTION='--type SPS30'  # apply correction to dust sensor SPS30
    ;;
    KIPSTER|OIRLO|KIP)
        GENERATOR="${WDIR}/ChartsPM.pl -j"   # script to generate webpage with chart
        POLLUTANTS='pm10|pm25|pm1,rv|temp|luchtdruk|prevrain|wind' # pollutants shown in chart
        # POLLUTANTS='pm10|pm25|pm1,rv|temp|luchtdruk|prevrain' # pollutants shown in chart
        SENSORTYPES='PM,Meteo'              # buttons to select graph
        POLs=pm10,pm25,pm1
        REGION=KIP
        STATIONS=${STATIONS:-NL0131} # add reference stations
        PROJ=${PROJ:-KIP}_ # use this as project identifier
        #AVOID='_(?!D54990(6DC049|0C6C33)|30aea4505(9f9|a00|a01|a03|a04)|130aea4ec9e2|788d27294ac5)' # avoid all but
        CORRECTION='--type SPS30'  # apply correction to dust sensor SPS30
        REFERENCE='-R NL10131'
        # METEO="${PROJ}CECEA5167524"               # use for meteo data this table
        # METEO_AVOID="(788d27294ac5|130aea4ec9e2)" # do not use meteo table for these ones
        AVG_AVOID="(788d27294ac5|130aea4ec9e2)"  # avoid kantine/werl kit in avg count
        # START="$(date --date='720 hours ago' '+%Y/%m/%d %H:%M')"
        START="$(date --date='4 May 2020' '+%Y/%m/%d %H:%M')"
        UPDATE_AQI=1   # update LKI index for the kits in this region/project
    ;;
    HORST|GRUBBENVORST|BDP|HADM)  # Horst aan de Maas Behoud de Parel
        GENERATOR="${WDIR}/ChartsPM.pl -j"   # script to generate webpage with chart
        REGION=HadM
        STATIONS=${STATIONS:-NL10131 NETT} # add reference stations, HadM is always included 
        PROJ=${PROJ:-HadM}_   # use this as project identifier, may well be a perl reg exp
        #AVOID='_(?!30aea4505888|30aea45075e4|30aea44e1934)'  # avoid all but
        UPDATE_AQI=1   # update LKI index for the kits in this region/project
        CORRECTION='--type SPS30'  # apply correction to dust sensor SPS30
    ;;
    RIVM|[CK]ALIBR*|VREDEPEEL)  # calibratie tests Vredepeel
        GENERATOR="${WDIR}/ChartsPM.pl -j -x 120"   # script to generate webpage with chart
        REGION=RIVM
        # POLs=pm10,pm25,pm1
        STATIONS=${STATIONS:-NL0131} # add reference stations, HadM is always included 
        PROJ=${PROJ:-RIVM}_   # use this as project identifier, may well be a perl reg exp
        #AVOID='_(?!30aea4505888|30aea45075e4|30aea4ec7cf8)'  # avoid all but
        REFERENCE='-R NL10131'
        UPDATE_AQI=1   # update LKI index for the kits in this region/project
        START="$(date --date='4 May 2020' '+%Y/%m/%d %H:%M')"
        #LAST="$(date --date='1 Jan 2021' '+%Y/%m/%d %H:%M')"
        CORRECTION=''   # no correction to sensor type
    ;;
    *)
        echo "$CMD FATAL: region '$REGIO' is unknown!" 1>&2
        exit 1
    ;;
    esac
    #DIR=${DIR}/$REGION # webpage files reside here
    if [ -n "$UPDATE_AQI" ]
    then
        if [ -x $WDIR/updateAQIwebsite.sh ]
        then
            UPDATE_AQI=$WDIR/updateAQIwebsite.sh
        else
            echo "WARNING: No $WDIR/updateAQIwebsite.sh executable found. Skipping AQI website updates." 1>&2
            UPDATE_AQI=''
        fi
    fi
}

function SendNotification() {
    if [ -z "$SLACK" ] ; then return ; fi
    if [ -z "$1" ] ; then return ; fi
    if [ ! -x /usr/bin/curl ] ; then return ; fi
    local CNTT='{"text": "Automatic notification. Attention malfunctioning MySense kit: ' CEND='"}'
    CCNT=$(/usr/bin/curl -X POST -H 'Content-type: application/json' --data "$CNTT$1$CEND" --silent --show-error "$SLACK")
    if [ "$CCNT"x = okx ] ; then return 0 ; else echo "$CCNT" ; return 1 ; fi
}

QRY=''
# pollutants to see if sensor kit is active
POLS='pm10 pm25 pm1 rv temp luchdruk prevrain ws wr wind'
# query generator to get stats of sensors for the TABLE (arg1)
function GenerateQRY() {
    local POL
    local MyPOLS=
    for POL in $($MYSQL -e "describe ${1}" | awk '/_valid/{ print $1; }' | sed 's/_valid//' | grep -P "(${POLS// /|})")
    do
        if (( $($MYSQL -e "SELECT count($POL) FROM ${1} WHERE not isnull($POL)") > 0 ))
        then
            MyPOLS+="$POL "
        fi
    done
    if [ -z "$QRY" ]
    then
        local TLAST=$(date --date="$LAST" '+%Y/%m/%d %H:%M')
        for  POL in $MyPOLS
        do
            if [ -z "$QRY" ] ; then QRY="SELECT CONCAT('time=',UNIX_TIMESTAMP('$TLAST')" ; fi
            QRY+=",' ${POL}=',COUNT(${POL})"
        done
        QRY+=") FROM ${1} WHERE datum > SUBTIME('$TLAST', '1:00:00.000000')" # one hour
    fi
    echo "$QRY"
    return
}
# generate QRY for last measurement
LQRY=''
function GenerateQRYlast() {
    local POL
    local MyPOLS=
    # if [ -z "$LQRY" ]
    # then
        for POL in $($MYSQL -e "describe ${1}" | awk '/_valid/{ print $1; }' | sed 's/_valid//' | grep -P "(${POLS// /|})")
        do
            MyPOLS+="$POL "
        done
        for  POL in $MyPOLS
        do
            if [ -z "$LQRY" ]
            then LQRY="SELECT UNIX_TIMESTAMP(datum) FROM TBL WHERE"
            else LQRY+=" OR"
            fi
            LQRY+=" not ISNULL($POL)"
        done
        LQRY+=" ORDER BY datum DESC LIMIT 1" # one hour
    # fi
    echo "$LQRY" | sed "s/TBL/${1}/g"
    return
}

# check if kit is active for dflt last 30 days
function IsActive() {
    declare -i PERIOD=$(date "--date=${2:-30} days ago" +%s) CNT=0
    CNT=$($MYSQL -e "SELECT count(*) FROM Sensors WHERE serial ='${1/*_/}' AND active")
    if (( ${CNT:-0} > 0 ))
    then
       CNT=$($MYSQL -e "SELECT count(datum) FROM ${1} WHERE datum > FROM_UNIXTIME($PERIOD);")
       if (( $CNT > 0 ))
       then
          return 0
       fi
    fi
    return 1
}

# send email if sensorkit is not seen quite active for a period of time (dflt one hour)
# minimal 5 measurements per hour, no measurements in one hour special warning
function CheckActive() {
    local MSG='' NME POLSMSG='Last one hour had number of measurements for '
    declare -i MAX=-1 MIN=100 SECS=$(date +%s) RTS=0 MLAST=0 CNT=0
    if (( $VERBOSE < 1 )) ; then return 0 ; fi
    if [ -n "${1/*_*/}" ] ; then return 0 ; fi # not a project sensor kit table
    CNT=$($MYSQL -e "SELECT count(*) FROM Sensors WHERE serial ='${1/*_/}' AND active")
    if (( ${CNT:-0} <= 0 )) ; then return 0 ; fi  # not active any more
    for NME in $($MYSQL -e "$(GenerateQRY $1)")
    do
        if [ "${NME/=*/}" = time ]
        then
            SECS=${NME/*=/}
            continue
        elif [ "${NME/=*/}" = prevrain ]
        then
            continue
        fi
        if (( ${NME/*=/} < $MIN )) ; then MIN=${NME/*=/} ; fi
        if (( ${NME/*=/} > $MAX )) ; then MAX=${NME/*=/} ; fi
        POLSMSG+="$NME, "
    done
    if (( $MAX < 1 ))
    then
        MLAST=$($MYSQL -e "$(GenerateQRYlast $1)") # get time last seen
        if (( ($MLAST + 10*60*60) < $(date --date="$LAST" '+%s') ))
        then
            return 1 # already warned the disactivity enough
        fi
	MSG="\nLast date/time of activity was: $(date --date=@$MLAST '+%x %X'). (MIN=$MIN, MAX=$MAX)."
        RTS=1
        # no measurements at all
    elif (( $MAX < 2 )) && (( $VERBOSE > 1 ))
    then
        MSG="Date/Time: $(date --date=@$SECS '+%x %X'). Seems sensor kit has been inactive for the last hour (MIN=$MIN, MAX=$MAX).$MSG"
    elif (( ($MAX - $MIN) > 5 ))
    then
        MSG="Date/Time: $(date --date=@$SECS '+%x %X'). Seems sensor kit has at least one sensor less functioning in the last hour (MIN=$MIN, MAX=$MAX)."
    else
        return 0
    fi
    echo -e "$MSG\n$POLSMSG" | \
        if [ -n "${MAILTO}" ]
        then
            mail -s "Sensor kit ${1/*_/} of project ${1/_*/} needs attention" -- ${MAILTO}
        else
            echo "$CMD ATTENT: Sensor kit ${1/*_/} of project ${1/_*/} needs attention"
            cat
        fi
        # SendNotification "Attention only. Sensor kit ${1/*_/} of project ${1/_*/} seems does not send data for more as one hour and probably needs attention!"
    return $RTS
}

function DoOnePMchart() {
    local ThisKIT=$1
    if [ -z "$1" ] ; then return ; fi

    if ! CheckActive ${ThisKIT} 30
    then
	echo "$CMD ATTENT: DB table ${ThisKIT}, kit not active. Skipped." 1>&2
	return
    elif (( $VERBOSE > 0 ))
    then
        echo "$CMD MESG: measurement DB table: ${ThisKIT}" 1>&2
    fi

    if [ -x "$UPDATE_AQI" ]  # update AQI values on website page for this kit
    then
        if [ -z "$DEBUG" ]
        then
	    # NODRUSH=1 do not run drush cache flush on website
            VERBOSE=${VERBOSE} NODRUSH=${NODRUSH} WEBHOST=${WEBHOST:-lunar} DEHOST=${DBHOST:-localhost} DBWeb=${DBWeb:-parel7} DBaq=${DB:-luchtmetingen} $UPDATE_AQI ${ThisKIT}
        else
            echo "No run in debug modus: VERBOSE=${VERBOSE} DBWeb=${DBWeb:-parel7} DBaq=${DB:-luchtmetingen} $UPDATE_AQI ${ThisKIT}" 1>&2
        fi
    fi

    if [ -x "$SPIKES_CMD" ] && [ -n "$REMOVE_SPIKES" ] # update removal of spikes
    then
        if (( $VERBOSE > 1 )) ; then SPIKES_OPT="${SPIKES_OPT/-q/}"; fi
        if [ -n "$DEBUG" ] ; then SPIKES_OPT+=' -d'; fi
        # for start to delete --startPM '2 years ago'
        if ! DBHOST=${DBHOST:-localhost} python3 "$SPIKES_CMD" $SPIKES_OPT ${ThisKIT}/"$REMOVE_SPIKES" 2>&1 | tee /var/tmp/spikes$$
        then
            echo "$CMD ERROR: failed to exec $SPIKES_CMD $OPT ${ThisKIT}/$REMOVE_SPIKES" 1>&2
        fi
        if [ -s /var/tmp/spikes$$ ]
        then
            echo "$CMD fail while exec $SPIKES_CMD $SPIKES_OPT ${ThisKIT}/$REMOVE_SPIKES" 1>&2
        fi
        rm -f /var/tmp/spikes$$
    fi

    if [ -z "$GENERATOR" ] ; then return 0 ; fi
    # /home/teus/BehoudDeParel/luchtmetingen/IoS/BdP/PMcharts-website/ChartsPM.pl -w /webdata/Drupal/cmsdata/BdP/files/luchtmetingen/BdP/ -d -v -c -e "pm10|pm25,pm10|rv|temp" -b PM,Meteo -O 30aea4505888 -R HadM -L now HadM_30aea4505888
    if [ -n "$METEO" ] # maybe use alternative meteo data
    then
        if ! echo "${ThisKIT}" | grep -q -P "$AVOID_METEO"
        then AMETEO="-m $METEO"
        fi
    fi
    rm -f "$TMPWDIR/${ThisKIT/${PROJ}/}.html"
    if ! perl $GENERATOR $MYREGION $LNG --alias "http://behouddeparel.nl/" $DEBUG -w "$TMPWDIR/" -e "$POLLUTANTS" -b "$SENSORTYPES" -S "$START" -O ${ThisKIT/${PROJ}/} $REFERENCE $CORRECTION -L "$LAST" $FIRST $AMETEO ${ThisKIT} 2>$TMPWDIR/ERRORS # Ref is HadM
    then # ERROR
        date 1>&2
        echo "Using command arguments: $MYREGION $LNG --alias 'http://behouddeparel.nl/' $DEBUG -w '$TMPWDIR/' -e '$POLLUTANTS' -b '$SENSORTYPES' -S '$START' -O ${ThisKIT/${PROJ}/} $REFERENCE -L '$LAST' $FIRST $AMETEO ${ThisKIT}" 1>&2
        echo "$CMD WARNING: $GENERATOR failed to generate $TMPWDIR/${ThisKIT/${PROJ}/}.html for chart" 1>&2
        echo "$CMD $GENERATOR ERRORS:" 1>&2
        cat $TMPWDIR/ERRORS 1>&2
        rm -f $TMPWDIR/ERRORS
        return
    fi
    if [ ! -f $TMPWDIR/${ThisKIT/${PROJ}/}.html ]
    then
        date
        if (( $VERBOSE > -1 ))
        then
            echo "$CMD $GENERATOR ERRORS:" 1>&2
            cat $TMPWDIR/ERRORS 1>&2
        fi
        echo "Using: $GENERATOR $MYREGION $LNG --alias 'http://behouddeparel.nl/' $DEBUG -w '$TMPWDIR/' -e '$POLLUTANTS' -b '$SENSORTYPES' -S '$START' -O ${ThisKIT/${PROJ}/} $REFERENCE -L '$LAST' $FIRST $AMETEO ${ThisKIT}" 1>&2
        echo "$CMD WARNING: $GENERATE failed to generate file $TMPWDIR/${ThisKIT/${PROJ}/}.html for chart" 1>&2
        rm -f $TMPWDIR/ERRORS
        return
    elif [ -n "$DEBUG" ] || (( $VERBOSE > 2 ))
    then
        cat $TMPWDIR/ERRORS 1>&2
    fi
    if grep -q -P "(WARNING|ERROR)" $TMPWDIR/ERRORS
    then
        echo "$CMD $GENERATOR ERRORS:" 1>&2
        grep -P "(ERROR|WARNING)" $TMPWDIR/ERRORS 1>&2
    fi
    rm -f $TMPWDIR/ERRORS ; CNT+=1
    if [ -n "$DEBUG" ]
    then
        echo "$CMD: Left generated PMchart file: $TMPWDIR/${ThisKIT/${PROJ}/}.html" 1>&2
        CNT+=1 ; return
    fi

    # copy generated html file to website destination
    if [ "${WEBHOST:-localhost}" != localhost ]   # remote WEBHOST website
    then
        if ! ssh ${WEBHOST} mkdir -p ${DIR}/Meetkits/$REGION
        then
            echo "$CMD ERROR: failed to get access to ${WEBHOST}:${DIR}/Meetkits/" 1>&2
            return
        fi
        ssh ${WEBHOST} chgrp -f www-data $DIR/Meetkits/$REGION
        if ! scp -q $TMPWDIR/${ThisKIT/${PROJ}/}.html ${WEBHOST}:$DIR/Meetkits/$REGION/${ThisKIT/${PROJ}/}.html
        then
            date 1>&2
            echo "$CMD ERROR: failed to copy chart to ${WEBHOST} for ${ThisKIT}" 1>&2
        else
            ssh ${WEBHOST} chgrp -f www-data $DIR/Meetkits/$REGION/${ThisKIT/${PROJ}/}.html
        fi
    else
        mkdir -p ${DIR}/Meetkits/$REGION
        chgrp -f www-data ${DIR}/Meetkits/$REGION
        cp $TMPWDIR/${ThisKIT/${PROJ}/}.html $DIR/Meetkits/$REGION/${ThisKIT/${PROJ}/}.html
        chgrp -f www-data $DIR/Meetkits/$REGION/${ThisKIT/${PROJ}/}.html
    fi

    rm -f $TMPWDIR/${ThisKIT/${PROJ}/}.html
    if (( $VERBOSE > 1 )) ; then
        echo "$CMD MESG: Installed PMchart on $WEBHOST:$DIR/Meetkits/$REGION" 1>&2
    fi
}

function DoPM_Overview() {
    local ThisPROJ=$1 ; shift
    local OVERVIEW="${ThisPROJ}Overview.html"  # output filename

    if [ -n "$DEBUG" ]
    then
        echo "perl $GENERATOR $MYREGION $LNG $REFERENCE --avoid '$AVG_AVOID' --alias 'http://behouddeparel.nl/' $DEBUG -w '$TMPWDIR/' -e '$POLs' -b '$POLs' $CORRECTION -L '$LAST' -S '$START' $FIRST -O ${OVERVIEW/.html/} $*" 1>&2
    fi
    if ! perl $GENERATOR $MYREGION $LNG $REFERENCE --alias "$REGION" $DEBUG --avoid "$AVG_AVOID"  -w "$TMPWDIR/" -e "$POLs" -b "$POLs" $CORRECTION -L "$LAST" -S "$START" $FIRST -O ${OVERVIEW/.html/} $* 2>$TMPWDIR/ERRORS
    then # ERROR
        date 1>&2
        echo "$CMD ERROR: Failed to generate chart for ${OVERVIEW}" 1>&2
        if (( $VERBOSE > 0 )) && [ -s $TMPWDIR/ERRORS ] ; then
            cat $TMPWDIR/ERRORS 1>&2
        fi
    else # install generated chart file on website
        if (( $VERBOSE > 0 )) || [ -n "$DEBUG" ]
        then
            if [ -n "$DEBUG" ] || (( $VERBOSE > 2 ))
            then cat $TMPWDIR/ERRORS 1>&2
            fi
            echo -e "$CMD MESG: generated overview for project ${OVERVIEW} with kits:\n\t$KITS" 1>&2
            if [ -n "$DEBUG" ] ; then return ; fi
        fi
        if [ "${WEBHOST:-localhost}" = localhost ] ; then
            if cp $TMPWDIR/${OVERVIEW} $DIR/Meetkits/$REGION/ ; then
                chgrp -f www-data $DIR/Meetkits/$REGION/${OVERVIEW}
            fi
        else # install on remote host WEBHOST
            if ! scp -q $TMPWDIR/${OVERVIEW} ${WEBHOST}:$DIR/Meetkits/$REGION/
            then
                date 1>&2
                echo "$CMD ERROR: Failed to copy chart to ${WEBHOST} for ${OVERVIEW}" 1>&2
                exit 1
            else
                ssh ${WEBHOST} chgrp -f www-data $DIR/Meetkits/$REGION/${OVERVIEW}
            fi
        fi
        if (( $VERBOSE > 1 )) ; then
            echo "$CMD MESG: installed chart ${OVERVIEW} to ${WEBHOST}:$DIR/Meetkits/$REGION" 1>&2
        fi
    fi
    rm -f $TMPWDIR/ERRORS
}

##########################################################
SetParameters "$REGION"   # get parameters
if [ -n "$STATIONS" ]
then    # synchronize measurements tables of official stations with DBHOST tables
    SYNC2DBHOST ${WEBHOST:-localhost} $STATIONS
fi

if [ ! -f ${GENERATOR/ */} ] || [ ! -d $WDIR ] # working directory
then
    echo "$CMD FATAL: cannot find $GENERATOR or $DIR or work dir $WDIR. EXITING" 1>&2
    exit 1
fi
TMPWDIR=$TMPWDIR/${PROJ/_/}    # temporary directory
mkdir -p $TMPWDIR
cd $WDIR    # working directory
if (( $VERBOSE > 0 ))
then
    echo "$CMD MESG: generate PM charts of region $REGION project ${PROJ/_} from: $START upto $LAST for kits:" 1>&2
fi

for C in $COMMAND
do
    case "$C" in
    KITS)
       #########################                     per kit of a project PROJ
       if [ -z "$KITsns" ]
       then
           KITS=$(GetActiveKits "${PROJ/_/}" "$LAST")
       else
           KITS=${KITsns}
       fi
       if [ -z "$KITS" ] ; then exit 0 ; fi
       # when use of other meteo measurement station
       if [ -n "$METEO" ] && echo "$POLLUTANTS" | grep -q -P "(rv|temp|lucht|rain|w[sr]|wind)"
       then
           if ! CheckActive $METEO
           then
               echo "$CMD ATTENT: $meteo kit $METEO not active. Not used." 1>&2
               METEO=
           elif (( $VERBOSE > 0 ))
           then
               echo "$CMD ATTENT: use meteo measurements from kit $METEO" 1>&2
           fi
       fi
       CNT=0
       for KIT in $KITS
       do
           DoOnePMchart "$KIT"
       done
       rm -f $TMPWDIR/ERRORS
   ;;
   OVERVIEW)
       #################################
       # generate all graphs for one pollutant type
       KITS=$(GetActiveKits "${PROJ/_/}" "$START" "$LAST") # all in this period
       if [ -z "$KITS" ]
       then
           if (( $VERBOSE > 0 ))
           then
               echo "$CMD MESG: No active kits in period found. Stop chart generation." 1>&2
           fi
           exit 0
       fi
       if [ -n "$METEO" ]
       then
           REFERENCE="-R ''"
           STATIONS=
           KITS=$(python -c "for x in set('$KITS'.split()) - set('$METEO'.split()): print(x)" | tr "\n" " ")
       fi
       ############################                per project overview PM charts
       DoPM_Overview "$PROJ" ${KITS} ${STATIONS}
    ;;
    esac
done

