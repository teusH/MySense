KIT1=BdP_8d5ba45f
KIT2=BdP_3f18c330
KIT3=BdP_33040d54
KIT4=BdP_f46d04af97ab
STRT=2017-06-19
END=2017-06-27
INTERVAL=900
REPORTS=./reports
OUTPUT=
TOTAL=$REPORTS/CorrelationReport_$(date '+%Y-%m-%dT%H:%M').html
HTML=${HTML:---HTML}
DBHOST=${DBHOST:-localhost}
DBUSER=${DBUSER:-$USER}
DBPASS=${DBPASS:-XXX}

if [ $DBPASS = XXX ]
then
    read "Give InFluxDB server $DBUSER password: " DBPASS
fi

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

function CloseReport(){
    local OUT=$1
    if [ -z "$OUT" ] ; then OUT=/dev/stdout ; fi
    cat >>"$OUT" <<EOF
</body></html>
EOF
}

PDF_FILES=''
function CombineReport() {
    local OUT=$1
    if [ -z "$OUT" ] ; then OUT=/dev/stdout ; fi
    if [ -n "$OUTPUT" ] && [ -n "$OUT" ] && [ -f "$OUTPUT" ]
    then
        cat "$OUTPUT" >>"$OUT"                          # combine all to html

        InitReport "${OUTPUT/.xml/.html}"               # one page report in html
        cat "$OUTPUT" >>"${OUTPUT/.xml/.html}"
        CloseReport "${OUTPUT/.xml/.html}"
        echo "Created ${OUTPUT/.xml/.html}" >/dev/stderr
        rm -f "$OUTPUT"

        if which wkhtmltopdf >/dev/null
        then
            # convert html to pdf
            if wkhtmltopdf "${OUTPUT/.xml/.html}" "${OUTPUT/.xml/.pdf}" 2>/dev/null
            then
                PDF_FILES+=" ${OUTPUT/.xml/.pdf}"
            fi
        fi
        # show errors if present
        sed -i '/Axes that are not/d' /var/tmp/ERR$$
        if [ -s /var/tmp/ERR$$ ]
        then
            echo "Encountered some errors: " >/dev/stderr
            cat /var/tmp/ERR$$ >/dev/stderr
        fi
        rm -f /var/tmp/ERR$$
    fi
}

function CreateReport(){
    local SENSE=$1 SENSOR1=$2 SENSOR2=$3
    CombineReport "$TOTAL"
    OUTPUT="$REPORTS/CorrelationReport_$SENSE-${SENSOR1}_with_$SENSOR2.xml"
    if [ -n "$HTML" ]
    then
        PNG="--file $REPORTS/CorrelationIMG_$SENSE-${SENSOR1}_with_$SENSOR2.png"
    else
        PNG=''
    fi
    local MEND=$END
    if [ $MEND = now ] ; then MEND=$(date) ; fi
    cat >$OUTPUT <<EOF
<h2>Correlation report for sensing $SENSE:<br /><div align=right>sensor type $SENSOR1 with $SENSOR2</div></h2>
<p>Date of calculation: $(date)<br>From date $STRT upto $MEND</br></p>
<h3>General information for the graphs</h3>
<p>
EOF
}

echo "Expect warnings about Axis fit for the graphs." >/dev/stderr
InitReport "$TOTAL"      # init TOTAL output HTML file

# PM10 PM2.5
for SENSE in pm10 pm25
do
    SENSOR1=dylos
    SENSOR2=sds011
    CreateReport  $SENSE $SENSOR1 $SENSOR2
    python MyRegression.py -T influx $HTML  $PNG -t $STRT/$END -i $INTERVAL $KIT1/${SENSE}/time/$SENSOR1/raw $KIT2/${SENSE}/time/$SENSOR2/raw 2>>/var/tmp/ERR$$ >>$OUTPUT
    CreateReport  $SENSE $SENSOR1 $SENSOR2
    python MyRegression.py -T influx $HTML  $PNG -t $STRT/$END -i $INTERVAL $KIT4/${SENSE}/time/$SENSOR2/raw $KIT2/${SENSE}/time/$SENSOR2/raw 2>>/var/tmp/ERR$$ >>$OUTPUT
    SENSOR1=ppd42ns
    CreateReport  $SENSE $SENSOR1 $SENSOR2
    python MyRegression.py -T influx $HTML  $PNG -t $STRT/$END -i $INTERVAL $KIT2/${SENSE}_pcsqf/time/$SENSOR1/raw $KIT3/${SENSE}_pcsqf/time/$SENSOR1/raw 2>>/var/tmp/ERR$$ >>$OUTPUT
    SENSOR2=sds011
    CreateReport  $SENSE $SENSOR1 $SENSOR2
    python MyRegression.py -T influx $HTML  $PNG -t $STRT/$END -i $INTERVAL $KIT2/${SENSE}/time/$SENSOR2/raw $KIT2/${SENSE}_pcsqf/time/$SENSOR1/raw 2>>/var/tmp/ERR$$ >>$OUTPUT
done


# temperature rel humidity
SENSOR1=bme280
SENSOR2=dht22
for SENSE in temp rh pha
do
    CreateReport  $SENSE $SENSOR1 $SENSOR1
    python MyRegression.py -T influx $HTML  $PNG -t $STRT/$END -i $INTERVAL $KIT1/${SENSE}/time/$SENSOR1/raw $KIT2/${SENSE}/time/$SENSOR1/raw 2>>/var/tmp/ERR$$ >>$OUTPUT
    if [ $SENSE != pha ]
    then
        CreateReport  $SENSE $SENSOR1 $SENSOR2
        python MyRegression.py -T influx $HTML  $PNG -t $STRT/$END -i $INTERVAL $KIT1/${SENSE}/time/$SENSOR1/raw $KIT1/${SENSE}/time/$SENSOR2/raw 2>>/var/tmp/ERR$$ >>$OUTPUT
        CreateReport  $SENSE $SENSOR2 $SENSOR2
        python MyRegression.py -T influx $HTML  $PNG -t $STRT/$END -i $INTERVAL $KIT1/${SENSE}/time/$SENSOR1/raw $KIT2/${SENSE}/time/$SENSOR1/raw 2>>/var/tmp/ERR$$ >>$OUTPUT
    fi
done

if [ -n "$OUTPUT" ] && [ -n "$TOTAL" ] && [ -f "$OUTPUT" ]
then
    CombineReport "$TOTAL"
    CloseReport "$TOTAL"
    echo "Combined HTML report is in $TOTAL" >/dev/stderr
    if [ -n "$PDF_FILES" ] && which pdftk >/dev/null
    then
        pdftk $PDF_FILES cat output "${TOTAL/.html/.pdf}"
        echo "Combined PDF report is in ${TOTAL/.html/.pdf}" >/dev/stderr
    fi
fi

