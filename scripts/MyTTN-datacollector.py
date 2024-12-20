#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
# 
# Copyright (C) 2017, Behoud de Parel, Teus Hagen, the Netherlands
# Open Source Initiative  https://opensource.org/licenses/RPL-1.5
#
#   Unless explicitly acquired and licensed from Licensor under another
#   license, the contents of this file are subject to the Reciprocal Public
#   License ("RPL") Version 1.5, or subsequent versions as allowed by the RPL,
#   and You may not copy or use this file in either source code or executable
#   form, except in compliance with the terms and conditions of the RPL.
#
#   All software distributed under the RPL is provided strictly on an "AS
#   IS" basis, WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESS OR IMPLIED, AND
#   LICENSOR HEREBY DISCLAIMS ALL SUCH WARRANTIES, INCLUDING WITHOUT
#   LIMITATION, ANY WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
#   PURPOSE, QUIET ENJOYMENT, OR NON-INFRINGEMENT. See the RPL for specific
#   language governing rights and limitations under the RPL.
__license__ = 'RPL-1.5'

# $Id: MyTTN-datacollector.py,v 5.1 2021/02/07 14:45:05 teus Exp teus $

# Broker between TTN and some  data collectors: luftdaten.info map and MySQL DB
# if nodes info is loaded and DB module enabled export nodes info to DB
# the latter will enable to maintain in DB status of kits and kit location/activity/exports

# module mqtt: git clone https://github.com/eclipse/paho.mqtt.python.git
# cd paho.mqtt.python ; python setup.py install
# broker server: Debian: apt-get install mqtt

""" Download measurements from TTN MQTTT server:
    Subscribe to measurements from a Mosquitto Broker server (eg TTN LoRa server)
    and
    Publish measurements as client to luftdaten.info and MySQL database
    Monitor traffic and output channels.
    One may need to change payload and TTN record format!
    MySense meta measurement kits data is read from MySQL database table Sensors.
    Output channel activation per kit is read from MySQL table TTNtable:
    active, luftdaten, luftdatenID.
    The script is designed to run autonomisly and send notices on discovered events.
    The script can run in different modi: data forwarder, monitoring forwarding,
    measurement kit info load into air quality DB, or with different combinations.
    The configuration is read from a json formatted initialisation file.

    Configuration:
    Script can be used to read meta kit information from json file and export
    it to MySql Sensors and TTNtable.
    Output channels defined: database, monitor, luftdaten, ...
    Input channels defined: TTN MQTT server.
    The Conf dict will define different configurable elements and
    every Conf setting can be changed from the command line.
    Command line arguments (only a few examples):
    file=nameMQTT_JSONfile.json this file will be used as input iso TTN MQTT server
    DevAddr=ttn_address only this topic subscription (default +)

    Events:
    The program will handle events and play as watchdog on kit activity.
    A measurement kit which is not seen for a long period is notified.
    A measurement kit which is too active is throttled. Notices are sent in this case.
    Notices are sent via email and Slack notices per kit, and group of kits.
    If the measurement kit generates out of band values (e.g. RH or temp is
    not changed for a long period) a notice will be sent.

    Updates:
    Every 3 hours the data collector will check data base meta entry
    for changed like other output channel activations.
    On DB kit meta info changes of measurement kit location this change will
    be updated in the meta data (Sensors DB table).

    LoRa decoding:
    LoRa decode is done via json decoding at MQTT level as well on subscribe
    level per port type.
    Sensor data decoding is done per sensor type.

    Configuration from CLI level:
    Various output channels can be reconfigured as eg:
    luftdaten:output=true (default) luftdaten:debug=true (dflt false)
    luftdaten:projects=(SAN|HadM|RIVM|KIP) (default forwarding data for these projects)
    monitor:output=false (default)
    monitor:projects=(test|SAN) (dflt: '([A-Za-z]+)')
    monitor:serials=(A-Fa-f0-9]+) (default) only output project_serial for this channel
    console:output=false (default)
    console:projects=([A-Za-z]+) (default)
    console:serials=(A-Fa-f0-9]+) (default)
    database:output=true (default)
    database:debug=false (default)
    notices:output=true (default)
    logger:print=true (default) print in colored format
    file=RestoredDataFile only restoire data from this dump file
    debug=true (default false) switch debugging on
    Or database acces credential settings: host=xyz, user=name, password=acacadabra
    Or use command CLI environment settings: DBHOST, DBUSER, DBPASS, or DB
    See Conf dict declaration for more details.
"""
modulename='$RCSfile: MyTTN-datacollector.py,v $'[10:-4]
__version__ = "0." + "$Revision: 5.1 $"[11:-2]

try:
    import MyLogger
    import dateutil.parser as dp
    import datetime
    import sys, os
    import signal
    import json
    from jsmin import jsmin     # tool to delete comments and compress json
    import socket
    import re
    from time import time, sleep, localtime
    socket.setdefaulttimeout(60)
    import MyTTNclient          # module to receive TTN MQTT data records
    from struct import *        # pack/unpack payloads
    import base64
    import traceback
except ImportError as e:
    sys.exit("One of the import modules not found: %s\n" % str(e))

debug = False   # output only for debugging reasons, no export of data
monitor = None  # output monitoring info via proj/serial pattern, no export of data
notices = None  # send notices of events
ProcessStart = time()  # time of startup

waiting = False          # waiting for telegram to arrive in queue
mid = None               # for logging: message ID
telegrams = []           # telegram buffer, max length is 100     
TelegramCnt = 0          # count of TTN records received so far.
PingTimeout = 0          # last time ping request was sent
Channels = []            # output channels
DB = None                # shortcut to Output channel database dict
ThreadStops = []         # list of stop routines for threads

def PrintException():
    lineno = sys.exc_info()[-1].tb_lineno
    filename = sys.exc_info()[-1].tb_frame.f_code.co_filename
    print('EXCEPTION IN %s, LINE %d' % (filename, lineno))

# cached meta info  and handling info measurement kits
# cache to limit DB access
cached = {
    # 'applID/deviceID': {
    # 'unknown_fields': [] seen but not used fields
    # 'last_seen': unix timestamp secs
    # 'count': received records count, will be reset after new meta info from DB
    # 'gtw': [[],...] LoRa gateway nearby [gwID,rssi,snr,(lat,long,alt)]
    # 'sensors': list of sensor types (same as firmware/sensors) deprecated
    # 'firmware': {sensors,fields,id (classId)}
    # 'port%d': {packing, adjust}
    # 'DB': {
    #    'SensorsID': Sensors table database row id
    #    'TTNtableID': TTNtable table database row id
    #    'kitTable': name of measurements table of a kit
    # },
    # 'ident': {} # collected meta info e.g. from AQ database
    # },
}
ReDoCache  = 3*60*60          # period in time to check for new kits
updateCacheTime = int(time()) # last time update cached check was done
dirtyCache = False            # force a check of cached items to DB info
ShowCached = False            # print cached items in INFO log

# sensor info: type, units etc
dirtySensorCache = False
SensorCache = {}

# configurable options
__options__ = [
        'input',       # list of input channels
        'hostname','port', 'user','password', # MQTT server credentials
        'dust', 'meteo'# classes field names coming from TTN MQTT server
        # to do: should go as conf per device and needs type of sensor
        'packing',     # how it is packed, which sensor types
        'classes',     # map appl/device to class of sensor kit config
        'sensors',     # sensor module types for 'dust', 'meteo' ...
        'timeout',     # timeout for no server active
        'rate',        # expected mininimal secs between telegrams per kit received
        'file',        # data input json records from file iso MQTT server
        'initfile',    # initialisation file with conf. info
        'nodesfile',   # nodes info mfile to be exported to DB
        'check',       # list of sensor fields to check for fluctuation faults
        'monitor',     # pattern for project_serial to monitor for. '.*' (all)
        ]

MQTTdefaults = {
            'address': 'eu.thethings.network', # server host number for mqtt broker
            'port': 1883,        # default MQTT port
            # + is a wild card in TTN
            'topic': '+/devices/+/up',  # main topic: appID/devices/devID/up
            # credentials to access broker
            'user': 'account_name',
            'password': 'ttn-account-v2.acacadabra',
            # MQTT dflt 0 (max 1 telegram), 1 (1 telegram), or 2 (more)
            # 'qos' : 0, # is default
            # TODO: 'cert' : None,       # X.509 encryption
        }

Conf = {
    'input': [],         # a list of input channels eg 'TTN' for TTN MQTT subscription
    'project': 'XYZ',    # default prefix to unique device/serial number
    'TTN': [             # round robin subscription list of MQTT TTN brokers
        MQTTdefaults,    # default broker access details
        ],
    'rate':    10*60,    # expected time(out) between telegrams published
                         # if data arrived < expected rate, throttling
                         # *2 is wait time to try to reconnect with MQTT server
    'check': ['luchtdruk','temp','rv','pm10','pm25'], # sensor fields for fluctuation faults
                         # if measurement values do not fluctuate send notice sensor is broken
    'DEBUG': False,      # debug modus

    # defines nodes, LoRa, firmware, classes, etc. for Configure info
    # this will read from a dump MQTT file, can be defined from command line file=..
    # notices:
    'notice': [['pattern','method:address',],], # send notices to email, slack, ...
    # 'file': 'Dumped.json', # uncomment this for operation from data from file
    'file': None,
    # 'initfile': 'MyTTN-datacollector.conf.json', # meta identy data for sensor kits
    'initfile': None,
    # 'nodes': {},  # DB of sensorkits info deprecated
    # LoRa, nodes, sensors, classes, firmware, and translate
    # 'test': True     # use TTN record example in stead of server access
    # DB dictionary with different sensors: type, producer, sensors/units
    # key calibrations is optional
    # types need to be capitalized
    # group classification is not used yet
    "notice": [
        [".*", "email:<noreply@behouddeparel.nl>", "slack:hooks.slack.com/services/123440" ],
        ["test.*", "email:<noreply@behouddeparel.nl>" ],
        ["lopyproto.*", "slack:hooks.slack.com/services/TGA123451234512345" ],
        ["gtl-ster.*", "slack:hooks.slack.com/services/T9W1234512345eSQ" ],
        ],
    "from": "Notice from TTN data collector <noreply@behouddeparel.nl>",
    "SMTP": "somesmtpservice.org",

    # the sensor products
    # DB dictionary with different sensors: type, producer, sensors/units
    # should go to a json initfile
    # types need to be capitalized
    # group classification is not used yet
    "sensors": [
            {  "type":"unknown",
                "producer":"unknown","group":"dust",
                "fields":["pm1","pm25","pm10"],
                "units":["ug/m3","ug/m3","ug/m3"],
                "calibrations": [[0,1.0],[0,1.0]]},
            {  "type":"SDS011",
                "producer":"Nova","group":"dust",
                "fields":["pm25","pm10"],
                "units":["ug/m3","ug/m3"],
                "calibrations": [[0,1.0],[0,1.0]]},
            # Sensirion standard ug/m3 measurements
            {  "type":"SPS30",
                "producer":"Sensirion","group":"dust",
                "fields":["pm1","pm25","pm10","pm05_cnt","pm1_cnt","pm25_cnt","pm4_cnt","pm10_cnt","grain"],
                "units":["ug/m3","ug/m3","ug/m3","pcs/cm3","pcs/cm3","pcs/cm3","pcs/cm3","pcs/cm3","um"],
                "calibrations": [None,[0,1.0],[0,1.0]]}, # None is [0,1.0]
            # Plantower standard ug/m3 measurements
            {  "type":"PMS7003",
                "producer":"Plantower","group":"dust",
                "fields":["pm1","pm25","pm10"],
                "units":["ug/m3","ug/m3","ug/m3"],
                "calibrations": [None,[0,1.0],[0,1.0]]}, # None is [0,1.0]
            # Plantower the atmosphere ug/m3 measurements
            {  "type":"PMS7003_ATM",
                "producer":"Plantower","group":"dust",
                "fields":["pm1_atm","pm25_atm","pm10_atm"],
                # "calibrations": [[0,1.0],[0,1.0],[0,1.0]],
                "units":["ug/m3","ug/m3","ug/m3"]
                },
            # Plantower the count particulates measurements
            {  "type":"PMS7003_PCS",
                "producer":"Plantower","group":"dust",
                "fields":["pm03_pcs","pm05_pcs","pm1_pcs","pm25_pcs","pm5_pcs","pm10_pcs"],
                "units":["pcs/0.1dm3","pcs/0.1dm3","pcs/0.1dm3","pcs/0.1dm3","pcs/0.1dm3","pcs/0.1dm3"],
                "calibrations": [[0,1.0],[0,1.0],[0,1.0],[0,1.0],[0,1.0],[0,1.0]]},
            {  "type": "PPD42NS",
                "producer":"Shiney","group":"dust",
                "fields":["pm25","pm10"],
                "units":["pcs/0.01qft","pcs/0.01qft"],
                "calibrations": [[0,1.0],[0,1.0]]},
            {  "type": "DC1100PRO",
                "producer":"Dylos","group":"dust",
                "fields":["pm25","pm10"],
                "units":["pcs/0.01qft","pcs/0.01qft"],
                "calibrations": [[0,1.0],[0,1.0]]},
            {  "type": "unknown",
                "producer":"unknown","group":"meteo",
                "fields":["temp","rv"],"units":["C","%"],
                "calibrations": [[0,1.0],[0,1.0]]},
            {  "type": "DHT22",
                "producer":"Adafruit","group":"meteo",
                "fields":["temp","rv"],"units":["C","%"],
                "calibrations": [[0,1.0],[0,1.0]]},
            {  "type": "BME280",
                "producer":"Bosch","group":"meteo",
                "fields":["temp","rv","luchtdruk"],
                "units":["C","%","hPa"],
                "calibrations": [[0,1.0],[0,1.0],[0,1.0]]},
            {  "type": "BME680",
                "producer":"Bosch","group":"meteo",
                "fields":["temp","rv","luchtdruk","gas", "aqi"],
                "units":["C","%","hPa","kOhm","%"],
                "calibrations": [[0,1],[0,1],[0,1],[0,1],[0,1]]},
            {  "type": "TTN NODE",
                "producer":"TTN","group":"LoRa",
                "fields":["battery","light","temp"],
                "units":["mV","lux","C"],
                "calibrations": [[0,1.0],[0,1.0],[0,1.0]]},
            {  "type": "TTN EVENT",
                "producer":"TTN","group":"LoRa",
                "fields":["event"],
                "units": ["id"],"calibrations": [None]},
            {  "type": "NEO-6",
                "producer":"NEO","group":"GPS",
                "fields":["longitude","latitude","altitude","gps"],
                "units": ["degrees","degrees","m","lon,lat,alt"],
                "calibrations": [[0,1],[0,1],[0,1],None]},
            {  "type": "PYCOM",
                "producer": "ESP", "group":"controller",
                "fields":["time"], "units":["sec"],"calibrations":[None]},
            {  "type": "MYSENSE",
                "producer": "BdP", "group": "IoS",
                "fields": ["version","meteo","dust"],
                "units": ["nr","type","type"],
                "calibrations": [None,None,None]},
           { "type": "ENERGY",
                "producer":"unknown", "group":"energy",
                "fields":["accu"], "units": ["V"],"calibrations":[None]},
           { "type": "WASPMOTE",
              "producer": "Libelium", "group": "meteo",
              "fields": ["accu","temperature","humidity","pressure","rain","prevrain","dayrain","winddir","windspeed"],
              "units": ["%","C","%","hPa","mm","mm","mm","degrees","m/sec"],
              "calibrations": [[0,1],[0,1],[0,1],[0,1],[0,1],[0,1],[0,1],[0,1],[0,1]]},
           { "type": "'windDIY1", # non mechanical wind measurement unit
              "producer": "WindSonic", "group": "meteo",
              "fields": ["winddir","windspeed"],
              "units": ["degrees","m/sec"],
              "calibrations": [[0,1],[0,1]]},
            # not yet activated
            { "type":"ToDo",
                "producer":"Spect", "group":"gas",
                "fields":["NO2","CO2","O3","NH3"],
                "units":["ppm","ppm","ppm","ppm"],
                "calibrations": [[0,1.0],[0,1.0],[0,1.0],[0,1.0]]}
    ],
    # if only as payload in packed format
    # To Do: use reg exp, classID gives pointer to payload for a device
    'classes': [
        { 'classID': 'VW2017', 'regexp': 'pmsensor/pmsensor\d+(/\d)?', },
        { "classID": "TTNnode",  "regexp": "201801275971az/2018[0-9a-zA-Z]+/[1-4]"},
        { "classID": "LoPyNode", "regexp": "201802215971az/lopyprototype2018[0-9]{4}"},
        ],
    # To Do: create a handle from application/device to device config
    # AppId eui, Dev eui and fport define the algorithm firmware to be used
    # should be in json admin file To Do: put this in a DB
    # To Do: add packing per length of bytes:
    # [ {'length': nr bytes, "packing": ">HH", "adjust":[[...]], "fields":[]}
    # To Do: check all referrals
    "firmware": [
        {
          "id":      "VW2017",    # size of payload as ident
          "port2": {
              "packing": ">HHHH", # how it is packed, here 4 X unsigned int16/short
              "adjust":  [[0,0.1],[0,0.1],[-20,0.1],[0,0.1]],  # unpack algorithm
              "fields":  ["pm25","pm10","temp","rv"],  # fields
              "sensors": ["SDS011","DHT22"]  # use upper cased names
            }
        },
        {
          "id":      "TTNnode", # size of payload as ident
          "port2": {
              "packing": ">HHH",# how it is packed, here 4 X unsigned int16/short
              "fields":  ["battery","light","temp"], # fields
              "adjust":  [[0,1],[0,1],[0,0.01]],     # unpack algorithm
              "sensors": ["TTN node","TTN node","TTN node"] # use upper cased names
            },
          # ports may be used as just an event iso 1 byte value
          "port3": { "packing": ">B", "fields": ["interval"], "adjust": [[0,1]]  },
          "port4": { "packing": ">B", "fields": ["motion"], "adjust": [[0,1]]  },
          "port5": { "packing": ">B", "fields": ["button"], "adjust": [[0,1]]  }
        },
        {
          "id": "LoPyNode",
          "port2": {
              # To Do: add HHH if gps is added
              # [">HHHHHHHHl",">HHHHHHHHllll"]
              "packing": ">HHHHHHHHl",
              # + "longitude","latitude","altitude"
              "fields": ["pm1","pm25","pm10","temperature","humidity","pressure","gas","aqi","time"],
              # + [0,0.000001],[0,0.000001],[0,0.1]
              "adjust": [[0,0.1],[0,0.1],[0,0.1],[-30,0.1],[0,0.1],[0,1],[0,1],[0,0.1],[0,1]],
              "sensors": ["PMS7003","SDS011","BME680","BME280","NEO-6","PYCOM"]
            },
          "port3": {
               "packing": ">BBlll",
                "fields": ["version","meteo","dust","latitude","longitude","altitude"],
                "adjust": [[0,0.1],[0,1],[0,0.000001],[0,0.00001],[0,0.1]],
                "sensors": ["MYSENSE","GPS"],
                "meteo": ["unknown","PPD42NS","SDS011","PMS7003"],
                "dust": ["unknown","DHT11","DHT22","BME280","BME680"]
          },
          "port4": {
              # needs to be corrected
              "packing": [">HHHHHHHHl",">HHHHHHHHlll",">HHHHHHHHllll"], # [">HHHHHHHHl",">HHHHHHHHllll"]
              # "fields": ["pm1","pm25","pm10","temperature","humidity","pressure","gas","aqi","time"],
              "fields": ["pm1","pm25","pm10","temperature","humidity","pressure","gas","aqi","time","latitude","longitude","altitude"],
              "adjust": [[0,0.1],[0,0.1],[0,0.1],[-30,0.1],[0,0.1],[0,1],[0,1],[0,0.1],[0,1]],
              "sensors": ["PMS7003","SDS011","SPS30","BME680","BME280","NEO-6","PYCOM","ENERGY"]
            },
            # "port10": {
            #   # Libelium Waspmote void,id,void,accu,temp,...
            #   #"packing": ["<B11sB7sBBBBBfBfBfBfBfBfBBBf"],
            #   "packing": ["<B11sB7sBBBBBfBfBfBfBfBfBBBf"], # (id,value),...
            #   # every field has sensor id one byte
            #   "nr2field": {"35": None, "239": "node", "60": None, "52": "accu", "74": "temp", "76": "rv","77":"luchtdruk","158":"rain","159":"prevrain","160":"dayrain","157":"wr","156":"ws"},
            #   "fields": ["accu","temp","rv","luchtdruk","rain","prevrain","dayrain","wr","ws"],
            #   "adjust": [[0,1],[0,1],[0,1],[0,0.01],[0,1],[0,1],[0,1],[0,1],[0,1]],
            #   "sensors": ["WASPMOTE"],
            #   "meteo": ["unknown"]
            # },
            # "port12": {
            #    # DIY weather station: wind dir, wind speed, volt, temp, humidity, air pressure
            #    # 2 bytes devided by 100.0
            #    # this one s just stupid, it needs generalisation eg a la Libelium!
            #    "packing": ["<hhhhhh"],
            #    "fields": ["wr","ws","accu","temp","rv","luchtdruk"],
            #    "adjust": [[0,0.01],[0,0.01],[0,0.01],[0,0.01],[0,0.01],[0,1.0]],
            #    "sensors": ["ANEMO","BME280"],
            #    "meteo": ["BME280"],
            # }
        }
    ],
    # defs of used fields by MySense, do not change the keys
    # To Do: put this in a DB
    "translate": {
        "pm03": ["pm0.3","PM0.3"],
        "pm05": ["pm0.5","PM0.5"],
        "pm1":  ["roet","soot"],
        "pm25": ["pm2.5","PM2.5"],
        "pm4":  ["pm4.0","PM4.0"],
        "pm5":  ["pm5.0","PM5.0"],
        "pm10": ["pm","PM"],
        "O3":   ["ozon"],
        "NH3":  ["ammoniak","ammonium"],
        "NO2":  ["stikstof","stikstofdioxide","nitrogendioxide"],
        "NO":   ["stikstof","stikstofoxide","nitrogenoxide"],
        "CO2":  ["koolstofdioxide","carbondioxide"],
        "CO":   ["koolstofmonoxide","carbonoxide"],
        "temp": ["temperature"],
        "luchtdruk": ["pressure","pres","pha","pHa"],
        "rv":   ["humidity","hum","vochtigheid","vocht"],
        "ws":   ["windspeed","windsnelheid"],
        "wr":   ["windrichting","winddirection","direction"],
        "altitude":  ["alt","hoogte","height"],
        "longitude":  ["long","lon","lengte graad"],
        "latitude":  ["lat","breedte graad"],
        "gps": ["GPS","coordinates","geo","geolocation"],
        "gas":  ["air"],
        "aqi":  ["air quality","luchtkwaliteit","lki"],
        "version": ["versie","release"],
        "meteo": ["weer"],
        "dust": ["fijnstof"],
        "grain": ["korrel"],
        "accu": ["accu","battery"],
        "rain": ["regen","rain"],
        "dayrain": ["dayrain"],
        "prevrain": ["prevrain"],
        "event": ["alarm"], "value": ["waarde"],
        "time": ["utime","timestamp"]
    },
}

# stop running input and output channel threads and exit
def EXIT(status):
  global ThreadStops, modulename
  if 'TTN' in Conf['input'] and len(Conf['TTN']):
     try: MyTTNclient.MQTTstop(Conf['TTN'])
     except: pass
  for stop in ThreadStops:
    try: stop()
    except: pass
  sleep(1)
  sys.exit("%s of %s" % (('FATAL: exit' if status else 'Exit'), modulename) )

# rename names into known field names
# prepend with field_ if not known
def translate( sense, ext=True ):
    sense.replace('PM','pm')
    sense.replace('_pcs','_cnt')
    for strg in ('O3','NH','NO','CO'):
        sense.replace(strg.lower(),strg)
    if not 'translate' in Conf.keys():
        if not ext: return sense
        return 'field_' + sense
    for strg in Conf['translate'].keys():
        if sense.lower() == strg.lower(): return strg
        if (strg[:2] == 'pm') and (strg == sense[:-4]): return sense.lower()
        for item in Conf['translate'][strg]:
            if item == sense: return strg
    if not ext: return sense
    return 'field_' + sense

# import notice addresses if available and changed
def importNotices():
    global Conf
    if (not 'noticefile' in Conf.keys()) or not os.path.isfile(Conf['noticefile']): return True
    if not 'gmtime' in importNotices.__dict__: importNotices.gmtime = 0
    try:
        if int(os.path.getmtime(Conf['noticefile'])) > importNotices.gmtime:
            importNotices.gmtime = int(os.path.getmtime(Conf['noticefile']))
        with open(Conf['noticefile']) as _typeOfJSON:
            new = jsmin(_typeOfJSON.read())
        new = json.loads(new)
        if (type(new) is dict) and ('notice' in new.keys()): new = new['notice']
        if not type(new) is list:
            raise ValueError('Notices in not a list of notices: expression, notes ...')
        if not 'notice' in Conf.keys(): Conf['notice'] = []
        for one in new:
            for i in range(len(Conf['notice'])):
                if one[0] == Conf['notice'][i][0]: Conf['notice'][i] = one
                else: Conf['notice'].append(one)
        MyLogger.log(modulename,'ATTENT','Imported notice addresses from file %s' % Conf['noticefile'])
        return True
    except Exception as e:
        MyLogger.log(modulename,'ERROR','Failed to load notice addresses. Error: e' % str(e))
        return False

# monitor output channel
def monitorPrt(test, color=0): # default color is black
    global monitor
    if not monitor: return
    try:
        if not monitor['output']: return
        monitor['output'].MyPrint(test, color=color)
        return
    except: pass
    try: sys.stdout(test+'\n')
    except: pass

# delete cache entries in DB tables Sensors/TTNtable, which DB entry has been updated
def UpdateCache():
    global cached, dirtyCache, updateCacheTime, ReDoCache
    global DB
    if (not dirtyCache) and (int(time()) < updateCacheTime+ReDoCache): return
    updateCacheTime = int(time())+ReDoCache
    dirtyCache = False
    if not len(cached) or not DB: return
    # get topics for which kits (Sensors) meta data has been changed meanwhile
    # get TTN_id's for which Sensor meta info is changed after updateCacheTime
    topics = DB.UpdatedIDs(updateCacheTime,field='TTN_id', table='TTNtable')
    if len(topics):
        MyLogger.log(modulename,'DEBUG','Kit meta info to be updated in cache: %s' % ', '.join(topics))
    else:
        return
    for one in cached.keys():
        indx = 0
        try: indx = '/'.index(one)+1
        except: pass
        if one[indx:] in topics:
            MyLogger.log(modulename,'ATTENT','Kit with topic %s to be updated in cache' % one)
            monitorPrt("Cached kit with topics %s to be updated." % one[indx:], 4)
            del cached[one]

# json file with predefined nodes administration details
# prefer to export nodes info via MyDB.py in standalone mode
def ExportNodes(name):
    global Conf, dirtyCache
    global Channels, DB
    if not name: return True
    fnd = False
    # json file may have comments in this case
    if type(name) is dict:
        new = name
    else:
        from jsmin import jsmin     # tool to delete comments and compress json
        try:
            with open(name) as _typeOfJSON:
                new = jsmin(_typeOfJSON.read())
            new = json.loads(new)
        except IOError:
            MyLogger.log(modulename,'WARNING', 'No file %s found' % name)
            return False
        except ValueError as e:
            MyLogger.log(modulename,'ERROR',"Json error in nodes file %s: %s" % (name,e))
            return False
    Nok = []
    for item in new.keys():
        if not type(new[item]) is dict:
            Nok.append('node %s type error. Skipped.' % item)
        else:
            canAdd = True
            for chck in ['project','GPS','label','serial','date','active']:
                if not chck in new[item].keys():
                    Nok.append('node %s: missing %s' % (item,chck))
                    canAdd = False
                if (chck == 'GPS') and (not type(new[item][chck]) is dict):
                    Nok.append('node %s: %s not dict with ordinates.' % (item,chck))
                    canAdd = False
            if canAdd:
                dirtyCache = True
                try:
                    if not DB.putNodeInfo(item):
                        Nok.append("Unable to export node info for: %s" % str(item))
                except Exception as e:
                    MyLogger(modulename,'WARNING',str(e))
    if len(Nok):
        MyLogger(modulename,'WARNING','Node %s in admin file %s error(s): %s' % (item,name,Nok.join(', ')))
        return False
    return True

def PrintMQTTlog(message): # convert log error messages into logging
    MyLogger.log('MQTT broker',message[:message.find(' ')],message[message.find(' ')+1:])

def Initialize():
    global Conf, dirtyCache, dirtySensorCache, notices, MQTTdefaults
    if (not 'initfile' in Conf.keys()) or not Conf['initfile']:
        MyLogger.log(modulename,'WARNING',"No initialisation file defined, use internal definitions.")
    else:
        MyLogger.log(modulename,'INFO',"Using initialisation file %s." % Conf['initfile'])
    new = {}
    if ('initfile' in Conf.keys()) and Conf['initfile']:
        # initialisation is read from json file
        try:
            # json file may have comments in this case
            from jsmin import jsmin     # tool to delete comments and compress json
            with open(Conf['initfile']) as _typeOfJSON:
                new = jsmin(_typeOfJSON.read())
            new = json.loads(new)
        except ValueError as e:
            MyLogger.log(modulename,'ERROR',"Json error in init file %s: %s" % (Conf['initfile'],e))
            MyLogger.log(modulename,'ATTENT','Missing or errors in LoRa init json file with info for all LaRa nodes. Exiting.')
            return False
            # example of content of admin node info file specified for TTN MQTT RIVM records
            # fields may be optional. Will be exported to Sensors and TTNtable in DB
            # Conf['nodes'] = {
            #     'pmsensorN': {           # Device id TTN
            #         'GPS': {
            #             'longitude': 51.12345, 'latitude': 6.12345, 'altitude': 23, },
            #         'label': 'Jelle', 'street': 'Fontys nr 8',
            #         'village': 'Venlo', 'pcode': '5888 XY',
            #         'province': 'Limburg', 'municipality': 'Venlo',
            #         'date': '20-12-2017', # start date
            #         'comment': 'test device',
            #         # 'serial': None, if not defined use hash topic/device name
            #         "serial": "30aea4008438", # PyCom unique ID
            #         'AppSKEY': 'xyz',         # LoRa key from eg RIVM
            #         'NwkSKey': 'acacadabra',  # LoRa key from eg RIVM
            #         # To Do: add calibration details
            #         'meteo': 'BME280',   # meteo sensor type
            #         'dust': 'SDS011',    # dust sensor type
            #         'gps': 'NEO-6',      # GPS sensor
            #         'luftdaten': False,  # forward to Open Data Germany?
            #         'active': False,
            #     }
            # }
        dirtySensorCache = True
        # nodes info are exported to Database tables Sensors and TTNtable
        for item in ['project','sensors','firmware','classes','translate','notice','from','SMTP','adminDB','nodes','initfile','noticefile','TTN']:
            if item in new.keys():
                Conf[item] = new[item]
                MyLogger.log(modulename,'ATTENT','Overwriting dflt definitions for Conf[%s].' % item)
    # collect type of input channels, here file TTN dump or list of TTN MQTT apps
    if 'file' in Conf.keys() and Conf['file']: Conf['input'] = ['file']
    for broker in ['TTN']:
      if not broker in Conf.keys(): # no input TTN broker(s) defined
        continue
      if 'file' in Conf['input']: # do only data from backup TTN file
        continue
      Conf['input'].append(broker) # add brokers type to input channels
      if not type(Conf[broker]) is list: Conf[broker] = [Conf[broker]]
      for item in Conf[broker]:
        if not type(item) is dict:
          MyLogger.log(modulename,'ERROR',"broker(s) misconfiguration: %s" % str(item))
          continue
        # setting defaults for MQTT broker
        for one in MQTTdefaults.keys():
          if not one in item.keys(): item[one] = MQTTdefaults[one]
      if not len(Conf[broker]):
        MyLogger.log(modulename,'FATAL','No broker defined. Exiting.')
    if 'nodesfile' in Conf.keys():
        if (not ExportNodes(Conf['nodesfile'])): return False
        del Conf['nodesfile']
    importNotices() # enable automatic import of notice addresses if noticefile is defined
    if not notices: Conf['notice'][0] = [] # notices turned off in eg test phase
    if 'nodes' in Conf.keys(): # deprecated
        if (not ExportNodes(Conf['nodes'])): return False
        del Conf['nodes']
    return True

# reread admin meta info of nodes in, may de/activate data arcghiving of the node
def SigUSR2handler(signum,frame):
    global dirtyCache
    try:
      dirtyCache = True
    except: pass
    return

# see if we know this product
unkownProducts = []
def ProductKnown( product ):
    global Conf
    if not 'sensors' in Conf.keys():
        MyLogger.log(modulename,'FATAL','Missing sensors key in Conf dictionary.')
        EXIT(1)
    if product in unkownProducts: return None
    for sense in Conf['sensors']:
        if sense['type'] == product:
            return sense
    if not product in unkownProducts:
        MyLogger.log(modulename,'ATTENT',"Unknown sensor product %s" % product)
        unkownProducts.append(product) 
    return None
        
# calibrate as ordered function order defined by length calibration factor array
def calibrate(coeffs,value):
    if not type(coeffs) is list: return value
    if type(value) is int: value = value/1.0
    if not type(value) is float: return value
    rts = 0; pow = 0
    for a in coeffs:
        rts += a*(value**pow)
        pow += 1
    return round(rts,2)

# search name of pollutant in fields and try to calibrate the value
def tryCalibrate(field,value,fields,calibrations):
    if (not type(fields) is list) or (not type(calibrations) is list):
        return value
    if field in ['latitude','longitude']: return round(value,6)
    try:
        # only first field with the name is expected
        if fields.count(field) > 0:
            idx = fields.index(field)
            if idx < len(calibrations):
                value = calibrate(calibrations[idx],value)
    except:
        pass
    return value

# returns distance in meters between two GPS coodinates
# hypothetical sphere radius 6372795 meter
# courtesy of TinyGPS and Maarten Lamers
# should return 208 meter 5 decimals is diff of 11 meter
# GPSdistance((51.419563,6.14741),(51.420473,6.144795))
LAT = 0
LON = 1
ALT = 2
def GPSdistance(gps1,gps2):
  from math import sin, cos, radians, pow, sqrt, atan2
  delta = radians(float(gps1[LON])-float(gps2[LON]))
  sdlon = sin(delta)
  cdlon = cos(delta)
  lat = radians(float(gps1[LAT]))
  slat1 = sin(lat); clat1 = cos(lat)
  lat = radians(float(gps2[LAT]))
  slat2 = sin(lat); clat2 = cos(lat)

  delta = pow((clat1 * slat2) - (slat1 * clat2 * cdlon),2)
  delta += pow(clat2 * sdlon,2)
  delta = sqrt(delta)
  denom = (slat1 * slat2) + (clat1 * clat2 * cdlon)
  return int(round(6372795 * atan2(delta, denom)))

# try to guess the sensor types and fields from the values present in the record
# returns dict with record data and 'sensors' + 'fields'
def checkFields(record):
    global Conf
    def recordTranslate(arecord):
        new = {}
        for item in arecord.items():
            if item[1] == None: continue
            transltd = translate(item[0],ext=False)
            if item[1] or (transltd in ['temp','wr','ws']):
                new[transltd] = item[1]
        return new

    def getTypes(sFlds,fld):
        for grp in sFlds.keys():
            if fld in sFlds[grp].keys(): return sFlds[grp][fld]
        return []

    # collect SenseFlds[groups][translated fields] per group fields
    new_record = recordTranslate(record)
    SenseFlds = {}
    for sensor in Conf['sensors']:
        if (not 'fields' in sensor.keys()) or (not 'group' in sensor.keys()):
            continue
        group = sensor['group']; omits = []
        for one in new_record.keys():
            if one in sensor['fields']:
               if not sensor['group'] in SenseFlds.keys(): SenseFlds[group] = {}
               if not one in SenseFlds[group].keys(): SenseFlds[group][one] = []
               if not sensor['type'] in SenseFlds[group][one]:
                   SenseFlds[group][one].append(sensor['type'])
    # we have a table with groups, and fields/values present, collect the sensor types
    data = { 'sensors':[], 'fields':[]}
    for item in new_record.items():
        if item[1] == None: continue
        if item[0] in ['sensors','fields','units']: continue
        data[item[0]] = item[1]
        data['fields'] = list(set(data['fields']+[item[0]]))
        sense = getTypes(SenseFlds,item[0])
        data['sensors'] = list(set(data['sensors']+list(sense)))
        # to do add units
    for item in new_record.items(): # overwrite 
        if not item[0] in ['sensors','fields','units']: continue
        data[item[0]] = item[1].split(',')
    return data

# for internal MySense data record assembly style
# extra fields: sensor product type, sensor types and units
# arguments: LoRa payload in base64, LoRa port nr or rule ID (string),
#            omit keys from data records, default measement value unit, add time stamp?
Coding = None
def MyDecode(payload,portNr, timestamp=None, omit=[], dfltunit='dflt'):
    global Coding
    if not Coding:
        import MyLoRaCode
        Coding = MyLoRaCode.LoRaCoding()  # use default port 10 and 12 decoding rules
    sensors = []; rslt = {}; fields = {}
    for( key, item) in Coding.Decode(payload,portNr,timestamp).items():
        if key in omit: continue
        if type(item) is dict:
            sensors.append(key)
            for (key,item) in item.items():
              if type(item) is list: continue
              if type(item) is dict:
                for (key,item) in item.items():
                  try:
                   rslt[key] = item[0]
                   fields[key] = 'dflt'
                   if len(item) > 1: fields[key] = item[1]
                  except: rslt[key] = item
              elif type(item) is tuple:
                  try:
                   rslt[key] = item[0]
                   fields[key] = dfltunit
                   if len(item) > 1: fields[key] = item[1]
                  except: rslt[key] = item
              else:
                  rslt[key] =  item
                  fields[key] = dfltunit
    if fields:
        flds = []; units = []
        for (key,item) in fields.items():
          if item:
            flds.append(key); units.append(item)
        if flds:
            rslt['fields'] = ','.join(flds)
            rslt['units'] = ','.join(units)
    if sensors: rslt['sensors'] = ','.join(sensors)
    return(rslt)

# unpack base64 TTN LoRa payload string into array of values NOT TESTED
# architecture is changed!, To Do: unpack on length of received bytes!
def payload2fields(payload, firmware, portNr, myID):
    global cached, Conf
    packing = None; port = 'port%d' % portNr
    load = base64.decodestring(payload)
    import struct
    declared = []; fnd = False; defined = []
    try:
        loadID = firmware['id']
        packing = firmware['packing']
        if (type(packing) is list) or (type(packing) is tuple):
            for pack in packing:
                save = load
                try:
                    load = list(struct.unpack(pack,load)); fnd = True
                    break
                except: load = save
        else:
          load = list(struct.unpack(packing,load)); fnd = True
    except: pass
    if (not fnd) and (not portNr in [10,12]):
        MyLogger.log(modulename,'ERROR','Cannot find payload converter definition for id %s. TTN topic %s, port %s' % (firmware['id'],myID,portNr))
        return {}
    rts = {}
    if (firmware['id'] == 'LoPyNode') and (not portNr in [10,12]): declared += ['GPS','PYCOM']
    try:
        # next is deprecated
        # # I do not like special cases
        # if (firmware['id'] == 'LoPyNode') and (portNr in [10]): # Libelium case
        #     if 'nr2field' in firmware.keys():
        #         new = [None]*len(firmware['fields'])
        #         for i in range(0,len(load),2):
        #             fldnr = '%d'%load[i]
        #             if fldnr in firmware['nr2field'].keys():
        #                 if firmware['nr2field'][fldnr]:
        #                   try:
        #                     new[firmware['fields'].index(firmware['nr2field'][fldnr])] = load[i+1]
        #                   except: pass
        #         if 'sensors' in firmware.keys(): defined = list(set(firmware['sensors']))
        #         load = new
        #     else: raise ValueError("incomplete json def")
        # elif (firmware['id'] == 'LoPyNode') and (portNr in [12]): # DIY weather station
        #     if 'fields' in firmware.keys():
        #         if 'sensors' in firmware.keys(): defined = list(set(firmware['sensors']))
        #     else: raise ValueError("incomplete json def")
        #     if len(load) != len(firmware['fields']): raise ValueError("incomplete json fields def")
        if (firmware['id'] == 'LoPyNode') and (portNr in [10,12]):
            rts = MyDecode(payload,portNr,omit=['ProdID'],timestamp=None)
            if 'sensors' in rts.keys(): declared = rts['sensors']
            load = None; declared = []
        elif (firmware['id'] == 'LoPyNode') and (portNr == 3):
            rts['sensors'] = []
            if (load[1] & 017) > 0:
                rts['sensors'] = list(set(rts['sensors']+[firmware['dust'][(load[1] & 017)]]))
                declared = list(set(declared+[rts['sensors'][-1]]))
            if ((load[1]>>4) & 07) > 0:
                rts['sensors'] = list(set(rts['sensors']+[firmware['meteo'][((load[1]>>4) & 017)]]))
                declared = list(set(declared+[rts['sensors'][-1]]))
            if (((load[1]>>4) & 010) > 0) and (not 'GPS' in rts['sensors']):
                rts['sensors'] = list(set(rts['sensors']+['GPS']))
                declared = list(set(declared+[rts['sensors'][-1]]))
            load.insert(2,None); load.insert(3,None)
        else:
            rts['sensors'] = firmware['sensors']
        if load:
          for idx in range(len(load)):
            if firmware['adjust'][idx] != None:
                rts[firmware['fields'][idx]] = calibrate(firmware['adjust'][idx],load[idx])
        # try to improve guess for sensor type via existing field value
        rts = checkFields(rts) # check code for units!
        if declared:
            rts['sensors'] = list(set(rts['sensors'] + declared))
            for sensor in Conf['sensors']:
                if (sensor['type'] in declared) or (sensor['type'].lower() in declared):
                    rts['fields'] = list(set(rts['fields']+sensor['fields']))
        if defined: rts['sensors'] = defined
        rts['sensors'].sort()
        # to be done: add units per field!
        rts['fields'].sort() # need to sort units as well!
    except:
        MyLogger.log(modulename,'ERROR','Unpacking LoRa MQTT payload. Record from %s port %s skipped.' % (myID,portNr))
        raise ValueError
        return{}
    return rts
        
# (Pdb) p Info.keys()
# ['info','geolocation','description','fields','DB','units','output','calibrations','types']
# (Pdb) p Info['info'].keys()
# ['province','description','municipality','datum','coordinates','label','project','street','village','active','sensors','last_check','id','comment','serial','first']
# (Pdb) p ident['output'].keys()
# ['AppEui','AppSKEY','datum','id','project','active','DevEui','TTN_id','serial','luftdaten','luftdatenID'}
# 
# (Pdb) p ident.keys()
# ['province','geolocation','description','luftdaten','municipality','street','village','active','sensors','serial','types','fields','label','project','pcode','units','calibrations']
# 

# update ident record with info from json admin file
def getIdent(info,Cached):
    global Channels
    ident =  { }
    for item in ['project','serial','active','count']:
        if item in Cached.keys(): ident[item] = Cached[item]
    if 'info' in info.keys(): ident.update(info['info'])
    for item in ['coordinates','geolocation','description','fields','types','units','calibrations']:
        if not item in info.keys(): continue
        try:
            if info[item] != ident[item]: ident[item] = info[item]
        except:  ident[item] = info[item]
    # to be improved
    try:
        ident['geolocation'] = ident['coordinates']
        del ident['coordinates']
    except: pass
    if not 'exports' in Cached.keys():
        Cached['exports'] = {}
        for one in Channels: Cached['exports'][one['name']] = None
    try:
        Cached['exports']['luftdaten'] = (True if info['output']['luftdaten'] else False)
    except: pass
    try:
        ident['luftdaten'] = Cached['exports']['luftdaten']
    except: pass
    # except: Cached['exports']['luftdaten'] = None
    try: Cached['exports']['luftdatenID'] = info['output']['luftdatenID']
    except: pass
    try: ident['luftdatenID'] = Cached['exports']['luftdatenID']
    except: pass
    # next: ident/active: activated, ident/activeDB: export to DB
    try: Cached['exports']['database'] = info['output']['active']
    except: pass
    try: ident['active'] =  Cached['exports']['database']
    except: pass
    
    return ident

# =======================================================
# post json data to a MQTT broker for nodes somewhere internet land
# =======================================================
# use telegram style

# use input file as MQTT records, used merely as restore data
def ReadFromFile(filename):
    global Conf
    if not 'fileFD' in Conf.keys():
      try:
        Conf['fileFD'] = open(Conf['file'],'r')
        Conf['registrated'] = True
      except:
        MyLogger.log(modulename,'FATAL',"unable to open json input file %s" % Conf['file'])
        EXIT(1)
    while(1):
      line = Conf['fileFD'].readline()
      if (not line) or (not len(line)): # EOF
        Conf['fileFD'].close()
        return None
      line = line.strip()
      if not len(line): continue
      indx = line.find('{')
      if indx < 0: continue
      if line.find('/up {') >= 0: line = line[line.find('/up {')+4:]
      try:
        return(json.loads(line))
      except:
        MyLogger.log(modulename,'WARNING',"Input line from file is not json: '%s'" % line)
        pass

last_records = {}       # remember last record seen so far

# sensor module name is received via TTN record field 'type'
# maintain some logging
# kits alive from previous TTN connection
previous = []

# show current status of nodes seen so far
def SigUSR1handler(signum,frame):
    PrtCached()

def PrtDict(one,spacing):
    if type(one) is dict:
        rts = ' {\n'
        for item in one.keys():
            rts += spacing + "  \"%s\": " % item
            rts += PrtDict(one[item],spacing+'  ')
        return rts + spacing + ' },\n'
    else: return str(one) + ',\n'

def PrtCached(item=None):
    global modulename, cached, ShowCached
    try:
      if item:
        if item in cached.keys():
          MyLogger.log(modulename,'INFO',"Cached[%s] status:\n\t%s\n" % (item, PrtDict(cached[item],'  ')) )
        return
      ShowCached = False
      for name in cached.keys():
        PrtCached(name)
    except: pass

# search record for gateway with best [value,min,max] rssi & snr, ID and ordinates
WRSSI = 0.2
WSNR = 10
def Get_Gtw(msg):
    global WRSSI, WSNR
    if (not 'gateways' in msg.keys()) or (not type(msg['gateways']) is list):
        return []
    signal = -1000 ; gtw = []
    for one in msg['gateways']: # get weighted best gateway signal
        gwSet = set(['timestamp','gtw_id','rssi','snr'])
        if len(set(one.keys()) & gwSet) != len(gwSet): continue
        if WSNR*one['snr']+WRSSI*one['rssi'] <= signal: continue
        else: signal = WSNR*one['snr']+WRSSI*one['rssi']
        location = []
        for crd in ['latitude','longitude','altitude']:
            try: location.append(one[crd])
            except: location.append(None)
        gtw = [one['gtw_id'], location, [one['rssi'],one['rssi'],one['rssi']],[one['snr'],one['snr'],one['snr']]]
    return gtw

# Sensor description cache
# to do: add memory use watchdog
def SensorInfo( sensors ):
    global SensorCache, dirtySensorCache, Conf
    sensors.sort()
    theKey = '/'.join(sensors)
    if dirtySensorCache:
        SensorCache = {} ; dirtySensorCache = False
    if theKey in SensorCache.keys(): return SensorCache[theKey].copy()
    ident = {
        # this is just a guess indicated by DFLTs flag!
        'description': ';hw: %s,TIME,DFLTs' % ','.join(sensors),
        'fields': ['time', ], 'types': ['time'], 'units': ['s',], 'calibrations': [None,],
        }
    for sensor in sensors:
        product  = ProductKnown(sensor)
        for j in range(len(product['fields'])):
            ident['types'].append(sensor.lower())
            for t in ['fields','units','calibrations']:
                try:
                    ident[t].append(product[t][j])
                except:
                    ident[t].append(None)
    SensorCache[theKey] = ident
    return ident.copy()
    
# get from appID/deviceID of TTN topic via classID firmware sensors config
def getFirmware( app, device, port):
    global Conf
    if (not 'classes' in Conf.keys()) or (not 'firmware' in Conf.keys()):
        MyLogger.log(modulename,'FATAL','Missing classes or firmware in Conf.')
        return {'sensors':[]}
    ID = None
    for item in Conf['classes']:
        if type(item['regexp']) is unicode:
            item['regexp'] = str(item['regexp'])
        if (type(item['regexp']) is str) or (type(item['regexp']) is unicode):
            item['regexp'] = re.compile(item['regexp'], re.I)
        if item['regexp'].match(app+'/'+device+'/'+ '%d' % port):
            ID = item['classID'] ; break
    if not ID: return {'sensors':[]}
    portNr = 'port%d' % port
    for item in Conf['firmware']:
        if (item['id'] == ID) and (portNr in item.keys()):
            rts = { "id": ID }
            for k in item[portNr].keys(): rts[k] = item[portNr][k]
            return rts
    return {'sensors':[]}

def delDecrFld(ident,fld):
    if (not 'description' in ident.keys()) or (not ident['description']):
        return
    descr = ident['description'].split(';')
    ident['description'] = []
    for item in descr:
        if item.find(fld) < 0: ident['description'].append(item)
    ident['description'] = ';'.join(ident['description'])

def addInfo(module,ident,clear=False):
    try: 
        if clear:
            for t in ['types','fields','units','calibrations']:
                ident[t] = []
            ident['sensors'] = ''
            delDecrFld(ident,'hw:')
            return True
        sensor = None
        for t in Conf['sensors']:
            if t['type'] == module:
                sensor = t; break
        if not sensor: raise ValueError("Unknown module type %s" % module)
        ident['sensors'] += ',' if len(ident['sensors']) else ''
        ident['sensors'] += module
        for t in ['types','fields','units','calibrations']:
            for i in range(len(sensor['fields'])):
                if t == 'types': ident[t].append(module.lower())
                else:
                    if (type(sensor[t]) is list) and (i < len(sensor[t])):
                        ident[t].append(sensor[t][i])
                    else: ident[t].append(None)
    except Exception as e:
        MyLogger.log(modulename,'WARNING',"addInfo error %s: on module %s, key %s, index %d" % (e,module,t,i))
        return False
    return True

# delete double addresses
def UniqAddress( to ):
    def email(address):
        try: return address[address.index('<')+1:address.index('>')].strip()
        except: return address.strip()

    Rslt = []; cleaned = []
    for one in to:
        addr = email(one)
        if not addr in cleaned:
            Rslt.append(one.strip()); cleaned.append(addr)
    return Rslt

def email_message(message, you):
    global Conf, debug
    if not 'from' in Conf.keys(): return True
    if not 'SMTP' in Conf.keys(): return True
    # Import smtplib for the actual sending function
    import smtplib
    # Import the email modules we'll need
    from email.mime.text import MIMEText

    # the text contains only ASCII characters.
    msg = MIMEText("Notice from TTN collector\n" + message)
    
    # me == the sender's email address
    # you == the recipient's email address
    if not type(you) is list: you = you.split(',')
    you = UniqAddress(you)
    msg['Subject'] = 'MySense: TTN data collector service notice'
    msg['From'] = Conf['from']
    msg['To'] = ','.join(you)
    if debug:
        sys.stderr.write("Email, not sent, via %s: %s\n" % (Conf['SMTP'],str(msg)))
        return True
    
    # Send the message via our own SMTP server, but don't include the
    # envelope header.
    try:
        s = smtplib.SMTP(Conf['SMTP'])
        s.sendmail(Conf['from'], you, msg.as_string())
        s.quit()
    except Exception as e:
        MyLogger.log(modulename,'ERROR',"Email notice failure: %s" % str(e))
        if debug: sys.stderr.write("Email notice failure with: %s\n" % str(msg)) # comment this out
        return False
    return True

def slack_message(message, slackURL):
    global debug
    rts = True
    if not type(slackURL) is list: slackURL = slackURL.split(',')
    for one in slackURL:
      one = 'https://' + one.strip()
      if debug:
        MyLogger.log(modulename,'DEBUG','Notice via curl/Slack sent to %s (not sent) via curl): %s' % (one, message))
        continue
      lines = []
      curl = [  #'/bin/echo',
        '/usr/bin/curl',
        '-X', 'POST',
        '-H', 'Content-type: application/json',
        '--data', '{"text": "_MySense_ TTN collector service *notice*!\n%s"}' % message,
        '--silent', '--show-error',
        one
        ]
      try:
        import subprocess
        p = subprocess.Popen(curl, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in p.stdout.readlines(): lines.append(line)
        if len(lines) and line[0] == 'ok': lines.pop(0)
      except Exception as e:
        MyLogger.log(modulename,'ERROR',"Slack notice failure: %s" % str(e))
        # print("Slack notice failure with: %s" % str(curl)) # comment this out
        rts = False
        continue
      p.wait()
    return rts

# obtain notice address for a kit
def kitInfo(myID,fields=[]):
    global cached, DB
    if not len(fields): return {}
    try:
        id = DB.getNodeFields(cached[myID]['DB']['SensorsID'],fields,'Sensors')
        if not id: raise ValueError
        if type(id) is dict: return id
        return {fields[0]: id[0]}
    except: return {}

# distribute notices for an event
def sendNotice(message,myID=None):
    global Conf, cached, debug, monitor, notices
    try:
        if not len(Conf['notice'][0]): return True
    except: return True
    if not notices: return True
    try:
        if not notices['output']: return
    except: pass
    nodeNotice = []; info = []
    if myID:
        try:
            kitID = {}
            kitID = kitInfo(myID,['notice','project','serial','street','village'])
            for item in ['notice','project','serial','street','village']:
                if not item in kitID.keys(): continue
                if (item == 'notice') and kitID['notice']:
                    nodeNotice = [[myID.split('/')[1]] + kitID['notice'].split(',')]
                else: info.append('%s: %s' % (item,KitID[info]))
        except: pass
    sendTo = { 'email': [], 'slack': [] }; info = ', '.join(info)
    for item in Conf['notice']+nodeNotice:
        try:
            if not (re.compile(item[0],re.I)).match(myID.split('/')[1]): continue
            for to in item[1:]:
                to = to.strip()
                one = to.split(':')
                if not one[0] in sendTo.keys(): continue
                try:
                    if not one[1].strip() in sendTo[one[0]]:
                        sendTo[one[0]].append(one[1].strip())
                except: continue
        except: continue
    if debug:
        sys.stderr.write("Send Notice to: %s\n" % str(sendTo))
        sys.stderr.write("     Message  : %s\n" % str(message))
        if info: sys.stderr.write("     Info: %s\n" % info)
    else:
        if monitor:
          if notices: monitorPrt("Send Notice to: %s\n" % str(sendTo), 1)
          monitorPrt("     Message  : %s\n" % str(message), (8 if not notices else 5))
        if info: message += '\nKit ID and location: %s' % info
        if len(sendTo['slack']): slack_message(message,sendTo['slack'])
        if len(sendTo['email']): email_message(message,sendTo['email'])
    return True

# search for minimal set of sensors covering all fields
def searchSensors(afields,candidates,keyList=None):
    fields = list(set(afields)-set(['fields','sensors']))
    if not fields or not candidates: return []
    if keyList == None: keyList = candidates.keys()
    if not len(fields): return []
    minimal = keyList[0:]; fnd = False
    for item in keyList:
        thisSet = list(set(fields)-set(candidates[item]))
        if not len(thisSet): return [item]
        if len(thisSet) == len(fields): continue
        fnd = True
        current = list(set([item] + searchSensors(thisSet,candidates, list(set(keyList)-set(item)))))
        if len(current) < len(minimal): minimal = current[0:]
    if not fnd: return ['unknown']
    return minimal

def AllowInterval(interval,now=None):
    if not now: now = time()
    return int( now - (4.5*interval + 7.5 + 0.5)*60)

# only once at startup time: get names operational defined kits silent for long period
def DeadKits():
    global DB, TelegramCnt
    if not DB: return
    # obtain all operational kits
    kitTbls = DB.db_query("SELECT DISTINCT Sensors.project, Sensors.serial FROM Sensors, TTNtable WHERE Sensors.active AND TTNtable.active ORDER BY Sensors.datum DESC", True)
    if not len(kitTbls): return
    lastRun = 0 # get last date one was active
    Selection = []
    for kit in kitTbls:
      datum = 0
      try:
        tbl = DB.db_query("SHOW TABLES like '%s_%s'" % (kit[0],kit[1]), True)
        if not len(tbl) or not len(tbl[0]): continue # table does not exists
        datum = DB.db_query("SELECT UNIX_TIMESTAMP(datum) FROM %s_%s ORDER BY datum DESC LIMIT 1" % (kit[0],kit[1]), True)
        if datum[0][0]:
          datum = int(datum[0][0])
          Selection.append([datum,kit[0],kit[1]])
          if lastRun < datum: lastRun = datum
      except: pass
    if not lastRun: return
    # topic id for dead kits
    for indx in range(len(Selection)):
      diff = lastRun - Selection[indx][0]
      if diff <= 2*60*60: continue
      try:
        TTNid = DB.db_query("SELECT DISTINCT TTN_id FROM TTNtable WHERE project = '%s' AND serial = '%s' AND active" % (Selection[indx][1],Selection[indx][2]), True)
        if not len(TTNid) or not len(TTNid[0]): continue
        MyLogger.log(modulename,'ATTENT',"Kit TTN id %s, project %s, serial %s, not seen for a while. Last seen: %s." % (TTNid[0][0], Selection[indx][1],Selection[indx][2],datetime.datetime.fromtimestamp(Selection[indx][0]).strftime("%Y-%m-%d %H:%M")) )
        if not TelegramCnt: continue  # sendNotices only when fully operating
        if diff <= 24*60*60:
          sendNotice("Kit TTN id %s (project %s, serial %s:\t last seen %dh:%dm:%ds ago.\nMaybe not connected?\nLast time seen: %s.\nMySense kit information: %s." % (TTNid[0][0],Selection[indx][1],Selection[indx][2],diff/3600,(diff%3600)/60,(diff%(3600*60))%60,datetime.datetime.fromtimestamp(Selection[indx][0]).strftime("%Y-%m-%d %H:%M"),MyId2Info(TTNid[0][0])),myID="all/%s" % TTNid[0][0])
        else:
          sendNotice("Kit TTN id %s (project %s, serial %s:\nMaybe not connected for a long time?\nLast time seen: %s.\nMySense kit information: %s." % (TTNid[0][0],Selection[indx][1],Selection[indx][2],datetime.datetime.fromtimestamp(Selection[indx][0]).strftime("%Y-%m-%d %H:%M"),MyId2Info(TTNid[0][0])),myID='all/events')
      except: pass
    return

def cleanupCache(saveID): # delete dead kits from cache
    global cached, previous, Conf
    now = time(); items = []
    for item in cached.keys():
      # if debug:
      #   diff = int(now - cached[item]['last_seen'])
      #   sys.stderr.write("Kit %s:\t interval %dm%ds,\tseen %dh:%dm:%ds ago.\n" % (item.split('/')[1],cached[item]['interval']/60,cached[item]['interval']%60,diff/3600,(diff%3600)/60,(diff%(3600*60))%60))
      if saveID == item: continue
      try:
        if (cached[item]['last_seen'] < (now-60*60*2)) or (cached[item]['last_seen'] <= AllowInterval(cached[item]['interval'],now)):
            items.append(item)
      except: pass
    if not len(items): return
    if len(items) < 3:   #  len(cached)-1
      for item in items:
        serial = 'unknown'; project = 'unknown'
        try:
            serial = cached[item]['serial']
            project = cached[item]['project']
        except: pass
        MyLogger.log(modulename,'ATTENT',"Kit %s (project %s, S/N %s) not seen longer as %d minutes." % (item, project, serial,(now-cached[item]['last_seen'])/60))
        try:
            sendNotice("Kit %s (project %s, S/N %s) not seen longer as %d minutes.\nKit seems to be disconnected.\nLast time seen: %s." % (item,project, serial, (now-cached[item]['last_seen'])/60,datetime.datetime.fromtimestamp(cached[item]['last_seen']).strftime("%Y-%m-%d %H:%M")),myID=item)
        except Exception as e:
            MyLogger.log(modulename,'ERROR',"Failed to send 'not seen' notice: %s" % str(e))
        del cached[item]
    else:
      MyLogger.log(modulename,'ATTENT',"Seems TTN server is down for a long period at %s" % datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M"))
      sendNotice("Seems TTN server is down for a long period at %s (kits with no measurements: %s)." % (datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M"),', '.join(items[:3]) + '...' if len(items) > 3 else ''), myID='all/event')
      for item in items:
        del cached[item]
        if not item in previous: previous.append(item)

# get TTNtable id for a node returns (SensorsID,TTNtableID,last_seen,project_serial)
def TTNtopic2IDs(topic):
    global DB
    indx = 0
    try: indx = topic.index('/')+1
    except: pass
    try:
        return(DB.Topic2IDs(topic[indx:]))
    except:
        MyLogger.log(modulename,'FATAL','No connection to database')
        EXIT(1)
    return None
    
# invalid sensor value: name [min,max]
InvalidSensed = {
    'accu':     [0,120],
    'aqi':      [0,100],
    'gas':      [0,6000],
    'grain':    [0,100],
    'altitude': [-300,500],
    'latitude': [-90,90],
    'longitude':[-180,180],
    'pm05_cnt': [0,25000],
    'pm1':      [0,1000],
    'pm10':     [0,1000],
    'pm10_cnt': [0,25000],
    'pm1_cnt':  [0,25000],
    'pm25':     [0,1000],
    'pm25_cnt': [0,25000],
    'pm5_cnt':  [0,25000],
    'pm4_cnt':  [0,25000],
    'luchtdruk':[500,1500],
    'rv':       [0,100],
    'temp':     [-50,80],
    'wr':       [0,360],
    'ws':       [0,50],
    'rain':     [0,100],
}
# check for valid value of sensed data
def ValidValue(myID,afld,avalue):
    global cached
    try:
        if InvalidSensed[afld][0] <=  avalue <= InvalidSensed[afld][1]:
            return True
    except: return True
    if not 'invalids' in cached[myID]: cached[myID]['invalids'] = {}
    try:
        cached[myID]['invalids'][afld] += 1
        if cached[myID]['invalids'][afld] > 100: del cached[myID]['invalids'][afld]
    except:
        cached[myID]['invalids'][afld] = 0
        MyLogger.log(modulename,'ATTENT','Kit %s generates for sensor %s(%5.2f) out of band values.' % (myID.split('/')[1],afld,avalue))
    return False

# check for sensor field value fluctuation, no fluctuation give notice
# if not present initialize cache entry
# reset after 100, notice once after 20 times same value. To do: use interval timings
def FluctCheck(myID,afld,avalue):
    global Conf, cached
    if (not myID in cached.keys()) or (not 'check' in Conf.keys()) or not len(Conf['check']):
        return True
    if not afld in Conf['check']: return True
    if not 'check' in cached[myID].keys(): # inititialize
        cached[myID]['check'] = []
        for i in range(len(Conf['check'])): cached[myID]['check'].append([None,None])
    i = Conf['check'].index(afld)
    if (cached[myID]['check'][i][0] == None) or (cached[myID]['check'][i][0] != avalue):
        cached[myID]['check'][i][0] = avalue
        cached[myID]['check'][i][1] = 0
        return True
    # same value: to do: make max value variable per sensor type
    cached[myID]['check'][i][1] += 1
    if cached[myID]['check'][i][1] < 20: # await fluctuations ca 5 hours
        return True
    if cached[myID]['check'][i][1] > 20+1: # have already give notice
        if cached[myID]['check'][i][1] > 100: cached[myID]['check'][i][1] = 0 # reset
        return False
    MyLogger.log(modulename,'ERROR','kit %s has (malfunctioning) sensor field %s, which gives static value of %.2f.' (myID,afld,avalue))
    sendNotice('%s: kit %s has (malfunctioning) sensor field %s, which gives static value of %.2f.' % (datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M"),myID,afld,avalue),myID=myID)
    return False


def MyId2Info(myid):
    global DB
    if not DB: return 'UNKNOWN'
    topic = myid
    try:
        topic = myid[myid.index('/')+1:]
    except: pass
    qry = "SELECT Sensors.project, Sensors.serial, Sensors.street, Sensors.village FROM Sensors, TTNtable WHERE TTNtable.TTN_id = '%s' AND TTNtable.serial = Sensors.serial AND TTNtable.project = Sensors.project ORDER BY Sensors.active DESC, Sensors.datum DESC LIMIT 1" % topic
    qry = DB.db_query(qry, True)
    if not len(qry): return 'UNKNOWN'
    for i in range(len(qry[0])):
        if not qry[0][i]: qry[0][i] = 'unknown'
    return "project: %s, serial: %s, location: %s, %s" % (qry[0][0],qry[0][1],qry[0][2],qry[0][3])
    
# hack to delete PM mass None values when PM count is not zero
# deprecate when LoRa compression is not mapping NaN values to 0
def CheckPMmass( record ):
    if not type(record) is dict or not len(record): return record
    for item in ['pm1','pm25','pm10']:
        try:
            if record[item] == None and record[item+'_cnt'] > 0:
                record[item] = 0.013
        except: pass
    return record

# convert MQTT TTN (json) structure to internal MySense ident,value structure
def TTN2MySense( data, **sensor): ###########################
    global Conf, cached, previous, debug, ProcessStart
    global updateCacheTime, ReDoCache, dirtyCache, ShowCached
    global DB, WRSSI, WSNR
    global monitor
    def recordTranslate(arecord):
        new = {}
        for item in arecord.items():
            if item[1] == None: continue
            transltd = translate(item[0],ext=False)
            if item[1] or (transltd in ['temp','wr','ws']):
                new[transltd] = item[1]
        return new

    timing = None
    myID = data['app_id']+'/'+data['dev_id'] # to do: should use eui ID
    values = {} # init record with measurements
    record = {}

    for item in ['counter','payload_raw','port',]:
        if item in data.keys():
            record[item] = data[item]
        else: record[item] = None       # should be an error: return {}

    if ShowCached: PrtCached() # show what is in cache
    # update cache if dirty or uptime time has arrived
    if dirtyCache or (int(time()) >= updateCacheTime+ReDoCache):
        UpdateCache()
        importNotices() # check if notice addreses file exists and is modified
    else: cleanupCache(myID)
    if not myID in cached.keys():       # caching
        if len(cached) >= 100: # FiFo to avoid exhaustion, maydisrupt chack on dead kits
            oldest = time() ; oldestKey = None
            for key in cached.keys():
                if cached[key]['last_seen'] <= oldest:
                    oldest = cached[key]['last_seen']
                    oldestKey = key
            del cached[oldestKey]
        DBtables = TTNtopic2IDs(myID) #  kit meta info and TTN/export info from DB
        cached[myID] = {
            'unknown_fields': [],
            'count': 0, 'interval': 15*60,
            'firmware': getFirmware(data['app_id'],data['dev_id'],record['port']),
            'sensors': [],
            'last_seen':  DBtables[2],
            'DB': {
                'SensorsID':  DBtables[0],
                'TTNtableID': DBtables[1],
                'kitTable':   DBtables[3],
            },
            'identified': False}
        cached[myID]['port%d' % record['port']] = {}
        for key in ['packing','adjust']:
            try:
                cached[myID]['port%d' % record['port']][key] = cached[myID]['firmware'][key]
            except: pass
        cached[myID]['port%d' % record['port']]['decode'] = None # always decode?
        try: cached[myID]['port%d' % record['port']]['decode'] = cached[myID]['firmware']['decode']
        except: pass
        if 'sensors' in cached[myID]['firmware'].keys():
            if type(cached[myID]['firmware']['sensors']) is unicode:
                cached[myID]['firmware']['sensors'] = str(cached[myID]['firmware']['sensors'])
            if type(cached[myID]['firmware']['sensors']) is str:
                cached[myID]['firmware']['sensors'] = cached[myID]['firmware']['sensors'].upper()
                cached[myID]['firmware']['sensors'] = cached[myID]['firmware']['sensors'].split(',')
    if not 'port%d' % record['port'] in cached[myID].keys():
        try:
            firmware = getFirmware(data['app_id'],data['dev_id'],record['port'])
            cached[myID]['port%d' % record['port']] = {}
            for key in ['packing','adjust']:
                try:
                    cached[myID]['port%d' % record['port']][key] = firmware[key]
                except: pass
            for key in firmware['sensors']:
                if not key in cached[myID]['firmware']['sensors']:
                    cached[myID]['firmware']['sensors'].append(key)
        except: pass

    try:
        if cached[myID]['port%d' % record['port']]['decode']: data['payload_fields'] = {}
    except: pass
    now = time()
    # seen the kit before? If so need to throttle the kit?
    if cached[myID]['last_seen']: # update datagram frequency and throttle if needed so
        if (not 'file' in Conf.keys()) and (cached[myID]['count'] > 2) and ((now - cached[myID]['last_seen']) < (Conf['rate'])):
            cached[myID]['count'] += 1
            if not 'throttling' in cached[myID].keys():
                cached[myID]['throttling'] = now
                MyLogger.log(modulename,'ERROR','%s (re)start throttling kit: %s (rate %d < throttle %d secs).' % (datetime.datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M"),myID.split('/')[1],now - cached[myID]['last_seen'],Conf['rate']))
                raise ValueError('Start throttling kit: %s' % myID) # kit on drift
            MyLogger.log(modulename,'DEBUG','%s Throddling kit: %s\n' % (datetime.datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M"),myID))
            raise ValueError('Skip throttling kit: %s' % myID)       # still on drift
        cached[myID]['interval'] = min((cached[myID]['interval']*cached[myID]['count']+(max(now - cached[myID]['last_seen'],5*60)))/(cached[myID]['count']+1),60*60)
    cached[myID]['count'] += 1
    if ('throttling' in cached[myID].keys()) and ((now - cached[myID]['throttling']) > 4*60*60):
        monitorPrt('%s Reset throttling kit: %s\n' % (datetime.datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M"),myID), 13)
        del cached[myID]['throttling'] # reset throttling after 4 hours

    # maybe a datagram from unknown wild kit
    if len(cached[myID]['firmware']['sensors']) <= 0: # unregistrated sensor kit
        if not (cached[myID]['count']%50): # notice once in the 50 times
            MyLogger.log(modulename,'ATTENT','Unknown (new) kit or port %d use: %s' % (myID,record['port']))
            # may need to send a notice
            sendNotice('Unknown (new?) kit or port %d use found: %s' % (myID,record['port']),myID=myID)
        cached[myID]['count'] += 1
        # skip this record
        raise ValueError('unknown kit %s or port %d' % (myID,record['port']))

    # is this kit interrupted?
    tstamp = ProcessStart
    if (cached[myID]['count'] == 1):
        tstamp = 0
        if cached[myID]['last_seen']:
            tstamp = time() - (cached[myID]['last_seen'] if cached[myID]['last_seen'] > ProcessStart else (ProcessStart-1)) 
        if not tstamp:
            MyLogger.log(modulename,'ATTENT','Not activated and/or not administrated kit %s found.' % myID)
            if time()-ProcessStart > 60*60:
              sendNotice('Not activated or not administrated kit %s found at time: %s' % (myID,datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M")),myID=myID)
        elif tstamp > 90*60:
            MyLogger.log(modulename,'ATTENT','Kit %s is restarted after %dh%dm%ds' % (myID,tstamp/3600,(tstamp%3600)/60,tstamp%60))
            sendNotice('Kit %s is restarted at time: %s after %dh%dm%ds.\nMySense kit information: %s.' % (myID,datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M"),tstamp/3600,(tstamp%3600)/60,tstamp%60,MyId2Info(myID)),myID=myID)
        if myID in previous:
            previous.remove(myID)
    cached[myID]['last_seen'] = now # may be overwritten by datagram timestamp later

    # some ports have errors in TTN Java Script decoding
    # make sure pay_load_fields have: keys types (sensors) and fields
    # this needs some rework! Too many fields and types!
    # collect sensor product names, cache them,
    # and check if (translated) fields are known 
    if ("payload_fields" in data.keys()) \
        and len(data['payload_fields']):
        data['payload_fields'] = recordTranslate(data['payload_fields'])
        if 'type' in data['payload_fields'].keys(): # deprecated
            if not data['payload_fields']['type'].upper() in cached[myID]['sensors']:
                cached[myID]['sensors'].append(data['payload_fields']['type'].upper())
            del data['payload_fields']['type']
        for skip in ['TTNversion']:
            # known to skip (To Do check it)
            if skip in data['payload_fields'].keys():
                del data['payload_fields'][skip]
        if 'sensors' in data['payload_fields'].keys():
            if not isinstance(data['payload_fields']['sensors'], list):
                data['payload_fields']['sensors'] = data['payload_fields']['sensors'].split(',')
            for sensor in data['payload_fields']['sensors']:
                if not sensor.upper() in cached[myID]['sensors']:
                    cached[myID]['sensors'].append(sensor.upper())
            del data['payload_fields']['sensors']
        if ('time' in data['payload_fields'].keys()) and (data['payload_fields']['time'] > 946681200): # 1 jan 2000
            record['time'] = values['time'] = data['payload_fields']['time']
            del data['payload_fields']['time']
            timing = values['time']
        # cached['sensors'] is now up to date
        candidates = dict()
        for afld in data['payload_fields'].keys():
            field = translate(afld)
            fnd = False
            for sensor in cached[myID]['firmware']['sensors']:
                description = ProductKnown(sensor)
                if not description: continue
                if field in description['fields']:
                    fnd = True
                    try: candidates[sensor].append(field)
                    except: candidates[sensor] = [field]
            if not fnd:
                if  not afld in cached[myID]['unknown_fields']:
                    sendNotice("Unknown field %s in sensor kit %s, field skipped." % (afld,myID),myID=myID)
                    MyLogger.log(modulename,'ERROR','Unknown field "%s" in sensor kit %s. Skipped.' % (afld,myID))
                    cached[myID]['unknown_fields'].append(afld)
                del data['payload_fields'][afld]
            elif afld != field:
                data['payload_fields'][field] = data['payload_fields'][sense]
                del data['payload_fields'][afld]
            # data['payload_fields'] =  checkFields(data['payload_fields'])
        fields = list(set(data['payload_fields'].keys())-set(['fields','sensors']))
        candidates = searchSensors(fields,candidates)
        if candidates:
            data['payload_fields']['sensors'] = candidates
        if fields:
            data['payload_fields']['fields'] = fields
    elif ('payload_raw' in data.keys()) \
        and len(data['payload_raw']):
            if not 'firmware' in cached[myID]:  # try default
                firmware = getFirmware(data['app_id'],data['dev_id'],data['port'])
                if not len(firmware):
                    firmware = getFirmware('201802215971az','lopyprototype20180000',2)
                    MyLogger.log(modulename,'ERROR',"Unable to find firmware for device %s using LoPyNode" % data['dev_id'])
            else:
                firmware = cached[myID]['firmware']
            data['payload_fields'] = payload2fields(data['payload_raw'],firmware,data['port'],myID)
    else: return {}
    # side effect payload2fields: key sensors
    for item in ['sensors','fields','units']:
      if item in data['payload_fields'].keys():
        if not item in cached[myID].keys():
            cached[myID][item] = []
        cached[myID][item] = list(set(cached[myID][item]+data['payload_fields'][item]))
        del data['payload_fields'][item]
    if not len(data['payload_fields']): return {}    # nothing to do
    # we have now all  needed payload_fields with known/guessed fields of known/guessed sensors

    # from known firmware collect info for each measurement data
    Info = SensorInfo( cached[myID]['sensors'] if 'sensors' in cached[myID].keys() else cached[myID]['firmware']['sensors'] )

    # collect used gateways from datagram. Just for statistics
    if 'metadata' in data.keys(): # used gateways
        gtw = Get_Gtw(data['metadata'])    # get best used gateway
    else: gtw = []
    # see if we have first LoRa signal strength
    if len(gtw): # gtw = [ID, [lat,lon,alt], [rssi,min,max], [snr,min,max]]
        if not 'gtw' in cached[myID].keys(): cached[myID]['gtw'] = gtw
        else:
          try:
            if (WRSSI*cached[myID]['gtw'][2][0]+WSNR*cached[myID]['gtw'][2][0]) > (WRSSI*gtw[2][0] + WSNR*gtw[3][0]):
                if cached[myID]['gtw'][0] == gtw[0]: # update min and max value
                    for i in 2,3:
                        cached[myID]['gtw'][i][0] = gtw[i][0]
                        if gtw[i][1] < cached[myID]['gtw'][i][1]:
                            cached[myID]['gtw'][i][1] = gtw[i][1]
                        if gtw[i][2] > cached[myID]['gtw'][i][2]:
                            cached[myID]['gtw'][i][2] = gtw[i][2]
                else:
                    cached[myID]['gtw'] = gtw
          except: pass

    # load all measurements values, may calibrate them
    for item in data['payload_fields'].keys():
        values[item] = data['payload_fields'][item]
        try:
            # To Do: add calibrate between nodes/nodes within one sensor product
            # calibrate between different sensor manufacturers
            for calArray in ['calibrations',]:
                values[item] = tryCalibrate(item,values[item],Info['fields'],Info[calArray])
        except:
            pass

    # see if FPORT defines something. This may change in the future
    # FPORT 3 denotes meta data like sensor types, GPS
    # TTN may use port numbers to denote events
    gotMetaInfo = False
    if record['port'] in [3]: # event or meta info
        if len(record['payload_raw']) <= 1:
            values['event'] = cached[myID]['ports%d' % record['port']]
            if not 'event' in Info['fields']:
                Info['fields'].append('event')
                Info['units'].append('nr')
                Info['types'].append('LoRa port')
                Info['calibrations'].append(None)
        elif 'event' in values.keys():
            value = 0
            try:
                events = {
                    13: 'Accu level',
                    14: 'Watch Dog',
                    15: 'Controller Reset',
                    }
                if values['event'] in events.keys():
                    values['event'] = events[ values['event']]
                value = values['value']
            except: pass
            raise ValueError("%s;Event %s;Value %s" % (myID,str(values['event']),str(value)))
        else: # info in values
            #record = values.copy()
            gotMetaInfo = True
            addInfo(None,Info,clear=True)
            location = []; mod = []
            for t in ['longitude','latitude','altitude']:
                if t in values.keys():
                    location.append(str(values[t]))
                    del values[t]
            if len(location):
                Info['geolocation'] = ','.join(location)
            for t in ['meteo','dust','gps']:
                if (t in values.keys()) and values[t]:
                    fnd = False
                    if t == 'gps': values[t] = 'NEO-6'
                    else: values[t] = str(values[t])
                    if values[t]:
                        for sensor in Conf['sensors']:
                            if sensor['type'] == values[t]:
                                fnd = True; break
                        if fnd:
                            mod.append(str(values[t]))
                            addInfo(str(values[t]),Info)
                        else:
                            sys.stderr.write("Error in sensors conf: %s not found.\n" % values[t])
                    del values[t]
            #if len(mod):
            #    mod = 'hw: ' + ','.join(mod)
            #    delDecrFld(Info,'hw:')
            #    Info['description'] += ';' + mod
            #for t in Info.keys():
            #    if not t in ['project','description']:
            #        del Info[t]
            if ('time' in values.keys()) and (values['time'] > 946681200): # 1 jan 2000
                values = { 'time': values['time'] }
                timing = values['time']
            else: values = {}
            record = values.copy()

    # give access to DB for export measurments (output channels)
    Info['DB'] = { 'DB': DB, 'tables': cached[myID]['DB'] }
    
    # try to get timestamp
    if "metadata" in data.keys():
        for item in data['metadata'].keys():
            # meta time field is not time of measurement but from system time gateway
            # this time can be unreliable
            if item in ['time',]:
                # w're using the gateway timestamp
                if item == 'time':      # convert iso timestamp to UNIX timestamp
                    # time is time() minus 3600 secs with python V2 !! ?
                    timing = int(dp.parse(data['metadata']['time']).strftime("%s"))
                    if sys.version_info[0] < 3: # ?!???
                        timing += 3600
                        # if localtime().tm_isdst: timing += 3600
                        # else: timing -= 3600
                else:
                    values[item] = data['metadata'][item]
    if ('time' in values.keys()) and (values['time'] < 946681200): # 1 jan 2000 00:00
        del values['time']      # controller not synced with real time
    # correct timestamp
    if not 'time' in values.keys():
        if timing: values['time'] = record['time'] = timing
        else: values['time'] = record['time'] = int(time()) # needs correction
    # cached[myID]['last_seen'] = values['time'] # time measurement
    cached[myID]['last_seen'] = int(time()) # time seen

    # maintain identification info of this kit
    # to do limit wild card
    if not cached[myID]['identified']:
        Info['info'] = DB.getNodeFields(cached[myID]['DB']['SensorsID'],'*',table='Sensors')
        if not len(Info['info']):  # unknown kit
            if not (cached[myID]['count'] % 10):
                MyLogger.log(modulename,'ATTENT','Unknown MySense kit %s. Skipped.' % myID)
            cached[myID]['count'] += 1
            return {}
        try: cached[myID]['active'] = Info['info']['active']
        except: pass
        for item in ['project','serial']:
            if item in Info['info'].keys(): cached[myID][item] = Info['info'][item]
        Info['output'] = DB.getNodeFields(cached[myID]['DB']['TTNtableID'],'*',table='TTNtable')
        # update ordinates location of the kit
        try:
            coordinates = [float(r) for r in Info['info']['coordinates'].split(',')]
            if (coordinates[0] < 0.1) and (values['latitude'] > 0.1):
                # collect GPS measurement if home location is not defined
                Info['info']['coordinates'] = '%.6f,%.6f,%.1f' % (values['latitude'],values['longitude'],values['altitude'])
                # update Sensors table
                DB.setNodeFields(cached[myID]['DB']['SensorsID'],'coordinates',Info['info']['coordinates'])
                MyLogger.log(modulename,'ATTENT','Update home location coordinates (%s) for kit (%s) in Sensors DB table.' % (Info['info']['coordinates'],myID.split('/')[1]))
            elif ('latitude' in values.keys()) and ('longitude' in values.keys()):
                # delete small changes from home location in GPS measurement
                if GPSdistance(coordinates,(values['latitude'],values['longitude'])) < 100: # should be > 100 meter from std location
                    del values['latitude']; del values['longitude']
                    if 'altitude' in values.keys(): del values['altitude']
        except: pass
        cached[myID]['identified'] = True
                
    # ident will get extra keys from cached:
    # active (operational kit) and count (nr datagrams for this kit in current cache
    # will have keys project, serial geolocation if present in Sensors/TTNtable table
    ident = getIdent(Info,cached[myID]) # collect meta data for backends

    try:
        if not 'active' in cached[myID].keys():
           MyLogger.log(modulename,'ATTENT','Record from unknown kit with topic %s' % myID)
           monitorPrt('Record from unknown kit with topic %s' % myID, 5)
           MyLogger.log(modulename,'DEBUG','Record from unknown source: ident: %s, values: %s' % (myID,str(Info),str(values)))
           sendNotice('Not known (in test?) TTN device found: %s' % myID,myID=myID)
           cached[myID]['active'] = False
        elif not cached[myID]['active'] and cached[myID]['count'] <= 1:
           MyLogger.log(modulename,'ATTENT','Record from not activated kit: %s_%s' % (ident['project'],ident['serial']))
           monitorPrt('Record from not activated kit: %s_%s' % (ident['project'],ident['serial']),31)
           MyLogger.log(modulename,'DEBUG','Record from not activated kit: ident: %s, values: %s' % (str(ident),str(values)))
           sendNotice('Not active (in test?) kit found: %s, project: %s, serial: %s' % (myID,ident['project'],ident['serial']),myID=myID)
           # gotMetaInfo = True
        if (not cached[myID]['active']) and (not debug): return {}
    except Exception as e:
        MyLogger.log(modulename,'ERROR','Failure to convert record from %s: %s' % (myID,str(e)))
        return {}
    # assert len(values) > 0, len(ident) > 6
    # sendNotice('Got record ident: %s, data: %s' % (str(ident),str(values)), myID=myID)
    if monitor:
      if type( Conf['monitor'] ) is str:
        Conf['monitor'] = re.compile(Conf['monitor'])
      try:
        if Conf['monitor'].match(ident['project']+'_'+ident['serial']):
            timestamp = time()
            if 'time' in values.keys() and values['time']:
              timestamp = int(values['time'])
            monitorPrt("%-66.65s #%4.d%s" % (
                '%s %s (%s_%s):' % (datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M"),
                myID.split('/')[1], ident['project'], ident['serial']),
                cached[myID]['count'],
                (' at %dm%ds' % (cached[myID]['interval']/60,(cached[myID]['interval']%60))) if (cached[myID]['interval'] < 60*60) else ''
            ), 34)
      except: pass
    if ('check' in Conf.keys()) and (type(Conf['check']) is list):
        for item in values.keys(): # out of band values
            if not ValidValue(myID,item,values[item]): del values[item]
        for item in Conf['check']: # malfunctioning sensors
            try:
                if not FluctCheck(myID,item,values[item]): del values[item]
            except: pass
    # decomment next if LoRa decompression is improved for NaN values
    # return { 'ident': ident, 'data': values, 'myID': myID}
    return { 'ident': ident, 'data': CheckPMmass( values ), 'myID': myID}

def BrokerLogger(string):
    global modulename
    string = string.lstrip()
    for priority in ['DEBUG','INFO','ATTENT','WARNING','ERROR','CRITICAL','FATAL']:
      try:
        if string.index(priority) == 0:
          MLogger.log(modulename,priority,string[len(priority)+1:].lstrip())
          return
      except: pass
    MyLogger.log(modulename,'INFO',string)

def getdata():
    global Conf, TelegramCnt
    if not Conf['input']:
      MyLogger.log(modulename,'FATAL','No input channel defined. Exiting.')
      return True
    msg = {}
    if 'file' in Conf['input']:
      try:
        msg = ReadFromFile(Conf['file'])
        if msg == None: return None # EOF
        if not type(msg) is dict:
            ErrorCnt += 1
            raise ValueError("Wrong data record type received: %s" % str(msg))
        TelegramCnt += 1
        ErrorCnt = 0
      except: raise ValueError("Read error from input file.")
    elif 'TTN' in Conf['input']:
      # yet on only handle one input channel of TTN MQTT
      while True:
        try:
          msg = MyTTNclient.GetData(Conf['TTN'],verbose=debug,keepalive=180,logger=MyLogger.log,sec2pol=10)
          if msg == None: return None # No records any more
          if (not type(msg) is dict) or not len(msg):
            # raise IOError("Wrong error type or empty data record received")
            MyLogger.log(modulename,'ERROR',"Wrong error type or empty data record received")
            if ErrorCnt > 20:
              MyLogger.log(modulename,'FATAL','Subscription failed Mid: %s. Aborted.' % e)
              return None
            ErrorCnt += 1; sleep(1) # slow down a bit on error
            continue
          TelegramCnt += 1
          ErrorCnt = 0
          break
        except IOError as e:
          if ErrorCnt > 20:
              MyLogger.log(modulename,'FATAL','Subscription failed Mid: %s. Aborted.' % e)
              return None
          ErrorCnt += 1
        # watch dog should restart collector after 5 minutes.
        except Exception as e:
          MyLogger.log(modulename,'FATAL','Subscription is failing Mid: %s.\nSlowing down.' % str(e))
        sleep(10)
    else: raise ValueError("No known input channel type defined.")

    # + ['counter','payload_fields',payload_raw','hardware_serial','port','metadata']:
    for key in ['dev_id','app_id']:
      if not key in msg.keys():
        MyLogger.log(modulename,'ERROR','Received an unknown record %s' % str(msg))
        sleep(0.1)
    # TO DO: check dev_id to api key (mqtt broker checks user with AppId/DevAddr)
    # convert fields and values to MySense ident/data record
    return TTN2MySense(msg)

# send kill -USR1 <process id> to dump status overview
# there is a namespace problem with signal handling if done inside an import
signal.signal(signal.SIGUSR1, SigUSR1handler)
signal.signal(signal.SIGUSR2, SigUSR2handler)

# MAIN part of MQTT The Things Network Broker #######################

# default configure settings for Conf dict and Channels
# make changes for your local (default) situation here, and
# probably mainly in MyTTN-datacollector.conf.json configuration file.
# DEBUG, file, init file, output channels, etc can be overwritten via CLI arguments
def Configure():
    global Conf      # configuration items
    global Channels  # output channels eg database, forwarding data, console, ...
    # next json will overwrite default configuration settings
    Conf['initfile'] = 'MyTTN-datacollector.conf.json' # meta identy data for sensor kits
    Conf['from'] = 'Notice from MySense TTN data collector <mysense@localhost>'
    Conf['SMTP'] = 'localhost'
    Conf['nodesfile'] = None
    # one should use the MySense main script in stead of next statements
    Conf['input'] = [] # eg ['TTN',]
    # Conf['file'] = 'test_dev11.json'    # read from file iso TTN MQTT broker
    # Conf['DEBUG'] = True  # print stderr output channel actions

    # module: None load module on output True, 0 load module, other: module loaded
    # print=True colorize on output, file=filename or file=fifo=filename named pipe
    Channels = [
        {   'name': 'logger', 'timeout': time()-1, # logger must be first in list
            'Conf': {
                'level': 'INFO', 'file': sys.stderr, 'print': True,
                'date': False, # prepend with timing
                'monitor': False,  # monitoring correct publish data
            }
        },
        {   'name': 'monitor', 'timeout': time()-1, # build in module
            'Conf': {
                'output': False, 'file': sys.stdout, 'print': True,
                'date': True, # prepend with timing
                'monitor': False,  # monitoring correct publish data
                'serials': '([a-fA-F0-9]+)',  # only these serials
                'projects': '([a-zA-Z]{3,6})',# only for these projects
            }
        },
        {   'name': 'notices', 'timeout': time()-1, # build in module
            'Conf': {
                'output': True,
                'monitor': False,  # monitoring correct publish data
                # to do: add notices filtering in sendNotices
            }
        },
        {   'name': 'console', 'script': 'MyCONSOLE', 'module': None,
            'timeout': time()-1,
            'Conf': {
                'output': False, 'timeout': time()-1,
                'file': sys.stdout, 'print': True,
                'monitor': False,  # monitoring correct publish data
                'serials': '([a-fA-F0-9]+)',  # only these serials
                'projects': '([a-zA-Z]{3,6})',# only for these projects
            }
        },
        {   'name': 'database', 'script': 'MyDB', 'module': 0, # 0 enable nodes info export to DB
            'timeout': time()-1,
            'Conf': {
                'output': True,
                # use credentials from environment
                'hostname': None, 'database': 'luchtmetingen', # overwritten by DB, DBHOST
                'user': None, 'password': None, # overwritten bij DBUSER, DBPASS
                'monitor': False,  # monitoring correct publish data
                # 'serials': '([a-fA-F0-9]+)',  # only these serials
                # 'projects': '([a-zA-Z]{3,6})',# only for these projects
                'DEBUG': False
            }
        },
        {   'name': 'luftdaten', 'script': 'MyLUFTDATEN', 'module': None,
            'timeout': time()-1,
            'Conf': {
                'output': True,
                'id_prefix': "TTN-", # prefix ID prepended to serial number of module
                'luftdaten': 'https://api.luftdaten.info/v1/push-sensor-data/', # api end point
                'madavi': 'https://api-rrd.madavi.de/data.php', # madavi.de end point
                'timeout': 1*15,  # wait timeout on http request result
                # expression to identify serials subjected for data to be forwarded
                'serials': '(cc50e3|130aea|30[aA][eE][aA]4|3c71bf|788d27|807[dD]3[aA]|b4e62[fd]|D54990|e101e8)[A-Fa-f0-9]{4,6}', # serials numbers allowed to be forwarded
                'projects': '(HadM|SAN|KIP|RIVM)',  # expression to identify projects to be posted

                'active': True,    # output to luftdaten is also activated
                'DEBUG' : False,   # show what is sent and POST status
                'monitor': False,  # monitoring correct publish data
            }
        },
        ]
    return True

def ImportArguments():
    global Conf, Channels, debug
    # allow: cmd file=abc user=xyz password=acacadabra
    #            debug=True, console:output=False monitor:file=fifo=/tmp/Monitoring.pipe
    # and other Conf options
    #        cmd nodesfile=filename.json will only export nodes info to database
    # parse arguments and overwrite defaults in Conf and Channels
    #   This allows CLI arguments for Conf (as key=value) and Channels (as name:key=value)
    for arg in sys.argv[1:]:
        Match =  re.match(r'\s*(?P<channel>luftdaten:|console:|database:|monitor:|notices:)?(?P<key>[^=]+)=(?P<value>.*)', arg, re.IGNORECASE)
        if Match:
            Match = Match.groupdict()
            if Match['value'] == '': Match['value'] = None
            elif Match['value'].lower() == 'none': Match['value'] = None
            elif Match['value'].lower() == 'false': Match['value'] = False
            elif Match['value'].lower() == 'true': Match['value'] = True
            elif Match['value'].isdigit(): Match['value'] = int(Match['value'])
            if ('channel' in Match.keys()) and Match['channel']:
                for indx in range(len(Channels)):
                    if Channels[indx]['name'].lower() == Match['channel'][:-1].lower():
                        key = Match['key']
                        if key.lower() in ['debug']:
                            key = key.upper()
                        if key in Channels[indx]['Conf'].keys():
                            if type(Channels[indx]['Conf'][key]) is list:
                                Match['value'].split(',')
                            Channels[indx]['Conf'][key] = Match['value']
                            # sys.stderr.write("Channel %s new value Conf[%s]: %s\n" %(Channels[indx]['name'],key,str(Match['value'])))
                        break
            else:
                CMatch = re.match(r'(file|initfile|smtp|from|debug|DevAddr)',Match['key'], re.IGNORECASE)
                if CMatch:
                    if Match['key'].lower() in ['smtp','debug']:
                        if type(Conf[Match['key'].upper()]) is list: Match['value'].split(',')
                        Conf[Match['key'].upper()] = Match['value']
                    else:
                        if type(Conf[Match['key']]) is list: Match['value'].split(',')
                        Conf[Match['key']] =  Match['value']
                    sys.stderr.write("New value Conf[%s]: %s\n" %(Match['key'],str(Match['value'])))
    debug = Conf['DEBUG']
    return True

# synchronize Conf with Channels
def UpdateChannelsConf():
    global Conf, Channels, DB, monitor, notices
    try:
      for indx in range(len(Channels)):
        if Channels[indx]['name'] == 'monitor':
          monitor = False
          try:
            if Channels[indx]['Conf']['output']:
              import MyPrint
              fifo = False
              if type(Channels[indx]['Conf']['file']) is str:
                if Channels[indx]['Conf']['file'].find('fifo=') == 0:
                  fifo = True
                  Channels[indx]['Conf']['file'] = Channels[indx]['Conf']['file'][5:]
              #monitor = MyPrint.MyPrint(output=Channels[indx]['Conf']['file'], color=Channels[indx]['Conf']['print'], fifo=fifo, date=False)
              monitor = Channels[indx]['Conf']
              monitor['output'] = MyPrint.MyPrint(output=Channels[indx]['Conf']['file'], color=Channels[indx]['Conf']['print'], fifo=fifo, date=False)
              ThreadStops.append(monitor['output'].stop)
              if not 'monitor' in Conf.keys() or not Conf['monitor']:
                Conf['monitor'] = '.*'
                try: # only once
                  Conf['monitor'] = monitor['projects'] + '_' + monitor['serials']
                except: pass
              if type( Conf['monitor'] ) is str:
                Conf['monitor'] = re.compile(Conf['monitor'])
          except: Channels[indx]['Conf']['output'] = False
        elif Channels[indx]['name'] == 'notices':
          if Channels[indx]['Conf']['output']:
            notices = Channels[indx]['Conf']
            if not 'notices' in Conf.keys() or not Conf['notices']:
              Conf['notices'] = '.*'
              try: # only once
                Conf['notices'] = notices['projects'] + '_' + notices['serials']
              except: pass
            if type( Conf['notices'] ) is str:
              Conf['notices'] = re.compile(Conf['notices'])
        elif Channels[indx]['name'] == 'logger':
          for item in Channels[indx]['Conf'].keys():
            MyLogger.Conf[item] = Channels[indx]['Conf'][item]
          if (type(MyLogger.Conf['level']) is str) and (not MyLogger.Conf['level'] in [ 'NOTSET','DEBUG','INFO','ATTENT','WARNING','ERROR','CRITICAL','FATAL']):
            sys.stderr.write("Wrong logging level %s, reset to WARNING\n" % MyLogger.Conf['level'])
            MyLogger.Conf['level'] = 'WARNING'
          MyLogger.log(modulename,'INFO',"Starting up %s, logging level %s" % (modulename,MyLogger.Conf['level']))
          if MyLogger.Conf['stop']: ThreadStops.append(MyLogger.Conf['stop'])
          continue
        if Channels[indx]['Conf']['output']:
          filterMsg = 'Output NOT filtered'
          if 'projects' in Channels[indx]['Conf'].keys() and 'serials' in Channels[indx]['Conf'].keys():
            filterMsg = "Output FILTER: '%s'" %  (Channels[indx]['Conf']['projects'] + '_' +  Channels[indx]['Conf']['serials'])
          MyLogger.log(modulename,'INFO','Output for "%s":\n\tOutput channel is %s\n\t%s' % (Channels[indx]['name'], 'enabled', filterMsg))
        else:
          MyLogger.log(modulename,'INFO','NO output for "%s":\n\tOutput channel is %s' % (Channels[indx]['name'], 'DISABLED'))
        if not 'script' in Channels[indx].keys():
          continue
        Channels[indx]['filter'] = None
        try:
            Channels[indx]['filter'] = re.compile(Channels[indx]['Conf']['projects'] + '_' + Channels[indx]['Conf']['serials'])
        except: pass
        Channels[indx]['net'] = {'module':False,'connected':Channels[indx]['Conf']['output']}
        if (not Channels[indx]['Conf']['output']) and (Channels[indx]['module'] == None):
          continue
        if (Channels[indx]['script'] == 'MyLUFTDATEN') and ('file' in Conf.keys()) and Conf['file'] and not Channels[indx]['Conf']['DEBUG']:
          # do not output to Luftdaten as timestamp is wrong
          Channels[indx]['Conf']['output'] = False
        if ('module' in Channels[indx].keys()) and not Channels[indx]['module']:
          # if not (Channels[indx]['module'] == None and ('output' in Channels[indx]['Conf'].keys) and not Channels[indx]['Conf']['output']):
          try:
            Channels[indx]['module'] = __import__(Channels[indx]['script'])
            if 'log' in Channels[indx]['module'].Conf.keys():
              Channels[indx]['module'].Conf['log'] = MyLogger.log # one log thread
            Channels[indx]['net']['module'] = True
          except:
            MyLogger.log(modulename,'FATAL','Unable to load module %s' % Channels[indx]['script'])
            return False
        if Channels[indx]['name'] == 'database': DB = Channels[indx]['module']
        for item in Channels[indx]['Conf'].keys():
          if Channels[indx]['module']:
            Channels[indx]['module'].Conf[item] = Channels[indx]['Conf'][item]
          Channels[indx]['errors'] = 0
        # end of channel update
    except ImportError as e:
      MyLogger.log(modulename,'ERROR','One of the import modules not found: %s' % e)
      return False
    except Exception as e:
      MyLogger.log(modulename,'ERROR','Exception in conf update with %s' % str(e))
      return False
    return True

def RUNcollector():
    global  Channels, debug, monitor, cached, Conf
    error_cnt = 0; inputError = 0
    # configure MySQL luchtmetingen DB access
    while 1:
        if inputError > 10:
            MyLogger.log(modulename,'WARNING','Slow down uploading from broker(s)')
            sleep(5*60)
        if (error_cnt > 20) or (inputError > 20):
            MyLogger.log(modulename,'FATAL','To many input errors. Stopped broker')
            sendNotice('Too many TTN MQTT server input errors. Try to restart the data collecting server %s' % socket.getfqdn(),myID='all/event')
            StopTTNconnection()
            return False
        record = {}
        try:
            record = getdata()
            if record == None:
              MyLogger.log(modulename,'INFO','END of Data input')
              break # no more records
        except ValueError as e:
            err = str(e)
            if err.find(';Event') > 0:
                MyLogger.log(modulename,'DEBUG',"Event: %s" % str(e))
                err = err.split(';')
                if (not type(err) is list) or (len(err) != 3):
                  MyLogger.log(modulename,'ATTENT',"Curious event: %s" % str(e))
                else:
                  # patch for elder kits firmware
                  if (str(err[1]).find('Accu level') < 0) or (str(err[2]).find('Value 0') < 0):
                    sendNotice("Sensor kit %s raised %s with %s" % (err[0],str(err[1]),str(err[2])),myID=err[0])
                  MyLogger.log(modulename,'ATTENT',"Sensor kit %s raised %s with %s" % (err[0],str(err[1]),str(err[2])))
            elif err.find('unknown') >= 0:
                try: err = str(err).split('/')[1]
                except: pass
                MyLogger.log(modulename,'INFO','Skip data from unknown kit: %s at time %s' % (err,datetime.datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M")))
            elif err.find('throttling') >= 0:
                if (err.find('Start') >= 0) and (not monitor):
                    MyLogger.log(modulename,'ATTENT',err)
                    sendNotice(err, err.split('/')[1])
                # else still throttling this kit, just skip the record
            elif err.find('I/O operation on closed file') >= 0:
                MyLogger.log(modulename,'INFO','EOF on input file %s' % Conf['file'])
                return True
            else:
                inputError += 1
                MyLogger.log(modulename,'INFO','Get get record error: %s (skipped)' % err)
            continue
        except Exception as e:
            PrintException()
            # sys.stderr.write(traceback.format_exc())
            MyLogger.log(modulename,'INFO','Get data failed with %s' % e)
            # sys.stderr.write("FAILED record: %s" % str(record))
            inputError += 1
            continue
        if (not type(record) is dict):
            MyLogger.log(modulename,'ATTENT','Data failure from LoRaWan data concentrator')
            error_cnt += 1
            continue
        elif not 'ident' in record.keys():
            MyLogger.log(modulename,'DEBUG','Undefined record from LoRaWan data concentrator')
            continue
        cnt = 0; inputError = 0
        if 'description' in record['ident'].keys():
            MyLogger.log(modulename,'DEBUG','%s Got data from sensors: %s' % (datetime.datetime.fromtimestamp(record['data']['time']).strftime("%Y-%m-%d %H:%M"),record['ident']['description']))
        else:
            MyLogger.log(modulename,'DEBUG','%s Got data (no  sensors description)' % datetime.datetime.fromtimestamp(record['data']['time']).strftime("%Y-%m-%d %H:%M"))
        for indx in range(len(Channels)):
            try:
              if not Channels[indx]['module']: continue
              if not Channels[indx]['Conf']['output']: continue
            except: continue
            PublishMe = True
            export = None
            try:
              export = cached[record['myID']]['exports'][Channels[indx]['name']]
            except: pass
            if debug:
              PublishMe = False; cnt += 1
            elif not record['ident']['active'] or ((export != None) and not export):
              PublishMe = False ; cnt += 1
              if cached[record['myID']]['count'] < 1:
                if not record['ident']['active']:
                  MyLogger.log(modulename,'ATTENT',"Kit MQTT %s with serial %s not activated. Skip other output." % (record['myID'],record['ident']['serial']))
                  monitorPrt("Kit MQTT %s with serial %s not activated. Skip other output." % (record['myID'],record['ident']['serial']), 1)
                else:
                  MyLogger.log(modulename,'ATTENT',"Kit MQTT %s with serial %s data export disabled. Skip other output." % (record['myID'],record['ident']['serial']))
                  monitorPrt("Kit MQTT %s with serial %s data export disabled. Skip other output." % (record['myID'],record['ident']['serial']), 5)
            elif time() < Channels[indx]['timeout']:
                PublishMe = False ; cnt += 1
            if Channels[indx]['module'] and Channels[indx]['Conf']['output']:
              if PublishMe:
                RsltOK = False
                try: RsltOK = Channels[indx]['Conf']
                except: pass
                Rslt = True; filtered = False
                try:
                    # check if output is filtered for this channel
                    if 'filter' in Channels[indx].keys() and Channels[indx]['filter'] and not Channels[indx]['filter'].match(record['ident']['project']+'_'+record['ident']['serial']):
                        filtered = True # do not publish if defined not to
                    if not filtered:
                        Rslt = Channels[indx]['module'].publish(
                            ident = record['ident'],
                            data = record['data'],
                            internet = Channels[indx]['net']
                            )
                    # failures without an exception event will not be queued for a retry
                    if type(Rslt) is bool and not filtered:
                        if Rslt == True:
                          if RsltOK and monitor:
                            try:
                              if Conf['monitor'].match(record['ident']['project']+'_'+record['ident']['serial']):
                                monitorPrt("    %-50.50s OK" % ('Kit %s/%s data output to %s:' % (record['ident']['project'],record['ident']['serial'],Channels[indx]['name'])),4)
                            except: pass
                        else:
                          MyLogger.log(modulename,'ATTENT','Kit %s/%s data no output to %s' % (record['ident']['project'],record['ident']['serial'],Channels[indx]['name']))
                          monitorPrt("    %-50.50s FAILED" % ('Kit %s/%s data no output to %s:' % (record['ident']['project'],record['ident']['serial'],Channels[indx]['name'])),1)
                    elif Rslt:
                        if type(Rslt) is str or type(Rslt) is unicode:
                            MyLogger.log(modulename,'ATTENT','Kit %s/%s data NO output to %s: %s' % (record['ident']['project'],record['ident']['serial'],Channels[indx]['name'],str(Rslt)))
                            monitorPrt("    %-50.50s FAILURE %s" % ('Kit %s/%s data NO output to %s:' % (record['ident']['project'],record['ident']['serial'],Channels[indx]['name']),str(Rslt)),1)
                        elif type(Rslt) is list:
                            try: Rslt = ', '.join(Rslt)
                            except: Rslt = str(Rslt)
                            if len(Rslt):
                              if RsltOK and monitor and not filtered:
                                try:
                                  if Conf['monitor'].match(record['ident']['project']+'_'+record['ident']['serial']):
                                    monitorPrt("    %-50.50s OK for %s" % (('Kit %s/%s data output to %s:' % (record['ident']['project'],record['ident']['serial'],Channels[indx]['name'])),str(Rslt)),31)
                                except: pass
                            else:
                              MyLogger.log(modulename,'ATTENT','Kit %s/%s data output to %s: %s' % (record['ident']['project'],record['ident']['serial'],Channels[indx]['name'],str(Rslt)))
                              monitorPrt("    %-50.50s NO output." % (('Kit %s/%s data output to %s:' % (record['ident']['project'],record['ident']['serial'],Channels[indx]['name'])),str(Rslt)),1)
                    else:
                        MyLogger.log(modulename,'ATTENT','Kit %s/%s data output to %s: unknown' % (record['ident']['project'],record['ident']['serial'],Channels[indx]['name']))
                        monitorPrt("    %-50.50s UNKNOWN FAILURE" % ('Kit %s/%s data NO output to %s:' % (record['ident']['project'],record['ident']['serial'],Channels[indx]['name'])),1)
                    if ('message' in Channels[indx]['module'].Conf.keys()) and Channels[indx]['module'].Conf['message']:
                        try:
                          sendNotice(Channels[indx]['module'].Conf['message'],myID=record['myID'])
                          Channels[indx]['module'].Conf['message'] = ''
                        except: pass
                    Channels[indx]['errors'] = 0
                    Channels[indx]['timeout'] = time()-1
                    cnt += 1
                    MyLogger.log(modulename,'DEBUG','Sent record to outputchannel %s' % Channels[indx]['name'])
                except Exception as e:
                    if str(e).find("EVENT") > 0:
                        sendNotice('Event notice "%s" on archive action for kit %s/%s' % (str(e)[str(e).index('EVENT')+5:],record['ident']['project'],record['ident']['serial']),myID='all/event')
                    else:
                        MyLogger.log(modulename,'ERROR','sending record to %s: %s' % (Channels[indx]['name'],str(e)))
                        Channels[indx]['errors'] += 1
                try:
                    one = Channels[indx]['module'].Conf['stop']
                    if one and not ThreadStops.count(one): ThreadStops.append(one)
                except: pass
            if Channels[indx]['errors'] > 20:
                if time() > Channels[indx]['timeout']: # throttle 5 mins
                    # skip output for 5 minutes
                    Channels[indx]['timeout']+5*50
                    Channels[indx]['errors'] += 1
            if Channels[indx]['errors'] > 40:
                Channels[indx]['module']['Conf']['output'] = False
                MyLogger.log(modulename,'ERROR','Too many errors. Loaded output channel %s: DISABLED' % Channels[indx]['name'])
                sendNotice('TTN MQTT Server %s: too many errors. Output channel %s: output is DISabled' % (socket.getfqdn(),Channels[indx]['name']),myID='all/event')
        if cnt or debug or monitor: continue
        MyLogger.log(modulename,'FATAL','No output channel available. Exiting')
        break
    return True

if __name__ == '__main__':
    Configure()
    ImportArguments()
    if not UpdateChannelsConf():
        MyLogger.log(modulename,'FATAL','Error on Update Channel configurations.')
        EXIT(1)
    if not Initialize():
        MyLogger.log(modulename,'FATAL','Error on initialisation.')
        EXIT(1)
    try: RUNcollector()
    except Exception as e: 
        sys.stderr.write("EXITING by exception: %s\n" % str(e))
    # stop all threads with brokers
    EXIT(0)
