## An outline
A description of the MySense PyCom based measurement kit, data collection and data visualisation is provided in a presentation at Meetkoppelting20 conference in Amersfoort, Jan 2020. The PDF slides can be found at <a href=""http://behouddeparel.nl/sites/behouddeparel.nl/files/20200125-Koppelting-WAR-Amersfoort.pdf" alt="an How To build a kit and show the results">"Measuring Air Quality in an Agri Region: an How To"</a> (PDF 3 MB).

## Handy info to access the MyCom (LoPy) controller

MySense is tested on PyCom firmware. Make sure one uses the latest firmware as interfaces to PyCom library routines may change over time.
PyCom *firmware release 1.20.1* and higher introduced smart configuration (device configuration with a PyCom smart phone app and Pybytes. From this firmware release wifi LoPy AP will not be permanently activated. One has to disable smart configuration and activate wifi at boot time first once. See SWcomponents.txt or MySense boot.py for a howto or upload MySense boot.py to the LoPy-4 via the PyCom Expansion board first.

The easiest way is to install Atom/PyMakr on your computer. See the PyCom documentation first.
Atom in fact will use a telnet and ftp approach to access the PyCom controller either via USB or WiFi.
Without the MySense scripts loaded the wifi SSID/PASS is LoPy-wlan-HHHH/www.pycom.io.
MySense main will change the wifi AP SSID/PASS to MySense-HHHH/www.pycom.io. Where HHHH are the last 4 hex of the LoPy S/N address or SSID configuration from `Config.py`.
Unless wifi power management is configured as False (dflt: True) the wifi will be powered off after one hour. This to avoid voltage dips caused by wifi beacon and/or a bad adapter.

You may need to (re)establish WiFi access often to secure access on your computer. WiFi password is `www.pycom.io`. For telnet or ftp use the default user `micro` with password `python`. Use ftp in passive mode.

Helpfull Python command within REPL (the prompt >>>) are:
* `import os; os.fsformat('/flash') or older firmware: os.mkfs('/flash')` to clear all flash memory.
* `import sys; sys.exit()` act as soft reset, simalar to <cntrl>d
* `import machine; machine.reset()` act has hard reset (you need to reestablish wifi)
* `import os; os.uname()` gives release and version details.
* test uart:
```python
from machine import UART
uart = UART(1,baudrate=9600,pins=('P4','P3')) # pin Tx and Rx
uart.any()
uart.readline()
```
One may need to set pin for powering device on some PCB boards with a mosfet.
* test LoRa access OTAA
```python
from machine import LoRa
from Config import dev_eui, app_eui, app_key
keys = (dev_eui,app_eui,app_key)
lora = LoRa(mode=LoRa.LORAWAN)
lora.join(activation=LoRa.OTAA, auth=keys, time=0)
lora.has_joined()
```
* serial number:
```python
from machine import unique_id
import binascii
binascii.hexlify(unique_id()).decode('utf-8')

The file `SWcomponents_test.txt` will give you quite some test examples to test devices, software and to familiarize yourself with the MySense software.

## MySense scripts

### Configuration definition

The file `Config.py` will give the default configuration definitions. You will need to define the TTN keys (visit The Things Network website).
All pins can be redefined. Default values are based on the PCB wiring board from Fontys GreenTechLab. Every define can be disabled as e.g. useGPS = False.
From Config.py one is able to define all functionality of MySense. On a cold restart a configuration will be compiled and stored in flash memory. A reboot will use the discovered configuration and detected devices.

### GPS kit location
MySense will complete the kit home location if the GPS coordinates in `Config.py` is defined as *[0,0,0]* (default). MySense will maintain current GPS location if distance to home location and previous location is more as 50 meters. In this case the (mobile) GPS location will be sent to the TTN server with the measurement data. This take place if a GPS satelite fixate is seen.

### current time (UTC)
On a GPS fixate the RTC clock of the controller will be updated. In this case measurement data will be completed with an offset (To be Done).
The RTC time will be updated every hour on a fixate. This is update time is configurable.
If there is no GPS fixate one is advised to use the lowest TTN gateway time as measurement time. For this type of measurements the offset of less as a second is neglectable.

### WLAN access point
Default WLAN AP is WPA2 as defined by PyCom firmware ('lopy-wlan-HEXN','www.pycom.io') and is overwritten via main.py with 'MySense-HEXN' SSID.
This can be redefined by W_SSID/W_PASS in the configuration file (default: MySense-HEXN','BehoudDeParel'). Unless wifi power management is switched on the wifi AP name will be effectuated after ca 1 hour from a cold (re)boot.
By default the WiFi will be switched off by defining 'wifi' (True) in 'power' config dictionary after 1 hour of measurements. Use this to save energy and security reasons.
WiFi AP can also be switched on via the remote LoRa command `W`.

### OVER The AIR (OTA) update
Via LoRaWan one can send the command 'W' to the MySense node. If the WiFi AP was turned off the WiFi AP will be enabled with the initial `MySense-HEXn`/`www.pycom.io` credentials for one hour.

To Do: use the <a href="https://docs.pycom.io/tutorials/all/ota.html">PyCom OTA</a> update method.

### Scripts to test devices and configuration (sensors)

MySense has provided several simple XYZ_test.py python scripts to test the sensor modules for needed libraries and check of wiring.
For every sensor type (dust, gps, oled, meteo) and 'bus' (I2C and UART) there is a script which uses the same interfaces to device libraries, device and config data structures.
So any change in a device driver, device type discovery, etc. should be tested with these scripts before putting the measurement in full operation or do a manual MySense run. After a 'run' for the test script one is advised to do a soft reboor (<cntrl>D short cut key).
The scripts are designed to be able to run via REPL and copy/paste each test statement.
The scripts have a support for setting 'debug' (switch debug on (dflt) or off) and 'update' (update configuration (dflt True) in the json configuration file in flash memory) environment variables.
E.g. before running the XYZ_test script file define debug=False or upadte=False at the REPL prompt.

There is no need to flash the test files on the LoPy. If needed one can delete the test file on the LoPy-4 as follows:
```python
>>>import os
>>>os.remove('/flash/XYZ_test.py')
```

Make sure to configure the right pin ID's in `Config.py` configuration file for the test scripts if you use other pins as the defaults.

### REPL modus
On the PyCom expansion board one can force the LoPy-4 to enter REPL modus so one interact manually with the controller and USB tty connection. See PyCom documentation how to achieve this (pin23 -> Gnd on elder PyCom expansion board or use a save boot switch & reset button simultaniously).

Later PCB boards have a hall sensor so use a magnet to enforce REPL modus.
Or set `REPL = True` in `Config.py` configuration file.

MySense will inicate a REPL modus via a special RGBled flash sequence: 3X orange-blue followed by  heartbeat ON.

WARNING: with MySense loaded even on a PyCom expansion board MySense may be started and use LoRa.
So make sure the LoRa antenne is always connected!

#### TEST connected devices first
E.g. start with testing the oled display:
```python
import oled_test
import meteo_test
import dust_test
import gps_test
import lora_test
```
All test script will finish with a soft controller reset.

LoRa may change some values in memory. So a restart of the lora test script may fail. After the LoRa test do a power cycle to clean up the LoRa values in memory.

Hint: Pymakr uploads default all files with e.g. .py, .txt, .log, .json, .xml in the default working directory. This may result in unexpected upoad of files onto the LoPy-4. Make sure to have a clean working directory with only those files needed on the LoPy-4.

Hint: Pymakr settings allow a so called Pyignore list. It is handy to use the following list of files which are only used in test sensor device situation, and are runprimary via the 'run' button in Pymakr: `dust_test.py,lopy_test.py,meteo_test.py,TTL_test.py,gps_test.py,I2C_test.py,lora_test.py,oled_test.py`.
Or create a test directory and use the directory name in the Pyignore list.

### TEST the main script MySense.py
The `MySense.py` script uses for every device type (Gps, Dust, Meteo, Network, Display) a python dict to kjeep track of the device status: use (can be used), enabled (operational), fd (file descriptor: loaded access library of the device), name (device name) and optional some other attributes as e.g. cnt (show PM counts), i2c (I2C bus handle), etc.

After a call with the init routine (e.g. initDust(), initMeteo(), initGps(), initNetwork(), initDisplay()) the device type dict will be adjusted with the discovered status. Use the argument `debug=True` in the routine call to allow MySense to be more verbose.

Example:
```python
import MySense
MySense.initDisplay(debug=True)
<cntrl>d
# or
import MySense
MySense.initMeteo(debug=True)
<cntrl>d
# or
import MySense
MySense.initDust(debug=True)
<cntrl>d
```

The init routines will use the routines `I2Cdevs(debug=True)` or `UARTdevs(debug=True)` to discover the pins to be used for the interface to the device, as well type of device hooked up to the pins automatically or via the Config.py definition. Use e.g. the following command to show the status and details of the device:
```python
Dust
Meteo
Gps
Display
Network
```

## First operational measurement test
If device configuration and initialisation seems to work the next step is to do some measurements.
For a final test a suggestion is to try do initate some measurements:
```python
import MySense
MySense.initDisplay()
MySense.DoMeteo(debug=True)
MySense.DoDust(debug=True)
<cntrl>d
```
More examples can be found in `SWcomponents_test.txt` file.

Test your setup one by one before trying out the main wrapper `MySense.py` via *MySense.runMe()* or `main.py`.
If everythings seems to work use the following to initiate a test loop:
```python
import MySense
MySense.runMe(debug=True,reset=True)
```
This will also forward the measurement data to the network.
Allow to run this for several hours.
This can be interrupted with a <cntrl>c. If needed to be followed by a soft reset <cntrl>d

`debug=True` will switch on debugging mode. The configuration routine will become very versatile. Default: debug=False.

`reset=True` will cause to clear nvs variables, e.g. marks, data telegram count, current values of eg GPS satellites, etc. As well it will clear the archived configuration in flash memory. Effectually clear the LoPy memory.
Use rest argument on a clean restart to allow MySense to discover the configuration items as well (newly) attached devices/sensors..

## make it operational

* on success try out `MySense.py` and finally install `main.py`:
```python
    import MySense
    MySense.runMe() # or MySense.runMe(debug=True,reset=True)
```
Some help scripts for testing hardware, connections and operational functions
provided in the script `SWcomponents_test.txt` one can test via copy/paste and 'atom' REPL the hardware and software.
* and give positive and negative feedback to us and contribute!

## events (RGB led is flashing)

MySense will try to notify unexpected events during the measurements.
These events will be shown via the RGB led: blinking red flash light and eventually constant red light on fatal events.
Some recoverable events will be sent via LoRa, if possible as well. Like STOP operations, and empty accu (<85% energy level).
If possible the events will be propagated to the TTN Lora sever.
Some examples:
* blue initial flash: start up
* blue repeating: controller is in REPL mode
* white repeating: wait in interval period
* green repeating: initializing or wait on stable air stream: starting up fan
* blue flash: LoRa send data
* read flash: sensor failing
RGB led may be turned of to save energy (see the configuration file).

On the reception of a remote LoRa command (see the script for all remote commands) the command will be sent as a ping-pong back to the TTN server as an event acknowledgement.

MySense is using a watchdog of `interval * 4` seconds.
An activated watchdog will sent an event on startup with a mark of the script location of the halt.

### MySense failure events

If the main MySense measurement loop (routine MySense.runMe()) will exit for some extra ordenary reason the main.py will alarm this via RGB led warning signals and force a cold reboot if this event happens after some time. To avoid a reboot loop the controller will enter a permanent sleep with RGB warnings every 10 minutes.

## accu watch dog

If the accu is connected to Gnd and ADC pin (board power pins: 5Vdc, Ground, Accu-Vcc, Accu-Gnd, s-reset on the PCB board), MySense will check via ADC the accu voltage. Will update the max/minimum value in nvs ram.
Initialy the maximum is set on cold boot to accu voltage level.
If accu voltage is lower as 85% of maximum MySense will enter first a 15 minute and later a 60 minutes deepsleep loop till the accu voltage level of 85% is reached.
An accu low event will be sent via LoRa every 15 minutes.
To Do: do not wakeup on low accu at night till sunrise.

# MySense firmware upgrades
## MySense release up to 3
Using Processor Connector Board from Fontys GTL Venlo: no power management on TTL and I2C-bus sockets.

## MySense release 4
* Using Processor Connector Board from Fontys GTL Venlo: power management on TTL and I2C sockets.
* Preparation of solar panel energy handling and battery load level management

## MySense release 5
* Using Processor Connector Board from stichting Burgerwetenschappers Land van Cuijk with better power management, accu level management, REPL mode via hall magnetic sensor
* software watch dogs introduced for post mortum debugging reasons
* wifi power management. Default wifi off after 1 hour.
* deepsleep energie management improvements

## MySense release 6 (major release update)
* sensor device drivers update (mainly I2C Adafruit origin)  to solve 32-bit bugs and I2C interface standardisation issues.
Added I2C semaphone support to avoid simultanius master access on I2C-bus.
* support added for multiple  I2C-busses.
* generalisation of I2C and TTL interfaces.
* start with multiple senosor support of same type.
* LoPy firmware 1.20.1 and later (pybytes, smart configuration) compatability changes.
* energy saving on wifi while using deepsleep and enabling wifi with power cycle.
* improved battery level watchdog
* updated different test scripts for TTL and I2C, and meteo/display/gps/dust sensor drivers. These XYZ_test.py files are only meant for operational initial tests and can be deleted from LoPy-4 flash file system when approved.

## To Do
* support for more sensors of same type
* standardisation e.g. use of LoRa payload compression engine
* use of standard internal data stream structure (json/python dict) format.
* use of Bluetooth for satelite sensor kits e.g. wind speed/direction and rain.
* mesh measurement support
* enforcing calibration of connected sensors (per type, and between manufaturer)
* support for better remote firmware updates eg via wifi (already supported) or Bluetooth.
