# Shinyei PPD42NS (Grove) dust sensor
## Hardware
Grove Shinyei PPD42NS dust sensor (€ 18.- Kiwi Electronics) is a PM10/PM2.5 particals counter. The module is 5VDC and output is also 5 VDC.
* Use Grove shield or volt regulator/3V3/5V converter to connect the module with the Pi.
Disadvantage connection via Grove shield: the Grove driver software will show zero counts without a resistor to tune the thresholt and fan to force a higher air stream.
Make sure you use the latest firmware of the GrovePi for this module: https://www.dexterindustries.com/GrovePi/get-started-with-the-grovepi/updating-firmware/
* Better solution: Use Arduino as special dust controller with the Pi (the MySense choice). Advantage: the particle counter is more precise (no interrupts). The MySense software is using this approach.

To use both dust sensor outputs: Attach a fourth white cable to the cable sockets. For wiring instructions see the sketch MyArduino.ino.

## USE comments
Experiences show that there are Shinyei modules which values correlates quite well with the Dylos DC1100 output (see e.g. the aqicn.org notes). However the experiences with MySense show that a considerable amout of dust readings are NULL valued and measurements become unusable. Maybe the tresholt resister can improve this. For test manpower reasons the focus is on an alternative module from Nova SDS011. This module is manufactured only since Sept 2016. The USB TTL type of interface is simple to use.

## literature
There are a lot of references how to use the Shinyei dust sensor. Thas the Shinyei dust sensor is a very popular one. Mostly one uses the sensor in combination with the Arduino controller.

Reading and software references used:
* http://www.sca-shinyei.com/pdf/PPD42NS.pdf
* https://github.com/opendata-stuttgart/
* http://irq5.io/2013/07/24/testing-the-shinyei-ppd42ns/
* http://andypi.co.uk/2016/08/19/weather-monitoring-part-2-air-quality-sensing-with-shinyei-ppd42ns/ Pi+ug/m3 algorithm
* https://github.com/opendata-stuttgart/sensors-software/blob/master/BeginnersGuide/Guide.md
* https://openhomeautomation.net/connect-esp8266-raspberry-pi/
* https://oshlab.com/esp8266-raspberry-pi-gpio-wifi/
* https://github.com/aqicn/shinyei-lpo
* https://www.raspberrypi.org/forums/viewtopic.php?t=120926
* https://software.intel.com/en-us/iot/hardware/sensors/ppd42ns-dust-sensor
* http://iotdk.intel.com/docs/master/upm/python/_modules/pyupm_ppd42ns.html#PPD42NS
* https://github.com/intel-iot-devkit/upm/blob/master/examples/python/ppd42ns.py
* http://ir.uiowa.edu/cgi/viewcontent.cgi?article=5915&context=etd paper on convertion to ug/m3 and compare Dylos with small budget dust sensors
* http://aqicn.org/data/dylos/Air-Quality-Sensor-Network-for-Philadelphia.pdf convert pcs/qf to ug/m3

## Artduino firmware
Use the Arduino IDE (GUI) or commandline inotool http://inotool.org/ to compile, build and install the firmware sketch MyArduino.ino into the Arduino controller. The Arduino controller is conneted with the PI via an normal USB cable.
The Arduino controller is hooked up with the Pi via a USB cable. The Arduino will run in two modes: send measurement data (json) on eacht configurable interval/sampling time or send measurements data (configurable sampling timing) on request for output.

For other controller possibilities:
* [ESP8266]https://www.raspberrypi.org/forums/viewtopic.php?f=32&t=122298&p=824523

## Shinyei PPD42 connector
You won't need the Grove board, the Shinyei sensor has digital outputs that the Pi can monitor

```
    1 : COMMON(GND)           COUNTS particles >2.5 micron
    2 : OUTPUT(P2)
    3 : INPUT(5VDC 90mA)
    4 : OUTPUT(P1)            COUNTS particles >1 micron
    5 : INPUT(T1)･･･FOR THRESHOLD FOR [P2] unused
```
The output is stated to be at 4V so a voltage divider is highly recommended to bring those down to 3V3 if you connect it to the Pi board!.

Connect as follows (you may need a breadboard)
```
Pi Pin 2 (or 4) (5V) connects to Shinyei pin 3 (5V input).
Pi Pin Gnd connects to Shinyei pin 1 (Common).
output uses voltage divider (or use a special V3.3-V5 converter (€ 1.25).
Pi Pin 6 (or 9, 14, 20, 25, 30, 34, 39) (Gnd) connects to a 3k3 resistor (voltage divider) the other end of which connects to Pi pin 16 (GPIO 23) (or any other GPIO pin of your choice) and to a 1k2 resistor, the other end of which is connected to Shinyei Pin 2 (output 2).
Pi Pin 6 (or 9, 14, 20, 25, 30, 34, 39) (Gnd) connects to a 3k3 resistor (voltage divider) the other end of which connects to Pi pin 18 (GPIO 24) (or any other GPIO pin of your choice) and to a 1k2 resistor, the other end of which is connected to Shinyei Pin 4 (output 1).
Pi Pin 6 (or 9, 14, 20, 25, 30, 34, 39) (Gnd) connects to a Variable resistor, the other end of which connectors to Pi pin 2 (or 4) (5V) and the wiper of which is connected to Shinyei Pin 5 (P2 threshold setting). Adjust the variable resistor to adjust the size of dust particle which triggers P2.
```
## MyArduino.ino firmware description
The firware will output via USB to the Pi in string format as a json value:
```
{"version": "1.06","type": "PPD42NS","pm25_count":391645,"pm25_ratio":1.20,"pm25_pcs/qf":623,"pm25_ug/m3":0.97,"pm10_count":2035010,"pm10_ratio":6.68,"pm10_pcs/qf":3634,"pm10_ug/m3":5.67}
```
If the ratio is found 0 `null` values will be printed.

The firmware will provide per PM type three classes of values per sample time:
1. dust count and low ratio (0-100%).
2. count per sample time as particals per square foot (0.01pcs/qf multiplied with 100).
3. partical weight value per sample time in ug/m3.

Default timings: The output will be on every `interval` secs time frame (default 60 seconds).
The samples are taken synchronously at every `sample time` frame (default 15 seconds).

The interval time can be on *request* timings (configure interval as 0 secs): the Arduino will delay till a return is sent from the Pi.

Sending a string `C interval sample R<return>` to the Arduino will change the Arduino default configuration: interval in seconds, sample in seconds, R (use request interval timings). The Arduino will respond with an empty line if the configuration change has been succeeded. This allow to change interval and sample timings from the Pi at will.

## calibration
Literature show that the Shinyei sensor can be improved via the threshold resistor, using a fan to increase the air stream.
Literature shows also that humidity play a role in the dust size countings. So measure the temperature and huminity in the sensor box.

Make sure to calibrate the sensor against other dust sensors of a higher quality as eg a Dylos dust sensor. Make sure you clean up the dust sensor once an a while.

The MySense Shinyei/Arduino plugin will provide handles to calibrate the sensor measurements.
* ref: https://www.ijirset.com/upload/2015/february/76_Evaluation.pdf 
International Journal of Innovative Research in Science, Engineering and Technology Vol. 4, Issue 2, February 2015
Day to day variation of particulate matter was observed indoor: Shinyei’s PPD42NS data agreed well with the
large particles data obtained using Dylos DC1100 Pro. A good correlation was found with R2
= 0.818. Lineair correlation factor `PM10/PPD45NS = 2.124\*PM10/Dylos - 113.3`



