#!/bin/bash
# script to produce e.g. script for HIGHcharts

# $Id: Get_AQIs.sh,v 2.6 2022/03/26 15:43:02 teus Exp teus $
# 

# Copyright (C) 2014, Teus Hagen, the Netherlands
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
# TO DO:
#       have mysql using named pipe or --socket=/path/my_socket
#       automate validation of measurements (use CheckDB.sh for this)
#       support normalisation factoring for RIVM originating values
#       add color info for missing colums colors
#       see also TO DO remarks below

# echo "Script $0 called as '$1' '$2' '$3' '$4' '$5'" 1>&2
# echo "Environment:" 1>&2
# printenv  | grep -e FORE -e DB 1>&2

DEBUG=${DEBUG:-0}       # 1: produce full html page, 2: do not compress JS
VERBOSE=${VERBOSE:-0}
if (( $DEBUG > 0 )) ; then VERBOSE=1 ; fi
export LC_TIME="nl_NL.UTF-8"
export DBUSER=${DBUSER:-$USER} # database user
export DBPASS=${DBPASS:-acacadabra} # database password for access
HOST=${HOST:-localhost}
export DBHOST=${DBHOST:-$HOST}
export DB=${DB:-luchtmetingen}
# website DB credentials
export WWWDBUSER=${WWWDBUSER:-$DBUSER}
# WWWDBPASS see below
export WWWDBHOST=${WWWDBHOST:-$DBHOST}
export WWWDB=${WWWDB:-parel7}
MYSQL="mysql -u $DBUSER -p$DBPASS -N -B --silent -h $DBHOST $DB"
if which mysql_config_editor >/dev/null
then
    PASSED=$(mysql_config_editor print --login-path=$DB \
        | awk '/password =/{ print "HIDDEN" ; }')
    MYSQL="mysql --login-path=$DB -N -B --silent -h $DBHOST $DB"
fi

FORECASTSCRPT=/webdata/luchtmetingen/forecast.pl
if [ -x ./forecast.pl ] ; then FORECASTSCRPT=./forecast.pl ; fi
if [ ! -x $FORECASTSCRPT ]
then
    echo "Script $FORECASTSCRPT does not exits!. Exiting." 1>&2
    exit 1
fi
TBL=${FORECAST/-*/}      # comes from environment as TBLid-AirQualIndType
TBL=${TBL:-HadM}         # HadM (Grubbenvorst) enabled by default
AQI=${FORECAST/*-/}
AQI=${AQI:-LKI}
declare -A FORECAST
case ${TBL:-xxx} in
    HadM) FORECAST[$TBL]=Grubbenvorst
    ;;
    NL[01]0131) FORECAST[$TBL]=Venray
    ;;
    MHF|MKH) TBL=MHF ; FORECAST[$TBL]=MaastrichtHF
    ;;
    MA2) TBL=MA2 ; FORECAST[$TBL]=Maastricht
    ;;
    G[VA]) TBL=GV ; FORECAST[$TBL]=Geleen
    ;;
    NL[01]0136) TBL=NL10136 ; FORECAST[$TBL]=HeerlenL
    ;;
    NL[01]0138) TBL=NL10138 ; FORECAST[$TBL]=HeerlenL
    ;;
    NETT) FORECAST[$TBL]=Nettetal
    ;;
    NL[01]0133) FORECAST[$TBL]=Wijnandsrade
    ;;
    *) TBL=''
    if [ -n "$FORECAST" ] ; then
        echo "$FORECAST is unknown, use DB_table-{AQI|LKI|all}" 1>&2
    else
        echo "FORECAST from env. was not defined. Exiting." 1>&2
        exit 1
    fi
    ;;
esac
FORECAST[$TBL,aqi]=${AQI}
if [ -z "${FORECAST[$TBL,aqi]/*LKI*/}" ]
then FORECAST[$TBL,aqi]=LKI ;
elif [ -z "${FORECAST[$TBL,aqi]/*all*/}" ]
then FORECAST[$TBL,aqi]=all ;
    echo "Forecast for 'all' aqi Indices is not yet supported!" 1>&2
    exit 1
elif [ -z "${FORECAST[$TBL,aqi]/*AQI*/}" ]
then FORECAST[$TBL,aqi]=AQI ;
else FORECAST[$TBL,aqi]=LKI ;
fi

# weather and PM2.5 forecast chart inclusiono# TO DO current only only one Index type
# add more village names for a table name if forecasts are required

# website location path
if [ -z "$WWW" ]
then
    for SITE in behouddeparel BdP
    do
        if [ -f /etc/apache2/sites-available/$SITE.conf ] ; then break ; fi
    done
    WWW=$(grep "DOCroot.*webdata" /etc/apache2/sites-available/$SITE.conf | head -1 | sed -e 's/.*DOCroot  *//' -e 's/\/ *$//' -e 's@/$@@')
    for WDIR in ../cmsdata/BdP sites/behouddeparel.nl cmsdata sites/default NULL
    do
        if [ -z "$WWW" ] ; then break ; fi
        if [ $WDIR = NULL ] ; then WWW='' ; break ; fi
        WDIR=$WDIR/files/luchtmetingen
        if [ -d ${WWW}/$WDIR ] ; then WWW=${WWW}/$WDIR ; break ; fi
    done
fi
if [ -z "$WWW" ] || [ ! -d ${WWW} ] || [ ! -w ${WWW} ]
then
    echo "ERROR: Cannot find WWW dir $WWW." 1>&2
    exit 1
fi
# website owner
GRP=$(ls -ld "$WWW" | awk '{ print $4; }')

AQIs=()           # the type IDs of aqi we are handling, max 2 are supported

# get the pollutants from the DB table arg1
function Get_pollutants() {
    local NO_POL='(id|datum|_[a-z]+|[A-Z]+)'      # name is not pollutant, use with grep -E
    if [ -z "$1" ] ; then return 1 ; fi
    if [ -z "${1/_aqi/}" ]
    then
        $MYSQL -e "DESCRIBE $1" | perl -d -e "my \$nopt = '$NO_POL';" -e '
            while(<STDIN>) { s/\s.*//g; s/_(aqi|lki|_color)$//g;
                print $_ if not /$nopt/ ; }' | sort | uniq
    else
        $MYSQL -e "DESCRIBE $1" | perl -e "my \$nopt = '$NO_POL';" -e 'while(<STDIN>) { s/\s.*//; print $_ if not /$nopt/ ; }' | sort | uniq
    fi
    return $?
}
# perl routine to obtain air quality index values for a range of standards
INDEXSCRIPT=/webdata/luchtmetingen/AQI.pl
function INDEX()
{
    local MYCMD=AQI ARG
    case "$1" in
    AQI)
                                # day average base
        MYCMD=maxAQI ; shift    # Air Quality Index algorithm (1968/2012, US, China ao)
    ;;
    AQHI)                       # Air Quality Health Index (2002/2013, Canada)
                                # day average base
        MYCMD=AQHI ; shift      # maxAQHI and AQHI are same routine
    ;;
    LKI)                        # LuchtKwaliteitsIndex algorithm (2015, RIVM Nld)
                                # hourly base !! need min-max per day as well.
        MYCMD=maxLKI ; shift
    ;;
    CAQI)                       # Common Air Quality Index (EU 2006/2012)
        MYCMD=maxCAQI ; shift
        # here used with 24h average measurements
        ARG="${*//pm_10/pm_10h24}" ; ARG="${ARG//pm_25/pm_25h24}" # day averages
    ;;
    view|VIEW)                       # get the index quality or color for an aqi value
        MYCMD=AQI_view ; shift
        ARG="${1:LKI} aqi ${2:-0}  ${3:qual}"       # aqi_type void value qual|color|gom
    ;;
    qual|color|QUAL|COLOR)
        MYCMD=AQI_view
        ARG="${2:LKI} aqi ${3:-0} ${1,,}" 
    ;;
    esac
    if [ -z "$ARG" ] ; then ARG="$*" ; fi
    if [ ! -f ${INDEXSCRIPT} ] ; then INDEXSCRIPT=./AQI.pl ; fi
    if [ ! -f "${INDEXSCRIPT}" ]
    then
       echo "ERROR: air quality index INDEX routine: AQI.pl script not found" 1>&2
       return 1
    fi
    perl -e "require '${INDEXSCRIPT}';" -e "${MYCMD} ('$ARG');"
    return $?
}

# dispatch routine
# args: TBL(HadM) TYPE_aqi(LKI) periods(2) interval(24) end_date(latest values)
function DataCollect() {
    local TBL=${TBL:-HadM} CMD=AQI_dataCollectFile
    local TBLS=$($MYSQL -e "SHOW TABLES" | grep -P "^${TBL}(_aqi)?\$")
    if ! echo "$TBLS" | grep -q "${TBL}"
    then
        echo ERROR
        echo "ERROR: Data collecton table $TBL doe not exists in DB." 1>&2
        return 1
    fi
    if ! echo "$TBLS" | grep -q "${TBL}_aqi"
    then
        CMD=AQI_dataCollectEmbedded       # get data series embedded format
    fi
    if ! TYPE=$TYPE TBL=$TBL $CMD "$@"
    then
        echo "ERROR"
        echo "ERROR: Data Collection $CMD failed." 1>&2
        return 1
    fi
    return 0
}

# get a collection of AQI values for an amount of hours
# arg1: table name (dflt HadM)
# arg2: type of index (dflt LKI)
# arg3: pollutant for the AQI calculation (dflt all available)
# arg4: nr of periods of 24 hours before end date/hour(dflt 2*24 hours)
# arg5: end date/hour (dflt upto last one available)
function AQI_dataCollectEmbedded() {
    local TYPE=${2:-LKI} WQRY SQRY STRG
    local -i SERIES=0 J
    declare -A POLS4TYPE
    POLS4TYPE[AQI]="o3|pm_10|pm_25|co|so2|no2"
    POLS4TYPE[LKI]="o3|pm_10|pm_25|no2"
    if ! echo "$TYPE" | grep -q -E "^(AQI|LKI)"
    then
        echo "ERROR: $TYPE is not yet supported." 1>&2
        return 1
    fi
    local TBL=${TBL:-${2:-HadM}}
    # full period statistics
    declare -i END=${5:-now}  STRT
    local POLs=()
    if [ -z "${TBL/[0-9]*/}" ]
    then
        TBL=$($MYSQL -e "SELECT stations.table FROM stations WHERE nr = '$TBL' LIMIT 1")
        TBL=${TBL:-HadM}
    fi
    if ! echo "$($MYSQL -e 'show tables')" | grep -v -e _ -e stations | grep -q $TBL
    then
        echo "ERROR: DB table $TBL is not present!" 1>&2
        exit 1
    fi
    # compile an array with names of pollutants for this aqi type
    local STRG=${3:-all}
    if [ $STRG = all ] ; then
      for STRG in $(Get_pollutants "$TBL")
      do
        if echo "$STRG" | grep -q -P "(${POLS4TYPE[$TYPE]})"
        then
            if [ "$STRG" = "${2:-all}" ]
            then
                POLs+=($STRG)
            elif [ "${2:-all}" = all ]
            then
                POLs+=($STRG)
            fi
        fi
      done
    fi
    if (( ${#POLs[@]} < 1 ))
    then
        echo "ERROR: no pollutant found in table as indicator." 1>&2
        return 1
    fi
    # compile the start and end hour for this chart
    local -i I
    STRG=''
    for (( I=0 ; I < ${#POLs[@]} ; I++ ))
    do
        STRG+="OR NOT ISNULL(${POLs[$I]}) "
    done
    STRG="${STRG/#OR/}"
    if [ -z "$5" ]
    then
        END=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM $TBL WHERE $STRG ORDER BY datum DESC LIMIT 1")
    else 
        END=$(date --date="${5:-now}" +%s)
        if (( $END <= 0 ))
        then
            echo "ERROR: unknown end date $5" 1>&2
            return 1
        fi
    fi
    PERIODS=${4:-2P24} INTERVAL=${4:-2P24} UNIT={UNIT:-3600}
    INTERVAL=${INTERVAL/*P/} ; PERIODS=${PERIODS/P*/}
    STRT=$(($END - (${PERIODS}*${INTERVAL}*${UNIT}) + 45*60 ))
    local CNT=$($MYSQL -e "SELECT COUNT(*) FROM $TBL WHERE ($STRG) AND (UNIX_TIMESTAMP(datum) >= $STRT) AND (UNIX_TIMESTAMP(datum) <= ($END+45*60))")
    if (( $CNT < $INTERVAL ))
    then
        echo "ERROR: minimal one period of $INTERVAL hours in a serie." 1>&2
        return 1
    fi

    # collected info for HighChart script generator parameters
    echo "TBL=$TBL"
    echo "TYPE=${TYPE:-LKI}"
    echo "HOURS=$(($PERIODS*$INTERVAL))"
    echo "POLS=${POLs[@]^^}" | sed -e 's/  */,/g' -e 's/_//g' -e 's/PM25/PM2.5/g'
    $MYSQL -e "SELECT CONCAT('LOCATION=',name,' (',municipality,')') FROM stations WHERE stations.table = '$TBL'" | sed -e 's% /% %g' -e 's/ /@/g'
    $MYSQL -e "SELECT CONCAT('MUNICIPALITY=',municipality) FROM stations WHERE stations.table = '$TBL'" | sed -e 's% /% %g' -e 's/ /@/g'
    $MYSQL -e "SELECT CONCAT('ORGANISATION=',organisation) FROM stations WHERE stations.table = '$TBL'" | sed -e 's% /% %g' -e 's/ /@/g'
    $MYSQL -e "SELECT CONCAT('ALIAS=',id) FROM stations WHERE stations.table = '$TBL'" | sed -e 's% /% %g' -e 's/ /@/g'
    # start one hour earlier to ident the graph
    echo "START=$(($STRT-$UNIT))"
    echo "END=${END}"
    if $MYSQL -e "DESCRIBE $TBL" | grep -E -q '^temp\s'
    then
        echo "LASTtemp=$($MYSQL -e "SELECT round(temp) FROM $TBL WHERE NOT ISNULL(temp) AND (UNIX_TIMESTAMP(datum) <= ($END+45*60)) ORDER BY datum DESC LIMIT 1")"
    fi

    # collect the pollutants values per hour delimiter for fields is @-character
    local HOURS=()
    for(( I=0 ; I < ${#POLs[@]}; I++))
    do  
        if [ -n "$SQRY" ] ; then SQRY+=", " ; fi
        SQRY+="concat('${POLs[$I]}=',${POLs[$I]})" 
        # if [ -n "$WQRY" ] ; then WQRY+=" or " ; fi
        # WQRY+="(not isnull(${POLs[$I]}) AND ${POLs[$I]}_valid)"
    done
    # if [ -n "$WQRY" ] ; then WQRY="($WQRY) AND" ; fi
    # we want exactly one per hour (null represents no value)
    if $MYSQL -e "SELECT @@sql_mode" | grep -q ONLY_FULL_GROUP_BY
    then
        $MYSQL -e "SET GLOBAL @@sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''))"
    fi
    STRG=$($MYSQL -e "
            SELECT FLOOR(($STRT-$STRT)/$UNIT);
            # get the values per hour
            SELECT FLOOR((UNIX_TIMESTAMP(datum)-$STRT)/$UNIT), $SQRY FROM $TBL
                WHERE $WQRY (UNIX_TIMESTAMP(datum) >= $STRT)
                    AND (UNIX_TIMESTAMP(datum) < ($END+(60+45)*60))
                GROUP BY DATE(datum), HOUR(datum) ORDER BY datum;
            SELECT FLOOR(($END-$STRT+(60+45)*60)/$UNIT);" | \
          awk -v CNT=${#POLs[@]}  'BEGIN { STRT=0; }
            # make sure there is one record per hour
            {   
                if ( NF < 1 ) { next ; }
                if ( STRT == 0 ) { STRT = $1-1; }
                while ( STRT < ($1 - 1) ) {
                    for( i=0; i < CNT; i++) {
                        printf("%snull",(i>0?" ":""));
                    }
                    printf("\n"); STRT++;
                }
                if ( STRT == $1 ) { next ; } /* skip this record */
                STRT=$1;
                for ( i = 2; i <= NF; i++ ) {
                    printf("%s%s", (i > 2 ? " " : "" ), $(i));
                }
                printf("\n");
            }
          ' | \
          sed -e 's/NULL/unknown=0/ig' -e 's/\t/ /g' -e 's/  */@/g')
    # to do add check that every hour has one value!

    HOURS=($STRG)
    declare -A STAT
    # max value of elements defines the chart hight
    STAT[MAX]=0 STAT[MIN]=1000 STAT[AVG]=0 STAT[CNT]=0
    local -i PERIODS=0 Hnr=$INTERVAL      # count number of Hnr (flt 24) periods
    local -i LASThr=0
    local M

    # collect the serie values serie 0 is total aiq, serie N is aqi per pol
    # collect statistical values per period: count, average, min, max 
    for (( J=0; J < ${#POLs[@]}; J++))
    do
        local THIS_POL=${POLs[$J]} THIS_VAL
        if (( $SERIES <= 0 )) ; then THIS_POL="${POLs[@]//\//}" ; fi
        local AQI=() AQIcol=()

        if (( ${#HOURS[@]} <= $Hnr )) ; then Hnr=${#HOURS[@]} ; fi
        PERIODS=0
        for(( I=0; I < ${#HOURS[@]}; I++))
        do
            HOURS[$I]="${HOURS[$I]//@/ }"
            AQIcol[$I]=''

            # get the AQI value and the AQI color
            if (( $SERIES <= 0 ))
            then
                THIS_VAL=$(echo "${HOURS[$I]}" | sed 's/unknown=0 *//g')
                if (( ${#POLs[@]} >= 1 ))
                then
                    # invalidate if there are less as 2 values
                    THIS_VAL=$(perl -e "my \$val = '$THIS_VAL';" -e '
                        my $cnt = () = $val =~ /\w=/g;
                        print $val if $cnt <= 1; exit 0 if $cnt <= 1;
                        my $flt = () = $val =~ /\w=0[\.0]*/g;
                        $val =~ s/=.*/=0/ if ($cnt - $flt) < 2;
                        print $val;
                    ')
                fi
            else
                THIS_VAL=$(echo "${HOURS[$I]}" | \
                             awk -v col=$J '
                                BEGIN { col++; }
                                { printf("%s",( col <= NF ? $(col) :"unknown=0")); }')
            fi
            if [ "${THIS_VAL:-unknown=0}" = "unknown=0" ]
            then
                AQI[$I]=null
                AQIcol[$I]="'rgba(0,0,0,0)'"
            else
                AQI[$I]=$(INDEX ${TYPE} aqi "${THIS_VAL}")
                if $(perl -e "exit 1 if '${AQI[$I]:-0}' >= 0.05")
                then
                    AQI[$I]=null ; AQIcol[$I]="'rgba(0,0,0,0)'"
                fi
            fi

            # only for the last period  or all if number of hours is less as 24
            # statistics
            if (( ($I % $Hnr) == (${#HOURS[@]} % $Hnr) ))
            then        # collect statistics per period of 24 hours
                ((PERIODS++))
                STAT[CNT,$PERIODS,$SERIES]=0
                STAT[AVG,$PERIODS,$SERIES]=0
                STAT[MIN,$PERIODS,$SERIES]=1000
                STAT[MAX,$PERIODS,$SERIES]=0
            fi
            if [ "${AQI[$I]}" != null ]
            then
#echo -n "Found LKI for hour $I (${HOURS[$I]}) -> ${AQI[$I])}" 1>&2
                if (( (${#HOURS[@]} <= $Hnr ) || (($I % $Hnr) >= (${#HOURS[@]} % $Hnr) ) )) 
                then
                    STAT[AVG,$PERIODS,$SERIES]=$(perl -e "printf(\"%3.2f\",(${STAT[AVG,$PERIODS,$SERIES]} * ${STAT[CNT,$PERIODS,$SERIES]} + ${AQI[$I]}) / (${STAT[CNT,$PERIODS,$SERIES]} + 1));")
                    STAT[CNT,$PERIODS,$SERIES]=$((${STAT[CNT,$PERIODS,$SERIES]}+1))
                    if perl -e "exit 1 if '${AQI[$I]}' >= '${STAT[MIN,$PERIODS,$SERIES]}'"
                    then STAT[MIN,$PERIODS,$SERIES]=${AQI[$I]} ; fi
                    if perl -e "exit 1 if '${AQI[$I]}' <= '${STAT[MAX,$PERIODS,$SERIES]}'"
                    then STAT[MAX,$PERIODS,$SERIES]=${AQI[$I]} ; fi
                fi
#echo " PERIODS=$PERIODS, SERIES=$SERIES: CNT=${STAT[CNT,$PERIODS,$SERIES]} MAX=${STAT[MAX,$PERIODS,$SERIES]}" 1>&2
                if perl -e "if ('${STAT[MIN]}' <= '${AQI[$I]}' ) { exit 1 ; } else { exit 0; }"
                then STAT[MIN]=${AQI[$I]} ; fi
                if perl -e "exit 1 if '${STAT[MAX]}' >= '${AQI[$I]}'"
                then STAT[MAX]=${AQI[$I]} ; fi
                STAT[AVG]=$(perl -e "printf(\"%3.2f\",('${STAT[AVG]}' * '${STAT[CNT]}' + '${AQI[$I]}') / ('${STAT[CNT]}' + 1));")
                STAT[CNT]=$((${STAT[CNT]}+1))
#echo "AQI=${AQI[$I]}, STAT CNT=${STAT[CNT]}, MAX=${STAT[MAX]}, MIN=${STAT[MIN]}, AVG=${STAT[AVG]}" 1>&2

                if (( $SERIES > 0 )) ; then continue ; fi
                # only for series 0 color the bar is colored
                AQIcol[$I]="'"$(INDEX ${TYPE} color ${HOURS[$I]} | sed 's/0x/#/')"'"
                LASThr=$I       # define last hour with real values for series 0
            fi
        done
        for (( I=1; I <= $PERIODS; I++ ))
        do
            if [ -z "${STAT[MIN,$I,$SERIES]/1000/}" ]
            then
                STAT[MIN,$I,$SERIES]=0
            fi
        done

        echo "DATA_$SERIES=data$SERIES"
        echo "[null,${AQI[@]}]" | sed -e 's/  */,/g' >/var/tmp/${TYPE^^}_${THIS_POL}.json
        echo "DATAFILE_$SERIES=/var/tmp/${TYPE^^}_${THIS_POL}.json"
        echo "COLORS_$SERIES=colors$SERIES"
        echo "['#FFFFFF',${AQIcol[@]}]" | sed -e 's/  */,/g' >/var/tmp/${TYPE^^}_${THIS_POL}_colors.json
        echo "COLORSFILE_$SERIES=/var/tmp/${TYPE^^}_${THIS_POL}_colors.json"
        for M in MIN AVG MAX
        do
            echo "${M}_$SERIES=0" 
            if [ ${TYPE:-LKI} = AQI ]
            then
                echo ${M}_$SERIES=$(perl -e "if ( '${STAT[${M},$PERIODS,$SERIES]}' > 0 ) {printf('%d','${STAT[${M},$PERIODS,$SERIES]}'+0.5);} else { printf('?'); }")
            else
                echo ${M}_$SERIES=$(perl -e "if ( '${STAT[${M},$PERIODS,$SERIES]}' > 0 ) { printf('%2.1f','${STAT[${M},$PERIODS,$SERIES]}'+0.05);} else { printf('?'); }")
            fi
        done
        echo "THIS_POL_$SERIES=${THIS_POL}"

        # per period of interval statistical values per serie
        for (( I = 2; I <= $PERIODS; I++))
        do
            if [ -n "${STAT[AVG,$I,$SERIES]/0/}" ] \
                && [ -n "${STAT[AVG,$(($I-1)),$SERIES]/0/}" ]
            then
                # could also inject diff per day
                echo "AVGcol_$SERIES=black"
                perl -e "
                    print \"AVGcol_$SERIES=red\n\"
                        if '${STAT[AVG,$I,$SERIES]}' > '${STAT[AVG,$(($I-1)),$SERIES]}';
                    print \"AVGcol_$SERIES=green\n\"
                        if '${STAT[AVG,$I,$SERIES]}' < '${STAT[AVG,$(($I-1)),$SERIES]}';"
                echo "AVGmsg_$SERIES=gelijk"
                perl -e "
                    print \"AVGmsg_$SERIES=stijgend\n\"
                        if '${STAT[AVG,$I,$SERIES]}' > '${STAT[AVG,$(($I-1)),$SERIES]}';
                    print \"AVGcol_$SERIES=dalend\n\"
                        if '${STAT[AVG,$I,$SERIES]}' < '${STAT[AVG,$(($I-1)),$SERIES]}';"
            fi
            if (( ${#POLs[@]} <= 1 )) ; then break ; fi
        done
        if (( SERIES <= 0 ))
        then
            if (( $LASThr < 8 ))
            then
                echo "WARNING: Last hour ($LASThr) was less as 8." 1>&2
            fi
            echo "LAST_$SERIES=${AQI[$LASThr]}"
            echo "LASTcol_$SERIES='$(INDEX ${TYPE} color ${HOURS[$LASThr]} | sed 's/0x/#/')'"
            echo "LASTmsg_$SERIES=$(INDEX ${TYPE} qual ${HOURS[$LASThr]} | sed 's/  */@/g')"
            ((J--))
        fi
        ((SERIES++))
    done
    for M in MIN AVG MAX
    do
        if [ ${TYPE:-LKI} = AQI ]
        then
            echo ${M}=$(perl -e "if ( '${STAT[${M}]}' > 0 ) {printf('%d','${STAT[$M]}' +0.5);} else { printf('0'); }")
        else
            echo ${M}=$(perl -e "if ( '${STAT[${M}]}' > 0 ) {printf('%2.1f','${STAT[$M]}' +0.05);} else { printf('0'); }")
        fi
    done
    echo "INTERVAL=$INTERVAL"
    echo "UNIT=$UNIT"
    echo "PERIODS=$PERIODS"
    echo "SERIES_CNT=$SERIES"
    if [ -z "${STAT[MAX]/0/}" ]
    then    # no elements in the chart
        echo "WARNING: no AQI index could be calculated: no chart." 1>&2
        echo "ERROR: giving up." 1>&2
        return 1
    fi

    return 0
}

# check if table has TYPE column defined and not null in this period
# if not recalculate the column TYPE
function CheckTBLintegrity() {
    local TBL=${1:HadM} TYPE=${2:-LKI} POLS=(${3:-pm_10 pm_25})
    local FROM=${4:-0} TO=${5:-$(date +%s)} QRY=''
    TO=$(($TO + (60+45)*60))
    local -i I
    for(( I=0; I < ${#POLS[@]}; I++ ))
    do  # filter to real pollutants names
        POLS[$I]=${POLS[$I]/*_color*/}
        POLS[$I]=${POLS[$I]/_${TYPE,,}/}
        POLS[$I]=${POLS[$I]/${TYPE,,}/}
    done
    POLS=(${POLS[@]})
    if (( ${#POLS[@]} <= 1 )) ; then return 0 ; fi

    # check for the need to update the TYPE table
    QRY=''
    for(( I=0; I < ${#POLS[@]}; I++ ))
    do
        QRY+="OR NOT isnull(${POLS[$I]}_${TYPE,,}) "
    done
    # get latest date/time before end of period with values
    if (( $($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM ${TBL}_aqi
        WHERE not isnull(${TYPE,,}) $QRY AND
        UNIX_TIMESTAMP(datum) >= $FROM AND UNIX_TIMESTAMP(datum) < $TO
        ORDER BY datum DESC LIMIT 1") < ($TO - (3600*24)) ))
    then        # more as one day missing, update the table from the DB original table
        echo "ATTENTION: updating ${TBL}_aqi via Get_data.pl with values upto $(date --date=@$TO '+%Y/%m/%d %H:00')." 1>&2
        ./Get_data.pl -t $TBL --aqi "$(date --date=@$TO '+%Y/%m/%d %H:00:00')"
    fi
    # return if there are no missing aqi alues due to failures elsewhere
    # count the rows with more as 2 pollutant aqi values and no aqi defined
    QRY=''
    for(( I=0; I < ${#POLS[@]}; I++ ))
    do
        if (( $I > 0 )) ; then QRY+='+' ; fi
        QRY+="(NOT isnull(${POLS[$I]}_${TYPE,,}))"
    done
    if (( $($MYSQL -e "SELECT COUNT(*) FROM ${TBL}_aqi
        WHERE isnull(${TYPE,,}) AND (($QRY) >= 2) AND
        UNIX_TIMESTAMP(datum) >= $FROM AND UNIX_TIMESTAMP(datum) < $TO") <= 0 ))
    then
        return 0        # OK nothing to update
    fi

    # try to update missing column TYPE data
    local QRY0='UNIX_TIMESTAMP(datum)'
    for(( I=0; I < ${#POLS[@]}; I++ ))
    do
        QRY0+=", ${POLS[$I]}_${TYPE,,}"
    done
    echo "ATTENTION: updating ${TBL}_aqi with $TYPE values." 1>&2
    $MYSQL -e "SELECT ${QRY0} FROM ${TBL}_aqi
        WHERE isnull(${TYPE,,}) AND (($QRY) >= 2) AND
        UNIX_TIMESTAMP(datum) >= $FROM AND UNIX_TIMESTAMP(datum) < $TO" \
    | perl -e "my \$type='${TYPE,,}';
               my \$tbl='${TBL}_aqi';" \
           -e '
        while(<STDIN>) {
            chop; s/^\s+//; s/\s+$//;
            my @line = split /\s+/; my $t = shift @line;
            my $min = 1000; my $max = 0;
            $fnd = 0;
            for( my $i=0; $i <= $#line; $i++ ) {
                next if $line[$i] =~ /=null/;
                next if $line[$i] <= 0.1; $fnd++;
                $min = $line[$i] if $line[$i] < $min;
                $max = $line[$i] if $line[$i] > $max;
            }
            if ( $fnd > 1 ) {
                # increase aqi if aqis are close to each other
                if( (($max-$min) <= ($type =~ /aqi/? 25 : 1)) ) {
                    $max += ($type =~ /lki/? 1 : 25);
                }
                printf("UPDATE %s_aqi SET %s = %4.2f WHERE UNIX_TIMESTAMP(datum) = %d;\n",
                    $tbl, $type, $max, $t);
            } 
        } ' \
    | $MYSQL
    return $?
}
    
# get a collection of AQI values for an amount of rows
# get the values from the AQI table and push data into JSON file
# arg1: table name (dflt HadM)
# arg2: type of index (dflt LKI)
# arg3: pollutant for the AQI calculation (dflt all available)
# arg4: nr of periods of interval hours before end date/hour(dflt 2P24 hours)
# arg5: end date/hour (dflt upto last one available)
function AQI_dataCollectFile() {
    local STRG
    declare -A POLS4TYPE
    PERIODS=${4:-2P24} INTERVAL=${4:-2P24} UNIT=${UNIT:-3600}
    INTERVAL=${INTERVAL/*P/} ; PERIODS=${PERIODS/P*/}

    POLS4TYPE[AQI]="o3|pm_10|pm_25|co|so2|no2"
    POLS4TYPE[LKI]="o3|pm_10|pm_25|no2"
    if ! echo "$TYPE" | grep -q -E "^(AQI|LKI)"
    then
        echo "ERROR: $TYPE is not yet supported." 1>&2
        return 1
    fi
    local TBL=${TBL:-${2:-HadM}}
    #  statistics period calculation
    local POLs=()
    if [ -z "${TBL/[0-9]*/}" ]
    then
        TBL=$($MYSQL -e "SELECT stations.table FROM stations WHERE nr = '$TBL' LIMIT 1")
        TBL=${TBL:-HadM}
    fi
    if ! echo "$($MYSQL -e 'show tables')" | grep -v -e stations | grep -q ${TBL}_aqi
    then
        echo "ERROR: DB table ${TBL}_aqi AQI table is not present!" 1>&2
        echo "Use the other data collection routine." 1>&2
        exit 1
    fi
    # compile an array with names of pollutants for this aqi type
    # in this case lki or aqi is called a pollutant
    
    local COLORS
    if $MYSQL -e "DESCRIBE ${TBL}_aqi" | grep -q -P "^\s*(${TYPE,,})_color"
    then
        COLORS=1
    fi
    local STRG
    # get them in a sorted by group row headed by aqi multi value
    STRG=$($MYSQL -e "DESCRIBE ${TBL}_aqi" \
            |  perl -e "my \$col=${COLORS:-0}; my \$type='${TYPE,,}';" \
                -e '
                my @pols = ();
                while(<STDIN>) {
                    next if not /$type/i; chop; s/\s.*//;
                    next if /${type}_(mesg|gom|qual)$/;
                    next if /_${type}_color/;
                    s/(.*)_($type)/$2_$1/i;
                    push(@pols,$_);
                }
                @pols = sort @pols;
                for(my $i = 0; $i <= $#pols; $i++) {
                    $pols[$i] =~ s/^($type)_(.*)(_color)?/$2_$1$3/i;
                    $pols[$i] =~ s/(_color)(.+)/$2$1/;
                    $pols[$i] =~ s/^color_(.*)/$1_color/;
                    print "$pols[$i]\n";
                }')
    
    if [ ${3:-all} != all ] ; then
        STRG=$(echo "${STRG}" | grep "${3,,}")
    fi
    POLs=($STRG)
    if (( ${#POLs[@]} < 1 ))
    then
        echo "ERROR: no pollutant found in table as indicator." 1>&2
        return 1
    fi

    # compile the start and end hour for this chart
    local -i I
    STRG=''
    for (( I=0 ; I < ${#POLs[@]} ; I++ ))
    do
        if [ -z "${POLs[$I]/*_color/}" ] ; then continue ; fi
        STRG+="OR ((NOT ISNULL(${POLs[$I]})) AND (${POLs[$I]} > 0)) "
    done
    STRG="${STRG/#OR/}"
    if [ -z "$5" ]      # no end date defined so use last date/time of DB
    then
        END=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM ${TBL}_aqi WHERE ${STRG:-not isnull(datum)} ORDER BY datum DESC LIMIT 1")
    else                # use end date/time from command line
        END=$(date --date="${5:-now}" +%s)
        if (( $END <= 0 ))
        then
            echo "ERROR: unknown end date $4" 1>&2
            return 1
        fi
    fi
    STRT=$(($END - (${PERIODS}*${INTERVAL}*$UNIT + 45*60) ))

    # update the table first if needed
    CheckTBLintegrity ${TBL:-HadM} ${TYPE:-LKI} "${POLs[@]}" $STRT $END 

    local CNT
    CNT=$($MYSQL -e "SELECT COUNT(*) FROM ${TBL}_aqi WHERE ($STRG) AND (UNIX_TIMESTAMP(datum) >= $STRT) AND (UNIX_TIMESTAMP(datum) <= ($END+45*60))")
    if (( $CNT < (${INTERVAL}/2) ))
    then
        echo "WARNING: Start $(date --date=@${STRT} '+%Y/%m/%d %H:00') upto $(date --date=@${END} '+%Y/%m/%d %H:00') only $CNT records. Require minimal one period of 50% of  ${INTERVAL} of $(($UNIT/3600)) hours in the chart" 1>&2
        return 1
    fi

    # collected info for HighChart script generator parameters
    local LOCATION=$($MYSQL -e "SELECT name FROM stations WHERE stations.table = '$TBL'")
    local MUNICIPALITY=$($MYSQL -e "SELECT municipality FROM stations WHERE stations.table = '$TBL'")
    local ORGANISATION=$($MYSQL -e "SELECT organisation FROM stations WHERE stations.table = '$TBL'")
    local ALIAS=$($MYSQL -e "SELECT id FROM stations WHERE stations.table = '$TBL'")

    # collect the pollutants values per hour dilimiter for fields is @-character
    local HOURS=() SQRY='' NQRY='' WQRY='' 
    local GRP=''
    local STDDEV=${RANGE}     # stddev 1 (50%), 2 (90%), 2.5 (95%)
    if (( $UNIT > 3600 ))
    then        # the case we are dealing with dayaverages per day (candle stick chart)
        GRP='GROUP BY DATE(datum)'
        COLORS=0
    fi
    local DATA_BASE=/var/tmp/${TYPE^^}
    for(( I=0 ; I < ${#POLs[@]}; I++))
    do  
        if [ -z "${POLs[$I]/*_color*/}" ] && (( $COLORS <= 0 ))
        then    # omit the aqi color data
            continue
        fi
        if (( $I > 0 )) ; then SQRY+=', ' ; NQRY+=', '; fi
        if (( $UNIT > 3600 ))
        then
            STDDEV=${RANGE:-2}
            SQRY+="concat('AVG:${POLs[$I]}=',if(AVG(${POLs[$I]}) < 0.05,'NULL',ROUND(AVG(${POLs[$I]}),1)))"
            SQRY+=",concat('STDDEV:${POLs[$I]}=',if(AVG(${POLs[$I]})<0.05,0,ROUND(STDDEV(${POLs[$I]}),1)))"
            # denote the pollutant names of the fields
            NQRY+="'AVG:${POLs[$I]}=NULL', 'STDDEV:${POLs[$I]}=NULL'"
        else
            SQRY+="concat('${POLs[$I]}=',if(isnull(${POLs[$I]}),'NULL',${POLs[$I]}))"
            # denote the pollutant names of the fields
            NQRY+="'${POLs[$I]}=NULL'"    # denote the pollutant names of the fields
        fi
        # if [ -n "$WQRY" ] ; then WQRY+=" or " ; fi
        # WQRY+="OR (NOT ISNULL(${POLs[$I]}) OR ${POLs[$I]} > 0)"
    done
    # if [ -n "$WQRY" ] ; then WQRY="(${WQRY/#OR /}) AND" ; fi
    # we want exactly one per UNIT seconds (null represents no value)
    # LAST is last UNIT [time/aqi and] time/aqi(pollutant) measurements
    if $MYSQL -e "SELECT @@sql_mode" | grep -q ONLY_FULL_GROUP_BY
    then
        $MYSQL -e "SET GLOBAL @@sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''))"
    fi
    STRG=$($MYSQL -e "
            SELECT FLOOR($STRT/$UNIT)*$UNIT, ${NQRY}; # start:total of hours
            # get the values per hour
            SELECT UNIX_TIMESTAMP(datum), $SQRY FROM ${TBL}_aqi
                WHERE $WQRY (UNIX_TIMESTAMP(datum) >= $STRT)
                    AND (UNIX_TIMESTAMP(datum) < ($END+(60+45)*60))
                $GRP ORDER BY datum;
            SELECT (FLOOR(($END+(60+45)*60)/$UNIT)+1)*$UNIT;" \
    | perl \
            -e "
                  require '${INDEXSCRIPT}';                 # AQI calculations
                  my \$CNT = ${#POLs[@]};                   # number fields per record
                  my \$location='$LOCATION';                # location of the station
                  my \$municipality=' $MUNICIPALITY';       # local government
                  my \$organisation=' ($ORGANISATION, NL)'; # organisation/owner
                  my \$lastTime = $END;                     # chart end date
                  my \$cols = ${COLORS:-0};                 # aqi color value enabled?
                  my \$period = ${PERIODS:-2};              # # measurements/timeframe
                  my \$interval = ${INTERVAL:-1};           # plot interval in secs
                  my \$unit = $UNIT;                        # measurement grid in secs
                  my \$type = '${TYPE}';                    # aqi type
                  my \$names = '${DATA_BASE}_POL.json';     # data output file path
                  my \$range = ${STDDEV:-2} ;                # R * stddev dflt 90%
                  my \$debug = ${DEBUG:-0};
               " \
            -e '
                use POSIX qw(strftime); use FileHandle;
                my $isAVG = ($unit > 3600 ? 1 : 0);         # day avg handling enabled
                $organisation =~ s/, NL/, DE/ if $organisation =~ /NRWF/;
                $CNT = ($CNT-1)*2 if $isAVG;                # nr of fields per record

                # we generate an array of values per pollutant
                # the x (date/time) values are taken from startime and intervaltime
                my $unit_cnt = 0; my @nulls = ();
                my $strt=0;                          # strt is the hour nr since epoch 
                my $remainder = int($lastTime/$unit) % $interval; # 24 hours case
                $remainder = 0 if $isAVG;                   # calendar day case
                my %files; $files{max} = 0; $start = 0;

                sub toJSON {                # output per pollutant, per unit timeframe
                    # keep statistics: min/avg/max per interval and total periods
                    # if defined min/max: value is avg and we use chandle stick chart
                    my ($timing,$PolValue,$stddev) = @_;
                    return 0 if $PolValue !~ /=/;
                    my $pol=$PolValue; $pol =~ s/=.*//;
                    $pol =~ s/^AVG://i;
                    $stddev =~ s/.*=// if defined $stddev;
                    my $value=$PolValue; $value =~ s/.*=//;
                    my $col="";
                    if ( ($PolValue =~ /^AVG:/i) && (defined $stddev) ) {
                        $pol =~ s/^AVG://i; $stddev =~ s/.*=//; # avg and stddev case
                    }
                    if( $pol =~ /_color/) {
                        $col = $value; $value=0;
                        $col =~ s/(0x)?([0-9a-f]{6})/"#$2"/i;
                        $col =~ s/(FFFFFF|0F0F0F)/000000/i;
                    } elsif ( $pol !~ /_/ ) {
                        $value = 0 if $value =~ /null/i;
                        $value = 0 if "$value" !~ /^[0-9\.]+$/;
                    } else { return 0 ; }
                    if( not defined $file{$pol}{FD} ){
                        my $T = uc($type);
                        if ( not $start ) {
                            $start = $timing - $unit;
                            print STDOUT "TYPE=$T\n";
                            print STDOUT "${T}_START=$start\n";
                        }
                        # wait initiating json file while we have null values
                        if ( $col ) { return 0 if $col =~ /null/i; }
                        else { return 0 if (not $value) || $value =~ /null/i; }
                        my $name = $names; $name =~ s/POL/$pol/;
                        $file{$pol}{FD} = new FileHandle;
                        open($file{$pol}{FD},">".$name)
                            || die ("ERROR: Cannot open $name for writing");
                        print STDOUT "${T}_DATA_${pol}=$name\n";
                        # print STDERR "Created data file ${T}_DATA_${pol}=$name for pol $pol\n" if $debug;
                        if( defined $stddev ) {
                            $name = $names; $name =~ s/POL/RANGE_$pol/;
                            $file{$pol}{STDDEV_FD} = new FileHandle;
                            open($file{$pol}{STDDEV_FD},">".$name)
                                || die ("ERROR: Cannot open $name for writing");
                            print STDOUT "${T}_RANGEFILE_${pol}=$name\n";
                            print STDERR "Created data file ${T}_RANGEFILE_${pol}=$name for pol $pol\n" if $debug;
                            # header of the json file output
                            # print $file{$pol}{FD} "?(\n";
                            $file{$pol}{STDDEV_FD}->printf("/* std dev (range) data created %s: %s %s Index values location %s %s (%s), from %s upto %s */\n",
                                strftime("%Y/%m/%d %R %Z",localtime(time)),
                                ($T eq $POL ?"":$T), $POL, $location, $municipality, $organisation,
                                strftime("%Y/%m/%d %H:00",localtime($timing)),
                                strftime("%Y/%m/%d %H:00",localtime($lastTime))
                            ) if $debug ;
                            $file{$pol}{STDDEV_FD}->printf("[\n");
                            for ( my $t = $start; $t < $timing; $t += $unit) {
                                $file{$pol}{STDDEV_FD}->printf("null,"); # indent of graph
                            }
                        }

                        # reset statistics
                        # statistics for full chart time
                        $file{$pol}{period_cnt} = 0; $file{$pol}{period_min}= 9999;
                        $file{$pol}{period_max} = 0; $file{$pol}{period_avg} = 0;
                        # statistics per last interval 24 hours, week, month, year
                        $file{$pol}{cnt} = 0; $file{$pol}{min}= 9999;
                        $file{$pol}{max} = 0; $file{$pol}{avg} = 0;
                        $file{$pol}{last_time} = 0;     # last date/time measurement
                        my $POL=uc($pol); $POL =~ s/(.*)_([A-Z])$/$2 ($1)/;
                        $POL =~ s/ROET/soot/i;
                        # header of the json file output
                        # print $file{$pol}{FD} "?(\n";
                        $file{$pol}{FD}->printf("/* created %s: %s %s Index values location %s %s (%s), from %s upto %s */\n",
                            strftime("%Y/%m/%d %R %Z",localtime(time)),
                            ($T eq $POL ?"":$T), $POL, $location, $municipality, $organisation,
                            strftime("%Y/%m/%d %H:00",localtime($timing)),
                            strftime("%Y/%m/%d %H:00",localtime($lastTime))
                        ) if $debug ;
                        $file{$pol}{FD}->printf("[\n");
                        for ( my $t = $start; $t < $timing; $t += $unit) {
                            $file{$pol}{FD}->printf("null,"); # indent of graph
                        }
                    }
                    # here period of interval/unit seconds from end of chart time
                    if( (int($timing/$unit) % $interval) == $remainder ) {
                        $file{$pol}{FD}->printf("\n/* last 24 hour period: min=%3.1f, avg=%3.1f, max=%3.1f */\n",
                            $file{$pol}{min},$file{$pol}{avg}, $file{$pol}{max})
                                if $debug && (defined $file{$pol}{max}) && ($file{$pol}{max} > 0);
                        $file{$pol}{FD}->printf("\n/* date %s */\n",
                            strftime("%Y/%m/%d %H:00",localtime($timing))) if $debug;
                        $file{$pol}{STDDEV_FD}->printf("\n/* date %s */\n",
                                strftime("%Y/%m/%d %H:00",localtime($timing)))
                            if $debug && (defined $file{$pol}{STDDEV_FD});
                        printf STDOUT ("%s_STAT_%s=%3.1f,%3.1f,%3.1f,%d\n",
                            uc($type),$pol, $file{$pol}{avg},
                            $file{$pol}{min}, $file{$pol}{max},$file{$pol}{cnt})
                                if (defined $file{$pol}{max}) && ($file{$pol}{max} > 0);
                        $file{$pol}{cnt} = 0; $file{$pol}{min}= 9999; # reset interval
                        $file{$pol}{max} = 0; $file{$pol}{avg} = 0;   # statistics
                    }
                    if ( $value > ($type =~ /^aqi/i ? 1 : 0.25) ) {
                        # real value: update statistics
                        my $I = $value; my $J = $value;
                        $I = $value - $range * $stddev if defined $stddev;
                        $I = 0.05 if $I < 0.05;
                        $J = $value + $range * $stddev if defined $stddev;
                        $file{$pol}{period_min} = $I if $file{$pol}{period_min} > $I;
                        $file{$pol}{period_max} = $J if $file{$pol}{period_max} < $J;
                        $file{$pol}{period_avg} = ($file{$pol}{period_avg}*$file{$pol}{period_cnt} +
                            $value) / ($file{$pol}{period_cnt}+1);
                        $file{$pol}{period_cnt}++;
                        $file{$pol}{min} = $I if $file{$pol}{min} > $I;
                        $file{$pol}{max} = $J if $file{$pol}{max} < $J;
                        $file{$pol}{avg} = ($file{$pol}{avg}*$file{$pol}{cnt} +
                            $value) / ($file{$pol}{cnt}+1);
                        $file{$pol}{cnt}++;

                        $file{max} = $J if $file{max} < $J;
                        $file{$pol}{last_time} = $timing;
                        $file{$pol}{last_value} = $value;

                        $value = sprintf("%3.1f", $value);
                    } else { $value = "null"; }
                    # $timing *= 1000; # milli seconds since epoch
                    $file{$pol}{FD}->printf("%s,", ($col?"$col":"$value"));
                    if ( defined $stddev ) {
                        # range graph [avg-stddev,avg+stddev] 50% range
                        if( $value eq "null" ) {
                            $file{$pol}{STDDEV_FD}->printf("null,");
                        } else {
                            $file{$pol}{STDDEV_FD}->printf("%3.1f,", $stddev);
                        }
                    }
                }
                my @interval_stat = (); my @nulls = ();
                while (<STDIN>) {
                    chop;
                    s/\s+/ /g; s/NULL/null/g; s/pm_(10|25)/pm$1/g; s/pm25/pm2.5/g;
                    s/_$type//ig;
                    my @flds = split(/\s+/, $_);
                    print STDERR "WARNING: skip this record $_, nr fields($#flds) != CNT($CNT)\n"
                        if ($#flds !=  $CNT) && $#flds;
                    next if $#flds !=  $CNT;
                    if( ($#nulls < 0) || (not $strt) ){
                        @nulls = @flds; my $rec = 0;
                        for( my $i=0; $i <= $#flds; $i++) {
                            $rec++ if ($i > 0) && ($flds[$i] !~ /NULL/i);
                            $nulls[$i] =~ s/=.+/=null/g;
                        }
                        $strt = $flds[0];
                        next if not $rec;
                        $flds[0] -= $unit;
                    }
                    while ( int($strt/$unit) < (int($flds[0]/$unit) -1) ) {
                        # for every missing hour add a pollutant null value
                        for( my $i=1; $i <= $#nulls; $i++ ) {
                            if( $isAVG ) {
                                toJSON($strt, $nulls[$i], $nulls[$i+1]);
                                $i++;
                            } else {
                                toJSON($strt, $nulls[$i]);
                            }
                        }
                        $strt += $unit; $unit_cnt++;
                    }
                    next if int($strt/$unit) == int($flds[0]/$unit);
                    #if(((int($flds[0]/$unit)%$interval) == $remainder)
                    #    && ($#interval_stat >= 0) ){
                    #    for ( my $i = 0; $i <= $#interval_stat; $i++ ) {
                    #        my $P = $interval_stat[$i]; my $S = $interval_stat[$i];
                    #        $P =~ s/\(.*//; $S =~ s/.*\(//; $S =~ s/\)//;
                    #        printf STDOUT ("%s_STATINT_%s=%s\n",uc($type),$P,$S);
                    #    }
                    #    @interval_stat = ();
                    #}
                    for( my $i = 1; $i <= $#flds; $i++ ) {
                        my $pol = $flds[$i]; $pol =~ s/=.*//;
                        if( (int($flds[0]/$unit)%$interval) == $remainder ) {
                            if( $file{$pol}{cnt} * 2 > $interval ){ # 50% measurements
                              my $stats = "$pol(";
                              foreach my $stat ("avg","min","max") {
                                # one may delete _type extention to the pol name
                                $stats .= sprintf("%3.1f,",$file{$pol}{"period_".$stat});
                              }
                              $stats .= sprintf("%d)",$file{$pol}{"period_".cnt});
                              push @interval_stat, $stats;
                            }
                        }
                        if( $flds[$i] =~ /^AVG:/i ) {
                            if ( (defined $flds[$i+1]) && ($flds[$i+1] =~ /^STDDEV:/i) ) {
                                # output candle stick for avg, min and max day values
                                toJSON( $flds[0], $flds[$i], $flds[$i+1]);
                                $i++;
                            }
                        } else {
                            toJSON($flds[0],$flds[$i]);
                        }
                    }
                    $strt = $flds[0];
                    $unit_cnt++;
                }
                $unit_cnt--;    # last record was just time indicator
                # at the end of data processing
                $file{LASThr}=0; my $POLS = "";
                foreach my $pol (@nulls){ # statistics per pol
                    next if $pol !~ /=/; next if $pol =~ /^(MIN:|MAX:)/i;
                    $pol =~ s/=.*//; $pol =~ s/^AVG://i; $POLS .= ",$pol";
                    if( defined $file{$pol}{last_time} ){
                        printf STDOUT ("%s_LASTHR_${pol}=$file{$pol}{last_time}\n",
                            uc($type)) if $file{$pol}{last_time};
                        if( $file{LASThr} < $file{$pol}{last_time} ){
                            $file{LASThr} = $file{$pol}{last_time};
                            $file{LAST} = $file{$pol}{last_value};
                            $file{LASTpol} = $pol;
                            $file{LASTpol} =~ s/_(lki|aqi)$//;
                        } elsif( ($file{LASThr} == $file{$pol}{last_time}) 
                                && ($pol =~ /^(aqi|lki)$/) ){
                            $file{LAST} = $file{$pol}{last_value};
                            $file{LASTpol} = $pol;
                        }
                    }
                    printf STDOUT ("%s_LASTV_${pol}=$file{$pol}{last_value}\n",
                        uc($type))
                        if defined $file{$pol}{last_value};
                    next if not defined $file{$pol}{FD};
                    $file{$pol}{FD}->printf("\n/* last 24 hour period: min=%3.1f, avg=%3.1f, max=%3.1f, hour count %d */\n",
                        $file{$pol}{min},$file{$pol}{avg},
                        $file{$pol}{max}, $file{$pol}{cnt})
                            if $debug && (defined $file{$pol}{max}) && $file{$pol}{max} > 0;
                    $file{$pol}{FD}->printf("\n/* full period: min=%3.1f, avg=%3.1f, max=%3.1f hour count %d */\n",
                        $file{$pol}{period_min},$file{$pol}{period_avg},
                        $file{$pol}{period_max},$file{$pol}{period_cnt})
                            if $debug && (defined $file{$pol}{period_max}) &&
                                $file{$pol}{period_max};
                    printf STDOUT ("%s_STATINT_%s=%3.1f,%3.1f,%3.1f,%d\n",
                        uc($type),$pol,
                        $file{$pol}{period_avg},$file{$pol}{period_min},
                        $file{$pol}{period_max},$file{$pol}{period_cnt})
                            if (defined $file{$pol}{period_max}) &&
                                $file{$pol}{period_max};
                    # close pollutant json file
                    $file{$pol}{FD}->printf("]\n");
                    # $file{$pol}{FD}->printf(");\n");
                    close $file{$pol}{FD};
                    if ( defined $file{$pol}{STDDEV_FD} ) {
                        $file{$pol}{STDDEV_FD}->printf("]\n");
                        close $file{$pol}{STDDEV_FD};
                    }
                }
                $POLS =~ s/^,//; printf STDOUT ("%s_POLS=%s\n",uc($type),$POLS);
                printf STDOUT ("%s_COUNT=$unit_cnt\n",uc($type));# record count
                # max for height chart
                printf STDOUT ("%s_MAX=%d\n",uc($type),int($file{max}+0.99));
                printf STDOUT ("%s_MIN=%d\n",uc($type),int($file{min}+0.99));
                printf STDOUT ("%s_AVG=%d\n",uc($type),int($file{avg}+0.99));
                printf STDOUT ("%s_LAST=$file{LAST}\n",uc($type));# time last record
                printf STDOUT ("%s_LASTPOL=$file{LASTpol}\n",uc($type));# pol name
                my @aqi = AQI_view(uc($type),$file{LASTpol},$file{LAST},"noprint");
                $aqi[0] =~ s/0x/#/;
                printf STDOUT ("%s_LASTCOL=%06.6x\n",uc($type),$aqi[0]);
                printf STDOUT ("%s_LASTMSG=%s\n",uc($type),$aqi[1]);
                printf STDOUT ("%s_END=$file{LASThr}\n",uc($type)); # time last
                #printf STDOUT ("%s_TIME=%s\n",
                #    uc($type),strftime("%Y/%m/%d %H:%M",localtime(time)));
            ' \
            | sed 's/  */@/g' \
    )
    # previous will generate e.g.:
#		TYPE=LKI
#		LKI_START=1474007400
#		LKI_DATA_lki=@database-lki.json
#		LKI_DATA_lki_color=@database-lki_color.json
#		LKI_DATA_pm10=@database-LKI-pm10.json
#		LKI_DATA_pm2.5=@database-LKI-pm2.5.json
#               # avg,min,max,cnt
#		LKI_STAT_lki=2.2,1.2,3.6,23
#		LKI_STAT_pm10=1.3,0.6,1.8,22
#		LKI_STAT_pm2.5=1.1,0.4,2.6,23
#		LKI_STAT_lki=3.7,2.2,4.9,24
#		LKI_STAT_pm10=2.4,1.2,3.2,23
#		LKI_STAT_pm2.5=2.9,1.0,3.9,24
#		LKI_LASTHR_lki=1474183800
#		LKI_LASTV_lki=3.70
#		LKI_STATINT_lki=3.0,1.2,4.9,49
#		LKI_LASTHR_pm10=1474183800
#		LKI_LASTV_pm10=2.70
#		LKI_STATINT_pm10=1.9,0.6,3.2,47
#		LKI_LASTHR_pm2.5=1474183800
#		LKI_LASTV_pm2.5=2.60
#		LKI_STATINT_pm2.5=2.0,0.4,3.9,49
#		LKI_POLS=lki,lki_color,pm10,pm2.5
#		LKI_COUNT=48
#		LKI_MAX=5
#		LKI_LAST=3.70
#		LKI_LASTPOL=lki
#		LKI_LASTCOL=fffda4
#		LKI_LASTMSG=matig
#		LKI_END=1474183800

    # to do add check that every hour has one value!
    declare -A STAT
    for J in $STRG
    do
        local ELMNT=${J/=*/}
        J=${J/*=/}
        STAT[${ELMNT:-null}]=${J//@/ }
    done
    # max value of elements defines the chart height
    if [ -z "${STAT[${TYPE}_MAX]/#0*/}" ]
    then    # no elements in the chart
        echo "WARNING: no AQI index could be calculated: no MAX(${STAT[${TYPE}_MAX]}) chart." 1>&2
        echo "ERROR: giving up." 1>&2
        return 1
    fi

    local S
    echo "TBL=$TBL"
    echo "TYPE=${TYPE:-LKI}"
    echo "UNIT=${UNIT}"       # in secs
    echo "INTERVAL=${INTERVAL:-24}"
    echo "PERIODS=${PERIODS:-2}"
    echo "COUNT=${STAT[${TYPE}_COUNT]}"
    echo "START=$((${STAT[${TYPE}_START]}-$UNIT))"      # indent the graphs
    echo "END=${STAT[${TYPE}_END]}"
    if $MYSQL -e "DESCRIBE $TBL" | grep -E -q '^temp\s'
    then
        echo "LASTtemp=$($MYSQL -e "SELECT round(temp) FROM $TBL WHERE NOT ISNULL(temp) ORDER BY datum DESC LIMIT 1")"
    fi
    echo "LOCATION=${LOCATION}"
    echo "MUNICIPALITY=${MUNICIPALITY}"
    echo "ORGANISATION=${ORGANISATION}"
    echo "ALIAS=${ALIAS}"

    # collect the serie values serie 0 is total aqi, serie N is aqi per pol
    # collect statistical values per period: count, average, min, max 
    local -i SERIES=0
    local THIS_POL S
    if echo "${STAT[${TYPE}_POLS]}" | grep -q -E "(^|,)${TYPE,,}(,|$)"
    then        # aqi type graph first in the chart
        THIS_POL=${TYPE,,}
        S=(${STAT[${TYPE}_STATINT_${THIS_POL}]//,/ })
        if [ -z "${S[3]}" ] || (( ${S[3]} <= ($PERIODS*$INTERVAL/20) )) # 5% minimal
        then
            echo "ATTENTION: skip graph for comprehensive ${TYPE^^} Index got ${S[3]:-none} records for the ${PERIODS}P${INTERVAL}." 1>&2
        else
            echo "THIS_POL_$SERIES=${THIS_POL}"
            echo "DATA_$SERIES=BdP.${TYPE}.data$SERIES"
            echo "DATAFILE_$SERIES=${STAT[${TYPE}_DATA_${THIS_POL}]}"
            echo "COLORS_$SERIES=BdP.${TYPE}.colors$SERIES"
            echo "COLORSFILE_$SERIES=${STAT[${TYPE}_DATA_${THIS_POL}_color]}"
            S=(${STAT[${TYPE}_STAT_${THIS_POL}]//,/ })
            echo "AVG_$SERIES=${S[0]}"
            echo "MIN_$SERIES=${S[1]}"
            echo "MAX_$SERIES=${S[2]}"
            if [ -n "${STAT[${TYPE}_RANGEFILE_${THIS_POL}]}" ]
            then
                echo "RANGE_$SERIES=BdP.${TYPE}.range$SERIES"
                echo "RANGEFILE_$SERIES=${STAT[${TYPE}_RANGEFILE_${THIS_POL}]}"
            fi
            SERIES=$(($SERIES+1))
        fi
    fi
    POLs=(${STAT[${TYPE}_POLS]//,/ }) ; STAT[${TYPE}_POLS]=""
    for (( J=0; J < ${#POLs[@]}; J++))
    do
        if [ -z "${POLs[$J]/${TYPE,,}/}" ] || [ -z "${POLs[$J]/*_color*/}" ] || [ -z "${POLs[$J]/*so2*/}" ]
        then
            continue
        fi
        S=(${STAT[${TYPE}_STATINT_${POLs[$J]}]//,/ })
        if [ -z "${S[3]}" ] || (( ${S[3]} <= ($PERIODS*$INTERVAL/20) )) # 5% minimal
        then
            if (( $VERBOSE > 0 )) ; then
                echo "ATTENTION: skip graph for ${TYPE,,} of ${POLs[$J]}: got ${S[3]:-no} values in this time frame of  ${PERIODS}P${INTERVAL}." 1>&2
            fi
            continue
        fi
        THIS_POL=${POLs[$J]/_${TYPE,,}/}
        S=(${STAT[${TYPE}_STAT_${THIS_POL}]//,/ })
        STAT[${TYPE}_POLS]="${STAT[${TYPE}_POLS]},$THIS_POL"
        echo "THIS_POL_$SERIES=$THIS_POL"
        echo "DATA_$SERIES=BdP.${TYPE}.data$SERIES"
        echo "DATAFILE_$SERIES=${STAT[${TYPE}_DATA_${THIS_POL}]}"
        echo "COLORS_$SERIES=BdP.${TYPE}.colors$SERIES"
        echo "COLORSFILE_$SERIES=${STAT[${TYPE}_DATA_${THIS_POL}_color]}"
        echo "AVG_$SERIES=${S[0]}"
        echo "MIN_$SERIES=${S[1]}"
        echo "MAX_$SERIES=${S[2]}"
        if [ -n "${STAT[${TYPE}_RANGE_${THIS_POL}]}" ]
        then
            echo "RANGE_$SERIES=BdP.${TYPE}.range$SERIES"
            echo "RANGEFILE_$SERIES=${STAT[${TYPE}_RANGE_${THIS_POL}]}"
        fi
        SERIES=$(($SERIES+1))
    done
    S=(${STAT[${TYPE}_STATINT_${POLs[0]}]//,/ })
    echo "AVG=${S[0]}"
    echo "MIN=${S[1]}"
    echo "MAX=${S[2]}"
    echo "POLS=${STAT[${TYPE}_POLS]/#,/}"
    echo "HGT=${STAT[${TYPE}_MAX]:-0}"
    echo "LAST_0=${STAT[${TYPE}_LAST]:-0}"
    echo "LASThr=${STAT[${TYPE}_END]:-?}"
    echo "LASTpol_0=${STAT[${TYPE}_LASTPOL]:-?}"
    echo "LASTcol_0='#${STAT[${TYPE}_LASTCOL]:-FFFFFF}'"
    echo "LASTmsg_0=${STAT[${TYPE}_LASTMSG]:-onbekend}"
    echo "SERIES_CNT=$SERIES"
    echo "PERIODS=$PERIODS"
    echo "INTERVAL=$INTERVAL"
    echo "UNIT=$UNIT"
    if [ -n "$STDDEV" ] ; then echo "RANGE=${STDDEV}" ; fi

    return 0
}

# convert string of pollutant names to HTML index type of names
# optional arg1 HTML forces HTML coding
function POL2name() {
    local HTML=0
    if [ "${1:-NO}" = HTML ] ; then HTML=1 ; shift ; fi
    local NAME="$@"
    perl -e "\$_ = '$NAME';" \
        -e 's/(\w)\s+/$1, /;' \
        -e 's|/||g;' \
        -e 's/_//g;' \
        -e 's/([^a-z])([cns]o)([^a-z])/$1\U$2$3/g;' \
        -e 's/([a-z]+[0-9])/\U$1/g;' \
        -e 's/PM25/PM2.5/;' \
        -e "if ( $HTML ) {" \
        -e 's|([A-Z])([0-9\.]+)|$1<span style="font-size:60%">$2</span>|g;' \
        -e '}' \
        -e 'print $_;'
    return 0   
}

# convert hex HTML color to rgb(value): RR,GG,BB
function HEX2RGB() {
    local VAL=$1
    if ! echo $1 | grep -q -P -e "^#?[a-zA-Z0-9]{6}"
    then
        echo 0,0,0
        return 1
    fi
    if ! echo $1 | grep -q "^#" ; then 
        VAL='#'$VAL
    fi
    perl -e "printf('%d,%d,%d',hex(substr('$VAL',1,2)),hex(substr('$VAL',3,2)),hex(substr('$VAL',5,2)));"
    return $?
}

# calculate band definition in the graph
# PlotBand font-size band-color from to label-msg transparency max-value-with-label
function PlotBand() {
    local -i SMALL=${1:-100}
    local COL=${2:-000000} FROM=${3:-0}
    local TO=${4:-0} MSG=$5 TRP=${6:-0.15} MAX=${7:-1000} ROT=${8:--90} TTRP=${9:-0.6}
    echo -n "         {  color: 'rgba($(HEX2RGB $COL),$TRP)', from: $FROM, to: $TO"
    if (( ${HEIGHT/px/} < 210 )) ; then SMALL=$((${SMALL}*${HEIGHT/px/}/210)) ; fi
    if (( ${SMALL:-100} >= 75 ))
    then
        if (( ${FROM/.*/} <= ${MAX/.*/} ))
        then
            SMALL=$(( ${SMALL} * 12/10 ))
        fi
        echo -n ", label: { text: '$(POL2name HTML $MSG)', rotation: ${ROT}, style: { color: 'rgba($(HEX2RGB $COL),${TTRP})', fontWeight: 'bold', fontSize: '${SMALL}%'}, x: 15}"
    fi
    echo "}"
    return 0
}

# convert date to java script utc date YYYY,MM-1,DD-1,H
function JSdate() {
    echo 'Date.UTC('$(date --date=@${1} "+%Y %m %e %H" | sed 's/ 0/ /g' | awk '{ printf("%d,%d,%d,%d\n", $1, $2-1, $3-1, $4); }')')'
    return $?
}

# calculate rgba from HTML color
function COL2RGBA() {
    local COL="${1//[#\']/}"
    perl -e '
        use Graphics::ColorNames;
        sub Col2Hex {
            my $col = shift; return "000000" if not defined $col;
            return $col if $col =~ /^#?[0-9a-f]{6}$/i;
            return "000000" if $col !~ /^[a-z]+$/i;
            my $po = new Graphics::ColorNames;
            return $po->hex($col);
        }
        sub Col2RGBA {
            my ($col,$trans) = @_;
            $trans = 1 if (not defined $trans) || (not length($trans));
            $trans = 1 if "$trans" !~ /^(0(\.[0-9]+)?|1)$/;
            $col = Col2Hex($col); $col =~ s/^#//;
            my @rgb = map $_, unpack "C*", pack "H*", $col;
            printf("rgba(%s,%3.2f)\n", join(",",@rgb),$trans);
        }
        ' -e "Col2RGBA('$COL',$2);"
}
            
        
# calculate the best HTML text contrast color agains background HTML color
function COL2BCKGRND() {
    local COL="${1//[#\']/}"
    if ! echo "$COL" | grep -q -P "^[0-9A-Fa-f]{6}" ; then echo "$1"  ; return 1 ; fi
    perl -e '
        # calculate best contrasting text color on background colour
        sub YIG{
            my $col = shift; $col =~ s/^#//;
            return ((hex(substr($col,0,2))*299)+(hex(substr($col,2,2))*587)+(hex(substr($col,4,2))*114))/1000;
        }
        
        sub rgbToHex {
            if( $_[0] =~ /rgb\s*\(\s*([0-9]+)\s*,\s*([0-9]+)\s*,\s*([0-9]+)\s*\)/ ) {
                return sprintf("%2.2X%2.2X%2.2X",$1,$2,$3);
            } else { return $_[0]; }
        }
        
        use Graphics::ColorNames;
        sub Col2Hex {
            my $col = shift; return "000000" if not defined $col;
            return $col if $col =~ /^#?[0-9a-f]{6}$/i;
            return "000000" if $col !~ /^[a-z]+$/i;
            my $po = new Graphics::ColorNames;
            return $po->hex($col);
        }
        
        use Color::Scheme;
        # choose contrast text color to background
        sub Text_col {
            my $bg = shift;
            my @colors = @_;
            @colors = ("000000", "ffffff") if not defined $_[0];
            $colors[0] =~ s/^/#/ if $colors[0] =~ /^[0-9a-f]{6}$/i;
            $colors[1] =~ s/^/#/ if $colors[1] =~ /^[0-9a-f]{6}$/i;
            return $colors[0] if not defined $bg;
            $bg =~ s/^#//;
            $bg =~ s/([0-9a-f])([0-9a-f])([0-9a-f])/$1$1$2$2$3$3/
                if( $bg =~ /^[0-9a-f]{3}$/ );
            $bg = rgbToHex($bg) if $bg =~ /rgb\([0-9,\s]+\)/i;
            $bg = Col2Hex($bg) if $bg !~ /^#?[0-9a-f]{6}$/i;
            return $colors[0] if (not defined $bg) or ($bg !~ /^[0-9a-f]{6}$/i);
            return (YIG( $bg ) >= 128 ) ? $colors[0] : $colors[1];
        }

        # use complement color as scheme dark/light text
        sub Text_col_schemed {
            my $col = shift; my $set = shift;
            $set = 3 if (not defined $set) || ($set < 0);
            return "#000000" if (not defined $col) || (not $col);
            $col =~ s/^#//;
            $col =~ s/([0-9a-f])([0-9a-f])([0-9a-f])/$1$1$2$2$3$3/
                if( $col =~ /^[0-9a-f]{3}$/ );
            $col = rgbToHex($col) if $col =~ /rgb\([0-9,\s]+\)/i;
            $col = Col2Hex($col) if $col !~ /^#?[0-9a-f]{6}$/i;
            return "#000000" if (not defined $col) && ($col !~ /^[0-9a-f]{6}$/);;
            my $scheme = Color::Scheme->new();
            $scheme->from_hex($col);
            $scheme->scheme("analogic");
            $scheme->distance(0.25);
            $scheme->add_complement(1);
            $scheme->variation("hard");
            $scheme->web_safe(1);
            my @setlist = @{$scheme->colorset};
            $set = $#setlist if $set > $#setlist;
            return Text_col($col,$setlist[$set][1],$setlist[$set][2]);
        }
    ' -e "print Text_col_schemed('$COL');"
    return $?
}
#COL2BCKGRND "#1234FF"

# output style needed for choice KLI/AQI push button
# put this content into the local css style sheet!
function Get_BUTTONstyle() {
    if (( $DEBUG > 0 )) && (( ${#AQIs[@]} > 1 ))
    then
        cat <<EOF
    <style>
    .table-button {
        margin: 5px 0;
        border-radius: 20px;
        border: 2px solid #D0D0D0;
        border:1px solid #7d99ca; padding-top:8px;
        -webkit-border-radius: 20px;
        -moz-border-radius: 20px;
        font-size:10px;
        font-family:arial, helvetica, sans-serif;
        text-decoration:none; display:inline-block;
        text-shadow: -1px -1px 0 rgba(0,0,0,0.3);
        font-weight:normal;
        color: #FFFFFF;
        background-color: #A5B8DA; 
        background-image: -webkit-gradient(linear, left top, left bottom, from(#A5B8DA), to(#7089B3));
        background-image: -webkit-linear-gradient(top, #A5B8DA, #7089B3);
        background-image: -moz-linear-gradient(top, #A5B8DA, #7089B3);
        background-image: -ms-linear-gradient(top, #A5B8DA, #7089B3);
        background-image: -o-linear-gradient(top, #A5B8DA, #7089B3);
        background-image: linear-gradient(to bottom, #A5B8DA, #7089B3);
        filter:progid:DXImageTransform.Microsoft.gradient(GradientType=0,startColorstr=#A5B8DA, endColorstr=#7089B3);
        -webkit-box-shadow: #B4B5B5 3px 3px 3px;
        -moz-box-shadow: #B4B5B5 3px 3px 3px;
        box-shadow: #B4B5B5 3px 3px 3px  ;
        height: 24px;
        cursor: pointer;
        width: 50px;
        position: relative;
        display: inline-block; user-select: none;
        -webkit-user-select: none;
        -ms-user-select: none;
        -moz-user-select: none;
    }
    .table-button button:hover{
        background-color: #d4dee1; background-image: -webkit-gradient(linear, left top, left bottom, from(#d4dee1), to(#a9c0c8));
        background-image: -webkit-linear-gradient(top, #d4dee1, #a9c0c8);
        background-image: -moz-linear-gradient(top, #d4dee1, #a9c0c8);
        background-image: -ms-linear-gradient(top, #d4dee1, #a9c0c8);
        background-image: -o-linear-gradient(top, #d4dee1, #a9c0c8);
        background-image: linear-gradient(to bottom, #d4dee1, #a9c0c8);
        filter:progid:DXImageTransform.Microsoft.gradient(GradientType=0,startColorstr=#d4dee1, endColorstr=#a9c0c8);
    }
    .table-button button {
        margin: 0px 0 0 -3px;
        cursor: pointer;
        outline: 0;
        display:block;
        position: absolute;
        left: 0; top: 0; border-radius: 100%;
        width: 32px; height: 32px;
        background-color: white;
        float: left;
        border: 2px solid #D0D0D0;
        transition: left 0.4s;
        font-size:10px;
        font-family:arial, helvetica, sans-serif;
        text-decoration:none; display:inline-block;
        text-shadow: -1px -1px 0 rgba(0,0,0,0.3);
        font-weight:bold;
        color: #3b5d9c;
        background-color: #f2f5f6;
        background-image: -webkit-gradient(linear, left top, left bottom, from(#f2f5f6), to(#c8d7dc));
        background-image: -webkit-linear-gradient(top, #f2f5f6, #c8d7dc);
        background-image: -moz-linear-gradient(top, #f2f5f6, #c8d7dc);
        background-image: -ms-linear-gradient(top, #f2f5f6, #c8d7dc);
        background-image: -o-linear-gradient(top, #f2f5f6, #c8d7dc);
        background-image: linear-gradient(to bottom, #f2f5f6, #c8d7dc);
        filter:progid:DXImageTransform.Microsoft.gradient(GradientType=0,startColorstr=#f2f5f6, endColorstr=#c8d7dc);
    }
    .table-button-selected {
        background-color: #83B152;
        border: 2px solid #7DA652;
    }
    .table-button-selected button {
        left: 26px; top: -2px; margin: 0;
        box-shadow: 0 0 4px rgba(0,0,0,0.1);
    }
    </style>
EOF
    fi
}

# output DOM chart instantiation
function Get_CHARTscript() {
   local CHRT
   echo "Get_CHARTscript $@" >/dev/stderr
   echo "document.addEventListener('DOMContentLoaded', function () {"
   for CHRT in $@
   do
     case $CHRT in
     LKI|AQI)
        echo "const chart${CHRT} = Highcharts.stockChart('myscript${CHRT}',myscript${CHRT});"
     ;;
     FORECAST)
        echo "const forecast = new Meteogram(weather, '${CHRT}_'+AQItype[0]);"
     ;;
     esac
   done
   echo '});'
}

# output script for AQO choice button
# only two choices are supported for now
function Get_BUTTONscript() {
    local CH=($@) I M T
    if (( ${#CH[@]} > 1 ))
    then
        for (( I=0; I < ${#CH[@]}; I++ )) ; do CH[$I]="'${CH[$I]}'" ; done
        M="${CH[@]}" ; T="$M " ; M=${M// /,} ; T=${T//\' /table\', }
        cat <<EOF
    var index = 0,
    messg = [
        ${M}
    //    ,'geen tabel'
    ];
    tables = [
        ${T}
        'null'
    ];

    function toggleButton() { 
        var myTable = document.getElementById(tables[index++]);
        myTable.style.display = 'none';
        index = (index % messg.length);
        myTable = document.getElementById(tables[index]);
        myTable.style.display = 'block';
        var myButton = document.getElementById('tableButton');
        myButton.innerHTML = messg[(index+1)%messg.length];
    }

    \$(document).on('click', '.table-button', function() {
        \$(this).toggleClass('table-button-selected'); 
        var myTable = document.getElementById(tables[index++]);
        myTable.style.display = 'none';
        index = (index % messg.length);
        myTable = document.getElementById(tables[index]);
        myTable.style.display = 'block';
        var myButton = document.getElementById('tableButton');
        myButton.innerHTML = messg[index];
        });
EOF
    fi
}

# HighCharts options
function HighChartsOptions() {
        echo "
        Highcharts.setOptions({
            lang: {
                months: ['januari','februari','maart','april','mei','juni','juli','augustus','september','october','november','december'],
                shortMonths: ['jan','feb','mrt','apr','mei','jun','jul','aug','sep','oct','nov','dec'],
                weekdays: ['zondag','maandag','dinsdag','woensdag','donderdag','vrijdag','zaterdag'],
                shortWeekdays: ['zo','ma','di','wo','do','vr','za'],
                rangeSelectorTo: 'tot', rangeSelectorFrom: 'van',
        "
        echo -e "\n }\n });"
}

# get a collection of AQI values for an amount of hours
# arg0: font size (percentage, optional, dflt: 100%)
# arg0: types of index (dflt LKI): types LKI, AQI and optional arg0 LKI arg1 AQI 
# arg1: table name (dflt HadM)
# arg2: pollutants ("pm_10 no2") for the AQI calculation (dflt "all" available)
# arg3: nr of periods of 24 hours before end date/hour(dflt 2*24 hours)
# arg4: end date and hour (format see date cmd, dflt upto last one available)
OUTPUTscript=''         # output file for generated JS scripts
OUTPUTdata=''           # output file for generated JS data chart values
OUTPUTtable=''          # output file for generated HTML table elements
trap 'rm -f /var/tmp/AQI_*_*; exit' EXIT
function AQI_HTML() {
    local W=${1:-100%}
    local I
    local OUTPUT=/var/tmp/AQI_$$.html
    local AVAILABLE="LKI
AQI"
    declare -A URL
    URL[jquery]='https://ajax.googleapis.com/ajax/libs/jquery/1.12.4/jquery.min.js'
    URL[highstock]='http://code.highcharts.com/stock/highstock.js'
    URL[highstock-more]='http://code.highcharts.com/highcharts-more.js'
    URL[export]='http://code.highcharts.com/modules/exporting.js'
    URL[windbarb]='https://code.highcharts.com/modules/windbarb.js'
    #URL[highchart]='http://code.highcharts.com/highcharts.js'
    #URL[highchart-more]='http://code.highcharts.com/highcharts-more.js'
    #URL[pattern-fill]='https://code.highcharts.com/modules/pattern-fill.js'
    #URL[data]='https://code.highcharts.com/modules/data.js'
    #URL[accessibility]='https://code.highcharts.com/modules/accessibility.js'
    if [ -z "${1/[0-9]*/}" ] ; then W=$1 ;  shift ; fi
    local AQIs=()
    while [ -n "$1" ] && echo "$AVAILABLE" | grep -q "^${1}$"
    do
        AQIs+=(${1})
        shift
    done
    if [ "$1" = all ] ; then AQIs=($AVAILABLE) ; shift ; fi
    if (( ${#AQIs[@]} <= 0 )) ; then AQIs[0]=LKI ; fi  # default LKI only
    local END=${4}
    PERIODS=${3:-2P24} INTERVAL=${3:-2P24} UNIT=${UNIT:-3600}
    PERIODS=${PERIODS/P*/} ; INTERVAL=${INTERVAL/*P/}
    local POLLUTANTS=${2:-all}
    local TBL=${1:-HadM}

    # generate the scripts and table(s)
    local TYPES=''
    for (( I=0; I < ${#AQIs[@]}; I++ ))
    do
        if (( I > 0 )) ; then TYPES+="+" ; fi
        TYPES+=${AQIs[$I]}
        if ! TYPE=${AQIs[$I]:-LKI} TBL=${TBL:-HadM} AQI_generate $W ${AQIs[$I]} "${TBL:-HadM}" "${POLLUTANTS:-all}" "${PERIODS:-2}P${INTERVAL:-24}" "${END:-now}"
        then
            echo "ERROR: failed to generate ${AQIs[$I]} data from table $TBL." 1>&2
            return 1
        fi
    done
    if [ ! -s "$OUTPUTscript" ] || [ !  -s "$OUTPUTtable" ] || [ ! -s "$OUTPUTdata" ]
    then
        echo "ERROR: Table $TBL: failed to get generated script $OUTPUTscript, table content $OUTPUTtable or data $OUTPUTdata." 1>&2
        return 1
    fi

    # combine the [header] scripts and table(s) into one HTML file
    if (( $DEBUG <= 0 ))
    then
        OUTPUT=$(mktemp --tmpdir=/var/tmp AQI_HTML_XXXX)
    else
        # the needed JS libraries
       echo "<!DOCTYPE html><html>
<head>
<script src='${URL[jquery]}'></script>
<script src='${URL[highstock]}'></script>
<script src='${URL[highstock-more]}'></script>
<script src='${URL[export]}'></script>
<script src='${URL[windbarb]}'></script>
        " >$OUTPUT
        Get_BUTTONstyle ${AQIs[@]}      >>$OUTPUT
        echo '</head><body>' >>$OUTPUT
    fi

    # ###### start of JS script insertion
    echo '<script type="text/javascript">' >>$OUTPUT

    # if available compress the JS code
    local COMPRESS="/usr/bin/uglifyjs" # "yui-compressor --type js"
    COMPRESS=cat # To Do: seems uglify has errors on functions
    local FORECAST_ADDED
    if ! which ${COMPRESS/ */} >/dev/null ; then COMPRESS=cat ; fi 
    if (( $DEBUG > 0 )) ; then COMPRESS=cat ; fi
    if [ -n "${FORECAST[$TBL]}" ]
    then
        # forecast.pl LKI|AQI output_file City_name DIV_id
        # forecast.pl in verbose mode > 1 will print File= for data files
        if ! $FORECASTSCRPT ${FORECAST[$TBL,aqi]:-LKI}  /var/tmp/FORECAST ${FORECAST[$TBL]} FORECAST
        then
            echo "ERROR failed to generate forecast chart" 1>&2
            return 1
        else
            FORECAST_ADDED=${FORECAST[$TBL,aqi]:-LKI}
            FORECAST_ADDED=${FORECAST_ADDED/all/LKI AQI}
        fi
        if [ ! -s /var/tmp/FORECAST.GLOB.json ] || [ ! -s /var/tmp/FORECAST.DOM.json ]
        then
            echo "Empty /var/tmp/FORECAST.{GLOB,DOM}.json for ${FORECAST[$TBL]}. Skipped." 1>&2
            echo "$FORECASTSCRPT ${FORECAST[$TBL,aqi]:-LKI}  /var/tmp/FORECAST ${FORECAST[$TBL]} FORECAST" 1>&2
            return 1
        fi
    else
        echo "Definition FORECAST[$TBL] does not exist! What exists: ${FORECAST} and ${FORECAST[@]}." 1>&2
        return 1
    fi
    if [ ! -s /var/tmp/FORECAST.GLOB.json ] || \
        [ ! -s /var/tmp/FORECAST.DOM.json ] || \
        [ ! -s $OUTPUTdata ] || [ ! -s $OUTPUTscript ]
    then 
        if [ ! -s $OUTPUTdata ]
        then echo "Error file: outputdata: $OUTPUTdata for $TBL" 1>&2
        fi
        if  [ ! -s $OUTPUTscript ]
        then echo "Error file: outputscript: $OUTPUTscript for $TBL" 1>&2
        fi
        if  [ ! -s /var/tmp/FORECAST.GLOB.json ]
        then echo "No global forecast available $TBL." 1>&2
        fi
        if  [ ! -s /var/tmp/FORECAST.DOM.json ]
        then echo "No dom forecast avialable $TBL" 1>&2
        fi
        echo "Skipping $TBL" 1>&2
        return 1
    fi
    if ! (
      cat /var/tmp/FORECAST.GLOB.json ;
      echo 'var BdP = new Object();' ;
      cat $OUTPUTdata ;
      cat $OUTPUTscript ;
      cat /var/tmp/FORECAST.DOM.json ;
      Get_BUTTONscript ${AQIs[@]}
        ) | $COMPRESS  2>/dev/null >>$OUTPUT
    then
        echo "ERROR: failed to compress $OUTPUTscript to output $OUTPUT." 1>&2
        return 1
    fi
    Get_CHARTscript ${TYPES/+/ } ${FORECAST_ADDED/*I*/FORECAST} >>$OUTPUT
    echo "</script>" >>$OUTPUT
    rm -f /var/tmp/FORECAST.{GLOB,DOM}.json
    rm -f $OUTPUTscript $OUTPUTdata
    # ###### end of JS script insertion
        
    # ###### add the HTML table(s) to the output
    echo -n '<p>' >>$OUTPUT
    cat $OUTPUTtable >>$OUTPUT
    rm -f $OUTPUTtable
    echo '</p>' >>$OUTPUT
    local BLOCK=block
    for I in $FORECAST_ADDED    # ### add forecast HTML code if needed
    do
        cat >>$OUTPUT <<EOF
<div class='${I}table' id='${I}table' style='display: $BLOCK'>
<p><table style='color:black;background:#f9f9f9;border-radius:7px;-moz-border-radius:7px;-webkit-border-radius:7px;box-shadow: 0px 7px 10px 0px #a0a0a0;text-align:left;padding:0px;padding-top:3px;padding-bottom:0.3%;margin:0px;border-spacing:0px;border:0px solid black;width:100%';>
<caption valign=top align=center><span style='color:#0376ab'>Verwachting fijnstof PM<span style='font-size:70%'>2.5</span> (<a href='https://aqicn.org/city/netherland/horst-a/d-maas/hoogheide/' title='more local forecasts weather and Air Quality Index'>AQICN</a>) en weer (<a href='https://www.yr.no/place/Netherlands/Limburg/Grubbenvorst/' title='more local weather information'>YR.no</a>) voor komende 48 uur voor Horst a/d Maas</span>
</caption>
<tbody>
<tr><td><div id='FORECAST_${I}' style='width: 100%; height: 310px; margin: 0 auto'>PM2.5 en weersverwachting voor komende 48 uur</div></td></tr>
</tbody>
</table>
</div>
EOF
    BLOCK=none  # all followers are not displayed
    done

    # close it up
    if (( $DEBUG > 0 ))
    then
        echo -e "</body>\n</html>" >>$OUTPUT
    fi
    # ##### end of HTML table code insertion

    local U=hours
    if (( ${UNIT} > 3600 )) ; then U=days ; fi
    if (( $DEBUG <= 0 ))        # push the HTML code to the website dir
    then
       # this generated file is included via dagwaarden.html
       # dagwaarden.html is generated by Day_results.sh
       cp $OUTPUT $WWW/${TYPES}-${U}_${TBL}.html
       rm -f $OUTPUT
       OUTPUT=$WWW/${TYPES}-${U}_${TBL}.html
       chmod go+r $OUTPUT
       chgrp $GRP $OUTPUT
       if (( $VERBOSE > 0 )) ; then 
           echo "FILE=$OUTPUT"
       fi
    fi
    if (( $VERBOSE > 0 ))
    then
        echo "New ${PERIODS} periods of $((INTERVAL*UNIT/(24*3600))) days in units of $((UNIT/3600)) hours chart for ${TBL} on $OUTPUT" 1>&2
    fi

    rm -f /var/tmp/AQI_{HTML,scripts,tables}_*  # and clean up
    return 0
}

# highchart script and table generation
# out put in 2 files: script part and html body part with only the tables
# uses the OUTPUTscript and OUTPUTtable tables
function AQI_generate() {
    local TBL=${3:-${TBL:-HadM}}
    declare -A OPT
    declare -A  POLCOL URL
    POLCOL[pm_25]='#bb0000'
    POLCOL[pm2.5]=${POLCOL[pm_25]}
    POLCOL[pm_10]='#8b4600'
    POLCOL[pm10]=${POLCOL[pm_10]}
    POLCOL[o3]='#003f8b'
    POLCOL[no2]='#07008b'
    POLCOL[so2]='#7e5000'
    POLCOL[co]='#006400'
    POLCOL[co2]='#006437'
    POLCOL[roet]='#373737'
    POLCOL[aqi]='#6a30f0'
    POLCOL[lki]='#bb30f0'
    URL[RIVM]="https://www.lml.rivm.nl/tabel"
    URL[PLIM]="https://www.luchtmeetnet.nl/stations/limburg/alle-gemeentes/alle-stoffen"
    URL[DENRWF]='https://www.umweltportal.nrw.de/servlet/is/811/'
    URL[AQI]="http://www.airqualitynow.eu/nl/about_indices_definition.php"
    URL[LKI]="http://www.rivm.nl/Documenten_en_publicaties/Algemeen_Actueel/Nieuwsberichten/2015/Nieuwe_app_mijn_luchtkwaliteit_gelanceerd"
    URL[AQHI]="https://www.ec.gc.ca/cas-aqhi/default.asp?Lang=En&n=065BE995-1"
    URL[CAQI]="http://www.airqualitynow.eu/about_indices_definition.php"

    local -i SMALL=100
    # width and height generated chart image
    # AQICN.org: WIDTH=310px HEIGHT=46px
    HEIGHT=${HEIGHT:-400px} ; WIDTH=${WIDTH:-540px}
    if [ -z "${WIDTH/*\%/}" ]
    then
        WIDTH="$((${WIDTH/\%/} * 540 / 100))px"
    fi
    # do we have a small chart image?
    if [ -n "$1" ] && echo "${1,,}" | grep -q -P "(.*small|[0-9]+%)"
    then
        SMALL=${1/\%/}
        case ${SMALL} in
        xx-small) SMALL=70 ;;
        x-small)  SMALL=80 ;;
        small)    SMALL=90 ;;
        esac
        shift
    fi
    if (( ${HEIGHT/px/} < 150 ))
    then
        SMALL=$(( ($SMALL * (${HEIGHT/px/}*100/150))/100 ))
    fi

    local INFO=$(TBL=${TBL:-HadM} TYPE=$TYPE DataCollect "$@" | sed 's/ /@/g')
    if echo "${INFO:-ERROR}" | grep -q ERROR ; then return 1 ; fi
    local -i I OUT=1
    INFO=($INFO)
    for(( I=0; I < ${#INFO[@]}; I++))
    do
        # INFO[$I]=${INFO[$I]//@/ /}
        # INFO[$I]=${INFO[$I]// \// /}
        INFO[$I]=$( echo "${INFO[$I]}" | perl -e 'while(<STDIN>){ s/@/ /g; s|\s/| |g; print $_;}')
        OPT[${INFO[$I]/=*/}]=${INFO[$I]/*=/}
        if (( $DEBUG > 0 ))
        then
            echo "Collected: ${INFO[$I]/=*/} = ${INFO[$I]/*=/}" 1>&2
        fi
    done

    # get the chart data definitions
    if [ -z "$OUTPUTdata" ]
    then
        OUTPUTdata=$(mktemp --tmpdir=/var/tmp AQI_DATA_XXXX)
        OUT=0
    fi
    echo "BdP.${TYPE} ={" >>${OUTPUTdata}
    local DT
    for DT in DATA COLORS RANGE
    do
        for ((I=0; I <= ${OPT[SERIES_CNT]}  ; I++))
        do
            if [ -z "${OPT[${DT}FILE_$I]}" ] ; then break ; fi
            if [ ! -s "${OPT[${DT}FILE_$I]}" ] ; then continue ; fi
            if (( $DEBUG > 1 )) ; then
                echo "add ${DT,,} JS data from file ${OPT[${DT}FILE_$I]} to ${OUTPUTdata}." 1>&2
            fi
            echo -n "${DT,,}$I: " >>${OUTPUTdata}
            cat ${OPT[${DT}FILE_$I]} >>${OUTPUTdata}
            echo ',' >>${OUTPUTdata}
            rm -f ${OPT[${DT}FILE_$I]}
            if [ $DT = RANGE ] && [ -n "${OPT[RANGE]}" ]
            then
                local J
                for(( J=1 ; $J <= ${OPT[RANGE]} ; J++)) # JS placeholder
                do echo "${DT,,}${I}${J}: []," >>${OUTPUTdata} ; done
            fi
        done
    done
    echo "};" >>${OUTPUTdata}
    if [ -n "${OPT[RANGE]}" ]
    then
        export RANGE=${OPT[RANGE]}
        for((I=0; I <= ${OPT[SERIES_CNT]}  ; I++))
        do
            if [ -z "${OPT[RANGEFILE_$I]}" ] ; then continue ; fi
            for(( J=1 ; J <= ${OPT[RANGE]}; J++))
            do
                echo "
                for (var i = 0; i < BdP.${TYPE}.range${I}.length; i++) {
                    BdP.${TYPE}.range${I}${J}[i] = new Array(2);
                    if ( BdP.${TYPE}.range${I}[i] == null ) {
                        BdP.${TYPE}.range${I}${J}[i][0] = null;
                        BdP.${TYPE}.range${I}${J}[i][1] = null;
                        continue;
                    }
                    BdP.${TYPE}.range${I}${J}[i][0] = BdP.${TYPE}.data${I}[i] - $J * BdP.${TYPE}.range${I}[i];
                    BdP.${TYPE}.range${I}${J}[i][1] = BdP.${TYPE}.data${I}[i] + $J * BdP.${TYPE}.range${I}[i];
                    if( BdP.${TYPE}.range${I}${J}[i][0] < 0.05 ) {
                        BdP.${TYPE}.range${I}${J}[i][0] = 0.05; }
                }
            " >>${OUTPUTdata}
            done
        done
    fi
    if (( $DEBUG > 1 )) ; then echo "Created: ${OUTPUTdata} with $TYPE script data." 1>&2 ; fi
            
    local PERIODS=${OPT[PERIODS]} INTERVAL=${OPT[INTERVAL]} UNIT=${OPT[UNIT]}
    local TFRAME=uren
    if (( $UNIT > 3600 )) ; then TFRAME=dagen ; fi
    OPT[ID]="myscript${OPT[TYPE]}"
    OPT[WIDTH]=${WIDTH:-540px}
    OPT[HEIGHT]=${HEIGHT:-400px}
    OPT[SMALL]="style:{fontSize:'${SMALL}%'},"
    local -i START=${OPT[START]}
    if (( $SMALL >= 100 )) && ((${WIDTH/px/} > 500))
    then        # we need to shift one place for band labels location
        START=$(($START - $UNIT))
        OPT[LBLFRMT]='dateTimeLabelFormats: { day:"%a %e %b", hour:"%Hh" },'
    else
        OPT[LBLFRMT]='dateTimeLabelFormats: { day:"%a", hour:"%Hh" },'
    fi
    local STR
    OPT[Xlines]="plotLines: ["
    local XSTRT=$(( ((${OPT[START]}+(($INTERVAL-1)*$UNIT))/($INTERVAL*$UNIT)*($INTERVAL*$UNIT)) ));
    XSTRT=$(date --date=@$XSTRT "+%Y/%m/%d") # get rid of DST and zone time difference
    XSTRT=$(date --date="$XSTRT" +%s)
    if (( $XSTRT < ${OPT[START]} )) ; then XSTRT=$(($XSTRT+($INTERVAL*$UNIT) )) ; fi
    for(( STR=((${OPT[START]}+(($INTERVAL-1)*$UNIT))/($INTERVAL*$UNIT)*($INTERVAL*$UNIT)); STR <= ${OPT[END]}; STR += ($INTERVAL*$UNIT) ))
    do
       OPT[Xlines]+="{color:'lightgray',dashStyle:'Dot',width:2,value:$(($STR * 1000)),zIndex:3},"
    done
    OPT[Xlines]=$(echo "${OPT[Xlines]}" | sed 's/,$//')
    OPT[Xlines]+="],"
    OPT[START]=$(JSdate ${OPT[START]})
    # OPT[START]=$(((${OPT[START]}+${UNIT}/2)/${UNIT}*${UNIT}))
    OPT[ZOOM]='' ; OPT[CHART]=highchart ; export CHART=highchart
    if (( ($PERIODS * $INTERVAL) > (4*24) ))    # 4 days of hourly or 76 days
    then
        export ZOOM=1
        OPT[ZOOM]="zoomType: 'x',"
    fi
    if (( ($PERIODS * $INTERVAL) >= (14*24) ))  # 2 weeks of hrly or 296 days
    then        # avoid extra traffic for minor amounts of chart data
        if (( $VERBOSE > 0 )) ; then
            echo "WARNING: $INTERVAL * $PERIODS > 360 records, using Stock Charts." 1>&2
        fi
        OPT[CHART]=highstock ; export CHART=highstock
    fi
    local WD=${WIDTH/px/} HT=0
    if (( "${HEIGHT/px/}" >= 100 ))
    then
        if (( ${HEIGHT/px/} < 250 )) ; then HT=-10 ; fi
        if [ -z "${WD/*\%/}" ] ; then WD=$((${WD/\%/} * 540 / 100)) ; fi
        if (( $WD < 540 ))
        then
            WD=$(($SMALL * $WD / 540))
        else
            WD=$SMALL
        fi
        OPT[TITLE]="
          title: {
           text: '' /*'${OPT[LOCATION]//\/}: ${OPT[TYPE]} index t.a.v. ${PERIODS}x${INTERVAL} $TFRAME'*/,
            y: 40${HT},
            align: 'center',
            style: {
                fontSize: '$((${WD} * 12/10))%',
                textShadow: '1px 1px 3px #777777',
                color: '#314877'
            }
          },
          subtitle: {
           text: '' /*'${OPT[TYPE]}($(POL2name HTML ${OPT[POLS]})): min ${OPT[MIN]}, gem ${OPT[AVG]}, max ${OPT[MAX]}' */,
            y: 40${HT}+14,
            align: 'center',
            style: {
                fontSize: '$((${WD} * 12/10 -10))%',
                textShadow: '1px 1px 3px #777777',
                color: '#314877'
            },
          },"
    else
        OPT[TITLE]="   title: { text: null },"
    fi
    case ${OPT[TYPE]^^} in
    AQI)
        OPT[XBANDS]="
          $(PlotBand $SMALL 00e400 0 50 goed 0.1 ${OPT[HGT]:-${OPT[MAX]}}),
          $(PlotBand $SMALL ffff00 50 100 matig 0.1 ${OPT[HGT]:-${OPT[MAX]}} -90 0.95),
          $(PlotBand $SMALL ff7e00 100 150 opgepast 0.1 ${OPT[HGT]:-${OPT[MAX]}} 0),
          $(PlotBand $SMALL ff0000 150 200 ongezond 0.1 ${OPT[HGT]:-${OPT[MAX]}} 0),
          $(PlotBand $SMALL 8f3f97 200 300 gevaarlijk 0.1 ${OPT[HGT]:-${OPT[MAX]}} 0),
          $(PlotBand $SMALL 7e0023 300 500 hachelijk 0.1 ${OPT[HGT]:-${OPT[MAX]}} 0)
            "
        OPT[YPOSITIONS]="0,51,101,151,201,301,501"
        # TO DO: OPT[ZONES]="
        #  zones: [
        #    { value:0,fillcolor:'#00e400' },
        #    { value:50,fillcolor:'#ffff00' },
        #    { value:100,fillcolor:'#ff7e00' },
        #    { value:150,fillcolor:'#ff0000' },
        #    { value:200,fillcolor:'#8f3f97' },
        #    { value:300,fillcolor:'#7e0023' },
        #    ],"
    ;;
    LKI)
        OPT[XBANDS]="
          $(PlotBand $SMALL 0020C5 0 3 goed 0.15 ${OPT[HGT]:-${OPT[MAX]}}),
          $(PlotBand $SMALL f4e645 3 6 matig 0.15 ${OPT[HGT]:-${OPT[MAX]}} -90 0.9),
          $(PlotBand $SMALL fe7626 6 8 onvoldoende 0.15 ${OPT[HGT]:-${OPT[MAX]}} 0),
          $(PlotBand $SMALL dc0610 8 10 slecht 0.15 ${OPT[HGT]:-${OPT[MAX]}} 0),
          $(PlotBand $SMALL a21794 10 12 "zeer slecht" 0.15 ${OPT[HGT]:-${OPT[MAX]}} 0)
              "
        OPT[YPOSITIONS]="0,3,5.4,8,10,12
                    // 0,0.5,1,1.5,2,2.5,3,3.6,4.2,4.8,5.4,6.0,6.7,7.4,8.0,9.0,10.0,11.0
              "
        # TO DO: OPT[ZONES]="
        #  zones: [
        #    { value:0,fillcolor:'#0020C5' },
        #    { value:3,fillcolor:'#f4e645' },
        #    { value:6,fillcolor:'#fe7626' },
        #    { value:8,fillcolor:'#dc0610' },
        #    { value:10,fillcolor:'#a21794' },
        #    { value:12,fillcolor:'#7e0023' },
        #    ],"
    ;;
    esac
    OPT[SERIES]=''
    local VISIBLE=true
    for(( I=0; I < ${OPT[SERIES_CNT]:-0} ; I++))
    do
        if (( $I < 1 )) && (( ${OPT[UNIT]:-3600} <= 3600 ))
        then
            OPT[SERIES]="
        { type: 'column',
          pointStart: ${OPT[START]},
          pointInterval: ${OPT[UNIT]:-3600} * 1000,
          name: '${OPT[TYPE]}($(POL2name HTML ${OPT[POLS]}))',
          data: ${OPT[DATA_$I]},
          colors: ${OPT[COLORS_$I]}
        }"
           OPT[LEGEND]=false
           VISIBLE=false
        elif (( $I < 1 )) && (( ${OPT[UNIT]:-3600} > 3600 ))
        then
            # avg and stddev range case: alternative to columns
            OPT[SERIES]="
        { type: 'spline',     /* dayly average */
          pointStart: ${OPT[START]},
          pointInterval: ${OPT[UNIT]:-3600} * 1000,
          name: 'daggemiddelde ${OPT[TYPE]}',
          data: ${OPT[DATA_$I]},
          color: '${POLCOL[${OPT[THIS_POL_$I]/ */}]:-#222222}',
          lineWidth: 1+$(( ($SMALL+20)/100 )),
          shadow: { color: '${POLCOL[${OPT[THIS_POL_$I]/ */}]:-#222222}',
            width: 15, offsetX: 0, offsetY: 0
          },
          marker:{
            fillColor: '${POLCOL[${OPT[THIS_POL_$I]/ */}]:-#222222}',
            radius: 1+$(( ($WD*2)/100 ))
          },
          zIndex: ${OPT[RANGE]:-0}
        }"
            if [ -n "${OPT[RANGE_$I]}" ] && [ -n "${OPT[RANGE]}" ]
            then
                local -i J
                for(( J=1; J <= ${OPT[RANGE]:-2}; J++))
                do
            OPT[SERIES]+=",
        { type: 'arearange',    /* stddev area */
          pointStart: ${OPT[START]},
          pointInterval: ${OPT[UNIT]:-3600} * 1000,
          name: '$(( 10 + ($J * 40) ))% spreiding',
          data: ${OPT[RANGE_$I]}$J,
          zIndex: $((${OPT[RANGE]:-2} - $J)),
          linkedTo: ':previous',
          fillOpacity: 0.9,
          lineWidth: 0,
          fillColor: '$(COL2RGBA ${POLCOL[${OPT[THIS_POL_$I]/ */}]:-#222222} 0.$((35-$J*10)) )',
          color: '$(COL2RGBA ${POLCOL[${OPT[THIS_POL_$I]/ */}]:-#222222} 0.1)',
          ${OPT[ZONES]}
        }"
                done
            fi
           OPT[LEGEND]=false
           VISIBLE=false
        else
            if(($SMALL >= 65 )) && [ ${HEIGHT/px/} -gt 150 ]
            then
                OPT[LEGEND]=true
                OPT[SERIES]+=",
            { type: 'spline',
              pointStart: ${OPT[START]},
              pointInterval: ${OPT[UNIT]:-3600} * 1000,
              name: '${OPT[TYPE]}($(POL2name HTML ${OPT[THIS_POL_$I]}))',
              data: ${OPT[DATA_$I]},
              color: '${POLCOL[${OPT[THIS_POL_$I]/ */}]:-#222222}',
              lineWidth: 1+$(( ($SMALL+20)/100 )),
              visible: ${VISIBLE},
              zIndex: ${OPT[RANGE]:-1},
              marker:{
                fillColor: '${POLCOL[${OPT[THIS_POL_$I]/ */}]:-#222222}',
                radius: 1+$(( ($WD*2)/100 ))
              }
            }"
            fi
        fi
    done

    # the highchart javascript content
    if [ -z "$OUTPUTscript" ]
    then
        OUTPUTscript=$(mktemp --tmpdir=/var/tmp AQI_scripts_XXXX)
        OUTPUTtable=$(mktemp --tmpdir=/var/tmp AQI_tables_XXXX)
        HighChartsOptions >$OUTPUTscript
    fi
    # the highchart definitions for this chart
    local TICK=6
    if (( $UNIT > 3600 )) ; then TICK=7 ; fi
    #echo -n "\$('#${OPT[ID]}').highcharts(" >>$OUTPUTscript
    echo -n "${OPT[ID]} = " >>$OUTPUTscript
    if [ $CHART = highstock ] ; then
        OPT[ZOOM]=''    # no need to zoom
        if (( $UNIT < 24*3600 )) ; then
        cat >>$OUTPUTscript <<EOF
        {
            rangeSelector: {
            selected: 0,
            height: 40,
            buttonPosition: { y: 2 },
            buttons: [
                { type: 'day', count: 3, text: '3d',
                 // dataGrouping: { forced: true, units:[['hour',[1]]]}
                },
EOF
        else
        cat >>$OUTPUTscript <<EOF
        {
            rangeSelector: {
            selected: 1,
            height: 40,
            buttonPosition: { y: 2 },
            buttons: [
EOF
        fi
        cat >>$OUTPUTscript <<EOF
                { type: 'week', count: 1, text: 'week',
                 // dataGrouping: { forced: true, units:[['day',[1]]]}
                },
                { type: 'month', count: 1, text: 'maand',
                 // dataGrouping: { forced: true, units:[['day',[1]]]}
                },
EOF
        if (( $PERIODS * $INTERVAL * $UNIT > ((52+26)*7*24*3600) )) # more as 1.5 year
        then
            echo"{ type: 'year', count: 1, text: 'jaar',
                 // dataGrouping: { forced: true, units:[['month',[1]]]}
                }," >>$OUTPUTscript
        fi
        cat >>$OUTPUTscript <<EOF
            ],
            buttonTheme: { // styles for the buttons
                fill: 'none',
                stroke: 'none',
                'stroke-width': 0, r: 8,
                style: {
                    color: '#37508f',
                    fontWeight: 'bold',
                    fontSize: '70%'
                },
                states: {
                    hover: {
                    },
                    select: {
                        fill: '#37508f',
                        style: {
                            color: 'white'
                        }
                    }
                    // disabled: { ... }
                }
            },
            inputPosition: { y: -23 },
            inputBoxBorderColor: 'rgba(0,0,0,0)',
            inputBoxWidth: 65,
            inputBoxHeight: 15,
            inputStyle: {
                color: '#37508f',
                fontWeight: 'bold',
                fontSize: '80%'
            },
            labelStyle: {
                color: '#37508f',
                fontWeight: 'bold',
                fontSize: '80%'
            },
            scrollbar: { enabled: false },
            inputEnabled: true
        },
EOF
    else
        echo '{' >>$OUTPUTscript
    fi
    cat >>$OUTPUTscript <<EOF
        ${OPT[TITLE]}
        chart: {
            type: 'column',
            borderRadius: 3,
            borderWidth: 1,
            backgroundColor: '#ffffff',
            borderColor: 'silver',
            shadow: true,
            margin: [28,6,7,6],
            spacing: [25,12,10,5],
            ${OPT[ZOOM]}
        },
        legend: {
            // title: { text: 'legendum' },
            layout: 'vertical',
            borderRadius: '3px',
            backgroundColor: 'rgba(196,206,228,0.5)',
            align: 'left',
            y: 2,
            itemStyle: { fontSize: '$((${SMALL}*75/100))%', color: '#314877' },
            itemHiddenStyle: { color: '#4a6396' },
            verticalAlign: 'center',
            enabled: ${OPT[LEGEND]},
            labelFormatter: function() { return this.name + ' (toon grafiek)'; }
        },
        credits: { enabled: false },
        tooltip: {
            shared: true,
            valueDecimals: 1,
            dateTimeLabelFormats: {
                hour:"%a %e %b om %H uur",
                day: '%e %B %Y'
            }
        },
        xAxis: {
            labels: {
                ${OPT[SMALL]}
                reserveSpace: false,
                step: 1
            },
            tickInterval: $TICK * $UNIT * 1000, // per 6 hours or per 7 days
            type: 'datetime',
            tickPosition: "outside",
            tickLength: $((5*${SMALL}/100)),
            minorTickInterval: 2,
            minorTickLength: $((2 + (18*${SMALL}-16*50)/50)),
            minorTickPosition: 'outside',
            // minorGridLineDashStyle: 'solid',
            lineWidth: 1,
            opposite: true,
            ${OPT[LBLFRMT]}
            ${OPT[Xlines]}
            crosshair: { dashStyle: 'dot' }
        },
        yAxis: { 
              // title: { text: '${OPT[TYPE]^^} Index' },
              title: { text: null },
              plotBands: [ ${OPT[XBANDS]} ],
              tickPositioner: function () {
                var positions = [], pos = [ ${OPT[YPOSITIONS]} ], tick =0;
                if (this.dataMax !== null && this.dataMin !== null) {
                    positions.push(pos[tick]);
                    for (tick = 1; tick < pos.length; tick++) {
                        if ( pos[tick] > this.dataMax ) { break; }
                    }
                    positions.push(pos[tick]*110/100);
                }
                return positions;
            }
        },
        plotOptions: {
            series: { groupPadding: 0, borderWidth: 0.3, pointPadding: 0.03 },
            column: { shadow: true, colorByPoint: true, showInLegend: false },
            spline: { shadow: false }
        },
        series: [ ${OPT[SERIES]} ]
    };
EOF

    # generate the table for this chart
    local -i AQInr=1 
    # adjust some values
    OPT[END]=$((${OPT[END]} - 60*60))   # minus one hour
    if [ "${OPT[LAST_0]}" = "?" ] ||(( ${OPT[LAST_0]/.*/} < 1 )) ; then
        OPT[LAST_0]='?' ; OPT[LASTcol_0]='#4a5744' ; OPT[LASTmsg_0]=onbekend
    fi
        
    local LASTtemp=''
    if [ ! -s $OUTPUTtable ]
    then        # first table output and mote tables to come: add choice button
        AQInr=0
        if [ -n "${OPT[LASTtemp]}" ]
        then
            LASTtemp="<br /><span style='font-size:90%;padding-top:0.5%;'><span title='plaatselijke gemeten buitentemperatuur op $ENDstrg'>temperatuur bij laatste meting: <span temp='${OPT[LASTtemp]:-onbekend}'><b>${OPT[LASTtemp]:-onbekend}</b>${OPT[LASTtemp]/*[0-9]*/ &deg;C}</span></span></span>"
        fi
        # explanation of the chart
        if (( ${#AQIs[@]} > 1 )) ; then
        cat >>$OUTPUTtable <<EOF
<table width=100% border=0 bordercolor=white><tr><td style='padding-right:25px'><div class="table-button" title="Druk (click) op deze knop om van luchtkwaliteits index weergave te wisselen bijv. van ${AQIs[0]} naar de ${AQIs[1]} index berekening en visa versa."><span style="position:relative;left:7px;top:-3px;">${AQIs[0]}&nbsp;&nbsp;${AQIs[1]}</span><button id="tableButton"><div style="margin-right:-10px">${AQIs[0]}</div></button><span style="position:absolute;top:30px;left:0px;text-shadow:none;text-weight:bold;color:#3b5d9c">keuzeknop&nbsp;Index&nbsp;type</span></div></td><td>De onderstaande tabel met de recente luchtkwaliteits Index voor ${OPT[LOCATION]//\//} geeft de indexwaarden weer voor de ${AQIs[0]} of ${AQIs[1]} Index over ${PERIODS} perioden van ${OPT[INTERVAL]} ${TFRAME}.
EOF
        else
        cat >>$OUTPUTtable <<EOF
<table width=100% border=0 bordercolor=white><tr><td title="Gebruik de cursor om een selectie te maken van de periode en/of meer detail informatie over een meting.">De onderstaande tabel met de recente luchtkwaliteits Index voor ${OPT[LOCATION]//\//} geeft de indexwaarden weer voor de ${AQIs[0]} Index over ${PERIODS} perioden van ${OPT[INTERVAL]} ${TFRAME}.
EOF
        fi
        if [ -n "${OPT[RANGE]}" ]
        then    # day average case
        cat >>$OUTPUTtable <<EOF
        In de grafiek wordt de Index met een gemiddelde dagwaarde aangegeven. De z.g. statistische 50%, resp. 90% spreiding t.o.v. de gemiddelde dag Index waarden wordt met een achtergrondskleur aangegeven.
EOF
        fi
        # the chart how to
        if (( ${#AQIs[@]} > 1 )) ; then
            echo -n "<br />Met de keuzeknop kan ook het type van de Index standaard gewijzigd worden." >>$OUTPUTtable
        fi
        cat >>$OUTPUTtable <<EOF
</td></tr><tr><td colspan=2>In de legendum kan door aanklikken de grafiek met indexwaarden voor een enkele emissiestof aan- of uitgezet worden.<br />De berekende indexwaarde en de kwalificatie over meerdere vervuilende stoffen kan hoger uitvallen dan de indexwaarde van elke emissiestof apart.
<br />De Index wordt berekend over alle beschikbaar gestelde meetwaarden van de lokatie welke voor de Index berekening van belang zijn.<br />Alle gebruikte (ruwe) meetwaarden zijn statistisch (Chi-kwadraad test) gevalideerd.<br />De Index over alle beschikbare Indices wordt alleen berekend en weergegeven indien er minimaal twee indexwaarden van de indicatoren bekend zijn.
EOF
        fi
        if [ -n "${OPT[ZOOM]}" ]
        then    # zooming is enabled
        cat >>$OUTPUTtable <<EOF
<br />De grafiek heeft een z.g. zoom functie. Door met de muis een bepaalde periode te selecteren wordt ingezoomd op die periode.
EOF
        fi
        if [ $CHART = highstock ] ; then
        cat >>$OUTPUTtable <<EOF
<br />De grafiek heeft de mogelijkheid om een bepaalde periode van de grafiek te laten zien. Met de "slider" kan de periode vergroot, verkleind of verschoven worden.
EOF
        echo '</td></tr></table><br />' >>$OUTPUTtable
    fi
    echo "<!-- ${OPT[TYPE]} index ${OPT[LOCATION]//\//}, ${PERIODS}x${OPT[INTERVAL]} ${TFRAME}  -->" >>$OUTPUTtable
    for(( I=0; I < ${OPT[SERIES_CNT]:-1} ;I++))
    do
        if [ -z "${OPT[MIN_$I]}" ] ; then continue ; fi
        echo "<!-- $(POL2name ${OPT[THIS_POL_$I]}): min:${OPT[MIN_$I]}, avg:${OPT[AVG_$I]}, max:${OPT[MAX_$I]} -->" >>$OUTPUTtable
    done

    if (( ${#AQIs[@]} > 1 ))
    then
        local TABLEblock=block ; if (( $AQInr > 0 )) ; then TABLEblock=none ; fi
        cat >>$OUTPUTtable <<EOF
<div class="${AQIs[$AQInr]}table" id="${AQIs[$AQInr]}table" style="display: ${TABLEblock}">
EOF
    fi

local UPDATEmsg=''
    # table caption
    cat >>$OUTPUTtable <<EOF
<table style='color:black;background:#f9f9f9;border-radius:7px;-moz-border-radius:7px;-webkit-border-radius:7px;box-shadow: 0px 7px 10px 0px #a0a0a0;text-align:left;padding:0px;padding-top:3px;padding-bottom:0.3%;margin:0px;border-spacing:0px;border:0px solid black;width:100%;'>
<caption valign=top align=center><span style='color:#0376ab'><a href="${URL[${OPT[TYPE]}]}" title="meer gegevens over de toegepaste air quality index">luchtkwaliteits Index ${OPT[TYPE]}</a> tabel
EOF
    if [ -n "${OPT[RANGE]}" ]
    then
        echo 'met daggemiddelden' >>$OUTPUTtable
    else
        echo 'met uurwaarden' >>$OUTPUTtable
    fi
    local ENDstrg=$($MYSQL -e "SELECT UNIX_TIMESTAMP(id) FROM ${OPT[TBL]}_aqi
        WHERE UNIX_TIMESTAMP(datum) < ${OPT[END]}+60*60 order by datum DESC LIMIT 1")
    ENDstrg=$(date --date=@${ENDstrg} "+%a %e %b %H:%M uur")
    cat >>$OUTPUTtable <<EOF
voor ${OPT[MUNICIPALITY]//\//}</span><br /><span valign=bottom style='font-size:85%;color:#2e3b4e;text-align:right'>Gebaseerd op data van <a href="${URL[${OPT[ORGANISATION]}]}" title="Bezoek website met actuele metingen voor het meetstation ${OPT[LOCATION]//\//}">${OPT[ORGANISATION]}</a> tot ${ENDstrg}</span>
</caption>
EOF
    # end of caption
    ENDstrg=$(date --date=@${OPT[END]} "+%a %e %b om %H:00 uur")
    # current aqi value message (optional)
    if (( ${OPT[END]} >= $(date --date=yesterday +%s) ))
    then
        if (( ${OPT[END]} >= $(date --date='6 hours ago' +%s) ))
        then
            if [ -z "${OPT[RANGE]}" ] ; then
            # last day / hour results
            cat >>$OUTPUTtable <<EOF
<tbody><tr>
<td style='padding-top:2%;padding-right:0.1%;'><span style="font-size:500%;font-weight:bold;background-clip:padding-box;border-radius:15px;-moz-border-radius:15px;-webkit-border-radius:15px;border:10px;text-shadow: 3px 2px 2px #a0a0a0;box-shadow: 0px 7px 10px 0px #a0a0a0;padding-left:20%;padding-right:20%;text-align:center;background-color: ${OPT[LASTcol_0]//\'/};color:$(COL2BCKGRND "${OPT[LASTcol_0]//\'/}"); "title="${OPT[TYPE]} index: ${OPT[LASTmsg_0]^[a-z]}">${OPT[LAST_0]/.*/}</span></td>
<td style='padding-left:10%;padding-top:2%;' colspan=4>actuele ${OPT[TYPE]} Index <span style="font-size:300%;font-weight:bold;text-shadow: 2px 1px 2px #a0a0a0;color:${OPT[LASTcol_0]//\'/}">${OPT[LASTmsg_0]^[a-z]}<br /></span><span val="${OPT[END]}">de laatste uurmeting was van ${ENDstrg}</span>${LASTtemp}</td>
</tr>
</tbody>
EOF
#<td colspan=2 style='vertical-align:top;text-align:right;padding-right:10px;padding-top:6px;font-size:60%'>bijgewerkt<br />$(date '+%a %e %b %R')</td>
#            UPDATEmsg=1
            fi
#         else
#             cat >>$OUTPUTtable <<EOF
# <tbody><tr>
# <td style='padding-top:2%;padding-right:0.1%;'><span style="font-size:500%;font-weight:bold;background-clip:padding-box;border-radius:15px;-moz-border-radius:15px;-webkit-border-radius:15px;border:10px;text-shadow: 3px 2px 2px #a0a0a0;box-shadow: 0px 7px 10px 0px #a0a0a0;padding-left:20%;padding-right:20%;text-align:center;background-color: #4a5744;color:white; "title="${OPT[TYPE]} index: unknown">?</span></td>
# <td style='padding-left:10%;padding-top:2%;' colspan=4>actuele ${OPT[TYPE]} Index <span style="font-size:300%;font-weight:bold;text-shadow: 2px 1px 2px #a0a0a0;color:#4a5744">onbekend<br /></span><span val="${OPT[END]}">de laatste uurmeting was van ${ENDstrg}</span></td>
# </tr>
# </tbody>
# EOF
# #<td colspan=2 style='vertical-align:top;text-align:right;padding-right:10px;padding-top:6px;font-size:60%'>bijgewerkt<br />$(date '+%a %e %b %R')</td>
# #        UPDATEmsg=1
         fi
    fi
    # end of current aqi values
    # graph chart
    local LAATST="voorgaande dag"
    if [ -n "${TFRAME/*ur*/}"  ] ; then LAATST="laatste ${INTERVAL} ${TFRAME}" ; fi
    if (( $DEBUG > 0 )) || (($OUT == 0)) ; then
        OPT[WIDTH]='100%'
    fi
    if [ -z "${OPT[HEIGHT]/*px/}" ] && [ $CHART = highstock ]
    then
        OPT[HEIGHT]="$((${OPT[HEIGHT]/px/}*3/2))px"
    fi
    cat >>$OUTPUTtable <<EOF
<tbody>
<tr style=' background-color:#eeeaee;'>
<td style='padding-left:1%;padding-top:0.5%;text-align:left'>${OPT[TYPE]} Index</td>
<td style='font-weight:bold;text-align:center'><a href="/${OPT[ALIAS]}">lokatie ${OPT[LOCATION]//\/} ${OPT[MUNICIPALITY]//\//}</a></td>
<td colspan=3 style='padding-left:0.1%;font-size:80%;padding-top:0.5%;text-align:center'>min/gem./max<br />${LAATST}</td>
</tr>
<tr style=' background-color:#eeeaee;'>
<td style='font-size:80%;text-align:center'>$(POL2name HTML ${OPT[POLS]})</td>
<td style='font-size:80%;padding-left:0.5%;padding-top:0.3%;text-align:left'>Index over de totale periode van ${PERIODS} x ${INTERVAL} $TFRAME<br />minimaal ${OPT[MIN]}, gemiddelde ${OPT[AVG]}, maximum ${OPT[MAX]}</td>
<td style='font-size:80%;max-width:30px'>min<br />${OPT[MIN_0]}</td>
<td style='font-size:80%;max-width:30px;color:${OPT[AVGcol_0]}' title='t.o.v. vorige 24 uur is het index gemiddelde ${OPT[AVGmsg_0]}'>gem.<br />${OPT[AVG_0]}</td>
<td style='font-size:80%;max-width:30px'>max<br />${OPT[MAX_0]}</td>
</tr>
<tr>
<td style='padding:1%' colspan=5 ><div title="${OPT[LOCATION]//\//} ${OPT[TYPE]}  index is gebaseerd op metingen afkomstig van ${OPT[ORGANISATION]}. De meetwaarden zijn niet gevalideerd.
EOF
    if [ "${OPT[TYPE]^^}"  = AQI ] ; then
        echo "De gasemissie &mu;g/m&sup3; waarden zijn zonodig geconverteerd naar ppb (moleculaire dichtheid) waarden. Bij een onbekende temperatuur is in de berekening uitgegaan van 20 graden Celsius. Voor de AQI niveaux is gebruikgemaakt van de APE standaard." >>$OUTPUTtable
    fi
    cat >>$OUTPUTtable <<EOF
Het minimum/gemiddelde/maximum is berekend over de hele periode van ${OPT[INTERVAL]} $TFRAME">
<div id="${OPT[ID]}" style="width:${OPT[WIDTH]}; height:${OPT[HEIGHT]};margin:0 auto"></div>
</div></td>
</tr>
EOF
    if [ -z "$UPDATEmsg" ]
    then
        echo "<tr><td colspan=5 style='vertical-align:top;text-align:right;padding-right:10px;padding-bottom:6px;font-size:70%'>geactualiseerd op $(date '+%a %e %b %R')</td></tr>" >>$OUTPUTtable
    fi
    echo -e "</tbody>\n</table>\n" >>$OUTPUTtable
    if (( ${#AQIs[@]} > 1 ))
    then
        echo '</div>' >>$OUTPUTtable
    fi

    return 0
}

function AQI_min_max() {
    local AQI=${1:-LKI}
    if [ -n "$1" ] && echo "$1" | grep -q -E "^(AQI|AQHI|LKI|CAQI)"
    then
        shift
    fi
    local TBL=${1:-HadM}
    local THIS_DAY=${2:-$(date --date=yesterday "+%Y-%m-%d")}
    local LIMIT=4       # minimum of measurents in a day to be valid
    if  [ -z "${1/%201*/}" ] ; then THIS_DAY=$1 ; TBL=HadM ; fi
    declare -a DayHour=() POLs=()
    local -i I CNT=0 LAST_DAY FIRST_DAY
    local QRY=""  STRG INDX=0 MAX=0 MIN=999
    # get all possible relevant pollutants
    STRG=$(Get_pollutants "$TBL" | grep -P '(o3|pm_(10|25)|roet|no|co|so|nh)')
    POLs=($STRG)
    for(( I=0; I < ${#POLs[@]}; I++))
    do  
        if [ -n "$QRY" ] ; then QRY+=" or " ; fi
        QRY+="(not isnull(${POLs[$I]}) AND ${POLs[$I]}_valid)"
    done
    if [ -n "$THIS_DAY" ]
    then
        LAST_DAY=$($MYSQL -e "SELECT TO_DAYS('${THIS_DAY//\//-} 02:00:00')")
        if [ -z "$LAST_DAY" ] || [ "$LAST_DAY" = NULL ]
        then
            echo "ERROR: ${AQI} index: date wrong format date $THIS_DAY" 1>&2
            return 1
        fi
        CNT=$($MYSQL -e "SELECT count(datum) FROM $TBL WHERE ($QRY) AND TO_DAYS(datum) = $LAST_DAY")
        # do we have enough measurements for this day?
        if (( $CNT <= $LIMIT )) ; then return 1 ; fi
    else
        LAST_DAY=$($MYSQL -e "SELECT TO_DAYS(datum) FROM $TBL ORDER BY datum DESC LIMIT 1")
        FIRST_DAY=$($MYSQL -e "SELECT TO_DAYS(datum) FROM $TBL LIMIT 1")
        for (( ; FIRST_DAY <= LAST_DAY ; LAST_DAY-- ))
        do
            CNT=$($MYSQL  -e "SELECT count(datum) FROM $TBL WHERE ($QRY) AND TO_DAYS(datum) = $LAST_DAY")
            if (( $CNT > $LIMIT )) ; then break ; fi
        done 
        if (( FIRST_DAY > LAST_DAY ))
        then
            echo "ERROR: ${AQI} index; cannot find a day with measurements." 1>&2
            return 1
        fi
    fi
    QRY=${POLs[*]}
    QRY=$(echo $QRY | sed -e 's/[^a-z0-9_]/ /g' -e 's/   */ /g' -e "s/\\([a-z0-9][a-z0-9_]*\\)/'\\1',\\1/g")
    QRY=$(\
        $MYSQL -e "SELECT ${QRY// /,} FROM $TBL WHERE TO_DAYS(datum) = $LAST_DAY" |\
        sed -e 's/NULL/0/g' -e 's/\t/ /g' -e 's/  */@/g'\
        )
    DayHour=($QRY)
    local MAXindex=-1 MINindex=-1 AVGindex AVG
    CNT=0
    for ((I=0; I < ${#DayHour[@]}; I++))
    do
        DayHour[$I]="${DayHour[$I]//@/ }"       # set spaces back again
        INDX=$(INDEX ${AQI} aqi ${DayHour[$I]})
        if ! perl -e "exit 1 if '${INDX:-0}' <= 0.01"
        then
            DayHour[$I]=""
            continue
        fi
        ((CNT++))
        if perl -e "exit 1 if '${INDX:-0}' <= '${MAX:-0.05}'"
        then MAX=$INDX ; MAXindex=$I
        fi
        if perl -e "exit 1 if '${INDX:-0}' >= '${MIN:-0}'"
        then MIN=$INDX ; MINindex=$I
        fi
    done

    QRY=${POLs[*]}
    QRY=$(echo $QRY | sed -e 's/[^a-z0-9_]/ /g' -e 's/   */ /g' -e "s/\\([a-z0-9][a-z0-9_]*\\)/'\\1',avg(\\1)/g")
    AVGindex=$(\
        $MYSQL -e "SELECT ${QRY// /,} FROM $TBL WHERE TO_DAYS(datum) = $LAST_DAY" |\
        sed -e 's/NULL/0/g' -e 's/\t/ /g' -e 's/  */ /g'\
        )
    AVG=$(INDEX ${AQI} aqi $AVGindex)
    if ! perl -e "exit 1 if '${AVG:-0}' >= 0.05"
    then
        echo "MMAvg${AQI}:$TBL=$AVG $AVGindex"
        if (( $MINindex >= 0 )) ; then echo "MMMin${AQI}:$TBL=$MIN ${DayHour[$MINindex]}" ; fi
        if (( $MAXindex >= 0 )) ; then echo "MMMax${AQI}:$TBL=$MAX ${DayHour[$MAXindex]}" ; fi
    fi
    if [ -z "$THIS_DAY" ]
    then
        THIS_DAY=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM $TBL WHERE TO_DAYS(datum) = $LAST_DAY LIMIT 1")
        THIS_DAY=$(date --date=@$THIS_DAY "+%a %-d %b %Y")
    else
        echo "MMDay${AQI}:$TBL=$THIS_DAY"
    fi
}

#AQI_min_max AQHI NL10131
#AQI_min_max LKI NL10131
#AQI_min_max AQI NL10131
#AQI_min_max CAQI NL10131
# arg0: font size (percentage, optional, dflt: 100%)
# arg0: type of index (dflt LKI)
# arg1: table name (dflt HadM)
# arg2: pollutants ("pm_10 no2") for the AQI calculation (dflt "all" available)
# arg3: nr of periods of 24 hours before end date/hour(dflt 2*24 hours)
# arg4: end date and hour (format see date cmd, dflt upto last one available)
# arg5: nr_periodsPnr_hours_interval Default 2 periods of 24 hourly measurements
#WIDTH="640px" HEIGHT=400px AQI_series '100%' LKI HadM all 2P24 "18 Sept 2016 8am"
# set defaults
UNIT=${UNIT:-hour}
case $UNIT in
day|dag)
    UNIT=$((3600*24))
    INTERVAL=${INTERVAL:-7}
    PERIODS=${PERIODS:-4}
;;
hour|uur|*)
    UNIT=3600
    INTERVAL=${INTERVAL:-24}
    PERIODS=${PERIODS:-2}
;;
esac
case x"$1" in
x[Cc]hart)
    if (( $VERBOSE > 0 ))
    then
        echo "Generating chart for table ${3:-HadM}, type ${2:-LKI}, periods ${PERIODS:-2}, interval ${INTERVAL:-24}, up to date ${4:-now}" 1>&2
    fi
    WIDTH=100% HEIGHT=200px AQI_HTML '100%' ${2:-LKI} ${3:-HadM} all ${5:-${PERIODS:-2}P${INTERVAL:-24}} "${4:now}"
;;
x)
    DEBUG=${DEBUG/0/1} WIDTH=540px  HEIGHT=200px AQI_HTML '100%' LKI HadM all ${PERIODS:-2}P${INTERVAL:-24} "18 Sept 2016 8am"
;;
xAQI|xaqi)
    AQI_min_max ${1:-LKI} ${2:-HadM}
;;
x-h|x--h*|xhelp)
    echo "
    The script has 2 functions: aqi (AQI avg/min/max) and chart generation.
    Usage:
        $0 aqi {LKI|AQI|all} [DBtable]  # AQI min/avg/max values printout
    or
        $0 chart {LKI|AQI|all} [DBtable] [end_date-hour] [periodsP#hours]
    Defaults: chart LKI HadM now 2P24
    Option 'all' will generate both charts: the LKI and AQI charts
    On option all the generated HTML tags has a button to switch 
    between LKI of AQI HTML table chart display.

    The script produces latest and current chart for a given period
    in JavaScript/HighChart format as HTML scripts.
    On STDOUT or when defined as env var FILE=path/filename
    where path/file is located in WWW directory.

    In debug modus (env DEBUG=1) will produce the output on a /var/tmp file.

    Environment variables to manage period types of generated charts:
        PERIODS=nr_of_periods ( dflt 2 24-hours or 4 7-days)
        INTERVAL=nr_of_hours/period (dflt: 24 hours or 7 days).
        UNIT={hour|day} interval in hours (dflt) or per day (with avg/stddev values).
    Chart zooming is enabled if (PERIODS * INTERVAL) > (3 * 24).
    So for larger amount of data the zoom chart will be used.
    If the aqi (AQI.pl) table is available this table will be used.

    Weather and Particular Matter PM2.5 local forecasts if enabled:
    Environ var FORECAST=DB_table[-LKI|AQI|all] (dflt: HadM-LKI) enables
    and defines the forecast. The bash script will define from this:
    FORECAST[DB_table]=Village_name is computed and the 48h weather/PM forecast chart
    will be inserted. E.g. FORECAST[HadM]=Grubbenvorst .
    FORECAST[DB_table,aqi]={LKI|AQI|all} defines the AQI forecast chart type (dflt LKI).
    See the Perl script (forecast.pl) for the supported locations.
    The Perl script forecast.pl will upload waether and PM forecasts and generates
    a forecast chart which can be used as table element e.g.
    <div id='FORECAST_AQItype' style='width: 100%; height: 310px; margin: 0 auto'>..</div>
    If FORECAST[DB_table]=Village is defined the HTML tags will be inserted as e.g.
    <div id='LKItable' class='LKItable' style='display: block|none'>
        <table ...><tr><td><div id='FORECAST_LKI'..>on load</div></td></tr></table>
    </div>.
    The id 'AQI_type'table is displayed ('block' or 'none') via the AQItype button.

    CLI example:
    DEBUG=1 DBPASS=${DBPASS:-acacadabra} DBUSER=${DBUSER:-$USER} DBHOST=${DBHOST:-localhost} DB=${DB:-luchtmetingen} VERBOSE=1 HOST=localhost UNIT=day PERIODS=52 INTERVAL=7 FORECAST=NETT-LKI ./Get_AQIs.sh chart all NETT now
    "
    exit 0
;;
esac
#WIDTH=310px HEIGHT=46px AQI_series '60%' AQI HadM all 2P24 "18 Sept 2016 8am"
