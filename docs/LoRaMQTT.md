<img src="images/MySense-logo.png" align=right width=100>

## input channel TTN LoRa MQTT subscription
* status subscribe beta test 2017-12-21
* status operational 2018-01-04

### INTRODUCTION
The TTN LoRa data concentrator server, eg `eu.thethings.network`,  publishes the telegrams received via LoRaWan e.g. as Mosquittoe (MQTT) json type of records.
This module will download the MQTT records (or via an input file with the records: one line one record) and convert the record to MySense internal json type dict records with the meta information (indent: Application ID, Device ID, serial nr, geolocation) and data record (time and fields with measurements).

The meta data is completed with information from an adminstration file (geolocation, street, village, country, description, comment, etc.).

The signal/event USR1 to the process will report curtrent status: nr of records seen per node, dat/time last node seen.

The signal/event USR2 will reload the meta info json file of the nodes. In this way meta data can be changed on the fly as well archiving/output of measurenets may be turned on or off per node.

### DESCRIPTION
The module script can be run standalone while using output channels and modules from MySense, as well via `MySense.py`. As such different outpout formats supported by MySense are possible.

This module was originally written to take part of the RIVM new years firework measurement project of dec 2017.

From the command line the configuration for MyTTNMQTT running as standalone module can be changed by using key=definitionSTRING as argument: e.g. the command `./MyTTNMQTT.py file=testdata/TTNMQTTexample.json` will read its input from the json file iso the TTN server.
The included `testdata/TTNMQTTexample.json` file can be used as example and test file before getting access to the MQTT server of eg TTN Europe.

MyTTNMQTT will read and uses meta definitions for the sensor kits identified via the TTN server interface. In this way completing the meta data (`ident` part in the output json record) for the output channels as eg GPS coordinates, location, etc.

### SECURITY
Use the SSL layer of the TTN server.

### INSTALLATION
See script for all configuration possibilities. 'Conf["all"]' will force measurements from all nodes (active or not, in admin file or not) to be used in the output.

### CONFIGURATION
The file `LoPy-Admin.conf.json` will allow to define which LoRa TTN server, LoRa measurment nodes, which classes of firmware of the nodes, which load unpacking, etc will be used. Default MySense will use the internal defined configurations.

Warning:
Make sure the configuration items are well referenced. There is not much checking done on the coherence of the configuration definitions. Make sure the file is json compliant.

To Do: move these configuration items into a database.

### APPLICATION
Forward measurements of LoRaWan TTN nodes to different configured output channels.
On reception of USR1 signal/event the process will log current status of telegrams received so far and last timestamp.
On reception of USR2 signal the process will reload the admin file if defined.

i of the sensor to the first gateway) he signal strength (rssi) of first node will be included in the measurements.

MySense module will skip those node names not defined in `nodes` unless `all` is defined as `true` in the configuration. Measurtment filed names will be translated to MySense internally used field names.
If in the MQTT input json data data_fields is defined the field names and values will be used instead of the raw data field.

Missing meta data will be searched for from the `nodes` configuration definition.

### PERFORMANCE
The module will cache identified (meta) information. A USR2 event will force a reread of the adminfile and invalidate the internal caches.

### CONFIGURATION
The TTN MQTT server will provide less meta info about the node location, owner. As well TTN will compact the measurments value and be less strict on the fields, field naming, used sensors in the node. The decompression will depend not only of the node but also on the FPORT value.

The `adminfile` configuration will define a json file with configuration of information needed to enable MySense to provide meta information and standardize name of pollutants, etc. See the module for examples or the `VM2017ADMINfile-TTNmqtt.json` json formatted file.

If the adminfile is omitting keys, the key defined in the module will be used instead.

Configuration keys to be defined:
* `nodes`: meta information of the measurement LoRa node
```json
"nodes": {
    "pmsensor1": {
        "GPS": { "latitude": 15.376043, "longitude": 4.125839, "altitude": 45},
        "label":"some name",
        "serial": "f07df1c500",
        "street": "some street 20",
        "village": "MyTown", "pcode": "925 SG",
        "province": "Limburg", "municipality": "Town",
        "date": "22 december 2017",
        "comment": "my comment",
        "NwkSKEY":"650CB7F932F59",
        "AppSKEY":"131868976445","devaddr":"261156E",
        "meteo": "DHT22", "dust": "SDS011",
        "luftdaten.info": false,
        "active": true
        },
    ...
```
* `sensors`: serie of descriptions of sensors: producer, type, unit of measurments,...
```json
"sensors": [
            {"type":"SDS011","producer":"Nova","group":"dust",
                "fields":["pm25","pm10"],
                "units":["ug/m3","ug/m3"],
                "calibrations": [[0,1.0],[0,1.0]]},
            // Plantower standard ug/m3 measurements
            {"type":"PMS7003","producer":"Plantower","group":"dust",
                "fields":["pm1","pm25","pm10"],
                "units":["ug/m3","ug/m3","ug/m3"],
                "calibrations": [null,[0,1.0],[0,1.0]]}, // null is [0,1.0]
    ...
```
* `classes`: serie of refences to find firmware details from node names (regular expression)
```json
 "classes": [
        { "classID": "VW2017", "regexp": "VW2017/pmsensor[0-9]+(/[0-9])?"},
        { "classID": "TTNnodes", "regexp": "2018[0-9]+5971az/2018[0-9a-zA-Z]+/[1-4]"}
        ],
```
* `firmware`: serie of senors in a node and how data can be unpacked.
```json
"firmware": [
        { "packing": ">HHH",    // how it is packed, here 4 X unsigned int16/short
          "adjust":  [[0,1],[0,1],[0,0.01]], // unpack algorithm
          "id":      "TTNnodes",     // size of payload as ident
          "fields":  ["battery","light","temp"],          // fields
          "sensors": ["TTN node","TTN node","TTN node"], // use upper cased names
          "ports":   [null, "setup", "interval", "motion", "button"] // events
        },
    ...
```
* `translate`: convert a field name to the internally used fieldnames within MySense
```json
   "translate": {      // defs of used fields by MySense, do not change the keys
        "pm03": ["pm0.3","PM03","PM0.3"],
        "pm1":  ["roet","soot"],
    ...
```

