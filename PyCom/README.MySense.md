## Handy info to access the MyCom (LoPy) controller

The easiest way is to install Atom/PyMakr on your computer. See the PyCom documentation first. Atom in fact will use a telnet and ftp approach to access the PyCom controller either via USB or WiFi. You may need to (re)establish WiFi access often to secure access on your computer. WiFi password is `www.pycom.io`. For telnet or ftp use the default user `micro` with password `python`. Use ftp in passive mode.

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

## MySense scripts

### Configuration definition

The file `Config.py` will give the default definitions. You will need to define the TTN keys (visit The Things Network website).
All pins can be redefined. Default values are based on the PCB wiring board from Fontys GreenTechLab. Every define can be disabled as e.g. useGPS = False.

### WLAN access point
Default WLAN AP is WPA2 as defined by PyCom firmware ('lopy-wlan-HEXN','www.pycom.io').
This can be redefined by W_SSID/W_PASS in the configuration file (default: MySense-HEXN','BehoudDeParel'). The wifi AP name will be effectuated after 15 measurements from a cold (re)boot.
The WiFi will be switched off by defining 'wifi' (True) in 'power' config dictionary after 15 measurments from a cold (re)boot.

### Scripts to test devices (sensors)

MySense has provided several simple XYZ_test.py python scripts to test the sensor modules for needed libraries and check of wiring.
Make sure to configure the right pin ID's in `Config.py` configuration file for the test scripts if you use other pins as trhe defaults.


E.g. start with testing the oled display:
```python
import oled_test
import meteo_test
import dust_test
import gps_test
import lora_test
```

### test the main script MySense.py
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
If device confioguration and initialisation seems to work thge next step is to do some measurements.
For a final test a susgestion is to try do initate some measurments:
```python
import MySense
MySense.initDisplay()
MySense.DoMeteo(debug=True)
MySense.DoDust(debug=True)
<cntrl>d
```

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
    MySense.runMe()
```
# some help scripts for testing hardware, connections and operational functions
Povided in the script `SWcomponents_test.py` one can test via copy/paste and 'atom' REPL the hardware and software.
* and give feedback to us
