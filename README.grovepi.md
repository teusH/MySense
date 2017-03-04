# GrovePi shield
This shield saves a lot of soldering and connection errors. But it costs some extra as well more software installation.
Make sure you update the shield to the latest firmware for GrovePi.

Kiwi electronics GrovePi+ € 35.-
Advise: buy a Grove-relay € 5.- for test and maybe fan switch purposes.
and maybe a I2C hub (€ 3.50) for adding I2C devices in a chain and some wiring packs (€ 5.- 4-pin conversion and or 4-pin cables pack say 30 cm).

## Manual configuration
* See: https://www.dexterindustries.com/grovepi-tutorials-documentation/

### Installation
* https://www.dexterindustries.com/GrovePi/get-started-with-the-grovepi/setting-software/
```shell
    mkdir -p git ; cd git
    git clone https://github.com/DexterInd/GrovePi
    cd GrovePi/Script
    chmod +x install.sh
    sudo ./install.sh
```
Some modules may have been already installed.

2017/02/17 installer said:
```
The script will download packages which are used by the GrovePi+. Press “y” when the terminal prompts and asks for permission to start the download.
Installs package dependencies:
   - python-pip       alternative Python package installer
   - git              fast, scalable, distributed revision control system
   - libi2c-dev       userspace I2C programming library development files
   - python-serial    pyserial - module encapsulating access for the serial port
   - python-rpi.gpio  Python GPIO module for Raspberry Pi
   - i2c-tools        This Python module allows SMBus access through the I2C /dev
   - python-smbus     Python bindings for Linux SMBus access through i2c-dev
   - python3-smbus    Python3 bindings for Linux SMBus access through i2c-dev
   - arduino          AVR development board IDE and built-in libraries
   - minicom          friendly menu driven serial communication program
Clone, build wiringPi in GrovePi/Script and install it
Removes I2C and SPI from modprobe blacklist /etc/modprobe.d/raspi-blacklist.conf
Adds I2C-dev, i2c-bcm2708 and spi-dev to /etc/modules
Installs gertboard avrdude_5.10-4_armhf.deb package
Runs gertboard setup
   - configures avrdude
   - downloads gertboard known boards and programmers
   - replaces avrsetup with gertboards version
   - in /etc/inittab comments out lines containing AMA0
   - in /boot/cmdline.txt removes: console=ttyAMA0,115200 kgdboc=ttyAMA0,115200 console=tty1
   - in /usr/share/arduino/hardware/arduino creates backup of boards.txt
   - in /usr/share/arduino/hardware/arduino creates backup of programmers.txt

The installer asks to restart the Pi.
```
Now when the Raspberry pi is powered down, stack the Grove Pi on top of the Raspberry Pi.  Ensure that the pins are properly connected before powering the Raspberry Pi.
GrovePi shield has 26 pins, the Pi has 40 pins. If you have the pins of both upwards and pins to the bottom: you should have 7*2 pins unshielded (free) at the left side.
Be carefull not to destroy by force the micro SDmemcard!

Power on the Raspberry Pi.  A green light should power up on the GrovePi+. 
Final check: the Raspberry Pi is able to detect the Grove pi: run i2cdetect
```shell
    sudo i2cdetect -y 1 # use 0 if your shiled is sold before Oct 2012
```
If you can see a “04” in the output, this means the Raspberry Pi is able to detect the GrovePi.

To test the GrovePi with a simple module: connect eg a Grove Relay to port D4. Relay is normally open, relay led will blink when closed and a click is sounded. 
```shell
    cd GrovePi/Software/Python
    sudo python grove_relay.py (switches relay on for 5 seconds)
```
### firmware upgrade
Some newer Grove modules need the latest GrovePi firmware so update the GrovePi firmware via the instructions of:
* https://www.dexterindustries.com/GrovePi/get-started-with-the-grovepi/updating-firmware/
Before you upgrade the firmware remove all modules to the GrovePi.

The upgrading software relies on the fact that GrovePi git software in installed at /home/pi/Desktop/GrovePi/
