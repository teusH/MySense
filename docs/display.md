2017/06/16
### Status
Operational 2017/6/17

# How To display text on Adafruit mon display
* Use `INSTALL.sh DISPLAY` to install the script and dependences.

The script has three modules:
* display server: which uses Adafruit lib and driver to receive text and display the text on the little Adafruit SSD1306 display. Try the command `./MyDisplayServer.py -help` to see all the options and command arguments. The server is multithreaded.
The DISPLAY service should be run as deamon. Add `@boot path/MyDisplayServer.py start`  e.g. to crontab of root.
* a client which is an example to send text to the display server/service on `localhost TCP/IP port 2017`.
* an output channel to send console type of measurement results to the little display. Use the plugin `MyDISPLAY.py`

The service can be used to send text to the small display to provide visual feedback for Pi operations, e.g. logging, poweroff messages, etc.

### To Do
* Add <text>, <clear> xml to the text to define font and text size changes, clear the display, etc.
* use the Richard Hull's luma modules.

### hardware
* Adafruit SSD1306  display  € 22.85 (Kiwi or SOS Solutions) or via China: € 2.-.
* GPIO: Cables to hook it up to 3.3V, Gnd, GPIO as follows:
* you need to enable GPIO on the Pi, as well add the DISPLAY service user to the `gpio` group.
```
For the 1306 Oled GPIO version:
*Pi3*       cable  *SSD1306*
type PINnr  color  id
----------------------------
3.3V    1   red    VDD (Vin)
GND     6   black  GND
GPIO23 16   green  DC
GPIO24 18   blew   RES (RST)
MOSI   19   purple SDA (DATA)
SCLK   23   orange SCK (CLK)
CEO    24   yellow CS
```
Note: If you use GrovePi shield, use the Oled I2C version!
* I2C: use the Grove Oled (need GrovePi shield and standard 4-wire cable) or I2C version (need to soldier the cable)
* The I2C version uses I2C address *3C*. Check this by running `i2cdetect -y 1`

### Pi installation
You need to enable GPIO (Oled GPIO version with 7 cables) abd I2C (Oled I2C version with 4 wires) via the Pi config `rasp-config` routine and reboot.

## SW dependencies
You need to install with apt: python-pil, python-imaging and python-smbus and with pip: Agafruit-GPIO, Adafruit-SSD1306. Make sure you have the latest version by using `pip list --outdated` and if needed upgrade with `pip install Adafruit-GPIO --upgrade` (version 1.0.2 gives parameter type error).
Or use `INSTALL.sh DISPLAY` for this.
If you use GPIO make sure the display user is added to the group `spi` and for I2C version to the group 'i2c'.

## HW I2C problems
The Pi3 shows sometimes i2c-bcm2835 transfer timeout failures. The display may be stalled or show weird characters. A restart of the display process may recover this. However sometimes a reboot or de/install of the 2835 kernel module may solve this. This error show once a day. A workaround?

### References
* https://github.com/adafruit/Adafruit_Python_SSD1306
TO DO: use this software package
A fork of the standard display software from Adafruit:
* https://luma-oled.readthedocs.io/en/latest/hardware.html
* https://luma-oled.readthedocs.io/en/latest/api-documentation.html
* https://github.com/rm-hull/luma.oled (Richard Hull)

