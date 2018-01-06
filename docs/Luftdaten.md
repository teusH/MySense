<img src="images/MySense-logo.png" align=right width=100>

## output channel InFlux publicize
* status publish beta test 2017-12-31
* status 2018-12-04: operational
### INTRODUCTION
Luftdaten.info will accept measurements via HTTP Posts. For detailed information see the FAQ on the website `http://luftdaten.info/faq` and for details the related github software `https://github.com/opendata-stuttgart/sensors-software`.

The posted measurements will be shown after sending an email with the location meta data  on their maps in a very nice way: http://deutschland.maps.luftdaten.info`.

### DESCRIPTION
The MySense configuration needs output to be enabled for the MyLUFTDATEN module to enable the Posts.
MySense internal json records will be posted to Madavi.de and if acknowledge with thge meta data for the sensorkit also to luftdaten.info map database.
The sensor kit serial numbers - the module configuration has a regular expression to enable the Posts for the sensor kits - are used to identify the which sensor kit is allowed and configured to do Posts to Luftdaten.
In order to get records Postage succesfully at the Luftdaten database however one need to provide the prefix, serial number and location details of the sensor kit to Luftdaten.info. Please see for the requirements the Luftdaten.info website before starting to send Posts to Luftdaten.info.
The serial number will be prefixed with an ID: `<ID>-<SN number>` to identify the kit on Luftdaten. Configure this ID.

Once active by default always the Posts of records is enabled to the Madavi.de database.

Note that Luftdaten.info has a limited range of Particular Matter and weather modules and a specific code (X-Pin) to identify the modules.

### APPLICATION
MySense can act as a broker or proxy to different output channels. In this case it acts with output channel to Luftdaten.info.
One way of operation is to use TTN LoraWan as dataconcentrator to forward measurements to Luftdaten. 
TTN-MQTT.py is such an input channel. TTN-MQTT.py uses an own json formated configuration file to add meta data to the TTN records.

### CONFIGURATION items
The follwing configuration settings can be altered:
* `output` False/True: enabling output handling
* `id_prefix` string to be prepended to the serial number: ID to Luftdaten
* `luftdaten` URL to Luftdaten maps database for Posts
* `madavi` URL to Madavi.de measurements database
* `serials` expression to match serial numbers candidates to be Posted
* `projects` expression to match projects id's candidates to be Posted
* `active` False/True, enable Posts to Luftdaten maps database
* `debug` False/True will enable/disable to display the Posted records.

The module has a conversion table `sense_table` to translate internal nomenclature to the nomenclature and X-Pin id's  used by Luftdaten.

### TESTING
Put the module step by step into operation:
* First run the module in standlone mode and turn debugging level to `DEBUG`. Avoid output to Madavi.de and certainly Luftdaten in this phase.
* Run the module e.g. via MyTTNMQTT module in standalone mode of MyTTNMQTT
* Turn Posts to Madavi.de on,. And see if the entries appear at madavi.de/graphs web page overview.
* Supply Luftdaten.info via email with the meta info: coordinates and location details. After an acknowledgement one can Posts the records to Luftdaten as well.

### EXAMPLE of POST
Example of 2 Post records: SDS011 PM10 (P1) and PM2.5 (P2), and DHT22 (temperature and humidity). All values are posted as strings in the json formated records here.
```json
{'X-Sensor': u'TTNMySense-f07df1c507', 'X-Pin': '1'}
{'sensordatavalues': [{'value_type': 'P2', 'value': '21.6'}, {'value_type': 'P1', 'value': '24.2'}], 'software_version': 'MySense0.1.2'}
{'X-Sensor': u'TTNMySense-f07df1c507', 'X-Pin': '7'}
{'sensordatavalues': [{'value_type': 'temperature', 'value': '9.1'}, {'value_type': 'humidity', 'value': '93.1'}], 'software_version': 'MySense0.1.2'}
```
All measurements are sent as `value_type` and `value` pairs. The header in the Post defines with the `X-Pin` code (a number) the sensor model. Every Post is carrying the measurements in an array of only one sensor module!
This will say that two sensors, say dust and weather of a sensor kit will be sent as 2 HTTP Posts.

### SENSOR MODULE ID's
The `X-Pin will define the sensor module:
```
X-Pin   sensors
-----   ---------
1       SDS011, all Plantower PM sensors (PMSx003), Honeywell HPM
3       BMP180, BMP280
5       PPD42NS
7       DHT11, DHT22, HTU21D
(9      GPS modules)
11      BME280
13      DS18B20
```

This list is not complete.

### VALUE TYPES
The values are floats, 2 decimal precision.
The value types in the data record:
```
value_type      semantics
----------      ---------------
P1              PM10
PM2             PM2.5
P10             PM10
P25             PM2.5
temperature     temperature in oC
humidity        relative humidity 1-100%
pressure        air pressure pHa
longitude       GPS coordinate as float
latitude        GPS coordinate
altitude        GPS coordinate
```

The list needs to be completed with PM1, PM0.3, PM50, loadness, and different gasses

### COMMENTS and SUGGESTIONS
* Suggest to combine the header and data part into data with an array of sensors per sensor kit. This saves bandwidth and performance.
* The measurement time is taken from time stamp of the Post. This allows only to add records and gives unsecure timings.
* Suggest to use one `X-Pin` code per sensor module type. So the branch of the sensor product will be clear as will correlations between sensor modules can be taken care of.
* Extent the `value_types` e.g. PM1 is a supported measurement in the Plantower dust sensor. E.g. extent the types as PM01, PM03, PM25, PM10, PM50 etc.
* Support gasses e.g. CO2, CO, NH3, O3, NO2, etc.
* Posts with errors in data fields should be notified as errors in the HTTP status
* Extend the API reference documentation
* Use a Post server which acts as test server.
* Automate the enabling of Luftdaten maps server on accepting Post records.
* Suggest to extend the meta info with calibration info e.g. coefficients of the calibration Taylor schema.
* Extend the measurement info with weather conditions: wind speed, wind direction, rain scale.

### REFERENCES
See also:
* http://deutschland.maps.luftdaten.info
* https://github.com/opendata-stuttgart/sensors-software for the software
* https://github.com/verschwoerhaus/ttn-ulm-muecke as MQTT e.g. TTN proxi for Luftdaten.info
* https://github.com/corny/luftdaten-python another Pi Python example
