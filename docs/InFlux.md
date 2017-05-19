## output channel InFlux publicize
status beta test 2017-05-19
### DESCRIPTION
InFlux from InFluxdata.com is a http oriented telegram timed data infrastructure with a simple sql type of functionality.

The documentation e.g. `https://docs.influxdata.com/influxdb/v0.8/api/reading_and_writing_data/` is in development. Versions vary abit in functionality. Documentation is changing and provided examples have to be used with care. The json support seems to be deprecated. So json is not used in this MySense application.

The type of data acquision is simular to mosquitto, which has full json support.
The retention and sql capability are of help in the data acquisition with InFlux.

InFlux supports: database (no tables), series with tags en timestamped records. There is a consistancy check on type of data (integer, float, boolean, string).

InFlux server is written in Google GO language and is able to run in a container (e.g. Docker).
The InFlux software is available from github: 
* https://github.com/influxdata/influxdb
* https://github.com/influxdata/influxdb-python
*   `wget https://dl.influxdata.com/influxdb/releases/influxdb_1.2.2_amd64.deb
    sudo dpkg -i influxdb_1.2.2_amd64.deb`

### SECURITY
Access control is per user (read/write/all) per database. Make sure to have the credentials confugured in the server. By default the security is disabled.
https as transport method is not yet used in this application.

### INSTALLATION
```shell
sudo apt-get install influxdb # installso the server
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


