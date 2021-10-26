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
__modulename__ ='$RCSfile: MyCONSOLE.py,v $'[10:-4]
__version__ = "0." + "$Revision: 3.26 $"[11:-2]
#
# $Id: MyCONSOLE.py,v 3.26 2021/10/26 14:03:43 teus Exp teus $

""" Publish measurements to console STDOUT (uses terminal colors in printout).
    Meta info will be shown on first new data record and at later intervals.
    Data shown will be as complete as possible: data types, calibrations, etc.
    Relies on Conf settings from e.g. main program MyDatacollector.py
    Module can be used in stand alone modus for debugging and tests.
"""

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
    import re
    from time import time
    import datetime
    try: from lib import MyPrint       # for printout in color
    except: import MyPrint
except ImportError as e:
    sys.exit("FATAL: One of the import modules not found: %s" % e)

# configurable options
__options__ = ['output','file','print','operational']

Conf = {
     'output': False,    # console output dflt enabled if no output channels defined
#    'fd': None,         # input handler
     'file': '/dev/stdout',   # Debugging: write to file
     'match': [          # translation table for db abd unit names
        ('C','oC'),      # ('C',u'\u2103'),
        ('F','oF'),      # ('F',u'\u2109'),
        # ('ug/m3',u'\u03BCg/m\u00B3'),
        # ('um',u'\u03BCm'),
        # ('pcs/dm3',u'pcs/dm\u00B3'),
        ('pcs/qf','pcs/0.01qf'),
          ],
     'CalRefs': [],      # which sensor typoe to calibrate with
     'DB': None,         # handle to database
     'print': True,      # if not None try to print color, or False: fifo
     'log': None,        # log print routine (name,level,message)
     'STOP': None        # routine to close named pipe connection, and stop threads
}

# ansi colors:
DFLT   = 0 # grayish
RED    = 1
GREEN  = 2
YELLOW = 3
PURPLE = 5
GRAY   = 8 # dark
BLACK  = 16
DBLUE  = 18
BLUE   = 21
LBLUE  = 33
BROWN  = 52

def printc(text, color=DFLT): # default color ansi black
    global Conf
    try:
      if Conf['print']:
        Conf['print'](text, color=color)
        return
    except: pass
    try: sys.stdout.write(text+'\n')
    except: pass

# meta info printouts
try: from pygeohash import decode
except: from geohash import decode
def registrate(info,artifacts):
    global Conf
    if not Conf['log']:
        try: from lib import MyLogger
        except: import MyLogger
        Conf['log'] = MyLogger.log
    if ('print' in Conf.keys()) and (type(Conf['print']) is bool):
      try:
        try: from lib import MyPrint
        except: import MyPrint
        fifo = False
        if (type(Conf['file']) is str) and (Conf['file'].find('fifo=') == 0):
            # use NAMED PIPE for console output
            fifo = True; Conf['file'] = Conf['file'][5:]
            Conf['STOP'] = Conf['print'].stop
        Conf['print'] = MyPrint.MyPrint(output=Conf['file'], color=Conf['print'], fifo=fifo, date=False)
        Conf['print'] = Conf['print'].MyPrint
      except: Conf['print'] = None

    fnd = None ; new = False
    # should be unique
    ID = []; rts = {}
    try:
      ID = [info['id']['project'],info['id']['serial']]
    except:
      try:
        ID = info['DATAid'].split('_')[:2]
      except: pass
    if not ID:
      try:
        ID = 'MQTT id: ' + info['MQTTid']
        rts = { 'MQTT id': ID } 
      except: ID = None
    else:
        rts = { 'project': ID[0], 'serial': ID[1] }
        ID = 'project: %s, serial: %s' % (ID[0],ID[1])
    showID = False if (info['count'] % 100) != 1 else True
    for one in artifacts:
      if one[:6] in ['Updated home location'[:6],'Change of sensortypes'[:6]]:
        showID = True; break  # force show of identity
    printc('ID%s: %s (#%s) at %s' % ((' (in test)' if info['valid'] == None else ''),str(ID),info['count'],datetime.datetime.fromtimestamp(time()).strftime('%b %d %Y %H:%M:%S')),DBLUE)

    if not showID: return rts
    try:
      if not Conf['DB'] or not info['SensorsID']: return
    except: return rts

    # Show meta information for this kit. (Updated) info from Sensors DB table.
    printc("  Identity info",LBLUE)
    try:
      ident = Conf['DB'].getNodeFields(info['SensorsID'],["label","project","serial","sensors","description","comment","longitude","latitude","altitude","geohash","street","housenr","pcode","village","province","municipality"])
    except: ident = {}
    if ident['housenr'] and ident['street']:
      ident['street'] += ' near %s' % ident['housenr']
    for one in ['WEBactive','active','MQTTid','DATAid']:
      try:
        if type(info[one]) is int:
          ident[one] = 'True' if info[one] else 'False'
        elif info[one] != None: ident[one] = info[one]
      except: pass
    for one in [
       ('Label',["label"]),
       ('Identity',["project","serial"]),
       ('Sensor types',["sensors"]),
       ('Description',["description"]),
       ('Comment',["comment"]),
       ('GPS location',["longitude","latitude","altitude","geohash"]),
       ('Fysical location',["street","pcode","village","province","municipality"]),
       ('Has web page',["WEBactive"]),
       ('Kit installed?',["active"]),
       ('MQTT subscription',["MQTTid"]),
       ('Measurement table',["DATAid"])]:
      try:
        fnd = False; string = ''
        for item in one[1]:
          if not ident[item]: continue
          if not fnd:
            string = "%-32.31s: " % one[0]
            fnd = True
          if item[:4] == 'geoh': string += 'geohash #%s, ' % ident[item]  
          elif type(ident[item]) is str: string += ident[item]+', '
          elif type(ident[item]) is unicode: string += str(ident[item])+', '
          elif item[:4] == 'alti': string += 'alt %dm, ' % int(ident[item])
          elif type(ident[item]) is float: string += 'l%s %.7f, ' % (item[1:3],ident[item])
          else: string += str(ident[item])+', '
      except: pass
      if string: printc('    '+string[:-2])
    return rts

# return Taylor sequence correction
def Taylor(avalue,seq,PM=True):
    if avalue == None: return None
    if not seq: return avalue
    rts = 0; i = 0
    try:
      for v in seq:
        rts += v*avalue**i; i += 1
    except: rts = avalue
    return (rts if rts > 0.0 else 0.01) if PM else rts

# get Taylor seq for refs
def getCalibration(serialized, stype, refs=[]):
    if not serialized: return None # similar to [0,1] Taylor
    if type(serialized) is list: return serialized

    # deprecated, is converted to list in MyDatacollector
    if not refs: return None
    if type(serialized) is dict: # has per ref a Taylor list
      for one in refs:
        try:
          if one.upper() == stype.upper(): return serialized[one]
        except: pass
      return None
    # deserialize calibration info string
    try: serialized = serialized.split('|')
    except: return None
    for ref in refs:
      ref = re.compile(ref+'/.*',re.I)
      if ref.match(stype): return None  # do not calibrate against similar sensor type
      for i in range(len(serialized)):
        if ref.match(serialized[i]): return [float(a) for a in serialized[i].split('/')[1:]]
    return None
    
# use meta sensor info, sensor type name, and field, and optional list of taylor ref types
# return category,sensor type/product name, sensor field name, unit, calibration Taylor seq
# e.g. findInfo('windDIY',['', u'BME280', u'NEO-6', u'windDIY1'],'ws')
def findInfo(SType,sensorInfo,field,refs=[]):
    UT = ['','','',field,'',None]   # (category,sensor type,producer,field,unit,calibration)
    # the game of unicode from DB queries and str from old style
    item = None
    for item in sensorInfo:
      if not item: continue
      try:
        if type(item['match']) in [str,unicode]:
          item['match'] = re.compile(item['match'],re.I)
        if item['match'].match(SType):
          break
      except:
        try:
          if SType.upper() == item['type'].upper(): break
        except: pass
      item = None
    if not item: return [SType,SType,field,'',None]
    for one in item['fields']:
      # one = (field,unit[,calibration])
      if str(field).lower() == one[0].lower():
        try:
          try: UT[0] = item['category']
          except: pass
          try: UT[1] = item['producer']
          except: pass
          UT[2] = item['type']
          UT[3:5] = [one[0],one[1]]
          try:
            if type(one[2]) is list:
              if len(one[2]): UT[5] = one[2]
            else:
              UT[5] = getCalibration(one[2],SType,refs=refs)  # 5/1.5 -> [5,1.5] Taylor
          except: pass
        except: pass
        break
    return UT
    
# Returns a sorted by field name list of acredited values per a sensor type.
# List item:
# [0:category, 1:sensor type, 2:field name, 3 unit, 4 calibration Taylor seq, 5 value]
def MeasurementsList(sensorInfo,Stype,item,refs=[]):
    def element(iterable):
        return(iterable[3])
    vals = []
    if type(item) is list:
      for one in item:
        vals += MeasurementsList(sensorInfo,Stype,one,refs=refs)
    #elif type(item) is dict:
    #  for one in item.keys():
    #    vals += MeasurementsList(sensorInfo,...
    elif not type(item) is tuple:
      # Conf['log'].log(WHERE(),'ERROR',"Error in data format for %s: %s" % (Stype,str(item)))
      printc("    Error in data format for %s: %s" % (Stype,str(item)),RED)
    else:
      UT = findInfo(Stype,sensorInfo,item[0],refs=refs)
      # list of category,SensorType,producer,field,unit,calibration seq or None, value
      UT.append(item[1])  # 6: value
      # To Do: if unit in data convert units
      vals.append(UT)
    if len(vals) == 1: return vals
    vals.sort(key=element)
    return vals

# print a list of measurements in data part of record
def printFld(sensorInfo,SType,data,refs=[]):
    global Conf
    def trans(name):
        if not name: return ''
        if (not 'match' in Conf.keys()) or (not type(Conf['match']) is list):
            return name
        for item in Conf['match']:
             if not type(item) is tuple: continue
             if name.find(item[0]) < 0: continue
             name = name.replace(item[0],item[1])
        return name
    for item in MeasurementsList(sensorInfo,SType,data,refs=refs):
      # item: [0:category,1:sensor type,2:producer,3:field,4:unit,5:calibration,6:value]
      # ST: category/sensor type.producer, item[5] value, item[4] calibration, item[3] units
      ST = "%s" % ('' if not item[0] else item[0]+'/')      # category
      ST += "%s" % ('?' if not item[1] else item[1])        # sensor type
      ST += "%s" % ('' if not item[2] else '.'+item[2])     # producer sensor
      FLD = item[3] if item[3] else '?'                     # sensor field/column name
      if item[6] == None:
        VAL = 'None'; UNIT = ''
      else:
        VAL = item[6]; UNIT = item[4]                       # value and unit name
      if item[5] and item[5] != [0,1] and type(item[6]) in (int,float):
        CAL = '(calibrated %.2f)' % Taylor(item[6],item[5]) # calibration seq
      else: CAL = ''
      if type(VAL) is bool: VAL = str(VAL)
      elif type(VAL) is float:
        if FLD[:3].lower() in ['lat','lon']: VAL = ".6f" % VAL
        else: VAL = "%.1f" % VAL
      elif type(VAL) is int: VAL="%d" % VAL
      ST = ST.ljust(31-len(FLD))+' '+FLD
      printc("    %-32.32s: %s%s%s" % (ST,VAL,CAL,' '+trans(UNIT) if UNIT != '%' else '%'))
      # to be added: refs
  
# =============================================
# print telegram with measurement values on console
# =============================================
# import datetime

# entry point to forward measurements to measurements table in the database
# returns:
#     True: OK stored, False: no data to be stored
#     string: failure reason on output
#     list of strings: ok : string which one of the sub output channels had result
# raised event on failure in eg connection, query error
# publish the measurement arguments: data (dict), meta info dict, artifacts (list)
# returns success
channels = {
   'forwarding': [('MQTT appl/topic: ','MQTTid'),('Sensors Community','Luftdaten')],
   'network': [('TTN version: ','type'),('#gateways seen: ','gateways')],
}

# print a human readable version of the data record
def publish(**args):
    global Conf
    
    if not Conf['output']:
      return False
    try:
      info = args['info']; data = args['data']; artifacts = args['artifacts']
    except: return "Console publish arguments error"
    # ??? net = args['net'] with gateway info

    id = registrate(info,artifacts)

    printc('  Measurements:',LBLUE)
    for one in sorted(data.keys(), reverse=True):
      if one == 'data': continue
      elif one == 'timestamp':
        printc("    %-32s: %d (%s)" % ('time',data[one],datetime.datetime.fromtimestamp(data[one]).strftime("%Y-%m-%d %H:%M:%S")))
      elif one == 'version':
        printc("    %-32s: %s" % ('data version',data[one]))
      elif one == 'id':
        if data[one] != id:
          printc("    %-32s: %s" % ('identification', str(data[one])))
      elif one == 'net':
          # e.g. {'TTN_id': u'salk-20190614', 'TTN_app': u'201802215971az',
          #      'type': 'TTNV2',
          #      'gateways': [{'rssi': -64, 'snr': 11,
          #           'gtw_id': u'eui-000080029c641f55', 'geohash': 'u1hjx4xkt72'}]}
          string = []
          for CHid,CHval in channels.items():
            for item in CHval:
              try:
                if type(data[one][item[1]]) is list: val = "%d" % len(data[one][item[1]])
                else: val = data[one][item[1]]
                string.append('%s %s' % (item[0], str(val)))
              except: pass
            if string: printc("    %-32s: %s" % (CHid,', '.join(string)))
      else:
        printc("    %-32s: %s" % ('unknown',str(data[one])))

    extra = []; color = BLACK
    for one in [('validity measurements','valid'),]:
      try:
        value = info[one[1]]
      except: continue
      if value != None:
        if one[1] != 'count': value = True if value else False
        if not value: color = RED
      else:
        value = 'TESTED'; color = YELLOW
      extra.append("%s: %s" % (one[0],str(value)))
    if extra: printc("    %s" % ', '.join(extra),color)

    refs = []
    try: refs = info['CalRefs']
    except: refs = Conf['CalRefs']
    finally: pass
    try:  #  show measurements
      for item in sorted(data['data'].keys(), reverse=True):
        if not item: continue
        try: printFld(info['sensors'],item,data['data'][item],refs=refs)
        except: pass
    except: pass

    if artifacts and type(artifacts) is list:
      printc("  Artifacts:",LBLUE)
      for item in artifacts: printc("    %s" % item)
    return True

# test main loop
if __name__ == '__main__':
    Conf['output'] = True
    import MyDB
    Conf['DB'] = MyDB
    Conf['CalRefs'] = ['SDS011']   # use these sensor types as calibration ref

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
                print("Record ID %s, result: %s" % (str(one['info']['id']),str(result)))
            except:
                print("Record ID NOT DEFINED, result: %s" % (str(info['id']),str(result)))
        except Exception as e:
            print("output channel error was raised as %s" % e)
         
        timings = 10 - (int(time())-timings)
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

