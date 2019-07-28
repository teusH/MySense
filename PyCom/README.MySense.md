## Handy info to access the MyCom (LoPy) controller

The easiest way is to install Atom/PyMakr on your computer. See the PyCom documentation first.
Atom in fact will use a telnet and ftp approach to access the PyCom controller either via USB or WiFi.
Without the MySense scripts loaded the wifi SSID/PASS is LoPy-wlan-HHHH/www.pycom.io.
MySense main will change the wifi AP SSID/PASS to MySense-HHHH/www.pycom.io. Where HHH are the last 4 hex of the wifi mac address. You may change the SSID/PAAS within the MySense configuration file.

You may need to (re)establish WiFi access often to secure access on your computer. WiFi password is `www.pycom.io`. For telnet or ftp use the default user `micro` with password `python`. Use ftp in passive mode.

Helpfull Python command within REPL (the prompt >>>) are:
* `import os; os.mkfs('/flash')` to clear all flash memory.
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
This can be redefined by W_SSID/W_PASS in the configuration file (default: MySense-HEXN','BehoudDeParel'). The wifi AP name will be effectuated after ca 1 hour from a cold (re)boot.
The WiFi will be switched off by defining 'wifi' (True) in 'power' config dictionary after 1 hour of measurements. Use this to save energy and security reasons.

### OVER The AIR (OTA) update
Via LoRaWan one can send the command 'W' to the MySense node. If the WiFi AP was turned off the WiFi AP will be enabled with the initial `MySense-HEXn`/`www.pycom.io` credentials for one hour.

To Do: use the <a href="https://docs.pycom.io/tutorials/all/ota.html">PyCom OTA</a> update method.

### Scripts to test devices (sensors)

MySense has provided several simple XYZ_test.py python scripts to test the sensor modules for needed libraries and check of wiring.
Make sure to configure the right pin ID's in `Config.py` configuration file for the test scripts if you use other pins as the defaults.

### REPL modus
On the PyCom expansion board one can force the LoPy-4 to enter REPL modus so one interact manually with the controller. See PyCom documentation how to achieve this (pin23 -> Gnd or save boot switch/reset).
To enable REPL mode otherwise e.g. using PCB connector board, MySense main.py checksthe enabled deepsleep and accu voltage. The following scheme is used:
* if deepsleep is enabled and accu voltage is higher as 4.8V REPL mode is entered.

WARNING: if MySense runMe() loop is used the LoRa antenna should be attached! On the PyCom expansion board MySense will see: deepsleep is enabled, but accu voltage (even without an accu is below 4.8 Volt. So REPL modus will be entered. A mistake will distroy the LoPy! so for security attach always the antenna!

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
MySense.runMe(debug=True)
```
This will also forward the measurement data to the network.
Allow to run this for several hours.
This can be interrupted with a <cntrl>c. If needed to be followed by a soft reset <cntrl>d

## make it operational

* on success try out `MySense.py` and finally install `main.py`:
```python
    import MySense
    MySense.runMe() # or MySense.runMe(debug=True)
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

If the main MySense measurement loop (routine MySense.runMe()) will exit for some extra ordenary reason the main.py will alarm this via RGB led warning signals and force a cold reboot if this event happens after some time. To avoid a reboot loop the controller will enter a permanant sleep with RGB warnings every 10 minutes.

## accu watch dog

If the accu is connected to Grn and ADC pin (board power pins: 5Vdc, Ground, Accu-Vcc, Accu-Gnd, s-reset on the PCB board), MySense will check via ADC the accu voltage. Will update the max/minimum value in nvs ram.
Initialy the maximum is set on cold boot to accu voltage level.
If accu voltage is lower as 85% of maximum MySense will enter a 15 minute deepsleep loop till the accu voltage level of 85% is reached.
An accu low event will be sent via LoRa every 15 minutes.
