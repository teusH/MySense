#!/bin/bash
# installation of modules needed by MySense.py
#
# $Id: INSTALL.sh,v 1.56 2017/09/08 13:39:31 teus Exp teus $
#

USER=${USER:-ios}
echo "You run this script as user $USER (preferrebly \"ios\" and install it from folder MySense).
You need to provide your password for root access.
Make sure this user is added at the sudoers list." 1>&2
#set -x

PATH=/sbin:/usr/sbin:/bin:/usr/bin:/usr/local/sbin:/usr/local/bin

declare -A HELP
declare -A DFLT
HELP[UPDATE]="Update will update the Pi OS and Debian packages One may skip this if done before."
DFLT[UPDATE]=N
function UPDATE() {
    /usr/bin/sudo apt-get update
    /usr/bin/sudo apt-get upgrade
    /usr/bin/sudo apt-get dist-upgrade
    /usr/bin/sudo apt-get autoremove
    # /usr/bin/sudo pip install --upgrade
}

# add a command to crontab of user executed at (re)boot
function AddCrontab() {
    local myUSER=${2:-root}
    local SUDO=''
    if [ -z "$1" ] ; then return 1 ; fi
    if [ "$myUSER" != "$USER" ] ; then SUDO=/usr/bin/sudo ; fi
    if ! $SUDO /usr/bin/crontab -u "$myUSER" -l 2>/dev/null | /bin/grep -q "^@boot.*$1"
    then
        ($SUDO /usr/bin/crontab -u "$myUSER" -l 2>/dev/null ; echo "@boot $1" ) | $SUDO /usr/bin/crontab -u "$myUSER" -
        echo "Added at (re)boot to execute $1 as $myUSER user."
    fi
    return $?
}

WIFI=wlan0
LAN=eth0
# Debian has changed names for internet interfaces
function GetInterfaces(){
    if /sbin/ifconfig -a | /bin/grep -q '[ew][ln]x.*: flag'
    then
        WIFI=$(/sbin/ifconfig -a | /bin/grep 'wlx..*: flag' | /bin/sed 's/: .*//')
        LAN=$(/sbin/ifconfig -a | /bin/grep 'enx..*: flag' | /bin/sed 's/: .*//')
    else
        WIFI=$(/sbin/ifconfig -a | /bin/grep 'wlan.*: flag' | /bin/sed 's/: .*//')
        LAN=$(/sbin/ifconfig -a | /bin/grep 'eth..*: flag' | /bin/sed 's/: .*//')
    fi
    if [ -z "$WIFI" ] || [ -z "$LAN" ]
    then
        echo "WARNING: only ${WIFI:-no wifi} and ${LAN:-no lan} internet interface available. Correct it manualy e.g. in /etc/network/interfaces." >/dev/stderr
    fi
    WIFI=${WIFI:-wlan0}
    LAN=${LAN:-eth0}
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
    if ! /usr/bin/pip --format=legacy list | /bin/grep -q -i "^$MOD"
    then
        echo "Installing $MOD via pip"
        if [ -n "$2" ]
        then
            mkdir -p src
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

function ASK(){
    local ANS DF
    if [ -z "${DFLT[${1}]}" ] ; then DFLT[${1}]=Y ; fi
    if [ "${DFLT[${1}]/N*/N}" = N  ] ; then DF="N|y" ; fi
    if [ "${DFLT[${1}]/Y*/Y}" = Y  ] ; then DF="Y|n" ; fi
    if [ -n "${HELP[${1}]}" ]
    then
        echo "    ${HELP[${1}]}" >/dev/stderr
    fi
    if [ "${DFLT[${1}]}" = none ] ; then return 0 ; fi
    if [ -n "$2" ] ; then echo "    ${2}" >/dev/stderr ; fi
    read -t 15 -p  "Do you want to install My${1} and dependences? [${DF}] " ANS
    DF=${DF/%??/}
    if [ -n "$ANS" ]
    then
        DF=$(echo "${ANS^^}" | sed 's/\(.\).*/\1/')
    fi
    if [ $DF = Y ] ; then return 0 ; else return 1 ; fi
}

function MYSENSE(){
    return $?
}

PLUGINS+=" MYSQL"
HELP[MYSQL]="MYSQL will install MySQL database client and Python modules."
function MYSQL(){
    DEPENDS_ON apt python-mysql.connector
    # mysql shell client command
    DEPENDS_ON  apt mysql-client
    # DEPENDS_ON apt mysql-navigator # GUI not really needed
    return $?
}

PLUGINS+=" DHT"
UNINSTALLS[DHT]+=' /usr/local/bin/set_gpio_perm.sh'
HELP[DHT]="Installation of DHT sensor libraries and general purpose IO use.
Please enable gpio via raspi-config command interfaces as root."
function DHT(){
    if [ ! -x /usr/local/bin/set_gpio_perm.sh ]
    then
        echo "Created the file /usr/local/bin/set_gio_perm.sh"
        /bin/cat >/tmp/perm.sh <<EOF
#!/bin/sh
chown root:gpio /dev/gpiomem
chmod g+rw /dev/gpiomem
EOF
        chmod +x /tmp/perm.sh
        /usr/bin/sudo mv /tmp/perm.sh /usr/local/bin/set_gpio_perm.sh
        /usr/bin/sudo chown root.root /usr/local/bin/set_gpio_perm.sh
        AddCrontab /usr/local/bin/set_gpio_perm.sh root
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
HELP[BME280]="Installation of BME280 library and BME280 sleep/wakeup script.
Please make sue I2C is activated: Use raspi-config command -> interfaces for this."
function BME280() {
    DEPENDS_ON pip adafruit/Adafruit_Python_GPIO.git Adafruit_Python_GPIO
    if [ ! -f ./Adafruit_Python_BME280.py ]
    then
        git clone https://github.com/adafruit/Adafruit_Python_BME280.git
        /bin/cp ./Adafruit_Python_BME280/Adafruit_BME280.py .
        /bin/cat >>Adafruit_BME280.py <<EOF

    # added by teus 2017-07-03 thanks to Thomas Telkamp
    # to avoid heating up the Boisch chip and so temp measurement raise
    def BME280_sleep(self):
        ''' put the Bosch chip in sleep modus '''
        self._device.write8(BME280_REGISTER_CONTROL,0x0)

    def BME280_wakeup(self):
        ''' wakeup the Bosch chip '''
        self._device.write8(BME280_REGISTER_CONTROL, 0x3F)

EOF
        /bin/rm -rf ./Adafruit_Python_BME280/
    fi
    return $?
}

INSTALLS+=" THREADING"
HELP[THREADING]="Using default multi threading for all input plugins (sensor modules)."
DFLT[THREADING]="none"
function THREADING(){
    #DEPENDS_ON pip threading
    return $?
}

PLUGINS+=" DYLOS"
HELP[DYLOS]="Using default serial python module"
DFLT[DYLOS]="none"
function DYLOS(){
    # DEPENDS_ON pip serial
    return $?
}

PLUGINS+=" GPS"
HELP[GPS]="Installing GPS Debian deamon and Python libraries via serial connection."
function GPS(){
    DEPENDS_ON apt gpsd         # GPS daemon service
    #DEPENDS_ON apt gps-client  # command line GPS client
    DEPENDS_ON apt python-gps   # python client module
    DEPENDS_ON pip gps3         # python gps client module
    return $?
}

# PLUGINS+=" GSPREAD"
HELP[GSPREAD]="Installing Google gspread connectivity. DEPRECATED"
DFLT[GSPRAED]=N
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
HELP[MQTTSUB]="Installing Mosquitto (MQTT) subscriber (client) part. Usually not needed."
DFLT[MQTTSUB]=N
function MQTTSUB(){
    DEPENDS_ON pip paho-mqtt    # mosquitto client modules
    # DEPENDS_ON apt python-mosquitto
    return $?
}

PLUGINS+=" MQTTPUB"
HELP[MQTTPUB]="Installing Mosquitto (MQTT) publishing client to send measurements to MQTT server."
function MQTTPUB(){
    DEPENDS_ON pip paho-mqtt    # mosquitto client modules
    # DEPENDS_ON apt python-mosquitto
    return $?
}

PLUGINS+=" SDS011"
HELP[SDS011]="Installing Python dependences for Nova SDS011 PM (USB) sensor."
function SDS011(){
    DEPENDS_ON pip enum34
    return $?
}

PLUGINS+=" PMSN003"
HELP[PMSN003]="Installing Python dependences for Plantower PMS 5003 or 7003 USB sensor"
function PMSN003(){
    # DEPENDS_ON pip serial
    return $?
}

EXTRA+=" MQTT"
HELP[MQTT]="Installing Mosquitto server deamon or broker. Usually not needed."
DFLT[MQTT]=N
function MQTT(){
    echo "see README.mqtt for authentication provisions" >/dev/stderr
    #DEPENDS_ON apt mqtt
    DEPENDS_ON apt mosquitto
    return $?
}

EXTRA+=" STARTUP"
HELP[STARTUP]="Installing auto MySense startup at boot via MyStart.sh script."
UNINSTALLS[STARTUP]+=" MyStart.sh"
function STARTUP(){
    echo "Installing: auto MySense start on boot: MyStart.sh"
    WD=$(pwd | sed -e s@$HOME@@ -e 's/^//')
    cat >MyStart.sh <<EOF
#!/bin/bash
# if there is internet connectivity start MySense

LED=\${LED:-D6}
WD=\${DIR:-$WD}
D_ADDR=2017

if [ ! -d \$HOME/\$WD ] ; then exit 1 ; fi
if [ ! -f \$HOME/\$WD/MySense.conf -o ! -f \$HOME/\$WD/MySense.py ]
then
    echo -e "<clear>MySense ERROR\nnot properly installed" | /bin/nc -w 2 localhost \$D_ADDR
    exit 1
fi

CNT=0
while ! /bin/ping -q -w 2 -c 1 8.8.8.8 >/dev/null
do  
    echo -e "<clear>No internet access\nfor \$CNT minutes" | /bin/nc -w 2 localhost \$D_ADDR
    CNT=\$((\$CNT+1))
    /usr/local/bin/MyLed.py --led \$LED --light ON
    sleep 1
    if [ \$CNT -gt 30 ] ; break ; fi
    /usr/local/bin/MyLed.py --led \$LED --light OFF
    sleep 59
done
if [ \$CNT -gt 30 ]
then
    echo -e "<clear>STARTING up MySense\nin LOCAL modus\nWelcome to MySense" | /bin/nc -w 2 localhost \$D_ADDR
    /usr/local/bin/MyLed.py --led \$LED --light OFF
    LOCAL=--local
else
    echo -e "<clear>STARTING up MySense\nWelcome to MySense" | /bin/nc -w 2 localhost \$D_ADDR
    LOCAL=''
fi

cd \$HOME/\$WD
python \$HOME/\$WD/MySense.py \$LOCAL start
exit 0
EOF
    chmod +x MyStart.sh
    AddCrontab "$(pwd)/MyStart.sh"
    /usr/bin/sudo /bin/chmod 4755 /bin/ping
}

EXTRA+=" DISPLAY"
HELP[DISPLAY]="Installing tiny Adafruit display support."
UNINSTALLS[DISPLAY]+=" /usr/local/bin/MyDisplayServer.py"
function DISPLAY(){
    # this needs to be tested
    echo "Installing Display service and plugin"
    DEPENDS_ON apt python-pil
    DEPENDS_ON pip Adafruit-GPIO
    DEPENDS_ON pip Adafruit-SSD1306
    # DEPENDS_ON pip Adafruit_BBIO
    DEPENDS_ON apt python-imaging
    DEPENDS_ON apt python-smbus
    local ANS=I2C
    read -p "Please answer: SSD1306 display uses I2C or SPI bus? [I2C|SPI]: " ANS
    case X"$ANS" in
    XI2C|XSPI)
        ANS=$ANS
    ;;
    *)
        return 1
    ;;
    esac
    if [ "$ANS" = SPI ] && ! /bin/ls /dev/spi* 2>/dev/null | grep -q "spidev0.[01]"
    then
        echo "GPIO: Missing spidev: please use \"sudo rasp-config\" and enable SPI"
    fi
    local INS_DIR=$(pwd)
    if [ ! -f MyDisplayServer.py ]
    then
        echo "ERROR: cannot locate MyDisplayServer.py for display service/server"
        return 1
    fi
    sudo /bin/cp MyDisplayServer.py /usr/local/bin
    sudo /bin/chmod +x /usr/local/bin/MyDisplayServer.py
    AddCrontab "/usr/local/bin/MyDisplayServer.py -b $ANS start" $USER
    echo "Installed to activate ${ANS} display service on reboot."
    if ! /usr/bin/groups | grep -q ${ANS,,}
    then
        if ! /bin/grep "^${ANS,,}.*$USER" && ! /usr/sbin/useradd -G ${ANS,,} $USER
        then
            echo "Please add $USER or MYSense user to ${ANS,,} group: sudo nano /etc/group"
        else
            echo "Added $USER to ${ANS,,} group and to access ${ANS,,}"
        fi
    fi
    return $?
}

PLUGINS+=" INFLUX"
HELP[INFLUX]="Installing influx publishing and server support modules."
function INFLUX(){
    DEPENDS_ON pip influxdb
    DEPENDS_ON pip requests
    return $?
}

INSTALLS+=" GROVEPI"
HELP[GROVEPI]="Installing GrovePi+ shield support, needed for several types of sensors."
# this will install the grovepi library
function GROVEPI(){
    if /usr/bin/pip --format=legacy list | /bin/grep -q grovepi ; then return ; fi
    if [ -d git/GrovePi ] ; then return ; fi
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
    # user needs user access to gpio and i2c
    /usr/bin/sudo adduser $USER gpio
    /usr/bin/sudo adduser $USER i2c
    echo "Please reboot and install the Grove shield"
    echo "Run sudo i2cdetect -y To see is GrovePi is detected."
    return
}

INSTALLS+=" USER"
HELP[USER]="Installing MySense main user (default ios) and needed IO permissions."
function USER(){
    local ANS=''
    if [ $(whoami) = ${USER} ]
    then
        echo "if not '${USER}' user owner of installation, provide new name or push <return" 1>&2
        read -p "new name: " -t 15 ANS
    fi
    if [ -z "$ANS" ] ; then return ; else USER=$ANS ;  fi
    if grep -q "$USER" /etc/passwd ; then return ; fi
    echo "Need to do this with root permissions."
    /usr/bin/sudo touch /dev/null
    echo "Adding user  $USER and password"
    /usr/bin/sudo adduser $USER 
    /usr/bin/sudo passwd $USER
    /usr/bin/sudo adduser $USER gpio
    /usr/bin/sudo adduser $USER i2c
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
    if [ -f "$FILE" ] || [ -d "$FILE" ]
    then
        if [ -f "$FILE.orig" ] || [ -d "$FILE.orig" ]
        then
            /usr/bin/sudo /bin/mv -f  "$FILE.orig" "$FILE"
	else
	    read -p "Want to keep $FILE? [Ny] " ANS
	    if [ -z "${ANS/[Nn]/}" ]
	    then
                if [ -f "$FILE" ]
                then
		    /usr/bin/sudo /bin/rm -f "$FILE"
                elif [ -d "$FILE" ]
                then
                    /usr/bin/sudo /bin/rm -rf "$FILE"
                fi
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
    elif [ -f $FILE ]
    then
        /usr/bin/sudo -b /bin/cp $FILE $FILE.bak
    fi
    done
}

INSTALLS+=" INTERNET"
HELP[INTERNET]="Installation of internet connectivity via LAN and/or WiFi.
If needed see /etc/network/interfaces for what has been configured."
UNINSTALLS[INTERNET]+=' /etc/network/if-post-up.d/wifi-gateway'
UNINSTALLS[INTERNET]+=' /etc/network/if-up.d/wifi-internet'
UNINSTALLS[INTERNET]+=' /etc/network/interfaces'
## wired line $LAN switch to wifi on reboot
# will bring up internet access via $LAN (high priority) or wifi $WIFI
function INTERNET() {
    GetInterfaces       # get names of internet devices
    KeepOriginal /etc/network/interfaces
    local WLAN=${1:-${WIFI:-wlan0}} INT=${2:-${LAN:-eth0}}
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
    /usr/bin/sudo /bin/mkdir -p /etc/network/if-post-up.d/
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

EOF
    /usr/bin/sudo /bin/cp /tmp/EW$$ /etc/network/interfaces
    /bin/rm -f /tmp/EW$$
}

# installs  system admin web interface on port 10000
# remote system admin (default via ssh)
EXTRA+=' WEBMIN'
HELP[WEBMIN]="Installation of system administration via web interface (port 10000). Usually not needed."
DFLT[WEBMIN]=N
function WEBMIN(){
    local ANS
    # DEPENDS_ON APT perl
    DEPENDS_ON APT libnet-ssleay-perl
    # DEPENDS_ON APT openssl
    DEPENDS_ON APT libauthen-pam-perl
    # DEPENDS_ON APT libpam-runtime
    DEPENDS_ON APT libio-pty-perl
    DEPENDS_ON APT apt-show-versions
    # DEPENDS_ON APT python

    /usr/bin/wget -O /tmp/webmin_1.831_all.deb http://prdownloads.sourceforge.net/webadmin/webmin_1.831_all.deb
    echo "Installation can take more as 5 minutes." 1>&2
    /usr/bin/sudo dpkg --install /tmp/webmin_1.831_all.deb
    /bin/rm  -f /tmp/webmin_1.831_all.deb
    /usr/bin/wget -O /tmp/jcameron-key.as http://www.webmin.com/jcameron-key.asc
    /usr/bin/sudo /usr/bin/apt-key add /tmp/jcameron-key.asc
    /bin/rm -f /tmp/jcameron-key.asc
    /usr/bin/sudo /bin/sh -c "echo 'deb http://download.webmin.com/download/repository sarge contrib' >> /etc/apt/sources.list"
}

# backdoor via Weaved service: the service gives you a tunnel by name
# the weaved daemon will connect to Weaved to build a tunnel to Weaved.
# Reminder: everybody knowing the port from Weaved and have Pi user credentials
# can login into your Pi
EXTRA+=' WEAVED'
HELP[WEAVED]="Installation of backdoor for remote access via the Waeved service. You need an account with Remo3.it."
DFLT[WEAVED]=N
function WEAVED(){
    local ANS
    echo "This will install a backdoor via the webservice from Weaved (remote3.it)." 1>&2
    echo "You may first register (free try) and obatain user/passwd through https://weaved.com" 1>&2
    DEPENDS_ON APT weavedconnectd
    echo "
Run the next configuring command for Weaved.
Use main menu: 1) Attach/reinstall to connect the Pi and enter a device name e.g. MySense-ssh
Use protocol selection menu 1) for ssh and 4) for webmin (enter http and 10000)
" 1>&2
    read -t 20 -p "Configure it now? [Yn] " ANS
    if [ -z "${ANS/[nN]/}" ] ; then return ; fi
    /usr/bin/sudo /usr/bin/weavedinstaller
}

# backdoor via ssh tunneling.
EXTRA+=' SSH_TUNNEL'
HELP[SSH_TUNNEL]="Besides a virtual desktop one can install a backdoor via ssh tunneling. If so install this script to create the tunnel."
DFLT[SSH_TUNNEL]=N
function SSH_TUNNEL(){
    local ANS
    echo "You need to have imported an ssh key of you as user@your-desktop-machine."
    echo "If not do this now: login into your laptop and authorize eg ios/IPnr.
        if there is not ~/.ssh private and public key in this directory:
        ssh-keygen   # no password, less secure it saves the trouble on each ssh run
        ssh-copy-id ios@IPnrPi # copy of key for ssh no passwd access"
    cat >/tmp/SH$$ <<EOF
#!/bin/bash
# note the identity should be for Pi user root in /root/.ssh/!
ME=\${1:-me}            # <--- your local user name
IP=\${2:-my-laptop-IP}  # <--- your local IP number, must be a static number
# generate/copy key as root first!
if ! /bin/nc -w 1 -z \${IP} 22 ; then exit 1 ; fi     # is there connectivity?
if ! /bin/ps ax | /bin/grep "ssh -R 10000:" | grep -q \$ME # is tunnel alive?
then
    /usr/bin/ssh -R 10000:localhost:10000 "\${ME}@\${IP}" -nTN & # webmin
    echo "Watchdog restart tunnel to \${ME}@\${IP}:10000 for webmin"
fi
if ! /bin/ps ax | /bin/grep "ssh -R 10001:" | grep -q "\$ME" # is tunnel alive?
then
    /usr/bin/ssh -R 10001:localhost:22 "\${ME}@${IP}" -nTN &    # ssh
    echo "Watchdog restart tunnel to \${ME}@\${IP}:10001 for ssh"
fi
exit 0
EOF
    cmod +x /tmp/SH$$
    sudo cp /tmp/SH$$ /usr/local/bin/watch_my_tunnel.sh
    echo "Add the following line to the crontab, by issuing 'crontab -e'"
    echo "Change USER HOSTIP by your user id and destop/laptop static IP number"
    echo "*/10 10-23 * * * /usr/local/bin/watch_my_tunnel.sh USER IPnr"
    sleep 5
    crontab -e
}
    
INSTALLS+=" WIFI"
HELP[WIFI]="Installation of WiFi access to the Pi: wifi for internet connectivity, wifi access point on connectivity failures."
####### wifi $WIFI for wifi internet access, uap0 (virtual device) for wifi AP
# wlan1 for USB wifi dongle (use this if wifi $WIFI fails and need wifi AP)
function WIFI(){
    GetInterfaces
    KeepOriginal /etc/network/interfaces
    local AP=${1:-uap0} ADDR=${2:-192.168.2}
    # make sure $WIFI is getting activated
    cat >/tmp/Int$$ <<EOF
# virtual wifi AP
auto ${AP}
iface ${AP} inet static
    address ${ADDR}.1
    netmask 255.255.255.0
    network 192.168.2.0                                                              
    broadcast 192.168.2.255                                                          
    gateway 192.168.2.1
EOF
    sudo cp /tmp/Int$$ /etc/network/interfaces.d/UAP
    cat >/tmp/Int$$ <<EOF
#!/bin/bash
INT=\${1:-$LAN}
WLAN=\$2
EXIT=0
if [ -z "\$2" ] ; then exit 0 ; fi
if /sbin/route -n | /bin/grep -q '^0.0.0.0.*dev  *'\${INT}
then
    EXIT=1      # do not bring up \${WLAN:-$WIFI} if not needed
fi
exit \$EXIT
EOF
    chmod +x /tmp/Int$$
    sudo cp /tmp/Int$$ /etc/network/if-pre-up.d/Check-internet
    cat >/tmp/Int$$ <<EOF
# interfaces(5) file used by ifup(8) and ifdown(8)

# Please note that this file is written to be used with dhcpcd

# Include files from /etc/network/interfaces.d:
source-directory /etc/network/interfaces.d

auto lo
iface lo inet loopback

iface $LAN inet manual

auto $WIFI
iface $WIFI inet dhcp
    pre-up /etc/network/if-pre-up.d/Check-internet $LAN $WIFI
    wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf

allow-hotplug wlan1
iface wlan1 inet manual
    wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf

source interfaces.d/UAP
EOF
    sudo cp /tmp/Int$$ /etc/network/interfaces
    rm -f /tmp/Int$$
    echo "If wired and wifi wireless fail you need wifi AP access." 1>&2
    read -t 15 -p "You want wifi Access Point installed? [Y|n] " ANS
    if [ -n "${ANS/[yY]/}" ] ; then return ; fi
    echo "Installing virtual wifi interface on $AP for wifi AP" 1>&2
    local NAT=YES
    WIFI_HOSTAP ${AP}              # give access if $LAN and $WIFI fail
    DNSMASQ "${AP}" ${ADDR}
    read -p "You want wifi AP clients to reach internet? [y,N] " ANS
    if [ -n "${ANS/[nN]/}" ] ; then NAT=NO ; fi
    VIRTUAL "${AP}" ${ADDR} ${NAT}
    # /usr/bin/sudo /usr/sbin/service dnsmasq restart
    # /usr/bin/sudo /usr/sbin/service hostapd restart
}

INSTALLS+=" LOGGING"
HELP[LOGGING]="Installation of loggin rotation script for /var/log/MySense/MySense.log."
UNINSTALLS[LOGGING]+=' /etc/logrotate.d/MySense /var/log/MySense'
# logging, may be different due to MySense.conf configuration
function LOGGING(){
    /bin/cat >/tmp/logging$$ <<EOF
/var/log/MySense/MySense.log {
        rotate 3
        daily
        compress
        size 100k
        nocreate
        missingok
        # postrotate
        #       /usr/bin/killall -HUP MySense
        # endscript
}
EOF
    # rotate the MySense logging file
    sudo cp /tmp/logging$$ /etc/logrotate.d/MySense
    rm /tmp/logging$$
    sudo mkdir /var/log/MySense
    sudo chown ${USER}.adm /var/log/MySense
    return 0
}

UNINSTALLS[DNSMASQ]+=' /etc/dnsmasq.conf'
# make dsnmasq ready to operatie on wifi Access Point
# activate it from elsewhere
function DNSMASQ() {
    local WLAN=${1:-uap0} ADDR=${2:-192.168.2}
    KeepOriginal /etc/dnsmasq.conf
    /usr/bin/sudo /usr/sbin/service isc-dhcp-server stop
    /usr/bin/sudo /bin/systemctl disable isc-dhcp-server
    DEPENDS_ON APT dnsmasq
    /usr/bin/sudo /usr/sbin/service dnsmasq stop
    /usr/bin/sudo /bin/systemctl disable dnsmasq
    # provide dhcp on wifi channel
    /bin/cat >/tmp/hostap$$ <<EOF
interface=${WLAN}
# access for max 4 computers, max 12h lease time
dhcp-range=${WLAN},${ADDR}.2,${ADDR}.5,255.255.255.0,12h
EOF
    /usr/bin/sudo /bin/cp /tmp/hostap$$ /etc/dnsmasq.conf
    /bin/rm -f /tmp/hostap$$
    # /usr/bin/sudo /usr/sbin/service dnsmasq restart
}

INSTALLS+=" NAT"
HELP[NAT]="Installation of network address translation for internetaccess via wifi to internet. Usually not needed."
DFLT[NAT]=N
# TO DO: add support for IPV6
function NAT(){
    GetInterfaces
    local WLAN={1:-uap0} INT=${2:-$LAN}
    if /bin/grep -q net.ipv4.ip_forward=1 /etc/sysctl.conf ; then return ; fi
    echo "Installing NAT and internet forwarding for wifi $WLAN to $INT" 1>&2
    /usr/bin/sudo /bin/sh -c "echo net.ipv4.ip_forward=1 >>/etc/sysctl.conf"
    /usr/bin/sudo /bin/sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
    /usr/bin/sudo /sbin/iptables -t nat -A POSTROUTING -o ${INT} -j MASQUERADE
    /usr/bin/sudo /sbin/iptables -A FORWARD -i ${INT} -o ${WLAN} -m state --state RELATED,ESTABLISHED -j ACCEPT
    /usr/bin/sudo /sbin/iptables -A FORWARD -i ${WLAN} -o ${INT} -j ACCEPT
    /usr/bin/sudo /bin/sh -c "/sbin/iptables-save > /etc/firewall.conf"
    /bin/cat >/tmp/hostap$$ <<EOF
#!/bin/sh
    if /bin/grep -q 'up' /sys/class/net/${INT}/operstate
    then
        INT=${INT}
        /sbin/ip link set dev ${WLAN} down
    else
        INT=${WLAN}
    fi
    if /sbin/ifconfig | /bin/grep -q uap0
    then
        WLAN=${WLAN}
        /sbin/iptables -t nat -A POSTROUTING -o \${INT} -j MASQUERADE
        /sbin/iptables -A FORWARD -i \${INT} -o \${WLAN} -m state --state RELATED,ESTABLISHED -j ACCEPT
        /sbin/iptables -A FORWARD -i \${WLAN} -o \${INT} -j ACCEPT
    fi
EOF
    /usr/bin/sudo /bin/cp /tmp/hostap$$ /etc/network/if-up.d/iptables
    /usr/bin/sudo /bin/chmod +x /etc/network/if-up.d/iptables
    /bin/rm -f /tmp/hostap$$
}

UNINSTALLS[VIRTUAL]+=' /usr/local/etc/start_wifi_AP'
# this will start wifi Access Point if $LAN and $WIFI have no internet access
# the virtual uap0 wifi will be combined with $WIFI (embedded in Pi3)
# TO DO: if uap0 is up, $WIFI cannot be used in symultane (does not work yet)
function VIRTUAL(){
    local WLAN=${1:-uap0} ADDR=${2:-192.168.2} NAT=${3:-YES}
    if [ $NAT = YES ]
    then
        NAT="/sbin/sysctl net.ipv4.ip_forward=1
/sbin/iptables -t nat -A POSTROUTING -s ${ADDR}.0/24 ! -d ${ADDR}.0/24 -j MASQUERADE"
    else
        NAT=""
    fi
    /bin/cat >/tmp/hostap$$ <<EOF
#!/bin/bash
# this will check wired, wifi if there is a connectivity
# if not it will initiate wifi AP to login locally

BUS=I2C
D_ADDR=2017
# led ON
if [ -x /usr/local/bin/MyLed.py ]
then
    /usr/local/bin/MyLed.py --led D6 --light ON
fi
if [ -x /usr/local/bin/MyDisplayServer.py ]
then
    /usr/bin/sudo -u ios /usr/local/bin/MyDisplayServer.py -b \$BUS start 2>/dev/null
    /bin/sleep 2
fi

function INTERNET() {
    GetInterfaces
    local WLAN=\${1:-$WIFI}
    local ADDR=''
    if /sbin/ifconfig \$WLAN | grep -q 'inet addr'
    then
        ADDR=\$(/sbin/ifconfig \$WLAN | /usr/bin/awk '/inet addr/{ split(\$2,a,":"); print a[2]; }')
        if /sbin/route -n | grep -q '^0.0.0.0.*'\${WLAN}
        then
            if ! ping -q -W 2 -c 2 8.8.8.8 >/dev/null
            then
                # no outside connectivity
                return 1
            fi
            # led OFF
            if [ -x /usr/local/bin/MyLed.py ]
            then
                /usr/local/bin/MyLed.py --led D6 --light OFF
            fi
            echo "\$WLAN \$ADDR" | /bin/nc -w 2 localhost \$D_ADDR
            exit 0
        fi
    fi
    return 1
}

INTERNET $LAN	# try wired internet line
INTERNET $WIFI  # try WiFi connectivity

# no connectivity. Start wifi AP
if /sbin/ifconfig | /bin/grep -q uap0
then
    /sbin/ip link set dev uap0 down
    /sbin/ifdown $LAN
    /sbin/ifup $WIFI
fi

SSIDS=(\$(/sbin/wpa_cli scan_results | /bin/grep WPS | /usr/bin/sort -r -k3 | /usr/bin/awk '{ print \$1;}'))
# try WPS on all BSSID's
echo "<clear>Try WiFi WPS on:" | /bin/nc -w 2 localhost \$D_ADDR
if [ -x /usr/local/bin/MyLed.py ]
then
    /usr/local/bin/MyLed.py --led D6 --blink 1,1,15 &
fi
for BSSID in \${SSIDS[@]}
do
    # try associated: led OFF-ON-OFF-ON...
    SSID=\$(/sbin/wpa_cli scan_results | /bin/grep \$BSSID | awk  -F '\t' '{ print \$5; exit(0); }')
    echo "  \$SSID" | /bin/nc -w 2 localhost \$D_ADDR
    if /sbin/wpa_cli wps_pbc "\$BSSID" | /bin/grep -q CTRL-EVENT-CONNECTED
    then
        echo "CONNECTED" | /bin/nc -w 2 localhost \$D_ADDR
        if [ -x /usr/local/bin/MyLed.py ]
        then
            kill %1
        fi
	# on success this process will die on next call
        INTERNET
    fi
    # try next available SSID
    if [ -x /usr/local/bin/MyLed.py ]
    then
        /usr/local/bin/MyLed.py --led D6 --light ON
    fi
done

# try wifi AP
WLAN=\${1:-uap0}
ADDR=\${2:-192.168.2}
# led ON-OFF-OFF-OFF-ON ...
echo "<clear>NO INTERNET" | /bin/nc -w 2 localhost \$D_ADDR
if [ -x /usr/local/bin/MyLed.py ]
then
    kill %1
    /usr/local/bin/MyLed.py --led D6 --blink 1,5,30 &
fi
WIFI=$(/sbin/ifconfig -a | grep '^w.*: flag' | /usr/bin/head -1 | /bin/sed 's/:.*//') 
/sbin/iw dev \${WIFI} interface add "\${WLAN}" type __ap
/sbin/ip link set "\${WLAN}" address \$(ifconfig  | /bin/grep HWadd | /bin/sed -e 's/.*HWaddr //' -e 's/:[^:]*\$/:0f/')
/sbin/ifup uap0 2>/dev/null >/dev/null   # ignore already exists error
/usr/sbin/service dnsmasq restart
/sbin/sysctl net.ipv4.ip_forward=1
/sbin/iptables -t nat -A POSTROUTING -s 192.168.2.0/24 ! -d 192.168.2.0/24 -j MASQUERADE
/usr/sbin/service hostapd restart
/sbin/route del default dev uap0
sleep 5
echo "WiFi AP please login" | /bin/nc -w 2 localhost \$D_ADDR
/bin/grep -e 'ssid=...' -e wpa_passphrase= /etc/hostapd/hostapd.conf | /bin/sed 's/.*phrase/phrase/' | /bin/nc -w 2 localhost \$D_ADDR
EOF
    sudo cp /tmp/hostap$$ /usr/local/etc/start_wifi_AP
    sudo chmod +x /usr/local/etc/start_wifi_AP
    /bin/rm -f /tmp/hostap$$
    sudo sh -c /usr/local/etc/start_wifi_AP
    AddCrontab /usr/local/etc/start_wifi_AP
}

INSTALLS+=" BUTTON"
HELP[BUTTON]="Installation of script to watch button presses and feedback via connected led. Use GrovePi Adafruit switch/led or DIY button for this."
UNINSTALLS[BUTTON]+=" /usr/local/bin/MyLed.py"
# install button/led/relay handler
function BUTTON(){
    local MYLED=/usr/local/bin/MyLed.py
    if [ -x $MYLED ] ; then return ; fi
    GROVEPI                # depends on govepi
    sudo cp MyLed.py /usr/local/bin/
    sudo chmod +x $MYLED
    cat >/tmp/poweroff$$ <<EOF
#!/bin/bash
# power off switch: press 15 seconds till led light up constantly
# button socket on Grove D5, led socket on Grove D6
SOCKET=\${1:-D5}
LED=\${2:-D6}
MYLED=$MYLED
D_ADDR=2017
if [ ! -x \$MYLED ] ; then exit 0 ; fi
\$MYLED --led \$LED --blink 1,2,1
while /dev/true
do
    "\$MYLED" --led \$LED --light OFF
    TIMING=$("\$MYLED" --led \$LED --button \$SOCKET)
    TIMING=$(echo "\$TIMING" | /bin/sed 's/[^0-9]//g')
    if [ -z "\$TIMING" ]
    then
        sleep 5
        continue
    fi
    if [ -n "\${TIMING}" -a "\$TIMING" -gt 20 ]
    then
         echo -e "<clear>POWERED OFF\n   MySense\n                     ..Bye..                     " | /bin/nc -w 2 localhost $D_ADDR
        "\$MYLED" --led \$LED --blink 0.25,0.25,2 &
        /usr/bin/killall -r ".*MySense.*"
        /sbin/poweroff
    elif [ -n "\${TIMING}" -a "\$TIMING" -gt 10 ]
    then
         echo -e "<clear>REBOOT\n   MySense\n                     ..=|=..                     " | /bin/nc -w 2 localhost $D_ADDR
        "\$MYLED" --led \$LED --blink 0.25,0.5,2 &
        /usr/bin/killall -r ".*MySense.*"
        /sbin/reboot
    elif [ "\${TIMING}" -gt 5 -a -x /usr/local/etc/start_wifi_AP ]
    then
        echo -e "<clear>WiFi reset\n   WiFi WPA\n   WiFi WPS" | /bin/nc -w 2 localhost \$D_ADDR
        /usr/local/bin/MyLed.py --led \$LED --blink 0.25,1.25,1 &
        /usr/local/etc/start_wifi_AP
    fi
done
EOF
    /usr/bin/sudo /bin/cp /tmp/poweroff$$ $MYLED
    /usr/bin/sudo /bin/chmod +x $MYLED
    AddCrontab $MYLED
}

INSTALLS+=" WIFI_HOSTAP"
HELP[WIFI_HOSTAP]="Installation of WiFi Access Point service. Provides access via wifi to the Pi if the WiFi device supports this."
UNINSTALLS[WIFI_HOSTAP]+=' /etc/etc/hostapd/hostapd.conf'
UNINSTALLS[WIFI_HOSTAP]+=' /etc/systemd/system/hostapd.service'
# install hostapd daemon
function WIFI_HOSTAP(){
    local WLAN=${1:-uap0} SSID=MySense PASS=BehoudDeParel HIDE=1
    KeepOriginal \
        /etc//etc/hostapd/hostapd.conf \
        /etc/systemd/system/hostapd.service
    # if [ -f /etc/hostapd/hostapd.conf ]
    # then /usr/bin/sudo /usr/bin/apt-get remove --purge hostapd -y
    # fi
    DEPENDS_ON APT hostapd
    /usr/bin/sudo /usr/sbin/service hostapd stop
    # /usr/bin/sudo /bin/systemctl enable hostapd
    echo "wifi Access Point needs SSID (dflt ${SSID}) and" 1>&2
    echo "WPA password (dflt ${PASS}):" 1>&2
    read -t 15 -p "wifi AP SSID (dflt ${SSID}): " SSID
    read -t 15 -p "wifi AP WPA (dflt ${PASS}): " PASS
    read -t 15 -p "Need to hide the SSID? [Y|n]: " HIDE
    if [ -n "${HIDE/[Yy]/}" ] ; then HIDE=0 ; else HIDE=1 ; fi
    KeepOriginal /etc/systemd/system/hostapd.service
    /bin/cat >/tmp/hostap$$ <<EOF
[Unit]
Description=Hostapd IEEE 802.11 Access Point
After=sys-subsystem-net-devices-${WLAN}.device
BindsTo=sys-subsystem-net-devices-${WLAN}.device
[Service]
Type=forking
EnvironmentFile=-/etc/default/hostapd
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
macaddr_acl=0
ssid=${SSID:-MySense}
wpa_passphrase=${PASS:-BehoudDeParel}
ignore_broadcast_ssid=${HIDE:-0}
EOF
    /usr/bin/sudo /bin/cp /tmp/hostap$$ /etc/hostapd/hostapd.conf
    /bin/rm -f /tmp/hostap$$
}

INSTALLS+=" NEW_SSID"
HELP[NEW_SSID]="Installation of new WiFi SSID of WiFi Access Point at installation time (now)."
UNINSTALLS[NEW_SSID]+=' /etc/wpa_supplicant/wpa_supplicant.conf'
# add wifi ssid/WPA password to enable $WIFI for internet access via wifi
function NEW_SSID(){
    GetInterfaces
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
        WLAN=$WIFI
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
        New_SSID ${WLAN}
        return
    fi
}
#New_SSID

if [ -n "$1" ] && [ "$1" = help -o x"$1" = x--help -o x"$1"  = x-h ]
then
   echo "Usage:
INSTALLS.sh will make the Pi ready for installing MySense.py by downloading and installing
all Python dependencies en services for MySense.py.
For the OS changes are available: $INSTALLS
For plugins are available: $PLUGINS
For extra\'s: $EXTRA
Calling INSTALL.sh without arguments will install all.
"
    exit 0
fi

MODS=$@
if [ -z "$MODS" ]
then
    MODS="$INSTALLS $PLUGINS $EXTRA"
fi

if ASK UPDATE ; then UPDATE ; fi
for M in $MODS
do
    # TO BE ADDED: check config if the plugin is really used
    case M in
    mysql|MySQL) M=MYSQL
    ;;
    INFLUX*) M=INFLUX
    ;;
    esac
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
        if ASK ${M^^}
        then
            if ! ${M^^}
            then
                echo "FAILED to complete needed modules/packages for My${M^^}.py." 1>&2
            fi
        else
            echo "Installation of ${M^^} skipped."
        fi
    else
        echo "Unknow plugin for $M. Skipped." 1>&2
    fi
done
