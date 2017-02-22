#!/bin/bash
# installation of modules needed by MySense.py
#
# $Id: INSTALL.sh,v 1.2 2017/02/16 19:38:21 teus Exp teus $
#

echo "You need to provide your password for root access.
Make sure this user is added at the sudoers list." 1>&2
#set -x

echo "Updating/upgrading current OS installation and packages?" 1>&2
read -p "Try to update? [N|y]:" -t 10 READ
if [ -n "$READ" -a "$READ" = y ]
then
    sudo apt-get update
    sudo apt-get upgrade
    sudo apt-get dist-upgrade
    sudo apt-get autoremove
fi

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
        if !  sudo apt-get install python-pip
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
            sudo /usr/bin/pip -q install -e "git+https://github.com/${PROJ}#egg=${PKG}"
            if [ -d src ]
            then
                sudo chown -R $USER.$USER src/${PKG,,}
            fi
        else
            sudo /usr/bin/pip -q install "$MOD"
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
            if ! sudo /usr/bin/apt-get -y -q install "${2,,}"
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

INSTALLS='USER'

function MYSENSE(){
    return $?
}

INSTALLS+=" DB"
function DB(){
    DEPENDS_ON apt python-mysql.connector
    # mysql shell client command
    DEPENDS_ON  apt mysql-client
    # DEPENDS_ON apt mysql-navigator # GUI not really needed
    return $?
}

INSTALLS+=" DHT"
function DHT(){
    if [ ! -x /usr/local/bin/set_gpio_perm.sh ]
    then
        echo "Create the file eg /usr/local/bin/set_gio_perm.sh with the content:"
        cat >/tmp/perm.sh <<EOF
#!/bin/sh
# add as super user to crontab -e
# @reboot      /usr/local/bin/set_gpio_perm.sh
chown root:gpio /dev/gpiomem
chmod g+rw /dev/gpiomem
EOF
        chmod +x /tmp/perm.sh
        sudo mv /tmp/perm.sh /usr/local/bin/set_gpio_perm.sh
        sudo chown root.root /usr/local/bin/set_gpio_perm.sh
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

INSTALLS+=" THREADING"
function THREADING(){
    #DEPENDS_ON pip threading
    return $?
}

INSTALLS+=" DYLOS"
function DYLOS(){
    #DEPENDS_ON pip serial
    return $?
}

INSTALLS+=" GPS"
function GPS(){
    echo "Installing GPS daemon service"
    DEPENDS_ON apt gpsd         # GPS daemon service
    #DEPENDS_ON apt gps-client   # command line GPS client
    DEPENDS_ON apt python-gps   # python client module
    return $?
}

INSTALLS+=" GSPREAD"
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

INSTALLS+=" MQTTSUB"
function MQTTSUB(){
    #DEPENDS_ON pip paho-mqtt    # mosquitto client modules
    DEPENDS_ON apt python-mosquitto
    return $?
}

INSTALLS+=" MQTTPUB"
function MQTTPUB(){
    #DEPENDS_ON pip paho-mqtt    # mosquitto client modules
    DEPENDS_ON apt python-mosquitto
    return $?
}

INSTALLS+=" MQTT"
function MQTT(){
    echo "Installing Moquitto broker"
    echo README.mqtt for authentication provisions
    #DEPENDS_ON apt mqtt
    DEPENDS_ON apt mosquitto
    return $?
}

INSTALLS+=" GROVE"
function GROVE(){
    if pip list | grep -q smbus ; then return ; fi
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
    sudo ./install.sh
    cd ..
    echo "Please reboot and install the Grove shield"
    echo "Run sudo i2cdetect -y To see is GrovePi is detected."
    return
}

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
    sudo touch /dev/null
    echo "Adding user  $USER and password"
    sudo adduser $USER 
    sudo passwd $USER
    sudo adduser $USER gpio
    sudo adduser $USER dialout
    echo "$USER ALL=(ALL) PASSWD: ALL" >/tmp/020
    sudo cp /tmp/020 /etc/sudoers.d/020_${USER}-passwd
    rm /tmp/020
    sudo chmod 440 /etc/sudoers.d/020_${USER}-passwd
    sudo update-rc.d ssh enable
    sudo service ssh restart
}

MODS=$@
if [ -z "$MODS" ]
then
    MODS="$INSTALLS"
fi
for M in $MODS
do
    # TO BE ADDED: check config if the plugin is really used
    if echo "$INSTALLS" | grep -q -i "$M"
    then
        if [ "${M^^}" = USER ]
        then
            echo "Looking for USER and install USER home dir setup:"
        else 
            echo "Plugin My${M^^}.py looking for missing modules/packages:" 
        fi
        if ! ${M^^}
        then
            echo "FAILED to complete needed modules/packages for My${M^^}.py." 1>&2
        fi
    else
        echo "Unknow plugin for $M. Skipped." 1>&2
    fi
done
