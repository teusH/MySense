#!/bin/bash
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
# 
# Copyright (C) 2017, Behoud de Parel, Teus Hagen, the Netherlands
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

# $Id: MakeReports.sh,v 1.17 2017/08/05 19:32:27 teus Exp teus $

# shell file produces pdf correlation report of influx raw series of timed data
# for the dust sensor only pcs/qf is used
# Usage examples:
# START=2017-06-01 END=now command dust BdP_12345=sds011,dylos,bme280 BdP_12346=ppd42ns,pms7003,dht22 ...
# START=2017-06-01 END=now command temp BdP_12345=sds011,dylos,bme280 BdP_12346=ppd42ns,pms7003,dht22 ...
# START=2017-06-01 END=now command pm25 BdP_12345=sds011,dylos,bme280 BdP_12346=ppd42ns,pms7003,dht22 ...

export LANG=en_GB.UTF-8
STRT=${START:-2017-07-30}
END=${END:-2017-08-04}
INTERVAL=900
MTYPE=raw
FIELD=time

REPORTS=reports
mkdir -p $REPORTS
rm -f ${REPORTS}/*@*@*{.png,.pdf,.html} # remove all old intermediate reports
OUTPUT=
TOTAL=$REPORTS/CorrelationReport_$(date '+%Y-%m-%dT%H:%M').html
CONTENT=$REPORTS/CorrelationReportContent_$(date '+%Y-%m-%dT%H:%M').html
# get this html to pdf converter from http://wkhtmltopdf.org
HTML2PDF=/usr/local/wkhtmltox/bin/wkhtmltopdf

HTML=${HTML:---HTML}

DBHOST=${DBHOST:-localhost}
DBUSER=${DBUSER:-$USER}
DBPASS=${DBPASS:-XXX}

declare -i CNT=0

if [ $DBPASS = XXX ]
then
    read "Give InFluxDB server $DBUSER password: " DBPASS
fi

# header of HTML document
function InitReport() {
    local OUT=$1
    if [ -z "$OUT" ] ; then OUT=/dev/stdout ; fi
    cat >"$OUT" <<EOF
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html>
<head>
        <meta http-equiv="content-type" content="text/html; charset=utf-8"/>
        <title></title>
        <meta name="generator" content="MySense report generator"/>
        <meta name="created" content="$(date --rfc-3339=date)"/>
        <meta name="changedby" content="$USER"/>
        <meta name="changed" content="$(date --rfc-3339=seconds)"/>
        <style type="text/css">
                p { font-size: 10pt }
                td { font-size: 9; border: none; padding: 0cm }
                h2.cjk { font-family: "Droid Sans Fallback" }
                h2.ctl { font-family: "FreeSans" }
                h3.cjk { font-family: "Droid Sans Fallback" }
                h3.ctl { font-family: "FreeSans" }
                th { font-size: 9; border: none; padding: 0cm }
                img { align="right" width="221" border="0" }
        </style>
</head>
<body lang="nl-NL" dir="ltr">
EOF
}

# bottom of html document
function CloseReport(){
    local OUT=$1
    if [ -z "$OUT" ] ; then OUT=/dev/stdout ; fi
    cat >>"$OUT" <<EOF
</body></html>
EOF
}

PDF_FILES=()
function CombineReport() {
    local OUT=$1 OUTPUT=$2 ERR=$3 TITLE=$4
    local OPT=${4/* */--title}
    if [ -z "$OUT" ] ; then OUT=/dev/stdout ; fi
    if [ -n "$OUTPUT" ] && [ -n "$OUT" ] && [ -f "$OUTPUT" ]
    then
        # show errors if present
        if [ -f "$ERR" ]
        then
            sed -i '/Axes that are not/d' /var/tmp/ERR$$
            if [ -s /var/tmp/ERR$$ ]
            then
                echo "Encountered some errors: " >/dev/stderr
                cat /var/tmp/ERR$$ >/dev/stderr
                echo "ERROR: skip this in reports" >/dev/stderr
                rm -f /var/tmp/ERR$$ "$OUTPUT"
                return 1
            fi
            rm -f /var/tmp/ERR$$
        fi

        # add output tot combined html report
        if [ ! -f "$OUT" ]
        then InitReport "$OUT"
        elif [ -n "$OUT" ] && [ -f "$OUT" ]
        then  sed -i "/<.body><.html>/d" "$OUT"
        fi
        cat "$OUTPUT" >>"$OUT"                          # combine all to html
        CloseReport "$OUT"

        InitReport "${OUTPUT/.xml/.html}"               # one page report in html
        cat "$OUTPUT" >>"${OUTPUT/.xml/.html}"
        CloseReport "${OUTPUT/.xml/.html}"
        echo "Created ${OUTPUT/.xml/.html}" >/dev/stderr

        # convert html page to pdf
        if [ -x $HTML2PDF ]
        then
            # convert html to pdf
            if $HTML2PDF ${OPT} "${TITLE}"  "${OUTPUT/.xml/.html}" "${OUTPUT/.xml/.pdf}" 2>/dev/null
            then
                PDF_FILES+=(${OUTPUT/.xml/.pdf})
            fi
        fi
        rm -f "$OUTPUT"
        return 0
    fi
    return 1
}

# give R-squared number a text color
function R_squared(){
    perl -e '
        while(<STDIN>){
            if ( /R-sq.*(0\.[0-9]+)/ ) {
                $b = $1; $color="Green";
                if ( $b < 0.1 ) {
                    $color="red"; }
                elsif ( $b < 0.2 ) {
                    $color="DarkRed" ; }
                elsif ( $b < 0.35 ) {
                    $color="GoldenRod" ; }
                elsif ( $b < 0.5 ) {
                    $color="DarkOrange" ; }
                elsif ( $b < 0.7 ) {
                    $color="DarkGrey" ; }
                elsif ( $b < 0.85 ) {
                    $color="DarkOliveGreen" ; }
                elsif ( $b < 0.95 ) {
                    $color="DarkGreen" ; }
                $b=sprintf("<div style=\"color: %s;\">%.4f</div>\n",$color,$b);
                s/0\.[0-9]+/$b/;
            }
            print;
        }
    '
}

LAST_SENSE=XXX  # remind last measurement type
declare -i SUM_CNT=0       # only 5 summaries on one page
SUM_HTML=()
function ExtractKeyValues(){
    local SENSE=${1^^} KIT1=$2 TYPE1=${3^^} KIT2=$4 TYPE2=${5^^} INPUT=$6 OUTPUT=$7
    if [ "$1" = pm25 ] ; then SENSE=PM2.5 ; fi
    declare -i HereCnt=$CNT
    if ((CNT >= 8)) ; then HereCnt+=1 ; fi
    if (( (HereCnt % 8) == 1 ))
    then
        SUM_CNT+=1
        OUTPUT="${OUTPUT/\//\/$SUM_CNT-}"
        SUM_HTML+=("$OUTPUT")
        InitReport "$OUTPUT"
        if ((SUM_CNT == 1))
        then
            cat >"$OUTPUT" <<EOF
        <h2>Summary of correlations of sensor kits and sensor modules</h2>
        Sensorkits: ${ARG_KITS[*]/#_/ ID=}<br />
        Report generated on: $(date)
        <h3>R-square and statistical summary</h3>
EOF
        fi
    else
        OUTPUT=${OUTPUT/\//\/$SUM_CNT-}
        sed -i '/<.body><.html>/d' "$OUTPUT"
    fi
    if [ "$LAST_SENSE" != "$SENSE" ]
    then
        LAST_SENSE="$SENSE"
        echo "<h4>Measurement <b>$SENSE</b> correlation key values</h4>" >>"$OUTPUT"
    fi
    echo "<p><div style='font-size: 10pt;'>Correlation ${CNT} - <b>${SENSE}</b> - kit ${KIT1} sensor type <b>${TYPE1}</b> with kit ${KIT2} sensor type <b>${TYPE2}</b>:</div>" >>"$OUTPUT"
    echo "<table noborder cellspacing=0 cellpadding=4>" >>"$OUTPUT"
    local IMG=${INPUT/Report/IMG}
    local HEIGHT=112
    # seems graph for these are height is less
    if echo "${TYPE1} ${TYPE2}" | grep -q -e PPD42 -e PMS.003
    then
        HEIGHT=102
    fi
    if [ -f "${IMG/xml/png}" ]
    then
        if file "${IMG/xml/png}" | grep -q '737 x'
        then
            IMG=${IMG/*\//}
            echo "<tr><td rowspan=4 width=184px><div style='width: 174px; height: ${HEIGHT:-112}; border: solid #EEEEEE; overflow: hidden; position: relative;'><img src='${IMG/xml/png}' style='position: absolute; left:-24px; top: -12px; width:210; height:286'/></div></td></tr>" >>"$OUTPUT"
        fi
    fi
    echo "<tr><td valign=top align=left><div style='font-size: 10pt;'>" >>"$OUTPUT"
    local GREP=('number.*min=.*max=' 'avg=.*std dev=' 'R-squared.*with.*:')
    local I
    for (( I=0; I < ${#GREP[*]}; I++))
    do
        echo "<br />" >>"$OUTPUT"
        grep "${GREP[$I]}" ${INPUT/.xml/.html} | sed -e 's/(R.*) //' -e 's/pm25/pm2.5/' -e 's/pm/PM/' -e '/ with .*:/s%.*%<b>&</b>%' -e 's/ with .*:/:/' -e 's/number/nr samples/' | R_squared >>"$OUTPUT"
    done
    # pick up the best fit polynomial coefficients
    local COEFF=''
    COEFF=$(grep -P '^[\- 0-9\.e,+\t]+$' ${INPUT/.xml/.html})
    if [ -n "$COEFF" ]
    then
        echo "<br />Best fit polynomial coefficients:<br />&nbsp;&nbsp;[${COEFF}]" >>"$OUTPUT"
    fi
    echo "</div></td></tr></table></p>" >>"$OUTPUT"
    CloseReport "$OUTPUT"
}
 
function CreateReport(){
    local SENSE=$1 KIT1=$2 TYPE1=$3 KIT2=$4 TYPE2=$5
    echo "Creating report for measurement $SENSE: kit(${KIT1}),type(${TYPE1}) with kit(${KIT2}),type(${TYPE2})" >/dev/stderr
    local NAME="$REPORTS/CorrelationReport_$SENSE-${TYPE1}@${KIT1}_with_${TYPE2}@${KIT2}"
    cat >$NAME <<EOF
<h2>Sensor ${TYPE1}@${KIT1} with<br />sensor ${TYPE2}@${KIT2}<br /><div align=right>correlation report for $SENSE (${MTYPE}) measurements</div></h2>
<p>Correlation details of project ${KIT1/_*/} sensor kit ID ${KIT1/*_/} with project ${KIT2/_*/} sensor kit ID ${KIT2/*_/}<br />
Date of correlation report: $(date)<br />
From date $STRT upto $(date --date="$END" "+%Y-%m-%d %H:%M")<br />
Origin of measurement time serie data from InFluxDB host: ${DBHOST}<br />
Report generated by MyRegression.py (GPL V4) (user $DBUSER)
</p>
<h3>General statistical information for the measurements graphs</h3>
<p>
EOF
    echo "$NAME"
    return 0
}

echo "Expect warnings about Axis fit for the graphs." >/dev/stderr

KIT1=BdP_8d5ba45f       # 192.168.178.49 IoS2 Pi3
KIT2=BdP_3f18c330       # 192.168.176.42 IoS3 Pi3
KIT3=BdP_33040d54       # 192.168.176.52 IoS1 Pi2
KIT4=BdP_f46d04af97ab   # 192.168.176.51 lunar desktop

declare -A SENSOR
# convert sensor type name to db identifier
SENSOR[dylos,pm25]=pm25
SENSOR[dylos,pm10]=pm10
SENSOR[ppd42ns,pm25]=pm25_pcsqf
SENSOR[ppd42ns,pm10]=pm10_pcsqf
SENSOR[sds011,pm25]=pm25
SENSOR[sds011,pm10]=pm10
SENSOR[pms7003,pm25]=pm25_atm
SENSOR[pms7003,pm10]=pm10_atm
SENSOR[dht22,temp]=temp
SENSOR[bme280,temp]=temp
SENSOR[dht22,rh]=rh
SENSOR[bme280,rh]=rh
SENSOR[bme280,pha]=pha
declare -a DUST=(dylos sds011 pms7003 ppd42ns)
declare -a DUST_TYPE=(pm1 pm25 pm10)
declare -a CLIMATE=(dht22 bme280)
declare -a CLIMATE_TYPE=(temp rh pha)
declare -A CONFIG
declare -a KITS

SENSES=""
if [ -z "$1" ] || [ -z "${1/*help*/}" ]
then
    cat >/dev/stderr <<EOF
Usage: $0 type ... where type is dust or climate
    or type is proj_sensorID=sensor_type list
        where sensor_type list is eg dylos,sds011,dht22,bme280,pms7003,ppd42ns
EOF
    exit 0
else
    for arg
    do
        case $arg in
        dust)
            ARGS+=" pm10 pm25"
        ;;
        climate)
            ARGS+=" temp rh pha"
        ;;
        pm1|pm25|pm10|temp|rh|pha)
            ARGS+=" $arg"
        ;;
        *=*)
            CONFIG[${arg/=*/}]=$( echo "${arg/*=/}" | sed 's/,/ /g')
            ARG_KITS+="${arg/=*/}"
        ;;
        *)
            echo "$arg Unknown sensing element type: use dust and/or climate"
            exit 1
        esac
    done
fi

if [ ${#ARG_KITS[*]} -le 0 ] # default for BdP
then
    CONFIG[BdP_8d5ba45f]="dylos dht22 bme280 sound gps"
    CONFIG[BdP_3f18c330]="sds011 ppd42ns dht22 bme280 gps"
    CONFIG[BdP_33040d54]="sds011 ppd42ns pms7003"
    # ordered list
    ARG_KITS=(BdP_8d5ba45f BdP_3f18c330 BdP_33040d54)
fi

HTML_REPORTS=() # list of generated correlation reports HTML format
for SENSE in $ARGS
do
    if ! echo " ${DUST_TYPE[*]} ${CLIMATE_TYPE[*]} " | grep -q " $SENSE "
    then
        echo "Skipping $SENSE, not in supported sensor element list"
        continue
    fi
    KITS=() ; SENSES=() ; TYPES=()
    for kit in ${ARG_KITS[*]}
    # ordered list sensor kits, sensor types, measurement ID
    do
        for Type in ${CONFIG[$kit]}
        do
            if [ -n "${SENSOR[$Type,$SENSE]}" ]
            then
                KITS+=($kit)                            # database sensorkit
                TYPES+=($Type)                          # sensor module type
                SENSES+=(${SENSOR[$Type,$SENSE]})       # serie measurement name
            fi
        done
    done
    for (( I=0; I < ${#KITS[*]}; I++))
    do
        for ((J=$I+1; J < ${#KITS[*]}; J++))
        do
            OUTPUT=$(CreateReport "$SENSE" "${KITS[$I]}" "${TYPES[$I]}" "${KITS[$J]}" "${TYPES[$J]}")
            echo "Using measurement for type ${TYPES[$I]}: ${SENSES[$I]} and for type ${TYPES[$J]}: ${SENSES[$J]}" >/dev/stderr
            if [ -n "$HTML" ]
            then
                PNG="--file ${OUTPUT/Report/IMG}.png"
                OUTPUT+=.xml
                mv "${OUTPUT/.xml/}" "$OUTPUT"
            else
                PNG=''
            fi
            python MyRegression.py -T influx $HTML  $PNG -t $STRT/$END -i $INTERVAL \
                ${KITS[$I]}/${SENSES[$I]}/${FIELD}/${TYPES[$I]}/${MTYPE} \
                ${KITS[$J]}/${SENSES[$J]}/${FIELD}/${TYPES[$J]}/${MTYPE} \
                2>>/var/tmp/ERR$$ >>"$OUTPUT"
            if ! CombineReport "$TOTAL" "$OUTPUT" /var/tmp/ERR$$ "Correlation Report for Measurement $SENSE from sensors ${TYPES[$I]} and ${TYPES[$J]}"
            then
                echo "ERRORS in correlation: report is skipped" >/dev/stderr
            else
                CNT+=1
                ExtractKeyValues "$SENSE" "${KITS[$I]}" "${TYPES[$I]}" "${KITS[$J]}" "${TYPES[$J]}" "${OUTPUT}" "${CONTENT}"               
                HTML_REPORTS+=("${OUTPUT/.xml/.html}")
            fi
        done
    done
done

if [ $CNT -le 0 ]
then
    echo "Did not find any kits (${KITS[*]}) with sensor type $ARGS"
    exit 1
fi

if [ -f "$TOTAL" ] && [ -x $HTML2PDF ]
then
    TT=''
    for T in $(for S in ${TYPES[*]} ; do echo ${S^^} ; done | sort | uniq)
    do
        if [ -z "$TT" ]
        then
            TT="$T"
        else
            TT+=", $T"
        fi
    done 
    TITLE="MySense ${KITS[0]/_*/} Correlation Reports for: [$( echo "$ARGS" | sed -e 's/pm/PM/g' -e 's/PM25/PM2.5/' -e 's/PM1 /PM0.1 /' -e 's/PM3/PM0.3/')], sensors: ${TT}"
    if (( ${#HTML_REPORTS[*]} > 1 ))
    then
        # convert html summary and correlation pages to pdf
        if $HTML2PDF --title "Summary for $TITLE" ${SUM_HTML[*]} "${CONTENT/.html/.pdf}" 2>/dev/null
        then
            echo "Generated summary report ${CONTENT/.html/.pdf} with ${#SUM_HTML[*]} summary entries" >/dev/stderr
            # make it git ready
            if [ -d ../MySense/statistics ]
            then
                cp ${CONTENT/.html/.pdf} ../MySense/statistics/$(basename ${CONTENT/-??T*/.pdf})
            fi
        fi
    else
        CONTENT=''
    fi
    #if [ -n "$PDF_FILES" ] && which pdftk >/dev/null
    #then
    #    pdftk $PDF_FILES cat output "${TOTAL/.html/.pdf}"
    #    echo "Correlation report in PDF format is in ${TOTAL/.html/.pdf}" >/dev/stderr
    #fi
    if $HTML2PDF --title "$TITLE" --footer-left "MySense correlation report, project ${KITS[0]/_*/}, [date]" --footer-right "page [page]/[topage]"  toc ${SUM_HTML[*]} ${HTML_REPORTS[*]/.pdf/.html} ${TOTAL/.html/.pdf}
    then
        echo "Combined HTML correlation reports are in ${TOTAL/.html/.pdf}" >/dev/stderr
        # make it git ready
        if [ -d ../MySense/statistics/ ]
        then
            cp ${TOTAL/.html/.pdf} ../MySense/statistics/$(basename ${TOTAL/-??T*/.pdf})
        fi
        rm -f ${SUM_HTML[*]} ${HTML_REPORTS[*]}
    else
        echo "Failure: to generate $CNT correlation reports to $TOTAL" >/dev/stderr
    fi
    
fi

