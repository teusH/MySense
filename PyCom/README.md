<img src="images/MySense-logo.png" align=right width=100>
# PyCom LoPy or WiPy  BME280/BME680 SDS011/PMS7003 GPS  MySense sensor kit

Simple low cost (€150) satelites sensor kits.
In beta development: 2018/02/23
LoRa sensor kit is operational.

## DESCRIPTION
The sensor kits are build with PyCom (loPy-4 and WiPy-3) ESP controllers and PyCom expansion board.
<img src="images/PVC-luchtpijpcase.png" align=right height=150>
<img src="images/SDS011-BME280-SSD1306.png" align=right height=150>
The controller has on board WiFi, BlueTooth and for LoPy LoRa. Use an external LoRa Wan 868/915 LoRa antenna on the LoPy.
The PyCom controller can be programmed via embedded micropython.
To access the board use the Atom (atom-beta) with the makr plugin.
Atom is interfacing either via WiFi (192.168.4.1) or serial (USB) connection to the controller.

The goal is to use the PyCom ESP as controller for MySense sensor satallite kits. Measuring dust, rel. humidity and GPS to forward this to Mosquitto database (WiFi) or LoRa data concentrator. From which the MySense configured as proxy can pick up sensor data to the MySense databases.
The hardware costs for such a sensor kit (controller+dust:meteo+gps+V220 case+adapter) is around €150.

## PyCom programming
Install *atom* (atom-beta) and pymkr from e.g. http://PyCom.com website.

The PyCom controller will run on power ON `/flash/boot.py' and `/flash/main.py`. If not you can interact via atom with the controller. In the directory `/flash` ('home' directory) your scripts should reside.
Push and keep it pushed the *user* button on the expansion board first and while pushing push the *reset* button on the controller will reboot the controller but will not run boot.py as well main.py. The other way is to press <cntrl>C on the keypboard (keyboard interrupt).

In the PyCom folder you will see some main scripts. The libraries for the sensor modules are in the lib folder. Copy the main scripts to the 'LoRa/firmware' directory, as well the needed libraries (see the statement *import* in the used scripts) to the *lib* directory. Point *atom* as new project to the configured *firmware* directory and press 'sync' or 'reload' button to load the files into the PyCom controller.

## tested MySense modules
Choose one meteo and one dust sensor: MySense modules in development are:
* BME280 meteo: temp, humidity and pressure on I2C bus
* BME680 meteo: temp, humidity, pressure and air quality on I2C bus
* PMS7003 dust: PM1, PM2.5 and PM10 on UART TTL (no USB)
* SDS011 dust: PM2.5 and PM10 on UART TTL (no USB)
* GPS location: UART TTL (no USB)
* SSD1306 tiny oled display: 128X64 pixels on GPIO bus or I2C bus.

## RTC clock
MySense will use GPS to initilyse the Real Time Clock module. Every time the GPS location is looked up the RTC clock will be updated automatically.
This will allow MySense to timestamp measurments more precise.

## MySense satellite kit configuration
Use the file `Config.py` to define which sensors are configured for the kit. Have a good look at the *pin*s definitions and bus used for the sensor. The `Config.py` file should reside in the *firmware* directory in order to upload it to the controller.

Do not change the order in the `Meteo` and `Dust` array definition!

## Testing hardware
MySense has provided several simple XYZ_test.py python scripts to test the sensor modules for needed libraries and check of wiring.
Make sure to configure the right pin ID's in `Config.py` configuration file for the test scripts.

Test your setup one by one before trying out the main wrapper `sense.py` via *sense.runMe()* or `main.py`.

## Your First Steps
* visit the PyCom.io website and follow the installation guide
The following is an outline how we do the developments and module testing:
* Add the expansion board to the PyCom LoPy or WiPy module. Make sure about the orientations.
* hook up the module (USB or via wifi) to your desktop and upgrade the firmware.
* disconnect the expansion/PyCom module from power and only wire up one module.
* copy the dependent XXX_test.py, Config.py and library module XXX.py to resp. XxPy/firmware and XxPy/firmware/lib.
* adjust the Config.py for the right pin setup wiring.
* Click on the *Upload* button of atom to load the scripts into the PyCom module.
* fireup XXX_test as follows:
```python
>>>import XXX_test
```
* if not successfully enter the statements of XXX_test.py one by one via atom REPL.

* on success do the next module wiring and test.
* on success try out `sense.py` and finally install `main.py`
* and give feedback

## MySense scripts
The main micropython script which drives the sensor kit is `sense.py`. Use `main.py` to import sense.py and run `sense.runMe()` to run the kit.

The micropython (looks like Python 3) script uses the Adafruit BME280 and BME680 (I2C-bus) python module, SDS011 (Uart 1) module from Rex Fue Feinstaub `https://github.com/rexfue/Feinstaub_LoPy` and Telenor weather station `https://github.com/TelenorStartIoT/lorawan-weather-station` and SSD1306 (Adafruit tiny display SPI-bus).

In the test phase one should not download main.py to the LoPy controller. Use `sense.py` in this phase instead and rename it to main.py later.
Use (open) the directory `firmware` as base for the atom project and upload all file by pressing the upload key.
On the console prompt `>>>` use the following:
```python
import sense
sense.runMe()
```
After this initial test rename sense.py to main.py. And upload main.py to the LoPy.

## I2C bus errors
The I2C together with SPI will cause I2C bus errors. After using the SPI SSD1306 display before the I2C bus can be used initialize the I2C bus first.

### how to reset the controller
You can delete old firmware using the instruction by PyCom. Usualy you only need to delete all uploaded file as follows:

Use the reset button on the LoPy to get the atom prompt `>>>` and do the following:
```python
    import os
    os.mkfs('/flash')
```
And upload your new files.

How to delete or enable previous firmware? Connect Pin P12 to 3V3: 1-3 sec (safe boot), 4-6 secs (previous user update selected), 7-9 secs (safe boot factory firmware).
P2 - Gnd low level bootloader (needed to update factory firmware upgrade).

### test PyCom controller
The PyCom will initiate the wifi. Use Wifi AO with pass: www.pycom.io and telnet (192.168.4.1) access user/password micro/python.

Make sure you have to upgrade the PyCom controller first. However upgrading LoPy-4 failed somehow.

Simple test to silence the blue flashing, at the prompt `>>>`:
```python
    import pycom
    pycom.heartbeat(False) # silence the blue flash
    pycom.rgbled(0x99ff55) # some color
    pycom.rgbled(0x000000) # led OFF
```

## MySense controller status
The console will print status as will the flashing led on the LoPy will flash different collors: red to establish LoRa connectivity, blue when LoRa is ready, green when measuremnts are arriving, and blue when data is sent, and white when SDS011 fan is turned off to save the fan and laser as well LoPy is in idle state. LoPy will send every 5 minutes (`sleep_time`) a measurement sample  to the TTN data concentrator.

## controller wiring

<img src="images/PyCom-wiring-BME-SDS-PMS-SSD-GPS.png" align=center height=250>

See for examples of wiring the `README.LopY.md` (LoRaWan TTN, BME280, SDS011 and SSD1306) or `README.WiPy.md` (wifi MQTT, BME680, PMS7003, SSD1306) readme's.

## To Do
Add more sensor modules. The Shiney PPD42NS (unreliable and too much errors), DHT22 and DHT11 (too much peaks and outdoor time to live too short) meteo sensor are depricated.
Note: The Plantower PMS7003 is much smaller and consumes less energy as the Nova SDS011 (has a nice air inlet).

## Licensing
If not noted the scripts and changes to external scripts are GPL V3.
