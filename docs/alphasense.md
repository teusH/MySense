<img src="images/MySense-logo.png" align=right width=100>

# gas sensors from AlphaSense
## Status
In alpha test since 11th of May 2018

## Description
The gas sensors from AlphaSense: NH3-B1 sensors, Digital Transmitter Board IBS, and connected to MySense Pi with A/D converter PCF8591 (4 channel, 8-bit).
<img src="images/NH3-IBC-ADC.png" align=left width=175>
Connect the IBC board with ADC I2C bus to Grove-Pi or SCL1/SDA1 of the Pi.The ADC is connected with 5V to the Pi as well the IBC board.
The ISB needs some minutes to establish reading. Note the first value readout by the ADC is a cached value. Use the second readout.
You need to check the sensivity of the sensor. For the NH3-B1 it is 4 mA -> 0 ppm, 20 mA (max) -> 100 ppm.

Cost pricing varies between if you buy the senor not from AliExpress: NH3-B1 sensor € 64, ISB board € 86€  and ADC-I2C converter € 1.73.

## Configuration
As there maybe more as one AlphaSense gas sensor connected to the Pi MySense will need a way to get all the ADC converters. You need to install I2C-tools. Use i2cdetect -y 1 to see if the ADC converter is connected to the Pi at address 0x48.

## References
* PVF8591 A/D 4 channel, 8-bit controller
     delete light, temp, pot straps to disable these sensors
     https://www.nxp.com/docs/en/data-sheet/PCF8591.pdf
* AlphaSense NH3 B1 sensor
     http://www.isweek.com/product/ammonia-sensor-nh3-sensor-nh3-b1_1712.html
* AlphaSense Digital Transmitter Board ISB
     http://www.isweek.com/product/4-20-ma-digital-transmitter-board-alphasense-type-a-and-b-toxic-gas-sensors-digital-transmitter-board_1835.html
     http://www.alphasense.com/WEB1213/wp-content/uploads/2013/11/Alphasense-Digital-Transmitter.zip

## Correlation test
To do.
Note: one has to convert ADC readout to ppm or even ug/m3. Use the product specification for this. See the example in the AlphaSense configuration part of MySense. 

To Do: conversion to ug/m3. This is much temperature and humdity dependent.

## Dependences
The Pi tooling I2C-tools and SMBus module.

## Usage
MySense tries to convert ADC mV, mA to the configured units for the gas. Deflt: mV -> PPM.

Output to MySense main part example:
```json
    { 'time': seconds, 'nh3': ppb }
```

## MySense module Configuration
* `input` boolean will define to enable the sensors read.
* `type` will identify the Spec gas sensor ID dflt AlphaSense
* calibrations, fiels, units is an array to identify calibration factors, names, and units of measuements.
* `raw` will enable raw values to output via MySense
* `interval` interval to read measurments by the thread, dflt 60 (one minute)
* `bufsize` is size to take average of measurments by the thread, dflt 30
* `sync` enable input threading (gas seanor readout is done in parallel, dflt enabled.
