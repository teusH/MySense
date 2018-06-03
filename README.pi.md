## Raspberry PI Jessie or Stretch configuration
2017/01/17
STATUS: BETA operational local

### Pi 3
Rasberry Pi basisbundel (incl behuizing, 2.5 A adapter, 16 GB micro card) € 65,-
Lunix versie Stretch
Power on with screen: change this if needed via raspi-config

FIRST: make a backup of the micro mem card on your desktop. So you can roll back.

### Pi Zero V1.3 and W V1.1
The Pi Zero is a tiny (half size) Pi3. Zero W V1.1 runs at the same speed as Pi3, has .5GB internal mem, uses less energy as Pi3, wifi, Bluetooth and has micro HDMI, micro USB for power and one micro USB only. The tiny board is only € 11.-.
The V1.3 has no buildin wifi and bluetooth.

Use a small micro USB (male) to full USB (female) cable and USB hub to connect USB devices to the board. If needed use small micro HDMI to full HDMI cable to use a screen with the Zero.

To Do: connection Check shell script need some work to support only one connected internet device.

### Installing latest Debian OS
See for simple how to: https://www.raspberrypi.org/documentation/installation/installing-images/

The Raspian Lite version is about 600Mb smaller as the desktop. The Lite version has no X-Window support and is ok to be used for a sensor kit. As well the Lite version makes less use of the SDcard and one has the possibility to configure a read only filesystem. So the lifetime of the filesystem is much increased as well a power off/on cycle is less likely to disrupt the filesystem.
Our preference due to the sensorkit focus is the latest Lite version.

The stepts to take to install the OS on the Pi within 10 minutes:
* download the zip file e.g. 20YY-MM-DD-raspbian-xyz.zip (2 or 5 GB) to your desktop
* insert a (empty) micro SD card in your desktop probably with a Micro SD aapter.
* download *etcher* from `https://etcher.io/` on your desktop
* start *etcher* and use the zip file as input, flash the SD card
* disconnect the SD adapter, and insert the micro SD card into the Pi
* connect the Pi to internet cable, HDMI monitor, and keyboard (mouse)
* connect the Pi to power
* login as user *pi* and password *raspberry*
* make sure you have internet access: `ifconfig` (write down Pi internet address) or `ping -c 2 8.8.8.8`
* enable ssh remote login: `sudo update-rc.d ssh enable ; /etc/init.d/ssh restart`
You should be able to install everything from remote by now.
* or: use `sudo raspi-config` command and define: host name, change pi password, set timezone, change the key board type to yours, in interfaces enable spi, i2c.
* with internet connectivity use `apt-get update`, `apt-get upgrade`, `apt-get dist-upgrade` and `apt-get autoremove` to bring the Debian OS up to date.
* add user `ios`

Make sure you check the keyboard settings on the console by pressing keys like `|` and `~` on the keyboard.

### HEADLESS Pi
No console no screen to the Pi well no problem.
Power on the Pi. Make sure the Pi is connected with a cable to your router.
Try to find the IP address eg via the command "arp -n" something as 192.168.0.34
Connect via ssh: ssh pi@192.168.0.34 use deflt password raspberry
If you are heading for a wireless (wifi) Pi? You have to set up some configuration
on the SD first: see http://dougbtv.com/2016/03/06/raspi-3-headless-wifi/

Only in the development and test phase one may need a screen and keyboard. In operational phase MySense will operate headless. Turning off the power on the HDMI will save ca 20 mA:
```bash
    vcgencmd display_power 0 # turns off the screen
    vcgencmd display_power 1 # turns on the screen
```
More on vcgencmd see http://www.elinux.org/RPI_vcgencmd_usage

### Pi firmware upgrade
Most common issue's like stalling of the LAN adapter, issues with USB FTDI adapters and SD card compatibility with Raspberry Pi is an outdated firmware.
To do a firmware update: `sudo rpi-update` followed by `sudo apt-get upgrade`.
And `sudo reboot` your Raspberry Pi.
See also: `https://github.com/Hexxeh/rpi-update`.

Troubleshooting:
If your download of the update seems to stall (1-2kb/s download) do the following:
```bash
sudo rm -rf /root/.rpi-firmware
sudo rpi-update
```
The complete update should take about 10 minutes (depending on your internet connection)

### serial connection
If you need 2 serial basic (TTL UART) serial connections for modules it is possible with some tuning. See https://spellfoundry.com/2016/05/29/configuring-gpio-serial-port-raspbian-jessie-including-pi-3/ for some instructions. You may need to lower slightly the CPU speed for `/dev/ttyS0`. See *tips and tricks* below for more info on this.

If you use USB serial cables from the same manufacturer one may have trouble to instruct MySense which USB port has which USB connected sensor module.

### Pi energy and USB power consumption
The Pi uses not much energy. Every USB port uses about 500 mA. So one may run out of power quickly with too many USB socket usage. A USB hup consumes by itself also about 500 mA. Be aware that quite some low cost power enabled hub do feed power to the Pi. Do not use these faulty hubs. There are good hubs with own power supply up to 3A.

### USB serial port number
Any Linux OS will assign at boot time a `/dev/ttyUSBn`, where n is a number starting with 0, to the connected USB serial.
'n' however is might change on a reboot.
With `/dev/serial/by-id/` one *may* detect the USB port number (see the MySense conf part for the product id recognition).
E.g. the cheaper Prolific serial USB will show a serial zero ID.s
With the use of two or more USB serial connections advised is to use either different products or serial numbers or change the serial ID (EEPROM) of e.g. FTDI (Future Technologies) serial USB chip: see http://rtr.ca/ft232r/ for a how to.

A good way to assure with USB connection is which sensors it is suggested to define a udev rule set for each different USB adapter.
The following will use the Spec (SPEC) gassensors on one particular USB serial adapter. We do not use the `by-id` method in this case.

Use `lsusb` command to get an overview before and after the USB adapter is connected. Here the difference as example:
```
...
Bus 001 Device 009: ID 10c4:ea60 Cygnal Integrated Products, Inc. CP210x UART Bridge / myAVR mySmartUSB light
Bus 001 Device 008: ID 10c4:ea60 Cygnal Integrated Products, Inc. CP210x UART Bridge / myAVR mySmartUSB light
...
```
Denote the idProduct (e.g. "ea60") and idVendor (e.g. "10c4"). And create the following udev rule in in the file `/etc/udev/rules.d/50-Sensor.rules`:
```
ACTION=="add", KERNEL=="ttyUSB*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0660", GROUP="dialout", SYMLINK+="SPEC%n"
```
After a reboot do a test:
```shell
ls -l /dev/SPEC*
```
It should show something like:
```
lrwxrwxrwx 1 root root 7 May  9 16:31 /dev/SPEC1 -> ttyUSB1
lrwxrwxrwx 1 root root 7 May  9 16:31 /dev/SPEC2 -> ttyUSB2
lrwxrwxrwx 1 root root 7 May  9 16:31 /dev/SPEC3 -> ttyUSB3
```
MySense `MySPEC.py` will look for the available gas sensors in a similar way and will detect which gas sensor is attached via a look at the eeprom readout or serial number as is configured in MySense.conf.

### FIRST UPGRADE
You need for this to have an internet connection.
You probably do not need the package wolfram-engine (680 MB) so delete the package:
```shell
    sudo apt-get purge wolfram-engine
```
Startup and perform an upgrade:
```shell
    sudo apt-get update     # update package info
    sudo apt-get -y upgrade # upgrade all packages
    sudo apt-get dist-upgrade       # upgrade to latest system packages
    sudo apt-get autoremove # remove packages not longer needed
```

### FIRST CONFIG
initiate/command: `sudo raspi-config` and
if still needed expand the filesystem if one created new PI OS on mem card.
On a fresh boot with a new Pi OS the filesystem will be expanded automatically.
For now enable start with screen (disable this later) and configure the
localisation options:
```
    set language eg to nl_NL.UTF-8
    set timezone eg Europe/Amsterdam
    set keyboard layout: and check by pushing @-key and see key response.
    set WiFi country id to your country
```
Had to edit /etc/default/keyboard the "gb" setting into "us" as well.
On wifi failure please check `/etc/wpa_supplicant/wpa_supplicant.conf` e.g. country=NL. And if needed complete add a network definition with your SSID and PSK.

* Change the Pi default password!
```shell
pi% `passwd pi` -> acacadabra 
```
* You need internet connectivity to update the Stretch: `sudo apt-get update upgrade dist-upgrade`. This takes a while ... and finally `sudo apt-get autoremove`
* Allow to remotely login via ssh (or putty):
```shell
    sudo update-rc.d ssh enable
    sudo service ssh restart
```

Install *git* for the archive downloads from eg github:
```shell
sudo apt-get install git
```

Choose a project name: say BdP
 and Give the pi a nice host name e.g. name: bdp
```shell
sudo hostname bdp
sudo nano /etc/hostname #  and change raspberripi to bdp
```
Is there an internet connectivity? Try: `host 8.8.8.8   # The Google DNS server`

### INSTALL the MySense PROJECT

Download the tar (tgz) fite or clone it from github: 
```shell
sudo git clone https://github.com/teusH/MySense
```
Or use `tar`:
Copy the `MySense.tgz` into the pi user home directory. Unpack the tar file (`tar xzf MySense.tgz`)
Use the `INSTALL.sh` shell file to install all dependent libraries and modules (try: `./INSTALL.sh help`.

### Remote desktop:
Install vnc: `sudo apt-get install tightvncserver`
and start the server: `tightvncserver`. You need to enter some passwords and remember them!
And start a session: `vncserver :0 -geometry 1920x1080 -depth 24`.
You should be able to get a desktop from remote e.g. Apple laptop: start "finder" and
make sure you enabled screen share on your Apple:
Menu item: `Go -> Connect to server ...  vnc://xxx.xxx.xxx.xxx`

### BACKDOOR
You probably want to get in touch with the node for remote management. Make sure you are allowed to walk around on the local network...

The following creates a backdoor :-( to the Pi via internet cloud.
Use `ssh` or if the PI is behind a firewall/router one can use simply *weaved*, or use ssh tunneling or VPN.

#### Remot3.it (formerly Weaved)
Install `Weaved`:
Create an account with `weaved.com`: meToo@MyHost.io password a6LpWprG41LD
 and respond with email to verify the account configuration.
Next add your Pi system names names:
```
    name: PI_IoS-BdP_01
    SSH-Pi ssh port 28
    HTTP-Pi HTTP port 8088
```
On your desktop install:
```shell
    sudo apt-get install weavedconnected
    sudo vi /etc/sshd/config add port 28 and service sshd reload
    sudo weavedinstaller
```
    check: webbrowser login  with weaved.com login desk and push SSH-Pi: proxy/portnr
```
    ssh -l pi proxy??.weaved.com -p "35757"
    # on your Pi
    sudo crontab -e and add line:
        @reboot /usr/bin/weavedstart.sh
```
*notice*: everyone with weaved password or proxy/port (and so weaved.com)
*notice*: and  knowing PI login/passwd can log into your PI via ssh!

Or use *TeamViewer*, which is also free for private use.

#### Remote access via ssh tunneling
Maybe you should better use *ssh tunneling*. See for instructions the answer paragraph in StackExchange:
* https://raspberrypi.stackexchange.com/questions/34556/how-to-connect-to-the-raspberry-pi-through-3g-dongle

If one need to use GPRS: The 3G dongle we use is the Huawei E3531 HSPA+USB Stick (ca € 30.00).

### USERS:
Install Internet of Sense user say *ios* (full name Internet of Sense):
```shell
    sudo adduser ios
    sudo passwd ios
```
and add the user *ios* to `/etc/sudoers` list:
```shell
    sudo su
    echo "ios ALL=(ALL) PASSWD: ALL" >>/etc/sudoers.d/020_ios-passwd
```
and test in another window if login/sudo works for ios user before proceeding.
In this home dir please install all MySense sources, eg in the directory MySense.

### Install modules using github:
Install eg in IoS home dir: `git clone https://github.com/<module name>`.
change dir into github project name and use `python setup.py install` (see REAME.md)
For python 3 use the command python3.

### PYTHON:
Update first your Pi: `sudo apt-get update``
Install the *python installer*: `apt-get install python-pip`
Make sure you have the latest openssl: `sudo apt-get install python-openssl`

For other modules/libraries needed by the MySense.py script see README.mysense
The collection of apt-get install, pip install and github setup.py install
will install the needed modules.
    
### Pi may have USB serial failures :-(
The Pi with several USB connection may run out of energy. If so you will see intermittant USB serial failures. One way to solve this is to use a quality USBhub with own power adapter of say 2.5A.

### Pi3 may have I2C transfer timeouts :-(
While using transports of say 512 bytes via the I2C interface of the Pi3, the Pi3 may show "transfer timeout i2c-bmc2835" log errors. E.g. using the SSD1306 tiny display via the I2C bus may hang your process. It seems to be a (driver) hardware problem. Retsrat the process helps, but sometimes a reboot is needed. Yet unknown if there is a work around.

### Raspberry Pi tips and tricks
* the O'Reilly older book Raspberry Pi Hacks from Ruth Suehle and Tom Callaway:
https://books.google.nl/books?id=pdWQAwAAQBAJ&printsec=frontcover&hl=nl#v=onepage&q&f=false

## TO DO's
### securing the Pi
Make sure the default user/password is gone and local network is not served, see:
* https://makezine.com/2017/09/07/secure-your-raspberry-pi-against-attackers/
### hard reset the Pi
Use a watchdog to watch the PI for normal operation or "power cycle".
Use `bash INSTALL.sh WATCHDOG` to install a hardware monitor and watchdog deamon.
Ref:
* https://raspberrypi.stackexchange.com/questions/1401/how-do-i-hard-reset-a-raspberry-pi
### read only root FS
The Pi SD card may be corrupted by disconnecting the power adapter without a proper `poweroff`. To avoid this and to increase the lifetime of the SD card a readonly root filesystem is advised in the operating phase. See https://ferdinandkeil.com/read-only-filesystem-for-raspberry-pi.html for a how-to.

Adafruit made a shell script available to configure a read-only fs on Debian Lite version. Other OS distr may work but one need to disable X11.
The script:
* https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/read-only-fs.sh

### remote Pi configuration
Best way is to use ssh via WiFi of Lan. Enabling the WiFi Access Point is also a good way. However this requires some Linux system adminstration skills. Initially one may only need to change the WiFi SSID and passphrase. Use ssh to access the WiFi Pi Access Point service and edit the file `/etc/wpa_supplicant/wpa_supplicant.conf` for this.

Other ways:
* https://github.com/peebles/rpi3-wifi-station-ap
* https://pifi.imti.co/ This uses Docker and json as wifi configuration interface.
* https://github.com/billz/raspap-webgui A web GUI for configuring the Pi.
