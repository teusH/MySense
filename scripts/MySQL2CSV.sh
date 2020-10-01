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

# $Id: MySQL2CSV.sh,v 1.5 2020/09/11 13:24:52 teus Exp teus $
CMD='MySQL2CSV.sh $Revision: 1.5 $'

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

FIELDS=${FIELDS:-pm1 pm25 pm10 temp rv luchtdruk} # default fields to export
ACTIVE=''
OUTPUT=KIT_DB_dump
declare -i VERBOSE=1  # 0 is quiet

function HELP(){
    cat 1>&2 <<EOF
This script will dump measurement data from a MySQL database in a zip file, every table is one file..
Database acredentials are obtained from environment: DBUSER (dflt $USER), DBPASS (dflt: acacadabra), DBHOST (dflt: localhost) and database DB (dlft: luchtmetingen).
Arguments can be a an option: XYX=option:
eg
START='1 day ago' start of period
END=now end of period
FORMAT=csv define format of dump: csv or ql ('csv sql' will do both formats)
ACTIVE=0 if 1 dump only operation/active measurement kits
VALID= if 1 dump also valid column for a value
OUTPUT=$OUTPUT file name redefine a name of zip output.
VERBOSE=0 verbosity what dump is doing

Arguments are taken as full measurement node table name (project_serial) or as
wildcard: eg SAN_ will dump all tables of project SAN,
5ab96 will search for measurement kits with label ending 5ab96 measurement kits
123456abf will search for kit with serial 123456abf
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
    -h*|help)
        HELP
        exit 0
    ;;
    *) ARGS+=("$1")
    ;;
  esac
  shift
done

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
#Serial2LuftID[SAN_30aea4ec8998]='#33315'        # SPS30 Boompjesweg
Serial2LuftID[SAN_30aea4ec8998]='#50229'        # SPS30 Boompjesweg 30-09-2020
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

    echo -n -e "\"timestamp\"\t\"datum\""
    declare -A COLS=()
    for CNT in $(GetSensors "$ONE")
    do
        if [ -n "$FIELDS" ]
        then
            if ! echo "$FIELDS" | grep -q -P "(^$CNT|\s$CNT)(\s|$)"
            then
                continue
            fi
        fi
        COLS[$CNT]=$($MYSQL -e "SELECT COUNT($CNT) FROM $ONE WHERE NOT ISNULL($CNT) AND datum >= '$START' AND datum <= '$END'")
    done
    for CNT in ${!COLS[@]}
    do
        if (( ${COLS[$CNT]:-0} <= 0 )) ; then continue ; fi
        # to do: check field is a database table column
        echo -e -n "\t\"${FLDnames[$CNT]}\""
        if (( $VALID > 0 ))
        then
            echo -e -n "\t\"OK\""
        fi
    done
    echo
    S='"'
    local PRT="CONCAT(UNIX_TIMESTAMP(datum),'@$S',datum,'$S'"
    # sql concat() fails on NULL values!
    for CNT in ${!COLS[@]}
    do
        if (( ${COLS[$CNT]:-0} <= 0 )) ; then continue ; fi
        PRT+=",'@',IF(ISNULL($CNT),'',$CNT)"
        if (( $VALID > 0 ))
        then
            PRT+=",'@',IF(ISNULL(${CNT}_valid),'',${CNT}_valid)"
        fi
    done
    PRT+=')'
    if ! $MYSQL -e "SELECT $PRT FROM $ONE WHERE datum >= '$START' AND datum <= '$END'"  | grep -v '^NULL$' | tr @ \\t
    then
        echo "Failed to dump $ONE in CSVC format." 1>&2
        return 1
    fi
    if (( $VERBOSE > 0 )) ; then
        echo "Collected measurements for kit: $ONE into CSV format." 1>&2
    fi
    return 0
}

function ExportData() {
    declare -a INFO
    local ONE CNT KITS
    declare -A FLDS
    if [ -z "$1" ] ; then return ; fi
    if echo "$1" | grep -q -P '(^[a-z]{3,6}[-_]|[-_][A-Fa-f0-9]{4}$)'
    then # label case
        KITS=$($MYSQL -e "SELECT concat(project,'_',serial) FROM Sensors WHERE label like '%$1%' $ACTIVE" | sort | uniq)
    elif echo "$1" | grep -q -P '^[A-Za-z]+_$'  # project
    then
        KITS=$($MYSQL -e "SELECT concat(project,'_',serial) FROM Sensors WHERE project = '${1/_/}' $ACTIVE" | sort | uniq)
    elif echo "$1" | grep -q -P '^[a-fA-F0-9]{4,}$'
    then
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
        fi
        CNT=$($MYSQL -e "SELECT COUNT(datum) FROM $ONE WHERE datum >= '$START' AND datum <= '$END'")
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
            echo "# Data dump DB ${DB:-luchtmetingen} date: $(date '+%Y/%m/%d %H:%M') Project:${INFO[0]} Serial:${INFO[1]}; Sensors:${INFO[7]}; Location:${INFO[3]},${INFO[4]},${INFO[5]},GPS(${INFO[2]}); Data forwarding:${INFO[6]}; Period:$START up to $END" >"$ONE".$FRMT
            case $FRMT in
            csv)
                if ! MySQLdump2CSV "$ONE" >>"$ONE".$FRMT
                then
                    rm -f "$ONE.$FRMT"
                    return 1
                fi
                zip -uq "$OUTPUT.zip" "$ONE.$FRMT"
                rm -f "$ONE.$FRMT"
            ;;
            sql)
                if ! MySQLdump2SQL "$ONE" >>"$ONE".$FRMT
                then
                    rm -f "$ONE.$FRMT"
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
