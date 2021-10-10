# MyDatacollectornapplication
$Id: README.md,v 1.1 2021/10/10 13:24:01 teus Exp teus $

## An outline of the data aquisition, monitoring, eventhandling and adatforwarder
MyDatacollector is a Python application to run as a deamon service downloading measurement data from (MQTT) brokers, monitoring the measurement kit operations, handling measurement kit events, while sending event notices via email or chat service (Slack), updating meta information of the measurement kits and forwarding the data to a collection of output channels as terminal console, measurment database, and different data portales as Sensors.Community, RIVM etc.

The datacollector has an enormous amounbt of functionality. Mainly to improve data aquisition and to provide a high quality operation of measurements over long periods.
This requires to configure the application in a thoroughfull way.
To limit the amount of notices repition of notices is kept to a configurabble minimum.

The scripts should run with either Python 2 or 3.

## licence
Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs

Copyright (C) 2019-2021, Behoud de Parel, Teus Hagen, the Netherlands.
Open Source Initiative  https://opensource.org/licenses/RPL-1.5

   Unless explicitly acquired and licensed from Licensor under another
   license, the contents of this file are subject to the *Reciprocal Public
   License ("RPL")* Version 1.5, or subsequent versions as allowed by the RPL,
   and You may not copy or use this file in either source code or executable
   form, except in compliance with the terms and conditions of the RPL.

   All software distributed under the RPL is provided strictly on an "AS
   IS" basis, WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESS OR IMPLIED, AND
   LICENSOR HEREBY DISCLAIMS ALL SUCH WARRANTIES, INCLUDING WITHOUT
   LIMITATION, ANY WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
   PURPOSE, QUIET ENJOYMENT, OR NON-INFRINGEMENT. See the RPL for specific
   language governing rights and limitations under the RPL.

Use of all sources under these condition implies a contribution in the form of code contribution, documentation, improvements or donations to MySense.
This enables us to continue withg more MySense developments as well to share the knowledge and experience.
It is not a free beer.
Make sure to use a phrase 'based on MySense' (Behoud de Parel Association) in all publications and reports when you use MySense software.

## configuration
The datacollector and input/output modules are highly configurable.
See the Python module(s) for e.g. 'Conf' dict for all the details.
Every input/output module can be tested on a stand alone base which eases testing and debugging. A set of examples is provided for this.
From the commandline (and with environment variable setting as
eg DBPASS=acacadabra, DBHOST=localhost, DBUSER=myself)
the datacollector configuration can be changed (try help).
E.g. 'community:output=false' will switch forwarding to Sensors.Community OFF.
Use the 'help' argument for more details.

## input channels (broker input channel modules)
It is possible to read measurement data from several (MQTT eg TTN V2 or V3 stack) simultaniously. The datacollector is able to detect data in TTN V2 or V3 automatically. Currently only MQTT broker input is implemented. With this as example eg InfluxDB or HTTP POST broker should be easily implemented.
To allow input from raw MQTT data e.g. commandline mqttclient application the datacollector is able to read data from several file(s): use file=file_name as CLI argument.

On (MQTT) broker connection problems the datacolelctor will try to reconnect and will send an event email on too many errors. If needed it will slow down the reconnecvt or in the end give that input channel up.

MyMQTTclient module is taking care of uploading measurement data from an MQTT broker (TTN V2 and/or V3 TTN broker) as well restore of MQTT data from a file. The module will use MyLoRaCode module to decode raw LoRa payloads with decode LoRa engine rules.
It is expected that every LoRa port has it's own decoding rules. See the comments in this module for more details.
The LoRa (TTN V2/V3) json format will be converted to the (internal) Measurement Data Echange Format (MDEF format). The internal MDEF format is very close to the proposed (MySense) MDEF standard proposal.

The datacollector will collect gateway information from each uploaded MQTT datagram for supporting statistics about which gateways in that region are forwarding datagrams to eg TTN. The information is stored in the datagram cache with signal strength information. To Do: make this information available in the database.

## output channels
Measurement data is forwarded via a dynamic configurable scheme of output channel modules as MyARCHIVE (MySense MySQL database), MyCONSOLE (terminal/console), and/or MyCOMMUNITY (Sensors.community, RIVM and other data portals).
As Sensors.community does not calibrate dust data from different dust sensor manufacturers, if possible the dust data is corrected via a regression scheme (measurements from 3 different dust sensors over a period of half a year in 2020) to the sensors from Sensirion. If needed a simple configuration change it can be switched of or to use a different sensor type. See Conf dict in MyCOMMUNITY module for more details.

The MySQL database (luchtmetingen) has for every measurement kit a measurement table 'project_serial'. If the kit is set 'active' (see meta data section Sensors table) the table will be automatically created and will have so called 'field's for every sensor field it encounters. Fields or columns are automaitcally added on the fly. Every measurement entry will have an id, timestamp, field(s), field validation (None if kist is in repair), and 'sensors' (senor type names configured in the kit).
Project name and seriaid are the reference id used in other (meta) database tables.

The output channel modules API is done via the module 'publish' routine.
Routine arguments:
- meta information (datagram count, sensor types, correction/calibration info, measurment unit info and id: project/serial). See the module for MDEF details and examples.
- data or measurement record. Example of MDEF format: `{"SHT31": [("temp",11.3,"C"),...]}'
- artifacts list encountered by the data collector as eg "Forward data", malfunctioning sensors, out of band values, static values, etc.

The datacollector uses a field name translation configuration tabel to translate sensor field names to the fields names as used in the MySQL database. E.g. translate 'temperature' to 'temp', 'RH' to 'rv', 'pressure' to 'luchtdruk', etc. Fields names are case independent.

## meta measurement kit data
The MySQL database has a few tables to describe meta data for each measurment kit:
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
Notices are about events, malfunctioning sensors, measurment faults (dead for more as 2 hours) to the 'owner', project manager, and operational manager.

## event handling
A measurement kit kan generate an event (low accu level, watchdog event, programming error, etc). The event number is translated to a name and priority. All events are logged. Priority will decide if a notice is generated as well. Event handling cannot be switched off.
Note that a measurement kit can remotely via LoRa be instructed for configuration change or even be switched off. This event will be received by the datacollector as well.

## logging
Default logging output (priority driven: info, ..., debug) is on standard error terminal. Configuration allow to forward logging to the OS syslog system, or even for remore simple access to a named pipe.
It is possible to configure each module with a different priority level.

## upgrading DB
MyDatacollector is dependent on meta information and measurment data tables.
These tables have had some changes in supported tables fields/columns. 
To update the elder DB please use the bash update script.

The MyAdmin script needs some update to the newer table schemes yet.

Measurement data is visualised via a CMS Drupal website. Drupal uses it's own database tables. So this type of tables need to be synchronised for meta information (locality etc). For this the script 'SyncWebDB.py' has been made available. However this script needs still to be upgraded with the newer DB table architecture yet.
The tables 'Sensors' and TTNtable' are still the main single source for the information.

## Measurement Data Exchange Format (MDEF format, 2021 draft standard)
The Measurement Data Exchange Format (MDEF) will be described in a separate README document. All modules will have runtime how-to examples for a more practical road to do an implementation and to test the data exchange.
The MDEF, based on 4 years of developments, is still in development and in concept as long as the implementation is only done on one or two implementation efforts. 

## data collector software architecture

### initialisation phase
See 'MyDatacollector.py' `__main__` section:
- Configure() routine will do initial configuration. The configuration is overwritten by the local configuration as supplied by 'MyTTN-datacollector.conf.json' (see the example file for a details).
- ImportArguments() routine will overwrite initial configuration from arguments supplied from commenand line.
- UpDateChannelConf() routine will setup input and output channels and configure those modules as well the library or support modules e.g 'MyGPS' (handle GPS location information), 'MyDB' (DB meta information and DB access routines), 'MyPrint' (use of colred terminal printout), 'MyThreading' (multithreading toolset), etc..
- Initialize() wrap up and enable input/output modules.

### Main run loop
The routine RUNcollector() is the main run loop routine.
It collects measurement datagrams from an input queue, which is loaded by the multithreaded input broker module(s) via a call to GetDataRecord().
GetDataRecord will first collect the meta information (a cached item per measuremnt kit active) 'info' and the MDEF 'data'gram. This information is passed to the 'Data2FGrwrd()' routine.
Data2Frwrd() will check if the measurement kit is behaving well (will throddle the kit datagram if needed so).
Next it datagram will be checked if the datagram is uploaded from a known measurement kit.
On the event that the kit clearly has been restarted this will be notified.
If the kit was disabled for some reason the datagram will be skipped and an event is raised.
From that point the datagram is checked if meta data (DB tables 'Sensors', 'TTNtable' and 'SensorTypes') needs to be changed in the database (write through cache) as e.g. new home location or is clearly in a repair situation (locality differs from home location).
Gateway statistics is updated.
Finally the datagram is checked if there is data for valid data, measurments to be forwarded, and which measurements are provided from known sensor types. If needed meta data will be corrected as well calibration reference sensor types and measurement correction information is attached to the cached meta information.
Data2Frwrd() routine will collect so called 'artifacts' as provided from the different checking routines.
This artifacts list is hand over to the output channels/modules publish() routines.

Next the meta cache item and measurement datagram (in MDEF format) will be provided to each output channel 'publish()' routine.
The result (True, False, remarks) will be handled and monitored/logged. Whereas the loop is continued as long as there are input channels active.

