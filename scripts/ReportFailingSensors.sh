#!/bin/bash
# Check MySense measurements database on misfunctioning sensors

# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
#
# Copyright (C) 2020, Behoud de Parel, Teus Hagen, the Netherlands
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

# $Id: ReportFailingSensors.sh,v 2.22 2021/01/30 20:21:43 teus Exp teus $
CMD=$(echo '$RCSfile: ReportFailingSensors.sh,v $' | sed -e 's/.*RCSfile: \(.*\),v.*/\1/')

SENSORS=${SENSORS:-'(temp|rv)'}  # sensors to check for static values
VERBOSE=${VERBOSE:-0}
NOMAIL=${NOMAIL:-0}
EMAILFROM="mysense@behouddeparel.nl"  # email from address
DEBUG=${DEBUG}
if [ -n "$DEBUG" ] ; then VERBOSE=3 ; NOMAIL=1 ; fi
ATTENTS=${ATTENTS:-$HOME/.ATTENTS.sh}  # ATTENT list archive
LOWER=${LOWER:-5}  # default count of static values, ie to decide sensor is failing
NOW=$(date +%s)    # will be used several times

# DB access info
export DB=${DB:-luchtmetingen}
export DBUSER=${DBUSER:-$USER}
export DBHOST=${DBHOST:-localhost}

declare -i PRTCMD=0 # PrtCmd should be called only once
function PrtCmd(){
    if (( $PRTCMD > 0 )) ; then return ; fi
    PRTCMD=1
    echo "Reporting command: $CMD $(echo '$Revision: 2.22 $' | sed -e 's/\$//g' -e 's/ision://')"
}

if [ "${1/*-h*/help}" == help ]
then
    PrtCmd 1>&2
    echo "
Example of command:
check kit SAN_1234567abc and all active kits of project HadM:
    VERBOSE=1 ${CMD/ */}  SAN_1234567abc HadM
Check all kits active of projects SAN and HadM
    DBUSER=$USER DBHOST=localhost DBPASS=acacadabra DB=luchtmetingen REGION='(SAN|HadM)' ${CMD/ */}
CLI arguments: kits to be searched for. No argument: all kits from the REGION
If command is used from terminal the output info will be colered.

Environment variables supported:
    DBUSER=$USER DBHOST=localhost DBPASS=acacadabra DB=luchtmetingen $0 SAN_1234567abc HadM
    MySQL credentials: DBUSER=$USER, DBPASS=interact, DBHOST=localhost, DB=luchtmetingen
    DBUSER (dflt: $USER),DBPASS (dflt: ${DBPASS:-ask it}),DB (dflt: ${DB}),DBHOST (dflt: $DBHOST),
    DEBUG  Dflt: ${DEBUG:-empy}. Increase VERBOSE level and do not send fialure notices.
    VERBOSE (verbosity dflt ${VERBOSE:-0}),START and END period,REGION (expresion, dflt:$VERBOSE or all),
    NOMAIL (dflt: $NOMAIL) Do not send email notices for failing kits.
    Sensors to check for eg SENSORS='(temp|rv|pm10|pm1)'
    SENSORS (expression, sensor values to test for), Dflt: $SENSORS,
    ATTENTS file with ATTENT list archive kits/sensors info. Dflt: $ATTENTS
    LOWER (minimal static value count), Dflt: $LOWER
    Date/time in period may have format understood by the 'date' command.
    START period to start scanning for. Dflt: '3 weeks a go'
    END end of period (dflt now).
    REGION regions to check kits of. Taken from CLI arguments or environment

    The script will use $ATTENTS as archive for ATTENT (associative array)
    per measurment kit (DB table name) notices:
    LOCATION: location of the measurement kit
    INITIATED: timestamp in secs of first failure message for the measurment kit
    NOTICE: timestamp in secs of last failure notice
    COMMENT: comment to be send in notice
    SENSORS: list of failing sensors
    NEW: list of new failing sensors since last notice
    Only if no failures are found in defined period the ATTENT element will be undefined.
    To Do: ATTENT messages should be in a database not in a file ${ATTENTS}.
    "
    exit 0
fi

# collect stderror messages for overview
trap "rm -f /var/tmp/ReportFailingSensors$$ /var/tmp/FailReport$$ /var/tmp/Check$$" EXIT

# MySQL database credentials
# will use here mysql --login-path=luchtmetingen as well!
if [ -z "$DBPASS" ]
then
    read -p "Provide password for database $DB on host $DBHOST user $DBUSER: " DBPASS
fi
export DBPASS=${DBPASS:-accacadabra}
# how to approach MySQL database. Uses mysql DB configuration in home user
# needs ~/.my.cnf
MYSQL="mysql --login-path=${DB:-luchtmetingen} -h ${DBHOST:-localhost} -N -B --silent ${DB:-luchtmetingen}"

# sensors to check if there is data for them
METEO='(temp|rv|luchtdruk)'      # meteo type of sensors
DUSTCNT='pm(1|25|10)_cnt'        # dust count type of sensors
DUST='pm[0-9]{1,2}'              # dust mass type of sensors
ACCU='(accu)'                    # solar accu voltage level

# exceptions when static value is natural
declare -A EXCLUDES
EXCLUDES[luchtdruk]=15

# REGIONs: BdP (HadM), GLV (Venray), RIVM, ...
if [ -z "$REGION" ] && [ -z "$1" ]
then
    if [ -z "$1" ]
    then
        read -p 'Choose region to check for valid values of sensor: ' REGION
    fi
    REGION="${REGION:-.*}"  # use REGION to be prepended to generated HTML file name
fi

# if present use attendation email events as last sending date
declare -A ATTENT
if [ -s ${ATTENTS:-/dev/null} ]
then
    grep -P '^ATTENT\[([A-Za-z]+_[A-Fa-f0-9]+@[a-zA-Z]+[a-zA-Z0-9]*|[a-zA-Z0-9_\-\.]+@[a-zA-Z0-9\-]+(\.[a-zA-Z]+)+)\]=' ${ATTENTS:-/dev/null} >/var/tmp/Check$$
    if [ -s /var/tmp/Check$$ ] ; then . /var/tmp/Check$$ ; fi
    rm -f /var/tmp/Check$$
fi
        
# period up to dflt now
if [ -z "$LAST" ] || ! date --date="$LAST" >/dev/null # last date to show in graphs
then
  LAST=now       # use measurement data up to $LAST
fi
LAST=$(date --date="$LAST" "+%Y/%m/%d %H:%M:00")
# start period from dflt 3 weeks ago
if [ -n "$START" ] && date --date=$START
then
    START="$(date --date='$START' '+%Y/%m/%d %H:%M')"
else
    START="$(date --date='3 weeks ago' '+%Y/%m/%d %H:%M')" # only last 3 weeks from now
fi

if [ -t 2 ] # if tty/terminal use color terminal output
then
    RED="\033[1;31m"
    GREEN="\033[1;32m"
    NOCOLOR="\033[0m"
    BLACK="\033[30m"
    YELLOW="\033[33m"
    BLUE="\033[34m"
    MAGENTA="\033[35m"
    CYAN="\033[36m"
    WHITE="\033[37m"
    RESET="\033[0m"
    BOLD="\033[1m"
    UNDERLINE="\033[4m"
    REVERSED="\033[7m"

    # MAILLOG='' # do not mail logging
else
    RED=""
    GREEN=""
    NOCOLOR=''
    BLACK=""
    YELLOW=""
    BLUE=""
    MAGENTA=""
    CYAN=""
    WHITE=""
    RESET=""
    BOLD=""
    UNDERLINE=""
    REVERSED=""
fi

function LOGGING(){
    if [ -z "$MAILLOG" ] || (( $VERBOSE > 0 ))
    then
        if [ -n "$1" ]
        then echo "$*" 1>&2
        else
            cat 1>&2
        fi
        return
    fi
    if [ -n "$1" ]
    then
        echo "$*" >>/var/tmp/ReportFailingSensors$$
    else
        cat >>/var/tmp/ReportFailingSensors$$
    fi
}

# human readable date/time in std format no seconds
function DATE() {
    date --date=@"${1:-$(date '+%s')}" '+%Y-%m-%d %H:%M'
    return $?
}

# convert date/time to seconds from UNIX epoch
function Date2Secs() {
    if echo "$1" | grep -P -q '^[0-9]+$'
    then echo "$1"
    else echo $(date --date="${1:-now}" "+%s")
    fi
    return $?
}

function GetLblLocation() {
    local AKIT="$1" LOC=''
    if echo "$AKIT" | grep -q -P '^[A-Za-z]+_[A-Fa-f0-9]+$'
    then
      LOC=$($MYSQL -e "SELECT concat('Label: ',if(isnull(label),'unknown',label), '. Location: ',if(isnull(street),'street unknown',street), ', ', if(isnull(village),'unknown village',village)) FROM Sensors WHERE active AND project = '${AKIT/_*/}' AND serial = '${AKIT/*_/}' LIMIT 1")
    fi
    LOC=$(echo "${LOC//NULL/}" | sed 's/ [0-9][0-9]*[a-dA-D]*,/,/') # delete house nr in street
    echo "${LOC:-Cannot obtain location for $AKIT}"
    return
}

# print ATTENT info for a kit
function PrtAttent() {
    local AKIT="$1" ALBL I S
    if [ -z "$AKIT" ] ; then return ; fi
    if [ -n "${2/NULL/}" ] ; then ALBL=" ($2)" ; fi
    declare -A LINES
    LINES["LOCATION"]="Location of the MySense${ALBL} kit:\n\t"
    LINES["INITIATED"]="Initial fail timestamp: "
    LINES["NOTICE"]="Last notice sent: "
    LINES["SENSORS"]="${RED}Failing${NOCOLOR} sensors: "
    LINES["COMMENT"]="Fail message(s):\n\t"
    LINES["NEW"]="${BOLD}New${NOCOLOR} failing sensors since last notice: "
    LINES["STOPPED"]="${RED}Mysense sensor kit stopped measuring${NOCOLOR}: "
    echo -e "\n${BOLD}Status info MySense kit${NOCOLOR} ${BLUE}$AKIT${NOCOLOR}:"
    for I in  LOCATION INITIATED NOTICE STOPPED SENSORS NEW COMMENT
    do
      if [ -z "${ATTENT[${AKIT}@$I]}" ] ; then continue ; fi
      if echo "${ATTENT[${AKIT}@$I]}" | grep -q -P '^[0-9]{10}$'
      then
        echo -e "${LINES[$I]}$(DATE ${ATTENT[${AKIT}@$I]})"
      else
        S="${ATTENT[${AKIT}@$I]}"
        case $I in
        SENSORS|NEW) # make sensor ids human
           S=$(echo "${S}" | sed -e 's/,/ /g' -e 's/   */ /g' -e 's/pm/PM/g' -e 's/_cnt/ count/g' -e 's/temp/oC/g' -e 's/luchtdruk/hPa/g' -e 's/rv/RH/g' -e 's/PM\([02]\)/PM\1./g' -e 's/^ //' -e 's/ $//' -e 's/ /, /g')
           S="${RED}${S}${NOCOLOR}"
        ;;
        esac
        echo -e "${LINES[$I]}$S"
      fi
    done
}

# send email to recepients: SendEmail subject [file] addr ...
function SendEmail() {
    local CNTNT RTS=0 ADDR
    if (( ${NOMAIL:-0} > 0 )) ; then return 0 ; fi
    local SUBJECT="${1:-MySense kit failure message}" ; shift
    local PRE="This is an automatic sent email with MySense kit sensor failure information.\nIf you do not want to receive any more notices or want to change your email adress please reply to the sender.\n"
    if [ -s "${1}" ]
    then
        CNTNT=${1}   # else read from stdin
        shift
    else
        CNTNT=/var/tmp/FailReport$$
        cat >$CNTNT
    fi
    # make bare email addresses as user@host.dom ... from arguments
    for ADDR in $(echo " $@ " | sed -r -e 's/,/ /g' -e 's/ [a-zA-Z][a-zA-Z\._-]+ / /g' -e 's/[<>]//g')
    do
        if  [ -z "${ATTENT[$ADDR]}" ] || (( "${ATTENT[$ADDR]}" < $NOW-(3600*24*30) ))
        then
            ATTENT[$ADDR]=$NOW
            PRE+="This might be the first time you receive this message.\nThe notices email software is in beta test. So the message may have misinformation or errors. Please send a reply if so.\nAny positive response in this period is very helpfull.\n"
        fi
        if ! (echo -e "$PRE" ; cat $CNTNT ) |  perl -pe 's/\033\[(1;)*[0-9]+m//g' | mail -r "$EMAILFROM" -s "$SUBJECT" $ADDR
        then
            RTS=1
            echo -e "${CMD/ */}: ${RED}ERROR${NOCOLOR} sending email to $ADDR"
            if [ -s "$CNTNT" ]
            then
                echo -e "Message:\n" "-----------------${BLUE}" 1>&2
                cat $CNTNT 1>&2
                echo -e "\n${NOCOLOR}-----------------" 1>&2
            fi
        fi
    done
    return $RTS
}
            
            
# email a notice on failure
function SendNotice() {
    local AKIT="$1" ALBL="$2" SENS="$3" FILE="$4"
    local ADDRESS
    if [ ! -s $FILE ] ; then return 0 ; fi
    if [ -n "$DEBUG" ] || (( $VERBOSE > 1 ))
    then
        cat $FILE 1>&2
    fi
    if [ -z "${ATTENT[${AKIT}@NOTICE]}" ]
    then
        ATTENT[${AKIT}@NOTICE]=0
    fi
    if [ -z "${ATTENT[${AKIT}@INITIATED]}" ] # mark date/time first discovered
    then
        ATTENT[${AKIT}@INITIATED]="$NOW"
    fi
    if [ -z "${ATTENT[${AKIT}@COMMENT]}" ] # mark date/time first discovered
    then
        ATTENT[${AKIT}@COMMENT]="First failure for MySense measuring kit: $(date --date=@${ATTENT[${AKIT}@INITIATED]} +%y/%m/%dT%H:%M )"
    fi
    ADDRESS=$($MYSQL -e "SELECT notice FROM Sensors WHERE active AND NOT isnull(notice) AND project = '${AKIT/_*/}' AND serial = '${AKIT/*_/}' LIMIT 1")
    ADDRESS=$(echo "$ADDRESS" | sed -e 's/,* *slack:[^,]*//' -e 's/email: *//g' -e 's/^  *//' -e 's/  *$//' -e 's/NULL//' -e 's/^  *$//')
    ADDRESS=$(echo " $ADDRESS " | sed -r -e 's/,/ /g' -e 's/ [a-zA-Z][a-zA-Z\._-]+ / /g' -e 's/[<>]//g' -e 's/^  *//' -e 's/  *$//')
    if (( $NOW > (${ATTENT[${AKIT}@NOTICE]} + 3*24*60*60) )) # only once in 3 days
    then
        ATTENT[${AKIT}@NOTICE]=$NOW
    elif (( $VERBOSE > 0 ))
    then
        echo "SendNotices to ${ADDRESS// /, } skipped upto $(DATE $((${ATTENT[${AKIT}@NOTICE]} + 3*24*60*60)) )" 1>&2
        return 0
    fi
    if [ -n "$DEBUG" ] || (( ${NOMAIL:-0} > 0 ))
    then
        if [ -n "$ADDRESS" ]
        then
            echo "${CMD/ */}: Would have sent email notice to '$ADDRESS'" 1>&2
            ADDRESS=''
        fi
    fi
    if (( ${ATTENT[${AKIT}@NOTICE]} == 0 ))
    then
        unset ATTENT[${AKIT}@NOTICE]; unset ATTENT[${AKIT}@NEW]
    fi
    if [ -n "${ADDRESS}" ]
    then
        if [ -z "${ATTENT[${AKIT}@LOCATION]}" ] ; then ATTENT[${AKIT}@LOCATION]=$(GetLblLocation "$AKIT") ; fi
        if (PrtAttent "$AKIT"  $ALBL ; cat $FILE ) | SendEmail "ATTENT: MySense kit $AKIT sensor $SENS ${LOCATION:-Location is not defined.}" $ADDRESS
        then
            if (( $VERBOSE > 0 ))
            then
                echo "Sent email notice to '$ADDRESS'" 1>&2
                if (( $VERBOSE > 1 ))
                then
                    echo -e "Email content: " 1>&2
                    (PrtAttent "$AKIT"  $ALBL ; cat $FILE ) 1>&2
                fi
            fi
        fi
        unset ATTENT[${AKIT}@NEW]
    fi
    return $?
}

# de activate measurment kits from data acquisition
function InActivate() {
    local AKIT
    for AKIT in $@
    do
        $MYSQL -e "UPDATE Sensors SET active = 0 WHERE project = '${AKIT/_*/}' AND serial = '${AKIT/*_/}' AND active; UPDATE TTNtable SET active = 0, luftdaten = 0 WHERE project = '${AKIT/_*/}' AND serial = '${AKIT/*_/}' AND (active OR luftdaten);"
        echo "MySense kit $AKIT has been deactivated for MySense measurements database and Luftdaten and other data portals forwarding." 1>&2
    done
    return $?
}

# check for enoug valid measurements in a period of time
# find null values for a TPE sensor as well static values over an amount of time
# deactivate kits not active in 6 months of time and send notice
function NrValids() {
    local KT="$1" TPE="$2" STRT=$(Date2Secs "$3") LST=$(Date2Secs "$4") DAT RTS=0
    declare -a STAT
    declare -i CNT
    CNT=$($MYSQL -e "SELECT count($TPE) FROM $KT WHERE not isnull($TPE)")
    if (( $CNT == 0 ))
    then
        echo "MySense kit $KT: has no active sensor $TPE on board." 1>&2
        return 0
    fi
    # STAT[0] count NULL values, STAT[1] count all measurements,
    # STAT[2]/STAT[3] min/max date/time
    STAT=($($MYSQL -e "SELECT count(*) FROM $KT WHERE isnull($TPE) AND UNIX_TIMESTAMP(datum) >= $STRT AND UNIX_TIMESTAMP(datum) <= $LST; SELECT count(*), UNIX_TIMESTAMP(min(datum)), UNIX_TIMESTAMP(max(datum)) FROM $KT WHERE UNIX_TIMESTAMP(datum) >= $STRT AND UNIX_TIMESTAMP(datum) <= $LST;") )
    if (( (${STAT[1]} - ${STAT[0]}) < 15 ))
    then  # not enough measurements in this period
        if (( $VERBOSE > 0 ))
        then
            if (( ${STAT[1]} > 0 ))
            then STAT[1]=$(( (${STAT[0]} * 100) / ${STAT[1]} ))
            else STAT[1]=0 ; fi
            echo "MySense kit $KT: not enough measurements (${STAT[1]} with ${STAT[0]} NULL values) ${STAT[1]}% in period of $(DATE ${STRT}) up to $(DATE ${LST})" 1>&2
            STAT[2]=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM $KT WHERE NOT isnull($TPE) ORDER BY datum DESC LIMIT 1")
            echo -e "\tLast active date $(DATE ${STAT[2]}) of sensor $TPE." 1>&2
            if (( ${STAT[2]} < $(date --date='6 months ago' +%s) ))
            then
                echo -e "Kit $KT was not active during last 6 months.\n" 1>&2
                InActivate $KT 1>&2
            fi
        fi
        # return nr of invalids, valids, first valued, last valued
        return 1
    fi
    declare -a VAL
    # see if a value looks like a static value in this period
    # get array of: different not NULL values, max date, a possible static value
    declare -i NEXT=$((${LST}-1))
    declare -i STATICS=0 NULLS=${STAT[0]} PERIODS=1 LAST_VALID=0
    local AVOID=10000
    while true   # try to find period(s) with static measurements
    do
        # NEXT last date/time this period of current loop, STAT[2] first date/time loop
        # current loop period: STAT[2] up to NEXT
        if (( ($NEXT - ${STAT[2]}) < 15 )) ; then break ; fi

        # VAL[0] static value, VAL[1] last date/time static value, VAL[2] count static value
        VAL=($($MYSQL -e "SELECT $TPE, UNIX_TIMESTAMP(max(datum)), count(*) AS cnt FROM $KT WHERE UNIX_TIMESTAMP(datum) >= ${STAT[2]} AND UNIX_TIMESTAMP(datum) < $NEXT AND NOT isnull($TPE) GROUP BY $TPE HAVING cnt > ${EXCLUDES[${TPE}]:-${LOWER}} ORDER BY cnt DESC LIMIT 1") )
        if [ -z "${VAL[2]}" ]
        then
            break
        elif (( ( (${VAL[2]}*100)/(${STAT[1]}-${STAT[0]}) ) <= 10 ))
        # more as 10%: probably they are static values
        then
            break
        fi
        if (( $LAST_VALID <= 0 ))
        # last value not null: not maybe static value
        then
            LAST_VALID=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM $KT WHERE UNIX_TIMESTAMP(datum) >= ${STAT[2]} AND UNIX_TIMESTAMP(datum) < $NEXT AND NOT isnull($TPE) AND $TPE != ${VAL[0]} ORDER BY datum DESC LIMIT 1")
        fi

        # NEXT date/time with a value not NULL and not maybe static
        NEXT=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM $KT WHERE NOT isnull($TPE) AND $TPE != ${VAL[0]} AND UNIX_TIMESTAMP(datum) < ${VAL[1]} AND UNIX_TIMESTAMP(datum) >= $STRT ORDER BY datum DESC LIMIT 1")
        if [ $NEXT = 0 ] ; then NEXT=${STAT[2]} ; fi # use first one

        # check if maybe static value was probably normal
        CNT=$($MYSQL -e "SELECT count(*) FROM $KT WHERE NOT isnull($TPE) AND $TPE = ${VAL[0]} AND UNIX_TIMESTAMP(datum) <= ${VAL[1]} AND UNIX_TIMESTAMP(datum) > $NEXT")
        if (( $CNT < 5 ))
        then
            continue
        fi

        if [ $AVOID = 10000 ] ; then AVOID=${VAL[0]} ; fi # first should be it
        STAT[0]=$(( ${STAT[0]} - $CNT)) ; STATICS+=$CNT ; PERIODS+=1
        if (( ${VAL[1]} > $LAST_VALID )) ; then RTS=1 ; fi # static period was old
        echo "MySense kit $KT: $CNT of ${STAT[1]} static (${VAL[0]} not NULL) measurements in period $(DATE ${NEXT}) up to $(DATE ${VAL[1]})" 1>&2
        RTS=1 ; break  # period has not NULL static values of cnt >= 5
        # continue loop, find next static period
    done
    echo "MySense kit $KT: $((${STAT[1]}-${STAT[0]})) of ${STAT[1]} valid measurements $(( ( (${STAT[1]}-${STAT[0]})*100) / ${STAT[1]} ))% in period $(DATE ${STAT[2]}) up to $(DATE ${STAT[3]})" 1>&2
    echo -e "\tMeasurements sensor $TPE:\n\tTotal ${STAT[1]}, null valued: $NULLS, static valued: $STATICS, and $((${STAT[1]} - $NULLS - $STATICS)) valid valued in $PERIODS period(s)." 1>&2
    STAT[2]=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM $KT WHERE NOT isnull($TPE) AND $TPE != $AVOID ORDER BY datum DESC LIMIT 1")
    echo -e "\tLast active date $(DATE ${STAT[2]}) of sensor $TPE." 1>&2
    if (( (${STAT[2]} - $LST) > 2*60*60 )) ; then rts=1 ; fi
    return $RTS
}

# check if kit is producing measurmeent data in a period
# returns true/false and last date/time any sensed
function LastMeasurement() {
    local AKIT="$1" STRT="$2" LST="$3"
    local COLS COL SENSED DUST_E="$DUSTCNT"
    declare -i DT
    declare -i RECENT=$(date --date="$STRT" '+%s') STRTi
    STRTi=$RECENT
    if $MYSQL -e "SELECT description FROM Sensors WHERE project = '${AKIT/_*/}' AND serial = '${AKIT/*_/}' AND active ORDER BY datum DESC" | grep -q -P '(SDS011)' 
    then
        DUST_E="$DUST"
    fi
    COLS=$($MYSQL -e "DESCRIBE $AKIT" | awk '{ print $1; }' | grep -P "^(${DUST_E:-XYZ}|${METEO:-XxX})$")
    for COL in $COLS
    do
        DT=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM $AKIT WHERE datum >= '$STRT' AND datum <= '$LST' AND NOT ISNULL($COL) ORDER BY datum DESC LIMIT 1")
        if (( $DT > $RECENT ))
        then
            RECENT="$DT" ; SENSED="$COL"
        fi
    done
    if (( $RECENT == $STRTi  )) ; then echo -e "${RED}No recent meteo or dust measurement of any sensor${NOCOLOR} after date $STRT" ; return 1 ; fi
    if (( $VERBOSE == 0 )) ; then return 0 ; fi
    echo "Recent e.g. $SENSED measurement at date: "
    date --date="@$RECENT" "+%Y/%m/%d %H:%M"
    return 0
}

# check accus values, accu max in period should be >11.5V
function CheckAccu() {
    local AKIT="$1" STRT="$2" LST="$3" COL="$4"
    local MAX MIN VAL
    declare -a VALS
    VALS=($($MYSQL -e "SELECT min(round($COL*10)), max(round($COL*10)), round(AVG($COL)*10) FROM $AKIT WHERE datum <= '$LST' AND datum > DATE_SUB('$LST', INTERVAL 3 DAY)"))
    if (( "${#VALS[@]}" < 3 )) ; then return 0 ; fi
    if (( "${VALS[2]/NULL/0}" < 50 )) ; then return 0 ; fi
    if ((  ${VALS[2]/NULL/0}  <= 115 )) # voltage warn level
    then
        echo "WARNING Accu voltage  ($((${VALS[0]}/10)).$((${VALS[0]}%10))V .. $((${VALS[1]}/10)).$((${VALS[1]}%10))V) (min,max), accu level is below 11.5V, current value: $((${VALS[2]}/10)).$((${VALS[2]}%10))V." 1>&2        
        echo -e "${RED}WARNING Accu voltage${NOCOLOR}  ($((${VALS[0]}/10)).$((${VALS[0]}%10))V .. $((${VALS[1]}/10)).$((${VALS[1]}%10))V) (min,max), accu level is below 11.5V, current value: $((${VALS[2]}/10)).$((${VALS[2]}%10))V." | LOGGING
        return 1
    elif (( $VERBOSE > 0 ))
    then
        echo "Accu voltage  ($((${VALS[0]}/10)).$((${VALS[0]}%10))V .. $((${VALS[1]}/10)).$((${VALS[1]}%10))V) (min,max), minimum below 10.8V, current value: $((${VALS[2]}/10)).$((${VALS[2]}%10))V." | LOGGING
    fi
    return 0
}

# check kit (arg1) for silent sensors in a period of time (arg2 and last time arg3)
ActiveSensors=()
NotActiveSensors=()
NotOperational=()
# side effect: collect active and not active sensors of a measurement kit
function CheckSensors() {
    local AKIT="$1" STRT="$2" LST="$3"
    local COLS COL QRY='' DUST_E="$DUSTCNT"
    ActiveSensors=()
    NotActiveSensors=()
    NotOperational=()
    local MSG=''
    declare -a DTS COLS
    # some dust sensors do not have bin count
    COLS=($($MYSQL -e "DESCRIBE $AKIT" | awk '{ print $1; }' | grep -P "^(${DUST:-XYZ}|${DUST_E:-XYZ}|${METEO:-XxX}|${ACCU:-XYZ})$") )
    if (( ${#COLS[@]} == 0 )) ; then return 2 ; fi
    for COL in ${COLS[@]}
    do
        QRY+="SELECT IF(COUNT($COL) > 0,'$COL','') FROM $AKIT WHERE datum > SUBDATE(NOW(), INTERVAL 1 YEAR) AND NOT ISNULL($COL);"
    done
    COLS=($($MYSQL -e "$QRY")) # delete those sensors not available by this kit 
    QRY=''
    # get sensors measuring in this period
    for COL in ${COLS[@]} # collect last date timestamp for all searched for pollutants
    do
        if [ -n "$QRY" ] ; then QRY+=',' ; fi
        QRY+="(SELECT UNIX_TIMESTAMP(max(datum)) FROM $AKIT WHERE NOT ISNULL($COL) AND datum >= '$STRT' AND datum <= '$LST')"
    done

    # separate those sensors active and not active in this period
    DTS=($($MYSQL -e "SELECT $QRY"))
    declare -i I=-1
    declare -i LSTi=$(date --date="$LST" '+%s')
    declare -i NullCnt=0
    for COL in ${COLS[@]}
    do
        I+=1
        if echo "$COL" | grep -q -P "${ACCU:-XYZ}"  # sensor is column accu level?
        then # special handling of accu
            if [ "${DTS[$I]}" != NULL ]
            then
              CheckAccu "$AKIT"  "$STRT" "$LST" "$COL" 1>&2
              # NotActiveSensors[${#NotActiveSensors[@]}]="$COL"
            fi # no accu attached
            ActiveSensors[${#ActiveSensors[@]}]="$COL"
            continue
        fi
        if [ "${DTS[$I]}" = NULL ]
        then # set device not operational if no measurement in this period
            NullCnt+=1
            if (( $($MYSQL -e "SELECT COUNT($COL) FROM $AKIT WHERE NOT ISNULL($COL) AND UNIX_TIMESTAMP(datum) >= ($LSTi-60*60*24*92) AND datum <= '$LST'") > 0 ))
            then
                MSG+="\tSensor $COL: no values in this period\n"
                NotActiveSensors[${#NotActiveSensors[@]}]="$COL"
            else
              NotOperational[${#NotOperational[@]}]="$COL"
              if (( $VERBOSE > 0 ))
              then
                echo "Sensor $COL in MySense kit $AKIT is not configured"
                if (( $VERBOSE > 1 ))
                then
                    QRY=$($MYSQL -e "SELECT max(datum) FROM $AKIT WHERE NOT ISNULL($COL) AND UNIX_TIMESTAMP(datum) >= ($LSTi-60*60*24*92) AND datum <= '$LST'")
                    QRY=${QRY/*NULL*/3 months before end of period}
                    echo "Sensor ${BOLD}$COL${NOCOLOR} is silent. Most recent measurement for $COL at date: ${RED}$QRY${NOCOLOR}"
                fi
              fi | LOGGING
            fi
        elif (( "${DTS[$I]}" <= ($LSTi - 4*60*60) )) # alarm after N hours silence
        then
            MSG+="\tSensor $COL: last seen $(date --date=@${DTS[$I]} '+%Y/%m/%d %H:%M')\n"
            NotActiveSensors[${#NotActiveSensors[@]}]="$COL"
        else
            ActiveSensors[${#ActiveSensors[@]}]="$COL"
        fi
    done
    if (( ${#ActiveSensors[@]} == 0 ))
    then # no measuring senors seen in this period
        echo -e "${RED}FAILURE: kit $AKIT is set active. Is silent in period: $STRT to $LST!${NOCOLOR}" 1>&2
    elif (( ${#NotActiveSensors[@]} > 0 ))
    then
        local IS=is
        if (( ${#NotActiveSensors[@]} > 1 )) ; then IS=are ; fi
        echo "There $IS ${#NotActiveSensors[@]} of ${#DTS[@]} sensors to be checked less functioning in kit $AKIT within the period $STRT up to ${LST/%:00/}:" 1>&2
        echo -e "$MSG" 1>&2
    else
        return 0
    fi
    return 1
}

#CheckSensors SAN_b4e62df48fe9 "$(date --date='3 weeks ago' '+%Y/%m/%d %H:%M')" "$(date '+%Y/%m/%d %H:%M')"

# gert all kit table names for kits or region
function GetRegionalKits() {
    local RGN AKIT AKITS='' TBLS REGEXP MATCH ARG
    TBLS=$($MYSQL -e 'SHOW TABLES' | grep -P '^[A-Za-z]+_[a-zA-Z0-9]{7,}$')
    for ARG in $@
    do
        MATCH=
        # argument is measurement kit in a project: project (all for a project)
        if echo "$ARG" | grep -q -P '^[A-Z][A-Za-z]+$'
        then
            RGN=$($MYSQL -e "SELECT DISTINCT concat(project,'_',serial) FROM Sensors WHERE project = '$ARG' AND active ORDER BY project, datum DESC")
        # argument is measurement kit with a label: eg bwlvc-9a7d as id-hex
        elif echo "$ARG" | grep -q -P '^[A-Za-z]+-[0-9a-fA-F]{4}$'
        then
            RGN=$($MYSQL -e "SELECT DISTINCT concat(project,'_',serial) FROM Sensors WHERE label = '$ARG' AND active ORDER BY project, datum DESC")
        # argument is pattern DB match for kits: _EXPRserial (eg '_%123' all with serial '?123')
        elif echo "$ARG" | grep -q -P '_.+'
        then
            if [ -n "${ARG/_*/}" ] ; then MATCH="project = '${ARG/_*/}' AND " ; fi
            RGN=$($MYSQL -e "SELECT DISTINCT concat(project,'_',serial) FROM Sensors WHERE $MATCH serial REGEXP '${ARG/*_/}' AND active ORDER BY project, datum DESC")
        fi
        if [ -z "$RGN" ]
        then
            echo "${CMD/ */}: Argument error in MySense kit ID: '$ARG' does not exists." 1>&2
            exit 1
        fi
        for AKIT in $RGN
        do
            if echo "$AKITS" | grep -q "$AKIT" ; then continue ; fi
            # some kit table names carry different regional ID but are in this project
            AKITS+=' '
            if ! echo "$TBLS" | grep -q "$AKIT"
            then
                AKITS+=$($MYSQL -e "SHOW TABLES LIKE '%${AKIT/*_/_/}'")
            else
                AKITS+=${AKIT}
            fi
        done
    done
    echo "$(echo  $AKITS | sort | uniq)"
}

# get last NR measurements of a kit from DB into error file
function LastSensed() {
    local NME="$1" ; shift
    if [ -z "$NME" ] || [ $($MYSQL -e "SHOW TABLES LIKE '$NME'") != "$NME" ]
    then
        echo "No DB table $NME found."
        return 1
    fi
    local NR=${1:-12} ; shift
    if [ -z "$1" ] ; then return 0 ; fi
    local POL=''
    local ACT="${1}" # active choice of sensors in kit
    local NONACT="${2}" # not active choice of sensors in this kit
    ACT=$(echo "${ACT}" | sed -e 's/^  *//' -e 's/  *$//' -e 's/  */ /g' -e 's/\([a-z0-9][a-z0-9_]*\)/\1 as "\1",/g' -e 's/as "pm/as "PM/g' -e 's/_cnt"/ cnt"/g' -e 's/as "temp/as "oC/g' -e 's/as "luchtdruk/as "hPa/g' -e 's/as "rv/as "RH/g' -e 's/PM\([02]\)/PM\1./g' -e 's/,$//')
    NONACT=$(echo "${NONACT}" | sed -e 's/^  *//' -e 's/  *$//' -e 's/  */ /g' -e 's/\([a-z0-9][a-z0-9_]*\)/\1 as "\1*",/g' -e 's/as "pm/as "PM/g' -e 's/_cnt."/ cnt*"/g' -e 's/as "temp/as "oC/g' -e 's/as "luchtdruk/as "hPa/g' -e 's/as "rv/as "RH/g' -e 's/PM\([02]\)/PM\1./g' -e 's/,$//')
    POL="$ACT"
    if [ -n "$POL" ] 
    then
        if [ -n "$NONACT" ] ; then POL+=", $NONACT" ; fi
    else
        POL="$NONACT"
    fi
    if [ -z "$POL" ] ; then return ; fi
    echo -e "Following overview is a selection of most recent and may not show previous failures. Failures are denoted as ${RED}*${NOCOLOR}  or NULL in the measurements of $NME in database table:"
    POL=$(echo "$POL" | sed -e 's/temp as/ROUND(temp,1) as/' -e 's/rv as/ROUND(rv) as/' -e 's/luchtdruk as/ROUND(luchtdruk) as/' -e 's/\(pm_*[0-9][0-9]*\) as/ROUND(\1,1) as/g' -e 's/\(pm[0-9][0-9]*_cnt\) as/ROUND(\1) as/g')
    $MYSQL --table --column-names -e "SELECT DATE_FORMAT(datum, '%d-%c-%y %H:%i') as 'timestamp', $POL FROM $NME ORDER BY datum DESC LIMIT ${NR}"
    return $?
}

#################################  main
# get KITS to check for working sensors
KITS=''
if [ -z "$1" ] && [ -n "$REGION" ] # region defined: check all active kits in that region
then
    KITS=$(GetRegionalKits $REGION)       
elif [ -n "$1" ]  # no region defined, there are arguments kits or region
then
    KITS=$(GetRegionalKits $@)
fi

# for each kit get failing sensors w're interested in and report failiong kits
for KIT in $KITS
do
  if (( $VERBOSE > 0 ))
  then
        PrtCmd 1>&2
        echo -e "\n${BLUE}${BOLD}Checking ${KIT}:${NOCOLOR}" 1>&2
  fi
  # ActiveSensors=()    # sensors operational
  # NotActiveSensors=() # sensors failing
  # NotOperational=()   # sensors more as several month with NULL values
  # next: side effect is a list ActiveSensors, NotActiveSensors and NotOperational
  CheckSensors "$KIT" "$START" "$LAST" 2>/var/tmp/Check$$  # is producing data

  SENSORS_FAILED=()
  NWline=0
  # check per interested sensor for failures
  for SENSOR in ${ActiveSensors[@]} ${NotActiveSensors[@]}
  do
    # SENSORS is pattern for sensors (dust/meteo/accu) to check for
    if ! echo "$SENSOR" | grep -q -P "$SENSORS" ; then continue ; fi
    # look into meteo sensor actives for static values in this period: failing sensors
    # for each sensor in ActiveSensors see if it is lately failing
    if ! NrValids "$KIT" "$SENSOR" "$START" "$LAST" 2>/var/tmp/CheckVal$$
    then # found recent failing sensors of this kit: add to SENSORS_FAILED array
        if (( $VERBOSE > 1 ))
        then
            if (( $NWline == 0 )) ; then echo "" 1>&2 ; NWline=1 ; fi
            echo -e "${BOLD}${KIT}${NOCOLOR} sensor ${RED}$SENSOR${NOCOLOR} is ${RED}NOT OK${NOCOLOR}." 1>&2
            if (( $VERBOSE > 3 ))
            then
                cat /var/tmp/CheckVal$$ 1>&2
            fi
        fi
        SENSORS_FAILED[${#SENSORS_FAILED[@]}]="$SENSOR" # add this recent failing sensor
        cat /var/tmp/CheckVal$$ >>/var/tmp/Check$$  # add fail info to overview
        # and delete this failing sensor from ActiveSensors
        for (( I=0; I < ${#ActiveSensors[@]} ; I++))
        do
            if [ "${ActiveSensors[$I]}" = "$SENSOR" ]
            then
              unset ActiveSensors[$I] ; break
            fi
        done
     elif (( $VERBOSE > 1 ))
     then # the sensor is OK
        if (( $NWline == 0 )) ; then echo "" 1>&2 ; NWline=1 ; fi
        echo -e "${BOLD}${KIT}${NOCOLOR} sensor ${GREEN}$SENSOR${NOCOLOR} is ${GREEN}OK${NOCOLOR}." 1>&2
        if (( $VERBOSE > 3 )) ; then cat /var/tmp/CheckVal$$ 1>&2 ; fi
     fi
     rm -f /var/tmp/CheckVal$$
  done
  # ActiveSensors: array with OK sensors
  # NotActiveSensors: array sensors not measuring 
  # SENSORS_FAILED: array recently failing

  if (( ${#SENSORS_FAILED[@]} == 0 ))
  then # fully measuring kit is OK, clear ATTENT info for this kit
    for F in ${!ATTENT[@]}
    do
        if echo "$F" | grep -q "${KIT}"
        then
            unset ATTENT[${KIT}@$F]
        fi
    done
    if (( $VERBOSE > 0 ))
    then
        echo -e "Kit ${BOLD}${KIT}${NOCOLOR}: ${ActiveSensors[@]} active are ${GREEN}OK${NOCOLOR}, not active sensors ${RED}${NonActiveSensors[@]:-none discovered}${NOCOLOR}." 1>&2
    fi
    continue # do next kit
  fi

  # measurement kit has sensor(s) failing: all (kit is dead) or one or more sensors
  # update ATTENT info
  if (( ${#ActiveSensors[@]} != 0 ))
  then  # one or more sensors are ok
    unset ATTENT[${KIT}@STOPPED]
    if [ -z "${ATTENT[${KIT}@SENSORS]}" ]
    then # all are new failures
      ATTENT[${KIT}@NEW]=$(echo "${SENSORS_FAILED[@]}" | sed -e 's/^  *//' -e 's/  *$//' -e 's/  */,/g')
      ATTENT[${KIT}@SENSORS]="${ATTENT[${KIT}@NEW]}"
      ATTENT[${KIT}@NOTICE]=0 # send email
    else
      # combine : copy failing ones and mark new ones
      S=" $(echo ${ATTENT[${KIT}@SENSORS]} | sed 's/,/ /g') " ; SN=''
      N=" $(echo ${ATTENT[${KIT}@NEW]} | sed 's/,/ /g') " ; NN=''
      for F in $(echo "${ATTENT[${KIT}@SENSORS]}" | sed -e 's/,/ /g')
      do
        if ! echo " $S " | grep -q " $F "
        then
            if ! echo " $NN " | grep -q " $F "
            then # add to NEW
                NN+="$F "
            fi
        fi
        if ! echo " $SN " | grep -q " $F "
        then # add to SENSORS
            SN+="$F "
        fi
      done
      ATTENT[${KIT}@SENSORS]=$(echo "${SN/% /}" | sed 's/ /,/g')
      ATTENT[${KIT}@NEW]=$(echo "${NN/% */}" | sed -e 's/^  *//' -e 's/  */,/g')
    fi
  else # measurement kit seems to be dead
    unset ATTENT[${KIT}@NEW] ; unset ATTENT[${KIT}@SENSORS]
    if [ -z "${ATTENT[${KIT}@STOPPED]}" ]
    then
        ATTENT[${KIT}@STOPPED]="$NOW"
    fi
  fi

  # make noise if there are failing sensors detected
  if [ -s /var/tmp/Check$$ ] # there is a failure message
  then
      PrtCmd | LOGGING
      if [ -n "${ATTENT[${KIT}@NEW]}" ] # new fail detected?
      then
          echo -e "\tNEW - since previous check" | LOGGING
          if (( ${#NotActiveSensors[@]} > 0 )) # only if not all failing
          then
            if (( ${#NotActiveSensors[@]} == 0 ))
            then
               echo -e "\tLooks like MySense kit $KIT is ${RED}NOT operational${NOCOLOR}!" | LOGGING
            else
                (echo -en "\tFailing sensors of MySense kit $KIT: ${RED}" ; echo -n "${NotActiveSensors[@]}" | sed 's/ /, /g' ; echo -e "${NOCOLOR}.") | LOGGING
            fi
          fi
      fi
      if (( ${#SENSORS_FAILED[@]} > 0 )) || [ -n "${ATTENT[${KIT}@STOPPED]}" ]
      then
        ATTENT[${KIT}@LOCATION]=$(GetLblLocation "$KIT" )
        if [ -z "${ATTENT[${KIT}@INITIATED]}" ]
        then
          if [ -z "${ATTENT[${KIT}@INITIATED]}" ] ; then ATTENT[${KIT}@INITIATED]=$NOW ; fi
          if [ -z "${ATTENT[${KIT}@COMMENT]}" ]
          then
            if (( ${#ActiveSensors[@]} == 0 ))
            then
              ATTENT[${KIT}@COMMENT]="No active sensors in the period found."
            else
              ATTENT[${KIT}@COMMENT]="Sensors: ${#ActiveSensors[@]} active, ${#SENSORS_FAILED[@]} has/have failures."
            fi
          fi
        fi
      fi
      if (( $VERBOSE > 3 ))
      then
        cat /var/tmp/Check$$ 1>&2
      fi

      # send email individual notice
      LABEL=$($MYSQL -e "SELECT label FROM Sensors WHERE active AND project = '${KIT/_*/}' AND serial = '${KIT/*_/}' LIMIT 1")
      if ! SendNotice "$KIT" "${LABEL/NULL/}" "$(echo ${NotActiveSensors[@]} | sed 's/ /,/g')" /var/tmp/Check$$
      then
           echo -e "${RED}FAILURE to send Notice${NOCOLOR} about kit $KIT, failing sensors ${NotActiveSensors[@]}" 1>&2
      fi

      # send overview notice
      PrtAttent "$KIT" $LABEL | LOGGING
      if (( ${#ActiveSensors[@]} <= 0 ))
      then
        if (( $VERBOSE > 0 ))
        then
           echo -e "${RED}$KIT is not measuring from $START up to $LAST!${NOCOLOR}"  1>&2
        fi
        echo -e "$KIT is not operational! No measurements in period $START up to $LAST." >>/var/tmp/Check$$
      elif (( "${#SENSORS_FAILED[@]}" > 0 ))
      then
        echo -e "MySense kit ${BLUE}$KIT${NOCOLOR} has maybe problems with sensors:\n\t${RED}$(echo "${SENSORS_FAILED[@]}${NOCOLOR}" | sed -e 's/ /,/g' -e 's/,,,*/,/g' -e 's/pm/PM/g' -e 's/_cnt/ count/g' -e 's/temp/oC/g' -e 's/luchtdruk/hPa/g' -e 's/rv/RH/g' -e 's/PM\([02]\)/PM\1./g' -e 's/,/, /g' -e 's/, *$//' )!" | LOGGING
        LastSensed $KIT 12 "$(echo ${ActiveSensors[@]})" "$(echo ${SENSORS_FAILED[@]})" | perl -pe "s/NULL/${RED}NULL${NOCOLOR}/g; s/\\*/${RED}*${NOCOLOR}/g" | tee -a /var/tmp/Check$$ | head --lines=6 | LOGGING
      fi
      rm -f /var/tmp/Check$$
  else # no failure detected, clean up ATTENT for this kit
      for AT  in ${!ATTENT[@]} # get rid of deprecated failing kits
      do
        if echo "$AT" | grep -q "^$KIT@" 
        then unset ATTENT[$AT]
        fi
      done
      if (( $VERBOSE > 0 ))
      then
        echo -e "\n${BOLD}$KIT${NOCOLOR} location: ${BOLD}$(GetLblLocation "$KIT")${NOCOLOR}." 1>&2
        echo -e "MySense kit ${BOLD}$KIT${NOCOLOR} is ${GREEN}OK${NOCOLOR}.\nSensors: ${ActiveSensors[@]}." 1>&2
      fi
  fi
done

# email combined report of failing kits logging to measurement kits system admins
if [ -s /var/tmp/ReportFailingSensors$$ ]
then
   if [ -n "$MAILLOG" ] && (( ${NOMAIL:-0} == 0 ))
   then
      if ! SendEmail "Log of failuring MySense measurementskits" /var/tmp/ReportFailingSensors$$ $MAILLOG
      then
        echo "${RED}ERROR${NOCOLOR}: Email logging to '$MAILLOG' is failing!" 1>&2
      fi
   elif [ -n "$DEBUG" ] || [ -z "$MAILLOG" ]
   then
      echo "Would have sent Report Failing Sensor email to '${MAILLOG:-Not defined}':" 1>&2
      cat /var/tmp/ReportFailingSensors$$ 1>&2
   fi
   rm -f /var/tmp/ReportFailingSensors$$
fi

# save notices history
if [ -s ${ATTENTS:-/dev/null} ] ; then rm -f ${ATTENTS:-/dev/null} ; fi
if (( ${#ATTENT[@]} > 0 ))
then
    echo "#
# $CMD: file created or modified  at $(DATE)
# notices and dates/time sent
#" >${ATTENTS:-/dev/null}
fi
for KIT in ${!ATTENT[@]}
do
    if echo "${ATTENT[$KIT]}" | grep -q -P '^[0-9]{10}$'
    then
      echo "ATTENT[$KIT]=${ATTENT[$KIT]} # $(date --date=@${ATTENT[$KIT]} '+%d/%m/%Y %H:%M')"
    else
      echo "ATTENT[$KIT]='${ATTENT[$KIT]}'"
    fi
done | sort >>${ATTENTS:-/dev/null}
