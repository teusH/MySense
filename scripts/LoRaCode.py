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

# $Id: LoRaCode.py,v 1.8 2020/12/02 09:21:43 teus Exp teus $

# WARNING do not use in full operational environment
# subject to change without notice.
# Proposal model implementation. Development Draft Request for Commments and Improvements
# This is a prototype model to obtain feasibility of a standard approach
# do not expect all functions are implemented yet
# as well do not expect to apply yet in full life yet.

# this approach will define for every LoRa port a unique LoRa encoding format
# library and test lib for handling LoRa encode and decode payloads
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

# use NaN as indicator for None or NULL values
# INFINITY = 1e200 * 1e200
# NAN = INFINITY / INFINITY

# LoRa encode  and decode to payload using LoRa code rules engine
#
# it uses Default unit attributes so exchange data format will be as "sensorproduct": {"sensortype1": (value,["unit type"]), ...}
# unit type is omitted if it is a default unit type e.g. C for Celcius degrees.
# the codings rule is identified (PortMap dict) either by "identifier" (string) or LoRa channel/port number (int)
# engine routines are LoRaCoding.Encode(): encode to LoRa payload and
#                     LoRaCoding.Decode(): decode the LoRa base64 payload
class LoRaCoding:
    def __init__(self, LoRaCodeRules=None, DefaultUnits = ['%','C','hPa','mm/h','degrees', 'sec','m','Kohm','ug/m3','pcs/m3','m/sec'], PortMap=None):
      # arguments:
      # LoRaCodeRules: a dictionary with coding rules, default: use defualt rule set
      # DefaultUnits: a list of defaukt unit types for measurement values. May be empty to force units in value tuple
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
      
      # dictionary with different LoRa encoding formats
      if LoRaCodeRules == None:
        LoRaCodeRules = {
          'DIY0': [
              # packing: >hhhhhh wr, ws, accu, temp, rv, pressure
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
              [21,'Argent',[['wr','H',NANh,[0,1.0],'degrees'],['ws','H',NANH,[0,10.0],'m/sec'],['rain','H',NANH,[0,10.0],'mm']] ],
              # wind dir, wind speed
              [22,'Ultrasonic',[['wr','H',NANh,[0,1.0],'degrees'],['ws','H',NANH,[0,10.0],'m/sec']] ],
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
              ['<','VERSION', [['header','3sBBQ#s?B',None,None, ['?start','type','?size','serial','?WASPid','?','?seq']]] ], # type,size-5 bytes,serial,ID,sep,sequence nr
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
          12: 'weerDIY1',
          10: 'Libelium'
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
     
    # compile a pack format and data dict to 2 pack and data list for encoding
    # data record is a dict with names of sensors,
    # each item is ordered list, or dict with types of sensed data, or single value
    # to do: variable size string with end of string mark (see Libelium header style)
    def Encode(self, data, ProdID ):
        import struct
        import base64
        rts = ''
        if type(ProdID) is int:
            try: ProdID = self.PortMap[ProdID]
            except: pass
        if not ProdID in self.LoRaCodeRules.keys():
            print "Unknown LoRa  payload coding product ID: %s" % format
            return rts
        if ProdID == 'Libelium':
            print("Libelium encoding is not yet supported")
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
            print(str(e))
            print("Error in pack %s:" % pck, values)
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
                    if packed[j] == strg[i]:
                        pck += '%d' % (j-cnt); mul = j-cnt
                        break
        return (cnt, pck)
    
    def Decode(self,raw,ProdID,timestamp=None):
        import base64
        import struct
        import datetime
        import dateutil.parser as dp
        from time import time
    
        if type(ProdID) is int:
            try: ProdID = self.PortMap[ProdID]
            except: pass
        if not ProdID in self.LoRaCodeRules.keys():
            raise valueError("Unknown LoRa payload encoding product ID: %s" % ProdID)
        frmt = self.LoRaCodeRules[ProdID]
        PackedData = base64.decodestring(raw)
    
        i = -1; endian = frmt[0][0]; data = { 'ProdID': ProdID, }
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
                print("Datagram error for %s on port or format %s with %e. Skip." % (raw,str(format),str(e)))
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
                  data[item[1]][fields[j][0]] = self.GetVal(values[j],fields[j][2],fields[j][3])
                  try:
                    if fields[j][4] and (not fields[j][4] in DefaultUnits):
                      if not 'units' in data[item[1]].keys(): # add unit type if not default
                        data[item[1]][fields[j][0]] = (self.GetVal(values[j],fields[j][2],fields[j][3]),fields[j][4])
                    else: 
                        data[item[1]][fields[j][0]] = (self.GetVal(values[j],fields[j][2],fields[j][3]),)
                  except: pass
              except:
                print("Decode error with sensor ID %d (fields %s, values %s)" % (i, str(fields), str(values)))
        except Exception as e:
            print("Decode error: %s" % str(e))
            return data
        # if defined it is in UTC time
        if type(timestamp) is str: timestamp = int(dp.parse(timestamp).strftime("%s"))
        if len(data): data['time'] = int(time()) if timestamp == None else int(timestamp)
        for one in ['VERSION']: # push these on time dict level
            if not one in data.keys(): continue
            if type(data[one]) is dict:
              for item in data[one].keys():
                if item[0] == '?': continue
                if item in ['serial'] and (not type(data[one][item]) is str):
                  data[one][item] = '%x' % data[one][item] # some have just a unsigned long
                data[item] = data[one][item]
              del data[one]
        return data
    
if __name__ == '__main__':
    Coding = LoRaCoding()
    port = 12
    # test sensor data, raw data from sensor, internal to measurement kit, test example

    # encode sensor data into encoded LoRa raw payload
    # record is a dict with names of sensors,
    # each item is ordered list, or dict with types of sensed data, or single value
    # next record is intended to be used as standard interface json record
    # TO DO: extend with change to unit of sensed data, and meta data
    SensedData = [
        {
            "version": 0.0,                         # version
            "BME280": [ 32.2, 55.2, 1024.5 ],       # temp C, RH %, hPa
            # alternative "BME280": { "temp": 32.2, "rv": 55.2, "luchtdruk": 1024.5, },
            "Neo-6": [ 5.123456, 61.123456, None ], # long, lat, alt
            "WindDIY1": { "wr":120, "ws":34.4 },    # wr degrees, ws m/sec
            # "timestamp": 123456789                # Posix type timestamp 
        },
    ]
    for i in [0]:
        print("LoRa encoding record nr %d:" % i)
        print(SensedData[i])
        payload = Coding.Encode( SensedData[i], port)
        print("Port %d with payload raw: '%s'" % (port,payload))

    # decode raw LoRa payload according to pack format indicated by port nr
    # as received from TTN MQTT interface
    # use self.PortMap to obtain portnr from format name
    # [ [ portnr, payload ], ...]
    records =  [
        { "port": port, "payload_raw": Coding.Encode(SensedData[0],port) },
        # sample record from TTN MQTT server:
        # 201802215971az/devices/gtl-kipster-weerstation/up {"app_id":"201802215971az","dev_id":"gtl-kipster-weerstation","hardware_serial":"0078CECEA5167524","port":12,"counter":70,"payload_raw":"AAEBQgIoBAETQKPzWkJ0fmv/////FAB4AVg=","payload_fields":{"version":0.0,"BME280":{"temp":32.2,"rv":55.2,"luchtdruk":1024.5},"Neo-6":{"logitude":5.123456,"latititude":61.123456,"altitude":None},"WindDIY1":{"wr":120,"ws":34.4},},"metadata":{"time":"2020-10-25T11:07:43.374546797Z","frequency":867.5,"modulation":"LORA","data_rate":"SF7BW125","airtime":87296000,"coding_rate":"4/5","gateways":[{"gtw_id":"gateway_sint_anthonis_004","timestamp":3340903908,"time":"2020-10-25T11:07:43Z","channel":0,"rssi":-107,"snr":4.75,"rf_chain":0}],"latitude":51.659508,"longitude":5.823824,"location_source":"registry"}},
        {  "app_id":"applicationID","dev_id":"MySenseData",
           "hardware_serial":"D4973556E6375618",
           "counter":70,
           "port":12,
           "payload_raw":"AAEBQgIoBAETQKPzWkJ0fmv/////FAB4AVg=",
           "payload_fields": {
             "version": 0.0,                         # version
             "BME280": { "temp": 32.2, "rv": 55.2, "luchtdruk": 1024.5, },
             "Neo-6": [ 5.123456, 61.123456, None ], # long, lat, alt
             "WindDIY1": { "wr":120, "ws":34.4 },    # wr degrees, ws m/sec
           },
           "metadata":{
              "time":"2020-09-14T22:35:04.515801716Z",
              "frequency":867.9,"modulation":"LORA","data_rate":"SF7BW125",
              "airtime":87296000,"coding_rate":"4/5",
              "gateways":[
                {"gtw_id":"eui-b827ebfffe65b8e9","timestamp":2171653268,
                "time":"2020-09-14T22:35:04.502767Z","channel":7,"rssi":-83,
                "snr":10.2,"rf_chain":0,
                "latitude":51.42083,"longitude":6.13541,"altitude":23}]
            }
        },
        # real life examples:
        # sample data record from TTN MQTT server:
        # 201802215971az/devices/gtl-kipster-weerstation/up {"app_id":"201802215971az","dev_id":"gtl-kipster-weerstation","hardware_serial":"0078CECEA5167524","port":10,"counter":21253,"payload_raw":"PD0+BjhPhxj9wzfe725vZGVfMDEj1TRgSs3MTL1MAADIQk16tMZHngAAAACfAAAAAKCEDQ8/nQicmpmZQA==","metadata":{"time":"2019-11-29T23:22:06.91516809Z","frequency":868.3,"modulation":"LORA","data_rate":"SF9BW125","airtime":431104000,"coding_rate":"4/5","gateways":[{"gtw_id":"eui-1dee0d671fa03ad6","timestamp":973238836,"time":"","channel":1,"rssi":-78,"snr":12.2,"rf_chain":1,"latitude":50.88568,"longitude":5.98243,"altitude":45}]}}
        # {'VERSION': {'seq': 35, 'WASPid': 'node_01', 'start': '<=>', 'serial': 17284313734798935887L, 'type': 6, 'size': 56}}
        {"app_id":"application id","dev_id":"Libelium weerstation",
          "hardware_serial":"0078CECEA5167524",
          "port":10,
          "payload_raw":"PD0+BjhPhxj9wzfe725vZGVfMDEjKDRgSoXrQcBMAADIQk3Jc8lHngAAAACfAAAAAKAAAAAAnQCcAAAAAA==",
          "counter":24152,
          "payload_fields": {
            "accu": 96.0, "temp": -3.03, "rv": 100.0, "luchtdruk": 1031.44,
            "rain": 0, "prevrain": 0, "dayrain": 0 },
          "metadata":{
            "time":"2019-12-31T23:43:41.396235563Z","frequency":868.1,
            "modulation":"LORA","data_rate":"SF9BW125","airtime":431104000,
            "coding_rate":"4/5",
            "gateways":[
                {"gtw_id":"eui-1dee0d671fa03ad6","timestamp":2263727172,"time":"",
                 "channel":0,"rssi":-81,"snr":12.8,"rf_chain":1,
                 "latitude":50.88568,"longitude":5.98243,"altitude":45}
            ]
            }
        },
        {  "app_id":"applicationID","dev_id":"MySenseData",
           "hardware_serial":"D4973556E6375618",
           "counter":9075,
           "port":4,
           "payload_raw":"hwCCAMwBJoAYQi0XHARYAIAALgH7Aq8D+wCpASs=",
           "payload_fields":{"TTNversion":"1.7","aqi":29.9,"gas":169,"grain":0.5,"humidity":68.7,"pm05_cnt":1694.1,"pm1":13,"pm10":29.4,"pm10_cnt":2412.1,"pm1_cnt":2285.7,"pm25":20.4,"pm25_cnt":2396.8999999999996,"pm5_cnt":2409.7,"pressure":1019,"temperature":20.7},
           "metadata":{
              "time":"2020-09-14T22:35:04.515801716Z",
              "frequency":867.9,"modulation":"LORA","data_rate":"SF7BW125",
              "airtime":87296000,"coding_rate":"4/5",
              "gateways":[
                {"gtw_id":"eui-b827ebfffe65b8e9","timestamp":2171653268,
                "time":"2020-09-14T22:35:04.502767Z","channel":7,"rssi":-83,
                "snr":10.2,"rf_chain":0,
                "latitude":51.42083,"longitude":6.13541,"altitude":23}]
            }
        },
        {  "app_id":"applicationID","dev_id":"MySenseKitMeta",
           "hardware_serial":"AAAA807D3A9369F4",
           "counter":2349,
           "port":3,
           "payload_raw":"BUsATqT+AAjuWgAAATk=",
           "payload_fields":{
                "altitude":31.3,"dust":"PMS7003","gps":1,
                "latitude":51.54046,"longitude":5.85306,"meteo":"BME680","version":0.5},
           "metadata":{
              "time":"2020-09-15T06:50:29.611740736Z","frequency":868.1,
              "modulation":"LORA","data_rate":"SF7BW125","airtime":66816000,
              "coding_rate":"4/5",
              "gateways":[
                {"gtw_id":"eui-60c5a8fffe766217","timestamp":2411118411,"time":"",
                "channel":0,"rssi":-105,"snr":6,"rf_chain":0},
                {"gtw_id":"gateway_sint_anthonis_005","timestamp":2865187259,
                "time":"2020-09-15T06:50:29Z","channel":0,"rssi":-119,"snr":-3.5,
                "rf_chain":0}]
           }
        },
        {  "app_id":"applicationID","dev_id":"MySenseDeprecated",
           "hardware_serial":"D4973556E6375616",
           "counter":14776,
           "port":2,
           "payload_raw":"hQAAAPIBEgHGAzMD+QBKAOc=",
           "payload_fields":{
                "aqi":23.1,"voc":74,"rv":81.9,"pm10":27.4,"pm25":24.2,
                "luchtdruk":1017,"temp":15.4},
           "metadata":{"time":"2020-09-15T07:00:49.806590697Z","frequency":868.5,
           "modulation":"LORA","data_rate":"SF7BW125","airtime":71936000,
           "coding_rate":"4/5",
           "gateways":[{"gtw_id":"eui-60c5a8fffe766217","timestamp":3031311307,"time":"","channel":2,"rssi":-100,"snr":5.5,"rf_chain":0},{"gtw_id":"eui-7276ff000b032609","timestamp":3899537203,"time":"2020-09-15T07:00:49.790066Z","channel":2,"rssi":-114,"snr":-0.8,"rf_chain":0,"latitude":51.44635,"longitude":5.48513,"altitude":75}]
           }
        }
      ]
    print("Decoding some examples:")
    for i in [0,2]:
        print("Decode(\"%s\")" % records[i]['payload_raw'])
        data = Coding.Decode(records[i]['payload_raw'],records[i]['port'])
        print(data)

