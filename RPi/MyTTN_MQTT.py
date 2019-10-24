#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
# 
# Copyright (C) 2017, Behoud de Parel, Teus Hagen, the Netherlands
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# $Id: MyTTN_MQTT.py,v 1.4 2019/10/24 13:34:16 teus Exp teus $

# Broker between TTN and some  data collectors: luftdaten.info map and MySQL DB

# module mqtt: git clone https://github.com/eclipse/paho.mqtt.python.git
# cd paho.mqtt.python ; python setup.py install
# broker server: Debian: apt-get install mqtt

""" Download measurements from TTN MQTTT server:
    Subscribe to measurements from a Mosquitto Broker server
    e.g.
    Publish measurements as client to luftdaten.info and MySQL
    One may need to change payload and TTN record format!
"""
modulename='$RCSfile: MyTTN_MQTT.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.4 $"[11:-2]

try:
    import MyLogger
    import dateutil.parser as dp
    import datetime
    import sys, os
    import signal
    import json
    import socket
    import re
    from time import time, sleep, localtime
    socket.setdefaulttimeout(60)
    import paho.mqtt.client as mqtt
    from struct import *
    import base64
    import traceback
except ImportError as e:
    print("One of the import modules not found: %s\n" % e)
    exit(1)

debug = False   # output only for debugging reasons, no export of data

waiting = False          # waiting for telegram
mid = None               # for logging: message ID
telegrams = []           # telegram buffer, max length is 100     
ErrorCnt = 0             # connectivity error cnt, slows down, >20 reconnect, >40 abort
PingTimeout = 0          # last time ping request was sent
noticeStarted  = 60*60   # point in time to note new kits

# TTN working command line example
# mosquitto_sub -v -h eu.thethings.network -p 1883 -u 20179215970128 -P 'ttn-account-v2.ZJvoRKh3kHsegybn_XhADOGEglqf6CGAChqLUJLrXA'  -t '+/devices/+/up' -v

# configurable options
__options__ = [
        'input',       # output enables
        'hostname','port', 'user','password', # MQTT server credentials
        'dust', 'meteo'# classes field names coming from TTN MQTT server
        # to do: should go as conf per device and needs type of sensor
        'packing',     # how it is packed, which sensor types
        'classes',     # map appl/device to class of sensor kit config
        'sensors',     # sensor module types for 'dust', 'meteo' ...
        'all',         # skip not registered and "inactive"  nodes
        'timeout',     # timeout for no server active
        'rate',        # expected rate of telegrams received
        'file',        # data input json records from file iso MQTT server
        'adminfile',   # meta data for sensor kits (location, etc.)
        ]

Conf = {
    'input': False,
    'hostname': 'eu.thethings.network', # server host number for mqtt broker
    'port': 1883,        # default MQTT port
    'user': 'account_name', 'password': 'ttn-account-v2.acacadabra',
    # credentials to access broker
    'qos' : 0,           # dflt 0 (max 1 telegram), 1 (1 telegram), or 2 (more)
    'cert' : None,       # X.509 encryption
    'project': 'XYZ',    # default prefix to unique device/serial number
    # + is a wild card in TTN
    'topic': 'devices',  # main topic
    'AppId': '+',        # to be fixed regular expression to accept AppId to subscribe to
    'DevAddr': '+',      # to be fixed regular expression to accept DevAddr numbers
    'timeout': 2*60*60,  # timeout for this broker
    'rate':    7*60,     # expected time(out) between telegrams published

    # TO DO: adminfile should go to database
    # defines nodes, LoRa, firmware, classes, etc. for Configure info
    # this will read from a dump MQTT file, can be defined from command line file=..
    # notices:
    'notice': [['pattern','method:address',],], # send notices to email, slack, ...
    # 'file': 'Dumped.json', # uncomment this for operation from data from file
    # 'adminfile': 'LoPy-Admin.conf.json', # meta identy data for sensor kits
    'nodes': {},  # DB of sensorkits info
    # adminfile will define and overwrite:
    #   LoRa, nodes, sensors, classes, firmware, and translate
    # 'test': True     # use TTN record example in stead of server access
    # DB dictionary with different sensors: type, producer, sensors/units
    # should go to a json file
    # key calibrations is optional
    # types need to be capitalized
    # group classification is not used yet
    "LoRa": {   # TO DO: create a row, one per threard
        "project": "test",
        "hostname": "eu.thethings.network",
        "port": 1883,
        "topic": "app id",      # used as Conf['user'] TTN MQTT access
        "account": "ttn-account-v2.acacadabra" # TTN password MQTT server
      },
    # send notices node pattern, to...
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
    # should go to a json adminfile To Do: put this in a DB
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
                "units":["ug/m3","ug/m3","ug/m3","pcs/dm3","pcs/dm3","pcs/dm3","pcs/dm3","pcs/dm3","um"],
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
            {  "type": "NEO",
                "producer":"NEO-6","group":"GPS",
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
              "sensors": ["PMS7003","SDS011","BME680","BME280","NEO","PYCOM"]
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
              "sensors": ["PMS7003","SDS011","SPS30","BME680","BME280","NEO","PYCOM","ENERGY"]
            },
            "port10": {
              # Libelium Wasnodes void,id,void,accu,temp,...
              #"packing": ["<B11sB7sBBBBBfBfBfBfBfBfBBBf"],
              "packing": ["<B11sB7sBBBBBfBfBfBfBfBfBBBf"], # (id,value),...
              # every field has sensor id one byte
              "nr2field": {"35": None, "239": "node", "60": None, "52": "accu", "74": "temp", "76": "rv","77":"luchtdruk","158":"rain","159":"prevrain","160":"dayrain","157":"wr","156":"ws"},
              "fields": ["accu","temp","rv","luchtdruk","rain","prevrain","dayrain","wr","ws"],
              "adjust": [[0,1],[0,1],[0,1],[0,0.01],[0,1],[0,1],[0,1],[0,1],[0,1]],
              "sensors": ["WASPMOTE"],
              "meteo": ["unknown"]
          }
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
    'all': False,       # skip non active and not registered nodes
}

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

dirtyCaches = False
startedCache = time()+noticeStarted
def GetAdminDevicesInfo( overwrite = True ):
    global Conf, dirtyCaches, dirtyIdentCache
    if (not overwrite) and (len(Conf['nodes']) > 0): return # only once
    new = {}
    if ('adminfile' in Conf.keys()) and Conf['adminfile']:
        # admin conf.json should be read from file
        try:
            # json file may have comments in this case
            from jsmin import jsmin     # tool to delete comments and compress json
            with open(Conf['adminfile']) as _typeOfJSON:
                new = jsmin(_typeOfJSON.read())
            new = json.loads(new)
        except ValueError as e:
            MyLogger.log(modulename,'ERROR',"Json error in admin file %s: %s" % (Conf['adminfile'],e))
            if not overwrite:
                MyLogger.log(modulename,'FATAL','Unable to proceed. Fix admin file.')
                return
            MyLogger.log(modulename,'ATTENT','Missing or errors in LoRa admin json file with info for all LaRa nodes. Using defaults.')
            Conf['nodes'] = { 'no_devices': {} }
            # return
            # example of content of admin file specified for TTN MQTT RIVM records
            # fields may be optional
            # TO DO: per AppID one nodes dict (device name may not be unique per TTN)
            Conf['nodes'] = {
                'pmsensorN': {           # Device id TTN
                    'GPS': {
                        'longitude': 51.12345, 'latitude': 6.12345, 'altitude': 23, },
                    'label': 'Jelle', 'street': 'Fontys nr 8',
                    'village': 'Venlo', 'pcode': '5888 XY',
                    'province': 'Limburg', 'municipality': 'Venlo',
                    'date': '20 december 2017', # start date
                    'tel': '+31773270012',
                    'comment': 'test device',
                    # 'serial': None, if not defined use hash topic/device name
                    "serial": "30aea4008438", # PyCom unique ID
                    # To Do: add calibration details
                    'AppSKEY': 'xyz',    # LoRa key from eg RIVM
                    'NwkSKey': 'acacadabra', # LoRa key from eg RIVM
                    'meteo': 'BME280',   # meteo sensor type
                    'dust': 'SDS011',    # dust sensor type
                    'luftdaten.info': False,     # forward to Open Data Germany?
                    'active': False,
                }
            }
        dirtyCaches = True ; dirtyIdentCache = True
        # nodes should go to database
        for item in ['project','nodes','sensors','firmware','classes','translate','LoRa','notice','from','SMTP']:
            if item in new.keys():
                Conf[item] = new[item]
                MyLogger.log(modulename,'ATTENT','Overwriting dflt definitions for Conf[%s].' % item)
    if not 'all' in Conf.keys():        # handle nodes: dflt all if not configured
        Conf['all'] = False
        if len(Conf['nodes']) > 1: Conf['all'] = False # dflt: only registrated nodes
    for device in Conf['nodes'].keys():       # build array of sensor types in this device
        if not 'sensors' in Conf['nodes'][device].keys():
            Conf['nodes'][device]['sensors'] = []
        for sense in ['meteo','dust','gas']:
            if (sense in Conf['nodes'][device].keys()):
                if type(Conf['nodes'][device][sense]) is unicode:
                    Conf['nodes'][device][sense] = str(Conf['nodes'][device][sense])
                if type(Conf['nodes'][device][sense]) is str:
                    Conf['nodes'][device][sense] = Conf['nodes'][device][sense].split(',')
                for item in Conf['nodes'][device][sense]:
                    item = item.upper()
                    if not item in Conf['nodes'][device]['sensors']:
                        Conf['nodes'][device]['sensors'].append(item)
        Conf['nodes'][device]['sensors'].sort()

# reread admin meta info of nodes in, may de/activate data arcghiving of the node
def SigUSR2handler(signum,frame):
    GetAdminDevicesInfo() # reload admin info from admin file

# see if we know this product
unkownProducts = []
def ProductKnown( product ):
    global Conf
    if not 'sensors' in Conf.keys():
        MyLogger.log(modulename,'FATAL','Missing sensors key in Conf dictionary.')
        return None
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
            if item[1] == None: confinue
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
        data[item[0]] = item[1]
        data['fields'] = list(set(data['fields']+[item[0]]))
        sense = getTypes(SenseFlds,item[0])
        data['sensors'] = list(set(data['sensors']+list(sense)))
    return data

# unpack base64 TTN LoRa payload string into array of values NOT TESTED
# architecture is changed!, To Do: unpack on length of received bytes!
def payload2fields(payload, firmware, portNr):
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
    if not fnd:
        MyLogger.log(modulename,'ERROR','Cannot find payload converter definition for id %s.' % firmware['id'])
        return {}
    rts = {}
    if (firmware['id'] == 'LoPyNode') and (portNr != 10): declared += ['GPS','PYCOM']
    try:
        # I do not like special cases
        if (firmware['id'] == 'LoPyNode') and (portNr == 10): # Libelium case
            if 'nr2field' in firmware.keys():
                new = [None]*len(firmware['fields'])
                for i in range(0,len(load),2):
                    fldnr = '%d'%load[i]
                    if fldnr in firmware['nr2field'].keys():
                        if firmware['nr2field'][fldnr]:
                          try:
                            new[firmware['fields'].index(firmware['nr2field'][fldnr])] = load[i+1]
                          except: pass
                if 'sensors' in firmware.keys(): defined = list(set(firmware['sensors']))
                load = new
            else: raise ValueError("incomplete json def")
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
        for idx in range(0,len(load)):
            if firmware['adjust'][idx] != None:
                rts[firmware['fields'][idx]] = calibrate(firmware['adjust'][idx],load[idx])
        # try to improve guess for sensor type via existing field value
        rts = checkFields(rts)
        if declared:
            rts['sensors'] = list(set(rts['sensors'] + declared))
            for sensor in Conf['sensors']:
                if (sensor['type'] in declared) or (sensor['type'].lower() in declared):
                    rts['fields'] = list(set(rts['fields']+sensor['fields']))
        if defined: rts['sensors'] = defined
        rts['sensors'].sort(); rts['fields'].sort()
    except:
        MyLogger.log(modulename,'ERROR','Unpacking LoRa MQTT payload. Record skipped.')
        raise ValueError
        return{}
    return rts
        
# update ident record with info from json admin file
def updateIdent( AppId, devAddr, ident, updateCache=False):
    global Conf, cached
    if not devAddr in Conf['nodes'].keys():
        return ident
    cacheKey = AppId+'/'+devAddr
    if updateCache:
        for k in ident.keys():
            Conf['nodes'][devAddr][k] = ident[k]
        cached[cacheKey]['ident'] = ident
    if not 'geolocation' in Conf['nodes'][devAddr].keys():
        if 'GPS' in Conf['nodes'][devAddr].keys():
            Conf['nodes'][devAddr]['geolocation'] = str(round(Conf['nodes'][devAddr]['GPS']['longitude'],6))+','+str(round(Conf['nodes'][devAddr]['GPS']['latitude'],6))+','+str(round(Conf['nodes'][devAddr]['GPS']['altitude'],1))
    for item in ["geolocation",'label','village','street','pcode','province','municipality','active']:
        if item in Conf['nodes'][devAddr].keys():
            ident[item] = Conf['nodes'][devAddr][item]
    if ('comment' in Conf['nodes'][devAddr].keys()) and Conf['nodes'][devAddr]['comment']:
        if not 'description' in ident.keys(): ident['description'] = ''
        else: ident['description'] += ';'
        ident['description'] += Conf['nodes'][devAddr]['comment']
    for item in ['luftdaten.info','luftdaten','madavi']:
        if item in Conf['nodes'][devAddr].keys():
            ident[item.replace('.info','')] = Conf['nodes'][devAddr][item]
    if 'ident' in cached[cacheKey].keys():
        return cached[cacheKey]['ident']
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
        except:
            MyLogger.log(modulename,'FATAL',"unable to open json input file %s" % Conf['file'])
            exit(1)
    while(1):
        line = Conf['fileFD'].readline()
        if (not line) or (not len(line)): # EOF
            Conf['fileFD'].close()
            exit(0)
        if line.find('/up {') < 0: continue
        return( { 'topic': line[0:line.find(' ')], 'payload': line[line.find(' ')+1:] } )

# Define event callbacks
# this is multi threaded: TTN download data thread
def PubOrSub(topic,option):
    global Conf, waiting, mid, telegrams, PingTimeout, ErrorCnt
    waiting = False
    mid = None
    telegram = None
    # uncomment if TTN server does not publish records
    # following is the telegram as is expected from TTN MQTT server
    if ('test' in Conf.keys()) and Conf['test']:
        return ( { 
            'topic': 'pmsensors/devices/pmsensor1/up',
            'payload': '{"app_id":"pmsensors","dev_id":"pmsensor10","hardware_serial":"EEABABABBAABABAB","port":1,"counter":73,"payload_raw":"ACgALAG0ASU=","payload__fields":{"PM10":4.4,"PM25":4,"hum":29.3,"temp":23.6,"type":"SDS011"},"metadata":{"time":"2017-12-15T19:32:04.220584016Z","frequency":868.3,"modulation":"LORA","data_rate":"SF12BW125","coding_rate":"4/5","gateways":[{"gtw_id":"eui-1dee14d549d1e063","timestamp":536700428,"time":"","channel":1,"rssi":-100,"snr":6,"rf_chain":1,"latitude":51.35284,"longitude":6.154711,"altitude":40,"location_source":"registry"}],"latitude":51.353,"longitude":6.1538496,"altitude":2,"location_source":"registry"}}'
            })

    def on_connect(client, obj, flags, rc):
        global waiting
        if rc != 0:
            MyLogger.log(modulename,'ERROR','Connection error nr: %s' % str(rc))
            waiting = False
            if 'fd' in Conf.keys():
                Conf['fd'] = None
            raise IOError("MQTTsub connect failure.")
        else:
            MyLogger.log(modulename,'DEBUG','Connected.')
            pass
    
    def on_message(client, obj, msg):
        global waiting, telegrams
        waiting = False
        try:
            if len(telegrams) > 100:    # 100 * 250 bytes
                MyLogger.log(modulename,'ERROR','Input buffer is full.')
                return
            # append the TTN data to local FiFo buffer
            # print str(msg.topic)
            # print str(msg.payload)
            telegrams.append( {
                'topic': msg.topic,
                # payload is unpacked by TTN: make sure to add the unpack rules TTN
                'payload': str(msg.payload),
                })
        except:
            MyLogger.log(modulename,'ERROR Except','In message.')
    
    def on_subscribe(client, obj, MiD, granted_qos):
        global waiting, mid
        mid = MiD
        MyLogger.log(modulename,'DEBUG','mid: ' + str(mid) + ",qos:" + str(granted_qos))
    
    def on_log(client, obj, level, string):
        global PingTimeout, Conf, ErrorCnt
        if string.find('PINGREQ') >= 0:
            if not PingTimeout:
                PingTimeout = int(time())
            elif int(time())-PingTimeout > 10*60: # should receive pong in 10 minutes
                MyLogger.log(modulename,'ATTENT','Ping/pong timeout exceeded.')
                if ('fd' in Conf.keys()) and (Conf['fd'] != None):
                    Conf['fd'].disconnect()
                    waiting = False
                    Conf['registrated'] = False
                    del Conf['fd']
                    ErrorCnt += 1
                    PingTimeout = 0
        elif string.find('PINGRESP') >= 0:
            if int(time())-PingTimeout != 0:
                MyLogger.log(modulename,'DEBUG','Log: ping/pong time: %d secs' % (int(time())-PingTimeout))
            PingTimeout = 0
        else:
            MyLogger.log(modulename,'DEBUG','Log: %s...' % string[:17])

    def on_disconnect(client, obj, MiD):
        global waiting, mid, Conf
        waiting = False
        if 'fd' in Conf.keys():
            Conf['fd'] = None
        # mid = MiD
        # MyLogger.log(modulename,'DEBUG','Disconnect mid: ' + str(mid))
        raise IOError("MQTTsub: disconnected")

    def reConnect():
        global Conf
        if ('fd' in Conf.keys()) and (Conf['fd'] != None):
            # disconnect
            Conf['fd'].disconnect()
            Conf['fd'].loop_stop()
            Conf['fd'] = None
            sleep(2)
        try:
            Conf['fd']  = mqtt.Client(Conf['project']+str(os.getpid()))
            Conf['fd'].on_connect = on_connect
            Conf['fd'].on_disconnect = on_disconnect
            if ('user' in Conf.keys()) and Conf['user'] and ('password' in Conf.keys()) and Conf['password']:
                Conf['fd'].username_pw_set(username=Conf['user'],password=Conf['password'])
            Conf['fd'].connect(Conf['hostname'], Conf['port'], keepalive=60)
            #Conf['fd'].connect(Conf['hostname'], Conf['port'])
            Conf['fd'].on_subscribe = on_subscribe
            Conf['fd'].on_message = on_message
            Conf['fd'].loop_start()   # start thread
            Conf['fd'].subscribe(topic, qos=Conf['qos'])
            return True
        except:
            return False

    if ('file' in Conf.keys()) and Conf['file']:
        return ReadFromFile(Conf['file'])
    try:
        if (not 'fd' in Conf.keys()) or (Conf['fd'] == None):
            if not reConnect(): raise IOError
            sleep(1)

        tryAgain = time()
        timeout = tryAgain + Conf['timeout']
        waiting = True
        while waiting:
            if len(telegrams):
                waiting = False
                break
            if time() > timeout: # give up
                break
            if time() > (tryAgain + Conf['rate']):
                reConnect()
                tryAgain = time()
                MyLogger.log(modulename,'ATTENT','Try to reconnect with TTN MQTT broker')
            else: sleep(30)   # slow down
    except:
        MyLogger.log(modulename,'ERROR','Failure type: %s; value: %s. MQTT broker aborted.' % (sys.exc_info()[0],sys.exc_info()[1]) )
        Conf['input'] = False
        del Conf['fd']
        raise IOError("%s" % str(mid))
        return telegram
    if waiting:
        MyLogger.log(modulename,'ATTENT','Sending telegram to broker')
        raise IOError("%s" % str(mid))
        return telegram
    MyLogger.log(modulename,'DEBUG','Received telegram from broker, waiting = %s, message id: %s' % (str(waiting),str(mid)) )
    if len(telegrams):
        return telegrams.pop(0)
    return telegram

# mqttc = mosquitto.Mosquitto()
# # Assign event callbacks
# mqttc.on_message = on_message
# mqttc.on_connect = on_connect
# mqttc.on_publish = on_publish
# mqttc.on_subscribe = on_subscribe
# 
# Uncomment to enable mqtt debug messages
#mqttc.on_log = on_log

last_records = {}       # remember last record seen so far

# sensor module name is received via TTN record field 'type'
# maintain some logging
cached = {
    # 'applID/deviceID': {
    # 'unknown_fields': [] seen but not used fields
    # 'last_seen': unix timestamp secs
    # 'count': received records count
    # 'eui': LoRa EUI ID
    # 'sensors': list of sensor types (same as firmware/sensors) deprecated
    # 'firmware': {sensors,fields,id (classId)}
    # 'port%d': {packing, adjust}
    # 'ident': collected meta info
    # },
}
# kits alive from previous TTN connection
previous = []

# show current status of nodes seen so far
def SigUSR1handler(signum,frame):
    global modulename, cached
    for name in cached.keys():
        MyLogger.log(modulename,'INFO',"Status device %s EUI=%s: count: %d, last seen: %s, unknown fields: %s, sensors %s" % (name,cached[name]['eui'] if 'eui' in cached[name].keys() else 'unknown',cached[name]['count'],datetime.datetime.fromtimestamp(cached[name]['last_seen']).strftime("%Y-%m-%d %H:%M:%S"), ' '.join(cached[name]['unknown_fields']),', '.join(cached[name]['firmware']['sensors'].keys()) if 'sensors' in cached[name]['firmware'].keys() else 'not defined'))

# search record for first EUI and rssi value of the sensor/node
def Get_GtwID(msg):
    return None # do not handle gateway archiving
    if (not 'gateways' in msg.keys()) or (not type(msg['gateways']) is list):
        return None
    tfirst = 0 ; rssi = None ; eui = None ; location = []
    for one in msg['gateways']:
        if (not 'timestamp' in one.keys()) or (not 'gtw_id' in one.keys()) or (not 'rssi' in one.keys()):
            continue
        if not tfirst: tfirst = one['timestamp']
        if one['timestamp'] <= tfirst:
            tfirst = one['timestamp']
            rssi = one['rssi']
            gtw_id = one['gtw_id']
            for crd in ['latitude','longitude','altitude']:
                try: location.append(one[crd])
                except: location.append(None)
    if tfirst: return (gtw_id,rssi,location)
    return None

# ident cache
# to do: add memory use watchdog
dirtyIdentCache = False
IdentCache = {}
def newIdent( sensors ):
    global IdentCache, dirtyIdentCache, Conf
    sensors.sort()
    theKey = '/'.join(sensors)
    if dirtyIdentCache:
        IdentCache = {} ; dirtyIdentCache = False
    if theKey in IdentCache.keys(): return IdentCache[theKey].copy()
    ident = {
        'project': '', 'sensors': '',
        'description': 'hw: '+','.join(sensors),
        'fields': ['time', ], 'types': ['time'], 'units': ['s',],
        'calibrations': [None,],
        }
    for sensor in sensors:
        product  = ProductKnown(sensor)
        for j in range(0,len(product['fields'])):
            # ident['sensors'] = ','.join([ident['sensors'],'%s(%s)' % (Conf['nodes'][sensor]['fields'][j],Conf['nodes'][sensor]['units'][j]])
            ident['types'].append(sensor.lower())
            for t in ['fields','units','calibrations']:
                try:
                    ident[t].append(product[t][j])
                except:
                    ident[t].append(None)
    IdentCache[theKey] = ident
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
            for i in range(0,len(sensor['fields'])):
                if t == 'types': ident[t].append(module.lower())
                else:
                    if (type(sensor[t]) is list) and (i < len(sensor[t])):
                        ident[t].append(sensor[t][i])
                    else: ident[t].append(None)
    except Exception as e:
        print("addInfo error %s: on module %s, key %s, index %d" % (e,module,t,i))
        return False
    return True

def email_message(message, you, debug=False):
    global Conf
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
    msg['Subject'] = 'MySense: TTN data collector service notice'
    msg['From'] = Conf['from']
    msg['To'] = ','.join(you)
    if debug:
        print("Email (debug/not sent via %s): %s" % (Conf['SMTP'],str(msg)))
        return True
    
    # Send the message via our own SMTP server, but don't include the
    # envelope header.
    try:
        s = smtplib.SMTP(Conf['SMTP'])
        s.sendmail(Conf['from'], you, msg.as_string())
        s.quit()
    except Exception as e:
        MyLogger.log(modulename,'ERROR',"Email notice failure: %s" % str(e))
        print("Email notice failure with: %s" % str(msg)) # comment this out
        return False
    return True

def slack_message(message, slackURL, debug=False):
    rts = True
    if not type(slackURL) is list: slackURL = slackURL.split(',')
    for one in slackURL:
      one = 'https://' + one.strip()
      if debug:
        print('Slack: notice to %s (debug/not sent via curl): %s' % (one, message))
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
        print("Slack notice failure with: %s" % str(curl)) # comment this out
        rts = False
        continue
      p.wait()
    return rts

def sendNotice(message,myID=None,debug=True):
    global Conf, cached
    try:
        if not len(Conf['notice'][0]): return True
    except: return True
    nodeNotice = []
    if myID:
        try:
            nodeNotice = [[myID.split('/')[1]] + cached[myID]['notice'].split(',')]
        except: pass
    sendTo = { 'email': [], 'slack': [] }
    for item in Conf['notice']+nodeNotice:
        try:
            if (type(item[0]) is str) or (type(item[0]) is unicode):
                item[0] = re.compile(item[0],re.I)
            if not item[0].match(myID.split('/')[1]): continue
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
        print("Send Notice to: %s" % str(sendTo))
        print("     Message  : %s" % str(message))
    else:
        if len(sendTo['email']): email_message(message,sendTo['email'],debug=debug)
        if len(sendTo['slack']): slack_message(message,sendTo['slack'],debug=debug)
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

def cleanupCache(saveID,debug=False): # delete dead kits from cache
    global cached, previous
    now = time(); items = []
    for item in cached.keys():
      # if debug:
      #   diff = int(now - cached[item]['last_seen'])
      #   print("Kit %s:\t interval %dm%ds,\tseen %dh:%dm:%ds ago." % (item.split('/')[1],cached[item]['interval']/60,cached[item]['interval']%60,diff/3600,(diff%3600)/60,(diff%(3600*60))%60))
      if saveID == item: continue
      try:
        if (cached[item]['last_seen'] < (now-60*60*2)) or (cached[item]['last_seen'] <= AllowInterval(cached[item]['interval'],now)):
            items.append(item)
      except: pass
    if len(items):
      if len(items) < 3:   #  len(cached)-1
        for item in items:
          MyLogger.log(modulename,'ATTENT',"Kit %s not seen longer as %d minutes." % (item,(now-cached[item]['last_seen'])/60))
          try:
              sendNotice("Kit %s not seen longer as %d minutes.\nKit seems to be disconnected.\nLast time seen: %s." % (item,(now-cached[item]['last_seen'])/60,datetime.datetime.fromtimestamp(cached[item]['last_seen']).strftime("%Y-%m-%d %H:%M")),myID=item,debug=debug)
          except Exception as e:
              MyLogger.log(modulename,'ERROR',"Failed to send notice: %s" % str(e))
          del cached[item]
      else:
        MyLogger.log(modulename,'ATTENT',"Seems TTN server is down for a long period at %s" % datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M"))
        sendNotice("Seems TTN server is down for a long period at %s (kits with no measurements: %s)." % (datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M"),', '.join(items[:3]) + '...' if len(items) > 3 else ''), myID='all/event', debug=debug)
        for item in items:
          del cached[item]
          if not item in previous: previous.append(item)

# convert MQTT structure to MySense ident,value structure
def convert2MySense( data, **sensor):
    global Conf, cached, previous, dirtyCaches, startedCache, debug
    def recordTranslate(arecord):
        new = {}
        for item in arecord.items():
            if item[1] == None: confinue
            transltd = translate(item[0],ext=False)
            if item[1] or (transltd in ['temp','wr','ws']):
                new[transltd] = item[1]
        return new

    device = data['topic'][2]
    values = {} # init record with measurements
    record = {}
    timing = None
    for item in ['counter','payload_raw','port',]:
        if item in data['payload'].keys():
            record[item] = data['payload'][item]
        else: record[item] = None       # should be an error: return {}

    myID = data['topic'][0]+'/'+data['topic'][2] # to do: should use eui ID
    if dirtyCaches:
        cached = {} ; dirtyCaches = False; startedCache = noticeStarted+time()
    else: cleanupCache(myID,debug=debug)
    if not myID in cached.keys():       # caching
        # TO DO: use DB for this as well
        if len(cached) >= 100: # FiFo to avoid exhaustion, maydisrupt chack on dead kits
            oldest = time() ; oldestKey = None
            for key in cached.keys():
                if cached[key]['last_seen'] <= oldest:
                    oldest = cached[key]['last_seen']
                    oldestKey = key
            del cached[oldestKey]
        cached[myID] = {
            'unknown_fields': [],
            'count': 0, 'interval': 15*60,
            'firmware': getFirmware(data['topic'][0],data['topic'][2],record['port']),
            'sensors': [],
            'identified': False}
        try: cached[myID]['notice'] = Conf['nodes'][data['topic'][2]]['notice']
        except: pass
        cached[myID]['port%d' % record['port']] = {}
        for key in ['packing','adjust']:
            try:
                cached[myID]['port%d' % record['port']][key] = cached[myID]['firmware'][key]
            except: pass
        if 'sensors' in cached[myID]['firmware'].keys():
            if type(cached[myID]['firmware']['sensors']) is unicode:
                cached[myID]['firmware']['sensors'] = str(cached[myID]['firmware']['sensors'])
            if type(cached[myID]['firmware']['sensors']) is str:
                cached[myID]['firmware']['sensors'] = cached[myID]['firmware']['sensors'].upper()
                cached[myID]['firmware']['sensors'] = cached[myID]['firmware']['sensors'].split(',')
    if not 'port%d' % record['port'] in cached[myID].keys():
        try:
            firmware = getFirmware(data['topic'][0],data['topic'][2],record['port'])
            cached[myID]['port%d' % record['port']] = {}
            for key in ['packing','adjust']:
                try:
                    cached[myID]['port%d' % record['port']][key] = firmware[key]
                except: pass
            for key in firmware['sensors']:
                if not key in cached[myID]['firmware']['sensors']:
                    cached[myID]['firmware']['sensors'].append(key)
        except: pass
    now = time()
    if cached[myID]['count']:
        #cached[myID]['interval'] = max(cached[myID]['interval'],now - cached[myID]['last_seen'])
        cached[myID]['interval'] = (cached[myID]['interval']*cached[myID]['count']+(max(now - cached[myID]['last_seen'],5*60)))/(cached[myID]['count']+1)
    cached[myID]['last_seen'] = now ; cached[myID]['count'] += 1
    if len(cached[myID]['firmware']['sensors']) <= 0: # unregistrated sensor kit
        if cached[myID]['count'] <= 1:
            MyLogger.log(modulename,'ATTENT','Unknown (new) kit: %s' % myID)
            # may need to send a notice
            sendNotice('Unknown (new?) kit found: %s' % myID,myID=myID,debug=debug)
        raise ValueError('unknown kit %s' % myID)  # skip this record
    if (cached[myID]['count'] == 1) and (now > startedCache): # notice this clearly starting new kit
        if not myID in previous:
            MyLogger.log(modulename,'ATTENT','Kit %s is (re)started.' % myID)
            sendNotice('Kit %s is (re)started at time: %s' % (myID,datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M")),myID=myID,debug=debug)
        else:
            previous.remove(myID)

    gtwID = None  # gateway id

    # make sure pay_load_fields have: keys types (sensors) and fields
    # this needs some rework! Too many fields and types!
    # collect sensor product names, cache them,
    # and check if (translated) fields are known 
    if ("payload_fields" in data['payload'].keys()) \
        and len(data['payload']['payload_fields']):
        data['payload']['payload_fields'] = recordTranslate(data['payload']['payload_fields'])
        if 'type' in data['payload']['payload_fields'].keys(): # deprecated
            if not data['payload']['payload_fields']['type'].upper() in cached[myID]['sensors']:
                cached[myID]['sensors'].append(data['payload']['payload_fields']['type'].upper())
            del data['payload']['payload_fields']['type']
        for skip in ['TTNversion']:
            # known to skip (To Do check it)
            if skip in data['payload']['payload_fields'].keys():
                del data['payload']['payload_fields'][skip]
        if 'sensors' in data['payload']['payload_fields'].keys():
            if not isinstance(data['payload']['payload_fields']['sensors'], list):
                data['payload']['payload_fields']['sensors'] = data['payload']['payload_fields']['sensors'].split(',')
            for sensor in data['payload']['payload_fields']['sensors']:
                if not sensor.upper() in cached[myID]['sensors']:
                    cached[myID]['sensors'].append(sensor.upper())
            del data['payload']['payload_fields']['sensors']
        if ('time' in data['payload']['payload_fields'].keys()) and (data['payload']['payload_fields']['time'] > 946681200): # 1 jan 2000
            record['time'] = values['time'] = data['payload']['payload_fields']['time']
            del data['payload']['payload_fields']['time']
            timing = values['time']
        # cached['sensors'] is now up to date
        candidates = dict()
        for afld in data['payload']['payload_fields'].keys():
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
                del data['payload']['payload_fields'][afld]
            elif afld != field:
                data['payload']['payload_fields'][field] = data['payload']['payload_fields'][sense]
                del data['payload']['payload_fields'][afld]
            # data['payload']['payload_fields'] =  checkFields(data['payload']['payload_fields'])
        fields = list(set(data['payload']['payload_fields'].keys())-set(['fields','sensors']))
        candidates = searchSensors(fields,candidates)
        if candidates:
            data['payload']['payload_fields']['sensors'] = candidates
        if fields:
            data['payload']['payload_fields']['fields'] = fields
    elif ('payload_raw' in data['payload'].keys()) \
        and len(data['payload']['payload_raw']):
            if not 'firmware' in cached[myID]:  # try default
                firmware = getFirmware(data['topic'][0],data['topic'][2],data['payload']['port'])
                if not len(firmware):
                    firmware = getFirmware('201802215971az','lopyprototype20180000',2)
                    print("Unable to find firmware for device %s using LoPyNode" % device)
            else:
                firmware = cached[myID]['firmware']
            data['payload']['payload_fields'] = payload2fields(data['payload']['payload_raw'],firmware,data['payload']['port'])
    else: return {}

    # side effect payload2fields: key sensors
    for item in ['sensors','fields']:
      if item in data['payload']['payload_fields'].keys():
        if not item in cached[myID].keys():
            cached[myID][item] = []
        cached[myID][item] = list(set(cached[myID][item]+data['payload']['payload_fields'][item]))
        del data['payload']['payload_fields'][item]
    if not len(data['payload']['payload_fields']): return {}    # nothing to do

    # we have now payload_fields with known/guessed fields of known/guessed sensors
    # TO DO: use 'defined' key in cache to overwrite guessed sensors
    ident = newIdent( cached[myID]['sensors'] if 'sensors' in cached[myID].keys() else cached[myID]['firmware']['sensors'] )
    ident['description'] += ';MQTT AppID=' + data['topic'][0] + ' MQTT DeviceID=' + data['topic'][2]
    try:
        if Conf['project'] == 'XYZ': raise ValueError
        if (data['topic'][2] in Conf['nodes'].keys()) and ('project' in Conf['nodes'][data['topic'][2]].keys()):
            ident['project'] = Conf['nodes'][data['topic'][2]]['project']
        else:
            ident['project'] = Conf['project']
    except: ident['project'] = data['topic'][0]
    if 'metadata' in data['payload'].keys():
        gtwID = Get_GtwID(data['payload']['metadata'])    # get signal strength of end node
    # see if we have first LoRa signal strengthy
    if gtwID != None:
        ident['description'] += ' EUI='+gtwID[0]
        if (not 'eui' in cached[myID].keys()) or (cached[myID]['eui'] != gtwID[0]):
            cached[myID]['eui'] = gtwID[0]
        values['rssi'] = record['rssi'] = gtwID[1] # pickup signal strength node
        if not 'rssi' in ident['fields']:
            ident['fields'].append('rssi')
            ident['units'].append('dB')
            ident['calibrations'].append(None)
            try: ident['types'].append(cached[myID]['firmware']['id'])
            except: ident['types'].append('')
        if gtwID[2][0]:   # location gateway for this node
            values['gwlocation'] = record['gwlocation'] = ','.join([str(a) for a in gtwID[2]])
            ident['fields'].append('gwlocation')
            ident['units'].append('GPS')
            ident['calibrations'].append(None)
            try: ident['types'].append(cached[myID]['firmware']['id'])
            except: ident['types'].append('')
        #  to do: add nearby gateway location

    for item in data['payload']['payload_fields'].keys():
        values[item] = data['payload']['payload_fields'][item]
        try:
            # To Do: add calibrate between nodes/nodes within one sensor product
            # calibrate between different sensor manufacturers
            for calArray in ['calibrations',]:
                values[item] = tryCalibrate(item,values[item],ident['fields'],ident[calArray])
        except:
            pass

    # see if FPORT defines something. This may change in the future
    # FPORT 3 denotes meta data like sensor types, GPS
    # TTN may use port numbers to define events
    gotMetaInfo = False
    if record['port'] in [3]: # event or meta info
        if len(record['payload_raw']) <= 1:
            values['event'] = cached[myID]['ports%d' % record['port']]
            if not 'event' in ident['fields']:
                ident['fields'].append('event')
                ident['units'].append('nr')
                ident['types'].append('LoRa port')
                ident['calibrations'].append(None)
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
        else: # ident info in values
            #record = values.copy()
            gotMetaInfo = True
            addInfo(None,ident,clear=True)
            location = []; mod = []
            for t in ['longitude','latitude','altitude']:
                if t in values.keys():
                    location.append(str(values[t]))
                    del values[t]
            if len(location):
                ident['geolocation'] = ','.join(location)
            for t in ['meteo','dust','gps']:
                if (t in values.keys()) and values[t]:
                    fnd = False
                    if t == 'gps': values[t] = 'NEO'
                    else: values[t] = str(values[t])
                    if values[t]:
                        for sensor in Conf['sensors']:
                            if sensor['type'] == values[t]:
                                fnd = True; break
                        if fnd:
                            mod.append(str(values[t]))
                            addInfo(str(values[t]),ident)
                        else:
                            print("Error in sensors conf: %s not found" % values[t])
                    del values[t]
            if len(mod):
                mod = 'hw: ' + ','.join(mod)
                delDecrFld(ident,'hw:')
                ident['description'] += ';' + mod
            #for t in ident.keys():
            #    if not t in ['project','description']:
            #        del ident[t]
            if ('time' in values.keys()) and (values['time'] > 946681200): # 1 jan 2000
                values = { 'time': values['time'] }
                timing = values['time']
            else: values = {}
            record = values.copy()
    # provide the device with a static serial number. Needed for Luftdaten.info
    if (data['topic'][2] in Conf['nodes'].keys()) and ('serial' in Conf['nodes'][data['topic'][2]].keys()) and Conf['nodes'][data['topic'][2]]['serial']:
        # serial is externaly defined
        ident['serial'] = Conf['nodes'][data['topic'][2]]['serial'][-12:]
    else:
        # create one
        ident['serial'] = hex(hash(data['topic'][0] + '/' + data['topic'][2])&0xFFFFFFFFFF)[-12:]
        if not data['topic'][2] in Conf['nodes'].keys(): Conf['nodes'][data['topic'][2]] = {}
        Conf['nodes'][data['topic'][2]]['serial'] = ident['serial']
        MyLogger.log(modulename,'ATTENT','Created serial number for %s: %s.' % (data['topic'][2],ident['serial']))
    # try to get geolocation
    geolocation = []
    if "metadata" in data['payload'].keys():
        for item in ['latitude','longitude','altitude']:
            if item in data['payload']['metadata'].keys():
                geolocation.append(str(data['payload']["metadata"][item]))
            else:
                geolocation.append('?')
                break
        geolocation = ','.join(geolocation)
        for item in data['payload']['metadata'].keys():
            # meta time field is not time of measurement but from system time gateway
            # this time can be unreliable
            if item in ['time',]:
                # w're using the gateway timestamp
                if item == 'time':      # convert iso timestamp to UNIX timestamp
                    # time is time() minus 3600 secs with python V2 !! ?
                    timing = int(dp.parse(data['payload']['metadata']['time']).strftime("%s"))
                    if sys.version_info[0] < 3: # ?!???
                        timing += 3600
                        # if localtime().tm_isdst: timing += 3600
                        # else: timing -= 3600
                else:
                    values[item] = data['payload']['metadata'][item]
    if (len(geolocation) <= 10):
        geolocation = None
    if geolocation and (not 'geolocation' in ident.keys()):
        ident['geolocation'] = geolocation    # might note we did ident once
        record['geolocation'] = geolocation
    if ('time' in values.keys()) and (values['time'] < 946681200): # 1 jan 2000 00:00
        del values['time']      # controller not synced with real time
    if not 'time' in values.keys():
        if timing: values['time'] = record['time'] = timing
        else: values['time'] = record['time'] = int(time()) # needs correction

    # maintain info last seen of this device
    if 'geolocation' in ident.keys():
        if ident['serial'] in last_records.keys():
            if 'geolocation' in last_records[ident['serial']].keys():
                # compare geo locations
                if GPSdistance(last_records[ident['serial']]['geolocation'].split(','),ident['geolocation'].split(',')) < 100: # less as 100 meters
                    # sensorkit changed location
                    values['geolocation'] = ident['geolocation']
                    # keep first location in ident
                    ident['geolocation'] = last_records[ident['serial']]['geolocation']
        else:
            record['geolocation'] = ident['geolocation']
        if ('latitude' in values.keys()) and ('longitude' in values.keys()):
            if GPSdistance(ident['geolocation'].split(','),(values['latitude'],values['longitude'])) < 100: # should be > 100 meter from std location
                del values['latitude']; del values['longitude']
                if 'altitude' in values.keys(): del values['altitude']
                
    last_records[ident['serial']] = record

    ident = updateIdent( data['topic'][0], data['topic'][2], ident, gotMetaInfo)
    if not 'active' in ident.keys(): # allowed, but not administrated, handle as not active
        ident['active'] = False
        if cached[myID]['count'] <= 1:
           MyLogger.log(modulename,'ATTENT','Record from not activated kit: %s_%s' % (ident['project'],ident['serial']))
           MyLogger.log(modulename,'DEBUG','Record from not activated kit: ident: %s, values: %s' % (str(ident),str(values)))
           sendNotice('Not administrated (in test?) kit found: %s, serial: %s' % (myID,ident['serial']),myID=myID,debug=debug)
    # assert len(values) > 0, len(ident) > 6
    # sendNotice('Got record ident: %s, data: %s' % (str(ident),str(values)), myID=myID, debug=debug)
    if debug:
        print("Got data from %s at %s, interval %dm%ds" % (myID.split('/')[1],datetime.datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M"),cached[myID]['interval']/60,cached[myID]['interval']%60))
    return { 'ident': ident, 'data': values, 'myID': myID }

def getdata():
    global Conf, ErrorCnt
    if not Conf['input']: return True
    if ErrorCnt:
        if ErrorCnt > 20:
            Conf['registrated'] = None
            if ('fd' in Conf.keys()) and (Conf['fd'] != None):
                try:
                    Conf['fd'].disconnect()
                    Conf['fd'] = None
                except:
                    pass
            sleep((ErrorCnt-20)*60)
        else:
            sleep(ErrorCnt)
    
    # input from file or from MQTT LoRa TTN broker
    if not 'registrated' in Conf.keys(): Conf['registrated'] = None
    if not Conf['registrated']:
        GetAdminDevicesInfo()
        if (not 'file' in Conf.keys()) or (not Conf['file']):
            if (not 'registrated' in Conf.keys()) or (Conf['registrated'] == None):
                if 'registrated' in Conf.keys():
                    MyLogger.log(modulename,'ATTENT','Try to reconnect to broker.')
                if (not 'AppId' in Conf.keys()) or (not len(Conf['AppId'])):
                    Conf['AppId'] = '+'
                if (not 'DevAddr' in Conf.keys()) or (not len(Conf['DevAddr'])):
                    Conf['DevAddr'] = '+'
                if (not 'topic' in Conf.keys()) or (Conf['topic'] == None):
                    Conf['topic'] = 'devices'
                for key in [['user','devices'],['password','account'],['hostname','hostname'],['port','port'],]:
                    if key[1] in Conf['LoRa'].keys():
                        Conf[key[0]] = Conf['LoRa'][key[1]]
                    if (not key[0] in Conf.keys()) or (Conf[key[0]] == None):
                        Conf['input'] = False
                        MyLogger.log(modulename,'FATAL','Missing login %s credentials.' % key[0])
        if 'LoRa' in Conf.keys(): del Conf['LoRa']
        Conf['registrated'] = True

    msg = None
    try:
        msg = PubOrSub("%s/%s/%s/up" % (Conf['AppId'],Conf['topic'],Conf['DevAddr']), None)
        if msg == None:
            ErrorCnt += 1
            return {}
        ErrorCnt = 0
        msg['topic'] = msg['topic'].split('/')
        msg['payload'] = json.loads(msg['payload'])
    except IOError as e:
        if ErrorCnt > 40:
            MyLogger.log(modulename,'FATAL','Subscription failed Mid: %s. Aborted.' % e)
        ErrorCnt += 1
        MyLogger.log(modulename,'WARNING','Subscription is failing Mid: %s. Slowing down.' % e)
    if (len(msg['topic']) < 3) or (msg['topic'][1] != Conf['topic']) or (not type(msg['payload']) is dict) or (not 'dev_id' in msg['payload'].keys()):
        MyLogger.log(modulename,'ERROR','Received an unknown record %s' % str(msg))
        sleep(0.1)
        return getdata()
    if ('app_id' in msg['payload']) and (msg['topic'][0] != msg['payload']['app_id']):
        msg['topic'][0] = msg['payload']['app_id']
    if ('dev_id' in msg['payload']) and (msg['topic'][2] != msg['payload']['dev_id']):
        msg['topic'][2] = msg['payload']['dev_id']
    msg['AppId'] = msg['topic'][0]
    msg['DevAddr'] = msg['topic'][2]
    # recursive getdata() call may lead to stack exhaustion
    # check the pay load
    if not type(msg['payload']) is dict:
        sleep(0.1)
        return getdata()
    # TO DO: check DevAddr to api key (mqtt broker checks user with AppId/DevAddr)
    # convert fields and values to MySense ident/data record
    return convert2MySense(msg)

# send kill -USR1 <process id> to dump status overview
signal.signal(signal.SIGUSR1, SigUSR1handler)
signal.signal(signal.SIGUSR2, SigUSR2handler)

# MAIN part of Broker for VW 2017

# next only for standalone testing
if __name__ == '__main__':
    #Conf['adminfile'] = 'LoPy-Admin.conf.json' # meta identy data for sensor kits
    Conf['all'] = False  # do not skip unknown sensors
    #Conf['slack'] = 'https://hooks.slack.com/services/TGA112345123451234512345123451234512345ylWl0'
    Conf['from'] = 'Notice TTN data collector <owner@some-address.somewhere>'
    Conf['SMTP'] = 'my.host.nowhere'

    # one should use the MySense main script in stead of next statements
    Conf['input'] = True
    # Conf['file'] = 'test_dev11.json'    # read from file iso TTN MQTT server
    # 'NOTSET','DEBUG','INFO','ATTENT','WARNING','ERROR','CRITICAL','FATAL'
    MyLogger.Conf['level'] = 'INFO'     # log from and above 10 * index nr
    #MyLogger.Conf['level'] = 'DEBUG'    # log from and above 10 * index nr
    MyLogger.Conf['file'] = '/dev/stderr'
    sys.stderr.write("Starting up %s, logging level %s\n" % (modulename,MyLogger.Conf['level']))
    if 'adminfile' in Conf.keys():
        sys.stderr.write("Using admin file %s\n" % Conf['adminfile'])
    else:
        sys.stderr.write("No admin file defined, use internal definitions.\n")
    sys.stderr.write("Collect mode for nodes: %s\n" % ('all' if Conf['all'] else 'only administered and activated'))
    # Conf['debug'] = True  # print output channel actions
    for arg in sys.argv[1:]:        # allow: cmd file=abc user=xyz password=acacadabra
        indx = arg.find('=')
        if indx > 0:
            if arg[indx+1:].lower() == 'false': Conf[arg[:indx].lower()] = False
            elif arg[indx+1:].lower() == 'true': Conf[arg[:indx].lower()] = True
            elif arg[indx+1:].isdigit(): Conf[arg[:indx].lower()] = int(arg[indx+1:])
            else: Conf[arg[:indx].lower()] = arg[indx+1:]
        elif arg.lower() == 'debug': debug = True

    error_cnt = 0
    OutputChannels = [
        {   'name': 'Console', 'script': 'MyCONSOLE', 'module': None,
            'Conf': {
                'output': True,
            }
        },
        {   'name': 'MySQL DB', 'script': 'MyDB', 'module': None,
            'Conf': {
                'output': True,
                # use credentials from environment
                'hostname': None, 'database': 'luchtmetingen',
                'user': None, 'password': None,
            }
        },
        {   'name': 'Luftdaten data push', 'script': 'MyLUFTDATEN', 'module': None,
            'Conf': {
                'output': True,
                'id_prefix': "TTNMySense-", # prefix ID prepended to serial number of module
                'luftdaten': 'https://api.luftdaten.info/v1/push-sensor-data/', # api end point
                'madavi': 'https://api-rrd.madavi.de/data.php', # madavi.de end point
                # expression to identify serials to be subjected to be posted
                'serials': '([0-9a-z]{8,12})', # pmsensor[1 .. 11] from pmsensors
                'projects': '(XYZ|UTV)',  # expression to identify projects to be posted
                'active': False,        # output to luftdaten is also activated
                # 'debug' : True,        # show what is sent and POST status
            }
        },
        ]

    # input from file or from MQTT LoRa TTN broker
    if not 'registrated' in Conf.keys(): Conf['registrated'] = None
    if not Conf['registrated']:
        GetAdminDevicesInfo()
        if (not 'file' in Conf.keys()) or (not Conf['file']):
            if (not 'registrated' in Conf.keys()) or (Conf['registrated'] == None):
                if 'registrated' in Conf.keys():
                    MyLogger.log(modulename,'ATTENT','Try to reconnect to broker.')
                if (not 'AppId' in Conf.keys()) or (not len(Conf['AppId'])):
                    Conf['AppId'] = '+'
                if (not 'DevAddr' in Conf.keys()) or (not len(Conf['DevAddr'])):
                    Conf['DevAddr'] = '+'
                if (not 'topic' in Conf.keys()) or (Conf['topic'] == None):
                    Conf['topic'] = 'devices'
                for key in [['user','devices'],['password','account'],['hostname','hostname'],['port','port'],]:
                    if key[1] in Conf['LoRa'].keys():
                        Conf[key[0]] = Conf['LoRa'][key[1]]
                    if (not key[0] in Conf.keys()) or (Conf[key[0]] == None):
                        Conf['input'] = False
                        MyLogger.log(modulename,'FATAL','Missing login %s credentials.' % key[0])
        if 'LoRa' in Conf.keys(): del Conf['LoRa']
        Conf['registrated'] = True

    import os.path
    # switch output to Luftdaten off if input data is read from file
    if ('file' in Conf.keys()) and os.path.isfile(Conf['file']):
        for indx in OutputChannels:
            if 'luftdaten' in indx['Conf'].keys(): indx['Conf']['output'] = False
        sendNotice('Import from backup file %s' % Conf['file'],myID='all/event',debug=debug)
    else:
        sendNotice('Automatic (re)start TTN MQTT server data collector service on server %s' % socket.getfqdn(),myID='all/event',debug=debug)
    try:
        for indx in range(0,len(OutputChannels)):
            MyLogger.log(modulename,'INFO','Loaded output channel %s: output is %s' % (OutputChannels[indx]['name'], 'enabled' if OutputChannels[indx]['Conf']['output'] else 'DISabled'))
            if not OutputChannels[indx]['Conf']['output']: continue
            if (OutputChannels[indx]['script'] == 'MyLUFTDATEN') and ('file' in Conf.keys()) and Conf['file']:
                # do not output to Luftdaten as timestamp is wrong
                OutputChannels[indx]['Conf']['ouput'] = False
            try:
                OutputChannels[indx]['module'] = __import__(OutputChannels[indx]['script'])
            except:
                MyLogger.log(modulename,'FATAL','Unable to load module %s' % OutputChannels[indx]['script'])
            for item in OutputChannels[indx]['Conf'].keys():
                OutputChannels[indx]['module'].Conf[item] = OutputChannels[indx]['Conf'][item]
                OutputChannels[indx]['errors'] = 0
    except ImportError as e:
        MyLogger.log(modulename,'ERROR','One of the import modules not found: %s' % e)
    net = { 'module': True, 'connected': True }

# nodes
    # configure MySQL luchtmetingen DB access
    while 1:
        if error_cnt > 20:
            MyLogger.log(modulename,'FATAL','To many input errors. Stopped broker')
            sendNotice('Too many TTN MQTT server input errors. Try to restart the data collecting server %s' % socket.getfqdn(),myID='all/event',debug=debug)
            exit(1)
        try:
            record = getdata()
        except ValueError as e:
            err = str(e)
            if err.find(';Event'):
                err = str(err).split(';')
                while len(err) < 3: err.append('')
                sendNotice("Sensor kit %s raised %s with %s" % (err[0],str(err[1]),str(err[2])),myID=err[0])
                MyLogger.log(modulename,'ATTENT',"Sensor kit %s raised %s with %s" % (err[0],str(err[1]),str(err[2])))
            elif err.find('unknown') >= 0:
                try: err = str(err).split('/')[1]
                except: pass
                MyLogger.log(modulename,'INFO','Skip data from unknown kit: %s at time %s' % (err,datetime.datetime.fromtimestamp(record['data']['time']).strftime("%Y-%m-%d %H:%M")))
            else:
                MyLogger.log(modulename,'INFO','Get get record error: %s (skipped)' % err)
            continue
        except Exception as e:
            print(traceback.format_exc())
            MyLogger.log(modulename,'INFO','Get data failed with %s' % e)
            print("FAILED record: ", record)
            continue
        if (not dict(record)) or (len(record) < 2):
            MyLogger.log(modulename,'ATTENT','Data failure from LoRaWan data concentrator')
            error_cnt += 1
            continue
        cnt = 0
        if 'description' in record['ident'].keys():
            MyLogger.log(modulename,'DEBUG','%s Got data from %s' % (datetime.datetime.fromtimestamp(record['data']['time']).strftime("%Y-%m-%d %H:%M"),record['ident']['description']))
        else:
            MyLogger.log(modulename,'DEBUG','%s Got data (no description)' % datetime.datetime.fromtimestamp(record['data']['time']).strftime("%Y-%m-%d %H:%M"))
        for indx in range(0,len(OutputChannels)):
            if not OutputChannels[indx]['Conf']['output']: continue
            PublishMe = True
            if debug: PublishMe = False; cnt += 1
            if not record['ident']['active']:
              if OutputChannels[indx]['name'] != 'Console':
                PublishMe = False ; cnt += 1
              else:
                print("Kit MQTT %s with serial %s not activated. Skip other output." % (record['myID'],record['ident']['serial']))
            if OutputChannels[indx]['module'] and OutputChannels[indx]['Conf']['output']:
              if not 'active' in record['ident'].keys():
                record['ident']['active'] = False
              if PublishMe:
                try:
                    OutputChannels[indx]['module'].publish(
                        ident = record['ident'],
                        data = record['data'],
                        internet = net
                    )
                    OutputChannels[indx]['errors'] = 0
                    cnt += 1
                    if ('debug' in Conf.keys()) and Conf['debug']:
                        MyLogger.log(modulename,'INFO','Sent record to outputchannel %s' % OutputChannels[indx]['name'])
                except:
                    MyLogger.log(modulename,'ERROR','sending record to %s' % OutputChannels[indx]['name'])
                    OutputChannels[indx]['errors'] += 1
            if OutputChannels[indx]['errors'] > 20:
                OutputChannels[indx]['module']['Conf']['output'] = False
                MyLogger.log(modulename,'ERROR','Too many errors. Loaded output channel %s: output is DISabled' % OutputChannels[indx]['name'])
                sendNotice('TTN MQTT Server %s: too many errors. Output channel %s: output is DISabled' % (socket.getfqdn(),OutputChannels[indx]['name']),myID='all/event',debug=debug)
        if not cnt:
            MyLogger.log(modulename,'FATAL','No output channel available. Exiting')
            exit(1)
