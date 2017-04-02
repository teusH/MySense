# Dylos DC1100 Pro dust sensor
Operationl: 2017/01/25

## Description
The Dylos PM meter is a good particlar matter measurement tool.
Make sure you have one with the serial RS232 PC (conventional)  output port.
E.g. Dylos DC1100-Pro. The adapter is 12 VDC.
Note: there is no humidity measurement.
The Dylos costs about 280 US$ or in Europe € 500.- - € 750.-.

The Dylos serial port runs at 9600 baud, 8 bits, noparity, 1 stopbit (8N1).
The Dylos will run in two modes: 
1. at power on (default) continuous mode (1 minute average PM counts),
2. one press on the mode button puts it into monitor mode: per 59 minutes/59 seconds a one minute sample.

The output is PM2.5 and PM10 measurements per line. On a power drop the Dylos will not continue with measurements.

## Dylos firmware
There is firmware which outputs 4 values. There is a fan which controls the airflow.
A periodic clean of the internals is needed to avoid dust problems.

## installation
Use a conventional USB-RS232 cable to hook Dylos up to the Pi. Cable costs price about € 10.-.

### identification of the USB serial port
1. With the command `lsusb` denote the manufacturer identification of the USB serial device. You need this identifier in the MySense init/config file.
This enables you to remain independent to the USB port umber (this numebr may vary).
2. Add the MySense user, e.g. ios to the dialout group: sudo addgroup ios dialout
You may need to logout/login to activate this.
3. Complete MySense the init/config file.

## testing the sensor
As ios try the command: python MySense -i dylos -o console -l debug
and turn manually the Dylos on.

The MySense Dylos plugin is able to read the Dylos data from a file. This can be used to test MySense output channels.

## calibration
MySense supports calibration of the sensors values via a Taylor polonium of order n. Use the MySense configuration/init file to change the calibration factors per sensor.

references:
* http://aqicn.org/data/dylos/Air-Quality-Sensor-Network-for-Philadelphia.pdf convert pcs/qf to ug/m3
