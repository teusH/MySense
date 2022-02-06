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

# $Id: MyARCHIVE.py,v 5.20 2022/02/06 14:58:40 teus Exp teus $

# reminder: MySQL is able to sync tables with other MySQL servers
# based on MyDB.py V4.5

""" Publish measurements to MySQL database
    Relies on Conf setting by main program
"""
__modulename__='$RCSfile: MyARCHIVE.py,v $'[10:-4]
__version__ = "0." + "$Revision: 5.20 $"[11:-2]
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
    import os
    import datetime
    from time import time
    import re
    import atexit
except ImportError as e:
    sys.exit("FATAL: One of the import modules not found: %s"% e)

# configurable options
__options__ = ['output','calibrate','DB','log','level','DEBUG']

Conf = {
    'output': False,     # output to database
    'DB': None,          # measurements database module to be used
    'log': None,         # MyLogger log routine
    'level': None,       # MyLogger log level, default INFO
    'DEBUG': False,      # Debugging info
                         # Reg. expression: fields not archived in DB
    'omit' : '(time|geolocation|coordinates|version|gps|meteo|dust|net|pwr|gwlocation|event|value)',
                         # Reg. expression of publication skipped on these artifacts
    'dontSkip': '(Forward data|New kit|Restarted kit|Static|Updated|Sensor.*Out).*' # only to handle data with these artifacts
}

# update kits cache, return list of value tuples as (field,value)
# check if field is supported and field name already exists in measurement table
# returns False (not supported), True (exists in measurement table), fieldname (supported, not exists)
# measurement table supported columns/fields are defined in MyDB.py getFieldInfo(), SupportedFields (reg exp)
def checkField(tableName, info, field):
    global Conf
    if field in info['fields']: return True
    DB = Conf['DB']   # SupportedFields
    if not DB.SupportedFields.match(field):
      try:
        if type(info['unknown_fields']) is list:
          info['unknown_fields'] = set(info['unknown_fields'])
      except: info['unknown_fields'] = set([])
      if not field in info['unknown_fields']:
        # Conf['log'](WHERE(),'ATTENT',"Unknown field '%s' for table %s. Skipped." % (field,tableName))
        info['unknown_fields'] |= set([field])
      return False
    return field  # add sensor field/column name to measurement table column names

def AddColumns(info,tableName,toAdd):
    global Conf
    qry = []
    for fld in toAdd:
      qry.append("ADD COLUMN %s %s" % (fld, Conf['DB'].Sensor_fields[str(fld)][0].replace("MMENT '",datetime.datetime.fromtimestamp(time()).strftime("MMENT 'dd %Y-%m-%d %H:%M, unit "))) )
      qry.append("ADD COLUMN %s_valid %s" % (fld,Conf['DB'].getFieldInfo('_valid')[0]))
    if len(qry):
      try:
        Conf['DB'].db_query("ALTER TABLE %s %s" % (tableName,','.join(qry)),False)
      except IOError: raise IOError
      except:
        Conf['log'](WHERE(True),'ERROR',"Unable to add column(s): %s" % ', '.join(toAdd))
        info['unknown_fields'] |= set(toAdd)
        return False
    Conf['log'](WHERE(),'ATTENT',"Added new column(s) '%s' to table %s" % (','.join(toAdd),tableName))
    info['fields'] |= set(toAdd)
    return True

# upgrade measurement table for one field/column
def UpgradeTable(tableName,field):
    global Conf
    try:
      Conf['DB'].db_query("ALTER TABLE %s ADD COLUMN %s VARCHAR(64) DEFAULT NULL COMMENT '%supgrading table'" % (tableName, field, datetime.datetime.fromtimestamp(time()).strftime("added %Y-%m-%d, ")), False)
    except:
      Conf['log'](WHERE(True),'ERROR',"Unable to add column(s): %s" % field)
      return False
    return True

# arguments example: info (dict), record (dict), artifacts (list)
#
# info:
# {'count': 1,
#  'id': {'project': u'SAN', 'serial': u'b4e2df4b3611'},
#  'DATAid': u'SAN_b4e62d4fb311',
#  'TTNtableID': 1565969067,
#  'valid': 1,  # if None values are not valid e.g. indoor measurements
#  'SensorsID': 1531639787,
#  'active': 1,
#  'Luftdaten': u'b462d4fe3b11',
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
#     'ttl': 1630373493}
#   ],
#  'location': u'u1hjztwmqd',
#  'kit_loc': '',  # if not atr home location it has the geohash
#  'MQTTid': u'201802215971az/bwvlc-1b31',
#  'unknown_fields': set([]),
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
#
# artifacts: [
#  'Forward data',                   'Start throttling kit: %s',
#  'Skip data. Throttling kit.',     'Unknown kit: %s',
#  'Unregistered kit: %s',           'MQTT id:%s, %s kit. Skipped.',
#  'Raised event: %s.',              'Updated home location',
#  'Kit removed from home location', 'New kit',
#  'Restarted kit',                  'Out of Range sensors: %s',
#  'Static value sensors: %s',       'Updated sensor types: %s -> %s',
#  'Measurement data format error',  'No input resources',
#  'Update firmware %s',             'Update sensor types: '%s',
#  'Static value sensors %s',        'Sensors with None value: %s',
#  'End of iNput Data',              'Fatal error on subscriptions',
# ]

def registrate(tableName, info, data):
    global Conf
    if type(Conf['omit']) is str: Conf['omit'] = re.compile(Conf['omit'])
    toAdd = []
    try: info['fields']
    except:
      if not Conf['DB'].db_table(tableName):
        raise ValueError("No archive table available")
      # we rely on the fact that fields in ident denote all fields in data dict
      # at some time check on 'sensors' and upgrade action should go away
      table_flds = Conf['DB'].db_query("SELECT column_name FROM information_schema.columns WHERE  table_name = '%s' AND table_schema = '%s' AND (column_name like '%%_valid' OR column_name = 'sensors')" % (tableName,Conf['DB'].Conf['database']),True)
      table_flds = set([ a[0].replace('_valid','') for a in table_flds])
      # only once to upgrade measurement table (should go away)
      if not 'sensors' in table_flds: UpgradeTable(tableName,'sensors')
      else: table_flds -= set(['sensors'])
      info['fields'] = table_flds
    valid = True
    try:  # True if in operation, None if invalid values, False if not active
      valid = True if info['valid'] else None
      if not info['active']: valid = False if valid else None
    except: pass

    # all measurements, column names to update, new column names, sensors used, double field names
    measurements = []; fields = []; toAdd = []; sensors = []; doubles = []
    Lon = None; Lat = None; GeoIndx = None
    # allow only one field name, skip double fields. To Do: use average
    for values in data.items(): # ('BME680', [(u'rv', 69.3, ...),...]) or (u'rv',69.3,...)
      if type(values) in [list,tuple]:
        # it might happen that data record has dicts iso tuples or lists
        #if type(values[1]) is dict: # a hack convert {'bme280': { 'rv': 35.0,...}, ... to [('rv',35,0),...
        #  ValArray = []
        #  for sens, value in values[1].items(): ValArray.append((sens,value))
        #  values[1] = ValArray
        #  # sys.stderr.write("CHANGED DICT values[1]. Values (%s). Data: %s\n" % (str(values),str(data)))
        if type(values[1]) in [list,tuple]:  # ('BME680', [(u'rv', 69.3, ...),...])
          sensors.append(values[0]); values = values[1]
        else:                                # convert to sensor rv (u'rv',69.3,...)
          sensors.append(values[0]); values = [values]
        for value in values:
          if type(value) is tuple: value = list(value)
          if type(value) is list:
            try:
              if value[0] in info['unknown_fields']:
                continue                               # old not supported field
            except: pass
            if Conf['omit'].match(value[0]): continue  # do not archive unwanted sensors
            checked = checkField(tableName, info, value[0])
            if not checked:
              Conf['log'](WHERE(True),'ATTENT',"Not supported sensor field '%s', value: %s. Skipped." % (value[0],str(value)))
              continue                   # new not supported field
            elif not type(checked) is bool:            # add new column to table
              toAdd.append(checked)
            # on GPS location no unit correction or calibration
            if value[0] == 'geohash':   GeoIndx = len(fields)
            if value[0]   == 'longitude': Lon = value[1]
            elif value[0] == 'latitude':  Lat = value[1]
            else:
              # (field, value, valid[, calibration seq])
              if value[0] in fields:                   # doubles, collect to caculate average later
                doubles.append(value[:2]+[valid if value[1] != None else (0 if valid else None),]+value[2:])
              else:
                measurements.append(value[:2]+[valid if value[1] != None else (0 if valid else None),]+value[2:])
                fields.append(value[0])
    if Lon != None and Lat != None: # calculate and add/correct geohash kit location
      try: import mygeohash as geohash
      except: import geohash
      if GeoIndx == None:
        measurements.append((u'geohash',str(geohash.encode(float(Lat),float(Lon),12),valid)))
        fields.append(u'geohash')
      else:
        measurements[GeoIndx] = (u'geohash',str(geohash.encode(float(Lat),float(Lon),12),valid))
    if toAdd: AddColumns(info,tableName,set(toAdd))
    # To Do: handle doubles -> average in measurements list (here no calibration diff is applied)
    # def calcAvg(mnts, dbls):
    #   for i in range(len(dbls)-1):
    #     if dbls[i] == None: continue
    #     cnt = 0; val = 0; fld = None
    #     for j in range(i,len(dbls)-1):
    #       fld = dbls[i][0]
    #       if dbls[j] == None: continue
    #       if dbls[j][0] == fld:
    #         cnt += 1; val +=  dbls[j][1]; dbls[i] = None
    #     if not fld: continue
    #     for j in range(len(mnts)-1):
    #       if  fld = mnts[j][0]: mnts[j] = (fld,(val+mnts[j][1])/(cnt+1.0))
    # if doubles: calcAvg(measurements, doubles)
    # To Do: add kit_loc geohash if kit is mobile and if kit not producing geo info

    if not measurements: return ([],[])
    sensors = sorted(set(sensors))
    return (sensors,measurements)

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

# unit conversion table to archive DB unit standard
UnitConversion = {
    "Pa": [0,0.01],  # Pa -> hPa
}

# Return calibated (if defined) value, unit converted
def correctValue(info,field,value,unit): # unit is [unit,[value calibration seq],...]
    try:
      for item in info['sensors']:
        for one in item['fields']:
          if field == one[0]:
            # calibrate on info calibration Taylor seq. Not taylor from unit[1]
            if len(one) > 2 and ( type(one[2]) is list) and field == one[0]:
              value = Taylor(value,one[2], True if field[:2] == 'pm' else False)
            break
        else: continue
        break
    except: pass
    # first calibrate, then unit convert?
    if unit:
      try:
        value = Taylor(value,UnitConversion[unit[0]])
      except: pass
    return value

# publish argument examples: cached info, measurements record, record artifacts.
# info = {                           # cached meta info per measurement kit
#     'count': 1,
#     'id': {'project': u'SAN', 'serial': u'b4e62df4b311'},
#     'last_seen': 1627828712,       # Posix timestamp in seconds
#     'interval': 240,               # guessed interval
#     'DATAid': u'SAN_b4e62df4b311', # DB measurements table name
#     'MQTTid': u'201802215971az/bwlvc-b311', # MQTT inpuit channel topic
#     'active': 1,                   # kit active, in operation
#     'valid': 1,   # null or false: 'mobile' e.g. in repair, not at home address
#     'location': u'u1hjtzwmqd',     # geohash home location, null: undefined
#     'kit_loc': null,               # if string: geohash of current not home location
#     'SensorsID': 1593163787, 'TTNtableID': 1590665967,
#     'Luftdaten': u'b4e62df4b311',  # Sensors.Community ID if null use serial
#     'WEBactive': 1,                # published on website
#     'sensors': [                   # sensors meta info
#       {  'category': u'dust', 'type': u'PMSx003', 'match': u'PMS.003',
#          'producer': u'Plantower',
#          'fields': ((u'pm25', u'ug/m3',[-1.619,1/1.545]), (u'pm10',u'ug/m3',[-3.760,1/1.157]),(u'grain', u'um')),
#       {  'category': u'meteo', 'type': u'BME680', 'match': u'BME680',
#          'producer': u'Bosch',
#          'fields': ((u'temp', u'C'), (u'aqi', u'%')),
#       {  'category': u'location', 'type': u'NEO-6', 'match': u'NEO.*',
#          'producer': u'NEO',
#          'fields': ((u'geohash', u'geohash'), (u'altitude', u'm')),
#       ],
#     'FromFILE': True,             # reading from file
#     'CatRefs': ['SDS011'],
#   }
# record = {                        # record data: measurements
#     'timestamp': 1629463231, 'version': '2.0.1',
#     'data': {
#        'BME680':  [(u'temp', 12.8)],
#        'PMS7003': [(u'pm1', 1.8),(u'pm25', 2.5)],   # has unknown field pm25
#     },
#   }
# artifacts = [                     # a selection, subject to change
#     'Forward data',                   'Start throttling kit: %%s',
#     'Skip data. Throttling kit.',     'Unknown kit: %%s',
#     'Unregistered kit: %%s',          'MQTT id:%%s, %%s kit. Skipped.',
#     'Raised event: %%s.',             'Updated home location',
#     'Kit removed from home location', 'New kit',
#     'Restarted kit',                  'Out of Range sensors: %%s',
#     'Static value sensors: %%s',      'Change of sensor types: %%s -> %%s',
#     'Measurement data format error',  'No input resources',
#     'Kit back to home location',      'Kit is set invalid',
#     'Kit removed from home location',
#     'End of iNput Data',              'Fatal error on subscriptions',],
#  ]

# entry point to forward measurements to measurements table in the database
# returns:
#     True: OK stored, False: no data to be stored
#     string: failure reason on output
#     list of strings: ok : string which one of the sub output channels had result
# raised event on failure in eg connection, query error
ErrorCnt = 0
skip = re.compile(r'(Skip data|Unregistered|Raised event|End of).*')
def publish(**args):
    global Conf, ErrorCnt
    """ add records to the database,
        on the first update table Sensors with ident info """
    if (not 'output' in Conf.keys()) or (not Conf['output']):
        return "Measurements archive forwarding disabled"
    try:
      info = args['info']; data = args['data']; artifacts = args['artifacts']
    except: return "Error in publish() arguments"
    if not 'Forward data' in artifacts: return "Not archiving"
    try: timestamp = data['timestamp']
    except: timestamp = None
    if 'data' in data.keys() and type(data['data']) is dict and len(data['data']):
      data = data['data']
    else: return "No data to archive" # no data to archive
    try:
      if not 'DATAid' in info.keys() or not info['DATAid']:
        info['DATAid'] = info['id']['project']+'_'+info['id']['serial']
    except: return "No archive table name"
    # skip records not to forward to Sensors.Community
    if len(artifacts) > 1:
      for one in artifacts:
        if type(Conf['dontSkip']) in [str,unicode]: Conf['dontSkip'] = re.compile(Conf['dontSkip'],re.I)
        if not Conf['dontSkip'].match(one): return "Archiving data is skipped: %s" % one
    
    try:   # ready to put measurements in the measurements table
      sensors, data = registrate(info['DATAid'],info,data) # list of measurements
      # registrate side effect: measurements table is updated with all fields needed
      if not data: return "No data to archive"
    except Exception as e: return str(e)
    try: DfltValid = info['valid']           # meta info about validity of measurements
    except: DfltValid = True
    try:
      if info['kit_loc']: DfltValid = None   # validity undefined (not at home location)
    except: pass

    # table is created and updated with missing fields, insert data into database
    cols = []; vals = []; DB = Conf['DB']
    for one in data:  # one: (field,value,valid[,Taylor calibration seq])
        if one[1] == None: continue
        if DfltValid: validity = one[2]
        else: validity = DfltValid
        # To Do: check one[0] for fields supported in DB archive
        if type(one[1]) in [str, unicode]: vals.append("'%s'" % one[1])
        elif type(one[1]) is bool: vals.append("1" if one[1] else "0")
        elif one[1] == None: vals.append('NULL')
        elif type(one[1]) in [int,float]: # check range of value is done by Datacollector
          dec = DB.getFieldInfo(one[0])[1] # try to find rounding factor.
          if dec == None: vals.append("1" if one[1] else "0")
          else:
            # add check if value is in range ?
            if dec == 0: vals.append(str(int(correctValue(info,one[0],one[1],one[3:]))))
            else: vals.append(str(round(correctValue(info,one[0],one[1],one[3:]),dec)))
        else: # not supported type, e.g. list. Skipped
          continue
        cols.append(one[0])
        # if info['FromFILE']: continue   # do not handle validity if restored from file
        if one[0] != 'geohash':
          cols.append(one[0]+'_valid')
          if validity == None: vals.append('NULL')
          elif validity: vals.append('1')
          else: vals.append('0')
    if not vals: return False
    cols += ['datum','sensors']; vals += ["FROM_UNIXTIME(%d)" % int(timestamp),"'%s'" % ','.join(sensors)]

    # assert len(cols) == len(vals)
    query = "REPLACE INTO %s " % info['DATAid']
    query += "(%s) " % ','.join(cols)
    query += "VALUES (%s)" % ','.join(vals)
    # speedup reasons suggests to first try without on duplicate flag first and try again
    #if info['FromFILE']:  # measurements from file have probably duplicate timestamps
    # use next with INSERT iso REPLACE
    #query += " ON DUPLICATE KEY UPDATE %s" % ','.join(['%s=VALUES(%s)' % (a,a) for a in cols])

    # insert or update new measurement
    if Conf['DEBUG']:
      sys.stderr.write("DEBUG DB: %s\n" % query); return ['DEBUG modus, skip archiving']
    else:
      # for speedup reasons try first without on dublicate check
      #for _ in range(1 if info['FromFILE'] else 2):
      try:
          # To Do: should add multi=True to query
          #if Conf['DB'].db_query(("LOCK TABLE %s WRITE;" % info['DATAid']) +query+ ";UNLOCK TABLES",False):
          if Conf['DB'].db_query(query,False):
            ErrorCnt = 0  #; break
          else: ErrorCnt += 1
      except IOError as e:
          raise IOError(e)
      except:
          #if not _: # try again with handling a duplicate on datum timestamp
          #  query += " ON DUPLICATE KEY UPDATE %s" % ','.join(['%s=VALUES(%s)' % (a,a) for a in cols])
          #  continue
          Conf['log'](WHERE(True),'ERROR',"Error in query: %s" % query)
          ErrorCnt += 1
    if ErrorCnt > 10: raise ValueError("ERROR %d: DB archiving problems" % ErrorCnt)
    elif ErrorCnt: return "WARNING archiving into DB tables"
    return True

# test main loop
if __name__ == '__main__':
    Conf['output'] = True
    Conf['DEBUG'] = True
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
                print("Record ID %s, result: %s" % (str(one['info']['id']),'OK' if result else 'OK nothing to send'))
              else:  # result message
                print("Record ID %s, result: ERROR %s" % (str(one['info']['id']),str(result)))
            except:
              print("Record ID NOT DEFINED, result: %s" % (str(result)))
        except Exception as e:
            print("output channel error event was raised as %s" % e)
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

