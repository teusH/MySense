#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
#
# Copyright (C) 2020, Behoud de Parel, Teus Hagen, the Netherlands
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
__modulename__='$RCSfile: MyMQTTclient.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.42 $"[11:-2]
import inspect
def WHERE(fie=False):
   global __modulename__, __version__
   if fie:
     try:
       return "%s V%s/%s" % (__modulename__ ,__version__,inspect.stack()[1][3])
     except: pass
   return "%s V%s" % (__modulename__ ,__version__)

# $Id: MyMQTTclient.py,v 2.42 2021/10/14 13:05:46 teus Exp teus $

# Data collector for MQTT (TTN) data stream brokers for
# forwarding data in internal data format to eg: luftdaten.info map and MySQL DB

# MQTT library installation:
# module mqtt: git clone https://github.com/eclipse/paho.mqtt.python.git
# cd paho.mqtt.python ; python setup.py install
# broker server: Debian: apt-get install mqtt
# to do: add InfluxDB broker handling.

""" Python script for MQTT broker access
    Broker access is designed for multiple brokers data record MQTT downloads.
    MQTT topics may be a list of topics.
    Main routine is MQTT_data.GetData() to start and handle data records downloads.
    MQTT_data.GetData() returns with the MQTT data record in
    json/dict internal std format, or
    empty dict for no recort, or None for End of Records/Data.
    Module can be used as library as well CLI
    MQTT_data(MQTTbrokers,verbose=False,debug=False,logger=None,sec2pol=10)
    MQTTbrokers: has configuration argument a list [broker, ...] of MQTT brokers:
      broker = {
        "resource": resource,                # Broker address or file name '-' std in
        "port":  1883,                       # Broker port or None for file input
        "user":  user,                       # Connection username if not from file
        "password": password,                # Connection password if not from file
        "clientID": clientID,                # MQTT client thread ID
        "keepalive": 180,                    # optional, MQTT max secs ack on repl request, dflt 180
        "topic": (topics[0][0] if len(topics) == 1 else topics), # topic to subscribe to
        "import": TTN2MySense().RecordImport # routine to import record to internal exchange format
      }
    Malfunctioning broker will be deleted from the brokers list.
    Use 'resource' as name for input (backup) file, std in, or named pipe.
    Use logging=function as logging function. Keepalive as ping delay.
    Use verbose or debug to enable more verbosity.
    Use sec2pol is wait time on empty rcrd queue.

    (test) command line (CLI) arguments:
        verbose=true|false or -v or --verbose. Default False. True if debug is true.
        debug=true|false or -d or --debug. Default False. Log level debug on true.
        user=MQTTuser user account name for TTN.
        password=MQTTpassword eg ttn-account-v2.abscdefghijl123456789ABCD.
        keepalive=N Keep A Live in seconds for connection, defaults to 180 secs.
            Dflt: None.
        node will be seen at TTN as topic ID. Multiple (no wild card) is possible.
        node='comma separated nodes' ... to subscribe to. Dflt node='+' (all wild card).
        show=pattern regular expression of device IDs to display the full data record.
        --show or -s is the same as show='.*': show details for all nodes
    MQTT_data class uses a list of broker dicts as configuration. Port=None defines
    to read from the file broker['resource'].

    Kit information from Sensors and TTNtable DB will be cached.
    Show chache on stderr with USR1 signal. Cache entry is cleared after 6 hours.
"""

import paho.mqtt.client as mqttClient
import threading
import time, datetime
import re
import sys
import json
import atexit
import signal

#
# The Things Netwoprk Stack V2 up to 2021-12-31
# From: https://www.thethingsnetwork.org/docs/applications/mqtt/api/
# CLI publish (not implemented use console): mosquitto_pub -h <Region>.thethings.network -d
#    -t 'my-app-id/devices/my-dev-id/down' -m '{"port":1,"payload_fields":{"led":true}}'
# Topic: <AppID>/devices/<DevID>/up: <AppID>/devices/+/up
# CLI subscribe: mosquitto_sub -h eu.thethings.network -d -t 'my-app-id/devices/+/up'
# Username: Application ID, Password: Application Access Key
# Message: Some values may be omitted if they are null, false, "" or 0.
# {
#   "app_id": "my-app-id",              // Same as in the topic
#   "dev_id": "my-dev-id",              // Same as in the topic
#   "hardware_serial": "0102030405060708", // In case of LoRaWAN: the DevEUI
#   "port": 1,                          // LoRaWAN FPort
#   "counter": 2,                       // LoRaWAN frame counter
#   // you could also detect this from the counter
#   "is_retry": false,                  // true if message is a retry
#   "confirmed": false,                 // true if message was confirmed
#   "payload_raw": "AQIDBA==",          // Base64 encoded payload: [0x01, 0x02, 0x03, 0x04]
#   // left out when empty
#   "payload_fields": {},               // Object results from the payload functions
#   "metadata": {
#     "airtime": 46336000,              // Airtime nanoseconds
#     "time": "1970-01-01T00:00:00Z",   // Time when server received message
#     "frequency": 868.1,               // Frequency at which message was sent
#     "modulation": "LORA",             // Modulation used - LORA or FSK
#     "data_rate": "SF7BW125",          // Data rate used - if LORA modulation
#     "bit_rate": 50000,                // Bit rate used - if FSK modulation
#     "coding_rate": "4/5",             // Coding rate used
#     "gateways": [
#       {
#         "gtw_id": "ttn-herengracht-ams", // EUI of the gateway
#         "timestamp": 12345,              // Timestamp when the gateway received the message
#         // left out when gateway does not have synchronized time
#         "channel": 0,                    // Channel where the gateway received the message
#         "rssi": -25,                     // Signal strength of the received message
#         "snr": 5,                        // Signal to noise ratio of the received message
#         "rf_chain": 0,                   // RF chain where the gateway received the message
#         "latitude": 52.1234,             // Lat of the gateway reported in its status updates
#         "longitude": 6.1234,             // Lon of the gateway
#         "altitude": 6                    // Alt of the gateway
#       },
#       //...more if received by more gateways...
#     ],
#     "latitude": 52.2345,              // Latitude of the device
#     "longitude": 6.2345,              // Longitude of the device
#     "altitude": 2                     // Altitude of the device
#   }
# }
#  END of TTN Stack V2 download message example

# TTN Stack V3 messages
# From: https://www.thethingsindustries.com/docs/reference/data-formats/
# CLI subscribe: mosquitto_sub -h eu.thethings.network -d -t 'my-app-id/devices/+/up'
# Username: Application ID, Password: Application Access Key
# Downlink messages not yet implemented: events, messages. Use console.
# Join accept message
# Some values may be omitted if they are null, false, "" or 0.
# {
#   "end_device_ids" : {
#     "device_id" : "dev1",                    // Device ID
#     "application_ids" : {
#       "application_id" : "app1"              // Application ID
#     },
#     "dev_eui" : "0004A30B001C0530",          // DevEUI of the end device
#     "join_eui" : "800000000000000C",         // JoinEUI of the end device (AppEUI in LoRaWAN versions below 1.1)
#     "dev_addr" : "00BCB929"                  // Device address known by the Network Server
#   },
#   "correlation_ids" : [ "as:up:01..." ],     // Correlation identifiers of the message
#   "received_at" : "2020-02-12T15:15..."      // ISO 8601 UTC timestamp received by the Application Server
#   "join_accept" : {
#     "session_key_id" : "AXBSH1Pk6Z0G166...", // Join Server issued identifier for the session keys
#     "received_at" : "2020-02-17T07:49..."    // ISO 8601 UTC timestamp received by the Network Server
#   }
# }
# Download json V3 message:
# { 
#   "end_device_ids" : {
#     "device_id" : "dev1",                    // Device ID
#     "application_ids" : {
#       "application_id" : "app1"              // Application ID
#     },
#     "dev_eui" : "0004A30B001C0530",          // DevEUI of the end device
#     "join_eui" : "800000000000000C",         // JoinEUI of the end device (AppEUI in LoRaWAN versions below 1.1)
#     "dev_addr" : "00BCB929"                  // Device address known by the Network Server
#   },
#   "correlation_ids" : [ "as:up:01...", ... ],// Correlation identifiers of the message
#   "received_at" : "2020-02-12T15:15..."      // ISO 8601 UTC timestamp received by the Application Server
#   "uplink_message" : {
#     "session_key_id": "AXA50...",            // Join Server issued identifier session keys used by this uplink
#     "f_cnt": 1,                              // Frame counter
#     "f_port": 1,                             // Frame port
#     "frm_payload": "gkHe",                   // Frame payload (Base64)
#     "decoded_payload" : {                    // Decoded payload object payload formatter
#       "temperature": 1.0, "luminosity": 0.64 },
#     "rx_metadata": [{                        // A list of metadata for each antenna gateway received
#       "gateway_ids": {
#         "gateway_id": "gtw1",                // Gateway ID
#         "eui": "9C5C8E00001A05C4"            // Gateway EUI
#       },
#       "time": "2020-02-12T15:15:45.787Z",    // ISO 8601 UTC timestamp received by the gateway
#       "timestamp": 2463457000,               // Timestamp of the gateway concentrator message received
#       "rssi": -35,                           // Received signal strength indicator (dBm)
#       "channel_rssi": -35,                   // Received signal strength indicator of the channel (dBm)
#       "snr": 5,                              // Signal-to-noise ratio (dB)
#       "uplink_token": "ChIKEA...",           // Uplink token injected by gateway, Gateway Server or fNS
#       "channel_index": 2                     // Index of the gateway channel that received the message
#       "location": {                          // Gateway location metadata (gateways location set to public)
#         "latitude": 37.97155556731436,       // Location latitude
#         "longitude": 23.72678801175413,      // Location longitude
#         "altitude": 2,                       // Location altitude
#         "source": "SOURCE_REGISTRY"          // Location source. SOURCE_REGISTRY is Identity Server.
#       }
#     }],
#     "settings": {                            // Settings for the transmission
#       "data_rate": {                         // Data rate settings
#         "lora": {                            // LoRa modulation settings
#           "bandwidth": 125000,               // Bandwidth (Hz)
#           "spreading_factor": 7              // Spreading factor
#         }
#       },
#       "data_rate_index": 5,                  // LoRaWAN data rate index
#       "coding_rate": "4/6",                  // LoRa coding rate
#       "frequency": "868300000",              // Frequency (Hz)
#     },
#     "received_at": "2020-02-12T15:15..."     // ISO 8601 UTC timestamp received by the Network Server
#     "consumed_airtime": "0.056576s",         // Time-on-air, calculated using payload size and transmission
#     "locations": {                           // End device location metadata
#       "user": {
#         "latitude": 37.97155556731436,       // Location latitude
#         "longitude": 23.72678801175413,      // Location longitude
#         "altitude": 10,                      // Location altitude
#         "source": "SOURCE_REGISTRY"          // Location source. SOURCE_REGISTRY is Identity Server.
#       }
#     }
#   }
#   "simulated": true,                         // Signals if the message from the Network Server or is simulated.
# }


# class to convert MQTT record from TTN json to a decoded internal data format
# data record exchange format is just a proof of concept
""" Data record exchange format definition: DRE 0.0 Draft May 2021
    Terminology here is Python syntax: dict, list, tuple. Maybe similar in JSON.
    Most key/value items are optional, if multiple value value becomes a list or tuple.
    Items are lossy definitions: if not defined defaults or last value is used (stateful).
    Defined keys: version, id, timestamp, KeyID, keys (key translation table), unitsID, units, 
        dust, geolocation, meteo, energy, gps,
        temperature, RH, pressure, voc, geohash, altitude, longitude, latitude,
    Undefined keys in DRE or in implementation will be skipped.
    Format definition by example:
    {
      // if timestamp is not defined in data record the timestamp of record recept is taken
      "version": 0.0,            // version of exhange format
      “id”: { “project”: “SAN”, “serial”: “78CECEA5167524” },
      "timestamp": 1621862416,   // or “dateTime”: “2021-05-24T15:20+02:00”,
      // next items are optional and global redefinitions of defaults
      “keyID”: “nl”,             // ref to defaults, default: "us"
      “keys”: { “timestamp”: “unixTime”, “rv”: “RH”, “lat”: “latitude”, “, ... },
      “unitsID”:”nl”,            // ref to deaults, default “unitsID”:”us”
      “units”: { “temperature”: “C”, “altitude”: “m”, ... },

      // meta data is state information of a measurement kit
      "meta": {                  // meta data (re)definitions, kit state sensor type in use definitions
        "version": 0.2,          // firware version, optional
        "timestamp": 1621862400, // meta info timestamp, optional
        "dust": "PMSx003",       // dust sensor types/manufacturer
        // default home location of measurement kit
        "geolocation" : { “geohash”: “u1hjjnwhfn”, "GeoGuess": True}
        // "GeoGuess" optional  if  defined as True if location is one gateway location
        // or as { "lat": 51.54046, "lon": 5.85306, "alt": 31.3, ["GeoGuess"]},
        "meteo": [ "BME680", ”SHT31” ], // more as one type present in kit
        “energy”: { “solar”: “5W”, “accu”: “Li-Ion” }, // energy type: dflt "adapter": "5V"
        "gps": "NEO-6"
        },

      // communication information for statistical and monitoring use. Only internaly use
      "net": {
        'TTN_id': u'kipster-k1', 'TTN_app': u'201802215971az', 'type': 'TTNV2',
        'gateways': [
          {'rssi': -94,  'gtw_id': u'eui-ac1f09fffe014c16', 'snr': 9.5},
          {'rssi': -107, 'gtw_id': u'eui-ac1f09fffe014c1c', 'snr': 3.3},
          {'rssi': -81,  'gtw_id': u'eui-ac1f09fffe014c1e', 'snr': 10.3},
          {'rssi': -120, 'gtw_id': u'20800293',             'snr': -7},
          {'rssi': -107, 'gtw_id': u'eui-ac1f09fffe014c15', 'snr': 3.8},
          {'rssi': -70,  'gtw_id': u'eui-1dee0d671fa03ad6', 'snr': 9.5, 'geohash': 'u1h32pkq8dr'}
        ]},

      // measurement data
      "data": {                  // measurements, only those active at that moment
        "version": 0.2,          // data version, optional
        "timestamp": 1621862400, // measurement timestamp, optional
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
# input TTN V2/V3 dict using applID, deviceID, timestamp, payload, gtw's
# to dict with
#   timestamp (epoch), ID
#   data (sensor types dust/meteo/gps: {field,value}),
#   meta (dust/meteo/gps [sensors types], geohash geolocation),
#   net (type=TTNV?,spf, gateways [{gwID,rssi,snr,geohash}]) skip gtw brokers
import MyLoRaCode
class TTN2MySense:
    def __init__(self, LoRaCodeRules=None, DefaultUnits = ['%','C','hPa','mm/h','degrees', 'sec','m','Kohm','ug/m3','pcs/m3','m/sec'], PortMap=None, logger=None):
        self.logger = logger  # routine to print logging from eg MyLoRaCode
        self.LoRaDecode = MyLoRaCode.LoRaCoding(LoRaCodeRules=LoRaCodeRules, DefaultUnits=DefaultUnits, PortMap=PortMap, logger=self.logger)
        # self.version = None  # TTN V2 or V3 stack version
        
    def _logger(self, pri, message):
        try: self.logger('TTN2MySense',pri,message)
        except: sys.stderr.write("TTN2MySense %s: %s\n" % (str(pri), message)) 

    # convert  and payload decode TTN V2/V3 record to data exchange format dict
    def RecordImport(self, record):
        import dateutil.parser as dp # add timezone infos!
        from geohash import encode as geohash
        if not record: return (None if record == None else {})
        def getLocation(rcrd):
          ord =  []; rts = {}
          try:
            # precision 11 is about 3 meter resolution
            rts['geohash'] = geohash(float(rcrd['latitude']),float(rcrd['longitude']),precision=11)
            rts['alt'](float(rcrd['altitude']))
          except: return rts
            
        rts = {}; airtime = 0.0; meta = {}
        # if not self.version:
        try:
          if record['payload_raw']:
            rts['net'] = {'type': 'TTNV2', 'gateways': []}
          rts.update(self.LoRaDecode.Decode(record['payload_raw'],port=record['port']))
          try:
            rts['net']['TTN_id'] = record['dev_id']
            rts['net']['TTN_app'] = record['app_id']
          except Exception as e:
            self._logger('ERROR',str(e))
        except:
          try:
            if record['uplink_message']:
              rts['net'] = {'type': 'TTNV3', 'gateways': []}
            rts.update(self.LoRaDecode.Decode(record['uplink_message']['frm_payload'],port=record['uplink_message']['f_port']))
            try:
              rts['net']['TTN_id'] = record['end_device_ids']['device_id']
              rts['net']['TTN_app'] = record['end_device_ids']['application_ids']['application_id']
            except: pass
          except:
            self._logger('ATTENT','Unknown TTN stack version in record: %s' % str(record))
            return {}

        # meta data handling
        if rts['net']['type'] == 'TTNV3': # TTN V3
          msg = None
          try:
            rts['timestamp'] = record['received_at']
            msg = record['uplink_message']
            airtime = float(msg['consumed_airtime'].replace('s',''))
          except: pass
          if 'rx_metadata' in msg.keys():
            msg = msg['rx_metadata']
            for i in range(len(msg)):
              gtw = {}
              if 'packet_broker' in msg[i].keys(): continue # skip brokers
              for one in ['gateway_id','rssi','snr']:
                v = None
                try:
                  if one == 'gateway_id':
                    v = msg[i]['gateway_ids']['gateway_id']
                  else: v = msg[i][one]
                  if not v == None: gtw[one] = v
                except: pass
              try: gtw.update(getLocation(msg[i]['location']))
              except: pass
              if gtw: rts['net']['gateways'].append(gtw)
        elif rts['net']['type'] == 'TTNV2':   # TTN V2, deprecated
          for item in [('timestamp','time'),('airtime','airtime'),('gateways','gateways'),('meta','longitude')]:
            try:
              val = record['metadata'][item[1]]
            except: continue   
            if not val: continue
            if item[1] == 'airtime':
              airtime = float(val)/1000000.0 # sec resolution
            elif item[1] == 'longitude': # geo location according to TTN account
              val = getLocation(record['metadata']); val['GeoGuess'] = True
              meta.update({ 'geolocation': val })
            elif item[0] == 'gateways':  # list of gateways
              for i in range(len(val)):
                gtw = {}
                for one in ['gtw_id','rssi','snr']:
                  try:
                    gtw[one] = record['metadata']['gateways'][i][one]
                  except: continue
                gtw.update(getLocation(record['metadata']['gateways'][i]))
                if gtw: rts['net']['gateways'].append(gtw)
            else: rts[item[0]] = val
        else: return {}
          
        if meta: rts['meta'] = meta
        if not rts['net']['gateways']: del rts['net']['gateways']
        try:
          if type(rts['timestamp']) is float: rts['timestamp'] = int(rts['timestamp']+0.5)
          if not type(rts['timestamp']) is int:    # convert timestamp is in epoch secs
            # somehow the parser diffs from data --date=timestamp +%s with 3600 secs
            rts['timestamp'] = int(float(dp.parse(rts['timestamp'], tzinfos={'Z': 0}).strftime("%s.%f"))+3600-airtime+0.5) # 1 sec resolution
        except:
          rts['timestamp'] = int(time.time()-airtime+0.5) # add a timestamp
        return rts

# routines to collect messages from MQTT broker (yet only subscription)
# collect records in RecordQueue[] using QueueLock
# broker with MQTT connection details: host, user credentials, list of topics
# broker = {
#        "resource": "eu.thethings.network", # Broker address default
#        "port":  1883,                      # Broker port default
#        "user":  "20201126grub",            # Connection username
#                                            # Connection password
#        "password": ttn-account-v2.GW36kBmsaNZaXYCs0jx4cbPiSfaK6r0q9Zj0jx4Bmsts"
#        "topic": "+" , # topic or list of topics to subscribe to
#    }
class MQTT_broker:
    def __init__(self, broker, fifo, lock, verbose=False, debug=False, logger=None):
        self.connected = None     # None=not yet, False from disconnected, True connected
        self.message_nr = 0       # number of messages received
        self.RecordQueue = fifo   # list of received data records
        self.QueueLock = lock     # Threadlock fopr queue handling
        self.client = None        # MQTT connection handle
        self.verbose = verbose    # verbosity
        self.debug = debug        # more verbosity
        self.broker = broker      # TTN access details
        if not 'port' in broker.keys(): broker['port'] = None
        if not 'lock' in broker.keys(): # make sure timestamp sema is there
            self.broker['lock'] = threading.RLock()
        self.KeepAlive = 240      # connect keepalive in seconds, default 240
        try: self.KeepAlive = broker['keepalive']
        except: pass
        if not self.KeepAlive: self.KeepAlive = 240
        self.logger = logger      # routine to print errors
    
    def _logger(self, pri, message):
        try: self.logger('MQTT_broker',pri,'MQTT client MQTT_broker: ' + str(message))
        except: sys.stderr.write("MQTT_broker MyMQTTclient %s: %s\n" % (str(pri), str(message))) 

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            if self.verbose: self._logger("INFO","Connected to broker")
            self.connected = True                # Signal connection 
            with self.broker['lock']: self.broker['timestamp'] = time.time()
        else:
            self._logger("ERROR","Connect to MQTT broker failed: %s." % [ "successful", "internet connection broke up", "invalid client identifier", "server unavailable", "bad username or password", "not authorised"][rc])
            raise IOError("MQTT broker connection failed")
    
    # callback on ping ack tooks more as keepalive
    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if self.verbose:
            self._logger("INFO","Disconnect rc=%d from MQTT broker %s, userdata: %s." % (rc, self.broker['clientID'],str(userdata)))
        #else:
        #    self._logger("WARNING","Disconnect rc=%d from MQTT broker %s." % (rc, self.broker['clientID']))
        time.sleep(0.1)
     
    # pickup in thread call back the MQTT record and queue it
    def _on_message(self, client, userdata, message):
        self.message_nr += 1
        try:
            record = json.loads(message.payload)
            if len(record) > 25: # primitive way to identify incorrect records
              self._logger("WARNING","TTN MQTT records overload. Skipping.")
            elif len(self.RecordQueue) > 100:
              try:
                self._logger("WARNING","exhausting record queue. Skip record: %s." % record['end_device_ids']['device_id'])
              except:
                self._logger("WARNING","exhausting record queue. Skip record: %s." % record['dev_id'])
            else:
              record = self.broker['import'](record) # convert TTN record to MySense internal data struct
              with self.QueueLock: # queue the record
                self.RecordQueue.append(record)
                # in principle next should be guarded by a semaphore
                with self.broker['lock']: self.broker['timestamp']  = time.time()
            return True
        except Exception as e:
            # raise ValueError("Payload record is not in json format. Skipped.")
            self._logger("ERROR","it is not json payload, error: %s" % str(e))
            self._logger("INFO","\t%s skipped message %d received: " % (datetime.datetime.now().strftime("%m-%d %Hh%Mm"),self.message_nr) + 'topic: %s' % message.topic + ', payload: %s' % message.payload)
            return False

    def _on_log(self, client=None, userdata=None, level=None, buf=None):
        if self.debug: self._logger(level,"userdata: %s, message: %s." % (str(userdata),str(buf)))
        elif self.verbose: self._logger(level,"%s." % str(buf))

    @property
    def Connected(self):
        return self.connected
     
    def MQTTinit(self):
        if self.client == None:
            # may need this on reinitialise()
            self.clientID = "ThisTTNtestID" if not 'clientID' in self.broker.keys() else self.broker['clientID']
            if self.verbose:
                self._logger("INFO","Initialize TTN MQTT client ID %s" % self.clientID)
            # create new instance, clean session save client init info?
            self.client = mqttClient.Client(self.clientID, clean_session=True)
            self.client.username_pw_set(self.broker["user"], password=self.broker["password"])    # set username and password
            self.client.on_connect = self._on_connect        # attach function to callback
            self.client.on_message = self._on_message        # attach function to callback
            self.client.on_disconnect = self._on_disconnect  # attach function to callback
            if self.debug or self.verbose: self.client.on_log = self._on_log   
            self.client.reconnect_delay_set(min_delay=4,max_delay=900) # 4 secs - 15 minutes
            for cnt in range(3):
                try:
                    # TODO: set_tls setting not yet supported
                    # if 'cert' in self.broker.keys() do set ssl
                    self.client.connect(self.broker["resource"], port=self.broker["port"], keepalive=self.KeepAlive) # connect to broker
                    break
                except Exception as e:
                    self._logger("INFO","%s connection failure." % datetime.datetime.now().strftime("%m-%d %Hh%Mm:"))
                    self._logger("ERROR","Try to (re)connect failed to %s:%s with error: %s" % (self.broker["resource"],str(self.broker["topic"]), str(e)))
                    time.sleep(60)
                    if cnt >= 2:
                        self._logger("FATAL","Giving up.")
                        exit(1)
        else:
            try:
                self.broker['count'] += 1
                time.sleep(self.broker['count']*60) # slow down a bit
            except: self.broker['count'] = 1
            self.client.reinitialise()
            if self.verbose:
                self._logger("INFO","Reinitialize TTN MQTT client")
        return True
    
    def MQTTstart(self):
        if self.connected: return True
        self.connected = False
        if not self.client:
            self.MQTTinit()
        else: self.client.reinitialise(client_id=self.clientID)
        cnt = 0
        if self.verbose:
            self._logger("INFO","Starting up TTN MQTT client %s." % self.clientID)
        self.client.loop_start()
        time.sleep(0.1)
        while self.connected != True:    # Wait for connection
          if cnt > 250:
            self._logger("FAILURE","%s: waited for connection too long." % self.clientID)
            self.MQTTstop()
            return False
          if self.verbose:
            if not cnt:
              self._logger("INFO","%s: Wait for connection" % self.clientID)
            elif (cnt%10) == 0:
              self._logger("INFO","%s: Wait for connection %3.ds"% (self.clientI,cnt/10))
          cnt += 1
          time.sleep(0.1)
        qos = 0 # MQTT dflt 0 (max 1 telegram), 1 (1 telegram), or 2 (more)
        try: qos = self.broker['qos']
        except: pass
        self.client.subscribe(self.broker['topic'], qos=qos)
        self._logger("INFO","TTN MQTT client %s started." % self.clientID)
        return True
    
    def MQTTstop(self):
        if not self.client: return
        if self.verbose: self._logger("ERROR","%s: STOP MQTT connection" % self.clientID)
        try:
          self.client.loop_stop()
          self.client.disconnect()
        except: pass
        self.connected = False
        self.client = None  # renew MQTT object class
        time.sleep(15) # give thread a chance to stop

# KitCache: cache with refs DB kit info into KitCached dict cache
class KitCache:
    import signal
    def __init__(self, ReDoCache=3*60*60, DB=None, logger=None):
      self.logger=logger
      # cached meta info  and handling info measurement kits
      # cache to limit DB access
      self.DB = DB
      if not DB:
        import MyDB
        self.DB = MyDB
        if MyDB.Conf['fd'] == None and not MyDB.db_connect():
          self._logger('FATAL','Unable to connect to DB')
          exit(1)
      if not self.DB.db_table('TTNtable') or not self.DB.db_table('Sensors'):
        self._logger('FATAL','Missing Sensors or TTNtable in DB')
        exit(1)

      self.redoCache  = ReDoCache        # period in time to check for new kits
      self.updateCacheTime = int(time.time())+ReDoCache # last time update cached check was done
      # self.dirtyCache = False            # force a check of cached items to DB info
      self.KitCached = {
        # 'project_serial': { 
            # 'id':        { 'project': project ID, 'serial':  measurement kit serial number ID }

            # 'SensorsID': Sensors table database row id
            # 'active':    kit active?
            # 'valid':     if NULL: kit not at home location, if True forward data
            # 'location':  current home location as geohash, None unknown
            # 'sensors':   comma separated list of sensor types (manufacturer ProdID's)

            # 'TTNtableID':TTNtable table database row id
            # 'MQTTid':    MQTT subscription ID eg TTN subscribe: TTN_app/TTN_id
            # 'DATAid':    measurements table if active? (PROJ_SERIAL)
            # 'Luftdaten': Luftdaten ID if active? (TTN-SERIAL)
            # 'WEBactive': active on website?

            # statistics
            # 'last_seen': unix timestamp secs, last seen
            # 'count':     received records count, rese on new info
            # 'interval':  guessed usual interval, dflt 15*60 secs
            # 'ttl':       time to live in cache. After 6 hours refresh from DB
            # 'gtw': [[],...] LoRa gateway nearby [gwID,rssi,snr,(lat,long,alt)]
            # 'unknown_fields': [] seen but not used fields
        # },
      }
      # there is a namespace problem with signal handling if done inside an import
      signal.signal(signal.SIGUSR1, self.SigUSR1handler)
      # signal.signal(signal.SIGUSR2, self.SigUSR2handler)

    def _logger(self, pri, message):
      try: self.logger('KitCache',pri,message)
      except: sys.stderr.write("KitCache %s: %s\n" % (str(pri), message)) 

    def PrtDict(self, one,spacing):
      if type(one) is dict:
        rts = ' {\n'
        for item in one.keys():
          rts += spacing + "  \"%s\": " % item
          rts += self.PrtDict(one[item],spacing+'  ')
        return rts + spacing + ' },\n'
      else: return str(one) + ',\n'

    def PrtCached(self, item=None):
      try:
        if item:
          try:
            self._logger('INFO',"Cached[%s] status:\n\t%s\n" % (item, PrtDict(cached[item],'  ')) )
          except: pass
          return
        for name in self.KitCached.keys():
          self.PrtCached(name)
      except: pass

    # show current status of nodes seen so far
    def SigUSR1handler(self, signum,frame):
      self.PrtCached()

    # clear KitCached with next data reception
    #def SigUSR2handler(self, signum,frame):
    #  self.dirtyCache = True

    def cleanCache(self):  # maintain cache first in, first out
      # if self.dirtyCache:
      #   self.KitCached = {}; self.dirtyCache = False
      #   return
      if len(self.KitCached) <= 50: return # allow max 50 cache entries
      timestamp = int(time.time()); fnd = False
      if self.updateCacheTime <  timestamp: # try to keep in sync
        for one, val in self.KitCached.items():
          if val['ttl'] < timestamp:
            del self.KitCached[one]  # refresh entry from DB
            fnd = True
        self.updateCacheTime += self.redoCache
      if fnd: return
      first = float('inf')
      for one, val in self.KitCached.items():
        if val['ttl'] < first:
          fnd = one; first = val['ttl']
      if fnd: del self.KitCached[fnd]

    # add key,value to a info record
    def addEntry( self, record, keys, values ):
        for i in range(len(keys)):
          try: record[keys[i]] = values[i]
          except: record[keys[i]] = None

    # initialize new cache record and put it into KitCached
    # rts: ref to KitCached entry
    def AccessInfo(self, ID):
        self.cleanCache()
        record = {}
        try:
          one = self.KitCached[ID]
          if one['ttl'] > int(time.time()): return one
          # force update entry for tables Sensors and TTNtable
          for i in ['count','interval','gtw','unknown_fields','last_seen']:
            record[i] = self.KitCached[ID][i] # copy cache statistics
          del self.KitCached[ID]
        except: pass # create a record

        match2 = None
        try:
          (match1,match2) = ID.split('/')
          col1 = 'TTN_app'; col2 = 'TTN_id'
        except:
          try:
            (match1,match2) = ID.split('_')
            col1 = 'project'; col2 = 'serial'
          except: pass
        if not match2:
          self._logger('ATTENT','Skip record from not registrated node: %s' % ID)
          return None
        if not record:
          record = {'last_seen': 0, # cache entry lives 6 hours max
                  'count': 0, 'interval': 15*16, 'gtw': [], 'unknown_fields': [], }
        try:  # get info items from TTNtables into KIT cache. TTL cell values is 6 hours.
          qry = """SELECT
                     TTNtable.project, TTNtable.serial,
                     UNIX_TIMESTAMP(now())+6*60*60, UNIX_TIMESTAMP(TTNtable.id),
                     IF(NOT ISNULL(TTNtable.DBactive) AND TTNtable.DBactive,
                          CONCAT(TTNtable.project,'_',TTNtable.serial),NULL),
                     IF(NOT ISNULL(TTNtable.TTN_id),
                          CONCAT(TTNtable.TTN_app,'/',TTNtable.TTN_id),NULL),
                     IF(NOT ISNULL(TTNtable.luftdaten) AND TTNtable.luftdaten,
                          IF(NOT ISNULL(TTNtable.luftdatenID),TTNtable.luftdatenID,TTNtable.serial),NULL),
                     TTNtable.website,
                     UNIX_TIMESTAMP(Sensors.id), Sensors.sensors, Sensors.geohash, Sensors.active, TTNtable.valid, Sensors.description
                   FROM TTNtable, Sensors
                   WHERE TTNtable.%s = '%s' AND TTNtable.%s = '%s'
                     AND Sensors.project = TTNtable.project AND Sensors.serial = TTNtable.serial
                   ORDER BY Sensors.active DESC, Sensors.datum DESC
                   LIMIT 1""" % (col1,match1,col2,match2)
          qry = self.DB.db_query( re.sub(r'\n *',' ',qry).strip(), True)[0]
        except:
          self._logger('ATTENT','Skip record with ID %s (not registrated).' % ID)
          return {}
        self.addEntry(record,['ttl','TTNtableID','DATAid','MQTTid','Luftdaten','WEBactive','SensorsID','sensors','location','active','valid','version'],qry[2:])
        record['id'] = { 'project': qry[0], 'serial': qry[1] }
        try: # measurement kit firmware version detection expected in field 'description'
          record['version'] = re.compile(r'.*(?P<version>V[0-9][0-9\.]*)').match(record['version']).group('version')
        except: del record['version']
        if not record['last_seen']:
          try:
            record['last_seen'] = self.DB.db_query("SELECT UNIX_TIMESTAMP(datum) FROM %s ORDER BY datum DESC LIMIT 1" % (qry[0]+'_'+qry[1]), True)[0][0]
          except: pass
        self.KitCached[ID] = record
        return record

    # use cache to get last meta info for app, dev ID conversion to project, serial
    def getDataInfo(self, record, FromFile=False):
      self.cleanCache()  # cache maintenance
      entry = {}
      try: entry = self.AccessInfo(record['id']['project']+'_'+record['id']['serial'])
      except: pass
      if not entry:
        for MQTTid in [('TTN_app','TTN_id')]:
          try:
            entry = self.AccessInfo(record['net'][MQTTid[0]]+'/'+record['net'][MQTTid[1]])
            if entry:
              if FromFile: entry['FromFILE'] = True
              record.update({'id': entry['id']})
              break
          except: pass
      if not entry:
        try: RecID = "MQTT %s/%s" % (record['TTN_app'],record['TTN_id'])
        except: RecID = 'NO MQTT applID/topic'
        self._logger("ATTENT","Skip record with ID: '%s' (not registrated node)." % RecID)
      else:
        try: # remove location guessed from GTW location from data dict
          if entry['location'] and record['meta']['geolocation']['GeoGuess']:
            del record['meta']['geolocation']
            if not record['meta']: del record['meta']
        except: pass
      return (entry,record)

# get data from MQTT server. Returns data record and DB access/forwarding info record from Kit cache
class MQTT_data:
    # logger is log routine to be used, database access for MQTT -> project/serial ID conversion
    def __init__(self, MQTTbrokers, DB=None, verbose=False, debug=False, logger=None, sec2pol=10):
      self.MQTTbrokers = MQTTbrokers
      if not type(MQTTbrokers) is list: self.MQTTbrokers = [MQTTbrokers] # single broker
      self.verbose = verbose
      self.debug = debug
      self.logger = logger
      self.sec2pol = sec2pol
      self.MQTTrunning = False          # atexit enabled
      self.MQTTFiFo = []                # first in, first out data records queue
      self.MQTTLock = threading.RLock() # lock for queue access
      self.Restart  = 0                 # time to retry MQTT broker client to startup
      if not DB:
        import MyDB
        DB=MyDB
      self.KitInfo = KitCache(DB=DB,logger=logger)    # kit cache with DB/forwarding info

      for i in range(len(self.MQTTbrokers)-1,-1,-1): # reading from file if port is 0 or None
        broker = self.MQTTbrokers[i]
        if not len(broker) or not type(broker) is dict:
          self.MQTTbrokers.pop(i); continue
        try:
          if not 'fd' in broker.keys(): broker['fd'] = None
          try:
            if not 'port' in broker.keys(): broker['port'] = None
            if broker['port']: continue
            if not broker['resource']: continue
          except: continue
          if not broker['fd']:
            try:
              if broker['resource'] == '-':
                broker['fd'] = sys.stdin  # just read from stdin
              elif type(broker['resource']) is str:
                broker['fd'] = open(broker['resource'],'r')
            except:
              raise IOError("INPUT ERROR: unable to read file %s\n" % str(broker['resource']))
              # exit(1)
        except: raise ValueError("Unknown broker %s definition" % str(broker))
      
    def _logger(self, pri, message):
      try: self.logger('MyMQTTclient', pri, message)
      except: sys.stderr.write("MyMQTTclient %s: %s\n" % (str(pri), message)) 

    # make sure MQTT threads are exiting on exit
    def MyExit(self, brokers, eol=True): # stop running broker threads on exit
      for broker in brokers:
        try:
          if broker['port']: # may block till thread stops
            print("Wait exit TTN client for broker %s" % str(broker['clientID']))
            broker['fd'].MQTTstop(); broker['fd'] = None
        except: pass
      print("END of MQTT broker handling.")
      if eol: exit(1)
    #   atexit.register(self.MyExit,self.MQTTbrokers,False)
    #   import signal
    #   signal.signal(signal.SIGINT,MyExit)
    #   signal.signal(signal.SIGTERM,MyExit)

    # find brokers who need to be (re)started up
    def MQTTstartup(self):
      StartedOne = False
      for indx in range(len(self.MQTTbrokers)-1,-1,-1):
        broker = self.MQTTbrokers[indx]
        if not broker or not type(broker) is dict:
          del self.MQTTbrokers[indx]
          continue
        elif not broker['port']: continue
        # init class object handle, nr of restarts, start time, secs to wait next strt,time last record
        for one in ['fd','restarts','startTime','count','timestamp']:
          if not one in broker.keys(): broker[one] = None if one == 'fd' else 0
        if broker['fd']: continue
        if broker['startTime'] > time.time():
          if not self.Restart or broker['startTime'] < self.Restart:
            self.Restart = broker['startTime']
          self._logger("ATTENT","Wait for broker %s to be started" % broker['clientID'])
          continue  # do not start a client which has to wait
        broker['lock'] = threading.RLock() # sema for timestamp
        broker['fd'] = MQTT_broker(broker, self.MQTTFiFo, self.MQTTLock, verbose=self.verbose, debug=self.debug, logger=self.logger)
        if not broker['fd']:
          self._logger("ERROR","Unable to initialize MQTT broker class for %s" % str(broker))
          del self.MQTTbrokers[indx]
          continue
        if not broker['fd'].MQTTstart():
          self._logger("ERROR","Unable to initialize MQTT connection: %s." % str(broker))
          del self.MQTTbrokers[indx]
        elif not broker['startTime']:
          with broker['lock']:
            broker['timestamp'] = broker['startTime'] = time.time()
        else: broker['restarts'] += 1
        StartedOne = True
      if not len(self.MQTTbrokers): return False
      if StartedOne:
        if not self.MQTTrunning:
          self.MQTTrunning = True; atexit.register(self.MyExit,self.MQTTbrokers,False)
          # signal.signal(signal.SIGINT,MyExit)
          # signal.signal(signal.SIGTERM,MyExit)
        return True
      if self.Restart:
        self.Restart = max(0,self.Restart-int(time.time()))
        self._logger("ATTENT","Wait %d secs and try to restart a broker" % self.Restart)
        time.sleep(self.Restart)
        self.Restart = 0
      return True

    # get a record from an MQTT broker eg TTN
    #     verbose: verbosity
    #     logger: fie to log, sec2pol: wait on record
    # returns (DB KitCached entry, record in exchange format)
    # returns KitCached = None if not identified in DB,
    #         record = None on end of input, {} unaccepted record
    def GetData(self):
      # try to read all records from a broker backup file
      for i in range(len(self.MQTTbrokers)-1,-1,-1): # reading from file
        broker = self.MQTTbrokers[i]
        if not len(broker) or not type(broker) is dict:
          self.MQTTbrokers.pop(i); continue
        if broker['port'] or not broker['fd']: continue
        try:
          record = broker['import'](self.GetDataFromFile(broker['fd']))
          if record: return self.KitInfo.getDataInfo(record, FromFile=True)
          broker['fd'].close()
          self.MQTTbrokers.pop(i)
        except: pass

      if not len(self.MQTTbrokers):
        self._logger("INFO","No MQTT broker data available anymore.")
        return (None,None)  # nothing to read from
 
      # maybe restart an MQTT broker client, get data from connected MQTTT brokers
      while True: # first see if MQTT broker client needs to be (re)started
        # find brokers who are disconnected
        for broker in self.MQTTbrokers: # cleanup brokers disconnected somehow
          try:
            if not broker['fd'].connected:
              for cnt in range(3): # see if there is a paho MQTT recovery in place
                time.sleep(15)  # see if there is a recovery in place
                if not broker['fd'].connected:
                  broker['fd'].MQTTstop() # routine uses sleep of 15 secs
                  broker['fd'] = None
                  # reconnect slow down gracefully
                  broker['timestamp'] = int(time.time()) + broker['restarts']*self.sec2pol
                  self._logger("INFO","Wait on stop %d (max wait: %d) for broker stop connection for MQTT client %s" % (cnt+1,broker['restarts']+1,broker['clientID']))
                else:
                  self._logger("INFO" if self.verbose else "ATTENT","Auto reconnect for broker %s" % broker['clientID'])
                  break # MQTT paho did a reconnect
              # enforce disconnect?
          except: pass
        # try to start MQTT brokers ready to go
        if not self.MQTTstartup():
          self._logger("INFO","no MQTT broker available")
          return (None,None)

        # reset dying connections, delete dead connections
        for i in range(len(self.MQTTbrokers)-1,-1,-1):
          broker = self.MQTTbrokers[i]

          # CONNECTED broker
          now = time.time()
          if broker['fd'].connected: # Are we waiting for data too long? Give up for this broker.
            if (now - broker['timestamp'] > 60*60):
              self._logger("ERROR","Waiting (waiting for %d secs, running %d seconds) too long for data from MQTT broker %s. Stopped connection." % (now - broker['timestamp'], now - broker['startTime'], broker['clientID']))
              broker['fd'].MQTTstop() # stop MQTT subscriber thread
              self.MQTTbrokers.pop(i)
              continue
            if not broker['timestamp']: # should not happen
              with broker['lock']: broker['timestamp'] = now
  
          # found a DISCONNECTED broker
          elif broker['restarts'] <= 5: # try simple restart max 5 times
            self._logger("ERROR"," %s: MQTT broker %s connection died. Try again." % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),broker['clientID']))
            broker['fd'].MQTTstop()
            if (now > broker['startTime']) and (now-broker['startTime'] > 15*60):
              # has been run for minimal 5 minutes
              broker['restarts'] = 0
              broker['fd'] = None
            with broker['lock']: broker['timestamp'] = now
          else:
            self._logger("ERROR"," %s: Too many restries on MQTT broker %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S",broker['clientID'])))
            broker['fd'].MQTTstop()
            self.MQTTbrokers.pop(i)
  
        # try to find a (next) queue with a data record
        if len(self.MQTTFiFo):
          with self.MQTTLock: record = self.MQTTFiFo.pop(0)
          return self.KitInfo.getDataInfo(record)
        else: time.sleep(self.sec2pol)
  
      return (None,None)

    # handle data records from (backup) file
    def GetDataFromFile(self,fd):  # obtain records from file iso a TTN broker
      import json
      # convert [0xhex,..,0xhex] to int values for json payload corrections
      def JsonHex2Int(string):
        string = string.replace(' ','')
        if string.find('[') >= 0:
          strt = string.find('[')+1
          end = string[strt:].find(']')
          if end < 0: raise ValueError("List does not end")
          end += strt
        else: return string.strip()
        lst = []
        for item in string[strt:end].split(','):
           item = item.strip()
           if item[:2] == '0x' or item[:2] == '0X': item = str(int(item,16))
           lst.append(item)
        lst = ','.join(lst)
        return string[:strt]+ lst + JsonHex2Int(string[end:]).strip()

      line = ''
      while(True):
        readln = fd.readline().strip()
        if not readln: return None               # EOF
        if 0 <= readln.find('#') < 10:
          sys.stderr.write("COMMENT: %s\n" % readln[readln.find("#")+1:])
          continue
        elif 0 <= readln.find('//') < 10:
          sys.stderr.write("COMMENT: %s\n" % readln[readln.find("//")+2:])
          continue
        line += readln
        # simple check if we have a full record
        if line.count('{') > line.count('}'): continue
        if 0 <= line.find('{') < 10:
          line = line[line.find('{'):]
        elif line.find('up {') > 0:
          line = line[line.find('up {')+3:]
        else:
          sys.stderr.write("WARNING not an MQTT record: skip: %s" % line)
          continue
        line = JsonHex2Int(line)
        try:
          line = json.loads(line)
        except Exception as e:
          sys.stderr.write("JSON ERROR: %s\n" % str(e))
          sys.stderr.write("ERROR in decoding json string: %s\n" % line)
          continue
        return line
  
if __name__ == '__main__':
    # command line defaults
    verbose = False     # be verbose
    debug = False       # log level debug
    # show full received TTN MQTT record for this pattern
    show = None         # show details of data record for nodeID pattern. Dflt: no show.
    monitor = True      # monitor reception of a record
    node = '+'          # TTN MQTT devID pattern for subscription device topic part
    import os
    files = []          # read json records from input file
    clientID = 'TTNeuV2broker'     # MQTT ID

    # TTN credentials, only for test purposes
    resource = "eu.thethings.network"  # Broker address
    # user = "1234567890abc"       # connection user name
    user = "201802215971az"        # Connection username
    # password = "ttn-account-v2.ACACADABRAacacadabraACACADABRAacacadabra"
    password = "ttn-account-v2.GW3msa6kBNZs0jx4aXYCcbPaK6r0q9iSfZjIOB2Ixts"

    keepalive = None               # play with keepalive connection settings, dflt 180 secs
    MQTTbrokers = []               # may be a list of TTN/user brokers

    # default logger = None        # sys.stderr.write
    import MyLogger
    logger = MyLogger.log          # routine to print messages in color to console
    MyLogger.Conf['level'] = 'WARNING'
    MyLogger.Conf['print'] = True
    
    for arg in sys.argv[1:]: # change default settings arg: <type>=<value>
        if arg  in ['-v','--verbode']:  # be verbose
            verbose = True; continue
        if arg  in ['-d','--debug']:    # more verbosity
            debug = True; continue
        if arg  in ['-s','--show']:     # show MySense data record for all nodes
            show = re.compile('.*', re.I); monitor = False
            continue
        if arg in ['-h', '--help' ]:
            print("Command %s usage:" % sys.argv[0])
            print("""\toptions: -v/--verbose, -h/--help, -d/--debug -s/--show
    settings: verbose|show|debug=true 
        show='regular expression node id'
        devIDs=devID0,...,devIDn dflt: all
        resource=eu.thethings.network
        file=filename read json records from file or stdin ('-')
        user|password=TTN MQTT credentials    dflt: user=unknown, password=acacadabra
        keepalive=secs   keep connection alive dflt: 180
""")
            exit(0)
        Match = re.match(r'(?P<key>verbose|debug|show|devIDs|file|resource|user|password|keepalive)=(?P<value>.*)', arg, re.IGNORECASE)
        if Match:
            Match = Match.groupdict()
            if Match['key'].lower() == 'verbose':       # be more versatyle
                if Match['value'].lower() == 'false': verbose = False
                elif Match['value'].lower() == 'true': verbose = True
            elif Match['key'].lower() == 'debug':       # debug logger level 
                if Match['value'].lower() == 'false': debug = False
                elif Match['value'].lower() == 'true':
                  debug = True; verbose = True
            elif Match['key'].lower() == 'show':        # show details record with reg expt
                show = re.compile(Match['value'], re.I)
                monitor = False
            elif Match['key'].lower() == 'file':        # read json records from file
                files.append(Match['value'])
            # to do: make this to a list of brokers
            elif Match['key'].lower() == 'devids':      # comma separated list of devID's to subscribe to
                if node == '+': node = Match['value']
                else: node += ',' + Match['value']
            elif Match['key'].lower() == 'resource':     # URL TTN
                resource = Match['value']
            elif Match['key'].lower() == 'user':        # user account id (appl id)
                user = Match['value']
            elif Match['key'].lower() == 'password':    # password TTN MQTT account
                password = Match['value']
            elif Match['key'].lower() == 'keepalive':   # keep TCP connection alive (secs)
                if Match['value'].isdigit(): keepalive = int(Match['value'])
            continue
        elif os.path.isfile(arg): files.append(arg)

    if verbose: MyLogger.Conf['level'] = 'INFO'
    if debug: MyLogger.Conf['level'] = 'DEBUG'
    
    # TTN MQTT broker access details
    topics = []
    for topic in node.split(','): # list of topics ie devID's: appID/devices/devID
      topics.append(("+/devices/" + topic + "/up",0))
    if files: MQTTbrokers = [] # either from file(s) or from list of brokers
    for file in files:
      if file == '-': broker['resource'] = sys.stdin  # just read from stdin
      else:
        try:
          MQTTbrokers.append({
             "resource": file,                     # file name
             "fd": open(file,'r'),                # file handler
             "topic": (topics[0][0] if len(topics) == 1 else topics), # topic to subscribe to
             "import": TTN2MySense().RecordImport # routine to import record to internal exchange format
           })
        except:
          sys.stderr.write("ERROR: unable to read file %s\n" % file)
          exit(1)

    if not MQTTbrokers: # read from MQTT broker. To DO: args should be able to define a list
      broker = { # default broker
        "resource": resource,                # Broker address or file 
        "port":  1883,                       # Broker port
        "user":  user,                       # Connection username
        "password": password,                # Connection password
        "clientID": clientID,                # MQTT client thread ID
        "topic": (topics[0][0] if len(topics) == 1 else topics), # topic to subscribe to
        "import": TTN2MySense().RecordImport # routine to import record to internal exchange format
      }
      if keepalive: broker['keepalive'] = keepalive  # default 180
      MQTTbrokers.append(broker)

    import MyDB   # use ID recognition from DB tables
    # main
    TTNdata = MQTT_data(MQTTbrokers, DB=MyDB, verbose=verbose, debug=debug, logger=logger)

    timing = time.time()      # last time record reception
    while True:
      try:
        DataRecord = TTNdata.GetData()[1]

        if DataRecord: # print out some details
          ID = None; ApID = None; net = None; timestamp = None
          try:
            ID = DataRecord['id']['serial']
            ApID = DataRecord['id']['project']
          except:
            try:
              ID = DataRecord['net']['TTN_id']
              ApID = DataRecord['net']['TTN_app']
              net = "TTN"
            except: pass
          try: timestamp = DataRecord['timestamp']
          except: pass
          if monitor:
            if net:
              print("%s:%s data record timestamp %s, TTN app:%s, id: %s" % (datetime.datetime.now().strftime("%m-%d %Hh%Mm%Ss"), (" delay %3d secs," % (time.time()-timing) if verbose else ''),datetime.datetime.fromtimestamp(int(timestamp)).strftime("%y-%m-%d %H:%M:%S") if timestamp else 'None',str(ApID),str(ID)))
            else:
              print("%s:%s data record timestamp %s, project:%s, serial: %s" % (datetime.datetime.now().strftime("%m-%d %Hh%Mm%Ss"), (" delay %3d secs," % (time.time()-timing) if verbose else ''),datetime.datetime.fromtimestamp(int(timestamp)).strftime("%y-%m-%d %H:%M:%S") if timestamp else 'None',str(ApID),str(ID)))
            timing = time.time()
          if show and show.match(str(ID)):
            if net:
              print("%s:%s data record timestamp %s, TTN app:%s, id: %s" % (datetime.datetime.now().strftime("%m-%d %Hh%Mm%Ss"), (" delay %3d secs," % (time.time()-timing) if verbose else ''),datetime.datetime.fromtimestamp(int(timestamp)).strftime("%y-%m-%d %H:%M:%S") if timestamp else 'None',str(ApID),str(ID)))
            else:
              print("%s:%s data record timestamp %s, project:%s, serial: %s" % (datetime.datetime.now().strftime("%m-%d %Hh%Mm%Ss"), (" delay %3d secs," % (time.time()-timing) if verbose else ''),datetime.datetime.fromtimestamp(int(timestamp)).strftime("%y-%m-%d %H:%M:%S") if timestamp else 'None',str(ApID),str(ID)))
            for item,value in DataRecord.items():
              if item == 'data':
                print("  data: {")
                for key,keyval in value.items():
                    print("         %s:  %s" % (str(key),str(keyval)))
                print("        }")
              elif item == 'timestamp':
                print("  %s:  %s (%s)" % (str(item),str(value),datetime.datetime.fromtimestamp(int(value)).strftime("%y-%m-%d %H:%M:%S") if value else ''))
              else:
                print("  %s:  %s" % (str(item),str(value)))
            timing = time.time()
        elif DataRecord == None:
          break # end of input
        else:
          sys.stderr.write("No data record received. Try again.\n")
      except Exception as e:
        sys.stderr.write("End of get data record with exception: %s.\n" % str(e))
        break

