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

# $Id: MyDatacollector.py,v 4.65 2021/12/08 16:48:30 teus Exp teus $

# Data collector (MQTT data abckup, MQTT and other measurement data resources)
# and data forwarder to monitor operations, notify events, console output,
# MySQL DB archive, forward measurements to  dataportals as e.g. Sensors.Community, etc.

# MySQL DB if nodes  (measurement kits) meta info is loaded, updated on the fly.
# The datacollector will use an internal Measurement Exchange Format (draft).

# module mqtt: git clone https://github.com/eclipse/paho.mqtt.python.git
# cd paho.mqtt.python ; python setup.py install
# broker server: Debian: apt-get install mqtt

__HELP__ = """ Download measurements from a server (for now TTN MQTT server):
    Data acquisition input is multithreaded.
    Subscribe to measurements from a Mosquitto Broker server(s) (eg TTN LoRa server)
    and
    Publish measurements as client to Sensors.Community and MySQL database
    Monitor traffic and output channels.
    One may need to change payload and TTN record format in MyLoRaCode.py!
    MySense meta measurement kits data is read from MySQL database table Sensors.
    Meta data is kept in caches via MyMQTTclient KitCache class,
    which elements are sync'd on the fly and reset every 12 hours.
    Output channel activation per kit is read from MySQL table TTNtable:
    valid, sensors.community via luftdaten, luftdatenID.
    The script is designed to run autonoom and send notices on discovered events.
    The script can run in different modi (activation via arguments):
    data forwarder, monitoring forwarding, measurement kit info load into air quality DB,
    or with different combinations.
    The configuration is read from a json formatted initialisation file.

    Configuration:
    Script can be used to read meta kit information from json file and export
    it to MySql DB meta kit data tables Sensors and TTNtable.
    Output channels defined: database, monitor, community (Sensors.Community, Luftdaten), ...
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
    Every period of time the data collector will check data base cache meta entry
    for changed like other output channel activations.
    On DB kit meta info changes of measurement kit location this change will
    be updated in the meta data (Sensors DB table).

    LoRa payload decoding:
    LoRa decode is done via json decoding at MQTT level as well on subscribe
    level (see MyMQTTclient.py) per port (indicating payload decoding) type.
    A data exchange format (draft) is used as intermediate data format between modules.

    Configuration from CLI level:
    Various output channels can be reconfigured as eg:

    Community:output=true (default) community:debug=true (dflt false)
    community:projects=(SAN|HadM|RIVM|KIP) (default forwarding data for these projects)
    monitor:output=false (default)
    monitor:projects=(test|SAN) (dflt: '([A-Za-z]+)')
    monitor:serials=(A-Fa-f0-9]+) (default) only output project_serial for this channel
    console:output=false (default)
    console:projects=([A-Za-z]+) (default)
    console:serials=(A-Fa-f0-9]+) (default)

    database:output=true (default)
    database:debug=false (default)

    notices:output=true (default)

    logger:print=true (default) print in colored format.
    file=RestoredDataFile only restore data from this dump file.
    debug=true (default false) switch debugging on.
    calibrate=SDS011,BME280 Calibrate values to this sensor type if defined in DB.
    Or database acces credential settings: host=xyz, user=name, password=acacadabra
    or use command CLI environment settings: DBHOST, DBUSER, DBPASS, or DB.

    See Conf dict declaration for more details.
"""

__modulename__='$RCSfile: MyDatacollector.py,v $'[10:-4]
__version__ = "1." + "$Revision: 4.65 $"[11:-2]
import inspect
def WHERE(fie=False):
    global __modulename__, __version__
    if fie:
      try:
        return "%s V%s/%s" % (__modulename__ ,__version__,inspect.stack()[1][3])
      except: pass
    return "%s V%s" % (__modulename__ ,__version__)

try:
    from time import time, sleep, localtime
    import dateutil.parser as dp
    import datetime
    import sys, os
    if sys.version_info[0] >= 3: unicode = str
    import signal               # handle kill signals e.g. reread DB meta values
    from struct import *        # pack/unpack payloads
    import base64
    import traceback
    import json                 # module to deal with json formated structures
    from jsmin import jsmin     # tool to delete comments and compress json
    import socket
    socket.setdefaulttimeout(120)
    import re                   # handle regular expressions
    import copy                 # copy values iso ref to objects

    from lib import MyDB                 # measurements kit database module
    from lib import MyLogger             # logging module
    from lib import MyMQTTclient         # module to receive MQTT data records
    from lib import MyGPS                # module to handle GPS ordinates/distances
except ImportError as e:
    sys.exit("One of the import modules not found: %s\n" % str(e))

debug = False  # output only for debugging reasons, no export of data
monitor = None # output monitoring info via proj/serial pattern
notices = None           # send notices of events
ProcessStart = time()    # time of startup

waiting = False          # waiting for telegram to arrive in queue
mid = None               # for logging: message ID
telegrams = []           # telegram buffer, max length is 100     
TelegramCnt = 0          # count of MQTT records received so far.
PingTimeout = 0          # last time ping request was sent
Channels = []            # output channels
DB = MyDB                # shortcut to Output channel database dict
Resources = None         # link to input resource handler
SensorsCache = {}        # is a cache (SensorTypes DB table) indexed by sensor product names with list of
                         # product (upper), producer, category and fields(name,unit,calibration) details

def PrintException():
    lineno = sys.exc_info()[-1].tb_lineno
    filename = sys.exc_info()[-1].tb_frame.f_code.co_filename
    print('EXCEPTION IN %s, LINE %d' % (filename, lineno))


# configurable options
__options__ = [
        'input',       # list of input channels
        'hostname','port', 'user','password', # MQTT server credentials To Do: list of brokers
        'timeout',     # timeout for no server active
        'rate',        # expected mininimal secs between measurements
        'FILE',        # data input json records from file iso MQTT server
        'DEBUG',       # debug modus
        'initfile',    # initialisation file with conf. info
        'check',       # list of sensor fields and trigger to check for fluctuation faults
        'monitor',     # pattern for project_serial to monitor for. '.*' (all)
        ]

MQTTdefaults = {
            'resource': 'eu1.cloud.thethings.network', # server host number for mqtt broker
            'topic': 'v3/+/devices/+/up',  # topic: appID/devices/devID/up, maybe a list of topics
            # use new import class for MQTT data to Internal Exchange Format
            #`'import': None, # MyMQTTclient.TTN2MySense(logger=None).RecordImport,
            'import': MyMQTTclient.TTN2MySense().RecordImport,
            # next required for MQTT broker access
            'port': 1883,        # default MQTT port, port 0 or None: read from file
            # + is a wild card in TTN
            # credentials to access broker
            'user': 'account_name',
            'password': 'ttn-account.acacadabra',
            # TODO: 'cert' : None,       # X.509 encryption
        }

Conf = {
    'DEBUG': False,      # debug modus
    'project': 'XYZ',    # default prefix to unique device/serial number
    'input': [],         # a list of input channels eg 'TTN' for TTN MQTT subscription
    'brokers': [             # round robin subscription list of MQTT TTN brokers
        MQTTdefaults,    # default broker access details
        ],
    'rate':    8*60,     # expected time(out) between telegrams published
                         # if data arrived < expected rate, throttling
                         # *2 is wait time to try to reconnect with MQTT server
    'check': [('luchtdruk',100),('temp',20),('rv',20),('pm10',30),('pm25',30)], # sensor fields for fluctuation faults
                         # if measurement values do not fluctuate send notice sensor is broken

    # defines nodes, LoRa, firmware, classes, etc. for Configure info
    # this will read from a dump MQTT file, can be defined from command line file=..
    # 'file': 'Dumped.json', # uncomment this for operation from data from file
    'FILE': None,
    # 'initfile': 'MyDatacollector.conf.json', # meta identy data for sensor kits
    'initfile': None,
    # 'nodes': {},  # DB of sensorkits info deprecated
    # LoRa, nodes, sensors, classes, firmware, and translate
    # 'test': True     # use TTN record example in stead of server access
    # DB dictionary with different sensors: type, producer, sensors/units
    # key calibrations is optional
    # types need to be capitalized
    # group classification is not used yet
    # notices:
    # 'notice': [['pattern','method:address',],], # send notices to email, slack, ...
    "notice": [
        [".*", "email:<noreply@behouddeparel.nl>", "slack:hooks.slack.com/services/123440" ],
        ["test.*", "email:<noreply@behouddeparel.nl>" ],
        ["lopyproto.*", "slack:hooks.slack.com/services/TGA123451234512345" ],
        ["gtl-ster.*", "slack:hooks.slack.com/services/T9W1234512345eSQ" ],
        ],
    "from": "Notice from TTN data collector <noreply@behouddeparel.nl>",
    "SMTP": "somesmtpservice.org",
    'CalRefs': [],      # list of sensor types to enable calibrate

    # defs of used fields by MySense, do not change the keys
    "translate": {
        "pm03":       {"pm03","pm0.3","PM0.3"},
        "pm05":       {"pm05","pm0.5","PM0.5"},
        "pm1":        {"pm1",},  # ,"roet","soot"},  # soot has diameter < PM0.1
        "pm25":       {"pm25","pm2.5","PM2.5"},
        "pm4":        {"pm4","pm4.0","PM4.0"},
        "pm5":        {"pm5","pm5.0","PM5.0"},
        "pm10":       {"pm10","pm","PM"},
        "O3":         {"O3","ozon"},
        "NH3":        {"NH3","ammoniak","ammonium"},
        "NO2":        {"NO2","stikstof","stikstofdioxide","nitrogendioxide"},
        "NO":         {"NO","stikstof","stikstofoxide","nitrogenoxide"},
        "CO2":        {"CO2","koolstofdioxide","carbondioxide"},
        "CO":         {"CO","koolstofmonoxide","carbonoxide"},
        "temp":       {"temp","temperature"},
        "luchtdruk":  {"luchtdruk","pressure","pres","hpa","hPa","Pa","pa"},
        "rv":         {"rv","humidity","hum","vochtigheid","vocht","rh"},
        "ws":         {"ws","windspeed","windsnelheid"},
        "wr":         {"wr","windrichting","winddirection","direction"},
        "geohash":    {"geohash",},
        "altitude":   {"altitude","alt","hoogte","height"},
        "longitude":  {"longitude","long","lon","lengte graad"},
        "latitude":   {"latitude","lat","breedte graad"},
        "gps":        {"gps","GPS","coordinates","geo","geolocation"},
        "gas":        {"gas","air","voc"},
        "aqi":        {"aqi","air quality","luchtkwaliteit","lki"},
        "version":    {"version","versie","release"},
        "meteo":      {"meteo","weer"},
        "dust":       {"dust","fijnstof"},
        "grain":      {"grain","korrel"},
        "accu":       {"accu","accu","battery"},
        "rain":       {"rain","regen","rain"},
        "dayrain":    {"dayrain","dayrain"},
        "prevrain":   {"prevrain","prevrain"},
        "event":      {"event","alarm"}, "value": ["waarde"],
        "time":       {"time","utime","timestamp"}
    },
}

# stop some threads or multi processing modules
__stop__ = []
# may need to put this in an atexit list
def EXIT(status=0):
    global __stop__, DB
    MyLogger.log(WHERE(),'CRITICAL' if status else 'ATTENT','Exiting')
    for one in __stop__: one()
    try:
      if DB.Conf['fd']: DB.Conf['fd'].disconnect()
    except: pass

    # just a hack to exit also with blocked threads
    import os
    import signal
    import platform
    # get the current PID for safe terminate server if needed:
    PID = os.getpid()
    if platform.system() != 'Windows':
        os.killpg(os.getpgid(PID), signal.SIGKILL)
    else:
        os.kill(PID, signal.SIGTERM)
    # for one in __threads__: stop(one) and join(one)
    exit(status)

# watchdog routines: one / off
def alrmHandler(signal,frame):
    global Conf
    Conf['log'].log(WHERE(True),'ATTENT','HTTP POST hangup, post aborted. Alarm nr %d' % signal)
    # signal.signal(signal.SIGALRM,None)

def watchOn(url):
    if url[:6] != 'https:': return None
    rts = [None,0,0]
    rts[0] = signal.signal(signal.SIGALRM,alrmHandler)
    rts[1] = int(time())
    rts[2] = signal.alarm(Conf['timeout'])
    return rts

def watchOff(prev):
    if prev == None: return 1
    alrm = signal.alarm(0)
    if prev[0] and (prev[0] != alrmHandler):
      signal.signal(signal.SIGALRM,prev[0])
      if prev[2] > 0: # another alarm and handler was active
        prev[1] = prev[2] - (int(time()) - prev[1])
        if prev[1] <= 0:
          prev[1] = 1
        signal.alarm(prev[1])
    return alrm

# rename names into known field names
# prepend with field_ if not known
# maybe we should do this only once the record is obtained from an input channel
def translate( sense, ext=False ):
    sense.replace('PM','pm')
    sense.replace('_pcs','_cnt')
    if not 'translate' in Conf.keys():
      if not ext: return sense
      return 'field_' + sense
    if type(Conf['translate']) is dict: # once to speedup
      Conf['trlt_set'] = set([a for a in Conf['translate'].keys()])
      Conf['translate'] = Conf['translate'].items()
    if sense in Conf['trlt_set']: return sense
    for field, org in Conf['translate']: # more detail work
      if sense.lower() == field.lower(): return field
      if (field[:2] == 'pm') and (field == sense[:-4]): return sense.lower()
      if sense.lower() in org: return field
    MyLogger.log(WHERE(False),'ATTENT','Found unimplemented sensor field: %s' % sense)
    if not ext: return sense
    return 'field_' + sense

# get Taylor seq for refs
def getCalibration(serialized, stype, refs=[]):
    if not serialized or not refs: return None # similar to [0,1] Taylor
    serialized = serialized.split('|')
    for ref in refs:
      ref = re.compile(ref+'/.*',re.I)
      if ref.match(stype): return None  # do not calibrate against similar sensor type
      for i in range(len(serialized)):
        if ref.match(serialized[i]): return [float(a) for a in serialized[i].split('/')[1:]]
    return None

# product information from DB table SensorTypes DB cache handling
def SensorInfo(product):
    global SensorsCache, DB, Conf
    try:
      one = SensorsCache[product.upper()]
      if one['ttl'] > int(time()): return one
    except: pass

    try:
      # time to live cache entry is 12 hours
      qry = DB.db_query("SELECT UNIX_TIMESTAMP(now())+12*60*60,matching,producer,category,fields FROM SensorTypes WHERE product LIKE '%s' LIMIT 1" % product, True)[0]
      if len(qry) != 5:
        MyLogger.log(WHERE(True),'ATTENT','Unable to find sensor type %s in SensorTypes DB table' % product)
      fields = []
      if qry[4]:
        for one in qry[4].split(';'):
          fields.append(one.split(','))
          try:
            if len(fields[-1]) == 3 and Conf['CalRefs']:
              fields[-1][2] = getCalibration(fields[-1][2],qry[1],Conf['CalRefs'])
              if not fields[-1][2]: fields[-1].pop(2)
          except:
            if len(fields[-1]) == 3: fields[-1].pop(2)
          fields[-1] = tuple(fields[-1])
      # match has reg exp for all product names withg same type of measurements
      SensorsCache[product.upper()] = {'ttl':qry[0],'type':product.upper(),'match':re.compile(qry[1].replace('?','.'),re.I),'producer':qry[2],'category':qry[3].lower(),'fields':tuple(fields)}
    except: # product does not exists in DB table and cache
      # SensorsCache[product.upper()] = product
      return product
    return SensorsCache[product.upper()]

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
        MyLogger.log(WHERE(True),'ATTENT','Imported notice addresses from file %s' % Conf['noticefile'])
        return True
    except Exception as e:
        MyLogger.log(WHERE(True),'ERROR','Failed to load notice addresses. Error: e' % str(e))
        return False

# monitor output channel. Color scheme:
DFLT   = 0
RED    = 1
GREEN  = 2
YELLOW = 3
PURPLE = 5
GRAY   = 8
BLACK  = 16
BLUE   = 21
LBLUE  = 33
BROWN  = 52
def monitorPrt(msg, color=DFLT): # default color is black
    global monitor
    if not monitor: return
    try:
        if not monitor['output']: return
        monitor['output'].MyPrint(msg, color=color)
        return
    except: pass
    try: sys.stdout(msg+'\n')
    except: pass

def Initialize(DB=DB, debug=debug, verbose=None):
    global Conf, notices, MQTTdefaults, Channels, Resources
    if (not 'initfile' in Conf.keys()) or not Conf['initfile']:
        MyLogger.log(WHERE(True),'WARNING',"No initialisation file defined, use internal definitions.")
    else:
        MyLogger.log(WHERE(),'INFO',"Using initialisation file %s." % Conf['initfile'])
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
            MyLogger.log(WHERE(True),'ERROR',"Json error in init file %s: %s" % (Conf['initfile'],e))
            MyLogger.log(WHERE(),'ATTENT','Missing or errors in LoRa init json file with info for all LaRa nodes. Exiting.')
            return False
        # nodes info are exported to Database tables Sensors and TTNtable
        for item in ['project','brokers','translate','notice','from','SMTP','MyDB','adminDB',]:
            if item in new.keys():
                Conf[item] = new[item]
                MyLogger.log(WHERE(),'ATTENT','Overwriting dflt definitions for Conf[%s].' % item)
    # collect type of input channels, here file TTN dump or list of TTN MQTT apps
    if 'FILE' in Conf.keys() and Conf['FILE']:
      MQTTdefaults['resource'] = Conf['FILE']
      del MQTTdefaults['port']
      Conf['input'] = [MQTTdefaults]
    elif not Conf['input']:
      try: Conf['input'] = Conf['brokers'] # different key in use
      except: pass
    for item in reversed(range(len(Conf['input']))):
      if not type(Conf['input'][item]) is dict:
          MyLogger.log(WHERE(True),'ERROR',"broker(s) misconfiguration: %s" % str(item))
          Conf['input'].pop(item)
          continue
        # setting defaults for MQTT broker
      for one in MQTTdefaults.keys(): # take over defaults
        if not one in Conf['input'][item].keys():
          if one == 'import':
            Conf['input'][item][one] = MyMQTTclient.TTN2MySense(logger=MyLogger.log).RecordImport, # MQTT data to Internal Exchange Format
            if isinstance(Conf['input'][item][one],tuple): # a hack
                Conf['input'][item][one] = Conf['input'][item][one][0]
          else:
            Conf['input'][item][one] = MQTTdefaults[one]
    importNotices()  # enable automatic import of notice addresses if noticefile is defined
    if not notices: Conf['notice'][0] = [] # notices turned off in eg test phase
    if Conf['FILE']: # turn output off to external data portals
      # do not output to Luftdaten as timestamp is wrong, nor send notices
      for item in Channels:
        try:
          if item['script'] in ['MyCOMMUNITY','notices']:
            if item['Conf']['id_prefix'] != 'TTN-': item['Conf']['output'] = False
            MyLogger.log(WHERE(),'ATTENT','Output to %s is switched off.' % item['name'])
        except: pass
    if not len(Conf['input']):
      MyLogger.log(WHERE(),'CRITICAL','No input channel defined.')
      EXIT(1)
    try:
      Resources = MyMQTTclient.MQTT_data(Conf['input'], DB=DB, verbose=verbose, debug=debug, logger=MyLogger.log)
    except: 
      MyLogger.log(WHERE(),'CRITICAL','Input initialisation for (MQTT) brokers failed')
      EXIT(1)
    for broker in Conf['input']:
      try: BrkrID = ' (%s)' % broker['clientID']
      except: BrkrID = ''
      MyLogger.log(WHERE(),'INFO','Input is read from: %s%s' % (broker['resource'],BrkrID))
    if not Resources: return False
    if 'MyDB' in Conf.keys(): # use DB info and credentials from init file
      for one,value in Conf['MyDB'].items():
        if one in ['hostname','port','database','user','password',]:
          DB.Conf[one] = value

    return True

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
    # msg['Subject'] = 'MySense: TTN data collector service notice'
    msg['Subject'] = 'MySense: TTN data collector service TEST notice'
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
        MyLogger.log(WHERE(True),'ERROR',"Email notice failure: %s" % str(e))
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
        MyLogger.log(WHERE(True),'DEBUG','Notice via curl/Slack sent to %s (not sent) via curl): %s' % (one, message))
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
        MyLogger.log(WHERE(True),'ERROR',"Slack notice failure: %s" % str(e))
        # print("Slack notice failure with: %s" % str(curl)) # comment this out
        rts = False
        continue
      p.wait()
    return rts

# obtain notice address for a kit from Sensors DB tbl
def kitInfo(DBi,project,serial,fields=[]):
    global DB
    if not len(fields): return {}
    if DBi: serial = None  # DB lookup via row ID
    elif project == None or serial == None: return {}
    try:
        id = DB.getNodeFields(DBi,fields,'Sensors',project=project,serial=serial)
        if type(id) is dict: return id
        return {fields[0]: id[0]}
    except: return {}

# distribute notices for an event
# info: identication project,serial or None
def sendNotice(message,info=None,all=False):
    global Conf, debug, monitor, notices
    try: # check if sending notices has methods and addresses
        if not len(Conf['notice'][0]): return False
    except: return False
    # check if notices is enabled
    if not notices: return True
    try:
        if not notices['output']: return True
    except: return False
    try: # throttle event notices to once per 4 hours
      if int(time()) < info['last_notice']: return True
      else: info['last_notice'] = int(time())+4*60*60
    except: pass

    # get ref to where to send notice to
    serial = None; id = None
    try: DBi = info['SensorsID']
    except: DBi = None
    try:
      info = info['id']
      if all: serial = info['id']['serial']
      id = info['id']['project']
    except: pass
      
    nodeNotice = [] # method/address to send noitice to
    extra = []      # location details of the kit
    if serial:      # notices sent via Sensors table
        try:
            kitID = {}
            kitID.update(kitInfo(DBi,id,serial,['notice','project','serial','label','serial','street','village','geohash']))
            # get MQTT topic, alternative is to match notices on label of the kit
            for item in ['notice','project','serial','street','village','geohash']:
                if not item in kitID.keys(): continue
                if (item == 'notice') and kitID['notice']:
                  nodeNotice += kitID['notice'].split(',')
                elif item == 'geohash':
                  try:
                    (lat,lon) = MyGPS.fromGeohash(kitID[item])
                    extra.append('latitude: %s, longitude: %s' % (lat,lon))
                  except: pass
                else: extra.append('%s: %s' % (item,kitID[item]))
            extra = 'Some more MySense kit details:' + "\n\t".join(extra)
            # comment next if in beta test
            extra += "\n\nMessage is a beta test message: please ignore this message."
        except: pass
    else:
      try: id = infoID['project']
      except: pass
    id = str(id) # if None '.*' will match, otherwise id = project name
    
    for item in Conf['notice']: # add global notice addresses from configuration
        if not (re.compile(item[0],re.I)).match(id): continue
        nodeNotice += item[1].split(',')

    sendTo = { 'email':(email_message,[]), 'slack':(slack_message,[]) }
    for item in nodeNotice:  # collect different notices send methods
        try:
            for to in item[1:]:
                to = to.strip()
                one = to.split(':')
                one[0] = one[0].strip().lower()
                if not one[0] in sendTo.keys(): continue
                try:
                    if not one[1].strip() in sendTo[one[0]]:
                        sendTo[one[0]].append(one[1].strip())
                except: continue
        except: continue

    for item, value in sendTo.items(): # send notice
      if debug:
        if value[1]:
          sys.stderr.write("Send %s Notice\n    to: %s\n" % (item,', '.join(value[1])) )
          sys.stderr.write("     Message  : %s\n" % str(message))
          if extra: sys.stderr.write("     Location  : %s\n" % extra)
        else: sys.stderr.write("No recipient for %s Notice\n" % item)
      else:
        if not value[1]: continue
        monitorPrt("Send %s Notice to: %s\n" % (item,', '.join(value[1])), RED)
        monitorPrt("     Message  : %s\n" % str(message), (GRAY if not notices else BLUE))
        if extra: message += '\nKit ID and location: %s' % extra
        value[0](message, value[1])
    return True

# only once at startup time: get names operational defined kits silent for long period
def DeadKits():
    global DB, TelegramCnt
    if not DB: return False
    # obtain all operational kits
    kitTbls = DB.db_query("SELECT DISTINCT Sensors.project, Sensors.serial FROM Sensors, TTNtable WHERE Sensors.active AND TTNtable.active ORDER BY Sensors.datum DESC", True)
    if not len(kitTbls): return False
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
    if not lastRun: return False
    # topic id for dead kits
    Fnd = False
    for indx in range(len(Selection)):
      diff = lastRun - Selection[indx][0]
      if diff <= 2*60*60: continue
      try:
        TTNid = DB.db_query("SELECT DISTINCT TTN_id FROM TTNtable WHERE project = '%s' AND serial = '%s' AND active" % (Selection[indx][1],Selection[indx][2]), True)
        if not len(TTNid) or not len(TTNid[0]): continue
        Fnd = True
        MyLogger.log(WHERE(),'ATTENT',"Kit TTN id %s, project %s, serial %s, not seen for a while. Last seen: %s." % (TTNid[0][0], Selection[indx][1],Selection[indx][2],datetime.datetime.fromtimestamp(Selection[indx][0]).strftime("%Y-%m-%d %H:%M")) )
        if not TelegramCnt: continue  # sendNotices only when fully operating
        if diff <= 24*60*60:
          sendNotice("Kit project %s, serial %s:\t last seen %dh:%dm:%ds ago.\nMaybe not connected?\nLast time seen: %s." % (Selection[indx][1],Selection[indx][2],diff/3600,(diff%3600)/60,(diff%(3600*60))%60,datetime.datetime.fromtimestamp(Selection[indx][0]).strftime("%Y-%m-%d %H:%M")), info={'id': {'project': Selection[indx][1],'serial':Selection[indx][2]}},all=True)
        else:
          sendNotice("Kit project %s, serial %s:\nMaybe not connected for a very long time?\nLast time seen: %s." % (Selection[indx][1],Selection[indx][2],datetime.datetime.fromtimestamp(Selection[indx][0]).strftime("%Y-%m-%d %H:%M")),info={'id':{'project': Selection[indx][1],'serial':None}})
      except: pass
    return Fnd

# dict of valid sensor values as name: list [min,max] or name: r'reg exg', 0.0 value is seen as invalid
# source: https://www.weerstationtzandt.nl/records.php
InvalidSensed = {
    'accu':     [0,15],    # accu voltage
    'level':    [14,120],   # accu level
    'aqi':      [0,100],
    'gas':      [0,6000],
    'grain':    [0,10],
    'altitude': [-20,500],
    'latitude': [-91,91],
    'longitude':[-181,181],
    'pm05_cnt': [0,25000],
    'pm1':      [0,1000],
    'pm10':     [0,1000],
    'pm10_cnt': [0,25000],
    'pm1_cnt':  [0,25000],
    'pm25':     [0,1000],
    'pm25_cnt': [0,25000],
    'pm5_cnt':  [0,25000],
    'pm4_cnt':  [0,25000],
    'luchtdruk':[700,1060],
    'rv':       [0,100],
    'temp':     [-20,45],
    'wr':       [0,360],
    'ws':       [0,50],
    'rain':     [0,50],
    'prevrain': [0,50],
    'geohash':  re.compile(r'^u1h[hjknu][a-z0-9]{,10}$',re.I),# reg exp, change this for other regions
}
# check for valid value of sensed data
def ValidValue(info,afield,avalue):
    global InvalidSensed
    if avalue == None: return True
    fld = afield.lower()
    if fld == 'accu' and avalue > 15: fld = 'level'
    try:
      if not type(InvalidSensed[fld]) is list:
        if type(avalue) in [str,unicode] and InvalidSensed[fld].match(avalue):
          return True # skip others not in this region
      elif InvalidSensed[fld][0] <=  avalue < InvalidSensed[fld][1]:
        # eg temp == 0.0 denotes a sensor failure
        if avalue != 0.0 or not fld in ['temp']:
          try: del info['invalids'][fld]
          except: pass
          return True
    except: return True
    try: info['invalids']
    except: info['invalids'] = {fld: -1}
    try: info['invalids'][fld] += 1
    except: info['invalids'][fld] = 0
    return False

# check for sensor field value fluctuation, no fluctuation give notice
# if not present initialize cache entry
# reset after 100?, notice once after 20 times same value. To Do: use interval timings
toBeChck = None
def FluctCheck(info,afield,avalue):
    global Conf, toBeChck
    if toBeChck == None: toBeChck = set([ a[0] for a in Conf['check']])
    if not afield in toBeChck: return None
    # if value == None: return afield
    try: chk = info['check']
    except: chk = info['check'] = {}
    try: chk[afield]
    except:
      chk[afield] = [0,avalue]
    if (chk[afield][1] == None) or (chk[afield][1] != avalue):
      # chk[afield][2] == max(chk[afield][0],avalue)
      # chk[afield][3] == min(chk[afield][0],avalue)
      chk[afield][1] = avalue
      chk[afield][0] = 0
      return None
    # same value: to do: make max value variable per sensor type
    chk[afield][0] += 1

    for one in toBeChck:  # get amount of static values permitted for afield
      if Conf['check'][0] == afield:
        trigger = Conf['check'][1]; break
    else: trigger = 20
    if chk[afield][0] <= trigger: # await fluctuations for ca 5 hours
      return None
    if chk[afield][0] > trigger+1 and (chk[afield][0] % 100): # have already give notice
      return afield
    MyLogger.log(WHERE(True),'ERROR','kit %s/%s has (malfunctioning) sensor field %s, which gives static value of %.2f #%d.' % (info['id']['project'],info['id']['serial'],afield,avalue,chk[afield][0]))
    sendNotice('%s: kit project %s, serial %s has (malfunctioning) sensor field %s, which gives static value of %.2f on a row of %d times. Skipped data.' % (datetime.datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M"),info['id']['project'],info['id']['serial'],afield,avalue,chk[afield][0]),info=info,all=False)
    return afield

# hack to delete PM mass None values when PM count is not zero
# deprecated when LoRa compression is not mapping NaN values to 0
def CheckPMmass( field, value, cnt ):
    if not type(record) is dict or not len(record): return record
    if field in ['pm1','pm25','pm10']:
      if value == None and cnt > 0:
        return 0.013
    return value

""" Data record exchange format definition: DREF V0.1 Draft Aug 2021
    {
      // if timestamp is not defined in data record the timestamp of record recept is taken
      "version": 0.0,            // version of exchange format
      “id”: { “project”: “SAN”, “serial”: “78CECEA5167524” },
      "timestamp": 1621862416,   // or “dateTime”: “2021-05-24T15:20+02:00”,

      // meta data is state information of a measurement kit
      "meta": {                  // meta data (re)definitions, kit state sensor type in use definitions
        "version": 0.2,          // firmware version, optional
        "timestamp": 1621862400, // meta info timestamp, optional
        "dust": "PMSx003",       // dust sensor types/manufacturer
        // default home location of measurement kit
        "geolocation": { “geohash”: “u1hjjnwhfn” },
        "GeoGuess": True,        // optional if location comes from gateway location
        "meteo": [ "BME680", ”SHT31” ], // more as one type present in kit
        “energy”: { “solar”: “5W”, “accu”: “Li-Ion” }, // energy type: dflt "adapter": "5V"
        "gps": "NEO-6",
        "event": 13              // measurement event
        },

      // communication information for statistical and monitoring use. Only internaly use
      "net": {
        'TTN_id': u'kipster-k1', 'TTN_app': u'201802215971az', 'type': 'TTNV2',
        'gateways': [
          {'rssi': -94,  'gtw_id': u'eui-ac1f09fffe014c16', 'snr': 9.5},
        ]},

      // measurement data
      "data": {                  // measurements, only those active at that moment
        "version": 0.2,          // data version, optional
        "timestamp": 1621862400, // measurement timestamp, optional
        // internal use: 'TYPE': [('FIELD',VALUE[,'UNIT'), ...], ...
        "NEO-6": { "geohash": "u1hjjnwhfn", "alt": 23 },
        "BME680": {
          // tuples in this example redefine the unit in use. None value: present but undefined value
        },
        “SHT31”: [ { “temp”: 20.1, “rv”: 70.1 }, { “temp”: 20.3, “rv”: 67.3 } ], // 1+ sensors same type
        "PMSx003": {             // _cnt items are PM count up to upper bound bin!!
          "pm05_cnt": 1694.1, "pm10": 29.4, "pm25_cnt": 2396.9, "pm03_cnt": None,
          "grain": 0.5,          // average grain size
          "pm1_cnt": 2285.7, "pm25": 20.4, "pm10_cnt": 2.4, "pm1": 13.0
        },
        “accu”: (89.5,”%”)
      }
    }
"""
# class KitCache
#      self.KitCached = {
#         'project_serial': {
#            'id':        { 'project': project ID, 'serial':  measurement kit serial number ID }
#
#            'SensorsID': Sensors table database row id
#            'active':    kit active?
#            'location':  current home location as geohash, None unknown
#            'sensors':   sensor types (manufacturer ProdID's): converting to list of senors type dicts
#
#            'TTNtableID':TTNtable table database row id
#            'MQTTid':    MQTT subscription ID eg TTN subscribe: TTN_app/TTN_id
#            'DATAid':    measurements table if active? (PROJ_SERIAL)
#            'Luftdaten': Luftdaten ID if active? (TTN-SERIAL)
#            'WEBactive': active on website?
#
#            # statistics
#            'timestamp': unix timestamp in KIT for cache mgt
#            'last_seen': unix timestamp secs, last seen
#            'count':     received records count, rese on new info
#            'interval':  guessed usual interval, dflt 15*60 secs
#            'gtw': [[],...] LoRa gateway nearby [gwID,rssi,snr,(lat,long,alt)]
#            'unknown_fields': [] seen but not used fields
#            'FromFILE':  True if data read is read from file
#            'check':     dict of current static sensor values
#        },
#      }
# Example:
# {'count': 0, 'DATAid': u'SAN_b4e62df4b311', 'WEBactive': 1, 'TTNtableID': 1590665967, 'valid': 1, 'timestamp': 1629569059, 'id': {'project': u'SAN', 'serial': u'b4e62df4b311'}, 'interval': 240, 'SensorsID': 1593163787, 'MQTTid': u'201802215971az/bwlvc-b311', 'location': u'u1hjtzwmqd', 'gtw': [], 'active': 1, 'Luftdaten': u'b4e62df4b311', 'unknown_fields': [], 'sensors': u'PMSX003,BME280,NEO-6', 'last_seen': 1627828712, 'check': {'rv': [5,100.0}}


# check if measurement kit is behaving: activated, needs to be throttled
def IsBehavingKit(info,now):
    global Conf
    # do not throttle if input comes from file
    # 
    if not info or not 'count' in info.keys(): return "Missing info"
    try:
      if info['last_seen']:
        # update datagram frequency and throttle if needed so
        try:
          if info['FromFILE']: return None
        except: pass
        if (info['count'] > 3) and ((now - info['last_seen']) < (Conf['rate'])):
            if not 'throttling' in info.keys():
                info['throttling'] = now
                MyLogger.log(WHERE(),'ERROR','%s (re)start throttling kit: %s (rate %d < throttle %d secs).' % (datetime.datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M"),str(info['id']),now - info['last_seen'],Conf['rate']))
                info['last_seen'] = now
                return 'Start throttling kit: %s' % str(info['id']) # artifacts kit on drift
            elif (now - info['throttling']) > 4*60*60:
              MyLogger.log(WHERE(),'INFO','%s Reset throttling kit: %s\n' % (datetime.datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M"),str(info['id'])) )
              del info['throttling'] # reset throttling after 4 hours
            else:
              MyLogger.log(WHERE(True),'DEBUG','%s Throttling kit: %s\n' % (datetime.datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M"),ID))
              info['last_seen'] = now
              return 'Skip data. Throttling kit.' # artifacts
        # try to guess interval timing of measurement
        if not info['interval'] or (now - info['last_seen'] > 60*60): # initialize
          info['interval'] = 15*60  # reset
        else:  # average guess
          info['interval'] = min((info['interval']*info['count']+(now - info['last_seen']))/(info['count']+1),30*60)
    except: pass
    return None

# give alarm notice, when time out exceeds. Set time sent.
# denote last time message was sent (info in cache may also be cleared at some point in time)
def AlarmMessage(info, msg, timeout=6*60*60):
    now = int(time())
    if timeout:
      try:
        if info['alarmTime'] + timeout < time():
          if info['alarmTime'] + 60*60 < now: # in first hour
            MyLogger.log(WHERE(),'INFO',msg)
            if timeout: monitorPrt(msg)
          return False
      except: pass
    MyLogger.log(WHERE(),'ATTENT',msg)
    if timeout: monitorPrt(msg, PURPLE)
    # may need to send a notice
    sendNotice('ATTENT',msg,info=info,all=True)
    info['alarmTime'] = now # denote time alarm message
    return True

# check if kit enabled for doing measurements
def kitIsEnabled(info, data):
    id = None
    try: # check if id is defined
      if info['active']: return []
      id = info['id']; id['project']; id['serial']
    except:
      if not info:
        msg = '%s kit with record: %s. Skipped.' % ('Unkown' if not id else 'Unregistered',str(data))
      else:
        msg = '%s disabled kit with record: %s. Skipped.' % ('Unkown' if not id else 'Unregistered',str(data))
      AlarmMessage(info, msg, 12*60*60)
      return ['%s kit: %s' % ('Unkown' if not id else 'Unregistered',str(id))] # artifacts
    return []

# check if kit is a known kit: info should exists and info['id']
def KnownKit(info):
    id = None
    try: topic = info['MQTTid']
    except: topic = None
    try: # check if id is defined
      id = info['id']; id['project']; id['serial']
    except:
      info['last_seen'] = int(time.time())
      msg = 'MQTT id:%s, %s kit. Skipped.' % (str(topic),'Unkown' if not id else 'Unregistered') # artifact
      AlarmMessage(info, msg, timeout=0)
      return msg
    return None

# handle events of measurement kit. Delete event from data record meta info
def HasEvent(info, meta):
   try:
     event = meta['event']    # translate event number to message
     event = { 13: 'Accu level', 14: 'Watch Dog', 15: 'Controller Reset', }[event]
     del meta['event'] # not needed anymore
   except: return []
   if event:
     if type(event) is int: event = str(event)
     try: info['last_notice']
     except:
       info['last_notice'] = int(time())
     msg = "Measurement kit with id %s raised event %s, value %s" % (str(info['id']), event, str(meta['event']))
     AlarmMessage(info, msg, timeout=6*60*60)
     return ['Raised event: %s.' % event] # artifacts
   try: del info['event_cnt']
   except: pass
   return []

def UpdateNewHome(info, geoloc, alt):
   global DB
   address = MyGPS.GPS2Address(geoloc)
   inTBL = DB.getNodeFields(info['SensorsID'],['geohash','alt','street','village','province','municipality','pcode','housenr','region'])
   fields = []; values = []
   for (field,value) in inTBL.items():
     try:
       if address[field] == None: continue
       if address[field] == inTBL[field]: continue
       fields.append(field); values.append(address[field])
     except: pass
   if fields:  # some value changed
     setNodeFields(info['SensorsID'],fields,values)

     msg = 'MySense measurement kit project %s, serial %s has been installed to new home location: ' % (info['project'],info['serial'])
     for one in ['longitude','latitude','street','housenr','village']:
       try: msg += address[one]+', '
       except: pass
     sendNotice(msg,info=info,all=False)
     MyLogger.log(WHERE(),'ATTENT',"Installed home location %s for kit project %s, serial %s" % (geoloc,info['project'],info['serial']))
     monitorPrt('Installed home location %s for kit project %s, serial %s' % (geoloc,info['project'],info['serial']), PURPLE)
     return True
   return False

# handle meta home location: cache: location, meta data: geolocation
def HasNewHomeGPS(info, data):
   global DB
   try: home = info['location']
   except: home = None
   geoloc = None; alt = None; guessed = False
   try:
     geoloc = data['meta']['geolocation']
     try: guessed = data['meta']['GeoGuess']
     except: pass
     if 'geohash' in geoloc.keys(): geoloc = geoloc['geohash']
     elif 'lon' in  geoloc.keys() and 'lat' in geoloc.keys():
       geoloc['geohash'] = convert2geohash([geoloc['lon'],geoloc['lat']])
       del geoloc['lon']; del geoloc['lat']
       geoloc = geoloc['geohash']
     if 'alt' in geoloc.keys(): alt = geoloc['alt']
   except: pass
   if not home and not geoloc: # maybe the data record has home geolocation kit
     try:
       loc = data['data']['gps']
       geoloc = loc['geohash']; guessed = False
       try:
         if not alt: alt = loc['alt']
       except: pass
     except:
       try:
         geoloc = convert2geohash([loc['lon'],loc['lat']])
         if not alt: alt = loc['alt']
       except: pass
   elif not geoloc or guessed: return []
   # if new location: update Sensors table
   rts = []
   if not home and geoloc:  # no home location defined, but there is a location via GPS
      home = info['location'] = geoloc
      try:
        if UpdateNewHome(info, geoloc, alt): rts.append('Updated home location') # artifacts
      except: pass
   if home and geoloc:      # maybe measurement kit is not on home location
      if MyGPS.GPS2Aproximate(home,geoloc) < 118: # distance in meters is about the same
        if info['valid'] == None:                 # kit is back home
          info['valid'] = True
          try:
            DB.db_query("UPDATE TTNtable SET valid = 1, refresh = NULL WHERE UNIX_TIMESTAMP(id) = %d" % info['TTNtableID'], False)
            MyLogger.log(WHERE(),'ATTENT',"Kit project %s, serial %s installed back to home location" % (info['project'],info['serial']))
            sendNotice("MySense measurement kit project %s, serial %s installed back to home location" % (info['project'],info['serial']),info=info,all=False)
            rts.append['Kit back to home location']
          except: pass
        # delete geohash from data record
        for item in ['NEO-6']:
          try:
            del data['data'][item]
            # if abs(data['data']['altitude'] - alt) < 10: # to be corrected
            #   del data['data']['altitude']
          except: pass
      else:  # kit is not at home location
        if info['valid']:                         # denote kit is from now eg in repair
          try:
            DB.dbquery("UPDATE TTNtable SET valid = NULL, refresh = now() WHERE UNIX_TIMESTAMP(id) = %d" % info['TTNtableID'], False)
            MyLogger.log(WHERE(),'ATTENT',"Kit project %s, serial %s has been removed from home location to %s" % (info['project'],info['serial'],geoloc))
            where = MyGPS.GPS2Address(geoloc)
            msg = 'MySense measurement kit project %s, serial %s has been removed from home location to: ' % (info['project'],info['serial'])
            for one in ['longitude','latitude','street','housenr','village']:
              try: msg += where[one]+', '
              except: pass
            sendNotice(msg,info=info,all=True)
            info['valid'] = None
            rts.append('Kit removed from home location') # artifacts
          except: pass
   return rts

# is this kit restarted after some time out?
def IsRestarting(tstamp,info):
    try:
      if tstamp == None:  # measurement table has no measurements
        MyLogger.log(WHERE(),'ATTENT','Kit %s is newly installed.' % str(info['id']))
        sendNotice('Kit project %s, serial %s is newly installed. First recort at time: %s.\nMySense kit identification: %s.' % (ID,datetime.datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M"),info['id']['project'],info['id']['serial']),info=info,all=True)
        return ['New kit'] # artifact
      elif tstamp > 90*60:
        MyLogger.log(WHERE(),'ATTENT','Kit %s is restarted after %dh%dm%ds' % (str(ID),tstamp/3600,(tstamp%3600)/60,tstamp%60))
        sendNotice('Kit %s is restarted at time: %s after %dh%dm%ds.\nMySense kit identification: %s.' % (str(ID),datetime.datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M"),tstamp/3600,(tstamp%3600)/60,tstamp%60,str(ID)),info=info,all=False)
        return ['Restarted kit'] # artifact
    except: pass
    return []

# return list of sensor types found in arg sensors (comma separated list of sensors)
# the returned list has sensor type info in dict or just a name
def SensorTypes(sensors):
    if not sensors: return []
    if type(sensors) is unicode: sensors = str(sensors)
    if not type(sensors) is str: return sensors
    rts = []
    for one in sensors.split(','):
      one = one.strip()
      if one.upper() == 'NEO': one = 'NEO-6' # correct one name
      item = SensorInfo(one)
      try:
        if one.upper() == item['type'].upper(): one = item
      except: pass
      rts.append(one)
    return rts

# update Sensor types, description, ... in meta info measurement DB table Sensors
# arguments: info, list of [field,old,new]
# try to change DB in one single query
def updateSensorsTbl(info,DBchanges):
    if not DBchanges: return True
    qry = []; msg = []
    for item,values in DBchanges.items():
      try:
        for i in [0,1]:
          if type(values[i]) in [list,set]:
            values[i] = ','.join(sorted([str(a) for a in values[i]]))
          if values[i] == 'None': values[i] = None # blame implementor
          if values[i] != None: values[i] = str(values[i])
      except: continue
      # compute qry for a field, default just a string
      if values[0] == values[1]: continue  # nothing changed
      if item == 'description':  # has a rather wild structure
        msg.append("version: %s -> %s" % (values[0],values[1]))
        if values[0]:
          if values[1]:
            qry.append("description = REPLACE(description,'%s','%s')" % (str(values[0]),str(values[1])))
          else:
            qry.append("description = REPLACE(description,'%s','')" % str(values[0]))
        elif values[1]: # add new firmware version mark
          qry.append("description = IF(ISNULL(description),'%s',CONCAT(description,' %s'))" % (str(values[1]),str(values[1])))
      else:
        msg.append("%s: '%s' -> '%s'" % (item,str(values[0]),str(values[1])) )
        if values[1] == None:
          qry.append("%s = %s" % (item,'NULL'))
        else:
          qry.append("%s = %s" % (item,str(values[1]) if not type(values[1]) is str else "'%s'" % values[1]))
    if not qry: return True
    try:
      DB.db_query("UPDATE Sensors SET %s WHERE UNIX_TIMESTAMP(id) = %d" % (', '.join(qry),info['SensorsID']),False)
      MyLogger.log(WHERE(),'ATTENT',"Updating Sensors tbl: %s. Project %s, serial %s." % (', '.join(msg),info['id']['project'],info['id']['serial']))
      monitorPrt("Updating Sensors tbl: %s' for project %s, serial %s." % (', '.join(msg),info['id']['project'],info['id']['serial']), PURPLE)
      sendNotice("Updating measurements kit meta information for project %s, serial %s:\n\t%s" % (info['id']['project'],info['id']['serial'],"\n\t".join(msg)),info=info,all=False)
    except: return False
    return True

# Forward measurement data with (cached) kit information ##############
# update info sensors when new sensors appeared in measurements or meta data record part
# return True if data has measurements
# convert different value types into one dict per sensor type
def HasMeasurements(info,data,DBchanges):
    rtsMsg = [] # artifacts
    # return True/False if sensor type is found in sensors list
    # if same 'category' change sensors list to new sensor type reference
    # if new add sensor type reference to sensors argument.
    # Plantower PMSx003, PMS7003 etc. are not discrimative, use first
    def UpdateKnownTypes(sensors,sensor):
      category2 = None; SType2 = sensor; key = 'category'
      if not type(sensors) is list: sensors = [sensors] if sensors else []
      try:
        if not type(sensor) is dict:
          for one in sensors:
            try:
              if type(one['match']) in [str,unicode]:
                one['match'] = re.compile(one['match'],re.I)
              if one['match'].match(sensor.upper()):
                return True
            except: pass
          sensor = SensorTypes(sensor)[0]
      except: return False
      try: category2 = sensor[key].upper()
      except:
        # raise ValueError("Unknown sensor type %s" % str(sensor))
        category2 = sensor.upper()

      for i in range(len(sensors)-1,-1,-1):  # allow one sensor type per category
        try:
          category1 = sensors[i][key].upper(); SType1 = sensors[i]['match']
        except:
          try: category1 = sensors[i].upper();  SType1 = sensors[i]
          except:
            category1 = None; SType1 = None
        if category1 != category2 or not SType1: continue
        if type(SType1) in [str,unicode]:
          SType1 = re.compile(SType1,re.I)
        if not SType1.match(SType2.upper()): # category same, sensor types differ
          sensors[i] = sensor; return False
        elif sensors[i]['type'] != SType2:# hack: no way to discriminate some sensor types
          sensors[i]['type'] = SType2     # use new value, blame implementor
        return True  # found sensor type in sensor types list
      sensors.append(sensor)
      return False # not known
      
    def getTypes(sensors, key=None):  # return list of sensor types names
      if type(sensors) in [str,unicode]:
        t = [one.strip() for one in sensors.split(',')]
      else: t = sensors
      if not key: return t
      rts = []
      for one in t:
        try: rts.append(one[key])
        except:
          if type(one) in [unicode,str]: rts.append(one)
      return rts

    try:
      if not type(info['sensors']) is list:
        info['sensors'] = SensorTypes(info['sensors'])
    except: pass
    DBsensors = set(getTypes(info['sensors'],key='type'))

    # find sensor types defined in meta data record data['meta']: {'dust': 'SPS30', ...} 
    Msensors = []
    try:
      meta = data['meta']
      # pick up sensor types from meta data element
      # should be list column category from SensorTypes DB table
      for item in ['dust','meteo','gps','energy','rain','wind','weather']:
        try:
          if type(meta[item]) is dict: Msensors += meta[item].values()
          elif type(meta[item]) is list: Msensors += meta[item]
          else: Msensors.append(meta[item])
        except: pass
    except: pass
    if Msensors: info['sensors'] = SensorTypes(Msensors)

    # "data": {  # To Do: use unit to update field unit
    #   "version": 0.2,
    #   "timestamp": 1621862400,                          -> internaly expressed as:
    #   "NEO-6": {"geohash":"u1hjjnwhfn","alt":(23,'m')}, -> [('geohash','u1hjjnwhfn'),('alt',23,'m')]
    #   "BME680": {},                                     -> []
    #   “SHT31”: [ { “temp”: 20.1, “rv”: 70.1 }, { “temp”: 20.3, “rv”: 67.3 } ], -> [('temp',20.1,None)...]
    #   "PMSx003":{ ..."pm05_cnt":1694.1,"pm10":29.4,...},-> [('pm05_cnt',1694.1) ...]
    #   “accu”: (89.5,”%”)                                -> [('accu',89.5,'%')]
    # }

    # convert deprecated data exchange format to [(),...] format
    # returns for each sensor type: [(field,value[,unit]),...]
    # field names are translated to MySense field names
    # check for reasonable values if not valid change value to None (unvalid)
    def ConvertValue(info,field,value,rts=[],flucts=[]):
      items = []
      fld = translate(field)
      if type(value) in [tuple,list]:
        if len(value) > 2:    # type field: (value,unit,cal) -> (field,value,unit,cal)
          item = (fld,value[0] if ValidValue(info,fld,value[0]) else None,value[1],value[2])
        elif len(value) > 1:  # type field: (value,unit) -> (field,value,unit)
          item = (fld,value[0] if ValidValue(info,fld,value[0]) else None, value[1])
        else:                 # type field: value -> (field,value)
          item = (fld, value[0] if ValidValue(info,fld,value[0]) else None)
        if item[1] == None: rts.append(item[0])
        items.append(item)
        if FluctCheck(info,item[0],item[1]): flucts.append(item[0])
      elif type(value) is dict:
        for one,val in value.items():
          if type(val) is dict or type(val) is tuple or type(val) is list: # recursive
            titems,trts,tflucts = ConvertValue(info, fld, val,rts=rts,flucts=flucts)
            items += titems; rts += trts; flucts += tflucts
          else: # add one to the 3 lists
            if not ValidValue(info,fld,val): val = None
            items.append((fld,val))
            if val == None: rts.append(fld)
            if FluctCheck(info,fld,val): flucts.append(fld)
      else:       # add one to the 3 lists
        if not ValidValue(info,fld,value): value = None
        items.append((fld,value))
        if value == None: rts.append(fld)
        if FluctCheck(info,fld,value): flucts.append(fld)
      return (items,rts,flucts) # list of tuples
            
    # collect sensors types in Dsensors from measurements data
    # SIDE EFFECT: convert to msmnt dict item "field": value or [("field",value[,unit])]
    # do not add 'sensor type: [(...),...] in data dict if there is no measurement data
    Dsensors = [] # find new sensor types from measurement data record part
    msmnt = {}; OoR = []; SVS = [] # measurement data, OutOfRange, None valued
    # data['data'] = {'version': '1.0', 'BME280': dict {'rv':2.1,}/list [('rv',2.1),]/tuple ('rv',2.1,'%',[0,1]), ...}
    if not 'data' in data.keys():  # probably an event
      # MyLogger.log(WHERE(),'ATTENT',"No data found in data record for measurment %s/%s" % (info['id']['project'],info['id']['serial']))
      data['data'] = {}
    thisData = copy.deepcopy(data['data'])
    for item, value in data['data'].items():   # pick up sensors from data part, convert values
      try:
        if item.lower() in ['version','timestamp']:
          if not item.lower() in data.keys():
             data[item.lower()] = str(value)
          continue
        elif item[:2] in ['L-']: # skip e.g. unused tags e.g. Libelium type/serial
          continue
        # check if sensor has measurements
        if value == None: continue
        if type(value) is list:
          if not value: continue
          if not type(value[0]) is tuple: # already in expected data format?
            tDR, tSVS, tOoR = ConvertValue(info, item, value)
            OoR += tOoR; SVS += tSVS
            if tDR:
              msmnt[item] = tDR
              Dsensors.append(item)
        elif type(value) is dict:
          if not value: continue
          new = []
          for one, val in value.items(): # (val,unit) or [val,unit] cases (To Do: convert unit)
            tDR, tSVS, tOoR = ConvertValue(info, one, val)
            new += tDR; OoR += tOoR; SVS += tSVS
          # if not new: log or raise ValueError("Exchange data format error for %s" % item)
          if new:
            msmnt[item] = new  # if nothing skip item and value(s)
            Dsensors.append(item)
        else: continue
      except Exception as e:
        MyLogger.log(WHERE(True),'DEBUG','Kit %s/%s generates non std data: %s.' % (info['id']['project'],info['id']['serial'],str(data['data'])) )
        MyLogger.log(WHERE(True),'ERROR','Kit %s/%s generates data error: %s.' % (info['id']['project'],info['id']['serial'],str(e)) )
    data['data'] = msmnt
    Dsensors = set(Dsensors)
    rtsMsg += LogInvalids(info)  # 'malfunctioning' sensors: out of band + temp == 0.0
    if OoR:                      # sensors only producing static values
      rtsMsg.append('Static value sensors ' + ', '.join(set(OoR))) # artifacts
    #if SVS: # disabled for now  # None valued measurements
    #  rtsMsg.append('Sensors with None value: ' + ', '.join(set(SVS))) # artifacts

    # update Sensors column sensors with new sensors found now
    # RESTRICTION: we allow only one sensor type per category
    Update = False
    # add found new sensor types.
    for one in Dsensors:
      try: UpdateKnownTypes(info['sensors'],one)
      except: pass
    new = set(getTypes(info['sensors'],key='type'))
    if new ^ DBsensors:
      rtsMsg += ["Update sensor types: '%s'" % ','.join(list(new))] 
      DBchanges['sensors'] = [DBsensors,new]
    return (len(Dsensors),rtsMsg)   # nr sensors with data, artifacts

# search record for gateway with best [value,min,max] rssi & snr, ID and ordinates
def GTWstrength(snr,rssi):
    WRSSI = 0.2
    WSNR = 10
    return WSNR*snr+WRSSI*rssi

def BestGtw(gateways):
    # weight values for best calculation search

    try:
      if not type(gateways) is list: return None
    except: return None
    strength = -1000; gtws = []; best = None
    for one in gateways: # get weighted best gateway signal
        gwSet = set(['gtw_id','rssi','snr']) # minimal gtw info needed to compare
        if len(set(one.keys()) & gwSet) != len(gwSet): continue
        if WSNR*one['snr']+WRSSI*one['rssi'] > strength:
          strength = GTWstrength(one['snr'],one['rssi'])
          best = one['gtw_id']
        location = None
        try: location = one['geohash']
        except:
          try: location = MyGPS.convert2geohash([one['latitude'],one['longitude']])
          except: pass
        # rssi/snr: [ min, max, value ]
        if not location:
          gtws.append([one['gtw_id'], [one['rssi'],one['rssi'],one['rssi']], [one['snr'],one['snr'],one['snr']]])
        else: gtw.append([one['gtw_id'], [one['rssi'],one['rssi'],one['rssi']], [one['snr'],one['snr'],one['snr'],location]])
    return (gtws,best,strength)

# handle event and/or meta information in data part, usually obtained via LoRa TTN port 3
# 'meta': {'dust': 'PMS7003', 'version': 'V0.5', 'meteo': 'BME680', 'gps': 'NEO-6'}
# updates Sensors when needed for sensor types and version
def MetaHasVersion(info,version, DBchanges):
    version = '' if not version else 'V'+str(version)
    try: prev = str(info['version'])
    except: prev = None
    if version != str(prev):
      if prev: del info['version']
      if version: info['version'] = str(version)
      DBchanges['description'] = [prev,version]
      return ["Update firmware %s" % version]
    return []

# update cache element with best gateways from record.
# cache info['gtw'] will have list of gateways during cache time:
# cache list is sorted by best first
# list of [id, , geohash gtw location, rssi and snr stats [cur,min,max]]
def GTWstat(info,data):
    try: gtws,best,strength = BestGtw(data['net']['gateways']) # get best used gateway
    except: return False
    # see if we have first LoRa signal strength
    # per gateway: [gtwID, geohash, [rssi,min,max], [snr,min,max]]
    def element(iterable):
      try: return GTWstrength(iterable[3][0],iterable[2][0]) # snr,rssi
      except: return 0

    try:
      if not info['gtw']:
        info['gtw'] = gtws
        gtws = []
    except:
      info['gtw'] = gtws
      gtws = []

    for gtw in gtws:
      Fnd = False
      for indx in info['gtw']:
        if indx[0] != gtw[0]: continue
        for j in 1,2:
          indx[j][0] = gtw[j][0] # last strength
          if indx[j][1] < gtw[j][1]: indx[j][1] = gtw[j][1]
          else: indx[j][2] = gtw[j][2]
        Fnd = True; break
      if not Fnd: info['gtw'].append(gtw)
    if not info['gtw']: del info['gtw']
    elif len(info['gtw']) > 1: # sort on best
      info['gtw'].sort(key=element, reverse=True)
    try: del data['net']  # ['gateways'] # net input info is not needed any more
    except: pass
    try: del data['data']['net']  # ['gateways'] # net input info is not needed any more
    except: pass
    return True

# get out of band value generating sensors and log once in 100 times
def LogInvalids(info):
    invalids = []; log = False
    try:
      for one, value in info['invalids'].items():
        if not info['invalids'][one] % 100: # log or again after a while
          log = True
        invalids.append((one,info['invalids'][one]))
    except: return []
    if invalids:
      if log:
        MyLogger.log(WHERE(),'ATTENT','Kit %s_%s generates for sensors %s out of band value(s).' % (info['id']['project'],info['id']['serial'],','.join(["%s (%dX)" % (a[0],a[1]+1) for a in invalids])))
      return ["Sensor(s) '%s' have Out of Band values" % ','.join([a[0] for a in invalids])]
    return []

# convert 'sensors' key into a list of refs.
# Return list of refs to sensor type descr dicts (type, fields, units, calibrations) or sensor type names
def Data2Frwrd(info, data):
    timing = None; now = int(time())
    rtsMsg = []                              # artifacts (remarks) to be returned with
    DBchanges = {}                           # changes to be made in Sensors DB table

    try: info['count'] += 1
    except: return (info,{},['info invalid'])

    # maybe a datagram from unknown wild kit
    rts = KnownKit(info)
    if rts: return (info, {},[rts])

    # is this kit restarting after some time not seen or first measurement data?
    try: rtsMsg += IsRestarting((now-info['last_seen'] if info['last_seen'] else None), info)
    except: pass

    # if measurement kit is disabled, skip forwarding
    try:
      rts = kitIsEnabled(info,data)
      if rts: return(info,{},rts)
    except: pass

    if not data or not type(data) is dict:   # no data to forward, skip silently
      return (info,{},["Measurement data format error"])

    # define timestamp when needed           # get best timestamp for this datagram
    try: timestamp = data['timestamp']
    except: data['timestamp'] = timestamp = int(time())

    # collect artifacts
    rtsMsg += HasNewHomeGPS(info, data) # has new home location or is in repair?
    try:
      data['meta']                           # handle meta data
      try:
        if timestamp > data['meta']['timestamp']:
          timestamp = data['meta']['timestamp']
          data['timestamp'] = timestamp                # set timestamp data record
        del data['meta']['timestamp']                  # clean up
      except: pass
      rtsMsg += HasEvent(info, data['meta'])           # it is an event
      # check sensor types/firmware version info for updates
      try:
        rtsMsg += MetaHasVersion(info,data['meta']['version'],DBchanges)
      except: pass
      if not data['meta']: del data['meta']            # clean up
    except: pass
            
    # handle communcation channel used via net key
    # gateway used statistics: collect/update used gateways from datagram
    GTWstat(info,data)

    # check for out of range values, static values, finally if record has measurements
    try:
      HsM, trts = HasMeasurements(info,data,DBchanges) # returns data sensors, artifacts
      rtsMsg += trts
    except Exception as e:
      HsM = 0; rtsMsg.append("Has measurements error")
      MyLogger.log(WHERE(True),'ERROR',"Exception '%s' raised with HasMeasurements() on %s/%s data '%s'" % (str(e),info['id']['project'],info['id']['serial'], str(data)))
    rtsMsg = sorted(list(set(rtsMsg)))# sorted list of artifacts

    if DBchanges: updateSensorsTbl(info,DBchanges)
    if not HsM: # no sensor measurements in this record
      info['last_seen'] = now
      return (info,{},rtsMsg)
    else: # has sensor measurements in this record
      # Is there a need to throttle the kit data production?
      rts = IsBehavingKit(info,now)
      if rts:
        rtsMsg.append(rts)
        return (info,{},rtsMsg)
      else:
        info['last_seen'] = now
        return (info,data,['Forward data']+rtsMsg)  # RETURN info,data,artifacts

      
# get a data record from input queue and forward it
ErrorCnt = 0
def GetDataRecord():
    global Conf, TelegramCnt, Resources, ErrorCnt
    if not Conf['input']:
      MyLogger.log(WHERE(True),'ERROR','No input resource available. Exiting.')
      return (None,None,['No input resources'])  # artifact
    # yet on only handle one input channel of TTN MQTT
    while True:
      data = None; info = None
      try:
        (info, data) = Resources.GetData()
        if not info and data:
          try: info = str(data['id'])
          except:
            try: info = "%s/%s" % (data['net']['TTN_app'],data['net']['TTN_id'])
            except: info = 'Unknown ID'
          MyLogger.log(WHERE(True),'ATTENT',"Skipping record from not registrated %s" % info)
          continue   # no cached info, probably not registrated
        if data == None:
          return (info,data,['End of iNput Data']) # artifact
        if not type(data) is dict or not data:
          # raise IOError("Wrong error type or empty data record received")
          MyLogger.log(WHERE(True),'ERROR',"Wrong error type or empty data record received")
          if ErrorCnt > 20:
            MyLogger.log(WHERE(True),'CRITICAL','Subscription failed Mid: %s. Aborted.' % str(data))
            return (None,None,['Fatal error on subscriptions']) # artifact
          ErrorCnt += 1; sleep(1) # slow down a bit on error
          continue
        try: info['CatRefs']
        except:
          try: info['CatRefs'] = Conf['CatRefs']
          except: info['CatRefs'] = [] 
        TelegramCnt += 1
        ErrorCnt = 0
        break
      except IOError as e:
        if ErrorCnt > 20:
            MyLogger.log(WHERE(True),'ERROR','Fatal input errors: Last erreor input failed with error: %s. Aborting.' % str(e))
            return (None,None,['Too many input errors'])
      # watch dog should restart collector after 5 minutes.
      except Exception as e:
        MyLogger.log(WHERE(True),'ERROR','Input broker is failing Mid: %s.\nSlowing down.' % str(e))
      ErrorCnt += 1
      sleep(10)

    # convert fields and values to MySense ident/data record
    return Data2Frwrd(info, data)

# MAIN part of MQTT The Things Network Broker #######################

# default configure settings for Conf dict and Channels
# make changes for your local (default) situation
# in MyDatacollector.conf.json configuration file.
# DEBUG, file, init file, output channels, etc can be overwritten via CLI arguments
def Configure():
    global Conf      # configuration items
    global Channels  # output channels eg database, forwarding data, console, ...
    # next json will overwrite default configuration settings
    Conf['initfile'] = 'MyDatacollector.conf.json' # meta identy data for sensor kits
    Conf['from'] = 'Notice from MySense data collector <mysense@localhost>'
    Conf['SMTP'] = 'localhost'
    Conf['input'] = [] # list of input brokers or files
    Conf['MyDB'] = {}  # dictionary with database info and credentials
    # Conf['DEBUG'] = True  # print stderr output channel actions

    # outpout channels for data
    # module: None load module on output True, 0 load module, other: module loaded
    Channels = [
        {   'name': 'logger', 'timeout': time()-1, # logger must be first in list
            'Conf': {
                'level': 'INFO', 'file': sys.stderr, 'print': True,
                'date': False, # prepend with timing
                'monitor': False,  # monitoring correct publish data
                # print=True colorize on output, file=filename or file=fifo=filename named pipe
            }
        },
        {   'name': 'database', 'script': 'MyDB', 'module': 0, # 0 enable nodes info export to DB
            'timeout': time()-1,
            'Conf': {
                # use credentials from environment
                'hostname': None, 'database': 'luchtmetingen', # overwritten by DB, DBHOST
                'user': None, 'password': None, # overwritten bij DBUSER, DBPASS
                'monitor': False,  # monitoring correct publish data
                'DEBUG': False
            }
        },
        {   'name': 'monitor', 'timeout': time()-1, # build in module
            'Conf': {
                'output': False, 'file': sys.stdout, 'print': True,
                'date': True, # prepend with timing
                'monitor': False,  # monitoring correct publish data
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
            }
        },
        {   'name': 'archive', 'script': 'MyARCHIVE', 'module': None,
            'timeout': time()-1,
            'Conf': {
                'output': True, 'timeout': time()-1,
                'file': sys.stdout, 'print': True,
                'monitor': False,  # monitoring correct publish data
                'DEBUG': False,    # do not insert data into measurements table
            }
        },
        {   'name': 'Community', 'script': 'MyCOMMUNITY', 'module': None,
            'timeout': time()-1,
            'Conf': {
                'output': True,
                'id_prefix': "TTN-", # prefix ID prepended to serial number of module
                'community': 'https://api.luftdaten.info/v1/push-sensor-data/', # api end point
                'timeout': 3*15,  # wait timeout on http request result
                # expression to identify serials subjected for data to be forwarded
                'active': True,    # output to sensors.community is also activated
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
        if arg in ['help','-help','-h']:
          print(__HELP__); exit(0)
        Match =  re.match(r'\s*(?P<channel>community:|console:|archive:|monitor:|notices:)?(?P<key>[^=]+)=(?P<value>.*)', arg, re.IGNORECASE)
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
                CMatch = re.match(r'(file|initfile|noticefile|smtp|from|debug|calibrate)',Match['key'], re.IGNORECASE)
                if CMatch:
                    if Match['key'].lower() in ['smtp','debug','file']:
                        Conf[Match['key'].upper()] = Match['value'].split(',') if type(Conf[Match['key'].upper()]) is list else  Match['value']
                        MyLogger.log(WHERE(),'INFO',"New value Conf[%s]: %s\n" %(Match['key'].upper(),str(Match['value'])))
                    elif Match['key'].lower() == 'calibrate':
                        Conf['CalRefs'] = Match['value'].split(',')
                        MyLogger.log(WHERE(),'INFO',"New value Conf[%s]: %s (sensor types as ref to calibrate)\n" %('CalRefs',str(Match['value'])))
                    else:
                        Conf[Match['key']] = Match['value'].split(',') if type(Conf[Match['key'].upper()]) is list else  Match['value']
                        MyLogger.log(WHERE(),'INFO',"New value Conf[%s]: %s\n" %(Match['key'],str(Match['value'])))
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
              from lib import MyPrint
              fifo = False
              if type(Channels[indx]['Conf']['file']) is str:
                if Channels[indx]['Conf']['file'].find('fifo=') == 0:
                  fifo = True
                  Channels[indx]['Conf']['file'] = Channels[indx]['Conf']['file'][5:]
              #monitor = MyPrint.MyPrint(output=Channels[indx]['Conf']['file'], color=Channels[indx]['Conf']['print'], fifo=fifo, date=False)
              monitor = Channels[indx]['Conf']
              monitor['output'] = MyPrint.MyPrint(output=Channels[indx]['Conf']['file'], color=Channels[indx]['Conf']['print'], fifo=fifo, date=False)
              if not 'monitor' in Conf.keys() or not Conf['monitor']:
                Conf['monitor'] = '.*'
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
            sys.stderr.write("Wrong logging level '%s', reset to WARNING\n" % MyLogger.Conf['level'])
            MyLogger.Conf['level'] = 'WARNING'
          MyLogger.log(WHERE(),'INFO',"Starting %s, logging level '%s'" % (WHERE(),MyLogger.Conf['level']))
          continue
        elif Channels[indx]['name'] == 'database':
          for item in Channels[indx]['Conf'].keys():
            MyLogger.Conf[item] = Channels[indx]['Conf'][item]
          continue
        if Channels[indx]['Conf']['output']:
          filterMsg = 'Output NOT filtered'
          if 'projects' in Channels[indx]['Conf'].keys() and 'serials' in Channels[indx]['Conf'].keys():
            filterMsg = "Output FILTER: '%s'" %  (Channels[indx]['Conf']['projects'] + '_' +  Channels[indx]['Conf']['serials'])
          MyLogger.log(WHERE(),'INFO','Output for "%s":\n\tOutput channel is %s\n\t%s' % (Channels[indx]['name'], 'enabled', filterMsg))
        else:
          MyLogger.log(WHERE(),'INFO','NO output for "%s":\n\tOutput channel is %s' % (Channels[indx]['name'], 'DISABLED'))
        if not 'script' in Channels[indx].keys():
          continue
        Channels[indx]['filter'] = None
        try:
            Channels[indx]['filter'] = re.compile(Channels[indx]['Conf']['projects'] + '_' + Channels[indx]['Conf']['serials'])
        except: pass
        Channels[indx]['net'] = {'module':False,'connected':Channels[indx]['Conf']['output']}
        if (not Channels[indx]['Conf']['output']) and (Channels[indx]['module'] == None):
          continue
        if ('module' in Channels[indx].keys()) and not Channels[indx]['module']:
          # if not (Channels[indx]['module'] == None and ('output' in Channels[indx]['Conf'].keys) and not Channels[indx]['Conf']['output']):
          try:
            if Channels[indx]['script'] == 'MyDB':
              Channels[indx]['module'] = DB
            elif Channels[indx]['script'] == 'MyCONSOLE':
              from lib import MyCONSOLE
              Channels[indx]['module'] = MyCONSOLE
              MyCONSOLE.Conf['DB'] = DB
              try:
                 if MyCONSOLE.Conf['STOP']: __stop__.append( MyCONSOLE.Conf['STOP'] )
              except: pass
              MyCONSOLE.__version__ = MyCONSOLE.__version__.replace('0.',' %s-' % __version__)
            elif Channels[indx]['script'] == 'MyARCHIVE':
              from lib import MyARCHIVE
              Channels[indx]['module'] = MyARCHIVE
              MyARCHIVE.Conf['DB'] = DB
              try:
                 if MyARCHIVE.Conf['STOP']: __stop__.append( MyARCHIVE.Conf['STOP'] )
              except: pass
              MyARCHIVE.__version__ = MyARCHIVE.__version__.replace('0.',' %s-' % __version__)
            elif Channels[indx]['script'] == 'MyCOMMUNITY':
              from lib import MyCOMMUNITY
              Channels[indx]['module'] = MyCOMMUNITY
              try:
                 if MyCOMMUNITY.Conf['STOP']: __stop__.append( MyCOMMUNITY.Conf['STOP'] )
              except: pass
              MyCOMMUNITY.Conf['DB'] = DB
              MyCOMMUNITY.__version__ = MyCOMMUNITY.__version__.replace('0.',' %s-' % __version__)
            else:
              MyLogger.log(WHERE(True),'CRITICAL','Unconfigured module %s' % Channels[indx]['script'])
              EXIT(1)
            if 'log' in Channels[indx]['module'].Conf.keys():
              Channels[indx]['module'].Conf['log'] = MyLogger.log # one log thread
            Channels[indx]['net']['module'] = True
          except:
            MyLogger.log(WHERE(True),'CRITICAL','Unable to load module %s' % Channels[indx]['script'])
            EXIT(1)
        for item in Channels[indx]['Conf'].keys():
          if Channels[indx]['module']:
            Channels[indx]['module'].Conf[item] = Channels[indx]['Conf'][item]
          Channels[indx]['errors'] = 0
        # end of channel update
    except ImportError as e:
      MyLogger.log(WHERE(True),'ERROR','One of the import modules not found: %s' % e)
      return False
    except Exception as e:
      MyLogger.log(WHERE(True),'ERROR','Exception in conf update with %s' % str(e))
      return False
    return True

# main run loop: collect measurement data records, and forward them to output channels.
def RUNcollector():
    global  Channels, debug, monitor, Conf
    error_cnt = 0; inputError = 0
    # configure MySQL luchtmetingen DB access
    while 1:
        if inputError > 10:
            MyLogger.log(WHERE(True),'WARNING','Slow down uploading from broker(s)')
            sleep(5*60)
        if (error_cnt > 20) or (inputError > 20):
            MyLogger.log(WHERE(True),'ERROR','To many input errors. Stopped broker')
            sendNotice('Too many broker server input errors. Suggest to restart the data collecting server %s' % socket.getfqdn(),info=None,all=False)
            break
        record = {}; info = None
        try:
            (info,record,artifacts) = GetDataRecord()
            if debug:
                MyLogger.log(WHERE(),'DEBUG',"Record info: %s" % str(info))
                MyLogger.log(WHERE(),'DEBUG',"Record record data: %s" % str(record))
                MyLogger.log(WHERE(),'DEBUG',"Record artifacts: %s" % str(artifacts))
            # data record example: info (dict), record (dict), artifacts (list)
            #
            # info:
            # {'count': 1,
            #  'id': {'project': u'SAN', 'serial': u'b4df4e621b31'},
            #  'DATAid': u'SAN_b4e6b32df41b31',
            #  'TTNtableID': 1590665967,
            #  'valid': 1,
            #  'SensorsID': 1596373187,
            #  'active': 1,
            #  'Luftdaten': u'b4e6b32df411',
            #  'WEBactive': 1,
            #  'sensors': [
            #    {'category': u'dust',
            #     'fields': ((u'pm1', u'ug/m3'), ... , (u'grain', u'um')),
            #     'type': u'PMSx003', 'match': u'PMS.003',
            #     'producer': u'Plantower',
            #     'ttl': 1630373493},
            #    {'category': u'meteo',
            #     'fields': ((u'temp', u'C'), ... , (u'aqi', u'%')),
            #     'type': u'BME680', 'match': u'BME680',
            #     'producer': u'Bosch',
            #     'ttl': 1630373493},
            #    {'category': u'gps',
            #     'fields': ((u'geohash', u'geohash'), (u'alt', u'm')),
            #     'type': u'NEO-6', 'match': u'NEO(-[4-9])*',
            #     'producer': u'NEO',
            #     'ttl': 1630373493}],
            #  'location': u'u1hjtzqdwm',
            #  'MQTTid': u'20180221a1597z/blwvc-31b1',
            #  'unknown_fields': [],
            #  'FromFILE': True,
            #  'interval': 240,
            #  'gtw': [[u'gateway_sint_anthonis_001', [-103, -103, -103], [7.75, 7.75, 7.75]]],
            #  'ttl': 1630351881,
            #  'last_seen': 1627828712}
            #
            # record: {
            #  'timestamp': 1629463231,
            #  'data': {
            #   'BME680': [(u'rv', 69.3), (u'luchtdruk', 1000), (u'gas', 32644), (u'temp', 12.8)],
            #   'PMS7003': [('pm05_cnt', 465.4), (u'pm10', 4.8), ... , (u'pm1', 1.8)]},
            #   'id': {'project': u'SAN', 'serial': u'b4e62df4b311'}}
            # artifacts: [
            #  'Forward data',                   'Start throttling kit: %s',
            #  'Skip data. Throttling kit.',     'Unknown kit: %s',
            #  'Unregistered kit: %s',           'MQTT id:%s, %s kit. Skipped.',
            #  'Raised event: %s.',              'Updated home location',
            #  'Kit removed from home location', 'New kit',
            #  'Restarted kit',                  'Out of Range sensors: %s',
            #  'Static value sensors: %s',       'Updated sensor types: %s -> %s',
            #  'Measurement data format error',  'No input resources',
            #  'End of iNput Data',              'Fatal error on subscriptions',
            # ]

            if record == None:
              MyLogger.log(WHERE(),'INFO','Finish: %s' % ', '.join(artifacts))
              break # no more records
            if not 'count' in info: # valid info or record?
              MyLogger.log(WHERE(),'INFO','Skipping record %s' % str(record))
              continue
        except ValueError as e:
            err = str(e)
            if err.find('I/O operation on closed file') >= 0:
                MyLogger.log(WHERE(),'INFO','EOF on input file %s' % Conf['FILE'])
                return True
            else:
                inputError += 1
                MyLogger.log(WHERE(True),'INFO','Get get record error: %s (skipped)' % err)
            continue
        except Exception as e:
            PrintException()
            # sys.stderr.write(traceback.format_exc())
            MyLogger.log(WHERE(True),'INFO','Get data failed with %s' % str(e))
            # sys.stderr.write("FAILED record: %s" % str(record))
            inputError += 1
            continue
        if (not type(record) is dict) or (not type(info) is dict):
            MyLogger.log(WHERE(True),'ATTENT','Data failure from LoRaWan data concentrator')
            error_cnt += 1
            continue
        elif not 'id' in info.keys():
            MyLogger.log(WHERE(True),'DEBUG','Undefined record from LoRaWan data concentrator')
            continue
        sentOne = False; inputError = 0
        if len(record) and 'Forward data' in artifacts: frwrd = True
        else:
          frwrd = False
          MyLogger.log(WHERE(True),'DEBUG',"No measurements data for %s/%s, %s." % (info['id']['project'],info['id']['serial'], 'no artifacts' if not artifacts else ';artifacts: "'+', '.join(artifacts)+'"') )
        if monitor:
          if type( Conf['monitor'] ) is str:
            Conf['monitor'] = re.compile(Conf['monitor'])
          try: MQTTid = info['MQTTid'].split('/')[1]
          except: MQTTid = 'None'
          try: TBLid = '%s_%s' % (info['id']['project'], info['id']['serial'])
          except: TBLid = 'None' 
          if Conf['monitor'].match(TBLid):
            try: timestamp = int(record['timestamp'])
            except: timestamp = int(time())
            try: sensors = ','.join([sensors for sensors in record['data'].keys()])
            except: sensors = ''
            try: NrGtws = ' %d gtws' % len(record['net']['gateways'])
            except: NrGtws = ''
            monitorPrt(
              "%-92.91s #%4.d%s" % (
                '%s %s (%s%s)%s' % (datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M"),
                    MQTTid, TBLid, '[%s]'%sensors if sensors else '',NrGtws),
                info['count'],
                (' at %dm%ds' % (info['interval']/60,info['interval']%60)) if (info['interval'] <= 60*60) else ''),
              BLUE)
            Acnt = 0
            for one in artifacts:
              if one == 'Forward data': continue
              if not Acnt: monitorPrt("    Artifacts:")
              monitorPrt("        %s" % one); Acnt += 1
            if not frwrd: monitorPrt("   Not forwarding data.",PURPLE)
        if not frwrd or not info or not record: continue

        for indx in range(len(Channels)): # forwarding record to an output channel
          try:
            if not Channels[indx]['module']: continue
            if not Channels[indx]['Conf']['output']: continue
          except: continue
          PublishMe = True; sentOne = True
          if time() < Channels[indx]['timeout'] or debug:
              PublishMe = False
          elif not info['active'] and PublishMe:
            # sent on active is decided by backend channel
            if info['count'] < 2:
              MyLogger.log(WHERE(True),'ATTENT',"Kit MQTT %s not activated, artifacts: %s. Forwarder may skip output." % (str(info['id']),', '.join(artifacts)))
              monitorPrt("Kit MQTT %s not activated, artifacts: %s. Forwarder may skip output." % (str(info['id']),', '.join(artifacts)),RED)
            elif not (info['count'] % 301):   # once a day a message
                MyLogger.log(WHERE(),'ATTENT',"Kit MQTT %s not activated, count: %s, artifacts: '%s'." % (info['count'], str(info['id']),', '.join(artifacts)))
                monitorPrt("Kit MQTT %s not activated, count: %s, artifacts: '%s'." % (info['count'], str(info['id']),', '.join(artifacts)),BLUE)

          if PublishMe:
              RsltOK = False
              try: RsltOK = Channels[indx]['Conf']
              except: pass
              Rslt = True; filtered = False
              try:
                  # check if output is filtered for this channel
                  if 'filter' in Channels[indx].keys() and Channels[indx]['filter'] and not Channels[indx]['filter'].match(info['id']['project']+'_'+info['id']['serial']):
                    filtered = True # do not publish if defined not to
                  if not filtered:
                    # supply output channel with a copy of data record
                    Rslt = Channels[indx]['module'].publish(
                          info = info,
                          data = copy.deepcopy(record),
                          artifacts = artifacts,
                          )
                  # handle normal result of the data forwarding
                  # failures without an exception event will not be queued for a retry
                  if type(Rslt) is bool and not filtered:
                    if Rslt == True:
                      if RsltOK and monitor:
                        try:
                          if Conf['monitor'].match(info['id']['project']+'_'+info['id']['serial']):
                            monitorPrt("    %s OK" % ('Forwarded record to %s:' % Channels[indx]['name']),LBLUE)
                        except: pass
                    else:
                      MyLogger.log(WHERE(),'ATTENT','Kit %s/%s data no output to %s' % (info['id']['project'],info['id']['serial'],Channels[indx]['name']))
                      monitorPrt("    %s no data output" % ('Forwarding record to %s:' % Channels[indx]['name']),BLUE)
                  elif Rslt:
                    if type(Rslt) is str or type(Rslt) is unicode:
                      MyLogger.log(WHERE(),'INFO','Kit %s/%s data output to %s: %s' % (info['id']['project'],info['id']['serial'],Channels[indx]['name'],str(Rslt)))
                      monitorPrt("    %s %s" % ('Attent forwarding record to %s, result ' % Channels[indx]['name'],str(Rslt)))
                    elif type(Rslt) is list:
                      try: Rslt = ', '.join(Rslt)
                      except: Rslt = str(Rslt)
                      if len(Rslt):
                        if RsltOK and monitor and not filtered:
                          try:
                            if Conf['monitor'].match(info['id']['project']+'_'+info['id']['serial']):
                              monitorPrt("    %s OK for %s" % ('Forwarding record to %s:' % Channels[indx]['name'],str(Rslt)),LBLUE)
                          except: pass
                      else:
                        MyLogger.log(WHERE(),'ATTENT','Kit %s/%s data output to %s: %s' % (info['id']['project'],info['id']['serial'],Channels[indx]['name'],str(Rslt)))
                        monitorPrt("    %-50.50s NO output." % (('Kit %s/%s data output to %s:' % (info['id']['project'],info['id']['serial'],Channels[indx]['name'])),str(Rslt)),RED)
                  else:
                    MyLogger.log(WHERE(),'ATTENT','Kit %s/%s data output failure to %s returned: %s' % (info['id']['project'],info['id']['serial'],Channels[indx]['name'],str(Rslt)))
                    monitorPrt("    %-50.50s UNKNOWN FAILURE" % ('Kit %s/%s data NO output to %s:' % (info['id']['project'],info['id']['serial'],Channels[indx]['name'])),RED)
                  if ('message' in Channels[indx]['module'].Conf.keys()) and Channels[indx]['module'].Conf['message']:
                    try:
                      sendNotice(Channels[indx]['module'].Conf['message'],info=info,all=False)
                      Channels[indx]['module'].Conf['message'] = ''
                    except: pass
                  Channels[indx]['errors'] = 0
                  Channels[indx]['timeout'] = time()-1
                  MyLogger.log(WHERE(True),'DEBUG','Sent record to outputchannel %s' % Channels[indx]['name'])

              # handle publishing exceptions for current output channel
              # try to redo the data forwarding later
              except Exception as e:
                MyLogger.log(WHERE(True),'ERROR','while sending record to %s: %s' % (Channels[indx]['name'],str(e)))
                Channels[indx]['errors'] += 1

          if Channels[indx]['errors'] > 20:
            if time() > Channels[indx]['timeout']: # throttle 5 mins
              # skip output for 5 minutes
              Channels[indx]['timeout']+5*50
              Channels[indx]['errors'] += 1
          if Channels[indx]['errors'] > 40:
            Channels[indx]['module']['Conf']['output'] = False
            MyLogger.log(WHERE(True),'ERROR','Too many errors. Loaded output channel %s: DISABLED' % Channels[indx]['name'])
            sendNotice('TTN MQTT Server %s: too many errors. Output channel %s: output is DISabled' % (socket.getfqdn(),Channels[indx]['name']),info=None,all=False)

        if not sentOne:
          MyLogger.log(WHERE(True),'ERROR','No output channel available. Exiting')
          monitorPrt("No output channels available. Exiting.",RED)
          break
    return True

if __name__ == '__main__':
    Configure()
    ImportArguments()
    if not UpdateChannelsConf():
        MyLogger.log(WHERE(),'CRITICAL','Error on Update Channel configurations.')
        EXIT(1)
    if not Initialize():
        MyLogger.log(WHERE(),'CRITICAL','Error on initialisation.')
        EXIT(1)
    try: RUNcollector()
    except Exception as e: 
        sys.stderr.write("EXITING by exception: %s\n" % str(e))
    # stop all threads with brokers
    EXIT(0)
