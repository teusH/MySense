<img src="images/MySense-logo.png" align=right width=100>

## input channel TTN LoRa MQTT subscription
* status subscribe alpha test 2017-12-16
### INTRODUCTION
The TTN LoRa data concentrator server publishes the telegrams received via LoRaWan e.g. as Mosquittoe (MQTT) json type of records.
This module will download the record (or via an input file with the records: one line one record) and convert the record to MySense internal json records with the meta information (indent: Application ID, Device ID, serial nr, geolocation) and data record (time and fields with measurements).

The meta data is completed with information from an adminstration file (geolocation, street, village, country, description, comment, etc.).

### DESCRIPTION
The module script can be run standalone while using output channels and modules from MySense, as well via `MySense.py`. As such different outpout formats supported by MySense are possible.

This module was originally written to take part of the RIVM new years firework measurement project of dec 2017.
### SECURITY
to do

### INSTALLATION
to do

### APPLICATION
to do
