## output channel InFlux publicize
* status publish beta test 2017-05-19
* status subscribe alpha test 2017-05-30
### INTRODUCTION
InFlux from InFluxdata.com is a http oriented telegram timed data infrastructure with a simple sql type of functionality.

The documentation e.g. `https://docs.influxdata.com/influxdb/v1.2/api/reading_and_writing_data/` is in development. Versions vary abit in functionality. Make sureuse the right version of the InFlux documentation. Documentation is changing and provided examples have to be used with care. The json support seems to be deprecated. So json is not used in this MySense application.

The type of data acquision is simular to mosquitto, which has full json support.
The retention and sql capability are of help in the data acquisition with InFlux.

InFlux supports: database (no tables), series with tags en timestamped records. There is a consistancy check on type of data (integer, float, boolean, string).

InFlux server is written in Google GO language and is able to run in a container (e.g. Docker).
The InFlux software is available from github: 
* https://github.com/influxdata/influxdb
* https://github.com/influxdata/influxdb-python
*   `wget https://dl.influxdata.com/influxdb/releases/influxdb_1.2.2_amd64.deb
    sudo dpkg -i influxdb_1.2.2_amd64.deb`

### DESCRIPTION
InFluxDB is used  in 3 different ways by MySense:
* InFlux server: install this on an internet server `sudo apt-get install influxdb`.
* InFlux client publisher MyINFLUXPUB.py. Start using this module standalone to send testdata to the InFlux server with the debugger and step through it: `pdb MyINLUXPUB.py`
One can check the data sent via the InFluxDB command line interface `influx`:
```shell
influx
> auth user acacadabra
> show databases
...
> use PrJ_12345678
> show series
...
> select * from info
...
> select * from data
...
```
* InFlux client subscriber. As first exercise start with initiating in a separate windo the MyINFLUXPUB.py to send records to the server. Check the `Conf[option]` in the MyINFLUXSUB.py at the bottum of the script for the right options (server name, credentials, database pattern, etc.).
Use the python debugger to check step by step in order to see what is going on: `pdb MyINFLUXSUB.py`. Finally add the channel in the MySense.conf. Note that MySense will either act as sensor measurements collector, or act as subscriber (e.g. MQTT subscriber or InFlux subscriber).

### SECURITY

```
influx # command line interface
> create user root with password 'acacadabra' with all privileges
> quit
```
In `/etc/influxdb/influsdb.conf` set in section `[http]` `auth-enabled = true`.
https as transport method is not yet used in this application.

MySense is using user.password credentials (no https yet). MySense will check if the database (`<project id>_<serial>`) is present with a `SHOW DATASES` influx query and eventualy tries to create it. This will fail on non admin rights and output a warning which is passed. 
Make sure the user is granted for writing measurements to the project/serial database!
```
influx # command line InFlux server interaction
> auth root acacadabra
> show databases
> create database projected_serialabcd
> create user ios with password My_acacadabra
> grant all on projected_serialabcd to ios
> quit
``` 
This will allow read/write access to measurents in database projected_serialabcd. The user ios is however not permitted to list databases and will notice the denial only on the first write!

### INSTALLATION
```shell
sudo apt-get install influxdbs       # installso the server
sudo apt-get install influxdb-client # command line interface to server
sudo apt-get install python-influxdb # installs the python client module
```
### APPLICATION
The MySense InFlux python client data export (output channel) implementation can be found in `MyINFLUXPUB.py`.
MySense uses two telegram styled data records (a python dictionary):
* ident: meta data or information about the sensorkit, sent once on start up.
* data: time (UNIX time stamp), sensor name and value(s).
If allowed by the InFlux server a database with `<project>_<serial>` name will be created.
* The time resolution used is 'seconds' ('s'). The InFlux default is nano seconds.
* Retention is set by the server configuration.
* *info* and *data* series are tagged with the *label* identifier. *data* series will also be tagged with the *new* tag (first data values joined with the *info* record).
* InFlux timing is time of record entry.
* All strings are sent double quoted. Comma's will have an backslash escape.

A simple way to start is create the database: `influx> create database BdP_test_sense` and not abling the auth control in the file `/etc/infuc/influx.config`.

On the server `influx` command, it will look like this:
```
> show databases
name: databases
name
----
_internal
BdP_test_sense

> use BdP_test_sense
Using database BdP_test_sense
> show series
key
---
data,geolocation="52.420635\,5.1356117\,22.9",label="alphaTest",new=0
data,geolocation="52.420635\,5.1351617\,22.9",label="alphaTest",new=1
data,geolocation="52.433\,5.22\,13",label="alphaTest",new=0

> 
> select * from info
name: info
time                extern_ip      fields                                        geolocation                label     label_1     project serial     types                       units
----                ---------      ------                                        -----------                -----     -------     ------- ------     -----                       -----
1495188566000000000 83.161.151.250 time\,pm_25\,pm_10\,dtemp\,drh\,temp\,rh\,hpa 51.420635\,6.1356117\,22.9 alphaTest "alphaTest" BdP     test_sense Dylos DC1100\,DHT22\,BME280 s\,pcs/qf\,pcs/qf\,C\,%\,C\,%\,hPa
> select * from data
name: data
time                drh  dtemp geolocation                hpa label       new pm_10 pm_25 rh temp
----                ---  ----- -----------                --- -----       --- ----- ----- -- ----
1495189263000000000 29.3 27.8  "51.420635,6.1356117,22.9" 712 "alphaTest" 1   62    318   25 28.75
1495189311000000000 29.5 27.8  "51.433,6.22,13"           714 "alphaTest" 0   63    318   26 27
1495189360000000000 29.6 27.8  "51.420635,6.1356117,22.9" 715 "alphaTest" 0   64    318   28 27.5

>
```

### TESTING
The MyINFLUXPUB.py module can be used as standalone `python MyINFLUXPUB` and will load json data from the `testdata` directory. Check the data at the InFlux with the InFlux command line: e.g.
```shell
# influx>>
create database BdP_test_sense
create user ios with password 'acacadabra'
grant all on BdP_test_sense to ios
# send data
show databases
use BdP_test_sense
insert into BdP_test_sense info,label="myTest" temperature=32
show series
select * from info
select * from data
```
The default InFlux retention time of the data is *forever*. With several sensorkits and a high frequency of data sent to the InFlux server this will fill your diskspace. So one might configure the retention time to a better period of time. Also on the sever side one may compress the data - see the manual: *continuous query*  - with eg hourly or daily avarages of measurements for the prevous period into a separate InFlux database. See the how to Influx documentation:
* https://docs.influxdata.com/influxdb/v1.2/guides/downsampling_and_retention/
