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

#### TTN LoRaWan service
One has tote a webaccount and register the LoRa measurement kits with TTN to obtain OTAA (or ABP) LoRa keys for accessing TTN.

Via the webaccount one is able to send (remote) a rich set of ota commands (change interval/sample, stop display, etc.)  to the kit node.

TTN uses a java script (see the example: `TTN-decode.js`) to compute a json dictionary with sensor fields/value measurements. Avalailable via application/device topic on the TTN Mosquitto interface.

The TTN-datacollector subscrips to `applicationID/+/devices/up/+`.
TTN LoRaWan uses a Mosquitto based download interface. The device topic is used as a handle to identify the kit node in the data base table `TTNtable` to access the meta info `Sensors` database table, as well as identifier via a regular expression match to send notices either via email or Slack notices.

The TTN-datacollector is able to uncompress TTN LoRa raw data downloads via the configuration json dictionary. As well to identify default sensors types in the kit node.

After handling events and updating meta data TTN-datacollector will provide the meta data as `ident` and measurements as `data` dictionaries to the various output channels.
Currently: monitoring, console, MySQL database `luchtmetingen` and `Luftdaten/Madavi`. Planned are output channels as InfluxDB and Mosquitto (see Pi folder section for drafts).

#### MySense kit administration
The database `Sensors` table will have meta data for every MySense measurement kit. Project ID and kit serial number are the keys to identify the kit in the table.
Every new home location (`geolocation`) describes the location of the kit on the kit location map.
Every new home location introduces a new record ordered by the column `datum`.
The column `active` in the `Sensors` table will denote a kit in operation.
The column `description` provides details of the used sensors (manufacturer/type).
The column `notice` will describe who to send events for this particular kit node.
Only maximal one row for a project/serial ID should have `active` set to true.
 Changes in the `Sensors` table can be notified to TTN-datacollector process via a USR2 signal. However TTN-collector will check for changes in `Sensors` table every 3 hours.

The `TTNtable` table will provide output channel details: `active` for enabled channel to kit measurements table `project_serial`, Luftdaten details: if true use `TTN-serial` as Luftdaten ID (dflt) or Luftdate.info as special ID.

### Air Quality Index
This perl script generates AQI, LKI, etc. index values.

### get data
This perl script will download measurement from official air measurement stations. It will upload the data into the local MySQL database.
