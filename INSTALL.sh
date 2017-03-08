#!/bin/bash
# installation of modules needed by MySense.py
#
# $Id: INSTALL.sh,v 1.8 2017/03/08 19:41:27 teus Exp teus $
#

echo "You need to provide your password for root access.
Make sure this user is added at the sudoers list." 1>&2
#set -x

function UPDATE() {
    echo "Updating/upgrading current OS installation and packages?" 1>&2
    read -p "Try to update? [N|y]:" -t 10 READ
    if [ -n "$READ" -a "$READ" = y ]
    then
        /usr/bin/sudo apt-get update
        /usr/bin/sudo apt-get upgrade
        /usr/bin/sudo apt-get dist-upgrade
        /usr/bin/sudo apt-get autoremove
    fi
}

# function to install python modules via download from github.
function git_pip() {
    local PROJ=$1
    local PKG=$2
    local MOD=$1
    if [ -n "$3" ]
    then
        MOD=$3
    fi
    if [ ! -x /usr/bin/pip ]
    then
        if !  /usr/bin/sudo apt-get install python-pip
        then
            echo "Cannot install pip. Exiting." 1>&2
            exit 1
        fi
    fi
    if ! /usr/bin/pip list | grep -q -i "^$MOD"
    then
        echo "Installing $MOD via pip"
        if [ -n "$2" ]
        then
            mkdir src
            /usr/bin/sudo /usr/bin/pip -q install -e "git+https://github.com/${PROJ}#egg=${PKG}"
            if [ -d src ]
            then
                /usr/bin/sudo /bin/chown -R $USER.$USER src/${PKG,,}
            fi
        else
            /usr/bin/sudo /usr/bin/pip -q install "$MOD"
        fi
    fi
    return $?
}

# check and install the package from apt, pip or github
function DEPENDS_ON() {
    case "${1^^}" in
    PYTHON|PIP)
        if ! git_pip "$2" $3 $4
        then
            echo "FAILURE: Unable to install $2 with pip." 1>&2
            return 1
        fi
    ;;
    APT)
        if [ ! -x /usr/bin/apt-get ]
        then
            echo "FATAL: need apt-get to install modules." 1>&2
            exit 1
        fi
        if ! /usr/bin/dpkg --get-selections | grep -q -i "$2"
        then
            echo "Installing $2 via apt"
            if ! /usr/bin/sudo /usr/bin/apt-get -y -q install "${2,,}"
            then
                echo "FAILURE: Unable to install $2 with apt-get" 1>&2
                return 1
            fi
        fi
    ;;
    GIT)
        if ! git_pip "$2" "$3" $4
        then
            echo "FAILURE: Unable to install $2 with pip in git modus." 1>&2
            return 1
        fi
    ;;
    *)
        echo UNKNOWN COMMAND "$1" 1>&2
        exit 1
    ;;
    esac
    return 0
}

INSTALLS=''
declare -A UNINSTALLS
PLUGINS=''

function MYSENSE(){
    return $?
}

PLUGINS+=" MySQL"
function MySQL(){
    DEPENDS_ON apt python-mysql.connector
    # mysql shell client command
    DEPENDS_ON  apt mysql-client
    # DEPENDS_ON apt mysql-navigator # GUI not really needed
    return $?
}

PLUGINS+=" DHT"
UNINSTALLS[DHT]+=' /usr/local/bin/set_gpio_perm.sh'
function DHT(){
    if [ ! -x /usr/local/bin/set_gpio_perm.sh ]
    then
        echo "Create the file eg /usr/local/bin/set_gio_perm.sh with the content:"
        /bin/cat >/tmp/perm.sh <<EOF
#!/bin/sh
# add as super user to crontab -e
# @reboot      /usr/local/bin/set_gpio_perm.sh
chown root:gpio /dev/gpiomem
chmod g+rw /dev/gpiomem
EOF
        chmod +x /tmp/perm.sh
        /usr/bin/sudo mv /tmp/perm.sh /usr/local/bin/set_gpio_perm.sh
        /usr/bin/sudo chown root.root /usr/local/bin/set_gpio_perm.sh
        echo "and add as super user to crontab -e the line line to exec it at reboot"
        echo "@reboot      /usr/local/bin/set_gpio_perm.sh"
        echo "<cntrl>z to wait for this, fg for continue and enter"
        sleep 15
        read -p "Continue?" -t 60 READ
    fi

    local P
    for P in build-essential python-dev python-openssl python-rpi.gpio
    do
        DEPENDS_ON apt $P
    done
    DEPENDS_ON pip adafruit/Adafruit_Python_DHT Adafruit_Python_DHT Adafruit-DHT
    return $?
}

PLUGINS+=" BME280"
function BME280() {
    DEPENDS_ON pip adafruit/Adafruit_Python_GPIO.git Adafruit_Python_GPIO
    if [ ! -f ./Adafruit_Python_BME280.py ]
    then
        git clone https://github.com/adafruit/Adafruit_Python_BME280.git
        /bin/cp ./Adafruit_Python_BME280/Adafruit_BME280.py .
        /bin/rm -rf ./Adafruit_Python_BME280/
    fi
    return $?
}

INSTALLS+=" THREADING"
function THREADING(){
    #DEPENDS_ON pip threading
    return $?
}

PLUGINS+=" DYLOS"
function DYLOS(){
    #DEPENDS_ON pip serial
    return $?
}

PLUGINS+=" GPS"
function GPS(){
    echo "Installing GPS daemon service"
    DEPENDS_ON apt gpsd         # GPS daemon service
    #DEPENDS_ON apt gps-client   # command line GPS client
    DEPENDS_ON apt python-gps   # python client module
    return $?
}

PLUGINS+=" GSPREAD"
function GSPREAD(){
    echo Make sure you have the latest openssl version:
    echo See README.gspread and obtain Google credentials: https://console.developers.google.com/
    DEPENDS_ON pip oauth2client # auth2
    DEPENDS_ON pip gspread      # Google client module
    #   git clone https://github.com/burnash/gspread
    #   cd gspread; python setup.py install
    DEPENDS_ON  apt python-openssl
    return $?
}

PLUGINS+=" MQTTSUB"
function MQTTSUB(){
    #DEPENDS_ON pip paho-mqtt    # mosquitto client modules
    DEPENDS_ON apt python-mosquitto
    return $?
}

PLUGINS+=" MQTTPUB"
function MQTTPUB(){
    #DEPENDS_ON pip paho-mqtt    # mosquitto client modules
    DEPENDS_ON apt python-mosquitto
    return $?
}

EXTRA+=" MQTT"
function MQTT(){
    echo "Installing Moquitto broker"
    echo README.mqtt for authentication provisions
    #DEPENDS_ON apt mqtt
    DEPENDS_ON apt mosquitto
    return $?
}

INSTALLS+=" GROVE"
function GROVE(){
    #if pip list | grep -q smbus ; then return ; fi
    echo "This will install Grove Pi shield dependencies. Can take 10 minutes."
    mkdir -p git
    cd git
    git clone https://github.com/DexterInd/GrovePi
    if [ ! -d GrovePi/Script ]
    then
        echo "FAILED to install GrovePi dependencies. Abort."
        exit 1
    fi
    cd GrovePi/Script
    chmod +x install.sh
    /usr/bin/sudo ./install.sh
    cd ..
    echo "Please reboot and install the Grove shield"
    echo "Run sudo i2cdetect -y To see is GrovePi is detected."
    return
}

INSTALLS+=" USER"
function USER(){
    READ=''
    if [ $(whoami) = ${USER} ]
    then
        echo "if not '${USER}' user owner of installation, provide new name or push <return" 1>&2
        read -p "new name: " -t 15 READ
    fi
    if [ -z "$READ" ] ; then return ; else USER=$READ ;  fi
    if grep -q "$USER" /etc/passwd ; then return ; fi
    echo "Need to do this with root permissions."
    /usr/bin/sudo touch /dev/null
    echo "Adding user  $USER and password"
    /usr/bin/sudo adduser $USER 
    /usr/bin/sudo passwd $USER
    /usr/bin/sudo adduser $USER gpio
    /usr/bin/sudo adduser $USER dialout
    echo "$USER ALL=(ALL) PASSWD: ALL" >/tmp/US$$
    /usr/bin/sudo /bin/cp /tmp/US$$ /etc/sudoers.d/020_${USER}-passwd
    /bin/rm /tmp/US$$
    /usr/bin/sudo chmod 440 /etc/sudoers.d/020_${USER}-passwd
    /usr/bin/sudo update-rc.d ssh enable
    /usr/bin/sudo service ssh restart
}

function RestoreOriginal() {
    local FILE ANS
    for FILE in $@
    do
    if [ -f $FILE ]
    then
        if [ -f $FILE.orig ]
        then
            /usr/bin/sudo /bin/mv -f  $FILE.orig $FILE
	else
	    read -p "Want to keep $FILE? [Ny] " ANS
	    if [ -z "${ANS/[Nn]/}" ]
	    then
		/usr/bin/sudo /bin/rm -f $FILE
	    fi
	fi
    fi
    done
}

EXTRA+=' UNINSTALL'
function UNINSTALL() {
    for F in $UNINSTALLS
    do
	RestoreOriginal "$F"
    done
}

function KeepOriginal() {
    local FILE
    for FILE in $@
    do
    if [ -f $FILE ] && ! [ -f $FILE.orig ]
    then
        /usr/bin/sudo /bin/cp $FILE $FILE.orig
    fi
    done
}

INSTALLS+=" INTERNET"
UNINSTALLS[INTERNET]+=' /etc/network/if-post-up.d/wifi-gateway'
UNINSTALLS[INTERNET]+=' /etc/network/if-up.d/wifi-internet'
UNINSTALLS[INTERNET]+=' /etc/network/interfaces'
## wired line eth0 switch to wifi on reboot
# will bring up internet access via eth0 (high priority) or wifi wlan0
function INTERNET() {
    KeepOriginal /etc/network/interfaces
    local WLAN=${1:-wlan0} INT=${2:-eth0}
    #/etc/if-post-up.d/wifi-gateway  adjust routing tables
    /bin/cat >/tmp/EW$$ <<EOF
#!/bin/sh
if [ -z "\$1" ] || [ -z "\$2" ]
then
   exit 0
fi
INT=\$1
WLAN=\$2
sleep 5           # wait a little to establish dhcp routing
if echo "\$INT" | /bin/grep wlan
then
    if /sbin/route -n | /bin/grep -q -e '^0\.0\.0\.0.*'"\$INT"
    then
        /sbin/route del default dev "\$INT"
    fi
    exit 0
fi
if ! /sbin/route -n | /bin/grep -q -e '^0\.0\.0\.0.*'"\$WLAN"
then
    if /sbin/route -n | /bin/grep -q "\${WLAN}"
    then
        GW=\$(/sbin/route -n | /bin/sed -e '/^[A-Za-Z0]/d' -e /\${INT}/d -e '/^10\./d' -e 's/\.0[ \t].*//' | /usr/bin/head -1).1
        if [ -n "\$GW" ]
        then
            if /sbin/route -n | /bin/grep -q -e '^0\.0\.0\.0.*'"\$INT"
            then
                /sbin/route del default dev "\$INT"
            fi
            /sbin/route add default gw \${GW} dev "\$WLAN"
            exit \$?
        fi
    fi
else
    exit 0
fi
EOF
    /bin/chmod +x /tmp/EW$$
    /usr/bin/sudo /bin/cp /tmp/EW$$ /etc/network/if-post-up.d/wifi-gateway
    # /etc/network/if-up.d/wifi-internet bring the other down
    /bin/cat >/tmp/EW$$ <<EOF
#!/bin/sh
if [ -z "\$1" ] || [ -z "\$2" ]
then
    exit 0
fi
INT=\$1
ALT=\$2
if  echo "\${INT}" | /bin/grep -q eth    # give time for eth for dhcp exchange
then
   sleep 5
fi
if /bin/grep -q 'up' /sys/class/net/"\${INT}"/operstate
then
    if /sbin/ifconfig "\${INT}" | grep -q 'inet addr'
    then
        if ! /sbin/ifdown "\${ALT}"
        then
            /sbin/ip link set dev "\${ALT}" down
        fi
        if echo "\${ALT}" | /bin/grep -q  wlan ; then exit 0 ; fi
        exit 1
    fi
fi
exit 0
EOF
    /bin/chmod +x /tmp/EW$$
    /usr/bin/sudo /bin/cp /tmp/EW$$ /etc/network/if-up.d/wifi-internet
    /bin/cat >/tmp/EW$$ <<EOF
# interfaces(5) file used by ifup(8) and ifdown(8)

# Please note that this file is written to be used with dhcpcd
# For static IP, consult /etc/dhcpcd.conf and 'man dhcpcd.conf'

# Include files from /etc/network/interfaces.d:
source-directory /etc/network/interfaces.d

auto lo
iface lo inet loopback

allow-hotplug $INT
iface $INT inet dhcp
        pre-up /etc/network/if-up.d/wifi-internet $WLAN $WLAN
        post-up /etc/network/if-post-up.d/wifi-gateway $WLAN $WLAN

allow-hotplug $WLAN
iface $WLAN inet dhcp
        pre-up /etc/network/if-up.d/wifi-internet $INT $WLAN
        post-up /etc/network/if-post-up.d/wifi-gateway $INT $WLAN
        wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf

allow-hotplug wlan1
iface wlan1 inet manual
        wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf

EOF
    /usr/bin/sudo /bin/cp /tmp/EW$$ /etc/network/interfaces
    /bin/rm -f /tmp/EW$$
}

INSTALLS+=" WIFI"
####### wifi wlan0 for wifi internet access, wlan1 (virtual device) for wifi AP
function WIFI(){
    local ANS=$1 WLAN=${1:-wlan0} INT=${2:-eth0}
    #sudo apt-get install wicd-curses # does not work well
    read -p "Want internet connectivity via wired and wifi (auto switched)? [Y|n]: " ANS
    if [ -z "${ANS/[Yy]/}" ]
    then
        INTERNET ${WLAN} ${INT}
	WIFI_AddSSID ${WLAN}
        INT=${WLAN}
    else
        WLAN=$WLAN}
    fi
    read -p "You want wifi Access Point installed? [y|N] " ANS
    if [ -z "${ANS/[nN]/}" ] ; then return ; fi
    echo "Installing virtual wifi interface on $WLAN for wifi AP" 1>&2
    for (( I=0; I <=5; I++))
    do
        WLAN=wlan$I
	if ! grep -q "$WLAN" /etc/network/interfaces ; then break ; fi
    done
    WIFI_HOSTAP $WLAN
    DNSMASQ "$WLAN" 10.0.0
    VIRTUAL "$WLAN" 10.0.0
    read -p "You want wifi AP clients to reach internet? [y,N] " ANS
    if [ ! -z "${ANS/[nN]/}" ] ; then NAT $WLAN $INT ; fi
    /usr/bin/sudo /usr/sbin/service dnsmasq restart
    /usr/bin/sudo /usr/sbin/service hostapd restart
}

UNINSTALLS[DNSMASQ]+=' /etc/dnsmasq.conf'
function DNSMASQ() {
    local WLAN=${1:-wlan1} ADDR=${2:-10.0.0}
    KeepOriginal /etc/dnsmasq.conf
    /usr/bin/sudo /usr/sbin/service isc-dhcp-server stop
    /usr/bin/sudo /bin/systemctl disable isc-dhcp-server
    /usr/bin/sudo /usr/bin/apt-get install dnsmasq -y
    /usr/bin/sudo /usr/sbin/service dnsmasq stop
    /usr/bin/sudo /bin/systemctl enable dnsmasq
    /bin/cat >/tmp/hostap$$ <<EOF
interface=${WLAN}
# access for max 4 computers, max 12h lease time
dhcp-range=${ADDR}.2,${ADDR}.5,255.255.255.0,12h
EOF
    /usr/bin/sudo /bin/cp /tmp/hostap$$ /etc/dnsmasq.conf
    /usr/bin/sudo /usr/sbin/service dnsmasq restart
    /bin/rm -f /tmp/hostap$$
}

INSTALLS+=" NAT"
# TO DO: add support for IPV6
function NAT(){
    local WLAN={1:-wlan1} INT=${2:-eth0}
    echo "Installing NAT and internet forwarding for wifi $WLAN to $INT" 1>&2
    /usr/bin/sudo /bin/sh -c "net.ipv4.ip_forward=1 >>/etc/sysctl.conf"
    /usr/bin/sudo /bin/sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
    /usr/bin/sudo /sbin/iptables -t nat -A POSTROUTING -o ${INT} -j MASQUERADE
    /usr/bin/sudo /sbin/iptables -A FORWARD -i ${INT} -o ${WLAN} -m state --state RELATED,ESTABLISHED -j ACCEPT
    /usr/bin/sudo /sbin/iptables -A FORWARD -i ${WLAN} -o ${INT} -j ACCEPT
    /sbin/iptables-save > /etc/firewall.conf
    /bin/cat >/tmp/hostap$$ <<EOF
#!/bin/sh
    if /bin/grep -q 'up' /sys/class/net/eth0/operstate
    then
        INT=eth0
        /sbin/ip link set dev wlan0 down
    else
        INT=wlan0
    fi
    if /sbin/ifconfig | /bin/grep -q wlan1
    then
        WLAN=wlan1
        /sbin/iptables -t nat -A POSTROUTING -o \${INT} -j MASQUERADE
        /sbin/iptables -A FORWARD -i \${INT} -o \${WLAN} -m state --state RELATED,ESTABLISHED -j ACCEPT
        /sbin/iptables -A FORWARD -i \${WLAN} -o \${INT} -j ACCEPT
    fi
EOF
    /usr/bin/sudo /bin/cp /tmp/hostap$$ /etc/network/if-up.d/iptables
    /usr/bin/sudo /bin/chmod +x /etc/network/if-up.d/iptables
    /bin/rm -f /tmp/hostap$$
}

UNINSTALLS[VIRTUAL]+=' /etc/network/if-up.d/virtual_wifi'
function VIRTUAL(){
    local WLAN=${1:-wlan2} ADDR=${2:-10.0.0}
    if /sbin/ifconfig | /bin/grep -q $WLAN ; then return ; fi
    /bin/cat >/tmp/hostap$$ <<EOF
#!/bin/bash
iw phy phy0 interface add ${WLAN} type __ap
ip link set ${WLAN} address \$(ifconfig ${INT} | /bin/grep HWadd | /bin/sed -e 's/.*HWaddr //' -e 's/:[^:]*\$/:00/')
# ip a add ${ADDR}.1/24 dev ${WLAN}
# ip link set dev ${WLAN} up
EOF
    /usr/bin/sudo /bin/cp /tmp/hostap$$ /etc/network/if-up.d/virtual_wifi
    /usr/bin/sudo chmod +x /etc/network/if-up.d/virtual_wifi
    /bin/cat >/tmp/hostap$$ <<EOF

auto ${WLAN}
iface ${WLAN} inet manual
    pre-up /etc/network/if-up.d/virtual_wifi
    address ${ADDR}.1
    netmask 255.255.255.0
EOF
    /usr/bin/sudo sh -c "cat /tmp/hostap$$ >>/etc/network/interfaces"
    /bin/rm -f /tmp/hostap$$
    /usr/bin/sudo /sbin/iw phy phy0 interface add ${WLAN} type __ap
    /usr/bin/sudo /sbin/ip link set ${WLAN} address $(ifconfig ${INT} | /bin/grep HWadd | /bin/sed -e 's/.*HWaddr //' -e 's/:[^:]*\$/:00/')
    /usr/bin/sudo /sbin/ip a add ${ADDR}.1/24 dev ${WLAN}
    /usr/bin/sudo /sbin/ip link set dev ${WLAN} up
}

INSTALLS+=" WIFI_HOSTAP"
UNINSTALLS[WIFI_HOSTAP]+=' /etc//etc/hostapd/hostapd.conf'
UNINSTALLS[WIFI_HOSTAP]+=' /etc/systemd/system/hostapd.service'
# install hostapd daemon
function WIFI_HOSTAP(){
    local WLAN=${1:-wlan1} SSID PASS HIDE
    KeepOriginal \
        /etc//etc/hostapd/hostapd.conf \
        /etc/systemd/system/hostapd.service
    if [ -f /etc/hostapd/hostapd.conf ]
    then /usr/bin/sudo /usr/bin/apt-get remove --purge hostapd -y
    fi
    /usr/bin/sudo /usr/bin/apt-get install hostapd -y
    /usr/bin/sudo /usr/sbin/service hostapd stop
    /usr/bin/sudo /bin/systemctl enable hostapd
    echo "wifi Access Point daemon needs SSID and password:" 1>&2
    read -p "wifi AP SSID: " SSID
    read -p "wifi AP password: " PASS
    read -p "Need the SSID to be hidden? [y|N]: " HIDE
    if [ -z "${HIDE/[Nn]/}" ] ; then HIDE=0 ; else HIDE=1 ; fi
    /bin/cat >/tmp/hostap$$ <<EOF
[Unit]
Description=Hostapd IEEE 802.11 Access Point
After=sys-subsystem-net-devices-${WLAN}.device
BindsTo=sys-subsystem-net-devices-${WLAN}.device
[Service]
Type=forking
PIDFile=/var/run/hostapd.pid
ExecStart=/usr/sbin/hostapd -B /etc/hostapd/hostapd.conf -P /var/run/hostapd.pid
[Install]
WantedBy=multi-user.target
EOF
    /usr/bin/sudo /bin/cp /tmp/hostap$$ /etc/systemd/system/hostapd.service
    /bin/cat >/tmp/hostap$$ <<EOF
interface=${WLAN}
hw_mode=g
channel=10
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
ssid=${SSID:-MySense}
wpa_passphrase=${PASS:-BehoudDeParel}
ignore_broadcast_ssid=${HIDE:-0}
EOF
    /usr/bin/sudo /bin/cp /tmp/hostap$$ /etc/hostapd/hostapd.conf
    /bin/rm -f /tmp/hostap$$
}

INSTALLS+=" WIFI_AddSSID"
UNINSTALLS[WIFI_AddSSID]+=' /etc/wpa_supplicant/wpa_supplicant.conf'
# add wifi ssid/WPA password to enable wlan0 for internet access via wifi
function WIFI_AddSSID(){
    local SSID PASS1=0 PASS2=1 WLAN=${1:-wlan}
    KeepOriginal /etc/wpa_supplicant/wpa_supplicant.conf
    SSID=$(/usr/bin/sudo /bin/grep ssid /etc/wpa_supplicant/wpa_supplicant.conf | /bin/sed -e 's/.*ssid=//' -e 's/"//g')
    if [ -n "$SSID" ]
    then
        echo "SSID's already defined in /etc/wpa_supplicant/wpa_supplicant.conf: $SSID"
    fi
    WLAN=$(/sbin/ifconfig | /usr/bin/awk "/$WLAN/{ print \$1; exit(0); }")
    if [ -z "$WLAN" ]
    then
        WLAN=wlan0
        if ! /usr/bin/sudo /sbin/ip link set dev ${WLAN} up || ! \
	    /usr/bin/sudo wpa_supplicant -B -c/etc/wpa_supplicant/wpa_supplicant.conf -i"$WLAN" >/dev/null
        then
            echo "ERROR: cannot enable wifi $WLAN"
            return 1
        fi
    fi
    echo "Wifi access points near by:"
    /usr/bin/sudo /sbin/iw "$WLAN" scan | /bin/grep -e SSID: -e signal:
    echo -e "Enter SSID and password for accessing the internet wifi router.\nJust return to stop." 1>&2
    read -p "wifi SSID: " SSID
    if [ -z "$SSID" ] ; then return 1 ; fi
    while [ "$PASS1" != "$PASS2" ]
    do
        read -p "wifi password: " PASS1
        read -p "retype passwd: " PASS2
    done
    /usr/bin/sudo /bin/cp /etc/wpa_supplicant/wpa_supplicant.conf /tmp/wpa$$
    /usr/bin/sudo /bin/chown $USER /tmp/wpa$$
    if /bin/grep -q "ssid=\"*$SSID\"*" /tmp/wpa$$
    then
        ed - /tmp/wpa$$ <<EOF
/ssid="*$SSID"*/-1,/}/d
w
q
EOF
    fi
    /bin/cat >>/tmp/wpa$$ <<EOF
network={
    ssid="$SSID"
    psk="$PASS1"
    proto=RSN
    key_mgmt=WPA-PSK
    pairwise=CCMP
    auth_alg=OPEN
}
EOF
    /usr/bin/sudo /bin/cp /tmp/wpa$$ /etc/wpa_supplicant/wpa_supplicant.conf
    /bin/rm -f /tmp/wpa$$
    /usr/bin/sudo pkill -HUP wpa_supplicant    # try the new ssid/passwd
    /usr/bin/sudo /sbin/wpa_cli reconnect
    sleep 5
    if /usr/bin/sudo /sbin/wpa_cli status | /bin/grep -q "ssid=$SSID"
    then
        break
    else
        echo "FAILURE: cannot connect to $SSID."
        read  -p "Try another password? [Y|n] " PASS1
        if [ -z "${PASS1/[Yy]/}" ] ; then continue ; fi
        read  -p "Try another SSID? [y|N] " PASS1
        if [ -z "${PASS1/[Nn]/}" ] ; then return ; fi
        WIFI_AddSSID ${WLAN}
        return
    fi
}
#WIFI_AddSSID
function WIFI_Internet(){
    local WLAN=${1:-wlan0}
    /bin/cat >/tmp/hostap$$ <<EOF
#!/bin/sh
    if /bin/grep -q 'up' /sys/class/net/eth0/operstate
    then
        /sbin/ip link set dev ${WLAN} down
    fi
EOF
    /usr/bin/sudo /bin/cp /tmp/hostap$$ /etc/network/if-up.d/iptables
    /usr/bin/sudo /bin/chmod +x /etc/network/if-up.d/iptables
    echo "Added network={} to /etc/wpa_supplicant/wpa_supplicant.conf" 1>&2
    echo "${WLAN} will be down on reboot if eth0 is active: /etc/network/if-up.d/iptables" 1>&2
}

if [ -n "$1" ] && [ "$1" = help -o x"$1" = x--help -o x"$1"  = x-h ]
then
   echo "Usage:
INSTALLS.sh will make the Pi ready for installing MySense.py by downloading and installing
all Python dependencies en services for MySense.py.
For the OS changes are available: $INSTALLS
For plugins are available: $PLUGINS
For extra's: $EXTRA
Calling INSTALL.sh without arguments will install all.
"
    exit 0
fi

MODS=$@
if [ -z "$MODS" ]
then
    MODS="$INSTALLS $PLUGINS $EXTRA"
fi

UPDATE
for M in $MODS
do
    # TO BE ADDED: check config if the plugin is really used
    if echo "$INSTALLS $PLUGINS $EXTRA" | grep -q -i "$M"
    then
        if echo "$INSTALLS" | /bin/grep -q "$M"
        then
            echo "System configuration for ${M^^}"
        elif echo "$PLUGINS" | /bin/grep -q "$M"
        then 
            echo "Plugin My${M^^}.py looking for missing modules/packages:" 
        else
            echo "For extra's not really needed  ${M^^} services:" 
        fi
        if ! ${M^^}
        then
            echo "FAILED to complete needed modules/packages for My${M^^}.py." 1>&2
        fi
    else
        echo "Unknow plugin for $M. Skipped." 1>&2
    fi
done
