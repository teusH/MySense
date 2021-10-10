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
__modulename__='$RCSfile: MyLoRaCode.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.10 $"[11:-2]
import inspect
def WHERE(fie=False):
   global __modulename__, __version__
   if fie:
     try:
       return "%s V%s/%s" % (__modulename__ ,__version__,inspect.stack()[1][3])
     except: pass
   return "%s V%s" % (__modulename__ ,__version__)

# $Id: MyLoRaCode.py,v 2.10 2021/10/07 11:36:06 teus Exp teus $

# module will decode MQTT TTN records
# for test the module can run standalone and obtain MQTT TTN records from stadin or file
# the module is tested with Python and Pytho3

# for firmware tests the module can also encode data records into payloads for LoRaWan

# rules engine part is a proposal, a model for generalized encoding/decoding payload implementation
# A development Draft Request for Commments and Improvements
# This engine rule model is a prototype model to obtain feasibility of a standard approach
# Do not expect all functions are implemented yet
# as well do not expect to apply yet in full life yet.

# this approach will define for every LoRa port a unique LoRa encoding format
# Contains a library and test lib for handling LoRa encode and decode payloads
# it is also a first step to a standard air quality exchange data (json) record format

# see for struct details: https://docs.python.org/3/library/struct.html

# dict with en/decoding formats based on Libelium style of payload coding
# for encoding and LoRa 64 encoding use inverse
# every LoRa port has its own encoding and decoding style
# description dict:
#     format name: VERSION or ID (byte) array of
#       ID (byte), sensor name, array of pack instructions
#               database value name, pack id, null value identifier, Taylor array to map value
#       VERSION has endian type and coding version number  as pack instruction                 
# every value is either u-type string, or int/float value.
# int/float values are (un)mapped to int or float via a Taylor ([a0,a1,...]: a0+a1*x...) mapping

# TO DO: server -> node (remode commands) protocol...
# TO DO: meta data protocol: serial, home location, sensor types, ...
# Consider: the exchange format allows only one sensor product type in the measurements
#          the alternative is to introduce iso sensor product type a sensor ID and tuple extention
#          and the hassle of configuration admin consistancy problems and length of records
#

# DRAFT data exchange format May 2021
# this draft is subject to comments and needs more implementations
# {  # envelope
# “id”: {
#           “project”: “SAN”,
#           “serial”: “78CECEA5167524”
#     },
# "timestamp": 1621862416, # or “dateTime”: “2021-05-24T15:20+02:00”, (optional)
# keys are case independant
# “keys”: { # and/or “keyID”: “nl”, # key translation table (optional)
#     “timestamp”: “epoch”,
#     "pm25": "pm2.5", "pm03": "pm0.3", # denote: some DB's will not accept e.g. '.'
#     "pm03_cnt": "pm0.3 bin", "pm1_cnt": "pm1 bin", "pm4_cnt": "pm4 bin", ...
#     "temp", "temperature", “rv”: “rh”, "luchtdruk": "pressure",
#     “lat”: “latitude”, "lon": "longitude", "alt": "altitude",
#     "supply": "energy",
#     …
#     },
# defaults of measurement
# “units”: { # and/or “unitsID”:”nl”, # default units definition (optional)
#     “temperature”: “C”,
#     "pm[0-9\.]+_cnt": "pcs/0.1dm3", "pm[0-9\.]+": "ug/m3", # reg expr
#     “altitude”: “m”,
#     "longitude": "degrees", "latitude": "degrees", "geohash": "grid",
#     …
#     },
# "meta": { # measurement kit meta info (optional)
#       "version": 0.5,
#       "geolocation": {             # administrative location
#           “geohash”: “u1hjjnwhfn”, # precision 10
#           "lat": 51.54046,         # deprecated
#           "lon": 5.85306,          # deprecated
#           "alt": 31.3, },
#       "dust": "PMSx003",
#       "meteo": [ "BME680", ”SHT31” ],
#       “energy”: { “solar”: “5W”, “accu”: “Li-Ion” },
#       "gps": "NEO-6",
#       …
#    },
# "data": { # measurement data (optional)
#       "version": 1.8,
#       "NEO-6": {
#           "geohash": "u1hjjnwhfn",
#           "alt": 23,
#       },
#       "BME680":   {
#           "aqi": (29.9,”%”),
#           "rv": None, "luchtdruk": 1019,
#           "voc": (169,"KOhm"),
#           "temp": (293.7,”K”),
#       },
#       “SHT31”: [ # more as one sensor
#           { “temp”: 20.1, “rv”: 70.1 }, { “temp”: 20.3, “rv”: 67.3 }
#       ],         # 1+ sensors
#       "PMSx003": {
#           "pm05_cnt": 1694.1, "pm10": 29.4, "pm25_cnt": 2396.9,
#           "pm1_cnt": 2285.7, "pm25": 20.4, "pm10_cnt": 2.4, "pm1": 13.0,
#           "grain": 0.5,
#       },
#       “accu”: { "level": (89.5,”%”)},
#   },
#   "net": { # network access information (optional) Only those fields used
#       "TTN": {
#                # "app_id":"201802215971az", "dev_id":"bwlvc-a6b9",
#                # "hardware_serial":"AAAAB4E62DF4A6B9",
#                # "time":"2021-05-30T17:51:11.735085828Z",
#                "gateways":[
#                   {"gtw_id":"gateway_sint_anthonis_001","rssi":-119,"snr":-6},
#                   {"gtw_id":"gateway_sint_anthonis_003","rssi":-118,"snr":-1.25}
#                   ],
#                   # "latitude":51.6234,"longitude":5.85521,"altitude":2,
#                   # "location_source":"registry"
#                   }
# }
# use NaN as indicator for None or NULL values
# INFINITY = 1e200 * 1e200
# NAN = INFINITY / INFINITY
# END of DRAFT proposal

######################################
# LoRa encode  and decode to payload using LoRa code rules engine
#
# it uses Default unit attributes so exchange data format will be as "sensorproduct": {"sensortype1": (value,["unit type"]), ...}
# unit type is omitted if it is a default unit type e.g. C for Celcius degrees.
# the codings rule is identified (PortMap dict) either by "identifier" (string) or LoRa channel/port number (int)
# engine routines are LoRaCoding.Encode(): encode to LoRa payload and
#                     LoRaCoding.Decode(): decode the LoRa base64 payload

import base64
from time import time
import sys

# uses python geohash lib, try to correct lat/long swap
# some Python libs and eg MySQL may differ in the order lon,lat or lat,lon!
from MyGPS import convert2geohash

############################ LoRaCoding ##############
class LoRaCoding:
    def __init__(self, LoRaCodeRules=None, DefaultUnits = ['%','C','hPa','mm/h','degrees', 'sec','m','Kohm','ug/m3','pcs/m3','m/sec'], PortMap=None, logger=None):
      # arguments:
      # LoRaCodeRules: a dictionary with coding rules, default: use defualt rule set
      # DefaultUnits: a list of default unit types for measurement values. May be empty to force units in value tuple
      # defaults: percentage, Celcius, hecto pascal, mm per hour, seconds, Kilo Ohm,
      # mu gram per square meter, particles per cubic meter, meter per second
      # PortMap: a map of port number to product ID, rule identification. Default see below
      # struct.pack(">f", float('nan')).encode("hex_codec") -> '7fc00000'
      # struct.unpack('>f','7fc00000'.decode("hex_codec")) -> (nan,)
      NANf = float('nan')
      NANB = 2**8-1
      NANb = 2**7-1
      NANH = 2**16-1
      NANh = 2**15-1
      NANL = 2**32-1
      NANl = 2**31-1
      
      self.logger = logger  # default logging print
      # decode version
      self.version = 1.8
      # convert number to sensor type name (meta info port 3)
      self.dustTypes = [
        'unknown',
        'PPD42NS', # deprecated
        'SDS011', 'PMS7003', 'SPS30',
        'unknown', 'unknown'
      ]
      self.meteoTypes = [
        'unknown',
        'DHT11',  # deprecated
        'SHT85', 'BME280', 'BME680', 'SHT31'
      ]
      # dictionary with different LoRa encoding formats (port 10 and 12)
      if LoRaCodeRules == None:
        LoRaCodeRules = {
          'DIY0': [
              # packing: >hhhhhh wr, ws, accu, temp, rv, luchtdruk
              ['>','VERSION',[['version','',None,None,None]] ],     # deprecated
              [None,'BME280',[['wr','h',NANh,[0,1],'degrees'],['ws','h',NANh,[0,100.0],'m/sec'],['accu','h',NANh,[0,100.0],'V'],
                              ['temp','h',NANh,[0,100.0],'C'],['rv','h',NANh,[0,100.0],'%'],['luchtdruk','h',NANh,[0,1.0],'hPa'] ],
              ],
          ],
          'weerDIY1': [
              ['>','VERSION',[['version','B',NANB,[0,10.0],None]] ], # big endian, version 1 decimal 0.0 - 25.5
              # meteo 1-9
              [1,'BME280',[
                  ['temp','h',NANh,[0,10.0],'C'],
                  ['rv','h',NANh,[0,10.0],'%'],
                  ['luchtdruk','H',NANH,[0,1.0],'hPa']]
              ],
              [2,'BME680',[
                  ['temp','h',NANh,[0,10.0],'C'],
                  ['rv','H',NANH,[0,10.0],'%'],
                  ['luchtdruk','H',NANH,[0,1.0],'hPa'],
                  ['voc','H',NANH,[0,1.0],'Kohm'],
                  ['aqi','B',NANB,[0,1.0],'%']]
              ],
              [3,'SHT31',[
                  ['temp','h',NANh,[0,10.0],'C'],
                  ['rv','H',NANH,[0,10.0],'%']]
              ],
              # dust 10-18
              # 10 Nova SDS011 PM2.5 PM10
              # 11 Plantower PMSA003, PMS7003, PMSx003 PM1 PM2.5 PM10 PM0.3 PM0.5 PM1 PM2.5 PM5 PM10
              # 12 Sensirion SPS31 PM1 PM2.5 PM10 PM0.3 PM0.5 PM1 PM2.5 PM5 PM10 PMsize
              [19,'NEO-6',[['lon','f',NANf,[0,1.0],'degrees'],['lat','f',NANf,[0,1.0],'degrees'],['alt','L',NANL,[0,10.0],'m']] ], # degrees, degrees, meter (unsigned long)
              [20,'windDIY1',[['wr','H',NANh,[0,1.0],'degrees'],['ws','H',NANH,[0,10.0],'m/sec']] ],
              # a mechanical simple wind fane, limited resolution of direction
              [21,'Argent',[['wr','H',NANh,[0,1.0],'degrees'],['ws','H',NANH,[0,20.0],'m/sec']] ],
              # wind dir, wind speed
              [22,'Ultrasonic',[
                  ['wr','H',NANh,[0,1.0],'degrees'],
                  ['ws','H',NANH,[0,10.0],'m/sec']]
              ],
              [23,'RainCounter',[
                  ['rain', 'H', NANH, [0, 10.0], 'mm/h']] ],
              # 21 cm3/h rain
              # 30 lux UV BH1750
              # 40 ppm CO2
              [254,'time',[
                  ['time','L',[2**31,1],'sec']] # Posix timestamp, seconds
              ],
              # 255 error message nr?
          ],
          'Libelium': [
              # taken from WaspMote Data Frame Programming Guide v7.7: tiny frame
              # this needs to be improved. Specification Libelium was unclear about this.
              # a real life example from one weather WaspMote station:
              # "packing": "<B11sB7sBBBBBfBfBfBfBfBfBBBf", header, node id, xyz, (id,value),...
              # the Libelium specs say:
              # header: '<=>',type B (=0), length -5 pck B, serial ID 2L,WaspID ?s '#', seq nr B
              # header needs special handling...
              # data payload: [sensorID B + value bytes, ...]
              # char '?' is end char to delete of variable length field
              # omit keys with '?' in data record
              ['<','VERSION', [['header','3sBBQ#s?B',None,None, ['?start','L-type','?size','L-serial','?L-WASPid','?','?L-seq']]] ], # type,size-5 bytes,serial,ID,sep,sequence nr
              # type == 6 WaspMote v15, here only a selection of sensor IDs (depends on firmware)
              [52,'energy',   [['accu','B',NANB,[0,1.0],'%']] ],   # accu level %
              [74,'BME280',   [['temp','f',NANf,[0,1.0],'C']] ],   # temp BME280?
              [76,'BME280',   [['rv','f',NANf,[0,1.0],'%']] ],     # RH BME280?
              [77,'BME280',   [['luchtdruk','f',NANf,[0,100.0],'hPa']] ], # luchtdruk BME280?
              [158,'WASPrain',[['rain','f',NANf,[0,1.0],'mm/h']] ],     # 
              [159,'WASPrain',[['prevrain','f',NANf,[0,1.0],'mm/h']] ], #
              [160,'WASPrain',[['dayrain','f',NANf,[0,1.0],'mm/24h']] ],#
              [157,'WASPwind',[['wr','B',NANB,[0,0.25],'degrees']] ],   # resolution 6.25 degrees
              [156,'WASPwind',[['ws','f',NANf,[0,1.0],'m/sec']] ],      #
          ]
      }
      if (not type(LoRaCodeRules) is dict) or not len(LoRaCodeRules):
          raise valueError("Fatal error: LoRa Decode rules")
      self.LoRaCodeRules = LoRaCodeRules
      # default vaule units, omit those in data records
      if not type(DefaultUnits) is list:
        DefaultUnits = []
      self.DefaultUnits = DefaultUnits
      
      # map a LoRa port to an encoding scheme
      # to do: usage of LoRa port number as type of compression is a bit strange
      # need to change this to some type of datagram header identification
      self.PortMap = {
          2:  ['MySenseV1',self.DecodePort2or4],
          3:  ['MySenseMeta',self.DecodePort3],
          4:  ['MySenseV2',self.DecodePort2or4],
          12: ['weerDIY1',self.DecodePort10or12],
          10: ['Libelium',self.DecodePort10or12],
      }
      
    # search in format array row type sensor ID, return tuple IDnr, IDname, array compressie
    # eg self.GetFrmt(LoRaCode['weerDIY1'],'BME280')
    def GetFrm(self, format, tpe, indx=1 ):
        try:
            for item in format:
                if str(item[indx]).lower() == str(tpe).lower():
                    return (item[0],item[1],item[2])
        except: pass
        raise ValueError("Error: Could not find %d format" % tpe)
        return None
    
    # convert value with Taylor factor to compressed value
    # (val=-25.7,[50,10.0]) -> 257+50 = 307 
    def SetVal(self, val, aNAN, taylor, integer=True ):
        if val == None: return aNAN
        if not taylor: return val
        if integer: return int((val*taylor[1])+taylor[0]+0.5)
        else: return (val/taylor[1])-taylor[0] # only linear is supported for now
    
    # (val=307,[50,10.0]) -> (307-50)/10 = 25.7
    def GetVal(self, val, aNAN, tailor):
        if val == aNAN: return None
        if not tailor: return val
        return (val-tailor[0])/tailor[1]       # only lineair is supported for now
        #import math
        #return round((val-tailor[0])/tailor[1],int(math.log10(abs(tailor[1]))))
    
    # from format ID, type of sensor, subsensor index nr and value
    # return a tuple with pack and value
    def CompElmnt(self, format, type, sensor, value):
        if not format in self.LoRaCodeRules.keys(): 
            raise valueError("Unknown encoding format: %s" % format)
        try:
            frmmt = self.GetFrmt( format, type )
            for item in frmmt[2]:
              try:
                if item[0] == sensor:
                    return (frmmt[0],item[1],self.SetVal(value,item[2],item[3],item[1] != 'f'))
              except: pass
        except: pass
        return None
     
    # encode into payload for port 2,3 and 4
    # See for EncodeMeta(port=3) MySense/PyCom/MySense.py SendMeta() routine
    # See for EncodePort2or4a() MySense/PyCom/MySense.py DoPack(dust,meteo,gps,wind,accu) routine

    # compile a pack format and data dict to 2 pack and data list for encoding
    # data record is a dict with names of sensors,
    # each item is ordered list, or dict with types of sensed data, or single value
    # to do: variable size string with end of string mark (see Libelium header style)
    def Encode(self, data, ProdID ):
        import struct
        rts = ''
        if type(ProdID) is int:
            try: ProdID = self.PortMap[ProdID]
            except: pass
        if not ProdID in self.LoRaCodeRules.keys():
            sys.stderr.write("ERROR Unknown LoRa  payload coding product ID: %s\n" % str(ProdID))
            return rts
        if ProdID == 'Libelium':
            sys.stderr.write("ERROR Libelium encoding is not yet supported\n")
            return rts
        if not type(data) is dict: return rts
        format = self.LoRaCodeRules[ProdID]
    
        if not 'version' in data.keys(): data['version'] = [None]
        if not type(data['version']) is list: data['version'] = [data['version']]
        values = []; pck = self.GetFrm(format,'version')[0]
    
        for item in ['version'] + list(set(data.keys()).difference(set(['version']))):
            if not type(data[item]) is dict:
                if not type(data[item]) is list: data[item] = [data[item]]
            frm = self.GetFrm(format,item) # tuple IDnr, name, array of sensed tuples (name,pack,tlr
            if type(frm[0]) is int:  # needs to be generalized
                pck += 'B'; values.append(frm[0]) # eg set of (B,value) case
            # to do: make dict, or array of array of tuples possible iso static array with values
            for i in range(len(frm[2])):
                value = None
                try:
                    if type(data[item]) is dict: value = data[item][frm[2][i][0]]
                    elif type(data[item]) is list: value = data[item][i]
                    else: value = data[item] if not i else None
                except: pass
                values.append( self.SetVal(value,frm[2][i][2],frm[2][i][3],not frm[2][i][1] in ['f']) )
                pck += frm[2][i][1]
        try: payload = struct.pack(pck,*values)
        except Exception as e:
            sys.stderr.write("ERROR "+str(e)+"\n")
            sys.stderr.write("ERROR in pack %s: %s\n" % (pck, str(*values)))
            return ''
        # somehow a '\n' is added on the end
        return base64.encodestring(payload).rstrip()
    
    # replaces struct.calcsize() returns wrong byte cnt for l and L
    # added variable char search for eg. Libelium compact style
    def calcsize(self, strg, packed):
        cnt = 0; mul = None; pck = ''
        for i in range(len(strg)):
            if strg[i].isdigit():
                if mul == None: mul = 0
                else: mul *= 10
                mul += ['0','1','2','3','4','5','6','7','8','9'].index(strg[i])
                pck += strg[i]
                continue
            elif mul == None: mul = 1
            if strg[i].lower() in ['b','c','s','?']:
                cnt += 1*mul; mul = None; pck += strg[i]
            elif strg[i].lower() == 'h':
                cnt += 2*mul; mul = None; pck += strg[i]
            elif strg[i].lower() in ['i','l','f']:
                cnt += 4*mul; mul = None; pck += strg[i]
            elif strg[i].lower() in ['d','q']:
                cnt += 8*mul; mul = None; pck += strg[i]
            else: # variable length defined by char
                for j in range(cnt, len(packed)):
                    if packed[j] == strg.encode('ascii')[i]:
                        pck += '%d' % (j-cnt); mul = j-cnt
                        break
        return (cnt, pck)
    
    # base64 handling for python2 and python3
    def Base64Decode(self, string, raw=False):
        decoded = base64.b64decode(string.encode('ascii'))
        if not raw:
          if type(decoded) is str:  # not python3 case
            decoded = [ord(x) for x in decoded]
          else: decoded = [x for x in decoded]
        return decoded

    # the micro processor does not have a reliable time provision
    # so we use the timestamps from the nearest LoRaWan gateway
    # some kits will have GPS timestamp available however
    def DecodePort10or12(self,raw,port=12,timestamp=None):
        import struct
        import datetime
        import dateutil.parser as dp
    
        ProdID = ''
        if type(port) is int:
            try: ProdID = self.PortMap[port][0]
            except: pass
        else: ProdID = port
        if not ProdID in self.LoRaCodeRules.keys():
            raise valueError("Unknown LoRa payload encoding product ID: %s" % ProdID)
        frmt = self.LoRaCodeRules[ProdID]
        # #try: PackedData = base64.b64decode(raw)
        # if type(raw) is list: PackedData = raw
        # else:
          # try: PackedData = base64.decodestring(raw)
          # except: PackedData = raw
        PackedData = self.Base64Decode(raw,raw=True)
        i = -1; endian = frmt[0][0]; data = {}; geohash = None
        try:
          while i < len(PackedData):
            pck = ''; stype = None
            try:
              if i < 0:
                i = 0
                item = self.GetFrm(frmt, 'version')
                endian = item[0]
                if not type(item[2]) is list: continue
                pck = ''
              else: # get array decoding items for one sensor
                item = self.GetFrm(frmt, struct.unpack(endian+'B',PackedData[i:i+1])[0], indx=0)
                i += 1
            except Exception as e:
                sys.stderr.write("ERROR: Datagram error for %s on port or format %s with %s. Skip.\n" % (raw,str(format),str(e)))
                return data
            fields = []
            for j in range(len(item[2])):
              fields.append(item[2][j])
              pck += item[2][j][1]
            (cnt, pck) = self.calcsize(pck, PackedData[i:])
            values = struct.unpack(endian+pck,PackedData[i:i+cnt])
            i += cnt
            for j in range(len(fields)):
              try:
                if fields[j][0] in ['unknown',None]: continue
                if not item[1] in data.keys(): data[item[1]] = {}
                if type(fields[j][4]) is list: # multiple values
                    for nr in range(len(values)):
                      if fields[j][4][nr] != '?': # not end of variable size string hack
                        data[item[1]][fields[j][4][nr]] = values[nr]
                else:
                  # default units: do not provide units info
                  data[item[1]][fields[j][0]] = self.GetVal(values[j],fields[j][2],fields[j][3])
                  if type(data[item[1]][fields[j][0]]) is float:  # try to round
                      if fields[j][0][:3] in ['lon','lat']:
                        geohash = item[1]
                        data[item[1]][fields[j][0]] = round(data[item[1]][fields[j][0]],7)
                      elif fields[j][0] in ['wr','luchtdruk']:
                        data[item[1]][fields[j][0]] = int(data[item[1]][fields[j][0]])
                      else: data[item[1]][fields[j][0]] = round(data[item[1]][fields[j][0]],
1)
                  try: # if value is type tuple it has units
                    if fields[j][4] and (not fields[j][4] in self.DefaultUnits):
                      if not 'units' in data[item[1]].keys(): # add unit type if not default
                        data[item[1]][fields[j][0]] = (data[item[1]][fields[j][0]],fields[j][4])
                    # else: 
                    #     data[item[1]][fields[j][0]] = (data[item[1]][fields[j][0]],)
                  except: pass
              except:
                sys.stderr.write("ERROR: Decode error with sensor ID %d (fields %s, values %s)\n" % (i, str(fields), str(values)))
        except Exception as e:
            sys.stderr.write("ERROR: Decode error: %s\n" % str(e))
            return data
        # if defined it is in UTC time
        if type(timestamp) is str:
          # sys.stderr.write("Got timestamp: '%s', " % timestamp)
          timestamp = int(dp.parse(timestamp).strftime("%s"))
          # sys.stderr.write("converted to: %d\n" % timestamp)
        if len(data) and timestamp == None:
          timestamp = int(time())
          # sys.stderr.write("Added timestamp: %d\n" % timestamp)
        if geohash:
          try: # convert deprecated ordinate to geohash
            data[geohash]['geohash'] = convert2geohash([data[geohash]['lat'],data[geohash]['lon']],precision=11) # 3 meters resolution
            del data[geohash]['lon']; del data[geohash]['lat']
          except: pass
        for one in ['VERSION']: # push these on time dict level
            if not one in data.keys(): continue
            if type(data[one]) is dict:
              for item in data[one].keys():
                if item[0] == '?': continue
                if item in ['serial'] and (not type(data[one][item]) is str):
                  data[one][item] = '%x' % data[one][item] # some have just a unsigned long
                data[item] = data[one][item]
              del data[one]
        return { 'data': data, 'timestamp': int(timestamp) }

     # old style decoding port 2,3, and 4 routines

    def bytes2(self,b, nr, cnt):
        return round(((b[nr] << 8) + b[nr + 1]) / cnt, 1)

    def bytes2rat(self,b, nr):
        return (b[nr] << 24) + (b[nr + 1] << 16) + (b[nr + 2] << 8) + b[nr + 3]

    def notZero(self, b, nr):
        if ((b[nr] | b[nr + 1])): return True
        else: return False

    # dustTypes = [ 'unknown', 'PPD42NS', 'SDS011', 'PMS7003', 'SPS30', 'unknown', 'unknown' ]
    def DecodePort4(self,Bytes,port=4):     # PM count type HHHHHH
        decoded = {}; ID = 0
        # print("port 4 PM %d Bytes " %  len(Bytes)); print( Bytes)
        expl = True # use PM0.3 upto PM PMi type of PM counting
        pm_4 = False
        try:
          if Bytes[0]&0x80: # Plantower
             expl = False; Bytes[0] = Bytes[0] & 0x7F
          if Bytes[4]&0x80: # Sensirion
             ID = 4; pm_4 = True; Bytes[4] = Bytes[4] & 0x7F
          else: ID = 3
          PM4orPM5 = 0.0
          decoded['pm10_cnt'] = round(self.bytes2(Bytes, 0, 10.0), 1)
          decoded['pm05_cnt'] = round(self.bytes2(Bytes, 2, 10.0), 1)
          decoded['pm1_cnt'] = round(self.bytes2(Bytes, 4, 10.0), 1)
          decoded['pm25_cnt'] = round(self.bytes2(Bytes, 6, 10.0), 1)
          PM4orPM5 = round(self.bytes2(Bytes, 8, 10.0), 1)
          if expl: # range PMi up to PM10 Plantower
            decoded['pm03_cnt'] = round(self.bytes2(Bytes, 10, 10.0), 1)
          else:    # range PM0.3 up to PMi Sensirion
            decoded['grain'] = round(self.bytes2(Bytes, 10, 100.0), 2)  # avg PM size
            # PMi - PMj conversion to PM0.3 - PMx
            decoded['pm1_cnt'] = round(decoded['pm1_cnt']+decoded['pm05_cnt'],1)
            decoded['pm25_cnt'] = round(decoded['pm1_cnt']+decoded['pm25_cnt'],1)
            PM4orPM5 = round(PM4orPM5+decoded['pm25_cnt'],1)
            decoded['pm10_cnt'] = round(PM4orPM5+decoded['pm10_cnt'],1);
          if pm_4: decoded['pm4_cnt'] = PM4orPM5  # Sensirion
          else: decoded['pm5_cnt'] = PM4orPM5        # Plantower
        except Exception as e: raise ValueError("Port 4 decode error: %s\n" % str(e))
        finally:
          # print("decode PM %d bytes port 4" % len(Bytes)); print(decoded)
          return { self.dustTypes[ID]: decoded, 'PMsensor': self.dustTypes[ID] }
    
    # dustTypes = [ 'unknown', 'PPD42NS', 'SDS011', 'PMS7003', 'SPS30', 'unknown', 'unknown' ]
    def decodePM(self,Bytes):              # ug/m3 [H]HH */
        decoded = {}; strt = 0; ID = 0
        # print("PM %d bytes: " % len(Bytes)); print( Bytes)
        try:
          if len(Bytes) > 4:
            if self.notZero(Bytes, 0):
              ID = 3
              decoded['pm1'] = round(self.bytes2(Bytes, 0, 10.0), 1)
            strt += 2
          if self.notZero(Bytes, strt):
            if not ID: ID = 2
            decoded['pm25'] = round(self.bytes2(Bytes, strt, 10.0), 1)
          if self.notZero(Bytes, strt+2):
            if not ID: ID = 2
            decoded['pm10'] = round(self.bytes2(Bytes, strt+2, 10.0), 1)
        except Exception as e: raise ValueError("PM decode error: %s\n" % str(e))
        # print("decodePM %d bytes decoded:" % len(Bytes)); print(decoded)
        return {self.dustTypes[ID]: decoded, 'PMsensor': self.dustTypes[ID] }
    
    # dustTypes = [ 'unknown', 'PPD42NS', 'SDS011', 'PMS7003', 'SPS30', 'unknown', 'unknown' ]
    def DecodePort2(self,Bytes,port=2):           # PM counts HHHBBB
        decoded = {}
        ID = 2
        # print("port 2 PM %d bytes to: " % len(Bytes)); print( Bytes)
        try:
          if self.notZero(Bytes, 0):
            decoded['pm03_cnt'] = round(self.bytes2(Bytes, 0, 10.0), 1)
          if self.notZero(Bytes, 2):
            decoded['pm05_cnt'] = round(self.bytes2(Bytes, 2, 10.0), 1)
          if self.notZero(Bytes, 4):
            decoded['pm1_cnt'] = round(self.bytes2(Bytes, 4, 10.0), 1)
          if Bytes[6]:
            decoded['pm25_cnt'] = round(Bytes[6] / 10.0, 1)
          if Bytes[7]:
            decoded['pm5_cnt'] = round(Bytes[7] / 10.0, 1)
          if Bytes[8]:
            decoded['pm10_cnt'] = round(Bytes[8] / 10.0, 1)
          if decoded['pm10_cnt'] or decoded['pm5_cnt']: ID = 3
        except Exception as e: raise ValueError("Dust decode error: %s\n" % str(e))
        finally:
          # print("decoded PM %d bytes port 2 to: " % len(Bytes)); print(decoded)
          return {self.dustTypes[ID]: decoded, 'PMsensor': self.dustTypes[ID] }
    
    # meteoTypes = [ 'unknown', 'DHT11', 'SHT85', 'BME280', 'BME680', 'SHT31' ]
    def decodeMeteo(self,Bytes):           # BME, SHT HH[H[HH]]
        ID = 0
        decoded = {}
        # print("Meteo decode %d bytes: " % len(Bytes)); print(Bytes)
        try:
          if self.notZero(Bytes, 0): # DHT?
            ID = 1
            decoded['temp'] = round(self.bytes2(Bytes, 0, 10.0) - 30, 1)
          if self.notZero(Bytes, 2): # SHT (DHT is deprecated)
            ID = 5
            decoded['rv'] = round(self.bytes2(Bytes, 2, 10.0), 1)
          if len(Bytes) <= 4: return self.meteoTypes[ID], decoded
          if self.notZero(Bytes, 4): # BME280
            ID = 3
            decoded['luchtdruk'] = int(self.bytes2(Bytes, 4, 1))
          if len(Bytes) <= 6: return self.meteoTypes[ID], decoded
          if self.notZero(Bytes, 6): # BME680
            ID = 4
            decoded['gas'] = int(self.bytes2(Bytes, 6, 1)) # kOhm
          if self.notZero(Bytes, 8): # 0-100% VOC
            decoded['aqi'] = round(self.bytes2(Bytes, 8, 10.0),1)
        except Exception as e: raise ValueError("Meteo decode error: %s\n" % str(e))
        finally:
          # print("decoded Meteo %d bytes to: " % len(Bytes)); print(decoded)
          return { self.meteoTypes[ID]: decoded}
    
    def decodeGPS(self,Bytes):            # GPS NEO 6
        decoded = {}
        # print("decode GPS %d bytes " % len(Bytes)); print(Bytes)
        try:
            tmp = self.bytes2rat(Bytes, 0); ord = []
            if not tmp: return {}
            ord.append(round(tmp / 100000.0, 5)) # lat 5 decimals 1.1 meters resolution
            tmp = self.bytes2rat(Bytes, 4)
            if not tmp: return {}
            ord.append(round(tmp / 100000.0, 5)) # lon 5 decimals
            # decode['lat'] = ord[0]; decode['lon'] = ord[1]
            decoded['geohash'] = convert2geohash(ord,precision=11) # 3 meters resolution
            tmp = self.bytes2rat(Bytes, 8)       # alt
            if tmp: decoded['alt'] = round(tmp /10.0, 1) # 1 decimal in meters
        except Exception as e: raise ValueError("GPS decode error: %s\n" % str(e))
        finally:
          # print("decoded GPS %d bytes to: " % len(Bytes)); print(decoded)
          return {'NEO-6': decoded }
    
    def decodeAccu(self,Bytes):            # voltage
        decoded = {}
        # print("Accu %d bytes: " % len(Bytes), Bytes)
        try:
          if Bytes[0] > 0: decoded['accu'] = round(Bytes[0]/10.0,2)
        except Exception as e: raise ValueError("Accu decode error: %s\n" % str(e))
        finally:
          # print("decode d %d bytes Accu to: " % len(Bytes)); print(decoded)
          return {'accu': decoded }
    
    def decodeWind(self,Bytes):           # speed m/sec, direction 0-359 */
        decoded = {}; speed = 0.0; direct = 0
        # print("Wind %d bytes: " % len(Bytes)); print( Bytes)
        try:
          speed = round(Bytes[0]/5.0,1)
          if (Bytes[1] & 0x80): speed += 0.1
          decoded['ws'] = speed
          direct = int(Bytes[1] & 0x7F)
          if direct > 0: decoded['wr'] = (direct*3)%360
        except Exception as e: raise ValueError("Wind decode error: %s\n" % str(e))
        finally:
          # print("decoded Wind %d bytes to: " % len(Bytes)); print(decoded)
          return 'wind', decoded
    
    # identify installed dust, meteo, and GPS presence at measurement kit
    def DecodePort3(self,Bytes,port=3):    # decode meta data at port 3
      if type(Bytes) is str or type(Bytes) is unicode: # encoded
         Bytes = self.Base64Decode(Bytes)
      decoded = {}
      # print("Info/Meta decode %d bytes: " % len(Bytes)); print(Bytes)
      try:
        decoded['version'] = round(Bytes[0] / 10.0,1)
        if Bytes[1] == 0:
          decoded['event'] = Bytes[len(Bytes)-1]
          if Bytes[len(Bytes)-2]: decoded['value'] = Bytes[len(Bytes)-2]
          return decoded
        decoded['dust'] = self.dustTypes[(Bytes[1] & 7)]
        if (Bytes[1] & 8): decoded['gps'] = "NEO-6"  # if True probably NEO-6
        if ((Bytes[1] >> 4) & 15) > len(self.meteoTypes): Bytes[1] = 0
        decoded['meteo'] = self.meteoTypes[((Bytes[1] >> 4) & 15)]
        lati = self.bytes2rat(Bytes, 2)
        if lati:
          decoded['geolocation'] = {}
          # decoded['geolocation']['lat'] = round(lati / 100000.0, 6)
          # decoded['geolocation']['lon'] = round(self.bytes2rat(Bytes, 6) / 100000.0, 6)
          try: # convert deprecated ordinate to geohash
            decoded['geolocation']['geohash'] = convert2geohash([round(lati / 100000.0, 6),round(self.bytes2rat(Bytes, 6) / 100000.0, 6)],precision=11) # 3 meters resolution
          except: pass
          decoded['geolocation']['alt'] = round(self.bytes2rat(Bytes, 10) / 10.0, 6)
      except Exception as e: raise ValueError("Meta decode error: %s\n" % str(e))
      finally:
          # print("decoded Meta info %d bytes into: " % len(Bytes)); print(decoded)
          return {'meta': decoded, 'timestamp': int(time()) }
    
    def DecodePort2or4(self,Bytes, port):   # decode payload for port 2 or 4
      # Decode an uplink message from a node
      # (array) of bytes to an object of fields.
      # print("port %d, %d bytes: " % (port, len(Bytes)); print(Bytes)
      if not port in [2,4] : return {}
      if type(Bytes) is str or type(Bytes) is unicode: # encoded payload
         Bytes = self.Base64Decode(Bytes)
      decoded = { "version": self.version }
      strt = 0; end = 1; Type = 0x0
      # dust [H]HH[HHH[BBB|HHH]]
      if Bytes[0] & 0x80:
        strt = 1; Type = Bytes[0]    # for kit firmware version >0.0
      elif port == 2:                # guess sensor type, deprecated
          if  len(Bytes) == 10:
              decoded.update(self.decodeMeteo(Bytes[:6]))
              decoded.update(self.decodePM(Bytes[6:10]))
              decoded['pm10'], decoded['pm25'] = decoded['pm25'], decoded['pm10']
              del decoded['PMsensor']
              return decoded
          elif  len(Bytes) >= 16: Type |= 0x5; # PM1 gas/aqi
      # PM ug/m3 [H]HH
      end = strt + 4
      if Type & 0x1: end += 2        # PM1
      decodedPM = self.decodePM(Bytes[strt:end])
      strt = end
      if Type & 0x2:                 # PM pcs/0.1dm3
          if port == 2:             # HHHBBB
              decoded.update(self.DecodePort2(Bytes[strt:strt+9]))
              decoded[decoded['PMsensor']].update(decodedPM[decodedPM['PMsensor']])
              del decoded['PMsensor']
              strt += 9
          elif port == 4:             # HHHHHH
              decoded.update(self.DecodePort4(Bytes[strt:strt+12]))
              decoded[decoded['PMsensor']].update(decodedPM[decodedPM['PMsensor']])
              del decoded['PMsensor']
              strt += 12
      else: # check if not Type & 0x2 in firmware probably SDS011
        decoded[decodedPM['PMsensor']] = decodedPM[decodedPM['PMsensor']]
      # meteo HHH[HH]
      end = strt+6
      if len(Bytes) < end:
        return { 'data': decoded, 'timestamp': int(time()) }
      if Type & 0x4: end += 4        # add gas & aqi
      decoded.update(self.decodeMeteo(Bytes[strt:end])); strt = end
      if len(Bytes) >= strt+3*4-1:   #  gps location
          if Type & 0x8:
              decoded.update(self.decodeGPS(Bytes[strt:strt+3*4]))
              strt += 3*4
      if len(Bytes) >= strt+1:       # wind dir/speed
          if Type & 0x10:
              decoded.update(self.decodeWind(Bytes[strt:strt+2]))
              strt += 2
      if len(Bytes) >= strt:         # accu/battery volt
          if Type & 0x20:
              decoded.update(self.decodeAccu(Bytes[strt:strt+1]))
              strt += 1
      return { 'data': decoded, 'timestamp': int(time()) }

    def Decode(self,payload,port=4): # payload decode fie wrapper
      try: return self.PortMap[port][1](payload,port)
      except: raise ValueError("ERROR: Unknown LoRa payload decode for port %d" % port)
    ############### end of class LoRaCode

    
if __name__ == '__main__':
    import sys
    import json
    Coding = LoRaCoding()

    def serialize(record,name):
      rts = {}; dicts = []
      for item, value in record.items():
        if type(value) is dict:
          if name: dicts.append(item)
          add, upd = serialize(value,name)
          rts.update(upd); dicts += add
        else: rts[item] = value
      return dicts, rts

    # convert [0xhex,..,0xhex] to int values for json payload corrections
    def JsonHex2Int(string):
      string = string.replace(' ','')
      if string.find('[') >= 0:
        strt = string.find('[')+1
        end = string[strt:].find(']')
        if end < 0: raise ValueError("List does not end")
        end += strt
      else: return string
      lst = []
      for item in string[strt:end].split(','):
         item = item.strip()
         if item[:2] == '0x' or item[:2] == '0X': item = str(int(item,16))
         lst.append(item)
      lst = ','.join(lst)
      return string[:strt]+ lst + JsonHex2Int(string[end:])

    cnt = 0
    def checkRecord(test):
       global cnt
       cnt += 1
       # guess which TTN V stack the record is generated from
       payload_fields = {}
       try: # is it TTN V2 record?
         payload = test["payload_raw"]
         port = test["port"]
         try: payload_fields = test["payload_fields"]
         except: pass
       except: # is it TTN V3 record?
         try:
           payload = test["uplink_message"]["frm_payload"]
           port = test["uplink_message"]["f_port"]
           try: payload_fields = test["uplink_message"]["decoded_payload"]
           except: pass
         except:
           # sys.stderr.write("ATTENT: unknown TTN version on record %d: %s\n" % (cnt,str(test)))
           return False
         
       try:
          if not port in [2,3,4,10,12]: raise ValueError
       except:
          raise ValueError("WARNING: unable to decode record %s" % str(test))
          return False
       print("########### record test %3.1d\n# Port %2.1d #\n###########" % (cnt,port))
       rslt =  Coding.Decode(payload,port=port)

       if port != 3: # print just the decoded payload
         print("  Payload decoded data:\n\t%s" % str(rslt['data']))
       else:
         print("  Payload decoded meta:\n\t%s" % str(rslt['meta']))

       # ease the check of the key,value pairs
       dicts, result = serialize(rslt,"test record")
       if len(dicts):
         print("  Test record keys with dict value: %s" % ', '.join(dicts))
       print("  Payload decoded serialized:\n\t%s" % str(result))

       if not payload_fields: return # no reference provided
       print("  Payload fields sample:\n\t%s\n" % str(payload_fields))
       try: # convert deprecated ordinate to geohash
          if 'NEO-6' in payload_fields.keys():
            ordinates = payload_fields['NEO-6']
          else: ordinates = payload_fields
          payload_fields['geohash'] = convert2geohash([ordinates['lat'],ordinates['lon']],precision=11) # 3 meters resolution
          del ordinates['lon']; del ordinates['lat']
       except: pass
       dicts, payld = serialize(payload_fields,"payload fields")
       if len(dicts):
         print("  Payload fields example keys with dict value: %s" % ', '.join(dicts))
       print("  Payload example serialized:\n\t%s" % str(payld))

       for item, value in result.items():
         if item in payld.keys():
           print("\t%12.12s: %s %s" % (item,value,("OK" if str(value).replace('.0','')[:8] == str(payld[item]).replace('.0','')[:8] else "should be %s" % str(payld[item]))))
         elif item in ['version','timestamp']:
           print("\t%12.12s not in example, added in decode as %s" % (item, str(value)))
         else:
           print("\t%12.12s (decoded %s) not found in example payload fields" % (item,str(value)))
       for item in payld.keys():
         if not item in result.keys():
            print("\t%12.12s (example %s) not found in decoded record fields" % (item,str(payld[item]))) 


    if len(sys.argv) > 1: # DECODING payload TTN V2 or V3 tests
      # check with data file input raw paytload from TTN
      import os.path
      import json
      # DECODING tests
      for file in sys.argv[1:]:
        if file == '-': fd = sys.stdin # just read from stdin with argument '-'
        else:
          try: fd = open(file,'r')
          except:
            sys.stderr.write("ERROR: unable to read file %s\n" % file)
            continue
        line = ''
        while(1):
          readln = fd.readline().strip()
          if not readln: break
          if 0 <= readln.find('#') < 10:
            sys.stderr.write("COMMENT: %s\n" % readln[readln.find("#")+1:])
            continue
          elif 0 <= readln.find('//') < 10:
            sys.stderr.write("COMMENT: %s\n" % readln[readln.find("//")+2:])
            continue
          #elif readln.find('[0x') > 0:
          #  sys.stderr.write("SKIP json does not support hexadecimals:\n\tline %s" % line)
          #  continue
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
          try: line = json.loads(line)
          except Exception as e:
            sys.stderr.write("JSON ERROR: %s\n" % str(e))
            sys.stderr.write("ERROR in decoding json string: %s\n" % line)
            continue
          checkRecord(line)
          line = ''
        fd.close()
    else: # ENCODING hardcoded firmware payload encoding tests
      # first encode into a raw payload encoding engine rules
      port = 12
      # test sensor data, raw data from sensor, internal to measurement kit, test example
  
      # encode sensor data into encoded LoRa raw payload
      # record is a dict with names of sensors,
      # each item is ordered list, or dict with types of sensed data, or single value
      # next record is intended to be used as standard interface json record
      # TO DO: extend with change to unit of sensed data, and meta data
      SensedData = [
          {
            "version": 0.3,                         # version
            "BME280": [ 32.2, 55.2, 1024.5 ],       # temp C, RH %, hPa
            # alternative "BME280": { "temp": 32.2, "rv": 55.2, "luchtdruk": 1024.5, },
            "NEO-6": { "lon": 5.123456, "lat": 61.123456, "alt":None },
            # "NEO-6": [ 5.123456, 61.123456, None ], # long, lat, alt deprecated
            "WindDIY1": { "wr":120, "ws":34.4 },    # wr degrees, ws m/sec
            # "timestamp": 123456789                # Posix type timestamp 
          },
      ]
      for i in [0]:
        print("LoRa encoding record nr %d:" % i)
        print(SensedData[i])
        payload = Coding.Encode( SensedData[i], port)
        print("Port %d with payload raw: '%s'" % (port,payload))
    # sample records from TTN V2 stack MQTT server:
    # more in file MyLoRaCodeTest.mqtt
    # TTN MQTT V2 examples
    # {"app_id":"201123456771az","dev_id":"gtl-1234567-weerstation","hardware_serial":"0071234567167524","port":12,"counter":70,"payload_raw":"AAEBQgIoBAETQKPzWkJ0fmv/////FAB4AVg=","payload_fields":{"version":1.8,"BME280":{"temp":32.2,"rv":55.2,"luchtdruk":1024.5},"NEO-6":{"lon":5.123456,"lat":61.123456,"alt":None},"WindDIY1":{"wr":120,"ws":34.4},},"metadata":{"time":"2020-10-25T11:07:43.374546797Z","frequency":867.5,"modulation":"LORA","data_rate":"SF7BW125","airtime":87296000,"coding_rate":"4/5","gateways":[{"gtw_id":"gateway_sint_anthonis_004","timestamp":3340903908,"time":"2020-10-25T11:07:43Z","channel":0,"rssi":-107,"snr":4.75,"rf_chain":0}],"lat":51.659508,"lon":5.823824,"location_source":"registry"}},
    # {"app_id":"201123456771az","dev_id":"gtl-1234567-weerstation","hardware_serial":"0071234567167524","port":10,"counter":21253,"payload_raw":"PD0+BjhPhxj9wzfe725vZGVfMDEj1TRgSs3MTL1MAADIQk16tMZHngAAAACfAAAAAKCEDQ8/nQicmpmZQA==","metadata":{"time":"2019-11-29T23:22:06.91516809Z","frequency":868.3,"modulation":"LORA","data_rate":"SF9BW125","airtime":431104000,"coding_rate":"4/5","gateways":[{"gtw_id":"eui-1dee0d671fa03ad6","timestamp":973238836,"time":"","channel":1,"rssi":-78,"snr":12.2,"rf_chain":1,"lat":50.88568,"lon":5.98243,"alt":45}]}}
    # { "port":4, "payload_raw":"hwCCAMwBJoAYQi0XHARYAIAALgH7Aq8D+wCpASs=", "payload_fields":{"version":1.8,"aqi":29.9,"gas":169,"grain":0.5,"rv":68.7,"pm05_cnt":1694.1,"pm1":13,"pm10":29.4,"pm10_cnt":2412.1,"pm1_cnt":2285.7,"pm25":20.4,"pm25_cnt":2396.8999999999996,"pm5_cnt":2409.7,"luchtdruk":1019,"temp":20.7}}
    # { "port":3, "payload_raw":"BUsATqT+AAjuWgAAATk=", "payload_fields":{ "alt":31.3,"dust":"PMS7003","gps":1, "lat":51.54046,"lon":5.85306,"meteo":"BME680","version":0.5}}
    # {"port": 2, "payload_raw": [0x00, 0x00, 0x00, 0x75, 0x00, 0x79, 0x01, 0x7E, 0x04, 0x3B, 0x04, 0x11, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], "payload_fields": { "rv": 108.3, "pm10": 12.1, "pm25": 11.7, "luchtdruk": 1041, "temp": 8.2 }}
    # TTN MQTT V3 example
    # { "end_device_ids": {
    #    "device_id": "meet-2022",
    #    "application_ids": { "application_id": "meet" },
    #    "dev_eui": "00001234567007E6",
    #    "join_eui": "70B12345670003BA",
    #    "dev_addr": "1234567C"
    #  },
    #  "correlation_ids": [
    #    "as:up:01..TH",
    #    "ns:uplink:01..PR",
    #    "pba:conn:up:01..S2",
    #    "pba:uplink:01..A4",
    #    "rpc:/ttn.lorawan.v3.GsNs/HandleUplink:01..JZ",
    #    "rpc:/ttn.lorawan.v3.NsAs/HandleUplink:01..J8"
    #  ],
    #  "received_at": "2021-04-19T14:56:21.194489256Z",
    #  "uplink_message": {
    #    "session_key_id": "AXiyq7cih+RxiSr095ptSQ==",
    #    "f_port": 13,
    #    "f_cnt": 1043,
    #    "frm_payload": "Yf8AAAAAAAATE27HAAUABXRwArcANHADpwA7cBTHAVRwFWcBVnAnZw38",
    #    "decoded_payload": {},
    #    "rx_metadata": [
    #      { "gateway_ids": { "gateway_id": "packetbroker" },
    #        "packet_broker": {
    #          "message_id": "01..A4",
    #          "forwarder_net_id": "000013",
    #          "forwarder_tenant_id": "ttn",
    #          "forwarder_cluster_id": "ttn-v2-eu-2",
    #          "home_network_net_id": "000013",
    #          "home_network_tenant_id": "ttn",
    #          "home_network_cluster_id": "ttn-eu1",
    #          "hops": [
    #            {
    #              "received_at": "2021-04-19T14:56:20.802090918Z",
    #              "sender_address": "52.169.73.251",
    #              "receiver_name": "router-dataplane-f8764784f-p5gbg",
    #              "receiver_agent": "pbdataplane/1.5.2 go/1.16.2 linux/amd64"
    #            },
    #            {
    #              "received_at": "2021-04-19T14:56:20.822681736Z",
    #              "sender_name": "router-dataplane-f8764784f-p5gbg",
    #              "sender_address": "forwarder_uplink",
    #              "receiver_name": "router-7665c7b677-kmdr7",
    #              "receiver_agent": "pbrouter/1.5.2 go/1.16.2 linux/amd64"
    #            },
    #            {
    #              "received_at": "2021-04-19T14:56:20.842067975Z",
    #              "sender_name": "router-7665c7b677-kmdr7",
    #              "sender_address": "deliver.000013_ttn_ttn-eu1.uplink",
    #              "receiver_name": "router-dataplane-f8764784f-p5gbg",
    #              "receiver_agent": "pbdataplane/1.5.2 go/1.16.2 linux/amd64"
    #            }
    #          ]
    #        },
    #        "time": "2021-04-19T14:56:20Z",
    #        "rssi": -121, "channel_rssi": -121, "snr": -9,
    #        "uplink_token": "ey..fQ=="
    #      },
    #      {
    #        "gateway_ids": { "gateway_id": "mjs-gateway-5", "eui": "1DEF5A0000000202" },
    #        "timestamp": 1789330364,
    #        "rssi": -57, "channel_rssi": -57, "snr": 13.2,
    #        "uplink_token": "Ch..IG"
    #      },
    #      {
    #        "gateway_ids": { "gateway_id": "packetbroker" },
    #        "packet_broker": {
    #          "message_id": "01..YH",
    #          "forwarder_net_id": "000013",
    #          "forwarder_tenant_id": "ttn",
    #          "forwarder_cluster_id": "ttn-v2-eu-2",
    #          "home_network_net_id": "000013",
    #          "home_network_tenant_id": "ttn",
    #          "home_network_cluster_id": "ttn-eu1",
    #          "hops": [
    #            { "received_at": "2021-04-19T14:56:20.806279605Z", "sender_address": "52.169.73.251", "receiver_name": "router-dataplane-f8764784f-n76ql", "receiver_agent": "pbdataplane/1.5.2 go/1.16.2 linux/amd64" },
    #            { "received_at": "2021-04-19T14:56:20.820444451Z", "sender_name": "router-dataplane-f8764784f-n76ql", "sender_address": "forwarder_uplink", "receiver_name": "router-7665c7b677-c47hd", "receiver_agent": "pbrouter/1.5.2 go/1.16.2 linux/amd64" },
    #            { "received_at": "2021-04-19T14:56:20.844223755Z", "sender_name": "router-7665c7b677-c47hd", "sender_address": "deliver.000013_ttn_ttn-eu1.uplink", "receiver_name": "router-dataplane-f8764784f-n76ql", "receiver_agent": "pbdataplane/1.5.2 go/1.16.2 linux/amd64" }
    #          ]
    #        },
    #        "time": "2021-04-19T14:56:20Z",
    #        "rssi": -95, "channel_rssi": -95, "snr": 13.25,
    #        "uplink_token": "ey..FQ=="
    #      },
    #      {
    #        "gateway_ids": { "gateway_id": "packetbroker" },
    #        "packet_broker": {
    #          "message_id": "01F3NA3RBC3Y3EV8FXVYMVD7GN",
    #          "forwarder_net_id": "000013",
    #          "forwarder_tenant_id": "ttn",
    #          "forwarder_cluster_id": "ttn-v2-eu-3",
    #          "home_network_net_id": "000013",
    #          "home_network_tenant_id": "ttn",
    #          "home_network_cluster_id": "ttn-eu1",
    #          "hops": [
    #            { "received_at": "2021-04-19T14:56:20.844936722Z", "sender_address": "40.113.68.198", "receiver_name": "router-dataplane-f8764784f-9pp7m", "receiver_agent": "pbdataplane/1.5.2 go/1.16.2 linux/amd64" },
    #            { "received_at": "2021-04-19T14:56:20.851232142Z", "sender_name": "router-dataplane-f8764784f-9pp7m", "sender_address": "forwarder_uplink", "receiver_name": "router-7665c7b677-7tm85", "receiver_agent": "pbrouter/1.5.2 go/1.16.2 linux/amd64" },
    #            { "received_at": "2021-04-19T14:56:20.855688915Z", "sender_name": "router-7665c7b677-7tm85", "sender_address": "deliver.000013_ttn_ttn-eu1.uplink", "receiver_name": "router-dataplane-f8764784f-n76ql", "receiver_agent": "pbdataplane/1.5.2 go/1.16.2 linux/amd64" }
    #          ]
    #        },
    #        "rssi": -119, "channel_rssi": -119, "snr": 0.8,
    #        "uplink_token": "ey..19"
    #      }
    #    ],
    #    "settings": {
    #      "data_rate": { "lora": { "bandwidth": 125000, "spreading_factor": 9 } },
    #      "data_rate_index": 3,
    #      "coding_rate": "4/5",
    #      "frequency": "868100000"
    #    },
    #    "received_at": "2021-04-19T14:56:20.878090650Z",
    #    "consumed_airtime": "0.349184s"
    #  }
    #}
