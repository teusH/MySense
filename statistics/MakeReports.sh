KIT4=BdP_f46d04af97ab
KIT1=BdP_8d5ba45f
KIT2=BdP_3f18c330
KIT3=BdP_33040d54
STRT=2017-06-20
END=now
INTERVAL=$INTERVAL
REPORTS=./reports
OUTPUT=

function CreateReport(){
    local SENSE=$1 SENSOR1=$2 SENSOR2=$3
    OUTPUT="$REPORTS/CorrelationReport_$SENSE-$SENSOR1_with_$SENSOR2.html"
    PNG="--file $REPORTS/CorrelationIMG_$SENSE-$SENSOR1_with_$SENSOR2.png"
    local MEND=$END
    if [ $MEND = now ] ; then MEND=$(date) ; fi
    cat >$NAME <<EOF
<h2>Correlation report for sensing $SENSE: senor type $SENSOR1 with $SENSOR2</h2>
<p>Date of calculation$(date)<br>From date $STRT upto $MEND</br></p>
<h3>General information for the graphs</h3>
<p>
EOF
}

# PM10 PM2.5
for SENSE in pm10 pm25
do
    SENSOR1=Dylos
    SENSOR2=sds011
    OUTPUT=/dev/stdout ; PNG=''
    CreateReport  $SENSE $SENSOR1 $SENSOR2
    python MyRegression.py -T influx $PNG -t $STRT/$END -i $INTERVAL $KIT1/${SENSE}/time/$SENSOR1/time/raw $KIT2/${SENSE}/time/$SENSOR2/raw >>$OUTPUT
    OUTPUT=/dev/stdout ; PNG=''
    CreateReport  $SENSE $SENSOR1 $SENSOR2
    python MyRegression.py -T influx $PNG -t $STRT/$END -i $INTERVAL $KIT4/${SENSE}/time/$SENSOR2/time/raw $KIT2/${SENSE}/time/$SENSOR2/raw >>$OUTPUT
    OUTPUT=/dev/stdout ; PNG=''
    SENSOR1=PPD42NS
    CreateReport  $SENSE $SENSOR1 $SENSOR2
    python MyRegression.py -T influx $PNG -t $STRT/$END -i $INTERVAL $KIT2/${SENSE}_pcsqf/time/$SENSOR1/time/raw $KIT3/${SENSE}_pcsqf/time/$SENSOR1/raw >>$OUTPUT
    OUTPUT=/dev/stdout ; PNG=''
    SENSOR2=sds011
    CreateReport  $SENSE $SENSOR1 $SENSOR2
    python MyRegression.py -T influx $PNG -t $STRT/$END -i $INTERVAL $KIT2/${SENSE}/time/$SENSOR2/time/raw $KIT2/${SENSE}_pcsqf/time/$SENSOR1/raw >>$OUTPUT
done

# temperature rel humidity
SENSOR1=BME280
SENSOR2=DHT22
for SENSE in temp rh pha
do
    if [ $SENSE != pha ]
    then
        OUTPUT=/dev/stdout ; PNG=''
        CreateReport  $SENSE $SENSOR1 $SENSOR2
        python MyRegression.py -T influx $PNG -t $STRT/$END -i $INTERVAL $KIT1/${SENSE}/time/$SENSOR1/time/raw $KIT2/${SENSE}/time/$SENSOR1/raw >>$OUTPUT
    fi
    OUTPUT=/dev/stdout ; PNG=''
    CreateReport  $SENSE $SENSOR1 $SENSOR2
    python MyRegression.py -T influx $PNG -t $STRT/$END -i $INTERVAL $KIT1/${SENSE}/time/$SENSOR2/time/raw $KIT2/${SENSE}/time/$SENSOR2/raw >>$OUTPUT
    if [ $SENSE != pha ]
    then
        OUTPUT=/dev/stdout ; PNG=''
        CreateReport  $SENSE $SENSOR1 $SENSOR2
        python MyRegression.py -T influx $PNG -t $STRT/$END -i $INTERVAL $KIT1/${SENSE}/time/$SENSOR1/time/raw $KIT1/${SENSE}/time/$SENSOR2/raw >>$OUTPUT
    fi
done
