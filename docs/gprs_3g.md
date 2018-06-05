<img src="images/MySense-logo.png" align=right width=100>

# 3G / GPRS internety connectivity
How to setup internet connectivity via a dongle and be able to receive or send SMS messages.

## STATUS
operational 2018/05/05

## DESCRIPTION
Huawei E3531 HSPA USB stick
<img src="images/HuaweiE3531.png" align=left width=100>

### How to set up 3G/GPRS dongle
Use in this setup is the Huawei E3531 HSPA+USB stick € 34.00. A prepaid SIM card (KPN mobile) was obtained from a store for € 1.00. To be loaded when needed so. To Do: estimation of data costs.

The SIM card needs to be activated before you continue via any mobile phone: an SMS message if activated is sent by the provider. Suggested is to configure the SIM card not requiring the SIM code (default 0000) on every power ON. See below for a how to.

The Huawei operate in two modes: modem mode (`/dev/gsmmodem` is present) and storage mode (the dongle is accessable as memory stick with e.g. Linux driver). If the command `lsusb` shows HPSA with the Huawei entry it is in modem mode.

You may use SMS messages to do small remote commands or send SMS with location details when powered up.


## sending SMS messages
* from: https://escapologybb.com/send-sms-from-raspberry-pi/
```shell
apt-get install gammu
sudo gammu-config
```
Gammu settings:
```
Port: /dev/gsmmodem
Connection: at19200
Model: empty
Synchronize time: yes
Log file: leave empty
Log format: nothing
Use locking: leave empty
Gammu localisation: leave empty
```
Identify the dongle: `gammu --identify`

Sending an SMS:
```
echo "test" | sudo gammu sendsms TEXT 06123456789
```
## Huawei modem installation
There is quite some material to be found with installation instructions.
They differ a small bit. With some we had success. With some not.

Essential is that the Huawei dongle will identify itself (use `lsusb` in two different modes: boot the Pi with the dongle inserted (cold installation) you will find the dongle in HSPA modem mode. Remove the dongle and insert it again and the dongle is in storage mode. Modem mode: `/dev/gsmmodem` is created. The modem may be found on `/dev/ttyUSB0`, better is to identify the port via `/dev/serial/by-id/` or `/dev/gsmmodem` (your dongle is in modem mode). Avoid to use `/dev/ttyUSB0` in your scripts.

The needed tooling:
```shell
apt-get install ppp usb-modeswitch usb-modeswitch-data wvdial gammu
```

### installation tactic 1 (success)
* https://github.com/EMnify/doc/wiki/How-to-use-a-Huawei-E3531-in-Modem-Mode

Identify manufacturere ID and producs ID via `lsusb`, something like `12d1:1f01`.
Create file `12d1:1f01` in `/etc/usb_modeswitch.d` with:
```
# Huawei E353 (3.se)

TargetVendor=  0x12d1
TargetProduct= 0x1f01 

MessageContent="55534243123456780000000000000011062000000100000000000000000000"
NoDriverLoading=1
```
and reboot the Pi: `sudo reboot`.

Verify if the GSM modem is recognized: `dmesg | grep USB`

Add new interface *gprs* in `/etc/network/interfaces.d/gprs`:
```
auto gprs
iface gprs inet ppp
provider gprs
```

Create provider *gprs* in `/etc/ppp/peers` with:
```
user "ios"
connect "/usr/sbin/chat -v -f /etc/chatscripts/gprs -T em"
/dev/gsmmodem
noipdefault
defaultroute
replacedefaultroute
hide-password
noauth
persist
usepeerdns
```
And check if the interface comes up: `ifup gprs` and monitor it via the system logging.
If wifi or lan connection is up this will fail and if not stopped (`ifdown gprs`) it will try to bring up ppp again and again.
On success you will see `ifconfig` the interface ppp0.
For details see the logging `/var/log/syslog`.

### installation tactic 2 (no success)
* https://nicovddussen.wordpress.com/2014/11/12/setting-up-your-raspberry-pi-to-work-with-a-3g-dongle/
```shell
apt-get install usb-modeswitch wvdial screen
```

Reboot with dongle plugged in and see if the Huawei is present `lsusb`: Huawei HSPA modem: it is in CD mode (the dongle has driver installation software also for Linux on board but not for Pi). `ifconfig -a` will show all interfaces available.
For the 3G dial-up the link file `/dev/gsmmodem` is required. And probably is not present.
Unplug the USB connection and plug in again: `lsusb` command should list it without the HSPA modem string, so not in modem mode. Run `ifconfig -a`
and it should show a new interface `wwan0` and `/dev/gsmmodem` should link to `ttyUSB0`. The modem is activated.

The dial process is done via `wvdial`, edit `/etc/wvdial.conf`:
```
[Dialer Defaults]

Init1 = ATZ
Init2 = ATQ0 V1 E1 S0=0 &C1 &D2 +FCLASS=0
Init3 = AT+CGDCONT=1,”IP”,”internet”
Stupid Mode = 1
Modem Type = Analog Modem
ISDN = 0
Phone = \*99#
Modem = /dev/gsmmodem
Username = { }
Password = { }
Baud = 460800
```
On success `ifconfig` will show `ppp0` as interface with an ip number.

### installation tactic 3 (no success)
* https://www.thefanclub.co.za/how-to/how-setup-usb-3g-modem-raspberry-pi-using-usbmodeswitch-and-wvdial

Needed software:
```shell
sudo apt-get install ppp usb-modeswitch wvdial
```

One need the modem switching codes for storgae mode and USB modem mode.o1. Power the Pi OFF. Connect the USB dongle and power ON without LAN or WiFi connection. Enter `lsusb` and note the manufacturer ID '12d1' and product ID '1f01' (DefaultProduct value).
2. Reboot and issue `lsusb` again. The product ID should be different: the TargetProduct value.

Now we create a usb_modeswitch config file: `/etc/usb_modeswitch.conf` and add (replace your product ID found with lsusb!):
First extract the product ID predefined items:
```shell
cd /tmp
tar -xzvf /usr/share/usb_modeswitch/configPack.tar.gz 12d1\:1f01
```
Edit the extracted file and replace code with TargetProducts vale found in step 2.
The values we are interested in are: `TargetVendor=` and `MessageContent?=`
Now we have Default and Target Vendor and Product ID's and one or more MessageContent definitions. We add those elements to `/etc/usb_modeswitch.conf`:
```
DefaultVendor=0x12d1
DefaultProduct=0x1f00   <--- change this

TargetVendor=0x12d1
TargetProduct=0x1f00    <--- change this

<---------- change next message content lines
MessageContent="5553424312345678000000000000061e000000000000000000000000000000"
MessageContent2="5553424312345679000000000000061b000000020000000000000000000000"
MessageContent3="55534243123456702000000080000c85010101180101010101000000000000"
```

Finally we create the vwdial file `/etc/wvdial.conf`:
```
[Dialer 3gconnect]
Init1 = ATZ
Init2 = ATQ0 V1 E1 S0=0 &C1 &D2 +FCLASS=0
Init3 = AT+CGDCONT=1,"IP","internet" <--- change internet to providers APN
Stupid Mode = 1
Modem Type = Analog Modem
ISDN = 0
Phone = *99#  <--- may need to change this phone number to connect
Modem = /dev/gsmmodem
Username = { } <--- may need to change this. {} is blank
Password = { } <--- may need to change this
Baud = 460800
```
Try to put the dongle in modem mode:
```shell
sudo usb_modeswitch -c /etc/usb_modeswitch.conf
```
And connect:
```shell
wvdial 3gconnect

## howto disable PIN CODE
If `/var/log/syslog` messages say ATD\*99# CME error the card needs  a pin or to be unlocked (?):

You may need to disable the sim pin. If so use AT commands to disable pin usage. Most SIM cards support this:
```
Let us assume the dongle is at /dev/gsmmodem. Note that the following command will not echo the characters typed in. Use the command `screen /dev/gsmmodem`:
```
ATZ     should return OK
AT+CPIN?        should return +CPIN: SIM PIN indicating pin is needed
AT+CPIN="xxxx"  where xxxx is your pin code 0000 by default
                should return OK
AT+CLCK="SC",0,"xxxx" replace xxxx by the pin code
and exit `screen` by `<cntrl>a` followed by `k` and `y`.
```

## howto unlock the dongle
If not successful the usb modem may need to be unlocked.
To unlock:
```
AT\^CARDUNLOCK="<Unlock Code>"
OK
```
You can find unlock code(s) via Google.

