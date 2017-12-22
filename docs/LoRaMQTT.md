<img src="images/MySense-logo.png" align=right width=100>

## input channel TTN LoRa MQTT subscription
* status subscribe beta test 2017-12-21
### INTRODUCTION
The TTN LoRa data concentrator server publishes the telegrams received via LoRaWan e.g. as Mosquittoe (MQTT) json type of records.
This module will download the MQTT records (or via an input file with the records: one line one record) and convert the record to MySense internal json type dict records with the meta information (indent: Application ID, Device ID, serial nr, geolocation) and data record (time and fields with measurements).

The meta data is completed with information from an adminstration file (geolocation, street, village, country, description, comment, etc.).

The signal/event USR1 to the process will report curtrent status: nr of records seen per node, dat/time last node seen.

The signal/event USR2 will reload the meta info json file of the nodes. In this way meta data can be changed on the fly as well archiving/output of measurenets may be turned on or off per node.

### DESCRIPTION
The module script can be run standalone while using output channels and modules from MySense, as well via `MySense.py`. As such different outpout formats supported by MySense are possible.

This module was originally written to take part of the RIVM new years firework measurement project of dec 2017.
### SECURITY
to do

### INSTALLATION
See script for all configuration possibilities. 'Conf["all"]' will force measurements from all nodes (active or not, in admin file or not) to be used in the output.

### APPLICATION
forward measurements of LoRaWan TTN nodes to different configured output channels.
On reception of USR1 signal/event the process will log current status of telegrams received so far and last timestamp.
On reception of USR2 signal the process will reload the admin file if defined.

i of the sensor to the first gateway) he signal strength (rssi) of first node will be included in the measurements.
