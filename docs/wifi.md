2017/02/27
### Status
Operational 2017/3/13

# How To enable Raspberry Pi wifi
## Use `INSTALL.sh WIFI` to do a tested set up:

INSTALL.sh configures wifi as follows:
1. Try wired internet connectivity on eth0. If this fails:
2. Try wireless wifi on wlan0 and use SSID/WPA from configuration for internet connectivity. If this fails:
3. Try WPS (press WPS on your router on a (re)boor of the Pi. If this fails:
4. Create a wifi AP point.
Wifi Access Point (MySense/BehoudDeParel) is only activated if wifi-client was not able to do a succesfull wifi AP association.
Use ssh or webmin (`https:192.168.2.1:10000`) to change the SSID and/or WPA in `/etc/wpa_supplicant/wpa-supplicant.conf` wifi configuration file.

TO DO:
Pi LED RED will be ON if there is no internet connectivity. Led will be ON/OFF while searching for a wifi association.
Press WPS to redo an association.

## Pi Wifi hardware
Pi 3 has an embedded wifi chip. The wifi chip is quit sensative. For older versions of the Pi you may use a good wifi dongle (USB wifi). With a wifi dongle one may need for wifi Access Point the hostapd from itwelt.org: `wget itwelt.org/downloads/hostapd`

## Pi wifi manual configuration
* From: http://www.raspberryconnect.com/network/item/315-rpi3-auto-wifi-hotspot-if-no-internet
* From: https://www.raspberrypi.org/documentation/configuration/wireless/wireless-cli.md

The next is much dependent on Pi *Jessie* distribution. Use the installaion `INSTALL.sh WIFI` if you want to avoid the manual installation.

Unsolved: was not able to have both wlan0 configured as wifi-client and a virtual wifi linked to wlan0 as wifi Access Point. Configuration went ok but as soon as hostapd is launched the wifi-client stopt forwarding packeges to the kernel.

Network connections are managed via configurations files e.g. network interfaces, wifi supplicant, host access points, dns masquarete, etc.
Make sure you copy before you make changes of these files for a backup:
```shell
    for FILE in \
        /etc/network/interfaces \
        /etc/wpa_supplicant/wpa_supplicant.conf \
        /etc/hostapd/hostapd.conf \
        /etc/systemd/system/hostapd.service \
        /etc/dnsmasq.conf
    do if [ -f $FILE ]
    then
        if ! [ -f $FILE.orig ] ; then sudo cp $FILE $FILE.orig ; fi
    fi
    done
```
This readme will describe some methods to use wifi with MySense:

* The MySense Pi is only connected with an UTP cable to Internet (skip this readme).
* The MySense Pi is connected with wifi to the internet. Add `network={}`  with SSID and password to the file `/etc/wpa_supplicant/wpa_supplicant.conf`. This as mentioned earlier. You can define more wifi internet access points `network={}` if you want to.
* The Pi3 uses automatically wifi and/or the UTP eth0 internet connection.
The INSTALL.sh script will give preceedence to wired and bring wifi-client down.
* You may want to use a combination of this all: wired, wifi-client and access point: only possible with a wifi USB dongle.

If you want to reach the Raspberry Pi MySense remotely via internet, see the how to example for access via ssh-tunneling or the Weaved free service, see the `README.pi.md` for the instructions. Be aware that this is a *backdoor*. But it can ease your live for remote updates and access from anywhere via `ssh`. A backdoor has privacy issues!

### Internet access via wifi
The headless Raspberry Pi 3 can be reached via wifi *nearly* out of the box. So you can the Pi via ssh (Putty) using user name `pi` and password `raspberry`.
In this case  *first* you should prepair the SIM filesystem separately and push the changed file back into the Pi. Detect the IP address of the PI and use `ssh` or `Putty` to get into the Pi.

#### Enabling wifi internet access
Change the file `/etc/wpa_supplicant/wpa_supplicant.conf` and add
```
network={
        ssid="MySSID"       <--- use the wifi SSID name
        psk="MyWifiPass"    <--- use the WPA password of your wifi"
        key_mgmt=WPA-PSK    <--- default WPA-Personal for home networks
        proto=RSN
        pairwise=CCMP
        auth_alg=OPEN
}
```

### Raspberry Pi wifi as Access Point
The next describe the configuration setup to use the wifi as a single wifi service: a wifi Access Point. This is not a wifi setup to connect via wifi the internet.
The setup is done via a virtual (second) wifi `wlan1` configuration as access point.

This enables you to access the sensor for configuration setups via eg `ssh` or `Putty`. But also to use the Pi as wifi internet access point.
After this configuration process you will see e.g. MySense appearing on the wifi access point list on your laptop.

* This is based on: https://gist.github.com/Lewiscowles1986/fecd4de0b45b2029c390

Think up a wifi access name e.g. `MySense` and wifi WPA2 password e.g. `BehoudDeparel`

The install script `INSTALL.sh WIFI` may be of help to you as well for wifi configurations.

#### (virtual) Access Point
If you do not use a Pi please check your wifi USB dongle if it is able to manage virtual wifi devices: `sudo wi wlan0 list` and look for the lines at the bottom for `valid interface combinations`, see [usb-wifi wifi-client AND Access Point](http://www.0xf8.org/2016/02/using-your-raspberry-pi-zeros-usb-wifi-adapter-as-both-wifi-client-and-access-point/).

Manual evaluation setup (this will not survive a reboot):
Here we use *wlan1* as virtual wifi device name. Check with `ifconfig wlan0` the MAC address of the _wlan0_ device. Add eg 1 to the MAC address as MAC address for wlan1 e.g. b8:27:eb:4d:96:65 -> b8:27:eb:4d:96:66).
```bash
    ifconfig wlan0 | grep HWaddr      # gives you MAC address + 1 for wlan1
    sudo iw phy phy0 interface add wlan1 type __ap
    sudo ip link set wlan1 address b8:27:eb:4d:96:66 # change this MAC
    sudo ip a add 10.0.0.1/24 dev wlan1
    sudo ip link set dev wlan1 up
    ifconfig    # this should show wlan0 and wlan1
```
You should add the iw and ip parts in an executable shell file e.g. `/etc/network/if-up.d/virtual_wifi` if virtual wifi device should survive a reboot.

#### Access Point daemon
Think up an SSID (eg MySense) and password (eg BehoudDeParel) for the new wifi Access Point.
You need to install `hostapd` (wifi access point daemon) and eg `dnsmasq` (DNS and IPV4 address service):
##### hostapd daemon
You can use the install script `./INSTALL.sh WIFI_HOSTAP wlan1` or do it manually:
```bash
    # purge what is already there so we do not mix up things
    sudo cp /etc/systemd/system/hostapd.service /etc/systemd/system/hostapd.service.orig
    sudo cp /etc/hostapd/hostapd.conf /etc/hostapd/hostapd.conf.orig
    sudo apt-get remove --purge hostapd -y
    sudo apt-get install hostapd -y
    sudo service isc-dhcp-server stop
    sudo systemctl disable isc-dhcp-server
```
Configure hostapd: create `/etc/systemd/system/hostapd.service`, with SSID (MySense)/password (BehoudDeParel):
```
[Unit]
Description=Hostapd IEEE 802.11 Access Point
After=sys-subsystem-net-devices-wlan1.device
BindsTo=sys-subsystem-net-devices-wlan1.device
[Service]
Type=forking
PIDFile=/var/run/hostapd.pid
ExecStart=/usr/sbin/hostapd -B /etc/hostapd/hostapd.conf -P /var/run/hostapd.pid
[Install]
WantedBy=multi-user.target
```
Create `/etc/hostapd/hostapd.conf` with:
```
interface=wlan1
hw_mode=g
channel=10
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
ssid=MySense                   <--- to be changed
wpa_passphrase=BehoudDeParel   <--- to be changed
```
If you want yout SSID hidden add the next line to this hoasap config file:
```
ignore_broadcast_ssid=1
```

##### dnsmasq
Dnsmasq daemon is easier as the  standard companion isc-dhcp-server.

* Install dnsmasq
You may use the install shell script `./INSTALL.sh DNSMASQ wlan1 10.0.0` or do it manually:
```bash
    sudo service isc-dhcp-server stop
    sudo systemctl disable isc-dhcp-server
    sudo apt-get install dnsmasq -y
```
and configure dnsmasq: create a new `/etc/dnsmasq.conf`
```bash
    sudo cp /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
    # edit and change /etc/dnsmasq.conf for the following lines:
    sudo nano /etc/dnsmasq.conf
interface=wlan1
# access for max 4 computers, max 12h lease time
dhcp-range=10.0.0.2,10.0.0.5,255.255.255.0,12h
```
Edit the file `/etc/network/interfaces` and delete (or better comment the old wlan1 one out):
```bash
    sudo cp /etc/network/interfaces /etc/network/interfaces.orig
    sudo nano /etc/network/interfaces
```
and create a sub IP4 net (10.0.0.1/24) (use *wlan1* (virtual wifi) iso wlan0) to:
```
    allow-hotplug wlan0
    iface wlan1 inet manual
        wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf
    # Added by rPi Access Point Setup
    allow-hotplug wlan1
    iface wlan1 inet static
        address 10.0.0.1
        netmask 255.255.255.0
        network 10.0.0.0
        broadcast 10.0.0.255
```
Now enable hostapd/dnsmasq service by the commands:
```bash
    systemctl enable hostapd
    systemctl enable dnsmasq
```
The wifi access should be active and visible after a reboot.
Enable on your laptop wifi to `MySense` and access it via `ssh pi@10.0.0.1`
If you want to make the Pi invisible: just add the following line

If you reboot now and have also eth0 connected to the same router you may first do the next.

#### NAT (IP4 Network Address Translation)
Raspberry Pi wifi AP as internet router. You need eg a fixed UTP line eg eth0 (or install also a wifi P2P-client) to an internet router.
Your Raspberry Pi will act as an access point to internet.
You may use the install shell script `./INSTALL.sh NAT wlan1 wlan0` (wlan1 is the AP virtual wifi, wlan0 or eth0 (?) as internet connection.

Or do it manually:

If needed you can install iptables with: `sudo apt-get install iptables`

Setting up NAT will allow multiple clients to connect to the WiFi (not needed for MySense).
If needed edit `sudo nano /etc/sysctl.conf` and add the line at the bottum:
```
    net.ipv4.ip_forward=1
```
You can activate this immediately by issuing:
```bash
    sudo sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
```
And (!) forward the connection packages to either eth0 (LAN) or wlan1 when connected to internet via wifi:
```bash
    sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    sudo iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
    sudo iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT
```
If this behaves as expected make the rules to survive a reboot (as root):
```bash
    iptables-save > /etc/firewall.conf
    echo "#!/bin/sh" > /etc/network/if-up.d/iptables 
    echo "iptables-restore < /etc/firewall.conf" >> /etc/network/if-up.d/iptables 
    chmod +x /etc/network/if-up.d/iptables
```
