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

# $Id: MyCOMMUNITY.py,v 4.14 2021/10/26 14:03:43 teus Exp teus $

# TO DO: write to file or cache
# reminder: InFlux is able to sync tables with other MySQL servers

""" Publish measurements to Luftdaten.info
    Make sure to enable acceptance for publishing in the map of Luftdaten
    by emailing the prefix-serial and location details.
    Madavi is disabled due to too many connection problems.
    Relies on Conf setting by main program.
"""
__modulename__='$RCSfile: MyCOMMUNITY.py,v $'[10:-4]
__version__ = "0." + "$Revision: 4.14 $"[11:-2]
import re
import inspect
def WHERE(fie=False):
   global __modulename__, __version__
   if fie:
     try:
       return "%s V%s/%s" % (__modulename__ ,__version__,inspect.stack()[1][3])
     except: pass
   return "%s V%s" % (__modulename__ ,__version__)

try:
    import sys
    if sys.version_info[0] >= 3: unicode = str
    import datetime
    from time import time
    import json
    import requests
    import signal
    from time import time
    import re
except ImportError as e:
    sys.exit("FATAL: One of the import modules not found: %s" % e)

# configurable options
__options__ = ['output','id_prefix', 'timeout', 'notForwarded','active','calibrate','DEBUG']

Conf = {
    'output': False,
    'hosts': ['community', ],    # 'madavi' deleted
    # defined by, obtained from Sensors Community: Rajko Zschiegner dd 24-12-2017
    'id_prefix': "MySense-",  # prefix ID prepended to serial number of module
    'community': 'https://api.luftdaten.info/v1/push-sensor-data/', # api end point
    'madavi':    'https://api-rrd.madavi.de/data.php', # madavi.de end point
    'notForwarded': r'(VW2017|test)_.*',    # expression to identify id's not to be forwarded
    'calibrate': True,   # calibrate values to default sensor type for Community pin nr
    'active': True,      # output to sensors.community maps is also activated
    'registrated': None, # has done initial setup
    'timeout': 3*30,     # timeout on wait of http request result in seconds
    'log': None,         # MyLogger log print routine
    'message': None,     # event message from this module, eg skipping output
    'DEBUG': False,      # debugging info
}

# ========================================================
# write data directly to a database
# =======================================================
# once per session registrate and receive session cookie
# =======================================================
# TO DO: this needs to have more security in it e.g. add apikey signature
def registrate():
    global Conf
    if Conf['registrated'] != None: return Conf['registrated']
    if not Conf['log']:
        try: from lib import MyLogger
        except: import MyLogger
        Conf['log'] = MyLogger.log
    # avoid too many HTTP request logging messages
    import logging
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    # req_log = logging.getLogger('requests.packages.urllib3')
    # req_log.setLevel(logging.WARNING)
    # req_log.propagate = True

    # skip some kits identified by reg expression
    Conf['notForwarded'] = re.compile(Conf['notForwarded'])
    Conf['registrated'] = True
    return Conf['registrated']

# send only a selection of possible measurements from the sensors
# Post meteo and dust data separately
# year 2020: Previous name of Sensors.Community was Luftdaten
def send2Community(info,values, timestamp=None):
    global __version__, Conf
    # the Luftdaten API json template
    # suggest to limit posts and allow one post with multiple measurements
    try:
      if not Conf['hosts']: return 'Forward to Sensors.Community not defined'
      hdrs = {
        'X-Sensor': Conf['id_prefix'] + str(info['Luftdaten']),
        # 'X-Auth-User': 'Content-Type: application/json',
      }
    except: return 'No ID to Sensors Community defined'
    postTo = []
    for url in Conf['hosts']: # Sensors.Community map (needs Luftdaten ID) and/or Madavi archive
      postTo.append(Conf[url])
    if not len(postTo): return "No server destination defined"
    try: ID = info['Luftdaten']
    except: ID = info['DATAid']

    pdata = {
        'software_version': 'MySense' + __version__,
        # to do: 'samples', 'signal', 'min_micro', max_micro'   ??
    }
    try: pdata['interval'] = info['interval']*1000
    except: pass
    if not timestamp:
      timestamp = time()
      try: timestamp = info['timestamp']
      except: pass
    # add .%f if msecs are needed (granulate is secs not msecs)
    pdata['timestamp'] = datetime.datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S")
    postings = [] # Sensors.Community and Madavi have same POST API interface
    # add measurements to postdata
    for pinNr,data in values.items():     # { 'pin nr': [(field,value), ...], ...}
        headers = hdrs.copy()
        headers['X-Pin'] = str(pinNr)
        postdata = pdata.copy()
        postdata['sensordatavalues'] = []
        if type(values[pinNr]) is list:
          for one in values[pinNr]:
            postdata['sensordatavalues'].append({ 'value_type': str(one[0]), 'value': one[1]})
        if not len(postdata['sensordatavalues']): continue
        postings.append((headers,postdata)) # type, POST header dict, POST data dict

    try:                                    # try to POST the data
        if not postings:
            Conf['log'](WHERE(True),'INFO',"No values for %s with postings: %s\n" % (str(headers['X-Sensor']),str(postings)))
            return False                    # no data to POST
        Rslt = post2Community(postTo,postings,ID)
        if not Rslt:
            Conf['log'](WHERE(True),'ERROR','HTTP POST connection failure')
            # sys.stderr.write("Failed X-Sensor %s with postings: %s\n" % (str(headers['X-Sensor']),str(postings)))
            raise IOError('HTTP POST connection failure')
    except Exception as e:
        raise IOError("Exception ERROR in post2Community as %s\n" % str(e))
    return Rslt
        
# seems https may hang once a while
import signal
def alrmHandler(signal,frame):
    global Conf
    Conf['log'](WHERE(True),'ATTENT','HTTP POST hangup, post aborted. Alarm nr %d' % signal)
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
    
# do an HTTP POST to [ Madavi.de, Luftdaten, ...]
Posts = {}
def PostError(key,cause,timeout=None):
   global Posts, Conf
   try:
       Conf['log'](WHERE(True),'ERROR',"For %s: %s" % (key,cause))
   except: pass
   if timeout: # no warnings case
       # madavi.de seems to forbid most traffic since May 2020, check every 2 days
       Posts[key] = { 'timeout':timeout + 60*60*(48 if key.find('madavi') > 0 else 1), 'warned': 6}
       return 
   elif not key in Posts.keys():
       Posts[key] = { 'timeout': int(time>()) + 60*60, 'warned': 1 }
   else:
       Posts[key]['warned'] += 1
       if Posts[key]['warned'] > 5: Posts[key]['timeout'] = int(time()) + 1*60*60

####### examples
# from: https://discourse.nodered.org/t/send-data-from-local-dust-sensor-to-lufdaten/25943/8 2021-09-12
# msg.headers = {},
# msg.headers['X-Auth-User'] = 'Content-Type: application/json',  
# 'X-Pin: 1' , 
# 'X-Sensor: esp8266-568371 ', 
# 
# {
#   "software_version": "NRZ- 2020129", 
#   "sampling_rate": null,                     # optional
#   "timestamp": "2020-01-02T09:29:41.300",    # optional else post timestamp in UTC ISO-8601
#   "sensordatavalues":[
#     {"value_type":"P1","value":"66.04"},     # optional add: "id": 123456789,
#     {"value_type":"P2","value":"53.32"}
#   ]
# }
#
# from: https://www.thethingsnetwork.org/forum/t/connection-from-ttn-node-to-luftdaten-api/33073/7
# var result = client.PostAsync(url.ToString(),
#    new StringContent("{\"sensor\": 16741, \"sampling_rate\": null,
#             \"timestamp\": \"2020-01-02 09:29:41\",
#             \"sensordatavalues\": [
#                {\"id\":12628208575, \"value\":\"1.00\", \"value_type\":\"temperature\" },
#                {\"value\":\"98.40\", \"id\":12628208576, \"value_type\":\"humidity\" }],
#             \"software_version\": \"123\" }")).Result;
#
# from: https://hmmbob.tweakblogs.net/blog/18950/push-data-to-luftdaten-and-opensensemap-api-with-home-assistant
# 2021-09-11
# 
# # The BME280 pressure value in HA is in hPa - the APIs expect it in Pa, hence the 
# # multiplication of the value in the templates below.
# 
# # Push to Luftdaten API. Luftdaten uses headers to distinguish between different sensor
# # types, so we need to push twice. The X-Sensor header contains the sensorID from Luftdaten,
# # typically formatted as esp8266-12345678 or similar.
# send_luftdaten_pm:
#   url: https://api.sensor.community/v1/push-sensor-data/
#   method: POST
#   content_type: 'application/json'
#   headers:
#     X-Pin: 1  ## This tells Luftdaten that it is SDS011 data
#     X-Sensor: !secret luftdaten_x_sensor
#   payload: >
#     {
#       "software_version": "HomeAssistant-{{ states('sensor.current_version') }}",
#       "sensordatavalues":[
#         {"value_type":"P1","value":"{{ states('sensor.particulate_matter_10_0um_concentration') }}"},
#         {"value_type":"P2","value":"{{ states('sensor.particulate_matter_2_5um_concentration') }}"}
#       ]
#     }
# send_luftdaten_tph:
#   url: https://api.sensor.community/v1/push-sensor-data/
#   method: POST
#   content_type: 'application/json'
#   headers:
#     X-Pin: 11  ## This tells Luftdaten that it is BME280 data
#     X-Sensor: !secret luftdaten_x_sensor
#   payload: >
#     {
#       "software_version": "HomeAssistant-{{ states('sensor.current_version') }}",
#       "sensordatavalues":[
#         {"value_type":"temperature","value":"{{ states('sensor.bme280_temperature') }}"},
#         {"value_type":"pressure","value":"{{ states('sensor.bme280_pressure') | float * 100 }}"},
#         {"value_type":"humidity","value":"{{ states('sensor.bme280_humidity') }}"}
#       ]
#     }
# 
# # Push to Madavi. This is related to Luftdaten and stores data for use in Grafana.
# send_madavi:
#   url: https://api-rrd.madavi.de/data.php
#   method: POST
#   content_type: 'application/json'
#   headers:
#     X-Pin: 0
#     X-Sensor: !secret luftdaten_x_sensor
#   payload: >
#     {
#       "software_version": "HomeAssistant-{{ states('sensor.current_version') }}", 
#       "sensordatavalues":[
#         {"value_type":"SDS_P1","value":"{{ states('sensor.particulate_matter_10_0um_concentration') }}"},
#         {"value_type":"SDS_P2","value":"{{ states('sensor.particulate_matter_2_5um_concentration') }}"},
#         {"value_type":"BME280_temperature","value":"{{ states('sensor.bme280_temperature') }}"},
#         {"value_type":"BME280_pressure","value":"{{ states('sensor.bme280_pressure') | float * 100 }}"},
#         {"value_type":"BME280_humidity","value":"{{ states('sensor.bme280_humidity') }}"}
#       ]
#     }
# 
# # Push to OpenSenseBox / OpenSenseMap. The url !secret contains the openSenseBox API url,
# # which looks like https://api.opensensemap.org/boxes/<<yoursenseboxid>>/data
# # The input_text items contain the sensor-IDs you need to publish the data to the API.
# # You can find those on your SenseBox page on https://opensensemap.org/account
# post_opensensebox:
#   url: !secret opensensebox_api_url
#   method: post
#   headers:
#     content-type: "application/json; charset=utf-8"
#   payload: >-
#     {
#       "{{ states('input_text.opensensebox_sensorid_temp') }}": "{{ states('sensor.bme280_temperature') }}",
#       "{{ states('input_text.opensensebox_sensorid_press') }}": "{{ states('sensor.bme280_pressure') | float * 100 }}",
#       "{{ states('input_text.opensensebox_sensorid_hum') }}": "{{ states('sensor.bme280_humidity') }}",
#       "{{ states('input_text.opensensebox_sensorid_pm25') }}": "{{ states('sensor.particulate_matter_2_5um_concentration') }}",
#       "{{ states('input_text.opensensebox_sensorid_pm10') }}": "{{ states('sensor.particulate_matter_10_0um_concentration') }}"
#     }
#######

# to each element of array of POST URL's, 
#    POST all posting elements tuple of type, header dict and data dict
def post2Community(postTo,postings,ID):
    global Conf, Posts, sense_table
    def getCategory(PinNr):
        global sense_table
        ctgr = ''
        for cat, types in sense_table.items():
          for nr in types['types'].values():
            if nr == PinNr:
              ctgr = cat; break
          else: continue
          break
        return ctgr
        
    # debug time: do not really post this
    Conf['log'](WHERE(True),'DEBUG',"HTTP POST ID %s to: %s" % (ID,', '.join(postTo)))
    for data in postings:
      Conf['log'](WHERE(True),'DEBUG',"Post headers:   %s" % str(data[0]))
      Conf['log'](WHERE(True),'DEBUG',"Post json data: %s" % str(json.dumps(data[1])))
    rts = {}
    for url in postTo:
      host = url.find('://')
      if host > 0: host = url[host+3:url.find('/',host+3)]
      else: # just make a guess
        host = ('api.luftdaten.info' if url.find('luftdaten') > 0 else 'api-rrd.madavi.de')
      key = ID + '@' + host.split('.')[1]
      # avoid holding up other posts and input
      if key in Posts.keys():
        if int(time()) < Posts[key]['timeout']:
          if Posts[key]['warned'] == 6:
            Conf['log'](WHERE(True),'ATTENT','HTTP too many connect errors: ID@URL %s skipping up to %s' % (key,datetime.datetime.fromtimestamp(Posts[key]['timeout']).strftime("%Y-%m-%d %H:%M")) )   
            if key.find('madavi') < 0: # if unimportant host no message
              Conf['message'] = 'HTTP POST connection failuring: ID@URL %s.\nSkip postages up to %s' % (key,datetime.datetime.fromtimestamp(Posts[key]['timeout']).strftime("%Y-%m-%d %H:%M"))
          if Posts[key]['warned'] > 5: # after 5 warnings just skip till timeout
            Posts[key]['warned'] += 1
            continue
        else: del Posts[key] # reset

      timeout = 6
      for data in postings:
        category = getCategory(int(data[0]['X-Pin']))

        if Conf['id_prefix'] != 'TTN-':  # TEST MODUS: do not POST
          sys.stderr.write("Post to: %s\n" % url)
          sys.stderr.write("Headers: %s\n" % str(data[0]))
          sys.stderr.write("Body (json data): %s\n" % str(json.dumps(data[1],indent=2)))
          sys.stderr.write("Timeout: %s secs\n" % str(timeout))
          try: rts[key].append(category)
          except: rts[key] = [category]
        else:

          try:                           # connect and POST to Sensors.Community
            prev = watchOn(host)         # set timeout to avoid long hang
            r = requests.post(url, json=data[1], headers=data[0], timeout=timeout)
            Conf['log'](WHERE(True),'DEBUG','Post %s returned status: %d' % (host,r.status_code))
            #if not r.ok:
            #  sys.stderr.write("Luftdaten %s POST to %s:\n" % (ID,url))
            #  sys.stderr.write("     headers: %s\n" % str(data[0]))
            #  sys.stderr.write("     data   : %s\n" % str(json.dumps(data[1])))
            #  sys.stderr.write("     returns: %d\n" % r.status_code)
            if Conf['DEBUG']:
              if not r.ok:
                sys.stderr.write("Luftdaten ID %s POST to %s:\n" % (ID,url))
                sys.stderr.write("     headers: %s\n" % str(data[0]))
                sys.stderr.write("     data   : %s\n" % str(json.dumps(data[1])))
                sys.stderr.write("     returns: %d\n" % r.status_code)
              else:
                sys.stderr.write("%s POST %s OK(%d) to %s ID(%s).\n" % (host,ID,r.status_code,host,data[0]['X-Sensor']))
            if not r.ok:
              if r.status_code == 403:
                PostError(key,'Post %s to %s ID %s returned status code: forbidden (%d)' % (ID,host,data[0]['X-Sensor'],r.status_code), int(time())+2*60*60)
              elif r.status_code == 400:
                # PostError(key,'Not registered post %s to %s with ID %s, status code: %d' % (ID,host,data[0]['X-Sensor'],r.status_code),int(time())+1*60*60)
                PostError(key,'Not registered post %s to %s with header: %s, data %s and ID %s, status code: %d' % (ID,host,str(data[0]),str(json.dumps(data[1])),data[0]['X-Sensor'],r.status_code),int(time())+1*60*60)
                # raise ValueError("EVENT Not registered %s POST for ID %s" % (url,data[0]['X-Sensor']))
              else: # temporary error?
                PostError(key,'Post %s with ID %s returned status code: %d' % (ID,data[0]['X-Sensor'],r.status_code))
              break
            else: # POST OK
              if key in Posts.keys():
                Conf['log'](WHERE(),'ATTENT','Postage to %s recovered. OK.' % key)
                del Posts[key] # clear errors
              Conf['log'](WHERE(True),'DEBUG','Sent %s postage to %s OK.' % (ID,key))
              try: rts[key].append(category)
              except: rts[key] = [category]
          except requests.ConnectionError as e:
            if str(e).find('Interrupted system call') < 0: # if so watchdog interrupt
              PostError(key,'Connection error: ' + str(e))
          except requests.exceptions.Timeout as e:
            PostError(key,'HTTP %d sec request timeout POST error with ID %s' % (timeout,data[0]['X-Sensor']))
          except Exception as e:
            if str(e).find('EVENT') >= 0:
              raise ValueError(str(e)) # send notice event
            PostError(key,'Error: ' + str(e))
          if not watchOff(prev): # 5 X tryout, then timeout on this url
            PostError(key,'HTTP %d sec timeout error with ID %s' % (Conf['timeout'],data[0]['X-Sensor']))
            break  # no more POSTs to this host for a while
      # end of postings loop to one host
    # end of URL loop
    if rts:
      return ['%s (%s)' % (a,', '.join(v)) for (a,v) in rts.items() ]
      # return ['%s (%s)' % (a,', '.join(set(v))) for (a,v) in rts.items() ]
    return False

# publish argument examples
# info = {
#     'count': 1,
#     'id': {'project': u'SAN', 'serial': u'b4e62df4b311'},
#     'last_seen': 1627828712,
#     'interval': 240,
#     'DATAid': u'SAN_b4e62df4b311',
#     'MQTTid': u'201802215971az/bwlvc-b311',
#     'valid': 1,   # null in repair
#     'SensorsID': 1593163787, 'TTNtableID': 1590665967,
#     'active': 1,  # kit active
#     'Luftdaten': u'b4e62df4b311',
#     'WEBactive': 1,
#     'sensors': [
#       {  'category': u'dust', 'type': u'PMS7003', 'producer': u'Plantower',
#          'fields': ((u'pm25', u'ug/m3',[-1.619,1/1.545]), (u'pm10',u'ug/m3',[-3.760,1/1.157]),(u'grain', u'um')),
#       {  'category': u'meteo', 'type': u'BME680', 'producer': u'Bosch',
#          'fields': ((u'temp', u'C'), (u'aqi', u'%')),
#       {  'category': u'location', 'type': u'NEO-6', 'producer': u'NEO',
#          'fields': ((u'geohash', u'geohash'), (u'altitude', u'm')),
#       ],
#     'FromFILE': True,
#     'CatRefs': ['SDS011'],
#     'location': u'u1hjtzwmqd',
#   }
# record = {
#     'timestamp': 1629463231, 'version': '2.0.1',
#     'data': {
#        'BME680':  [(u'temp', 12.8)],
#        'PMS7003': [(u'pm1', 1.8),(u'pm25', 2.5)],   # has unknown field pm25
#     },
#   }
# artifacts = [  # all known ones
#     'Forward data',                   'Start throttling kit: %%s',
#     'Skip data. Throttling kit.',     'Unknown kit: %%s',
#     'Unregistered kit: %%s',          'MQTT id:%%s, %%s kit. Skipped.',
#     'Raised event: %%s.',             'Updated home location',
#     'Kit removed from home location', 'New kit',
#     'Restarted kit',                  'Out of Range sensors: %%s',
#     'Static value sensors: %%s',      'Change of sensor types: %%s -> %%s',
#     'Measurement data format error',  'No input resources',
#     'End of iNput Data',              'Fatal error on subscriptions',],
#  ]

# Luftdaten API nomenclature and ID codes:
# see eg https://github.com/opendata-stuttgart/sensors-software/blob/master/airrohr-firmware/defines.h
sense_table = {
    # "location": { "types": { 'NEO6M': pin 9 },
    #               "translate": {'GPS_lat': { 'latitude' },'GPS_lon': {'longitude'},
    #                        'GPS_alt': {'altitude'}, 'GPS_timestamp': {'timestamp'} }, }, # To be completed
    # "noise": { "types": { 'DNMS': pin 15 }, "translate": {'noise?': {'noise?','dB'}} }, # To Do
    "meteo": {
        # X-Pin codes as id used by Luftdaten for meteo sensors
        # from airrohr-firmware/ext_def.h
        "types": { # To Do: add calibration info from database table SensorTypes
            'BME280':  11,  # BME680 pin nr is a guess
            'DEFLT':   'BME280',  # for SHT3*, BME* use this as default
            'BMP280': 3,
            'DHT22':    7, 'HTU21D': 7, 'SHT31': 7,
            'DS18B20': 13,
        },
        'translate': {
            "temperature": {'temperature','temp','dtemp',},
            "humidity":    {'humidity','hum','rv','rh',},
            "pressure":    {'pres','pressure','luchtdruk',},
        }
    },
    "dust": {
        # X-Pin codes as id used by Luftdaten for dust sensors
        # TO DO: complete the ID codes used by Luftdaten
        "types": {
            'SPS30': 1,   # seems default if pm1 is needed to support
            'SDS011': 1,  # community does not calibrate towards DEFLT (historical reasons)
            'DEFLT':  'SPS30',  # for PMS, SPS, NPM use this as default
            'HPM': 25, 'PPD42NS': 5, 'SHINEY': 5,

            # To Do: calibration should come from DB table SensorTypes
            # calibration here is from summer Jun-Sep 2020 Vredepeel ca 9.000 samples
            # sensor type: (pin nr, { field: [Taylor seq], cache time to live), ...
            'PMSx003': (1,{'pm1': [1.099,1/1.835],'pm25':[1.099,1/1.835],'pm10':[-2.397,1/1.666]},0),
            'PMSX003': (1,{'pm1': [1.099,1/1.835],'pm25':[1.099,1/1.835],'pm10':[-2.397,1/1.666]},0),
            'PMS5003': (1,{'pm1': [1.099,1/1.835],'pm25':[1.099,1/1.835],'pm10':[-2.397,1/1.666]},0),
            'PMS6003': (1,{'pm1': [1.099,1/1.835],'pm25':[1.099,1/1.835],'pm10':[-2.397,1/1.666]},0),
            'PMS7003': (1,{'pm1': [1.099,1/1.835],'pm25':[1.099,1/1.835],'pm10':[-2.397,1/1.666]},0),
            # 'SDS011':  (1,{'pm25':[2.163,0.7645],'pm10':[1.689,0.6323]},0),
        },
        'translate': {
            "P0": {'pm1','pm1_atm','P0'},     # should be P01
            "P1": {'pm10','pm10_atm','P1'},   # should be P10
            "P2": {'pm2.5','pm25','P2'},      # should be P25
            "N05": {'pm5_cnt','N05'},         # dust count PM0.5
            "N1": {'pm1_cnt','N1'},           # dust count PM0.5
            "N25": {'pm25_cnt','N25'},        # dust count PM2.5
            "N4": {'pm4_cnt','N4'},           # dust count PM4
            "N10": {'pm10_cnt','N10'},        # dust count PM10
            # missing avg grain size, PMS: N03, N5
        }
    },
}

# update sense_table cached calibration info from database if possible
# returns (pin nr, { sensor type to be calibrated, Taylor seq }).
# To Do: maybe on failure should try again after a while
def getCalDB(SType,category):
    global Conf, sense_Table
    if not Conf['calibrate']: return {}
    try: entry = category['types']
    except: return None
    try:
      if not Conf['calibrate']:                                # do not calibrate
        try: return (entry[SType],{})
        except: return (entry[entry['DEFLT']],{})
      if type(entry[SType]) is int: return (entry[SType],{})   # has pin nr, no calibration
      elif type(entry[SType]) is tuple:                        # has pin nr, calibration, DB entry ttl
        if len(entry[SType]) > 2:
          if time() < entry[SType][2]: return entry[SType][:2] # pin,cal,ttl OK
          try:
            if not Conf['DB']: return entry[SType][:2]         # cannot use DB table for calibration info
          except: pass
      elif not entry[SType]: return None
    except: pass

    try: # try to get calibration from DB table SensorTypes
      refSType = None
      for one in entry.keys():
        if one != 'DEFLT' and entry[one] == entry[entry['DEFLT']]:
          refSType = one; break
      if not refSType:
        raise ValueError("Missing default sensor ref type %d" % refType)
      cals = {}
      flds = Conf['DB'].db_query("SELECT fields FROM SensorTypes WHERE product = '%s'" % SType, True)[0][0]
      if len(flds):
        flds = flds.split(';')
        # list of eg pm10,ug/m3,SDS011/-3.7600/0.8643|SPS30/-2.3970/0.6002|BAM1020/13.6900/0.2603
        for fld in flds:
          fld = fld.split(',')  # [field,unit,ref type/T1/T2]
          if len(fld) > 2: # has calibration info
             for cal in fld[2].split('|'):
                cal = cal.split('/')      # [ref sensor type, Taylor args ...]
                if cal[0].upper() != refSType.upper(): continue  # only need to info
                cals[fld[0]] = [float(a) for a in cal[1:]]
      entry[SType] = (entry[entry['DEFLT']],cals,int(time())+24*60*60)  # TTL one day
      return entry[SType][:2]
    except: pass
    return None

# return Taylor sequence correction
def Taylor(avalue,seq,positive=False):
    if avalue == None: return None
    if not seq: return avalue
    rts = 0; i = 0
    try:
      for v in seq:
        rts += v*avalue**i; i += 1
    except: rts = avalue
    return (rts if rts > 0.0 else 0.01) if positive else rts

# make the value a calibrated value
def getCal(calibrations,field,value,PM=False):
    if not type(calibrations) is dict: return value
    for one,cal in calibrations.items():
      if field.lower() == one.lower(): return Taylor(value,cal,positive=PM)
    return value

# turn values into a list of tuples (pin, field, value) to be sent
# calibrate the value if needed and instructed
def SensorData(SType,values,info):
    global sense_table        # DB cache with sensor type information
    rts = [] # list of (pin,field,value)
    Sflds = {}
    try:
      # forget sensor types not in info as dict
      for sens in info['sensors']:
        if not type(sens) is dict: continue
        if type(sens['match']) in [str,unicode]:
          sens['match'] = re.compile(sens['match'],re.I)
        if sens['match'].match(SType):
          Sflds = sens; break
    except: return []
    if not Sflds: return []
    try:
      s_tble_entry = sense_table[Sflds['category']]
      calibrations = []; pin = None
      pin, calibrations = getCalDB(SType,s_tble_entry)
      for val in values: # val = (sensor field,value,unit) # unit is optional
        #              (calibration seq, field, value, is dust?)
        field = None; value = val[1]
        value = getCal(calibrations,val[0],value,PM=(Sflds['category']=='dust'))
        try:
          for item, tr in s_tble_entry['translate'].items():
            # translate field name into Sensors Community field name
            if val[0] in tr:
              field = item; break
        except: pass
        if not field or not pin: continue  # field not supported, or pin not defined
        # we have now sensor Stype, field name, value, sensor type ref for calibration
        # Community API corrections
        if field == 'pressure': value = int(value*100)  # hPa -> Pa unit
        else: value = round(value,2)                    # API uses round 2 decimals
        rts.append((pin, field, value))
    except: return []
    return rts

# entry point to forward measurements to measurements table in the database
# returns:
#     True: OK stored, False: no data to be stored
#     string: failure reason on output
#     list of strings: ok : string which one of the sub output channels had result
# raised event on failure in eg connection, query error
skip = re.compile(r'(Skip data|Unregistered|Raised event|End of).*')
def publish(**args):
    global Conf, notMatchedSerials
    if (not 'output' in Conf.keys()) or (not Conf['output']):
        return "Sensor Community forwarding disabled"
    try:
      info = args['info']; data = args['data']; artifacts = args['artifacts']
      try:
        # do not forward data from input file in debug modus
        if info['FromFILE'] and Conf['DEBUG']: return True
      except: pass
    except: return "ERROR in publish() arguments"
    try: timestamp = data['timestamp']
    except: timestamp = None
    if 'data' in data.keys() and type(data['data']) is dict and len(data['data']):
      data = data['data']
    else: return False # no data to forward

    # skip records not to forward to Sensors.Community
    if not 'Forward data' in artifacts: return "Forwarding to Sensors.Community disabled"
    reasons = []
    for one in ['id','active','Luftdaten','valid']:
      try:
        if not info[one]: reasons.append('no '+one)
      except: reasons.append('not defined: %s' % one)
    if reasons:
      return "Disabled: '%s'" % ','.join(reasons)
    for one in artifacts:
      if skip.match(one): return "Sensors.Community skipping: %s" % str(one)

    if not registrate():  # initialize once
        Conf['log'](WHERE(True),'WARNING',"Unable to registrate the sensor.")
        return "ERROR Sensors.Community registration failure"

    try:
      if Conf['notForwarded'].match(info['id']['project']+'_'+info['id']['serial']):
        return "Forwarding to Sensors.Community disabled for %s" % (info['id']['group']+'_'+info['id']['serial'])
    except: return "ERROR no id defined for %s" % str(info['id'])

    # find sensor data to forward from the data record
    # to be done: wifi 'signal', min_micro, max_micro, samples, interval
    data2send = {}
    for one,values in data.items():
       for item in SensorData(one,values,info):
         try: data2send[item[0]].append(item[1:])
         except: data2send[item[0]] = [item[1:]]
    if data2send: return send2Community(info,data2send,timestamp)
    return False

# test main loop
if __name__ == '__main__':
    Conf['output'] = True
    import MyDB
    Conf['DB'] = MyDB
    MyDB.Conf['hostname'] = 'localhost'

    from time import sleep
    try:
        import Output_test_data
    except:
        print("Please provide input test data: ident and data.")
        exit(1)

    for one in Output_test_data.data:
        timings = int(time())
        try:
            result = publish(
                info=one['info'],
                data = one['record'],
                artifacts = one['artifacts'],
            )
            try:
              if type(result) is list:
                print("Record ID %s, sent OK: %s" % (str(one['info']['id']),', '.join(result)))
              elif type(result) is bool:
                print("Record ID %s, result: %s" % (str(one['info']['id']),'FAILED' if not result else 'OK nothing to send'))
              else:  # result message
                print("Record ID %s, result: %s" % (str(one['info']['id']),str(result)))
            except:
              print("Record ID NOT DEFINED, result: %s" % (str(result)))
        except Exception as e:
            print("output channel error was raised as %s" % e)
        timings = 5 - (int(time())-timings)
        if timings > 0:
            print("Sleep for %d seconds" % timings)
            sleep(timings)

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

