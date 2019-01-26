<img src="images/MySense-logo.png" align=right width=100>

# Adafruit tiny display SSD1306
### Status
2017/06/16
Operational 2017/6/17

## How To display text on Adafruit mon display
* Use `INSTALL.sh DISPLAY` to install the script and dependences.

The script
<img src="images/SSD1306-RGBled.png" align=right width=225>
has three modules:
* display server: which uses Adafruit lib and driver to receive text and display the text on the little Adafruit <a href="https://www.aliexpress.com/item/0-96-inch-IIC-Serial-White-OLED-Display-Module-128X64-I2C-SSD1306-12864-LCD-Screen-Board/32896971385.html?spm=a2g0s.9042311.0.0.3da24c4dctrvsH">SSD1306 display</a> (Y/B, blue or white; AliExpress € 1.80).
Optional <a href="https://www.aliexpress.com/item/1PCS-Smart-Electronics-FZ0455-4pin-KEYES-KY-016-Three-Colors-3-Color-RGB-LED-Sensor-Module/32763280158.html?spm=a2g0s.9042311.0.0.27424c4dN3XhqH">RGB led</a> (AliExpress € 0.35).
We used Dupont female connector/wires (€ 0.50) to connect it to the Pi.

Try the command `./MyDisplayServer.py -help` to see all the options and command arguments. The server is multithreaded.
The DISPLAY service should be run as deamon. Add `@boot path/MyDisplayServer.py start`  e.g. to crontab of root.
* a client which is an example to send text to the display server/service on `localhost TCP/IP port 2017`.
* an output channel to send console type of measurement results to the little display. Use the plugin `MyDISPLAY.py`

The service can be used to send text to the small display to provide visual feedback for Pi operations, e.g. logging, poweroff messages, etc.

### To Do
* Add <text>, <clear> xml to the text to define font and text size changes, clear the display, etc.
* use the Richard Hull's luma modules.
* fix for I2C: display suddenly and sometimes displays from bottum up.

## the Display (RGB led) server
The display server listens on localhost port 2017 for incoming line based commands.
Use eg `echo MyCommand | nc -w 2 localhost 2017`.
MyCommand may be a text line. This text is fed to the oled display. The display will scroll if the text exceeds the display size. A bar in the text will delay the horizontal scroll longer.
The text line may have attributes as eg `<clear>text line one` (clear display first).
The `-y` command line option will define the oled Y/B (yellow/blue) use (first text line is yellow).

The server will also be able to light the RGB led. Eg `<led color=red secs=1.5 repeat=5>` will light the red red for 1.5 seconds, wait 1.5 seconds and repeat 4 times the sequence. The `secs` argument is optional as secs=0 (led not turned off). Repeat attribiute is optional (default 1). RGB led handling is enabled by the `-rgb` command line argument.
The RGB pinnumbers have to be defined as GPIO numbers, default GPIO 17 R, GPIO 27 G, GPIO 22 B (pin board numbers: 11 R, 13 G, 15 B). Grpound eg board pinnr 9.
RGB led use allows simple feed back e.g. red on error, green on data transaction, yellow on startup, etc.

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
You need to install with apt: python-pil, python-imaging and python-smbus and with pip: Agafruit-GPIO (uses GPIO pin numbering), Adafruit-SSD1306. Make sure you have the latest version by using `pip list --outdated` and if needed upgrade with `pip install Adafruit-GPIO --upgrade` (version 1.0.2 gives parameter type error).
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

