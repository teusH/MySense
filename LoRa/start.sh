#! /bin/bash
# reset LoRa board, complete local_conf.json if needed with GPS end GW ID

INSTALL_DIR=/opt/ttn-gateway
LOCAL_CONFIG_FILE=$INSTALL_DIR/bin/local_conf.json
OPTIONS=
NODISPLAY=
for ARG
do
    case "$ARG" in
    -t|-q|-v)
	OPTIONS+=" $ARG"
    ;;
    -n|nodisplay)
	NODISPLAY=True
    esac
done

# messages on oled display or just print it
function display() {
    if [ -x /bin/nc ]
    then
        if ! echo "$*" | /bin/nc -w 2 localhost 2017
        then echo "$*"
        fi
    fi
}

function GW_reset() {
    display "Reset gateway"
    # Reset iC880a PIN
    #SX1301_RESET_BCM_PIN=25
    SX1301_RESET_BCM_PIN=22	# changed by teus 14-10-2018
    echo "$SX1301_RESET_BCM_PIN"  > /sys/class/gpio/export 
    echo "out" > /sys/class/gpio/gpio$SX1301_RESET_BCM_PIN/direction 
    echo "0"   > /sys/class/gpio/gpio$SX1301_RESET_BCM_PIN/value 
    sleep 0.1  
    echo "1"   > /sys/class/gpio/gpio$SX1301_RESET_BCM_PIN/value 
    sleep 0.1  
    echo "0"   > /sys/class/gpio/gpio$SX1301_RESET_BCM_PIN/value
    sleep 0.1
    echo "$SX1301_RESET_BCM_PIN"  > /sys/class/gpio/unexport 
    display 'reset iC880A-spi'
}

function Wait4Internet() {
    # Test the connection, wait if needed.
    declare -i count=0
    while [[ $(ping -c1 google.com 2>&1 | grep " 0% packet loss") == "" ]]; do
      if ((count >= 20))
      then
         display '<clear>ERROR no internet'
         exit 1
      fi
      echo "[TTN Gateway]: Waiting for internet connection..."
      display 'WAIT for internet'
      sleep 30
      count+=1
    done
    return 1
}

function item() {
    if [ -z "$1" ] ; then return 1 ; fi
    echo "$1" | grep -e "$2" | sed -e 's/".*://' -e 's/[^0-9\.]//g'
}

function getGPS() {
    local GPS=''
    GPS=$(/usr/bin/gpspipe -w -n 100 | /bin/grep -v 1970-01 | /bin/grep -m 1 lat | /bin/sed -e 's/lon"/long"/' -e 's/,/,\n/g' )
    if [ -z "$GPS" ] ; then GPS=0 ; fi
    echo "$GPS"
}

export -f getGPS

# adjust GPS location if GPS module is installed
function location() {
    local coord
    local CONF="${1:-/opt/ttn-gateway/bin/local_conf.json}"
    if grep -q "gps_tty_path.*dev/tty" "$CONF" && grep -q "fake_gps.*false" "$CONF"
    then
        display 'using FRWDR GPS'
        return 0 # no GPS config needed
    fi
    display "Get GW GPS updated"
    if [ ! -x /usr/bin/gpspipe ] ; then return 1 ; fi # GPS daemon not installed
    if ! /bin/systemctl status gpsd | grep -q '(running)' ; then return 1 ; fi # no daemon running
    source /etc/default/gpsd
    local FND=""
    for DEV in $DEVICES
    do
       if [ -c $DEV ]; then FND=1; break ; fi
    done
    if [  -z "$FND" ] ; then return 1 ; fi # gps is waiting on device
    #local GPS=$(/usr/bin/gpspipe -w -n 100 | /bin/grep -v 1970-01 | /bin/grep -m 1 lat | /bin/sed -e 's/lon"/long"/' -e 's/,/,\n/g' )
    local GPS=$(timeout 90 bash -c getGPS)
    if [ -z "$GPS" ]
    then
        display 'GPS is blocked'
        return 1
    elif [ "$GPS" = 0 ]
    then
        return 2
    else
      # echo "$GPS" | /bin/grep -e 'long"' -e 'alt"' -e 'lat"' | /bin/sed -e 's/"/\t\t"ref_/' -e 's/":/itude":/'
      for co in lat long alt
      do
        coord=$(item "$GPS" "$co")
        if [ -n "$coord" ]
        then
	    /bin/sed -i "/ref_${co}itude\":/s/:\s*[0-9\.]*/: $coord/" "${1:-/opt/ttn-gateway/bin/local_conf.json}"
	    display "$co: $coord"
        fi
      done
    fi
    return 0
}

# edit Gaterway ID in local_conf.json
iot_update_gwid() {
    # get gateway ID from its MAC address to generate an EUI-64 address
    # gives essential Pi serial nr (mac address) for eth0
    
    # semtech legacy
    local GWID_BEGIN="eui_"
    local GW_EUI=$(/bin/grep '"gateway_ID":' $1 | /bin/sed 's/.*ID":.*"\(.*\)".*/\1/')
    if [ -z "$GW_EUI" ]
    then
        local NIC
	for NIC in eth0 wlan0
        do
            if /bin/grep -q $NIC /proc/net/dev ; then break ; else NIC='' ; fi
        done
        if [ -z "$NIC" ] ; then display "ERROR no NIC" ; exit 1 ; fi
        GW_EUI=$(/sbin/ip link show $NIC | /usr/bin/awk '/ether/ {print $2}' | awk -F\: '{print $1$2$3 "FFFE" $4$5$6 }')

        # replace last 8 digits of default gateway ID by actual GWID
        # in given JSON configuration file
        /bin/sed -i '/gateway_ID/s/.*/                "gateway_ID": "'${GW_EUI^^}'",/' $1
    fi
    # echo "Gateway_ID set to Semtech legacy "${GWID_BEGIN}$GWID_EUI" in file "$1
    display "<clear>Gateway ID:"
    display "SemTech legacy"
    display "${GWID_BEGIN}${GW_EUI,,}"
}

display "<clear>Starting TTN Gway"
# If there's a remote config, try to update it
if [ -d ../gateway-remote-config ]; then
    display "Remote config update"
    # First pull from the repo
    pushd ../gateway-remote-config/
    git pull
    git reset --hard
    popd

    # And then try to refresh the gateway EUI and re-link local_conf.json

    # Same network interface name detection as on install.sh
    # Get first non-loopback network device that is currently connected
    GATEWAY_EUI_NIC=$(ip -oneline link show up 2>&1 | grep -v LOOPBACK | sed -E 's/^[0-9]+: ([0-9a-z]+): .*/\1/' | head -1)
    if [[ -z $GATEWAY_EUI_NIC ]]; then
      echo "ERROR: No network interface found. Cannot set gateway ID."
      exit 1
    fi

    # Then get EUI based on the MAC address of that device
    GATEWAY_EUI=$(cat /sys/class/net/$GATEWAY_EUI_NIC/address | awk -F\: '{print $1$2$3"FFFE"$4$5$6}')
    GATEWAY_EUI=${GATEWAY_EUI^^} # toupper

    echo "[TTN Gateway]: Use Gateway EUI $GATEWAY_EUI based on $GATEWAY_EUI_NIC"
    INSTALL_DIR="/opt/ttn-gateway"
    LOCAL_CONFIG_FILE=$INSTALL_DIR/bin/local_conf.json

    if [ -e $LOCAL_CONFIG_FILE ]; then rm $LOCAL_CONFIG_FILE; fi;
    ln -s $INSTALL_DIR/gateway-remote-config/$GATEWAY_EUI.json $LOCAL_CONFIG_FILE

else
    iot_update_gwid $LOCAL_CONFIG_FILE
    for (( I=0; I < 5; I++))
    do
      if location $LOCAL_CONFIG_FILE ; then break ; fi
      location $LOCAL_CONFIG_FILE
      case $? in
      0) break  # success conf updated
      ;;
      1) break  # tty GPS locked
      ;;
      esac
      display 'Wait for fixate'
      sleep 120
      display 'GPS try again'
    done
fi

if [ "$1"x = resetx ]
then
    GW_reset
    exit 0
elif [ "$1"x = configure ]
then
    location $LOCAL_CONFIG_FILE
    exit 0
fi

display '<clear>LoRa gateway'
sleep 30
Wait4Internet
for INT in eth0 wlan0
do
    ADDR=$(/sbin/ifconfig $INT | /bin/sed s/addr:// | /usr/bin/awk '/inet.*cast/{printf("%s",$2); }')
    if [ -n "$ADDR" ]
    then
        display "<clear>$INT $ADDR"
        break
    fi
done
# Fire up the forwarder.
for NR in first second third fourth fifth
do
    display "LoRa FWDR startup\nstarted $NR time"
    GW_reset
    if [ -x /usr/local/bin/GatewayLogDisplay.py ] && [ -z "$NODISPLAY" ]
    then
	${INSTALL_DIR:-/opt/ttn-gateway}/bin/poly_pkt_fwd | /usr/local/bin/GatewayLogDisplay.py $OPTIONS
    elif [ -n "$NODISPLAY" ]
    then
	${INSTALL_DIR:-/opt/ttn-gateway}/bin/poly_pkt_fwd | grep -e ERROR -e main
    else
	${INSTALL_DIR:-/opt/ttn-gateway}/bin/poly_pkt_fwd
    fi
    if [ $? -le 0 ] ; then break ; fi
    if /bin/systemctl status gpsd | grep -q '(running)'
    then # gpsd may block gpsd serial, a ctl restart did fail
	/bin/systemctl stop gpsd ; sleep 5
	/bin/systemctl start gpsd ; sleep 5
	if [ -x /usr/bin/gpspipe ]
	then # and get it run serial
	    /usr/bin/gpspipe -w -n 2 >/dev/null
	fi
    fi
    # seems concentrator board sometimes does not start but can be restarted
done
display "LoRa Forwarder stopped"
