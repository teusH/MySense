MySense
=======

Goal
----
Provide a generalised dynamic Open Source based infrastructure to allow environmetal measurements data acquisition, dynamic transport of data to other systems, datastorage and archiving and access for free visualisation and free availability  of the data.

Main program
------------
The main python script is MySense.py
The script is the central management script beween sensor and broker input (modules) plugins (temperature, dust, etc. sensor device modules and brokers) to output modules (console output, (MySQL) database, (CSV/gspread) spreadsheets, and brokers.
Try ./MySense.py --help to get an overview.
MySense.py can be called with the argument start (or status, or stop) to start MySense as background process.
On the command line input or output plugins can be switched on or off.
The MySense configuration file defines all plugins available for the MySense.py command.
The output of sensor values to an output channel will always be preceeded (on startup) with an identification json info record.
If switched on and configured an email with identification information will be sent to the configured user.

Make sure one obeys the PII privacy rulings.

Plugin configuration 
--------------------
MySense.conf is the configuration/init file from which plugin or modules are imported into the MySense process. See the MySense.conf.example for all plugins (sections) and the plugin options.

For every plugin module there is an README.plugin with explanations of the input/output plugin.
The input from sensors is read asynchronous (in parallel) via the module MyTHREAD.py.
If needed it can be switched to read only in sync with the other input sensors.

A working example of MySense in todays operation:

    DHT-sensor ----------------|         |-- CSV
    GPS-locator ---------------|-MySense-|-- console
    RSSI-wifi-signal-strength -|  Pi     |-- MYSQL                  |--gspread
    Dylos-dust-sensor ---------|         |-- Mosquitto ---|-Mysense-|--MySQL
                                         |-- HTTP-Post       Debian |--CSV
                                         |-- email
                                         |-- Google gspread

Interaction data format
-----------------------
Interaction with plugins and output channels is done in json datastructure:
Example of json to display a measurment on the console (and others):
     { "time": UNIXtimeStamp,
        "temp": 23.2,
        "rh": 30.2,
        "pm": 234.2,
        "o3": None }

At the startup MySense.py will start with an identifaction record providing details of the version, the location if available, a unique identifier, sensor types and measurement unit, etc.
This information will define eg the first row of a spreadsheet or the database table with all sensor info (called Sensors).

Towards a broker the output will consist of an (updated e.g. GPS location) combination of the data json record and the infomration json record:
    { "ident": id-record, "data": data-record }

The input sensor plugins provide (sliding window of a per plug definable buffer size)) averages in a per input plugin defined interval time in seconds. The output is done on a general interval period timing using the average time of input timings.

Typical input rate from a sensor is 60 seconds (can be tuned) and for brokers it is 60 minute interval (can be tuned).

Brokers
-------
MySense can act either sensor manager or as input from broker manager to a set (dynamic) of output channels. 

Available input plugins:
Dust: Dylos DC1100 or 1700 via serial interface, Shinyei GPIO (e.g. Grove dust sensor)
Temperature/humidity: Adafruit DHT11/22 or AM3202 and Grove variants
RSSI (strength of wifi signal): via the platform
Location: GPS (GPS Ultimate from Adafruit/Grove) via TTL serial interface

Platform:
--------
Sensors have a hardware inrface to I2C, GPIO: those sensors are tested on RaspBerry Pi (and Arduino Uno)
Sensors with USB serial are tested on Linux Debian platforms which run Python.

Installation
------------
See README.pi for installation of the Raspberry Pi platform.
MySense plugins: Use the shell file INSTALL.sh to download all dependent modules

Operation status:
----------------
See the various README.plugin's for the status of operation, development status, or investigation.

Current development focus
-------------------------
The MySense framework/infrastructure is operational. A so called lightweight process (multithreaded).
Input is tested with serial and GPIO sensors.
Focus now is on allow Grove based sensors (easier to plugin to the MySense system) and weather resistent cases for the system
Gas sensor development (NO2, O3, NH3, CO) is just (Febr 2017) started.
Calibration of dust is started in March 2017.
Calibration of gas sensors is a problematic area

Funding
-------
There is no funding (costs to many time of the developers).
Money is lacking for sensors reseach and travel expenses coverage.

Licensing:
---------
FSF GPLV4
Feedback of improvements, or extentions to the software are required.
Copyright: Teus Hagen, ver. Behoud de Parel, the Netherlands 2017

