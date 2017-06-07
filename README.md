# MySense
Software Infrastructure or framework for managing environmental sensors and data aquisition

## Goal
Provide a generalised dynamic Open Source based infrastructure to allow environmetal measurements data acquisition, dynamic transport of data to other systems, datastorage and archiving and access for free visualisation and free availability  of the data.

## Main program
The main python script is MySense.py

The script is the central management script beween sensor and broker input (modules) plugins (temperature, dust, etc. sensor device modules and brokers) to output modules (console output, (MySQL) database, (CSV/gspread) spreadsheets, and brokers.
* Try `./MySense.py --help` to get an overview.
MySense.py can be called with the argument start (or status, or stop) to start MySense as background process.

On the command line input or output plugins can be switched on or off.
The MySense configuration file defines all plugins available for the MySense.py command.
The output of sensor values to an output channel will always on startup to send an identification json info record.
Each configurable interval period of time MySense will send (input) measurements values to all configured output channels. For each output channel connected via internet MySense will keep a queue in the case the connection will be broken. If the queue is exceeding memory limits the oldest records in the queue will be deleted first.

If switched on and configured an email with identification information will be sent to the configured user.
Make sure one obeys the Personally Identifiable Information ([PII]http://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-122.pdf) privacy rulings.

# Plugin configuration 
MySense.conf is the configuration/init file from which plugin or modules are imported into the MySense process. See the `MySense.conf.example` for all plugins (sections) and the plugin options.

For every plugin module there is an README.plugin with explanations of the input/output plugin.
The input from sensors is read asynchronous (in parallel) via the module MyTHREAD.py.
If needed it can be switched to read only in sync with the other input sensors.

A working example of MySense in todays operation:
```
          remote access             |  INTERNET (wired/wifi)
          syst.mgt.     webmin -----||_ wifi AP -- webmin/ssh system mgt
                    ssh tunnel -----||
                    Weaved IoT -----||
                                    ||
                                    ||    
    INPUT PLUGINs                 _____      OUTPUT CHANNELS    GATEWAY/BROKER
    DHT11/22-meteo ---GPIO---->| /     \ |>- CSV                _____
    GPS-locator ------RS232--->|=MySense=|>- console         | /     \ |
    RSSI-wifi signal-strength >|| Pi    ||>- MYSQL           |=MySense=|>-gspread
    Dylos-dust -USB-- RS232--->||Jessie ||>- Mosquitto pub-->||  any  ||>-MySQL
    Grove-loudness ---GPIO---->| \_____/ |>- HTTP-Post       || Linux ||>-CSV
    EMS280 -meteo ----I2C----->|    |    |>- email info      | \_____/ |>-console
    PPD42NS -dust-Arduino-USB->|    |    |>- Google gspread (alpha)    |>-InFlux pub
    Nova SDS011 -dust -USB --->|    |    |>- InFlux publish >|         |
    LoRaWan (planned) -------->|    |    |>- broker? (planned)
    Mosquitto sub ----server ->|    |    |>- display SSD1306
    InFlux subscribe -server ->|    |
                                    |>-raw measurement values -> InFlux server or file
                                           calibration
```

## Interaction data format
Interaction with plugins and output channels is done in json datastructure:
Example of json to display a measurement on the console (and others):
```javascript
     { "time": UNIXtimeStamp,
        "temp": 23.2,
        "rh": 30.2,
        "pm": 234.2,
        "o3": None }
```

At the startup MySense.py will start with an identification record providing details of the version, the location if available, a unique identifier, sensor types and measurement unit, etc.
This information will define eg the first row of a spreadsheet or the database table with all sensor info (called Sensors).

Towards a broker the output will consist of an (updated e.g. GPS location) combination of the data json record and the infomration json record:
```javascript
    { "ident": id-record, "data": data-record }
```

The input sensor plugins provide (sliding window of a per plug definable buffer size)) averages in a per input plugin defined interval time in seconds. The output is done on a general interval period timing using the average time of input timings.

Typical input rate from a sensor is 60 seconds (can be tuned) and for brokers it is 60 minute interval (can be tuned).

## Brokers
MySense can act either *sensor manager* or as *input from broker manager* to a set (dynamic) of output channels. 

Available input plugins:
* Dust: Dylos DC1100 or 1700 via serial interface, Shinyei GPIO (e.g. Grove dust sensor)
* Temperature/humidity: Adafruit DHT11/22 or AM3202 and Grove variants
* RSSI (strength of wifi signal): via the platform
* Location: GPS (GPS Ultimate from Adafruit/Grove) via TTL serial interface

## Remote management
The Pi allows to install a wifi connectivity with internet as well a virtual wifi Access Point. A backdoor configuration is provided via direct access to `webmin` and `ssh` (Putty), as well via a proxy as *ssh tunneling* and/or using the proxy service of Weaved (`https://www.remot3.it/web/index.html`).

## Platform:
Sensors have a hardware interface to I2C, GPIO: those sensors are tested on RaspBerry Pi (and Arduino Uno)
Sensors with USB serial are tested on Linux Debian platforms which run Python.

## Installation
See README.pi for installation of the Raspberry Pi platform.
MySense plugins: Use the shell file `INSTALL.sh [DHT GPS DB plugin ...]` to download all dependent modules.

The sensor plugins can be tested in standalone mode, e.g. for BME280 Bosch chip, use `python MyBME280.py`. See the script for the use of sync and debug options at the end of the script to test.

## Documentation
See the REAME's and docs directory for descriptions how to prepair the HW, python software and Pi OS for the different modules.

`CONTENT.md` will give an overview of the files and short description.

## Operation status:
See the various README/docs directory for the plugin's and modules for the status of operation, development status, or investigation.

Failures on internet connectivity and so retries of access is provided.

## Current development focus
The MySense framework/infrastructure is operational. By default MySense uses a so called lightweight process (multithreaded) to allow sensor data to be collected asynchronously..
Input is tested with serial, I2C-bus and GPIO sensors.
The focus is to allow Grove based sensors (easier to plugin to the MySense system) and weather resistent cases for the system.

![Pi Breadboard in action](https://www.github.com/teusH/MySense/tree/master/images/MySense0.png)

A picture of the breadboard with Dylos and Raspberry Pi3

The gas sensor development (NO2, O3, NH3, CO) is just (Febr 2017) started.

## Calibration
Calibration of dust counters like Shinyei, Nova SDS011 and Dylos is started in May/June 2017.

Calibration of Alpha Sense gas sensors is a problematic area. Probably June 2017.

To facilitate measurements for calibration purposes all sensor plugins are optionaly (set `raw` option to `True` for the particular sensor in `MySense.conf`) able to output on file or to an InFlux DB server the *raw* measurements values, as follows:
```
    raw,sensor=<type> <field1>=<value1>,<field2>=<value2>,... <nano timestamp>
```
This is an InFlux type of telegram, where the UNIX timestamp is in nano seconds. Example for database BdP_02345pa0:
```
    raw,sensor=bme280 temp=25.4,rh=35.6,pha=1024 1496503325005000
    raw,sensor=dylos pm25=250,pm10=15 1496503325045000
```
E.g. download the *serie* for eg correlation calculation from this server or into a CVS file (`awk` maybe your friend in this).
Or use a file, say `MyMeasurements_BdP_02345pa0.influx`.
```shell
    # send the file to the InFluxdb server via e.g.
    curl -i -XPOST 'http://localhost:8086/write?db=BdP_02345pa0&u=myname&p=acacadabra' --data-binary @MyMeasurements_BdP_02345pa0.influx
```
InFlux query reference manual:
* https://docs.influxdata.com/influxdb/v1.2/query_language/

Using the Influx CLI (command line interface) one is able to convert the columnized output into whatever format, e.g. to CSV:
```
    influx --format csv | tee InFlux.csv
    >auth myname acacadabra
    >use db_name
    >show series
    >select * from raw order by time desc limit 1
    >select * from raw where time > now() - 2d and time < now() - 1d order by time desc
    >quit
```

After the correlation calculation set for the sensor the `calibration` option: e.g. `calibration=[[25.3,-0.5],[13.5,63.203,0.005]]` for here two fields with a linear regression: `<calibrated value> = 25.3 - 0.5 * <measured value>` for the first field values. The second field has a 2-order polynomial as calibration.

To avoid *outliers* the MySense input multi threading module will maintain a sliding average of a window using the buffersize and interval as window parameters. Python numpa is used to delete the outliers in this window. The parameters for this filtering technique are default set to a spread interval of 25% (minPerc MyThreading class parameter)) - 75% (maxPerc). Set the parameters to 0% and 100% to disable outlier filtering. Set busize to 1 to disable sliding average calculation of the measurements.

For calibration the Python tool `statistics/Calibration.py` has been developped. The script uses pyplot and is based on numpy (numeric analyses library). The calibration uses values from two or more database columns, or (XLSX) spreadsheets, or CSV files as input and provides a best fit polynomial (dflt order 1/linear), the R square and shows the scattered plot and best fit graph to visualize the difference between the sensors. Make sure to use a long period of measurements in a fluctuating environment (a fixed indoor temperature measurement comparison between two temp sensors does not make much sense).

## Funding
There is no funding (costs to many time of the developers).
Money is lacking for sensors reseach and travel expenses coverage.

## Licensing:
FSF GPLV4
Feedback of improvements, or extentions to the software are required.
* Copyright: Teus Hagen, ver. Behoud de Parel, the Netherlands, 2017

## References
A list of references for the documentation and/or code used in MySense.py:
* http://opensense.epfl.ch/wiki/index.php/OpenSense_2
* http://mysensors.org
* http://opensensors.io
* http://mydevices.org (Cayenne)
* MIT Clairity CEE Senior Capstone Project report V1 dd 15-05-14
* Waag Society Amsterdam Smart Citizens Lab Urban AirQ
* Citi-Sense
* Smart-Citizen-Kit
* smartemission
* polluxnzcity
* AirCastingAndroidClient
* Mosquitto
* smart-city-air-challenge (USA GOV)
* InFluxData.com
