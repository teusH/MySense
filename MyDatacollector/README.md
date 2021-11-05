# MyDatacollectornapplication
## An outline of the data aquisition, monitoring, eventhandling and adatforwarder
MyDatacollector is a Python application to run as a deamon service downloading measurement data from (MQTT) brokers, monitoring the measurement kit operations, handling measurement kit events, while sending event notices via email or chat service (Slack), updating meta information of the measurement kits and forwarding the data to a collection of output channels as terminal console, measurement database, and different data portales as Sensors.Community, RIVM etc.

## license
Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs

Copyright (C) 2021, Behoud de Parel, Teus Hagen, the Netherlands
Open Source Initiative  https://opensource.org/licenses/RPL-1.5

   Unless explicitly acquired and licensed from Licensor under another
   license, the contents of this file are subject to the Reciprocal Public
   License ("RPL") Version 1.5, or subsequent versions as allowed by the RPL,
   and You may not copy or use this file in either source code or executable
   form, except in compliance with the terms and conditions of the RPL.

   All software distributed under the RPL is provided strictly on an "AS
   IS" basis, WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESS OR IMPLIED, AND
   LICENSOR HEREBY DISCLAIMS ALL SUCH WARRANTIES, INCLUDING WITHOUT
   LIMITATION, ANY WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
   PURPOSE, QUIET ENJOYMENT, OR NON-INFRINGEMENT. See the RPL for specific
  language governing rights and limitations under the RPL.

Use of all sources under these condition implies a contribution in the form of code contribution, documentation, improvements or donations to MySense.
It is not a free beer.

## configuration
The datacollector and input/output modules are highly configurable.
See the Python module for e.g. Conf dict for all details.
Every input/output module can be tested on a stand alone base which eases testing and debugging. A set of examples is provided for this.
The (default) init file (MyDatacollector.conf.json, see MyDatacollector.conf.json.example) defines a lot of configuration defaults.
The database access information e.g. MySQL credentials for the tables) is taken from the init file. Database credentials may be taken from environment variables (e.g. DBPASS=acacadabra, DBHOST=localhost, DBUSER=myself)
when the configuration item 'MyDB' in the init file is undefined.
Broker access information has to be defined via the init file.

From the command line one is able to redefine e.g. inputr and output channels.
E.g. 'community:output=false' will switch forwarding to Sensors.Community OFF.

## input channels (broker input channel modules)
It is possible to read measurement data from several (MQTT eg TTN V2 or V3 stack) simultaniously. The datacollector is able to detect data in TTN V2 or V3 automatically. Currently only MQTT broker input is implemented. With this as example eg InfluxDB or HTTP POST broker should be easily implemented.
To allow input from raw MQTT data e.g. commandline mqttclient application the datacollector is able to read data from several file(s): use file=file_name as CLI argument.

On (MQTT) broker connection problems the datacolelctor will try to reconnect and will send an event email on too many errors. If needed it will slow down the reconnecvt or in the end give that input channel up.

MyMQTTclient module is taking care of uploading measurement data from an MQTT broker (TTN V2 and/or V3 TTN broker) as well restore of MQTT data from a file. The module will use MyLoRaCode module to decode raw LoRa payloads with decode LoRa engine rules.
It is expected that every LoRa port has it's own decoding rules. See the comments in this module for more details.
The LoRa (TTN V2/V3) json format will be converted to the (internal) Measurement Data Echange Format (MDEF format). The internal MDEF format is very close to the proposed (MySense) MDEF standard proposal.

The MyMQTTclient modue will try to automatically reconnect. On too many reconnects the MQTT broker will be disconnected. If no input channels are available anymore the data collector will exiting.

## output channels
Measurement data is forwarded via a dynamic configurable scheme of output channel modules as MyARCHIVE (MySense MySQL database), MyCONSOLE (terminal/console), and/or MyCOMMUNITY (Sensors.community, RIVM and other data portals).
As Sensors.community does not calibrate dust data from different dust sensor manufacturers, if possible the dust data is corrected via a regression scheme (measurements from 3 different dust sensors over a period of half a year in 2020) to the sensors from Sensirion. If needed a simple configuration change it can be switched of or to use a different sensor type. See Conf dict in MyCOMMUNITY module for more details.

The MySQL database (luchtmetingen) has for every measurement kit a measurement table 'project_serial'. If the kit is set 'active' (see meta data section Sensors table) the table will be automatically created and will have so called 'field's for every sensor field it encounters. Fields or columns are automaitcally added on the fly. Every measurement entry will have an id, timestamp, field(s), field validation (None if kist is in repair), and 'sensors' (senor type names configured in the kit).
Project name and kit serial id are defining the reference id used in other (meta) database tables.

The output channel modules API is done via the module 'publish' routine.
Routine arguments:
- meta information (datagram count, sensor types, correction/calibration info, measurement unit info and id: project/serial). See the module for MDEF details and examples.
- data or measurement record. Example of MDEF format: `{"SHT31": [("temp",11.3,"C"),...]}'
- artifacts list encountered by the data collector as eg "Forward data", malfunctioning sensors, out of band values, static values, etc.

The datacollector uses a field name translation configuration tabel to translate sensor field names to the fields names as used in the MySQL database. E.g. translate 'temperature' to 'temp', 'RH' to 'rv', 'pressure' to 'luchtdruk', etc. Fields names are case independent.

## meta measurement kit data
The MySQL database has a few tables to describe meta data for each measurement kit:
- 'Sensors': table with project/serial id's, location, sensor types configuration, operational info (active, in repair). The datacollector will complete info as eg geohash information, street, village, in repair when location if not the homelocation, installation home location, etc. on the fly. The datacollector uses a write throug cache to avoid too many accesses to the database server.
- 'TTNtable': table with forwarding information to database, portals and project/serial match with TTN topic/device id.
- 'SensorTypes': table with information about different sensor types of sensor manufacturers, sensor names, sensor correction

The meta in formation uses MDEF format. For details and examples see MyDatacollector.

The MySQL tables 'Sensors' and 'TTNtable' are initialy created when needed. However do not have meta data at that time. In order to update these table with meta measurement kit information the Python script 'MyAdmin.py' is provided. The script needs as input a json file with basic information. If needed the script will complete eg location information from other info in the json input file. E.g. from longitude and latitude the street, village, etc information is obtained via internet search.

The bash script 'MyDB-upgrade.sh' is a scriot which will upgrade the MYSQL database to a newer release. E.g. support of sensor types, SensorTypes DB table, geohash, etc.

## monitoring
Default the MyDatacollector the monitor output is switch ON (monitor:output=true).
On standard error output monitoring (global processing) information will be supplied.
Information about timestamp, measurement kit name, sensor types in the datagram and result of data forwarding.

## notices mechanism
By default notices via email or chat notices service (eg Slack) will be active (notices:output=true).
Notices are about events, malfunctioning sensors, measurement faults (dead for more as 2 hours) to the 'owner', project manager, and operational manager.

## event handling
A measurement kit kan generate an event (low accu level, watchdog event, programming error, etc). The event number is translated to a name and priority. All events are logged. Priority will decide if a notice is generated as well. Event handling cannot be switched off.
Note that a measurement kit can remotely via LoRa be instructed for configuration change or even be switched off. This event will be received by the datacollector as well.

## logging
Default logging output (priority driven: info, ..., debug) is on standard error terminal. Configuration allow to forward logging to the OS syslog system, or even for remore simple access to a named pipe.
It is possible to configure each module with a different priority level.
One can configure via Conf['file'] the way logging is done: sys.stderr.write, syslog, name pipe, or a logfile.

## upgrading DB
MyDatacollector is dependent on meta information and measurement data tables.
These tables have had some changes in supported tables fields/columns. 
To update the elder DB please use the bash update script.

The MyAdmin script needs some update to the newer table schemes yet.

Measurement data is visualised via a CMS Drupal website. Drupal uses it's own database tables. So this type of tables need to be synchronised for meta information (locality etc). For this the script 'SyncWebDB.py' has been made available. However this script needs still to be upgraded with the newer DB table architecture yet.
The tables 'Sensors' and TTNtable' are still the main single source for the information.

## Python standard modules
You should be able to run the scripts on Python 2 or 3.

Make sure you have installed the Python modules.
Usualy the system standard modules are installed.  The modules dateutil.parser, jsmin, mysql.connector and paho.mqtt.client has to be installed.
From which jsmin, paho.mqtt.client and mysqwl.connector are not supported in the last Debian distributions anymore.
Geohash module: use 'pip install pygeohash' if needed so.
Try this by using the following Python script.
` Python -e '
import atexit
import base64
import copy
import datetime
import dateutil
import email.mime
try: import pygeohash
except: import geohash # if not use copy python3 module
import geopy
import inspect
import jsmin
import json
import lib
import logging
import math
import mysql
import os
import paho.mqtt
import platform
try: import queue
except: import Queue
import random
import re
import requests 
import signal
import smtplib
import socket
import struct
import subprocess
import sys
import threading
import time
import traceback
import xtermcolor
'
`
An example to create initial tables for MySQL database: Use  `MySQLdbSetup.sql`.
