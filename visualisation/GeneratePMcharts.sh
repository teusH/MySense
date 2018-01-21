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

# $Id: GeneratePMcharts.sh,v 1.3 2018/01/21 16:21:18 teus Exp teus $

# script to generate several charts for sensor kits of a project
# will notify by email non active sensor kits as well

# MySQL database credentials
# will use here mysql --login-path=luchtmetingen as well!
export DBUSER=${DBUSER:-$USER}
export DBHOST=${DBHOST:-localhost}
export DBPASS=${DBPASS:-acacadabra}
DB=luchtmetingen

WDIR=/webdata/luchtmetingen/    # working directory
#WDIR=.
RHOST=localhost                 # host where webfiles reside


PROJ=${PROJ:-VW2017}_   # use this as project identifier, may well be a perl reg exp
KITsns=''      # GetKits will assign values to array of sensor kits for charts
AVOID=${AVOID:-3d73279dd} # avoid this kit, may wel be a perl reg expression

STATIONS=${STATIONS:-NL10131 NETT} # add reference stations, HadM is always included 

GENERATOR=${WDIR}/ChartsPM.pl   # script to generate webpage with chart
DIR=/webdata/Drupal/cmsdata/BdP/files/luchtmetingen # webpage files reside here
MAILTO=teus@theunis.org         # email address to send inactive sensor kits notices

# how to approach MySQL database
MYSQL="mysql --login-path=$DB -h ${RHOST:-localhost} -N -B --silent $DB"

# default pollutants for chart webpage with overview of all sensor kits 
#POLs=pm25
POLs=pm10,pm25

# get all sensor kits of a project
function GetKits() {
    if ! $MYSQL -e 'SHOW TABLES' | grep -P "$1" | grep -P -v "$AVOID"
    then
        echo "Unable to find the sensor kits for project $1" >/dev/stderr
        exit 1
    fi
}

QRY=''
# pollutants to see if sensor kit is active
POLS='pm10 pm25 rv temp rssi'
# query generator to get stats of sensors for the TABLE (arg1)
function GenerateQRY() {
    local POL
    if [ -z "$QRY" ]
    then
        for  POL in $POLS
        do
            if [ -z "$QRY" ] ; then QRY="SELECT CONCAT('time=',UNIX_TIMESTAMP(now())" ; fi
            QRY+=",' ${POL}=',COUNT(${POL})"
        done
        QRY+=") FROM TBL WHERE datum > SUBTIME(NOW(), '1:00:00.000000')" # one hour
    fi
    echo "$QRY" | sed "s/TBL/${1}/g"
    return
}
# geberate QRY for last measurement
LQRY=''
function GenerateQRYlast() {
    local POL
    if [ -z "$LQRY" ]
    then
        for  POL in $POLS
        do
            if [ -z "$LQRY" ]
            then LQRY="SELECT UNIX_TIMESTAMP(datum) FROM TBL WHERE"
            else LQRY+=" AND"
            fi
            LQRY+=" not ISNULL($POL)"
        done
        LQRY+=" ORDER BY datum DESC LIMIT 1" # one hour
    fi
    echo "$LQRY" | sed "s/TBL/${1}/g"
    return
}

# next routine is deprecated
declare -i ACTIVETIME
ACTIVETIME=$((60*60))   # one hour
# send email if sensorkit is not seen active for a period of time (dflt one hour)
function OldCheckActive() {
    local TBL RTS=0
    declare -i CUR=$(date +%s) LAST MSG
    for TBL in $*
    do
        if [ -n "${TBL/VW2017*/}" ] ; then continue ; fi
        LAST=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM ${TBL}
            WHERE not ISNULL(pm10) AND not ISNULL(pm25) AND not ISNULL(rv) AND not ISNULL(temp)
             ORDER BY datum DESC LIMIT 1")
        if (( ( $CUR - $ACTIVETIME ) < $LAST ))
        then
            MSG=$($MYSQL -e "SELECT CONCAT('label: ',label, ', street: ',street, ',village: ',village) FROM Sensors WHERE serial = '${TBL/VW2017_/}' ORDER BY datum DESC LIMIT 1")
            echo "Last activity of all sensors on sensor kit $TBL was on: $(date --date=@$LAST).\nDetails: $MSG" | \
            if [ -n ${MAILTO} ]
            then
                mail --subject="Sensor kit $TBL needs attention"
            else
                cat
            fi
            RTS=1
        fi
    done
    return $RTS
}

# send email if sensorkit is not seen quite active for a period of time (dflt one hour)
# minimal 5 measurements per hour, no measurements in one hour special warning
function CheckActive() {
    local MSG='' NME POLSMSG='Last one hour had number of measurements for '
    declare -i MAX=-1 MIN=100 SECS=$(date +%s) RTS=0 LAST=0
    if [ -n "${1/*_*/}" ] ; then return 0 ; fi # not a project sensor kit table
    for NME in $($MYSQL -e "$(GenerateQRY $1)")
    do
        if [ "${NME/=*/}" = time ]
        then
            SECS=${NME/*=/}
            continue
        fi
        if (( ${NME/*=/} < $MIN )) ; then MIN=${NME/*=/} ; fi
        if (( ${NME/*=/} > $MAX )) ; then MAX=${NME/*=/} ; fi
        POLSMSG+="$NME, "
    done
    if (( $MAX < 1 ))
    then
        LAST=$($MYSQL -e "$(GenerateQRYlast $1)") # get time last seen
        if (( ($LAST + 10*60*60) < $(date '+%s') ))
        then
            return 1 # already warned the disactivity enough
        fi
        RTS=1
    fi # no measurements at all
    if (( $MAX < 5 ))
    then
        MSG="Date/Time: $(date --date=@$SECS '+%x %X'). Seems sensor kit has been inactive for the last hour."
    elif (( ($MAX - $MIN) > 5 ))
    then
        MSG="Date/Time: $(date --date=@$SECS '+%x %X'). Seems sensor kit has at least one sensor less functioning in the last hour."
    else
        return 0
    fi
    echo -e "$MSG\n$POLSMSG" | \
        if [ -n "${MAILTO}" ]
        then
            mail --subject="Sensor kit ${1/*_/} of project ${1/_*/} needs attention" ${MAILTO}
        else
            echo "Sensor kit ${1/*_/} of project ${1/_*/} needs attention" >/dev/stderr
            cat >/dev/stderr
        fi
    return $RTS
}
        

if [ ! -f $GENERATOR ] || [ ! -d $DIR ] || [ ! -d $WDIR ]
then
    echo Cannot find $GENERATOR or $DIR or work dir $WDIR. EXITING
    exit 1
fi

cd $WDIR

KITsns=$(GetKits "${PROJ:-VW2017}")
for KIT in $KITsns
do
    if ! CheckActive $KIT ; then continue ; fi
    if ! perl $GENERATOR -e 'pm10|pm25,pm10|rv|temp' -b 'PM,Meteo' -O ${KIT/${PROJ}/} -L now $KIT 2>/dev/null # Ref is HadM
    then
        date
        echo Failed to generate chart for ${PROJ}$KIT 
        continue
    fi
    if [ ! -f $DIR/${KIT/${PROJ}/}.html ]
    then
        date
        echo Failed to get file $DIR/${KIT/${PROJ}/}.html for chart
        continue
    fi
    if [ "${RHOST:-localhost}" != localhost ]
    then
        if ! scp $DIR/${KIT/${PROJ}/}.html ${RHOST}:$DIR/${KIT/${PROJ}/}.html
        then
            date
            echo failed to copy chart to ${RHOST} for ${KIT}
            continue
        else
            ssh ${RHOST} chgrp www-data $DIR/${KIT/${PROJ}/}.html
        fi
    else
        chgrp www-data $DIR/${KIT/${PROJ}/}.html
    fi
    # echo Installed chart $KIT.html to ${RHOST} dir $DIR
done
    
# generate all graphs for one pollutant type
if ! perl $GENERATOR -e "$POLs" -b "$POLs" -L now -O ${PROJ}${POLs/,*/} ${KITsns} ${STATIONS} 2>/dev/null
then
    date
        echo Failed to generate chart for ${PROJ}${POLs/,*/}.html
else
    if [ "${RHOST:-localhost}" = localhost ]
    then
        chgrp www-data $DIR/${PROJ}${POLs/,*/}.html
    else
        if ! scp $DIR/${PROJ}${POLs/,*/}.html ${RHOST}:$DIR/${PROJ}${POLs/,*/}.html
        then
            date
            echo failed to copy chart to ${RHOST} for ${PROJ}${POLs/,*/}.html
        else
            ssh ${RHOST} chgrp www-data $DIR/${PROJ}${POLs/,*/}.html
        fi
    fi
fi
