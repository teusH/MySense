#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
# 
# Copyright (C) 2017,2021, Behoud de Parel, Teus Hagen, the Netherlands
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
#

# $Id: MyDB2Drupal.py,v 1.5 2021/05/01 10:31:45 teus Exp teus $

# TO DO: write to file or cache
# reminder: MySQL is able to sync tables with other MySQL servers
# database qry proviodes unicode, currently ad hoc unicode is converted to ascii string

# Update CMS DB (Drupal) with meta info from database tables Sensors and TTNtable
# Database credentials can be defined via Conf dict but are overwritten by environment vars
# CMS DB credentials: WEBUSER, WEBHOST (localhost), WEBPASS and WEBDB
# data database credentials: DBUSER, DBHOST (localhost), DBPASS (acacadabra), and DB (luchtmetingen)

__modulename__ = '$RCSfile: MyDB2Drupal.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.5 $"[11:-2]
__license__ = 'Open Source RPL 1.5'

try:
    import sys
    import os
    import re
except ImportError as e:
    sys.exit("FATAL: One of the import modules not found: %s"% e)

# term colors: blue:34, red:31, green: 32
def colored(string,color):
    if not sys.stderr.isatty(): return str(string)
    colors = {'red': 31, 'gre': 32, 'blu': 34, 'cya': 36, 'mag': 35}
    try: return "\033[%dm%s\033[0m" % (colors[color[:3].lower()],str(string))
    except: return str(string)

# table/column translation table between CMS Web DB abd air quality DB Sensors/TTNtable
provincies = [None,'Groningen','Friesland','Drente','Gelderland','Overijssel','Flevoland','Noord-Holland','Zuid-Holland','Zeeland','Brabant','Limburg']
# configuration mapping field/column names to webDB tables access and defined tables in DB
# need to be checked for existance once
# some keys may depend on others and shoulkd be handled especially
# eg CMS street: OneStreet 25 to DB street: Onestreet housenr: 25
Info2CMS = {
    # next project and serial are special: used as indicator/link
    "project":     ["project_id","tid",'Sensors'],   # taxonomy_term_data(tid,name)
    "serial":      ["serial_kit","value",'Sensors'], # delta 0 kit serial number hex

    "label":       ["label","value","Sensors"],      # delta 0 handy lable XYZ_a1f9
    "first":       ["datum","value","Sensors"],       # delta 0 date of installation
    "active":      ["operationeel","value","Sensors"],# delta 0 also in TTNtable

    "gps":         ["gps","value",'CMS'],             # delta 0 GPS sensor type
    "meteo":       ["meteo","value",'CMS'],           # delta 0 meteo sensor type
    "dust":        ["fijnstof","value",'CMS'],        # delta 0 dust sensor type
    # see HQtypes:
    # "net":         ["net","value",'CMS'],           # delta 0 data communication type wlan, ttn
    # "power":       ["power","value",'CMS'],         # delta 0 energie source type in volts
    # "time":        ["time","value",'CMS'],          # delta 0 energie source type in volts
    # previous rely in description, hence no Web DB table, column True indicator
    "description": [None,True,"Sensors"],             # combination dust, meteo, gps
    "comment":     ["commentaar","value","Sensors"],  # delta 0 kit comments
    "notice":      ["notices","value","Sensors"],     # event addresses

    # "GPS":         ["kaart_meetkit","ordinates",None],       # delta 0 dict deprecated
    # "coordinates": ["kaart_meetkit","ordinates","Sensors"],  # lat,long,alt deprecated
    # "longitude":   ["kaart_meetkit","ordinate","Sensors"],   # lon deprecated
    # "latitude":    ["kaart_meetkit","ordinate","Sensors"],   # lat deprecated
    "altitude":    [None,None,"Sensors"],                      # delta 0 alt to be added
    "geohash":     ["kaart_meetkit","ordinate","Sensors"],     # delta 0 geohash
    # "kaart":       ["kaart_meetkit","value",None],    # delta 0 

    # "adres":       ["fysiek_adres","address",None],          # delta 0
    # "name":        ["fysiek_adres","name_line",None],        # delta 0
    # "organisation":["fysiek_adres","organisation_name",None],# delta 0
    "street":      ["fysiek_adres","thoroughfare","Sensors"],  # delta 0
    "housenr":     [None,True,"Sensors"],                      # depends on street
    "pcode":       ["fysiek_adres","postal_code","Sensors"],   # delta 0
    "village":     ["fysiek_adres","locality","Sensors"],      # delta 0
    "municipality":["admin_gemeente","value","Sensors"],       # delta 0
    "province":    ["admin_provincie","value","Sensors",provincies],# delta 0, indexed
    "region":      ["regio","tid","Sensors"],         # taxonomy_term_data(tid, name)
    # "country":     ["fysiek_adres","country",None], # delta 0 NL

    "TTN_id":      ["ttn_topic","value","TTNtable"], # delta 0 TTN device topic name
    # "valid":       [None,None,"TTNtable"], #  valid measurement, if None in repair
    "luftdaten":   ["luftdaten_actief","value","TTNtable"],# delta 0 post to Luftdaten map
    "luftdatenID": ["luftdaten_id","value","TTNtable"],# delta 0 non default luftdaten ID
    # luftdate.info bool or hex strg is converted to luftdaten en luftdatenID deprecated

    "AppEui":      [None,None,"TTNtable"],   # TTN application ID to be added Web DB
    "DevEui":      [None,None,"TTNtable"],   # TTN device ID to be added Web DB
    "AppSKEY":     [None,None,"TTNtable"],   # TTN secret key to be added Web DB
    "DevAdd":      [None,None,"TTNtable"],   # TTN ABP device key to be added Web DB
    "NwkSKEY":     [None,None,"TTNtable"],   # TTN ABP secret key to be added Web DB

    # "AQI":         ["lucht_kwaliteits_index","value",None],    # delta 0 .. 3 aqi index values
    # "AQIdatum":    ["aqi_datum","value",None],                 # delta 0 date aqi index update
    # "AQIcolor":    ["marker_color","value",None],              # delta 0 aqi index color
}
# check and adjust Info2CMS dict configuration
MetaDBtables = {} # None indicated Info2CMS not yet checked for defined DB columns
def CheckInfo2CMS(MyDB=None, tables=['Sensors','TTNtable']):
    global Info2CMS, MetaDBtables
    if not MyDB: raise IOError("No database access point defined")
    if MetaDBtables: return True
    for item, value in Info2CMS.items():
        if not value[1] or not value[2] in tables: continue
        Info2CMS[item][2] = None
    for tbl in tables: # collect available tbl DB column names (fields)
        MetaDBtables[tbl] = []
        qry = MyDB.db_query("DESCRIBE %s" % tbl, True)
        for item in qry:
          try:
            if not Info2CMS[item[0]][1]: continue  # WebDB column not related to DB column
            if not Info2CMS[item[0]][2]:
              Info2CMS[item[0]][2] = tbl
              MetaDBtables[tbl].append(item[0])
          except: pass
    for item, value in Info2CMS.items():
        if not value[2]: del Info2CMS[item]
    return True

# reminder: info dict keys uised as internal exchange format
#Info = {
#        "project",       # project name (str) used as identification
#        "serial",        # serial nr hex kit (str) used as identification
#        "datum",         # from Sensors table: Posix time used in last updated check

#        "label",         # label (str)
#        # "name", "phone"# (str) contact details not supported
#        "street","housenr","pcode",# (str)
#        "municipality", "village", "province", # (str), (str), (str)
#        "GPS", # { "altitude":float,"latitude":float,"longitude":float}, # converted
#        "coordinates",   # deprecated [float lat,float lon,float alt], # converted
#        "longitude","latitude",    # deprecated converted
#        "geohash",       # (str) has long and lat precision max 12
#        "altitude",      # (float)
#        "first",         # first date (str) is parsed
#        "comment",       # any commenteg location detail (str)
#        "net", "pwr",    # eg TTN, WLAN, 12V converted to description
#        "meteo", "dust", "gps",  #  eg BME680, PMSx003, NEO-6  (str) converted to:
#        "power","net","time", # see HWtypes
#        "description",   # (str) eg "abcd...;hw: BME680,PMSx003,NEO-6;abcd",
#        "notice",        # (str) eg "email:metoo@host.org,slack:http://host/notices/12345",
#        "active",        # (bool) operational/installed

#        "TTN_id",        # TTN topic (str)
#        "AppEui",        # TTN application ID "70B3D75E0D0A04D3" void
#        "DevEui",        # TTN device ID "AAAA10D739A3D689" void
#        "AppSKEY",       # TTN secret key "3E210C866D12AFF288F3A1C857DB5292" void
#        "DevAdd",        # TTN ABP device key void
#        "NwkSKEY",       # TTN ABP secret key void
#        "valid",         # (bool) archive in air qual DB, eg True, None: in repair, False not valid
#         deprecated "luftdaten.info",#  (bool or str) may have luftdatenID serial, converted to:
#        "luftdaten",     # (bool) forward to Lufdaten.info, if None no forwd Madavi.de
#        "luftdatenID",   # (str) use as Luftdaten ID iso default TTN-<serial kit>
#   }

HWtypes = { # regular expression for different sensor types
    'dust' : r'(PMS[57x]003|SPS30|SDS011)', # PM type Plantower, Sensirion, Nova
    'meteo': r'(DHT(11|22)|SHT[38][125]|BME[26]80|Si[0-9]{2,4})', # T, RH, hPa, VOC type
    'gps'  : r'(NEO-6|NEO)',                # location sensor type
    # hardware modules types, to be completed
    'power': r'([0-9]{1,3}V)',              # type of energy voltage watchdog
    'net'  : r'(TTN|WiFi|WLAN|LAN)',        # data communication type 
    'time' : r'(GPStime|RTCtime)',          # real time module
}
for key, reg in HWtypes.items(): HWtypes[key] = re.compile(reg, re.I)

# classify HW sensor type into pollutant class and known HW sensor type into dict entry
# returns False if classification fails
def getHWtype(sensor,info={}):
    global HWtypes
    value = None
    sensor = sensor.strip()
    if sensor == 'TIME': sensor = 'GPStime'
    elif sensor == 'NEO': sensor = 'NEO-6'
    for key, reg in HWtypes.items():
      if reg.match(sensor.strip()):
          value = key; break
    if not value:
      sys.stderr.write("ATTENT unknown sensor type %s found!\n" % colored(item,'red'))
      value = 'unknown'
    if not value in info.keys(): info[value] = []
    elif type(info[value]) is str: info[value] = info[value].split(',')
    elif type(info[value]) is unicode: info[value] = str(info[value]).split(',')
    try: info[value].index(sensor)
    except: info[value].append(sensor)
    info[value] = ','.join(sorted(info[value]))
    if value == 'unknown': return False
    return value

# from description string separate HW sensors types from deescriptive string
# returns tuple (descriptive string, MW sensors types dict)
def extractDesc(description,sep=';'):
    global HWtypes
    description = str(description).split(sep)
    info = {}
    if not description: return ('',info)
    for i in range(len(description)-1,-1,-1):
      if not description[i]: description.pop(i)
      elif description[i].strip()[:3] == 'hw:':
        for x in description[i].strip()[3:].split(','):
          getHWtype(x,info)
        description.pop(i)
    if not 'gps' in info.keys() and 'time' in info.keys():
      getHWtype('NEO-6',info)
    if not 'time' in info.keys() and 'gps' in info.keys():
      getHWtype('GPStime',info)
    return (sep.join(description),info)
        
# reformat description string with on end HW sensors comma separated
def correctDesc(value): # correct description values
    desc, hw = extractDesc(value)
    return desc + ';hw: ' + ','.join(sorted(hw.values()))

# cleanup description string and convert sensor types into fields (meteo,...)
# site effect: info['description'] if exists ;hw: ... is deleted from string
# may add to info dict dust, meteo, ... fields
def desc2SensInfo(info,description=None):
    try:
      if not description: description = info['description']
      del info['description']
    except: return False
    description, hw = extractDesc(description)
    if description: info['description'] = description
    if hw: info.update(hw)
    return True

def getCMS(item):
  global Info2CMS
  try: return Info2CMS[item][2]  # return DB table name
  except: return None

# translate month from dutch to english and similar format
# return if not format defined the Posix time base secs
def DateTranslate(datum, format=None):
    from dateutil.parser import parse
    import datetime
    from time import mktime
    tbl = [('januari','Jan'),('februari','Feb'),('maart','Mar'),('april','April'),('mei','May'),
        ('juni','Jun'),('juli','Jul'),('augustus','Aug'),('september','Sep'),('october','Oct'),
        ('oktober','Oct'),('november','Nov'),('december','Dec')]
    rslt = datum
    if rslt == None: rslt = 0
    elif not type(rslt) is int and rslt.isdigit():
        rslt = int(rslt)
    if not type(rslt) is int:
      t = datum.strip().split(' '); rslt = datum
      for one in t:
        if not one or not one.isalpha(): continue
        this = one
        one = str(one.strip()[:3].lower())
        for m,mt in tbl:
          if one[:3].lower() != m[:3]: continue
          rslt = datum.replace(this,mt)
          break
      try: rslt = int(mktime(parse(rslt, dayfirst=True, yearfirst=False).timetuple()))
      except Exception as e:
        sys.stderr.write(colored("ERROR",'red')+" Unable to parse time: %s, error %s." % (rslt,str(e)))
        if format: return datum
        rslt = 0
    try:
      if format: return datetime.datetime.fromtimestamp(rslt).strftime(format)
      return rslt
    except: return datum
        
# adjust 'description' item with types of sensors
# add hw from description if info does not have that field
# site effect cleanup info description
def senseInfo2Desc(info):
    global HWtypes
    old = {}; description = ''; WHinfo = {}
    try: # collect description sensors types into new
      description, HWinfo = extractDesc(info['description'])
      del info['description']
    except: pass
    for hw in HWtypes.keys():
      try:
        if info[hw]: HWinfo[hw] = info[hw]
      except: pass
    if HWinfo.values(): description += ';hw: ' + ','.join(sorted(HWinfo.values()))
    if description: info['description'] = description

# standardize and check coordinates (deprecated) field in info
# convert: change the fields coordinates, geohash, longitude, latitude, altititude
#          to internal field/values: geohash, and altitude fields
# to avoid overloading location details
def ordinates2Geohash(info):
    global Info2CMS
    import MyGPS
    try:
      longitude = round(float(info['longitude']),7)
      del info['longitude']
    except: longitude = 0
    try:
      latitude = round(float(info['latitude']),7)
      del info['latitude']
    except: latitude = 0
    try:
      altitude = round(float(info['altitude']),1)
      del info['altitude']
    except: altitude = 0
    try:
      geohash = info['geohash']
      del info['geohash']
    except: geohash = ''
    if 'coordinates' in info.keys() and info['coordinates']: # coordinates is deprecated
      # coordinates: e.g. lat,long[,alt] string lat/long maybe swapped
      if type(info['coordinates']) is str:  # may try to correct order
        ord = info['coordinates'].split(',')
      elif type(info['coordinates']) is unicode:
        ord = str(info['coordinates']).split(',')
      else: ord = info['coordinates']
      del info['coordinates']  # not needed any more
      ord = [ float(x) for x in ord ]
      if ord and (not geohash or not altitude): 
        while len(ord) < 3: ord.append(float(0))
        # make sure [lat,lon,alt] order
        ord = [round(max(ord[0],ord[1]),7),round(min(ord[0],ord[1]),7),round(ord[2],1)]
        if not longitude: longitude = ord[1]
        if not latitude: latitude = ord[0]
        if not altitude: altitude = ord[2]
    try:
      if longitude and latitude and not geohash and Info2CMS['geohash'][0] and Info2CMS['geohash'][1]:
        geohash = MyGPS.convert2geohash([latitude,longitude])
    except: pass
    try:
      if geohash and Info2CMS['geohash'][0] and Info2CMS['geohash'][1]:
        info['geohash'] = geohash
    except: pass
    try:
      if longitude and latitude and Info2CMS['coordinates'][0] and Info2CMS['coordinates'][1]:
        info['coordinates'] = "%.7f,%.7f,%.1f" % (latitude,longitude,altitude)
    except: pass
    try:
      if altitude and Info2CMS['altitude'][0]: info['altitude'] = altitude
    except: pass

class SyncWithCMS:
    def __init__(self, WebDB=None, logger=None, verbose=False,debug=False):
      if not logger:
        import MyLogger
        self.log = MyLogger.log
      else: self.log = logger
      if WebDB: self.WebDB=webDB
      else:
        import MyWebDB
        self.WebDB=MyWebDB
        if not MyWebDB.Conf['fd']:
            if not MyWebDB.db_connect(): raise IOError("Unable to connect to CMS web DB")
        self.WebDB.Conf['log'] = self.log

      self.prepend = 'field_data_field_' # for all CMS table names
      self.module = 'SyncWithCMS'
      # to convert value to Nld province name and visa versa. Indexed list.
      # next can be changed on command line
      self.debug = debug
      self.verbose=verbose

    # get human address home location info for a node nid from CMS database into info dict
    # fields are country dependent. community, province are in value tables
    def getWebAddress(self, nid,items,info):
      global Info2CMS
      if not type(items) is list: items = str(items).split(',')
      if not len(items): return True
      qry = []; fields = []
      for item in items:
        if Info2CMS[item][0] != 'fysiek_adres': continue
        fields.append(item)
        qry.append('field_fysiek_adres_'+Info2CMS[item][1])
      if not len(qry): return True
      qry = self.WebDB.db_query("SELECT %s FROM %sfysiek_adres WHERE entity_id = %d LIMIT 1" % (','.join(qry),self.prepend,nid),True)
      if not len(qry) or len(qry[0]) != len(fields):
        raise ValueError("Unable to obtain all address fields (%s) got (%s)" % (str(fields),str(qry[0])))
      for indx in range(len(fields)):
        if qry[0][indx]:
            info[fields[indx]] = qry[0][indx]
            # if fields[indx] == 'street':  # house nr is in here?
            #   m = re.compile(r'(.*)\s+([0-9]+[0-9a-z]*)$').match(qry[0][indx].strip())
            #   if m:
            #     info['street'] = m.group(1); info['housenr'] = m.group(2)
        else: info[fields[indx]] = None
      return True

    # update for one info item (key,value) of a node id (nid) in the CMS website DB tables
    # Not used: bundle check, deleted bool, revision_id, language, delta = 0, geom = longblob (???)
    def setWebValue(self, nid,item,value):
      global Info2CMS
      from MyGPS import convert2geohash, fromGeohash # geohash de/encoder for CMS map
      import datetime
      try:
        if not Info2CMS[item][1] or not Info2CMS[item][0]: return False
      except: return False
      if type(value) is bool: value = "1" if value else "0"
      elif item in ['first']: value = "'%s'" % datetime.datetime.fromtimestamp(value).strftime("%Y-%m-%d")
      else: value = "'%s'" % str(value)
      updates = [] # compile update Web DB CMS query
      try:
        if item in ['longitude','latitude']: return False
        if item in ['coordinates','geohash']:      ### ordinate type
          if item == 'coordinates':                      ### kaart_meetkit type
            if type(value) is list: ord = value
            elif type(value) is str: ord = value[1:-1].split(',')
            elif type(value) is unicode: ord = str(value[1:-1]).split(',')
            else: return False
            lat = max(ord[0],ord[1]); lon = min(ord[0],ord[1])
          if item == 'geohash':
            lat, lon = fromGeohash(value.replace("'",''))
          flds = [
            # in Nld lat is > lon, watch out for script and admin errors
            # entity_type = map point
            Info2CMS[item][0]+'_lat = %3.7f' % lat,
            Info2CMS[item][0]+'_top = %3.7f' % lat,
            Info2CMS[item][0]+'_bottum = %3.7f' % lat,
            Info2CMS[item][0]+'_lon = %3.7f' % lon,
            Info2CMS[item][0]+'_left = %3.7f' % lon,
            Info2CMS[item][0]+'_right = %3.7f' % lon,
            Info2CMS[item][0]+"_geohash = '%s'" % str(convert2geohash([lon,lat],precision=12)),
          ]
          updates.append("UPDATE %s SET %s WHERE entity_id = %d" % (self.prepend+Info2CMS[item][0],','.join(flds),nid))

        elif Info2CMS[item][1] == 'value':          ### value type
          updates.append("UPDATE %s SET %s = %s WHERE entity_id = %d" % (self.prepend+Info2CMS[item][0],'field_'+Info2CMS[item][0]+'_value',value,nid))

        elif Info2CMS[item][1] == 'tid':            ### tid type
          qry = self.WebDB.db_query("SELECT tid FROM taxonomy_term_data WHERE name = %s" % value, True)
          if not len(qry) or not len(qry[0]): # unknown term, insert new one
              self.log(self.module,'WARNING','Add to Web CMS DB taxonomy term %s' % value)
              if self.verbose:
                sys.stderr.write('Add to Web CMS DB taxonomy term %s\n' % colored(value,'cyan'))
              qry = "INSERT INTO %s (vid,name,description,weight,format) VALUES (8,%s,'project ID',1)" % value
              if self.debug:
                sys.stderr.write("WebDB change to tid 1001:\n  %s\n" % colored(qry,'cyan'))
                qry =[(1001,)]
              else:
                self.WebDB.db_query(qry, False)
                qry = self.WebDB.db_query("SELECT tid FROM taxonomy_term_data WHERE name = %s" % value, True)
                if not len(qry) or not len(qry[0]):
                  self.log(self.module,'ERROR','Failed to insert new taxonomy term %s' % value)
                  return False
          updates.append("UPDATE %s SET %s = %d WHERE entity_id = %d" % (self.prepend+Info2CMS[item][0],'field_'+Info2CMS[item][0]+'_tid', qry[0][0], nid))

        elif Info2CMS[item][0] == 'fysiek_adres': ### addres type
          if Info2CMS[item][1] in ['thoroughfare','locality']:
            # locality == village, thoroughfare == street, pick up either of 2
            qry = self.WebDB.db_query("SELECT field_fysiek_adres_%s FROM %s WHERE entity_id = %d" % (('locality' if Info2CMS[item][1] == 'thoroughfare' else 'thoroughfare'),self.prepend+Info2CMS[item][0],nid),True)
            if len(qry) and len(qry[0][0]): # location changed
              if item == 'street':
                m = re.compile(r'^(.*)\s+[0-9]\w*$').match(value[1:-1])
                street = m.group(1).strip(); village = str(qry[0][0])
                updates.append("UPDATE %s SET field_fysiek_adres_thoroughfare = %s WHERE entity_id = %d" % (self.prepend+Info2CMS[item][0],value,nid))
              else: # village part
                street = str(qry[0][0]); village = value[1:-1]
                updates.append("UPDATE %s SET field_fysiek_adres_thoroughfare = %s WHERE entity_id = %d" % (self.prepend+Info2CMS[item][0],value,nid))
              # update title with village, street info
              updates.append("UPDATE node SET title = '%s: %s' WHERE nid = %d" % (village,street,nid))
          else:
              updates.append("UPDATE %s SET field_fysiek_adres_%s = %s WHERE entity_id = %d" % (self.prepend+Info2CMS[item][0], Info2CMS[item][1], value, nid))
        else:
          raise ValueError("ERROR Web item %s: unknown update field %s\n" % (item,Info2CMS[item][0]))

        if not updates: return False
        updates = str(';'.join(updates))
        if self.debug:
          sys.stderr.write("DEBUG: try update Web CMS DB with:\n  %s\n" % colored(updates,'cyan'))
        else:
          if self.verbose:
            sys.stderr.write("WebDB changed with:\n  %s\n" % updates)
          try: self.WebDB.db_query(updates, False)
          except:
            sys.stderr.write("FAILURE WebDB updating with:\n  %s\n" % updates)
            return False
      except:
        self.log(self.module,'DEBUG','Failed to update CMS web DB with %s: query %s' % (item,str(updates)))
        self.log(self.module,'ERROR','Failed to update CMS web DB with %s: value %s' % (item,value))
        return False
      return True

    # get tid values from taxonomy Drpual website table to dict
    def getTIDvalues(self, nid,items,info):
      global Info2CMS
      if not type(items) is list: items = str(items).split(',')
      if not len(items): return True
      for item in items:
        if Info2CMS[item][1] != 'tid': continue
        qry = self.WebDB.db_query('SELECT taxonomy_term_data.name FROM taxonomy_term_data, %s%s WHERE  %s%s.entity_id = %d AND taxonomy_term_data.tid = %s%s.field_%s_tid' % (self.prepend,Info2CMS[item][0],self.prepend,Info2CMS[item][0],nid,self.prepend,Info2CMS[item][0],Info2CMS[item][0]), True)
        if not len(qry) or not qry[0]:
            raise ValueError('Taxonomy lookup problem for %s' % item)
        if qry[0][0]: info[item] = qry[0][0]
        else: info[item] = None
      return True

    # get values and tids for a node nid from CMS database into info dict
    def getFromWebDB(self, nid, info, items=[]):
      global Info2CMS, MetaDBtables
      selects = []; address = []; fields = []; tids = []
      if not items:
        # internally used table columns from air quality database tables
        for item in Info2CMS.keys():
          if not MetaDBtables: raise ValueError("Database table columns not initialized.")
          if Info2CMS[item][2] in MetaDBtables.keys() + ['CMS']:
            items.append(item)
      if not type(items) is list: items = str(items).split(',')
      for item in items: # compile select column for Web DB qry
        if not item in Info2CMS.keys() or not Info2CMS[item][0]:
          continue
        if Info2CMS[item][0] == 'fysiek_adres':
          address.append(item); continue
        if Info2CMS[item][1] == 'tid':
          tids.append(item); continue
        # handle field_*_value type of info
        fields.append(item)
        if Info2CMS[item][1] == 'value':
          selects.append('(SELECT field_'+Info2CMS[item][0]+'_value FROM '+self.prepend+Info2CMS[item][0]+" WHERE entity_id = %s) AS '%s'" % (nid,item))
        elif Info2CMS[item][1] == 'ordinates' and item == 'coordinates':  # deprecated
          selects.append('(SELECT CONCAT(field_'+Info2CMS[item][0]+'_lon,",",field_'+Info2CMS[item][0]+'_lat,",",0) FROM '+self.prepend+Info2CMS[item][0]+' WHERE entity_id = %s) AS "%s"' % (nid,item))
        elif Info2CMS[item][1] == 'ordinates' and item == 'geohash':
          selects.append('(SELECT field_'+Info2CMS[item][0]+'_%s' % (item if item == 'geohash' else item.lower()[:3]) + ' FROM '+self.prepend+Info2CMS[item][0]+' WHERE entity_id = %s) AS "%s"' % (nid,item))
          for ord in ['longitude','latitude']:
            fields.append(ord)
            selects.append('(SELECT field_'+Info2CMS[item][0]+'_%s' % one[:3] + ' FROM '+self.prepend+Info2CMS[item][0]+' WHERE entity_id = %s) AS "%s"' % (nid,one))
        elif Info2CMS[item][1] == 'ordinate':
          selects.append('(SELECT field_'+Info2CMS[item][0]+'_%s' % (item if item == 'geohash' else item.lower()[:3]) + ' FROM '+self.prepend+Info2CMS[item][0]+' WHERE entity_id = %s) AS "%s"' % (nid,item))
      # try to get them in one show if not one by one
      qry = 'SELECT ' + ','.join(selects)
      qry = self.WebDB.db_query(qry, True)
      if not len(qry): # try one by one
        self.log(self.module,'DEBUG','Failed to get info %s from Web database' % str(items))
        qry = [[]]
        for indx in range(len(fields)):
          qry[0].append(None)
          nqry = self.WebDB.db_query('SELECT %s FROM %s WHERE %s' % (selects[indx],froms[indx],wheres[indx]),True)
          if len(nqry) and len(nqry[0]): qry[0][indx] = nqry[0][0]

      for indx in range(len(fields)): # get qry values into a internal used dict
        try:
          if qry[0][indx] is None: continue
          elif len(Info2CMS[fields[indx]]) > 3: # indexed value
            try:
              info[fields[indx]] = Info2CMS[fields[indx]][3][int(qry[0][indx])]
            except:
              self.log(self.module,'ERROR','Unexpected index %s for field %s.' % (qry[0][indx],fields[indx]))
              info[fields[indx]] = qry[0][indx]
          elif type(qry[0][indx]) is int:
            if qry[0][indx] <= 1: info[fields[indx]] = (True if qry[0][indx] else False)
            else: info[fields[indx]] = qry[0][indx]
          elif not type(qry[0][indx]) is unicode: # decimal.Decimal DB class
            info[fields[indx]] = float(qry[0][indx])
          else: info[fields[indx]] = qry[0][indx]
        except:
          self.log(self.module,'ERROR','Failed to import info %s from Web database' % fields[indx])
          return False

      # adjust dict to what is used internaly as values to synchronize
      if 'GPS' in info.keys():
        if not 'coordinates' in info.keys(): info['coordinates'] = info['GPS']
        ord = [float(x) for x in str(info['GPS']).split(',')]
        info['GPS'] =  { 'longitude': ord[LON], 'latitude': ord[LAT], 'altitude': None }
      for item in ['first','datum']:
        if item in info.keys() and (not type(info[item]) is int):
          info[item] = DateTranslate(info[item])
      ordinates2Geohash(info)  # convert ordinates fields to internal use
      desc2SensInfo(info)      # convert description field to internal dict
      if len(tids) and not self.getTIDvalues(nid,tids,info): return False
      if len(address) and not self.getWebAddress(nid,address,info): return False
      for key,value in info.items(): # convert unknown value to None
        if value == 'None' or value == 'NULL': info[key] = None

      return True

    # get node id's, changed, project, serial from CMS with node type 'meetkit_lokatie'
    # matching reg exp's list KitSelect
    def getMeetKits(self,KitSelect):
      qry = self.WebDB.db_query("""
            SELECT
                node.nid, node.changed, taxonomy_term_data.name,
                # field_data_field_project_id.field_project_id_tid,
                field_data_field_serial_kit.field_serial_kit_value
            FROM node, field_data_field_project_id, field_data_field_serial_kit,
                 taxonomy_term_data
            WHERE node.type = 'meetkit_lokatie' AND node.status = 1 AND
                field_data_field_serial_kit.entity_id = node.nid AND
                field_data_field_project_id.entity_id = node.nid AND
                taxonomy_term_data.tid = field_data_field_project_id.field_project_id_tid
            ORDER BY node.changed DESC""", True)
      ids = ['nid','changed','project','serial']
      rts = []
      for row in range(len(qry)):
        fnd = False
        for i in range(len(KitSelect)):
            if KitSelect[i].match(str(qry[row][2]+'_'+qry[row][3])):
                fnd = True; break
        if not fnd: continue
        item = {}
        for i in range(len(ids)): item[ids[i]] = qry[row][i]
        rts.append(item)
      return rts

class UpdateDBandWebDB:
    def __init__(self, verbose=False, interact=False, debug=False, db=None, webdb=None, logger=None):
        self.debug = debug; self.verbose = verbose; self.interact = interact
        if not logger:
            import MyLogger
            self.log = MyLogger.log
        else: self.log = logger
        if not db:
          import MyDB
          self.MyDB = MyDB
          self.MyDB.Conf['log'] = self.log
          # self.MyDB.Conf['debug'] = debug
        else: self.MyDB = db
        if not 'fd' in self.MyDB.Conf.keys() or not self.MyDB.Conf['fd']:
          if not self.MyDB.db_connect():
            raise IOError("Unable to connect to MySQL measurements database")
        if not webdb:
          import MyWebDB
          self.MyWebDB = MyWebDB
          self.MyWebDB.Conf['log'] = self.log
          # self.MyWebDB.Conf['debug'] = debug
        else: self.MyWebDB = webdb
        if not 'fd' in self.MyWebDB.Conf.keys() or not self.MyWebDB.Conf['fd']:
          if not self.MyWebDB.db_connect():
            raise IOError("Unable to connect to MySQL CMS database")
        if verbose:
          sys.stderr.write(coloring("Synchronizing DB on %s@%s and Web DB on %s@%s" % (self.MyDB.Conf['user'],self.MyDB.Conf['hostname'],self.MyWebDB.Conf['user'],self.MyWebDB.Conf['hostname']),'cyan'))
        CheckInfo2CMS(MyDB=self.MyDB) # initialize DB tables columns definitions
        self.module = 'UpdateDBandWebDB'
        self.SyncWithCMS = SyncWithCMS(WebDB=webdb, logger=self.log, verbose=verbose,debug=debug)
          
    # get values and tids for a node nid from CMS database into info dict
    def getInfoFromDB(self, project, serial, info):
        global Info2CMS, MetaDBtables
        CheckInfo2CMS(MyDB=self.MyDB) # make sure column names are defined in DB tables
        upgrades = {}   # table may need to be upgraded
        for tbl in MetaDBtables.keys(): # collect available tbl DB column names (fields)
          fields = ['id']; selects = ['UNIX_TIMESTAMP(id)']
          for fld in MetaDBtables[tbl]:
              fields.append(fld)
              if fld in ['first','datum','last_check','id']: # date format use POSIX timestamp
                 selects.append('UNIX_TIMESTAMP('+fld+')')
              elif fld == 'geohash':
                 selects.append(fld)
                 fields.append('longitude'); selects.append('ST_LongFromGeoHash(geohash)')
                 fields.append('latitude'); selects.append('ST_LatFromGeoHash(geohash)')
              else: selects.append(fld)
          qry = "SELECT %s FROM %s WHERE project = '%s' and serial = '%s' ORDER BY %sdatum DESC LIMIT 1" % (','.join(selects),tbl,project,serial,('active DESC, ' if 'active' in MetaDBtables[tbl] else ''))
          qry = self.MyDB.db_query(qry, True)
          if not len(qry) or not len(qry[0]) == len(fields):
              raise ValueError('Unknown fields in %s table: %s.' % (tbl,str(selects[tbl])))
          for key,val in zip(fields,qry[0]):
            try:
              if key == 'id':  # must be first in list
                upgrades[tbl] = (val,[])
                continue
              if type(val) is int:
                if 0 <= val <= 1:
                  info[key] = (True if val else False)
                else:
                  info[key] = val
              elif str(val).isdigit():
                info[key] = int(str(val))
              elif str(val) == 'None' or val is None:
                continue # info[key] = None
              elif not type(val) is unicode:
                info[key] = float(val)
              else:
                info[key] = str(val)
              if key == 'description': # if differ one may update dada DB for this value
                info[key] = correctDesc(val)
                if str(info[key]) != str(val): # old format changed to new format
                   upgrades[tbl][1].append("%s = '%s'" % (key,info[key]))
            except Exception as e:
                sys.stderr.write("ERROR: %s:\n\tUncatched value conversion on key %s with value %s\n" %(str(e),key,str(val)))
        # convert and check old style to new style and try to upgrade the data DB
        for tbl,qry in upgrades.items(): # upgrade Sensors from old style
          if not qry[1]: continue
          qry = "UPDATE %s SET datum = datum, %s WHERE id = FROM_UNIXTIME(%s)" % (tbl,','.join(qry[1]),qry[0])
          if self.debug: sys.stderr.write("Data DB qry: %s\n" % colored(qry,'cyan'))
          else:
            try: self.MyDB.db_query(qry, False)
            except: pass
        # convert to internal info format for location info
        try:
          info['street'] += ' ' + str(info['housenr'])
          del info['housenr']
        except: pass
        ordinates2Geohash(info)
        # convert to internal info format for hw sensors info
        desc2SensInfo(info)
        return True
    
    # interactively change field values in either db
    def InteractDBvalues(self, fld,DrValue,AqValue,ChangeAQDB):
        if not ChangeAQDB:
          ChangeValueTo = AqValue
          PrevValue = DrValue
          sys.stderr.write("web CMS DB  %s: changing value %s to %s from data DB\n" % (colored(fld,'blue'),colored(DrValue,'green' if ChangeAQDB else 'red'),colored(AqValue,'red' if ChangeAQDB else 'green')))
        else:
          ChangeValueTo = DrValue
          PrevValue = AqValue
          sys.stderr.write("Data DB     %s: changing value %s (data DB) to %s from Web DB\n" % (colored(fld,'blue'),colored(AqValue,'red' if ChangeAQDB else 'green'),colored(DrValue,'green' if ChangeAQDB else 'red')))
        while True:
          try: line = raw_input("    change value %s to %s (Y/n) or enter new value: " % (colored(PrevValue,'red'),colored(ChangeValueTo,'green')))
          except: line =  input("    change value %s to %s (Y/n) or enter new value: " % (colored(PrevValue,'red'),colored(ChangeValueTo,'green')))
          line = line.strip()
          if not line or (line.lower()[0] == 'y'): break
          elif len(line) < 3 and line.lower()[0] == 'n':
            return None
          else:
            # PrevValue = ChangeValueTo
            ChangeValueTo = line
          if not ChangeValueTo: ChangeValueTo = None
          elif ChangeValueTo.lower() == 'true': ChangeValueTo = True
          elif ChangeValueTo.lower() == 'false': ChangeValueTo = False
          elif ChangeValueTo.isdigit(): ChangeValueTo = int(ChangeValueTo)
          elif ChangeValueTo.replace('.','',1).isdigit(): ChangeValueTo =float(ChangeValueTo)
          elif ChangeValueTo.lower() == 'none': ChangeValueTo = None
          # else it is a string
        if not self.verbose: # one message is enough
          sys.stderr.write(" %s %s: changing %s to %s\n" % (('Data DB' if ChangeAQDB else 'Web DB'),colored(fld,'blue'),colored(AqValue if ChangeAQDB else DrValue,'red'),colored(ChangeValueTo,'blue')))
        return ChangeValueTo
    
    def GPSdistance(self, gps1,gps2): # returns None on a not valid GPS oordinate
        from math import sin, cos, radians, pow, sqrt, atan2
        LAT = 0
        LON = 1
        ALT = 2
        def str2list(val):
          if type(val) is list:
              rts = val
          elif val == None or val == 'None': return None
          else:
            try: rts = [float(x) for x in str(val).split(',')]
            except: return None
          if len(rts) < 2: return None
          # if rts[0] < 0.1 or rts[1] < 0.1: return None
          return rts
    
        gps1 = str2list(gps1); gps2 = str2list(gps2)
        # if gps1 == None and gps2 == None: return 0
        if gps1 == None or gps2 == None: return None
        if gps1[:2] == gps2[:2]: return 0
    
        delta = radians(float(str2list(gps1)[LON])-float(str2list(gps2)[LON]))
        sdlon = sin(delta)
        cdlon = cos(delta)
        lat = radians(float(str2list(gps1)[LAT]))
        slat1 = sin(lat); clat1 = cos(lat)
        lat = radians(float(str2list(gps2)[LAT]))
        slat2 = sin(lat); clat2 = cos(lat)
    
        delta = pow((clat1 * slat2) - (slat1 * clat2 * cdlon),2)
        delta += pow(clat2 * sdlon,2)
        delta = sqrt(delta)
        denom = (slat1 * slat2) + (clat1 * clat2 * cdlon)
        return int(round(6372795 * atan2(delta, denom)))
    
    # show differences per field between CMS web DB meetkit info and air quality meta data DB
    def diffInfos(self, CMS,AQDB, ChangeAQDB, WebMeetkit):
        from time import mktime
        import datetime
        from dateutil.parser import parse
        fields = list(set(CMS.keys()+AQDB.keys()))

        def valuesDiffer(fld,val1,val2): # some fields need special differ check
          import MyGPS
          global HWtypes
          # sys.stderr.write("Diff %s (%s,%s)\n" % (fld, str(val1), str(val2)))
          if str(val1).lower() == 'none' or str(val2).lower() == 'none':
              return str(val1).lower() != str(val2).lower()
          if fld == 'coordinates':
            return (MyGPS.GPS2Aproximate(MyGPS.convert2geohash(val1),MyGPS.convert2geohash(val2)) > 118)
          elif fld == 'geohash':
            return (MyGPS.GPS2Aproximate(val1,val2) > 118)
          elif fld == 'longitude' or fld == 'latitude':
            return round(float(val1),6) != round(float(val2),6)
          elif fld == 'altitude': return round(float(val1),0) != round(float(val2),0)
          return str(val1) != str(val2)

        if self.verbose or self.interact:
          hdr = ['%s info (nid %d)' % (colored('web CMS DB','red' if not ChangeAQDB else 'green'), WebMeetkit['nid'])]
          hdr.append('%s info (%s,%s)' % (colored('AQ data DB','red' if ChangeAQDB else 'green'),WebMeetkit['project'],WebMeetkit['serial']))
          if self.verbose:
             hdr.append(datetime.datetime.fromtimestamp(WebMeetkit['changed']).strftime("%Y-%m-%d %H:%M"))
             hdr.append(datetime.datetime.fromtimestamp(WebMeetkit['datum']).strftime("%Y-%m-%d %H:%M"))
          sys.stderr.write("Update (%s) " % colored('in red','red'))
          for i in range(0,2,len(hdr)-1):
             if ChangeAQDB: sys.stderr.write("%s >> %s\n" % (hdr[i],hdr[i+1])) 
             else:  sys.stderr.write("%s >> %s\n" % (hdr[i+1],hdr[i]))

        fields.sort(); DRrslt = {}; AQrslt = {}
        for fld in fields:
            if fld == 'gps':
                sys.stderr.write("gps")
            DrItem = 'None' if not fld in CMS.keys() or CMS[fld] == None else CMS[fld]
            AqItem = 'None' if not fld in AQDB.keys() or AQDB[fld] == None else AQDB[fld]
            if fld in ['first','datum'] and DrItem != 'None':
                DrItem = DateTranslate(DrItem,format='%Y-%m-%d')
            if fld in ['first','datum'] and AqItem != 'None':
                AqItem = DateTranslate(AqItem,format='%Y-%m-%d')
            diff =  valuesDiffer(fld,DrItem,AqItem)
            # term colors: 34: blue, 32: green, 31: red, 33: yellow, 0: reset
            if not diff:
              if self.verbose: sys.stderr.write("  %s: %s (no change)\n" % (colored(fld,'blue'),str(DrItem)))
              continue
            ItemToChange = (AqItem if ChangeAQDB else DrItem)
            if self.interact:
              ItemToChange = self.InteractDBvalues(fld,DrItem,AqItem,ChangeAQDB)
              if ItemToChange == None:
                if self.debug:
                  sys.stderr.write("  %s: %s CMS DB, %s data DB (%s)\n" % (colored(fld,'blue'),str(DrItem),str(AqItem),colored('unchanged','blue')))
                continue
            sys.stderr.write("  %s: %s (changing in %s DB)\n" % (colored(fld,'blue'),colored(ItemToChange,'blue'),'Data' if ChangeAQDB else 'Web'))
            if valuesDiffer(fld,ItemToChange,AqItem):
              AQrslt[fld] = (ItemToChange if ItemToChange != 'None' else None)
              if fld in ['first','datum'] and ItemToChange != 'None':
                AQrslt[fld] = int(mktime(parse(AQrslt[fld], dayfirst=True, yearfirst=False).timetuple()))
            if valuesDiffer(fld,ItemToChange,DrItem):
              DRrslt[fld] = (ItemToChange if ItemToChange != 'None' else None)
              if fld in ['first','datum'] and ItemToChange != 'None':
                DRrslt[fld] = int(mktime(parse(DRrslt[fld], dayfirst=True, yearfirst=False).timetuple()))
        if len(set(HWtypes.keys()).intersection(set(AQrslt.keys()))) > 0:
          for fld in set(HWtypes.keys()).difference(set(AQrslt.keys())):
            if fld in CMS.keys(): AQrslt[fld] = CMS[fld]
        if self.debug or self.interact: sys.stderr.write("DIFF RESULTs:\n")
        if self.debug or self.interact:
            sys.stderr.write("  CMS DB  : %s\n" % str(DRrslt))
        if self.debug or self.interact:
            sys.stderr.write("  Air Qual DB: %s\n" % str(AQrslt))
        return (DRrslt,AQrslt)
    
    # insert new entrys in Sensors/TTNtable for this CMS entry if operational
    def insertNewKit(self, WebKit):
        def setMembers(column,table): # get all different column values from a meta info table
          qry = self.MyDB.db_query("SELECT DISTINCT %s FROM %s" % (column,table), True)
          rslt = []
          if not len(qry) or not len(qry[0]): return rslt
          for item in qry:
            if len(item): rslt.append(item[0])
          return rslt
    
        import datetime
        qry = self.MyDB.db_query("SELECT UNIX_TIMESTAMP(datum) FROM Sensors WHERE project = '%s' AND serial = '%s' ORDER BY active DESC, datum DESC LIMIT 1"% (WebKit['project'],WebKit['serial']), True)
        if len(qry) and len(qry[0]) and qry[0][0]: return qry[0][0]
        operational = self.WebDB.db_query("SELECT field_operationeel_value from field_data_field_operationeel WHERE entity_id = %d" % WebKit['nid'], True)
        if not len(operational) or not len(operational[0]): operational = None
        elif not operational[0][0]: operational = False
        else: operational = True
        if not operational: return 0
        # vid == 8 for project names defined in CMS
        # qry = self.WebDB.db_query("SELECT name FROM taxonomy_term_data WHERE vid = 8", True)
        setSensors = setMembers('project','Sensors')
        setTTNtable = setMembers('project','TTNtable')
        if not WebKit['project'] in set(set(setSensors) & set(setTTNtable)):
            self.log(self.module,'WARNING','Unknown project "%s" for a kit. Insert it manually.' % WebKit['project'])
            if not self.interact: return 0
            try: line = raw_input("Insert new project %s serial %s in Sensors/TTNtable? (Y/n): " % (WebKit['project'],WebKit['serial']))
            except: line = 'no'
            line = line.strip()
            if line and (line.lower()[0] != 'y'): return 0
        try:
            t = WebKit['changed']-12*60*60 # make sure CMS date time overrules AQ date time
            self.log(self.module,'ATTENT','Insert new entry project %s, serial %s in AQ DB tables from CMS node %d dated: %s.' % (WebKit['project'],WebKit['serial'],WebKit['nid'],datetime.datetime.fromtimestamp(WebKit['changed']).strftime("%Y-%m-%d %H:%M")))
            if not self.debug:
              self.MyDB.db_query("INSERT INTO Sensors (datum,project,serial,active) VALUES (FROM_UNISTIMESTAMP(%d),%s,%s,0)" % (t,WebKit['project'],WebKit['serial']),False)
            else:
              sys.stderr.write("DEBUG: "+colored("INSERT INTO Sensors (datum,project,serial,active) VALUES (FROM_UNISTIMESTAMP(%d),%s,%s,0)" % (t,WebKit['project'],WebKit['serial']),'cyan'))
            qry = self.MyDB.db_query("SELECT id FROM TTNtable WHERE project = %s AND serial = '%s'" % (WebKit['project'],WebKit['serial']), True)
            if len(qry) and len(qry[0]): return t
            if not self.debug:
              self.MyDB.db_quEry("INSERT INTO TTNtable (datum,project,serial,active) VALUES (FROM_UNISTIMESTAMP(%d),%s,%s,0)" % (t,WebKit['project'],WebKit['serial']),False)
            else:
              sys.stderr.write("DEBUG: " + colored("INSERT INTO TTNtable (datum,project,serial,active) VALUES (FROM_UNISTIMESTAMP(%d),%s,%s,0)" % (t,WebKit['project'],WebKit['serial']),'cyan'))
            return t
        except: return 0
    
    def UpdateAQDB(info, project=None, serial=None, tables = ['Sensors','TTNtable']):
        def members(table): # get all different column values from a meta info table
          global Info2CMS
          if not project or not serial:
            sys.stderr.write("ERROR: unable to find project/serial ID\n")
            return False
          qry = self.MyDB.db_query("DESCRIBE %s" % table, True)
          rslt = []
          if not len(qry) or not len(qry[0]): return rslt
          flds = []
          for item in qry:
            if item[0] == 'coordinates':  # deprecated still there
              if not 'geohash' in info.keys(): continue
              info['coordinates'] = [ ".7f" % (float(x) for x in list(fromGeohash(info['geohash']) )) ]
              info['coordinates'].append("%.1f" % (info['altitude'] if 'altitude' in info.keys() else 0))
              info['coordinates'] = ','.join(info['coordinates'])
            try:
              if item[0] in ['project','serial']: continue
              if Info2CMS[item[0]] == table and item[0] in info.keys():
                rslt.append(item[0])
            except: pass
          return rslt

        # convert internal fields to DB fields
        try:
          m = re.compile(r'(.*)\s+([0-9]+[0-9a-z]*)$').match(info['street'].strip())
          if m:
            info['street'] = m.group(1).strip(); info['housenr'] = m.group(2).strip()
        except: pass
        for tbl in tables:
          flds = members(tbl)
          if not flds: continue
          try:
            id = self.MyDB.db_query("SELECT id%s FROM %s WHERE project = '%s' AND serial = '%s' ORDER BY %sdatum DESC" % ((', active' if tbl == 'Sensors' else ''), tbl, project, serial, ("'active' DESC, " if tbl == 'Sensors' else '')), True)[0][0]
          except: id = None
          if tbl == 'Sensors':
            if id and 'geohash' in info.keys(): # measurement kit has moved
              qry = "UPDATE Sensors SET active = 0, datum = datum WHERE project = '%s' AND serial = '%s'" % (project,serial)
              try:
                if self.debug: sys.stderr.write("Update data DB: %s\n" % qry)
                else: self.MyDB.db_query(qry, False)
              except: pass
              id = None
          if not id: # new entry
            qry = "INSERT INTO %s (datum,project,serial) VALUES (now(),'%s','%s')" % (tbl,project,serial)
            if self.debug:
              sys.stderr.write("data DB qry: %s\n" % qry)
            else:
              self.MyDB.db_query(qry, False)
              id = self.MyDB.db_query("SELECT id%s FROM %s WHERE project = '%s' AND serial = '%s' ORDER BY datum DESC" % (tbl, project, serial), True)[0][0]
          updates = []
          for fld in flds:
            value = info[fld]
            if type(value) is bool:
              value = (1 if value else 0)
            elif type(value) is list:
              value = "'%s'" % ','.join([str(x).strip() for x in value])
            elif value is None:
              value = "NULL"
            elif type(value) is str or type(value) is unicode:
              value = "'%s'" % str(value).strip()
            elif fld in ['first','datum']:
              value = "FROM_UNIXTIME(%d)" % value
            updates.append("%s = %s" % (fld,str(value)))
          if not updates: continue
          try:
            qry = "UPDATE %s SET datum = datum, %s WHERE id = '%s'" % (tbl,', '.join(updates),str(id))
            if self.debug: sys.stderr.write("data DB query: %s\n" % qry)
            else: self.MyDB.db_query(qry, False)
          except:
            sys.stderr.write("ERROR Updating table with: %s\n" % qry)

    # on arg ToDB is False: update WebDB DB with the DB info. Or otherway around.
    # if interact True, ask it first else do it silently
    # useDB if True use DB info as source for updates
    # info is on interact the header
    def UpdateWebDB(self,WebDBInfo,nid=None):
        updates = []
        try:
          # may need to return also a dict with fields/values which are not change but present
          if len(WebDBInfo) and nid:
            for (item,value) in WebDBInfo.items():
                if not value: continue
                if item == 'housenr': continue
                if item == 'street' and 'housenr' in  WebDBInfo.keys():
                  if not re.compile(r'.*\s[0-9]+[a-z0-9]*$').match(value):
                    value += ' '+WebDBInfo['housenr']
                self.log(self.module,'INFO',"Synchronize web CMS DB node %d: %s: '%s'." % (nid,item,str(value)))
                if self.SyncWithCMS.setWebValue(nid,item,value):
                  updates.append(item)
                elif self.verbose:
                  sys.stderr.write("ATTENT: field %s value %s not updated\n" % (item,str(value)))
          if updates:
            if self.verbose:
              sys.stderr.write("UPDATE Web DB node %d: changed = time now(), fields %s\n" % (nid,', '.join(['changing:']+updates)))
            if not self.debug:
              self.WebDB.db_query("UPDATE node SET changed = UNIX_TIMESTAMP(now()) WHERE nid = %d" % nid, False)
        except Exception as e:
           self.log(self.module,'ERROR',"Failed to synchronize WebDB with DB: %s" % str(e))
        return True
    
    # synchronize all CMS web kits known with meta info from database tables Sensors and TTNtable
    # the routine uses change timestamp as indicater which direction updates are done
    # interact forces interaction about changes to be made (both sides of update)
    # so interaction may cause both DB's to be updated.
    # all: increase verbosity on interaction (show kit ID)
    # update: if None or 'DB' data DB is source to update Web DB
    #          if 'WebDB' Web DB (CMS DB) is source to update data DB
    #          if 'time' (5 minutes) or number of seconds: use last changed DB date diff
    # info: synchronize part of data DB meta info. Default: get all from data DB
    def syncWebDB(self, KitSelect, update=None, info={}):
        import datetime
        if type(KitSelect) is str: WebMeetkits = [KitSelect]
        else: WebMeetkits = KitSelect
        for i in range(len(WebMeetkits)):  # select which kits to synchronize
          if type(WebMeetkits[i]) is str:
            WebMeetkits[i] = re.compile('^'+WebMeetkits[i]+'$', re.I)
        # minimal time in secs difference to do synchronisation in DB's
        if update == None: update = 'WebDB'
        if update.lower() == 'time': update = 5*60
        if type(update) is int or type(update) is float:
            update = (5*60 if update < 5*60 else int(update))
        if type(update) is str or type(update) is unicode:
            if re.compile(r'^\s*DB\s*$', re.I).match(update): update = 'DB'
            elif re.compile(r'^\s*WebDB\s*$', re.I).match(update): update = 'WebDB'
            else: raise ValueError("syncWebDB argument unknown: %s" % update)
        # get a list of dicts from CMS (Web) DB matching serial/project id's
        WebMeetkits = self.SyncWithCMS.getMeetKits(WebMeetkits)
        if not WebMeetkits:
            if self.verbose or self.debug:
              sys.stderr.write("ATTENT: no measurement kit found for selection %s\n" % KitSelect)
            return False

        # try to synchronize Web DB abnd data DB for every measurement kit in Web DB
        for indx in range(len(WebMeetkits)):
            # project, serial as data DB id's,
            # datum data DB timestamp, changed WebDB timestamp for last updated time,
            # NID  as webDB id
            qry = self.MyDB.db_query("SELECT UNIX_TIMESTAMP(datum) FROM Sensors WHERE project = '%s' AND serial = '%s' ORDER BY active DESC, datum DESC LIMIT 1" % (WebMeetkits[indx]['project'],WebMeetkits[indx]['serial']), True)
            if not len(qry):
                self.log(self.module,'ATTENT','Sensor kit from CMS node %d with project %s,serial %s is not defined in Sensors/TTNtable table(s).' % (WebMeetkits[indx]['nid'],WebMeetkits[indx]['project'],WebMeetkits[indx]['serial']))
                if type(update) is int:
                  if self.verbose or self.debug:
                    sys.stderr.write("No data DB relevant info found for project %s, serial %s! Inserting meetkit in data DB.\n" % (WebMeetkits[indx]['project'],WebMeetkits[indx]['serial'])) 
                  WebMeetkits[indx]['datum'] = self.insertNewKit(WebMeetkits[indx])
            else: WebMeetkits[indx]['datum'] = qry[0][0]

            # WebMeetkits list of dict nid, changed, project, serial, Sensors datum keys
            self.log(self.module,'DEBUG','Kit CMS node nid %d dated %s AND data DB kit %s_%s dated %s.' % (WebMeetkits[indx]['nid'],datetime.datetime.fromtimestamp(WebMeetkits[indx]['changed']).strftime("%Y-%m-%d %H:%M"),WebMeetkits[indx]['project'],WebMeetkits[indx]['serial'],datetime.datetime.fromtimestamp(WebMeetkits[indx]['datum']).strftime("%Y-%m-%d %H:%M")))
            #################################### synchronize measurement kit meta info
            # update either always from source AQ DB or last time changed
            ChangeAQDB = None
            if type(update) is str:
              if update == 'WebDB': ChangeAQDB = False
              else: ChangeAQDB = True
            elif WebMeetkits[indx]['datum'] and (abs(WebMeetkits[indx]['datum']-WebMeetkits[indx]['changed']) >= update):
              if WebMeetkits[indx]['datum'] <= WebMeetkits[indx]['changed']:
                ChangeAQDB = True
              else:
                ChangeAQDB = False
            if ChangeAQDB == None: return # no change to be done
            try:
              # modification times bigger as 5 minutes
              WebInfo = {}
              # info fields from Web DB:
              # "project", "serial", used as identification
              # "label", "active",
              # "street", "pcode", "municipality", "village", "housenr" added
              # "province", "region",
              # "geohash", "altitude" to be added, # "coordinates" deprecated
              # "first",
              # "meteo", "dust", "gps", # to be added "power","net","time" see HWtypes
              # "notice",
              # "TTN_id", "luftdaten", "luftdatenID",
              # not synchronized: "AppEui", "DevEui", "AppSKEY", "DevAdd", "NwkSKEY",
              try:
                  if not self.SyncWithCMS.getFromWebDB( WebMeetkits[indx]['nid'],WebInfo):
                    self.log(self.module,'WARNING',"Unable to get CMS meta data info for nid %d." % nid)
              except: pass
              AQinfo = info.copy()
              if not AQinfo:
                try:
                  if not self.getInfoFromDB(WebMeetkits[indx]['project'],WebMeetkits[indx]['serial'],AQinfo):
                    self.log(self.module,'WARNING',"Unable to get AQ meta data info for kit projec %s serial %s." % (WebMeetkits[indx]['project'], WebMeetkits[indx]['serial']))
                except: pass
              if not AQinfo: # nothing to do, should not happen
                if self.verbose or self.debug:
                  sys.stderr.write(colored("No data DB relevant info found",'red')+ " for project %s, serial %s!\n" % (colored(WebMeetkits[indx]['project'],'red'),colored(WebMeetkits[indx]['serial'],'red'))) 
                continue

              # get WebDB/DB info/dicts with column values to be changed
              # interact on fields to update in either DB
              (WebInfo,AQinfo) = self.diffInfos(WebInfo,AQinfo, ChangeAQDB, WebMeetkits[indx])
              if WebInfo:
                self.UpdateWebDB(WebInfo,nid=WebMeetkits[indx]['nid'])
              if AQinfo:
                self.UpdateAQDB(AQinfo,project=WebMeetkits[indx]['project'],serial=WebMeetkits[indx]['serial'])
            except Exception as e:
              sys.stderr.write("%s: While handling %s/%s, exception error: %s\n" % (__modulename__,WebMeetkits[indx]['project'],WebMeetkits[indx]['serial'],str(e)))
          # one measurement kit WebMeetkits[indx] synchronized
        return True
    
###################################################
# test main loop
if __name__ == '__main__':
    from time import sleep

    import MyLogger
    MyLogger.Conf['level'] = 'INFO'
    MyLogger.Conf['print'] = True    # print colored tty output

    help = """
    Command: python %s {option|arg} ...
        --help | -h         This message.
        --time=<secs> | -t=<secs>  Minimal change time. Dflt 300 (5 minutes).
        --update=<DB> | -u=<DB> Synchronize time, DB or WebDB with the other as source.
                            Default: time; use db with last time change as source.
        --interact | -i     Make changes interactively.
        --debug | -d        Debug modus, do not change values in database.
        --verbose | -v      Show differences in DB's. Deflt: false.
        <project>_<serial pattern> Pattern match, only those measurement kits: eg SAN_.*.

    Synchronize meta information between air quality DB luchtmetingen
    and map/graphs visualisation, and interact a form to enter meta information DB CMS.
    Using Sensors/TTNtable from air quality DB.
    Using various CMS tables under field_data_field as eg
        project_id, serial_kit, ttn_topic, label, kaart_meetkit, datum, gps/meteo/fijnstof
        luftdaten_actief, admin_gemeente/provincie, fysiek_adres, node/nid/changed/title,
        operational.
    CMS uses for every field in the meta data form a different table.
    Fields values of both are synchronized using last modification date.
    Effect: marker on map are automatically adjusted, as well fysical addres.

    Without an argument synchronisation action will take place between both databases
    for all measurement kits in the database or for a selection of <project>_<serial>
    id's.
    Any command argument not mentioning a json file is used as an string expression
    for the match <project>_<serial>. E.g. '(HadM|SAN)_[0-9a-f]+abcd' will match all kits
    with serial number ending with 'abcd' of project 'HadM' or 'SAN'.
    
    Script can be called with an argument: file name with .json file name extension.
    This json file name used internal
    key/value pairs describing the meta data to be entered into the air quality Sensors
    and TTNtable tables.
    keys: see below for an example. Only those keys handled in the tables will be modified
    or entered as a new row/entry in the table. Old meta data in Sensors table will be
    maintained in deactivated modus. Ie the history of sensor kits is maintained.

    Database access credentials can be defined by Conf dict settings, or via environment
    CMS DB credentials: WEBUSER, WEBHOST (localhost), WEBPASS and WEBDB
    data database credentials: DBUSER, DBHOST (localhost), DBPASS (acacadabra), and DB (luchtmetingen)
""" % __modulename__

    # get nodes info from a json file and update node info to DB
    interact = False    # interact on changes
    verbose  = False    # interact verbosity increased
    update   = 5*60     # minimal time diff CMS and DB Default we use time diff DB's
    debug = False       # debugging turned on, lots of logging in DEBUG level
    KitSelections = []  # synchronize only these kit (match string expressions)

    for i in range(1,len(sys.argv)):
        if sys.argv[i] in ['--help', '-h']:       # help, how to use CLI
            print(help); exit(0)
        if sys.argv[i] in ['--verbose', '-v']:    # show differences in DB's
            verbose =  True; continue
        elif sys.argv[i] in ['--debug', '-d']:    # do not change DB values
            MyLogger.Conf['level'] = 'DEBUG'
            verbose = True; debug = True; continue
        elif sys.argv[i][:3] in ['--t', '-t=']:     # minimal modification diff in time 
            sys.argv[i] = sys.argv[i].replace('--time','-t')
            update = int(sys.argv[i][3:])
            continue
        elif sys.argv[i][:3] in ['--u', '-u=']:   # update either WebDB or DB from other
            sys.argv[i] = sys.argv[i].replace('--update','-u')
            update = sys.argv[i][3:]
            continue
        elif sys.argv[i] in ['--interact', '-i']: # interactive synchronization mode
            interact = True; continue
        elif sys.argv[i] in ['--all', '-a']:      # if in interactive mode also interact on not different values
            verbose = True; continue
        else: KitSelections.append(sys.argv[i])
    if not len(KitSelections):
        KitSelections = [ '.*' ]
    else:
        MyLogger.log(__modulename__,'ATTENT',"Limit kit synchronisation to kits matching: %s" % ('('+'|'.join(KitSelections)+')')) 
    
    updating = UpdateDBandWebDB(logger=MyLogger.log, verbose=verbose, interact=interact, debug=debug)
    try:
        # synchronize CMS Web MyWebDB kit info with Air Quality MyDB
        if not updating.syncWebDB(KitSelections, update=update):
          sys.stderr.write("Unable to find kit(s) in Web CMS DB: %s\n", KitSelections)
    except:
        MyLogger.log(__modulename__,'FATAL',"FAIL to synchronize CMS web kit info with Air Qual DB")

    #    Sensors = self.MyDB.TableColumns("Sensors")
    #    # return list of dicts {node nid,changed,project,serial} matching r'project'+'_'+r'serial' reg expression
   # 
   # # stop running threads and exit
   # ThreadStops = []
    
