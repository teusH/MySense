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

# $Id: MySQL2CSV.sh,v 1.6 2020/10/25 12:23:28 teus Exp teus $
CMD='MySQL2CSV.sh $Revision: 1.6 $'

# export measurements data from MySQL database to a csv file
# use start and end time to limit amounts
# provide some meta info of the measurement kit
# DB credentials from environment: DBUSER=$USER, DBPASS=acacadabra, DBHOST=localhost, DB=luchtmetingen
# arguments: example START="3 days ago' END=now
ARGS=()
declare -i VALID=${VALID:-0} # show also validation value. Dflt: no
TMPDIR=/var/tmp
OUTPUTDIR=${OUTPUTDIR:-$(pwd)}
cd $TMPDIR
declare -a SORTED=(pm1 pm_1 pm25 pm_25  pm10 pm_10 pm03_cnt pm05_cnt pm1_cnt pm25_cnt pm4_cnt pm5_cnt pm10_cnt  temp rv rh luchtdruk pressure aqi gas)

FIELDS=${FIELDS:-pm1 pm25 pm10 temp rv luchtdruk} # default fields to export
ACTIVE=''                                         # denote active or not active of measurements
OUTPUT=KIT_DB_dump                                # name of output file
declare -i VERBOSE=${VERBOSE:-1}                  # 0 be quiet
HOUR=0         # calculate HOUR average of pollutant in CSV file
               # if 1 get average of measurements of a pollutant per HOUR
TIMEFORMAT=''  # extra time format besides UNIX timestamp
               # e.g. TIMEFORMAT='%Y, %M, %D %T' or TIMEFORMAT='%y/%m/%dT%H:%i:%s'§
SEP='\t'       # CSV field separator, dflt TAB
declare -i TIMESHIFT=0                            # time shift in minutes for official stations
                                                  # to do: must be made more flexible

function HELP(){
    cat 1>&2 <<EOF
This script will dump measurement data from a MySQL database in a zip file, every table is one file..
Database credentials are obtained from environment vairiables:
    DBUSER (dflt $USER), DBPASS (dflt: acacadabra),
    DBHOST (dflt: localhost) and database DB (dlft: luchtmetingen).
Arguments can be a an option: XYX=option eg:
  START='1 day ago' start of period.
  END='now' end of period.
  FORMAT='csv' define format of dump: csv or ql ('csv sql' will do both formats).
  ACTIVE=0 if 1 dump only operation/active measurement kits.
  VALID=0 if 1 dump also valid column for a value, only for CSV file format.
  OUTPUT=$OUTPUT file name redefine a name of zip output.
  VERBOSE=0 verbosity what dump is doing.
  FIELDS='pm1 rv temp ...' Default: '', all pollutants in database for the kit(s).
              only for CSV file outout format
    some pollutant names are:
        pm1, pm25, pm10, pm05_cnt, pm1_cnt, pm5_cnt, pm25_cnt, pm10_cnt, grain,
        rv, temp, luchtdruk, gas, aqi, o3, no2, nh3, co2, ...
    only available pollutants will be exported.
  SORTED='${SORTED[@]}' sort CSV fiels follwing this template.
  HOUR_AVERAGE=$HOUR if 1 calculate average value per hour (only for CSV outout).
  TIMEFORMAT='' extra time format besides UNIX timestamp, default SQL std format local time
              e.g. TIMEFORMAT='%y/%m/%d %T' or TIMEFORMAT='%y/%m/%dT%H:%i:%s'§
              only for CSV file format.
  SEP='\t'      CSV separator, e.g. ';'. Default tab.
  TIMESHIFT=0 timeshift in minutes for an offical station measurements
Arguments are taken as full measurement node table name (project_serial or official table name) or as
    wildcard: eg SAN_ will dump all tables of project SAN,
    available projects: HadM, SAN, RIVM, KIP, ...
    5ab96 will search for measurement kits with label ending 5ab96 measurement kits,
    123456abf will search for kit with serial 123456abf.
 or as label (may be a wildcard): eg hadm-75e4 or bwlvc-7113 or 'bwlvc-' all with bwlvc label
    label patterns ending on space or - char will also search for data of not active kits.
Meta info may differ from MySense DB tables or national station DB tables.
This is recognized from table name formats.
EOF
}

while [ -n "$1" ]
do # allow arguments with START='one month a ago" etc
  case "$1" in
    START=*) START="${1/*=/}"
    ;;
    END=*) END="${1/*=/}"
    ;;
    # define FIELDS='' if all available sensors in database is needed
    FIELDS=*) FIELDS="${1/*=/}"
    ;;
    VALID=*) VALID="${1/*=/}"
    ;;
    SORTED=*)
        SORTED="${1/*=/}"
    ;;
    ACTIVE=*) 
        if [ -n "${1/ACTIVE=0*/}" ] ; then ACTIVE=" AND active" ; fi
    ;;
    FORMAT=*)
        FORMAT="${1/*=/}"
    ;;
    OUTPUT=*)
        OUTPUT="${1/*=/}"
    ;;
    VERBOSE=*)
        VERBOSE="${1/*=/}"
    ;;
    HOUR_AVERAGE=*|HOUR=*|AVERAGE=*|AVG=*)
        HOUR="${1/*=/}"
    ;;
    TIMEFORMAT=*|TIME=*|DATE=*)
        TIMEFORMAT="${1/*=/}"
    ;;
    SEP=*)
        SEP="${1/*=/}"
    ;;
    TIMESHIFT=[-0-9]*)
        TIMESHIFT=${1/*=/}
    ;;
    -h*|help)
        HELP
        exit 0
    ;;
    *) ARGS+=("$1")
    ;;
  esac
  shift
done
if (( $HOUR == 1 ))
then # avg on group in 1 HOUR interval so use middle time
    TIMEFORMAT=$(echo "$TIMEFORMAT" | sed -e 's/:%i:%s/:30:00/' -e 's/:%i/:30/')
fi

DAYS=3
if [ -n "$START" ] && date --date="$START" >/dev/null
then
    START=$(date --date="$START" '+%Y/%m/%d %H:%M')
elif [ -z "$START" ]
then
    START=$(date --date="$(($DAYS + 1)) days ago" '+%Y/%m/%d %H:%M') # only last 4 days ago from now
else
    echo "Date start definition error" ; exit 1
fi
if [ -n "$END" ] && date --date="$END" >/dev/null
then
    END=$(date --date="$END" '+%Y/%m/%d %H:%M')
elif [ -z "$END" ]
then
    END="$(date --date='1 day ago' '+%Y/%m/%d %H:%M')" # up to 1 day ago from now
else
    echo "Date end definition error" ; exit 1
fi
OUTPUT=${OUTPUTDIR}/${OUTPUT}_$(date --date="$START" '+%Y-%m-%d-%H%M')_$(date --date="$END" '+%Y-%m-%d-%H%M')

# MySQL credentials
if [ ! -f ~/.my.cnf ]
then
    MYSQL="mysql -u ${DBUSER:-$USER} -p${DBPASS:-acacadabra} -h ${DBHOST:-localhost} -N -B --silent ${DB:-luchtmetingen}"
else
    # needs ~/.my.cnf
    MYSQL="mysql --login-path=${DB:-luchtmetingen} -h ${DBHOST:-localhost} -N -B --silent ${DB:-luchtmetingen}"
fi
if (( $VERBOSE > 0 ))
then
    echo "Export measurement data from MySQL database: ${DBUSER:-$USER} @ ${DBHOST:-localhost}, DB ${DB:-luchtmetingen} period $START up to $END" 1>&2
fi

if [ -z "${ARGS[0]}" ]  # do all if no kits are defined
then # no argument do all kits
   ARGS=($($MYSQL -e "SELECT DISTINCT serial FROM TTNtable WHERE luftdaten") )
fi
if [ -z "${ARGS[0]}" ]
then
    echo "Nothing to do. Exiting." 2>&1
    exit 0
fi

# list of tables and luftdaten external ID's
declare -A Serial2LuftID
Serial2LuftID[RIVM_807D3A9369F4]='#23873'       # SPS30 Vredepeel
Serial2LuftID[RIVM_30aea4ec7cf8]='#23872'       # PMSx003 Vredepeel
Serial2LuftID[RIVM_30aea4505888]='#23874'       # SDS011 Vredepeel
Serial2LuftID[HadM_e101e82a2c]='#16921'         # PMSx003 Bisweide
Serial2LuftID[SAN_30aea4509eb4]='#33671'        # SPS30 Rijkevoort
Serial2LuftID[SAN_30aea4ec8998]='#33315'        # SPS30 Boompjesweg
Serial2LuftID[SAN_30aea4509eb4]='#33343'        # SPS30 Klaproosstr
Serial2LuftID[SAN_807d3a9376dc]='#33080'        # PMS5003 Koningslinde
Serial2LuftID[SAN_807d3a935cb8]='#33341'        # SPS30 Mullemsedijk
Serial2LuftID[SAN_b4e62df55731]='#33670'        # SPS30 Beekstraat
Serial2LuftID[SAN_3c71bf876dbc]='#35554'        # Ledeackersestr
Serial2LuftID[SAN_807d3a937140]='#35096'        # SPS30 Lamperen
Serial2LuftID[SAN_30aea4ec8a24]='#35585'        # SPS30 den Akker
Serial2LuftID[SAN_b4e62df55729]='#35374'        # SPS30 Kerkstraat
Serial2LuftID[SAN_b4e62df5571d]='#36229'        # SPS30 Schapendreef
Serial2LuftID[SAN_b4e62df49ca5]='#37935'        # PMSx003 Willem Alexanderlaan, LF ID b4e62fd49ca5

# collect meta data of the measurement kit from MySQL
function GetIdentityInfo() {
    declare -i CNT
    # active sending data to LoRa?
    CNT=$($MYSQL -e "SELECT COUNT(serial) FROM TTNtable WHERE project = '${1:-X}' AND serial = '${2:-Y}' $ACTIVE")
    if (( $CNT > 0 )) # obtain meta info
    then
        $MYSQL -e "SELECT Sensors.project,Sensors.serial,Sensors.coordinates,REPLACE(Sensors.street,' ','_'),if(isnull(Sensors.village),'unknown',REPLACE(village,' ','_')),if(isnull(Sensors.pcode),'unknown',REPLACE(pcode,' ','_')),if(TTNtable.luftdaten > 0,'Luftdaten,AirTube,RIVM','none'), REPLACE(Sensors.description,' ','_'),'unknown' FROM Sensors, TTNtable WHERE Sensors.project = '${1:-X}' AND Sensors.serial = '${2:-Y}' AND Sensors.active AND TTNtable.serial = '${2:-X}' AND TTNtable.project = '${1:-X}' ORDER BY Sensors.datum DESC LIMIT 1"
        return 0
    else
        return 1
    fi
}

# collect meta data of measurements of governmental station from MySQL
# INFO=(0:project,1:serial,2:GPS,3:street,4:village,5:postcode,6:luftdatenID,7:sensors,8:publicID)
function GetStationInfo() {
    local CNT SENSORS=''
    CNT=$($MYSQL -e "SELECT COUNT(stations.table) FROM stations WHERE stations.table = '${1:-X}'")
    if (( $CNT > 0 )) # obtain meta info
    then
        SENSORS=$($MYSQL -e "DESCRIBE ${1:-X}" | grep _valid | grep -v lki | sed 's/_valid.*//' )
        # delete sensors which are not active in this period
        local ONE SQL=''
        for ONE in $SENSORS
        do
            SQL+="SELECT CONCAT('$ONE=',COUNT($ONE)) FROM ${1:-X} WHERE NOT ISNULL($ONE) AND datum >= '$START';"
        done
        SENSORS=$($MYSQL -e "$SQL" | sed -e 's/[a-z0-9][a-z0-9]*=0//' -e 's/=[1-9][0-9]*//')
        SENSORS=$(echo $SENSORS | sed -e 's/pm_/pm/g' -e 's/pm25/PM2.5/' -e 's/ /,/g' | tr a-z A-Z | sed 's/PM01/roet/' )
        $MYSQL -e "SELECT stations.table,CONCAT(stations.organisation,':',stations.id),if(isnull(stations.geolocation),'_',REPLACE(stations.geolocation,' ',',')),if(isnull(stations.name),'_',REPLACE(stations.name,' ','_')),if(isnull(stations.municipality),'_',REPLACE(stations.municipality,' ',',')),'_','no','$SENSORS','_' FROM stations WHERE stations.table = '${1:-X}' LIMIT 1"
        return 0
    else
        return 1
    fi
}

# sort CSV fields in a dedicated order
function MySORT() {
    declare -a MyORDER=()
    declare -i M=${#SORTED[@]} I=0
    local ONE
    for ONE in $@
    do
        for (( I=0; I < ${#SORTED[@]}; I++ ))
        do
            if [ ${SORTED[$I]} = "$ONE" ] ; then break ; fi
        done
        if (( $I == ${#SORTED[@]} ))
        then
            MyORDER[$M]="$ONE"
            M+=1
        else
            MyORDER[$I]="$ONE"
        fi
    done
    echo ${MyORDER[@]}
    return 0
}

# get all sensor configured in the table
function GetSensors() {
    local TBL=$1
    $MYSQL -e "DESCRIBE $TBL" | grep _valid | sed 's/_valid.*//'
}

EXPORTED=()
# export for a kit with serial $1 (match on last digits) measurements in a period START/END to CSV file
# translate fields/column names to header names
declare -A FLDnames
FLDnames[pm25]=PM2.5
FLDnames[pm25_cnt]='#PM2.5'
FLDnames[pm_25]=PM2.5
FLDnames[pm10]=PM10
FLDnames[pm10_cnt]='#PM10'
FLDnames[pm_10]=PM10
FLDnames[temp]=temp
FLDnames[rv]=RH
FLDnames[luchtdruk]=pressure
FLDnames[pm1]=PM1
FLDnames[pm1_cnt]=PM1
FLDnames[pm03]=PM0.3
FLDnames[pm03_cnt]='#PM0.3'
FLDnames[pm05]=PM0.5
FLDnames[pm05_cnt]='#PM0.5'
FLDnames[pm4]=PM4
FLDnames[pm4_cnt]='#PM4'
FLDnames[pm5]=PM5
FLDnames[pm5_cnt]='#PM5'

function MySQLdump2SQL(){
    local ONE="$1"
    if ! mysqldump -u ${DBUSER:-$USER} -p"${DBPASS:-acacadabra}" -h ${DBHOST:-localhost} --where="datum >= '$START' AND datum <= '$END'" ${DB:-luchtmetingen} "$ONE" 2>/dev/null
    then
        echo "Failed to execute msqldump for $ONE" 1>&2
        return 1
    fi
    if (( $VERBOSE > 0 )) ; then
        echo "Collected measurements for kit: $ONE into SQL format." 1>&2
    fi
    return 0
}

function MySQLdump2CSV() {
    local ONE="$1" CNT
    declare -A FLDS=()
    local AVG=''  # output as average per hour
    declare -i TSHIFT=${3:-0}
    TSHIFT=$((60*$TSHIFT)) # in seconds
    if (( "${2:-0}" > 0 ))
    then
        AVG="GROUP BY YEAR(datum + INTERVAL $TSHIFT SECOND), MONTH(datum + INTERVAL $TSHIFT SECOND), DAY(datum + INTERVAL $TSHIFT SECOND), HOUR(datum + INTERVAL $TSHIFT SECOND)"
    fi
    if (( $TSHIFT != 0 ))
    then
        echo "# Timestamp is shifted for $(($TSHIFT/60)) minutes."
    fi
    echo -n -e "\"timestamp\"$SEP\"datum\""
    declare -A COLS=()
    for CNT in $(GetSensors "$ONE")
    do
        if [ -n "$FIELDS" ]
        then
            if ! echo "$FIELDS" | sed -e 's/pm10/pm10 pm_10/' -e 's/pm25/pm25 pm_25/' | grep -q -P "(^$CNT|\s$CNT)(\s|$)"
            then
                continue
            fi
        fi
        COLS[$CNT]=$($MYSQL -e "SELECT COUNT($CNT) FROM $ONE WHERE NOT ISNULL($CNT) AND datum + INTERVAL $TSHIFT SECOND >= '$START' AND datum + INTERVAL $TSHIFT SECOND <= '$END'")
    done
    for CNT in $(MySORT ${!COLS[@]} )
    do
        if (( ${COLS[$CNT]:-0} <= 0 )) ; then continue ; fi
        # to do: check field is a database table column
        echo -e -n "$SEP\"${FLDnames[$CNT]}\""
        if [ -z "$AVG" ] && (( $VALID > 0 ))
        then
            echo -e -n "$SEP\"OK\""
        fi
    done
    echo
    S='"'
    local PRT
    if [ -z "$TIMEFORMAT" ]
    then
        PRT="CONCAT(UNIX_TIMESTAMP(datum) + $TSHIFT,'@$S',datum + INTERVAL $TSHIFT SECOND,'$S'"
    else
        PRT="CONCAT(UNIX_TIMESTAMP(datum) + $TSHIFT,'@$S',DATE_FORMAT(datum + INTERVAL $TSHIFT SECOND,'$TIMEFORMAT'),'$S'"
    fi
    # sql concat() fails on NULL values!
    for CNT in $(MySORT ${!COLS[@]} )
    do
        if (( ${COLS[$CNT]:-0} <= 0 )) ; then continue ; fi
        if [ -z "$AVG" ]
        then
            PRT+=",'@',IF(ISNULL($CNT),'',ROUND($CNT,2))"
            if (( $VALID > 0 ))
            then
                PRT+=",'@',IF(ISNULL(${CNT}_valid),'',${CNT}_valid)"
            fi
        else
            PRT+=",'@',IF(ISNULL(AVG($CNT)),'',ROUND(AVG($CNT),2))"
        fi
    done
    PRT+=')'
    if ! $MYSQL -e "SELECT $PRT FROM $ONE WHERE datum + INTERVAL $TSHIFT SECOND >= '$START' AND datum + INTERVAL $TSHIFT SECOND <= '$END' $AVG"  | grep -v '^NULL$' | tr @ "$SEP"
    then
        echo "Failed to dump $ONE in CSV format." 1>&2
        return 1
    fi
    if (( $VERBOSE > 0 )) ; then
        echo "Collected measurements for kit $ONE with timeshift of $(($TSHIFT/60)) minutes into CSV format." 1>&2
    fi
    return 0
}

# export measurements to zip file
function ExportData() {
    declare -a INFO
    local ONE CNT KITS
    declare -A FLDS
    declare -i TSHIFT=0
    if [ -z "$1" ] ; then return ; fi
    if echo "$1" |  grep -q -P '^(HadM|G[AV]|M(A2|HF|KH)|NETT|NL101[03][13678])$' # governmental station
    then # table name of official measurement station <ID>[<number>]
        KITS="$1"
        TSHIFT=${TIMESHIFT:-0}
    elif echo "$1" | grep -q -P '(^[a-z]{3,6}[- ]$)'
    then # Sensor label cases
        KITS=$($MYSQL -e "SELECT concat(project,'_',serial) FROM Sensors WHERE label like '$1%'" | sort | uniq)
    elif echo "$1" | grep -q -P '(^[a-z]{3,6}[-_]|[-_][A-Fa-f0-9]{4}$)'
    then # DB table name or label xyz-abcd cases: single MySense kit with table name <project>_<serial>
        KITS=$($MYSQL -e "SELECT concat(project,'_',serial) FROM Sensors WHERE label like '%$1%' $ACTIVE" | sort | uniq)
    elif echo "$1" | grep -q -P '^[A-Za-z]+_$'  # project
    then # all kits of a project: <project>_
        KITS=$($MYSQL -e "SELECT concat(project,'_',serial) FROM Sensors WHERE project = '${1/_/}' $ACTIVE" | sort | uniq)
    elif echo "$1" | grep -q -P '^[a-fA-F0-9]{4,}$'
    then # measurement kis with serial ending with some hex chars <last serial chars>
        KITS=$($MYSQL -e "SELECT concat(project,'_',serial) FROM Sensors WHERE serial like '%$1' $ACTIVE" | sort | uniq)
    else
        echo "Kit pattern \"$1\" not recognized. Use serial pattern or label" ; return 1
    fi
    for ONE in $KITS
    do
        # to do: add RIVM station tables
        if echo "$ONE" | grep -q -P '[A-Za-z]+_[a-fA-F0-9]{6,}'
        then
            INFO=($(GetIdentityInfo ${ONE/_*/} ${ONE/*_/}))
            if [ $? -gt 0 ]
            then
                echo "$ONE not known. Skipped" 1>&2
                continue
            fi
        else
            INFO=($(GetStationInfo $ONE))
            if [ $? -gt 0 ]
            then
                echo "$ONE not known. Skipped" 1>&2
                continue
            fi
            # fields sed 's/pm\([0-9]\)/pm_\1/g'
        fi
        CNT=$($MYSQL -e "SELECT COUNT(datum) FROM $ONE WHERE datum + INTERVAL $TSHIFT SECOND >= '$START' AND datum + INTERVAL $TSHIFT SECOND <= '$END'")
        if (( ${CNT:-0} < 10 )) # less as 10 in this period skip this kit
        then
            if (( $VERBOSE > 0 )) ; then
                echo "SKIP $ONE: not enough measurements forwarded in this period from $START to $END" 1>&2
            fi
            continue
        fi
        # INFO=(0:project,1:serial,2:GPS,3:street,4:village,5:postcode,6:luftdatenID,7:sensors,8:publicID)
        # delete house nr, spaces back again
        INFO[3]=$(echo "${INFO[3]}" | sed -e 's/_/ /g' -e 's/ [0-9][0-9]*[aAbB]*$//' -e 's/NULL/unknown/')
        INFO[4]=$(echo "${INFO[4]}" | sed 's/_/ /g') # village
        INFO[5]=$(echo "${INFO[5]}" | sed 's/_//g')  # postcode
        if [ -n "${Serial2LuftID[${ONE}]}" ]
        then
            INFO[6]=${INFO[6]/Luftdaten/Luftdaten(${Serial2LuftID[$ONE]})}
        fi
        INFO[7]=$(echo "${INFO[7]}" | sed -e 's/^/#/' -e 's/.*;hw:__*//' -e 's/,*TIME//' -e 's/$/,adapter/' -e 's/\(PMS.003\)/Plantower(\1)/' -e 's/\(SPS30\)/Sensirion(\1)/' -e 's/\(SDS011\)/Nova(\1)/' -e 's/\(BME.80\)/Bosch(\1)/' -e 's/\(SHT..\)/Sensirion(\1)/' -e 's/\(DHT..\)/Adafruit(\1)/' -e 's/NEO-*6*/GPS(NEO-6)/' -e 's/ENERGIE/SOLAR/i' -e '/SOLAR/s/,*adapter//'  -e 's/#.*/unknown/' -e 's/_//')
        if (( $VERBOSE > 1 )) ; then
            echo "Project:${INFO[0]} Serial:${INFO[1]}; Sensors:${INFO[7]}; Location:${INFO[3]},${INFO[4]},${INFO[5]},GPS(${INFO[2]}); Forwarding:${INFO[6]}; Period:$START up to $END" 1>&2
        fi

        local FRMT
        for  FRMT in ${FORMAT:-csv}
        do
            # header meta information
            echo "# Generated via $CMD. Date: $(date '+%Y/%m/%d %H:%M')." >"$ONE".$FRMT
            echo "# Measurements data dump DB ${DB:-luchtmetingen}, project:${INFO[0]}, kit serial:${INFO[1]}." >>"$ONE".$FRNT
            echo "# Sensors:${INFO[7]}; Data forwarding:${INFO[6]}" >>"$ONE".$FRNT
            echo "# Location:${INFO[3]},${INFO[4]},${INFO[5]},GPS(${INFO[2]})" >>"$ONE".$FRMT

            case $FRMT in
            csv)
                if (( ${HOUR:-0} > 0 ))
                then
                    echo "# Average per hour. Period:$START up to $END" >>"$ONE".$FRMT
                else
                    echo "# Period:$START up to $END" >>"$ONE".$FRMT
                fi
                if ! MySQLdump2CSV "$ONE" "${HOUR:-0}" "${TSHIFT:-0}"  >>"$ONE".$FRMT
                then
                    rm -f "$ONE.$FRMT"
                    echo "FAILURE in generating CSV file for $ONE. Skipped." 1>&2
                    return 1
                fi
                zip -uq "$OUTPUT.zip" "$ONE.$FRMT"
                rm -f "$ONE.$FRMT"
            ;;
            sql)
                if ! MySQLdump2SQL "$ONE" >>"$ONE".$FRMT
                then
                    rm -f "$ONE.$FRMT"
                    echo "FAILURE in generating SQL dump for $ONE. Skipped." 1>&2
                    return 1
                fi
                zip -uq "$OUTPUT.zip" "$ONE.$FRMT"
                rm -f "$ONE.$FRMT"
            ;;
            esac
        done
    done
    return $?
}

# export data for a measurement kit via eg last 4 Hex of MySense serial nr
for ARG in ${ARGS[@]}
do
   ExportData "$ARG"
done
if [ -f "$OUTPUT.zip" ]
then
    cat <<EOF | zip -z ${OUTPUT}.zip 2>/dev/null
Dump made by $CMD
MySQL DB dump from ${DB:-air quality} at server ${DBHOST:-localhost} period ${START} up to ${END}.
The ${DB:-air quality} data is open data under conditions of FSF GPLV3
(http://www.gnu.org/licenses/).
In short: no warranty, only for non-commercial use, any changes, contributions, reports remain Open Source.
EOF
    if (( $VERBOSE > 0 )) ; then
        echo "Zip ${FORMAT/ / and } measurements DB data files into archive $OUTPUT.zip" 1>&2  
    fi
elif (( $VERBOSE > 0 )) ; then
    echo "No $FORMAT files to be exported." 1>&2
fi
