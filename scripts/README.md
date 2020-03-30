<img src="RPi/images/MySense-logo.png" align=right width=100>

# MySense
Last update of the README on 30th of March 2020

## Description
Several Python and Perl scripts to be used to collect MySense kit measurement data from TTN LoRaWan service and to generate website graphs.

### TTN datacollector
TTN datacollector is a Python script to collect measurement LoRaWan data from TTN LoRa service.
The script uses `TTN-datacollector.conf.json` json data for configuration items and TTN credentials and general info to send event notices based on a pattern (TTN topic id's).
The `TTN-collector.nodes.json` can be used to enter kit node information into the MySQL Sensors table database table.
TTN collector will use the MySQL database to obtain kit (Sensors table) information, and TTNtable to find measurements table at run time. The script will regular empty the internal cache woth collected kit info. 
Any change in the database will be updated in the  cache periodically, eg every 3 hours or via a USR1 interrupt.
The script will use several backends (channels) for it's output: console, mySQL DB, Luftdaten, InfluxDB (see Pi folder), Mosquitto (see Pi folder).

The script is able to send LoRa events (low accu, malfunctioning kit or sensor, kit which died, etc.) via email or slack notices.
The script can also be used in monitor mode.

The TTN datacollector script has the abality to upload measurement raw mosquitto file. So uploads from a mirrored archive can be used if needed.

MyDB.py backend can be used to upload kit location information into the MySQL database.

### Air Quality Index
This perl script generates AQI, LKI, etc. index values.

### get data
This perl script will download measurement from official air measurement stations. It will upload the data into the local MySQL database.
