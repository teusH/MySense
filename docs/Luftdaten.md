<img src="images/MySense-logo.png" align=right width=100>

## output channel InFlux publicize
* status publish beta test 2017-12-31
### INTRODUCTION
Luftdaten.info will accept measurements via HTTP Posts. For detailsed information see the website `http://luftdaten.info` and related github software.

The posted measurements will be shown on their maps in a nice way.

### DESCRIPTION
The MySense configuration needs output to be enabled for the MyLUFTDATEN module to enable the Posts.
MySense internal json records will be posted to Madavi.de and if enabled for the sensorkit also to luftdaten.info map database.
The sensor kit serial numbers - the module configuration has a regular expression to enable the Posts for the sensor kits - are used to identify the which sensor kit is allowed and configured to do Posts to Luftdaten.
Once active by defaulkt always the Posts of records is enabled to the Madavi.de database.

Note that Luftdaten.info has a limited range of Particular Matter and weather modules and a specific code (X-Pin) to identify the modules. To Do: add more X-Pin codes.

In order to get records Postage succesfully at the Luftdaten database however one need to provide the prefix, serial number and location details of the sensor kit to Luftdaten.info. Please see for the requirements the Luftdaten.info website before starting to send Posts to Luftdaten.info.
### INSTALLATION
### APPLICATION
MySense can act as a broker or proxy to different output channels. In this case it acts with output channel to Luftdaten.info.

See also the input channels of MySense e.g. MyTTN_MQTT.py as input channel and others.
### REFERENCES
See also:
* https://github.com/verschwoerhaus/ttn-ulm-muecke as MQTT e.g. TTN proxi for Luftdaten.info
* https://github.com/corny/luftdaten-python another Pi Python example
