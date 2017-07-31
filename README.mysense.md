# MySense architecture
MySense overview:
<img src="images/MySense-logo.png" align=left width=150>
the building blocks

## STATUS
2017/02/08
<img src="images/MySense0.png" align=right width=150>
STATUS: BETA operational

## USAGE:
Note that the main python program MySense.py may need to operate fully a config or init file.
The file is looked up as program name extended with .conf: eg MySense.conf
The initfile may also be defined by the environment variable captial program name. Eg. MYSENSE=/etc/ios/MySense.ini
See the config file example for all plugin sections and plugin options.

## PLUGINS
MySense is build in a Lego fashion: as well physical Lego blocks as programmically: input plugins and output channel modules.
All plugins have the name *MyPLUGIN.py*.
python ./MySense.py --help will provide a short command line options.
Use it to see how to overwrite (disable or enable) the input and output plugins.
And how to get more logging output: eg "-l debug"
Not all plugins have been tested deeply (e.g. broker, gspread, gas, dht).
Operational plugins:
* input: dylos, Shinyei (via Arduino controller) and SDS011 dust, meteo (DHT22 and BME280
* output: MQTT: mqttsub (subscribe) and mqttpub, InFlux (publicise), db (mysql), CSV and console.

## Adding a NEW PLUGIN
Adding an input or output plugin named xyz is easy.
Keep the setup from any other plugin and create the MyXYZ.py script.
And add the xyz as section to the init/config file.
Use Conf as global var to import options for the plugin from the init file.
The input plugin needs the attribute getdata() and returns a dict with data.
The output plugin is called with the attribute publish(dict). Where dict has the keys ident, data and internet.
And returns True of False.
A plugin with the Conf key hostname will be denoted as internet access enabled.

Use pdb (python debugger) to step through the script(s) if anything goes wrong.

All input and output pluging should be able to run with pdb in a standalone mode for testing the module. Look for the __main__ part in the python script.

MySense plugins are imported as modules when the are defined in the MySense.conf configure/init file on startup. So if the plugin is not needed it will not be imported and there is at that moment no need to have the dependent python library module installed.

## INTERNET
All access via internet is guarded by user/password or signature credentials.
To enable access for input or output plugins, say the xyz plugin one need to define the user/password (gspread needs a credential signature file). The definition of the credential happens at the server site. MySense acts always as a client, eg to mosquitto (mqtt) broker, but is able to act as gateway: input mqttsub, output as mqttpub.
The password can be defined in the init/config file (not recommanded), as well be overwritten by the command environment variable XYZHOST, XYZPASS, en XYZUSER for the plugin "xyz".

MySense can operate as deamon by "python MySense.py start command". Or use status or stop as argument to eg stop the script.

## INSTALL:
Every MySense plugin modules do some python module imports.
They need to be installed in the Pi if one uses a MySense plugin module..
If pip is not installed do so with: sudo apt-get install python-pip
Install missing modules with sudo pip install <module name>

Installation of library dependencies one can use the `INSTALL.sh help` script.

## DEPENDENCES
This is a list of pyhon modules of imports done by various plugins:
Non standard modules to be installed with e.g. sudo pip install module
* configparser:	MySense.py
* gspread:	MyGSPREAD.py
* oauth:	MyGSPREAD.py

* mysql:	MyDB.py
Installed with: sudo apt-get install python-dev libmysqlclient-dev build-essential python-dev (needed to do a manual DB access to the MySQL (remote) database.
and sudo python3-mysql.connector python-mysql.connector
If the MySQL database needs to be installed on the Pi as server see e.g. https://www.stewright.me/2014/06/tutorial-install-mysql-server-on-raspberry-pi/

* gps:	MyGPS.py
Install gpsd deamon and client: sudo apt-get install gpsd python-gps
paho.mqtt.client:	MyMQTTPUB.py MyMQTTSUB.py
installed by: git clone https://github.com/eclipse/paho.mqtt.python.git
and `sudo cd paho.mqtt.python; python setup.py install`.
Standard modules installed with Jessie Pi OS:
Check this manually by the command "python"
```
>>> and copy/paste the next lines
import argparse,atexit,calendar,csv,datetime,email
import fcntl,getpass,grp,json,logging,os,pwd,random
import re,requests,serial,signal,smtplib,socket
import subprocess,sys,threading,time,urllib2
<cntrl d>
```

### List of plugins
Here is the list of the plugings and imported python modules:
* argparse:	MySense.py
* atexit:	MySense.py
* calendar:	MyGPS.py
* csv:	MyCSV.py
* datetime:	MyCONSOLE.py, MyCSV.py, MyDB.py, MyEMAIL.py, MyGPS.py, MyGSPREAD.py, MySense.py
* email:	MyEMAIL.py
* fcntl:	MySense.py
* getpass:	MyEMAIL.py
* grp:	MySense.py
* json:	MyBROKER.py, MyMQTTPUB.py, MyMQTTSUB.py
* logging:	MyLogger.py
* os:	MyCSV.py, MyGPS.py, MyGSPREAD.py, MyMQTTSUB.py, MySense.py
* pwd:	MySense.py
* random:	MyInternet.py
* re:	MyDYLOS.py, MyInternet.py, MyMQTTSUB.py, MyRSSI.py, MySense.py
* requests:	MyBROKER.py
* serial:	MyDYLOS.py, MySDS011.py, MyPMS7003.py
* signal:	MySense.py
* smtplib:	MyEMAIL.py
* socket:	MyBROKER.py, MyEMAIL.py, MyInternet.py, MyMQTTPUB.py, MyMQTTSUB.py
* subprocess:	MyDYLOS.py, MyInternet.py, MyRSSI.py, MySense.py, MySDS011.py, MyPMS7003.py
* sys:	MyBROKER.py, MyCONSOLE.py, MyDB.py, MyLogger.py, MyMQTTPUB.py, MyMQTTSUB.py, MySense.py
* threading:	MyGPS.py, MyRSSI.py, MySense.py
* time:	MyCONSOLE.py, MyCSV.py, MyDB.py, MyGPS.py, MyGSPREAD.py, MyInternet.py, MyMQTTPUB.py, MyMQTTSUB.py, MyRSSI.py, MySense.py
* urllib2:	MyInternet.py
