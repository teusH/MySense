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
Add <text>, <clear> xml to the text to define font and text size changes, clear the display, etc.

### hardware
* Adafruit SSD1306  display  € 22.85 (Kiwi or SOS Solutions) or via China: € 2.-.
* Cables to hook it up to 3.3V, Gnd, GPIO as follows:
* you need to enable GPIO on the Pi, as well add the DISPLAY service user to the `gpio` group.
```
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

