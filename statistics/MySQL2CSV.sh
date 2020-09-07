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

# $Id: MySQL2CSV.sh,v 1.3 2020/09/07 12:59:47 teus Exp teus $

# export measurements data from MySQL database to a csv file
# use start and end time to limit amounts
# provide some meta info of the measurement kit
# DB credentials from environment: DBUSER=$USER, DBPASS=acacadabra, DBHOST=localhost, DB=luchtmetingen
# arguments: example START="3 days ago' END=now
ARGS=()
declare -i VALID=${VALID:-0} # show also validation value. Dflt: no
TMPDIR=/var/tmp

FIELDS=${FIELDS:-pm1 pm25 pm10 temp rv luchtdruk} # default fields to export
for ARG in $*
do # allow arguments with START='one month a ago" etc
  case "$ARG" in
    START=*) START="${ARG/*=/}"
    ;;
    END=*) END="${ARG/*=/}"
    ;;
    # define FIELDS='' if all available sensors in database is needed
    FIELDS=*) FIELDS="${ARG/*=/}"
    ;;
    VALID=*) VALID="${ARG/*=/}"
    ;;
    *) ARGS+=("$ARG")
    ;;
  esac
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
if [ -n "$END" ] && date --date=$END >/dev/null
then
    END=$(date --date="$END" '+%Y/%m/%d %H:%M')
elif [ -z "$END" ]
then
    END="$(date --date='1 day ago' '+%Y/%m/%d %H:%M')" # up to 1 day ago from now
else
    echo "Date end definition error" ; exit 1
fi

# MySQL credentials
if [ ! -f ~/.my.cnf ]
then
    MYSQL="mysql -u ${DBUSER:-$USER} -p${DBPASS:-acacadabra} -h ${DBHOST:-localhost} -N -B --silent ${DB:-luchtmetingen}"
else
    # needs ~/.my.cnf
    MYSQL="mysql --login-path=${DB:-luchtmetingen} -h ${DBHOST:-localhost} -N -B --silent ${DB:-luchtmetingen}"
fi
echo "Export measurement data from MySQL database: ${DBUSER:-$USER} @ ${DBHOST:-localhost}, DB ${DB:-luchtmetingen} period $START upto $END" 1>&2

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
    CNT=$($MYSQL -e "SELECT COUNT(serial) FROM TTNtable WHERE project = '${1:-X}' AND serial = '${2:-Y}' AND luftdaten AND active")
    if (( $CNT > 0 )) # obtain meta info
    then
        $MYSQL -e "SELECT Sensors.project,Sensors.serial,Sensors.coordinates,REPLACE(Sensors.street,' ','_'),if(isnull(Sensors.village),'onbekend',REPLACE(village,' ','_')),if(isnull(Sensors.pcode),'onbekend',REPLACE(pcode,' ','_')),if(isnull(TTNtable.luftdatenID),TTNtable.serial,TTNtable.luftdatenID), REPLACE(Sensors.description,' ','_'),'onbekend' FROM Sensors, TTNtable WHERE Sensors.project = '${1:-X}' AND Sensors.serial = '${2:-Y}' AND Sensors.active ORDER BY Sensors.datum DESC LIMIT 1"
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

function ExportData() {
    declare -a INFO
    local ONE CNT KITS
    declare -A FLDS
    if [ -z "$1" ] ; then return ; fi
    if echo "$1" | grep -q -P '(^[a-z]{3,6}[-_]|[-_][A-Fa-f0-9]{4}$)'
    then # label case
        KITS=$($MYSQL -e "SELECT concat(project,'_',serial) FROM Sensors WHERE label like '%$1%'" | sort | uniq)
    elif echo "$1" | grep -q -P '^[a-fA-F0-9]{4,}$'
    then
        KITS=$($MYSQL -e "SELECT concat(project,'_',serial) FROM TTNtable WHERE serial like '%$1'" | sort | uniq)
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
            echo "SKIP $ONE: not enough measurements forwarded in this period from $START to $END"
            continue
        fi
        # INFO=(0:project,1:serial,2:GPS,3:street,4:village,5:postcode,6:luftdatenID,7:sensors,8:publicID)
        # delete house nr, spaces back again
        INFO[3]=$(echo "${INFO[3]}" | sed -e 's/_/ /g' -e 's/ [0-9][0-9]*[aAbB]*$//' -e 's/NULL/onbekend/')
        INFO[4]=$(echo "${INFO[4]}" | sed 's/_/ /g') # village
        INFO[5]=$(echo "${INFO[5]}" | sed 's/_//g')  # postcode
        INFO[7]=$(echo "${INFO[7]}" | sed -e 's/^/#/' -e 's/.*;hw:__*//' -e 's/,*TIME//' -e 's/$/,adapter/' -e 's/\(PMS.003\)/Plantower(\1)/' -e 's/\(SPS30\)/Sensirion(\1)/' -e 's/\(SDS011\)/Nova(\1)/' -e 's/\(BME.80\)/Bosch(\1)/' -e 's/\(SHT..\)/Sensirion(\1)/' -e 's/\(DHT..\)/Adafruit(\1)/' -e 's/NEO-*6*/GPS(NEO-6)/' -e 's/ENERGIE/SOLAR/i' -e '/SOLAR/s/,*adapter//'  -e 's/#.*/onbekend/' -e 's/_//')
        if [ -n "${Serial2LuftID[$ONE]}" ]
        then
            INFO[8]=${Serial2LuftID[$ONE]}
        fi
        echo "Project:${INFO[0]} Serial:${INFO[1]}; Sensors:${INFO[7]}; Location:${INFO[3]},${INFO[4]},${INFO[5]},GPS(${INFO[2]}); Luftdaten:publicID(${INFO[8]}),internalID(TTN-${INFO[6]}); Period:$START upto $END" | tee $TMPDIR/$ONE.csv 1>&2
        echo -n -e "\"timestamp\"\t\"datum\"" >>$TMPDIR/$ONE.csv
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
            echo -e -n "\t\"${FLDnames[$CNT]}\"" >>$TMPDIR/$ONE.csv
            if (( $VALID > 0 ))
            then
                echo -e -n "\t\"OK\"" >>$TMPDIR/$ONE.csv
            fi
        done
        echo >>$TMPDIR/$ONE.csv
        S='"'
        local PRT="CONCAT(UNIX_TIMESTAMP(datum),'@$S',datum,'$S'"
        for CNT in ${!COLS[@]}
        do
            if (( ${COLS[$CNT]:-0} <= 0 )) ; then continue ; fi
            PRT+=",'@',$CNT"
            if (( $VALID > 0 ))
            then
                PRT+=",'@',${CNT}_valid"
            fi
        done
        PRT+=')'
        $MYSQL -e "SELECT $PRT FROM $ONE WHERE datum >= '$START' AND datum <= '$END'"  | grep -v '^NULL$' | tr @ \\t >>$TMPDIR/$ONE.csv
        echo "Collected measurements for kit: $ONE into $TMPDIR/$ONE.csv" 1>&2
        EXPORTED+=($ONE.csv)
   done
}

# export data for a measurement kit via eg last 4 Hex of MySense serial nr
for ARG in ${ARGS[@]}
do
   ExportData "$ARG"
done
if [ -n "${EXPORTED[0]}" ]
then
    WDIR=$(pwd)
    (cd $TMPDIR ; zip -u $WDIR/MySense_MySQL2CSVdump_$(date +%Y-%m-%dH%H).zip ${EXPORTED[@]} ; rm -f ${EXPORTED[@]})
    echo "Zip csv files into: MySense_MySQL2CSVdump_$(date +%Y-%m-%dH%H).zip" 1>&2  
else
    echo "No CSV files to be exported." 1>&2
fi
