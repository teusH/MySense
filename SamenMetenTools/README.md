# MySense Samen Meten Tools
Last update of the README on 30 August 2024

## Description
Python toolset to do air quaility data analistics on measurement data from low-cost stations.
This is work in progress, inspirated by the Samen Meten Tools from Zuinige Rijder (Rick).
Current (first) module is to provide a Python engine to obtain meta stations information in Python dict format and sensor observation data over a period of time in Python Pandas format for processing these website queries results by other tooling.

## Outline of modules
### SamenMetenThings.py
The Samen Meten Things module provides a python interface to the RIVM Things API (an API) and various other website query services like Open Data Soft (CBS queries) and Open Street Map (addresses of stations).
The main routines are able to collect meta information (status information of the station, installed sensors and sensor types, period of availability, location (resolytion is ca 100 meters), address, reference stations), neighbouring stations in a region, stations in a municipality of near a GPS location) and observation data in a period of time in Pandas format.
The routines can be called as stant alone for test purposes.

The module is operating in multiprocessing modus. This gives a factor of 2-5 of speedup.
E.g. a website query can take 2-30 seconds (usualy 15 seconds). To obtain foe one sensor of a station it takes about 2 information requests, and 1 observation requests per sensor. A station has about 4-6 sensors. A municipality has about 100 stations: 100 X (2 X 5 X 6) X 15 seconds if done sequently.
The amound of records in one observation stream is not the main delay factor.

The current version is in alpha status and subjected to improvementrs and extent with more or better functionality.

The module consists about of 50% of documentaion and help texts. It gives a good overview of backgrounds of the website query interfaces and use.
So read the module script!

### Things2Xlsx.py
Things2Xlsx will generate XLSX spreadsheet with overview of Things station names, location (GPS, address),
station properties (owner, project, gemcode, reference station codes),
and operational data of installed sensors (type, first and last timestamps, record count).
The spreadsheets will show per sheet the historical and current stations information.

The script uses municipality stations routine of the SamenMetenThings class module.

## Licensing
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


