KIT4=BdP_f46d04af97ab
KIT1=BdP_8d5ba45f
KIT2=BdP_3f18c330
KIT3=BdP_33040d54
STRT=2017-06-19
END=2017-06-27
INTERVAL=900
REPORTS=./reports
OUTPUT=
TOTAL=$REPORTS/CorrelationReport_$(date '+%Y-%M-%dT%H:%m').html
HTML=${HTML:---HTML}
DBHOST=${DBHOST:-localhost}
DBUSER=${DBUSER:-USER}
DBPASS=${DBPASS:-XXX}

if [ $DBPASS = XXX ]
then
    read "Give InFluxDB server $DBUSER password: " DBPASS
fi

function CreateReport(){
    local SENSE=$1 SENSOR1=$2 SENSOR2=$3
    if [ -n "$OUTPUT" ] && [ -n "$TOTAL" ] && [ -f "$OUTPUT" ]
    then
        cat "$OUTPUT" >>"$TOTAL"
    fi
    OUTPUT="$REPORTS/CorrelationReport_$SENSE-${SENSOR1}_with_$SENSOR2.html"
    if [ -n "$HTML" ]
    then
        PNG="--file $REPORTS/CorrelationIMG_$SENSE-${SENSOR1}_with_$SENSOR2.png"
    else
        PNG=''
    fi
    local MEND=$END
    if [ $MEND = now ] ; then MEND=$(date) ; fi
    echo "Creating $OUTPUT" >/dev/stderr
    cat >$OUTPUT <<EOF
<h2>>Correlation report for sensing $SENSE: sensor type $SENSOR1 with $SENSOR2</h2>
<p>Date of calculation$(date)<br>From date $STRT upto $MEND</br></p>
<h3>General information for the graphs</h3>
<p>
EOF
}

echo "Expect warnings about Axis fit for the graphs." >/dev/stderr

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
    cat "$OUTPUT" >>"$TOTAL"
    echo "Combined report is in $TOTAL" >/dev/stderr
fi

sed -i '/Axes that are not/d' /var/tmp/ERR$$
if [ -s /var/tmp/ERR$$ ]
then
    echo "Encountered some errors: " >/dev/stderr
    cat /var/tmp/ERR$$ >/dev/stderr
fi
rm -f /var/tmp/ERR$$
