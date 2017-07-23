# MySense
## Description
Software Infrastructure or framework for managing environmental sensors and data aquisition

## Goal
Provide a generalised dynamic Open Source based infrastructure to allow:
* environmental measurements with sensors
* data acquisition
* dynamic transport of data to other data systems: e.g. databases, mosquitto, Influx,...
* data storage and archiving
* access for free visualisation
* free availability  of the data
* free availability of all software (GPLV4 license)

## Scripts
All scripts are written in Python 2. Python 3 is supported but not tested well.
Scripts have been tested on Raspberry Pi (2 and 3) running Wheezy and Jessie Debian based OS.
Scripts have a -h (help) option. With no arguments the script will be started in interactive mode. Arguments: *start*, *status*, *stop*.
### Support scripts
* MyLed.py: control the Pi with button to poweroff and put it in wifi WPA mode. Pi will set up a wifi access point `MySense` if no internet connectivity could be established via wifi or LAN.
* MyDisplayServer.py, a display service: messages received will be shown on a tiny Adafruit display.
### Main script
The main python script is MySense.py. It acts as intermediate beween input plugins and output channels. It uses `MySense.conf` (see MySense.conf.example) to configure itself.
The MySense configuration file defines all plugins available for the MySense.py command.

* input (modules) plugins: temperature, dust, etc. sensor device modules and brokers
* output (modules) channels: console output, (MySQL) database, (CSV/gspread) spreadsheets, and brokers (mosquitto, InFlux, ...).

Try `./MySense.py --help` to get an overview.

On the command line the option --input and --output plugins can be switched on (all other configured plugins are disabled).
#### operation phases
MySense starts with a configuring phase (options, arguments, reading configuration, loading modules), whereafter in the `readsensors()` routine it will first access the input modules to obtain measurement values, combine them into an internal buffer cache per output channel, and finaly tries per output channel to empty the queued records.

The output of sensor values to an output channel will always on startup to send an identification json info record.
Each configurable interval period of time MySense will send (input) measurements values to all configured output channels. For each output channel connected via internet MySense will keep a queue in the case the connection will be broken. If the queue is exceeding memory limits the oldest records in the queue will be deleted first.
If the configured *interval* time is reached it will redo the previous loop.

If switched on and configured an email with identification information will be sent to the configured user.
Make sure one obeys the Personally Identifiable Information ([PII]http://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-122.pdf) privacy rulings.

### Plugin configuration 
MySense.conf is the configuration/init file from which plugin or modules are imported into the MySense process. See the `MySense.conf.example` for all plugins (sections) and the plugin options.

For every plugin module there is an README.plugin with explanations of the input/output plugin.
The input from sensors is read asynchronous (in parallel) via the module MyTHREAD.py.
If needed it can be switched to read only in sync with the other input sensors.

A working example of MySense script in todays operation:
```
          remote access             |  INTERNET (wired/wifi)
          syst.mgt.     webmin -----||_ wifi AP -- webmin/ssh system mgt
                    ssh tunnel -----|
                    Weaved IoT -----|
                                    |
                                    |    
    INPUT PLUGINs                 __|__      OUTPUT CHANNELS    GATEWAY/BROKER
    DHT11/22-meteo ---GPIO---->| ///|\\\ |>- CSV                _____
    GPS-locator ------RS232--->|=MySense=|>- console         | ///|\\\ |
    RSSI-wifi signal-strength >||  Pi3  ||>- MYSQL           |=MySense=|>-gspread
    Dylos-dust -USB-- RS232--->||Jessie ||>- Mosquitto pub-->|| Debian ||>-MySQL
    Grove-loudness ---GPIO---->| \\\|/// |>- HTTP-Post       || Linux ||>-CSV
    EMS280 -meteo ----I2C----->|    |    |>- email info      | \\\|/// |>-console
    PPD42NS -dust-Arduino-USB->|    |    |>- InFlux publish  |         >-InFlux pub
    Nova SDS011 -dust -USB --->|    |    |>- display SSD1306
    Plantower PMS7003 -USB --->|    |    |>- Google gspread (alpha)
    LoRaWan (planned) -------->|    |    |>- broker? (planned)
    Mosquitto sub ----server ->|    |    |>- LoRaWan (planned)
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
See for an example the file: `testdata/Output_test_data.py`

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

## Hardware Platform
Sensors have a hardware interface to I2C, GPIO: those sensors are tested on RaspBerry Pi (and Arduino Uno)
Sensors with USB serial are tested on Linux Debian platforms which run Python.

## Installation
See README.pi for installation of the Raspberry Pi platform.
MySense plugins: Use the shell file `INSTALL.sh [DHT GPS DB plugin ...]` to download all dependent modules.

The sensor plugins, and output modules can be tested in *standalone mode*, e.g. for BME280 Bosch chip, use `python MyBME280.py`. Or use the Python debugger `pdb` in stead. See the script for the use of sync and debug options at the end of the script to test.

## Documentation
See the REAME's and docs directory for descriptions how to prepair the HW, python software and Pi OS for the different modules.

`CONTENT.md` will give an overview of the files and short description.

## Operation status
See the various README/docs directory for the plugin's and modules for the status of operation, development status, or investigation.

Failures on internet connectivity and so retries of access is provided.

## Extensive test support
Use the following first if one uses MySense for the first time: test each sensor input or output channel one at a time first.
Use the Conf dictionary to set configuration for the test of the module.

The sensor plugin as well the output pugin channels *all* have a `__main__` test loop in the script.
This enables one to test each plugin (one at a time) in standalone modus: `pdb MyPLUGIN.py`.
Use for the sensor input plugins `Conf['sync']=False` (to disable multithreading) and switch debug on: `Conf['debug']=True`.
Set the python debugger `pdb` to break on `break getdata` (input plugin) or `break publish` for stepping through the script. Failures in configuration are shown in this way easily.

After you have tested the needed input/output modules: To test the central script `MySense.py` use first the Python debugger `pdb`. The main routine after the initiation and configuration phase is `sensorread`, in `pdb` use `break sensorread`. Continue to this break point and use `print Conf` to show you the configuration settings. Step to the first `getdata` call or `publish` call to go into the input or output module.
Note that the `getdata()` input routine may need some time in order to allow the module to collect measurement(s) from the sensor.

## Current development focus
The MySense framework/infrastructure is operational (alpha phase).

By default MySense uses a so called lightweight process (multithreaded) to allow sensor data to be collected asynchronously.
Input is tested with serial, I2C-bus and GPIO sensors (meteo,dust,geo,audio, (gas in July 2017).
The focus is to allow Grove based sensors (easier to plugin to the MySense system) and weather resistent cases for the system.

![Pi Breadboard in action](images/MySense0.png)

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

### Calibration tool
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
* MIT Clairity CEE Senior Capstone Project report V1 dd 15-05-14
* https://www.challenge.gov/challenge/smart-city-air-challenge/ Smart City Air Challenge (2016, USA GOV)
See also: https://developer.epa.gov/air-pollution/
* http://opensense.epfl.ch/wiki/index.php/OpenSense_2
* http://mysensors.org
* http://opensensors.io
* http://mydevices.org (Cayenne)
* https://waag.org/nl/project/urban-airq Waag Society Amsterdam Smart Citizens Lab Urban AirQ
* http://www.citi-sense.eu/ Citi-Sense EU project
* http://waag.org/nl/project/smart-citizen-kit Smart-Citizen-Kit Waag Society
* http://smartemission.ruhosting.nl/ Smart Emission, Maps 4 Society Nijmegen
* https://github.com/guyzmo/polluxnzcity Pollux NZcity, NZ
* https://github.com/HabitatMap/AirCastingAndroidClient AirCasting on Android Client
* https://mosquitto.org/ Mosquitto (MQTT) broker
* https://docs.influxdata.com/influxdb/v1.2/ documentation from InFluxData.com
* https://cdn.hackaday.io/files/21912937483008/Thomas_Portable_Air_Quality.pdf interesting overview of sensors
