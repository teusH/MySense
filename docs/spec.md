<img src="images/MySense-logo.png" align=right width=100>

# gas sensors from Spec
## Status
In alpha test since 11th of May 2018

## Description
The gas sensors from Spec
<img src="images/spec.png" align=left width=175>
is simple to connect via a TTL USB. The serial output is 9600 baud, and input (commands)/ output are in ascii. Default on poweron the Spec gas sensor will be in standby mode. Any input character will put the module in active mode smapling internally PPB values and averaging (dflt disabled) them. The manual dictates: By sending a 'c' the module will send regularly a line of values to the host. By sending a '\r' character the module will respond with a measurement line. 
Note: we tried to read the eeprom but did not succeed.
The module needs one hour to stabalize.

A module has three parts: the Spec sensor (O3, NO2, or CO), the TTL interface with the eeprom, and the USB TTL adapter. All input is read in parrallel (threaded input).

Cost pricing varies between € 50 and higher. Make sure one uses an serial USB converter to interface to the 3V3 based TTL serial interface of the module. MySense used `Cygnal Integrated Products, Inc. CP210x UART Bridge / myAVR mySmartUSB light`. See the config example for the appetrn to recognize which USB has the gas adapter.

## References
* http://www.spec-sensors.com/wp-content/uploads/2017/01/DG-SDK-968-045_9-6-17.pdf specification of the API
While testing the Spec input module no commands were honored. On any character sent the sensor reacted by sending one measurement.

## Correlation test
Output has been tested against reference sensors at GGD Amsterdam early 2017. They look good but there is a need to retest after an outdoor period.

## Dependences

## Usage
MySense tries to read the eeprom to identify wich serial interface with the USB adapter from Cygnal Intergrated measures which gas. On failure one measurement is read to lookup the gas ID via the serial number (on the back of the gas sensor part). Only the configured gas fields are added for measurements.

Serial input is read (9600 baud, 8-bit, no parity, 1 stop bit)  on interval basis with the request for input command. The serial line output of the TTL is as follows (all integers):
```
SerialNr,PPB gas, temperature oC, rel. humidity %,
    SDAraw, Traw, RHraw, days, hours, minutes, seconds \r\n
```
For every USB gas sensor a thread is initiated measuring at interval periods PPB, temp and RH (average) values and averaging them. `BUFSIZE` will limit the max of measurements by the sensor.

MySense will recognize all USB interface and join this withe gas ID automatically. Make sure to use a unique serial TTL USB converter.

Output to MySense main part example:
```json
    { 'time': seconds, 'o3': ppb, 'no2': ppb, 'co': ppb }
```

## MySense module Configuration
* `input` boolean will define to enable the sensors read.
* `type` will identify the Spec gas sensor ID dflt Spec ULPSM
* `usbid` will identfy the USB serial adapter, dflt Silicon_Labs_CP210
* calibrations, fiels, units is an array to identify calibration factors, names, and units of measuements.
* `raw` will enable raw values to output via MySense
* `is_stable` is amount of seconds to wait for measurments after power on, dflt one hour.
* `omits` is gn array with names of gasses to omit
* `data` list of names to pick up from sensor modules, dflt ppb, temp, rh (None is disable this field)
* `interval` interval to read measurments by the thread, dflt 60 (one minute)
* `bufsize` is size to take average of measurments by the thread, dflt 30
* `sync` enable input threading (gas seanor readout is done in parallel, dflt enabled.
