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

# $Id: SyncWebDB.py,v 1.2 2020/05/02 15:38:36 teus Exp teus $

# TO DO: write to file or cache
# reminder: MySQL is able to sync tables with other MySQL servers

modulename='$RCSfile: SyncWebDB.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.2 $"[11:-2]

help = """
    Command: python %s arg ...
        --help | -h         This message.
        --time | -t <secs>  Minimal change time.
        --interact | -i     Make changes interactively.
        --debug | -d        Debug modus, do not change values in database.
        --quiet | -q        Be quiet: do not show differences in DB's. Deflt: false.
        <project>_<serial pattern> Pattern match, only those measurement kits: eg SAN_.*.
        <filename>.json     Filename json type with meta info to be entered in Sensors.

    Synchronize meta information between air quality DB luchtmetingen
    and map/graphs visualisation, and interact a form to enter meta information DB Drupal.
    Using Sensors/TTNtable from air quality DB.
    Using various Drupal tables under field_data_field as eg
        project_id, serial_kit, ttn_topic, label, kaart_meetkit, datum, gps/meteo/fijnstof
        luftdaten_actief, admin_gemeente/provincie, fysiek_adres, node/nid/changed/title,
        operational.
    Drupal uses for every field in the meta data form a different table.
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
""" % modulename

try:
    import sys
    import os
    import datetime
    import re
    from time import time, mktime
    from dateutil.parser import parse
    import geohash              # used to get geohash encoder for Drupal map
    import MyDB                 # routines to connect to air quality sensor DB
    import WebDB                # routines to connect to Drupal website visualisation DB
    import MyLogger             # logging routines
except ImportError as e:
    sys.exit("FATAL: One of the import modules not found: %s"% e)

# configurable options
__options__ = ['output',
    'DBhostname','DBdatabase','DBuser','DBpassword',
    'WEBhostname','WEBdatabase','WEBuser','WEBpassword',
    ]

Conf = {
    'output': False,
    'DBhostname': 'localhost', # host MySQL server
    'DBuser': None,        # user with insert permission of MySQL DB
    'DBpassword': None,    # DB credential secret to use MySQL DB
    'database': 'luchtmetingen', # MySQL database name
    'WEBhostname': 'localhost', # host MySQL server
    'WEBuser': None,       # user with insert permission of MySQL DB
    'WEBpassword': None,   # DB credential secret to use MySQL DB
    'WEBdatabase': 'unknown',    # MySQL database name
    'log': None,           # MyLogger log routiune
}
modulename='$RCSfile: SyncWebDB.py,v $'[10:-4]
KitSelections = []         # synchronize only these kit (match string expressions)

# stop running threads and exit
ThreadStops = []
def EXIT(status):
  global ThreadStops, modulename
  for stop in ThreadStops:
    try: stop()
    except: pass
  sys.exit("%s of %s" % (('FATAL: exit' if status else 'Exit'), modulename) )

quiet = False      # be queit while showing differences in DB's
prepend = 'field_data_field_' # for all DSrupal table names
# to convert value to Nld province name and visa versa. Indexed list.
provincies = [None,'Groningen','Friesland','Drente','Gelderland','Overijssel','Flevoland','Noord-Holland','Zuid-Holland','Zeeland','Brabant','Limburg']
# table/column translation tablke between Drupal Web DB abd air quality DB Sensors/TTNtable
fld2drupal = {
    "project":     ["project_id","tid","Sensors"],   # taxonomy_term_data(tid,name)
    "serial":      ["serial_kit","value","Sensors"], # delta 0 kit serial number hex

    "TTN_id":      ["ttn_topic","value","TTNtable"], # delta 0 TTN device topic name
    "GPS":         ["kaart_meetkit","ordinates",None],       # delta 0 dict
    "coordinates": ["kaart_meetkit","ordinates","Sensors"],  # delta 0 lat,long,alt
    "label":       ["label","value","Sensors"],      # delta 0 handy lable XYZ_a1f9
    "kaart":       ["kaart_meetkit","value",None],   # delta 0 
    "first":       ["datum","value","Sensors"],      # delta 0 date of installation
    "gps":         ["gps","value",'drupal'],         # delta 0 GPS sensor type
    "meteo":       ["meteo","value",'drupal'],       # delta 0 meteo sensor type
    "dust":        ["fijnstof","value",'drupal'],    # delta 0 dust sensor type
    "description": [None,None,"Sensors"],            # combination dust, meteo, gps
    "comment":     ["commentaar","value","Sensors"], # delta 0 kit comments as situation

    # "adres":       ["fysiek_adres","address",None],        # delta 0
    # "name":        ["fysiek_adres","name_line",None],      # delta 0
    # "organisation":["fysiek_adres","organisation_name",None],# delta 0
    "street":      ["fysiek_adres","thoroughfare","Sensors"],# delta 0
    "pcode":       ["fysiek_adres","postal_code","Sensors"], # delta 0
    "village":     ["fysiek_adres","locality","Sensors"],    # delta 0
    "municipality":["admin_gemeente","value","Sensors"],     # delta 0
    "province":    ["admin_provincie","value","Sensors",provincies],# delta 0, indexed
    "region":      ["regio","tid","Sensors"],        # taxonomy_term_data(tid, name)
    # "country":     ["fysiek_adres","country",None],# delta 0 NL

    "active":      ["operationeel","value","Sensors"],       # delta 0 also in TTNtable
    "luftdaten":   ["luftdaten_actief","value","TTNtable"],  # delta 0 post to Luftdaten map
    "luftdatenID": ["luftdaten_id","value","TTNtable"],      # delta 0 non default luftdaten ID
    # luftdate.info bool or hex strg is converted to luftdaten en luftdatenID
    "notice":      ["notices","value","Sensors"],    # event addresses

    "AppEui":      [None,None,None],   # TTN application ID "70B3D75E0D0A04D3" void
    "DevEui":      [None,None,None],   # TTN device ID "AAAA10D739A3D689" void
    "AppSKEY":     [None,None,None],   # TTN secret key "3E210C866D12AFF288F3A1C857DB5292" void
    "DevAdd":      [None,None,None],   # TTN ABP device key void
    "NwkSKEY":     [None,None,None],   # TTN ABP secret key void

    "AQI":         ["lucht_kwaliteits_index","value",None],  # delta 0 .. 3 aqi index values
    "AQIdatum":    ["aqi_datum","value",None],               # delta 0 date aqi index update
    "AQIcolor":    ["marker_color","value",None],            # delta 0 aqi index color
}
# example info dict keys uised as internal exchange format
#info_fields = [
#        "TTN_id",        # TTN topic (str)
#        "project",       # project name (str)
#        "GPS", # { "altitude":float,"latitude":float,"longitude":float}, # converted
#        "coordinates", # [float lat,float lon,float alt],
#        "label",         # label (str)
#        "serial",        # serial nr hex kit (str)
#        # "SN",          # serial cpu (str) not supported
#        # "name", "phone" # contact details not supported
#        "street","pcode",# (str)
#        "municipality", "village", "province", # (str), (str), (str)
#        "first",         # first date (str)
#        "comment",       # any commenteg location detail (str)
#        "AppEui",        # TTN application ID "70B3D75E0D0A04D3" void
#        "DevEui",        # TTN device ID "AAAA10D739A3D689" void
#        "AppSKEY",       # TTN secret key "3E210C866D12AFF288F3A1C857DB5292" void
#        "DevAdd",        # TTN ABP device key void
#        "NwkSKEY",       # TTN ABP secret key void
#        "meteo", "dust", "gps", #  eg BME680, PMSx003, NEO-6  (str) converted to:
#        "description",   # (str) eg ";hw: BME680,PMSx003,NEO",
#        "notice",        # (str) eg "email:metoo@host.org,slack:http://host/notices/12345",
#        "active",        # (bool) archive in air qual DB, eg True
#        "luftdaten.info",#  (bool or str) may have luftdatenID serial, converted to:
#        "luftdaten",     # (bool) forward to Lufdaten.info, if None no forwd Madavi.de
#        "luftdatenID",   # (str) use as Luftdaten ID iso default TTN-<serial kit>
#   ]

# internally used table columns from air quality database tables
info_fields = []
for item in fld2drupal.keys():
    if fld2drupal[item][2] in ['Sensors','TTNtable','drupal']: info_fields.append(item)
DustTypes  = ['SDS','PMS','SPS']  # different handled types Nova, Plantower, Sensirion
MeteoTypes = ['DHT','SHT','BME']  # different handled types Adafruit, Sensirion, Bosch
GpsTypes   = ['NEO']              # Swiss chip NEO-6

# next can be changed on command line
interact = False          # interact about changes to be made
interactAll = False       # interact also when the is no diff 
debug = False             # make changes into DB's, on True no changes are made to DB's
changeTime = 5*60         # minimal time in secs difference to do synchronisation in DB's

def convert2geohash(ordinates):
    geo = ordinates
    if not type(geo) is list:
        geo = [float(x) for x in geo.split(',')]
    if len(geo) < 2:
        raise ValueError("location coordinates error with %s" % str(ordinates))
    return pygeohash(float(geo[0]), float(geo[1]), precision=12)

def GPSdistance(gps1,gps2): # returns None on a not valid GPS oordinate
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


# get fysical address info for a node nid from Drupal database into info dict
# fields are country dependent. community, province are in value tables
def getWebAddress(nid,items,info):
    if not type(items) is list: items = items.split(',')
    if not len(items): return True
    qry = []; fields = []
    for item in items:
        if fld2drupal[item][0] != 'fysiek_adres': continue
        fields.append(item)
        qry.append('field_fysiek_adres_'+fld2drupal[item][1])
    if not len(qry): return True
    qry = WebDB.db_query("SELECT %s FROM %sfysiek_adres WHERE entity_id = %d LIMIT 1" % (','.join(qry),prepend,nid),True)
    if not len(qry) or len(qry[0]) != len(fields):
        raise ValueError("Unable to obtain all address fields (%s) got (%s)" % (str(fields),str(qry[0])))
    for indx in range(len(fields)):
      if qry[0][indx]: info[fields[indx]] = qry[0][indx]
      else: info[fields[indx]] = None
    return True

# make changes in Drupal website DB. Not used are bundle check, deleted bool, revision_id,
#              language, delta = 0, geom = longblob (???)
def setWebValue(nid,item,value,adebug=False):
    global prepend, fld2drupal, modulename
    if not item in fld2drupal.keys() or not fld2drupal[item][1]: return False
    if type(value) is bool: value = "1" if value else "0"
    elif item in ['first']: value = "'%s'" % datetime.datetime.fromtimestamp(value).strftime("%Y-%m-%d")
    else: value = "'%s'" % str(value)
    update = '' # compile update Web DB Drupal query
    try:
        if item == 'coordinates':                      ### kaart_meetkit type
          ord = value[1:-1].split(',')
          lat = max(ord[0],ord[1]); lon = min(ord[0],ord[1])
          flds = [
            # in Nld lat is > lon, watchout for script and admin errors
            # entity_type = map point
            fld2drupal[item][0]+'_lat = %3.7f' % lat,
            fld2drupal[item][0]+'_top = %3.7f' % lat,
            fld2drupal[item][0]+'_bottum = %3.7f' % lat,
            fld2drupal[item][0]+'_lon = %3.7f' % lon,
            fld2drupal[item][0]+'_left = %3.7f' % lon,
            fld2drupal[item][0]+'_right = %3.7f' % lon,
            fld2drupal[item][0]+"_geohash = '%s'" % str(pygeohash(lat,lon,precision=12)),
          ]
          update = "UPDATE %s SET %s WHERE entity_id = %d" % (prepend+fld2drupal[item][0],','.join(flds),nid)

        elif fld2drupal[item][1] == 'value':          ### value type
          update = "UPDATE %s SET %s = %s WHERE entity_id = %d" % (prepend+fld2drupal[item][0],'field_'+fld2drupal[item][0]+'_value',value,nid)

        elif fld2drupal[item][1] == 'tid':            ### tid type
          qry = WebDB.db_query("SELECT tid FROM taxonomy_term_data WHERE name = %s" % value, True)
          if not len(qry) or not len(qry[0]): # unknown term, insert new one
              MyLogger.log(modulename,'WARNING','Add to Web Drupal DB taxonomy term %s' % value)
              update = "INSERT INTO %s (vid,name,description,weight,format) VALUES (8,%s,'project ID',1)" % value
              if adebug:
                print("WebDB change to tid 1001:\n  %s" % update); qry =[(1001,)]
              else:
                WebDB.db_query(update, False)
                qry = WebDB.db_query("SELECT tid FROM taxonomy_term_data WHERE name = %s" % value, True)
                if not len(qry) or not len(qry[0]):
                  MyLogger.log(modulename,'ERROR','Failed to insert new taxonomy term %s' % value)
                  return False
          update = "UPDATE %s SET %s = %d WHERE entity_id = %d" % (prepend+fld2drupal[item][0],'field_'+fld2drupal[item][0]+'_tid', qry[0][0], nid) 

        elif fld2drupal[item][0] == 'fysiek_adres': ### adres type
          if fld2drupal[item][1] in ['thoroughfare','locality']:
            qry = WebDB.db_query("SELECT field_fysiek_adres_%s FROM %s WHERE entity_id = %d" % (('locality' if fld2drupal[item][1] == 'thoroughfare' else 'thoroughfare'),prepend+fld2drupal[item][0],nid),True)
            if len(qry) and len(qry[0]):
                if fld2drupal[item][1] == 'thoroughfare':
                  try: update = "%s: %s" % (str(qry[0][0]),str(value[1:value.rindex(' ')]))
                  except: update = "%s: %s" % (str(qry[0][0]),str(value[1:-1]))
                else:
                  update = "%s: %s" % (str(value[1:-1]),str(qry[0][0]))
                update = "UPDATE node SET title = '%s' WHERE nid = %d" % (update,nid)
                if not adebug:
                  WebDB.db_query(update, False)
          update = "UPDATE %s SET %s = %s WHERE entity_id = %d" % (prepend+fld2drupal[item][0],'field_fysiek_adres_'+fld2drupal[item][1], value, nid)

        if adebug: print("WebDB change with:\n  %s" % update)
        elif update: WebDB.db_query(update, False)
    except:
        MyLogger.log(modulename,'DEBUG','Failed to update Drupal web DB with %s: query %s' % (item,update))
        MyLogger.log(modulename,'ERROR','Failed to update Drupal web DB with %s: value %s' % (item,value))
        return False
    return True
            
    

# get tid values from taxonomy Drpual website table to dict
def getTIDvalues(nid,items,info):
    global prepend, fld2drupal
    if not type(items) is list: items = items.split(',')
    if not len(items): return True
    for item in items:
        if fld2drupal[item][1] != 'tid': continue
        qry = WebDB.db_query('SELECT taxonomy_term_data.name FROM taxonomy_term_data, %s%s WHERE  %s%s.entity_id = %d AND taxonomy_term_data.tid = %s%s.field_%s_tid' % (prepend,fld2drupal[item][0],prepend,fld2drupal[item][0],nid,prepend,fld2drupal[item][0],fld2drupal[item][0]), True)
        if not len(qry) or not qry[0]:
            raise ValueError('Taxonomy lookup problem for %s' % item)
        if qry[0][0]: info[item] = qry[0][0]
        else: info[item] = None
    return True

# get values and tids for a node nid from Drupal database into info dict
def getFromWeb(nid, info, items=info_fields):
    global Conf, prepend, fld2drupal
    selects = []; froms = []; wheres = []; address = []; fields = []; tids = []
    if not type(items) is list: items = items.split(',')
    for item in items:
        if not item in fld2drupal.keys() or not fld2drupal[item][0]:
          continue
        if fld2drupal[item][0] == 'fysiek_adres':
          address.append(item); continue
        if fld2drupal[item][1] == 'tid':
          tids.append(item); continue
        # handle field_*_value type of info
        fields.append(item)
        if fld2drupal[item][1] == 'value':
          selects.append(prepend+fld2drupal[item][0]+'.field_'+fld2drupal[item][0]+'_'+fld2drupal[item][1])
          froms.append(prepend+fld2drupal[item][0])
          wheres.append(prepend+fld2drupal[item][0]+'.'+'entity_id = %s' % nid)
        elif fld2drupal[item][1] == 'ordinates':
          selects.append('CONCAT('+prepend+fld2drupal[item][0]+'.field_'+fld2drupal[item][0]+'_lat,",",'+prepend+fld2drupal[item][0]+'.field_'+fld2drupal[item][0]+'_lon,",0")')
          froms.append(prepend+fld2drupal[item][0])
          wheres.append(prepend+fld2drupal[item][0]+'.'+'entity_id = %s' % nid)
    # try to get them in one show if not one by one
    qry = 'SELECT '+','.join(selects)+' FROM '+','.join(list(set(froms)))+' WHERE '+' AND '.join(list(set(wheres)))
    qry = WebDB.db_query(qry, True)
    if not len(qry): # try one by one
        MyLogger.log(modulename,'DEBUG','Failed to get info %s from Web database' % str(items))
        qry = [[]]
        for indx in range(len(fields)):
          qry[0].append(None)
          nqry = WebDB.db_query('SELECT %s FROM %s WHERE %s' % (selects[indx],froms[indx],wheres[indx]),True)
          if len(nqry) and len(nqry[0]): qry[0][indx] = nqry[0][0]
    for indx in range(len(fields)):
        try:
          if len(fld2drupal[fields[indx]]) > 3: # indexed value
            try:
              info[fields[indx]] = fld2drupal[fields[indx]][3][int(qry[0][indx])]
            except:
              MyLogger.log(modulename,'ERROR','Unexpected index %s for field %s.' % (qry[0][indx],fields[indx]))
              info[fields[indx]] = qry[0][indx]
          elif type(qry[0][indx]) is int:
            if qry[0][indx] <= 1: info[fields[indx]] = (True if qry[0][indx] else False)
            else: info[fields[indx]] = qry[0][indx]
          else: info[fields[indx]] = qry[0][indx]
        except:
          MyLogger.log(modulename,'ERROR','Failed to import info %s from Web database' % fields[indx])
          return False
    if 'GPS' in info.keys():
        if not 'coordinates' in info.keys(): info['coordinates'] = info['GPS']
        ord = [float(x) for x in info['GPS'].split(',')]
        info['GPS'] =  { 'longitude': ord[LON], 'latitude': ord[LAT], 'altitude': None }
    for item in ['first','datum']:
        if item in info.keys() and (not type(info[item]) is int):
          info[item] = DateTranslate(info[item])
    if not 'description' in info.keys() or not info['description']:
        hw = []
        for item in ['meteo','dust','gps']:
          if item in info.keys() and info[item]: hw.append(info[item].upper())
        hw.sort()
        if len(hw): info['description'] = ";hw: %s,TIME" % ','.join(hw)

    if len(tids) and not getTIDvalues(nid,tids,info): return False
    if len(address) and not getWebAddress(nid,address,info): return False
    for key,value in info.items():
        if value == 'None' or value == 'NULL': info[key] = None

    return True

# get values and tids for a node nid from Drupal database into info dict
def getFromAQ(project,serial, info, items=info_fields):
    global Conf, modulename
    selects = { 'Sensors': [], 'TTNtable': [] }
    if not type(items) is list: items = items.split(',')
    for item in items:
        if (not item in fld2drupal.keys()) or (not fld2drupal[item][2]) or (not fld2drupal[item][2] in selects.keys()):
          continue
        selects[fld2drupal[item][2]].append(item)
    for table in selects.keys(): # could be done in one query with a join tables
        if not len(selects[table]): continue
        fields = []
        for indx in range(len(selects[table])):
            fields.append(selects[table][indx])
            if selects[table][indx] in ['first','datum','last_check','id']: # date format use POSIX timestamp
                selects[table][indx] = 'UNIX_TIMESTAMP('+fields[indx]+')'
        qry = MyDB.db_query("SELECT %s FROM %s WHERE project = '%s' and serial = '%s' ORDER BY active DESC, datum DESC LIMIT 1" % (','.join(selects[table]),table,project,serial),True)
        if not len(qry) or not len(qry[0]):
            raise ValueError('Unknown fields in %s table: %s.' % (table,str(selects[table])))
        for indx in range(len(selects[table])):
            if type(qry[0][indx]) is int:
              if 0 <= qry[0][indx] <= 1:
                info[fields[indx]] = (True if qry[0][indx] else False)
              else:
                info[fields[indx]] = qry[0][indx]
            elif str(qry[0][indx]).isdigit():
              info[fields[indx]] = int(str(qry[0][indx]))
            elif str(qry[0][indx]) == 'None': info[fields[indx]] = None
            else:
              info[fields[indx]] = str(qry[0][indx])
    if 'coordinates' in info.keys() and type(info['coordinates']) is str:  # may try to correct order
        ord = [float(x) for x in info['coordinates'].split(',')]
        if ord[0] < ord[1]:
            tmp = ord[1]
            try: ord[2] = "%4.1f" % ord[2]
            except: pass
            ord[1] = "%3.7f" % ord[0]; ord[0] = "%3.7f" % tmp
            info['coordinates'] = ','.join(ord)
    return True

Sensors = MyDB.TableColumns("Sensors")
kitType = 'meetkit_lokatie'
def getMeetKits():
    global kitType
    qry = WebDB.db_query("""
            SELECT
                node.nid, node.changed, taxonomy_term_data.name,
                # field_data_field_project_id.field_project_id_tid,
                field_data_field_serial_kit.field_serial_kit_value
            FROM node, field_data_field_project_id, field_data_field_serial_kit,
                 taxonomy_term_data
            WHERE node.type = '%s' AND node.status = 1 AND
                field_data_field_serial_kit.entity_id = node.nid AND
                field_data_field_project_id.entity_id = node.nid AND
                taxonomy_term_data.tid = field_data_field_project_id.field_project_id_tid
            ORDER BY node.changed DESC""" % kitType, True)
    ids = ['nid','changed','project','serial']
    rts = []
    for row in range(len(qry)):
        fnd = False
        for i in range(len(KitSelections)):
            if KitSelections[i].match(str(qry[row][2]+'_'+qry[row][3])):
                fnd = True; break
        if not fnd: continue
        item = {}
        for i in range(len(ids)): item[ids[i]] = qry[row][i]
        rts.append(item)
    return rts

def nodesImport(file):
    from jsmin import jsmin     # tool to delete comments and compress json
    import json
    try:
        new = {}
        with open(file) as _typeOfJSON:
            print('Importing nodes from json file %s' % sys.argv[1:][0])
            new = jsmin(_typeOfJSON.read())
        new = json.loads(new)
    except IOError:
        print('WARNING No node json file %s found' % sys.argv[1:][0])
        exit(1)
    except ValueError as e:
        print('ERROR Json error in admin nodes file %s: %s' % (sys.argv[1:][0],e))
        exit(1)
    # if not db_connect():
    #     print('ERROR Unable to connect to DB via Conf: %s' % str(Conf))
    #     exit(1)
    for item in new.items():
        print('Importing node info for node %s' % item[0])
        item[1]['TTN_id'] = item[0]
        if not MyDB.putNodeInfo(item[1]):
            print('ERROR importing node %s info to DB' % item[0])

# interact to change values
def InteractDBvalues(fld,DrItem,AqItem,ToChange):
    global interact, debug
    if not interact: return str(ToChange)
    AqItemC = "\033[%dm%s\033[0m" % ((32 if AqItem == ToChange else 31),str(AqItem)[:25])
    DrItemC = "\033[%dm%s\033[0m" % ((32 if DrItem == ToChange else 31),str(DrItem)[:25])
    GEL = '=='
    if AqItem != ToChange: GEL = '->'
    if DrItem != ToChange: GEL = '<-'
    print("  %12.12s: %34.34s %s %-34.34s %s" % (fld,str(DrItemC),GEL,str(AqItemC),str(ToChange)))
    while True:
      try: line = raw_input("Changes to be made (Y/n) to \033[32m%s\033[0m? " % ToChange)
      except: line = input("Changes to be made (Y/n) to \033[32m%s\033[0m? " % ToChange)
      line = line.strip()
      if not line or (line.lower()[0] == 'y'):
        break
      elif len(line) < 3 and line.lower()[0] == 'n': line = None
      ToChange = line
      if ToChange == None: ToChange = None
      elif ToChange.lower() == 'true': ToChange = True
      elif ToChange.lower() == 'false': ToChange = False
      elif ToChange.isdigit(): ToChange = int(ToChange)
      elif ToChange.lower() == 'none': ToChange = None
    AqItemC = "\033[%dm%s\033[0m" % ((32 if AqItem == ToChange else 31),str(AqItem)[:25])
    DrItemC = "\033[%dm%s\033[0m" % ((32 if DrItem == ToChange else 31),str(DrItem)[:25])
    GEL = '=='
    if AqItem != ToChange: GEL = '->'
    if DrItem != ToChange: GEL = '<-'
    print("  %12.12s: %34.34s %s %-34.34s \033[1m\033[35m%s\033[0m" % (fld,str(DrItemC),GEL,str(AqItemC),str(ToChange)))
    return ToChange

# translate month from dutch to english and similar format
# return if not format defined the Posix time base secs
def DateTranslate(datum, format=None):
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
        sys.stderr.write("Unable to parse time: %s, error %s." % (rslt,str(e)))
        if format: return datum
        rslt = 0
    try:
      if format: return datetime.datetime.fromtimestamp(rslt).strftime(format)
      return rslt
    except: return datum
        
# show differences per field between Drupal web DB meetkit info and air quality meta data DB
def diffInfos(Drupal,AQDB,left,line1='',line2=''):
    fields = list(set(Drupal.keys()+AQDB.keys()))
    if line1: print("Diff %s:" % line1)
    if line2: print("%s" % line2)
    fields.sort(); DRrslt = {}; AQrslt = {}
    for fld in fields:
        DrItem = 'None' if not fld in Drupal.keys() or Drupal[fld] == None else Drupal[fld]
        AqItem = 'None' if not fld in AQDB.keys() or AQDB[fld] == None else AQDB[fld]
        if fld in ['first','datum'] and DrItem != 'None':
            DrItem = DateTranslate(DrItem,format='%Y-%m-%d')
        if fld in ['first','datum'] and AqItem != 'None':
            AqItem = DateTranslate(AqItem,format='%Y-%m-%d')
        diff =  DrItem != AqItem
        if fld == 'coordinates':
            if GPSdistance(DrItem,AqItem) > 50: diff = True
            else: diff = False
        if not diff and not interactAll:
          if not quiet: print("  %12.12s: %s" % (fld,str(DrItem)))
          continue
        ToChange = (DrItem if left else AqItem)
        AqItemC = "\033[%dm%s\033[0m" % ((32 if AqItem == ToChange else 31),str(AqItem)[:25])
        DrItemC = "\033[%dm%s\033[0m" % ((32 if DrItem == ToChange else 31),str(DrItem)[:25])
        if interact:
          ToChange = InteractDBvalues(fld,DrItem,AqItem,ToChange)
          if ToChange == None:
            if debug:
              print("  %12.12s: %34.34s -- %-34.34s unchanged" % (fld,str(DrItemC),str(AqItemC)))
            continue
        elif debug:
          print("  %12.12s: %34.34s %s %-34.34s %s" % (fld,str(DrItemC),('<-' if AqItem == ToChange else '->'),str(AqItemC),str(ToChange)))
        if ToChange != AqItem:
          AQrslt[fld] = (ToChange if ToChange != 'None' else None)
          if fld in ['first','datum'] and ToChange != 'None':
            AQrslt[fld] = int(mktime(parse(AQrslt[fld], dayfirst=True, yearfirst=False).timetuple()))
        if ToChange != DrItem:
          DRrslt[fld] = (ToChange if ToChange != 'None' else None)
          if fld in ['first','datum'] and ToChange != 'None':
            DRrslt[fld] = int(mktime(parse(DRrslt[fld], dayfirst=True, yearfirst=False).timetuple()))
    if len(set(['meteo','dust','gps','time']).intersection(set(AQrslt.keys()))) > 0:
      for fld in set(['meteo','dust','gps','time']).difference(set(AQrslt.keys())):
        if fld in Drupal.keys(): AQrslt[fld] = Drupal[fld]
    if debug or interact: print("DIFF RESULTs:")
    if debug or interact:
        print("  Drupal DB  : ", str(DRrslt))
    if debug or interact:
        print("  Air Qual DB: ", str(AQrslt))
    return (DRrslt,AQrslt)

def setMembers(column,table):
    qry = MyDB.db_query("SELECT DISTINCT %s FROM %s" % (column,table), True)
    rslt = []
    if not len(qry) or not len(qry[0]): return rslt
    for item in qry:
        if len(item): rslt.append(item[0])
    return rslt

# insert new entrys in Sensors/TTNtable for this Drupal entry if operational
def insertNewKit(WebKit):
    global modulename, interact
    qry = MyDB.db_query("SELECT UNIX_TIMESTAMP(datum) FROM Sensors WHERE project = '%s' AND serial = '%s' ORDER BY active DESC, datum DESC LIMIT 1"% (WebKit['project'],WebKit['serial']), True)
    if len(qry) and len(qry[0]) and qry[0][0]: return qry[0][0]
    operational = WebDB.db_query("SELECT field_operationeel_value from field_data_field_operationeel WHERE entity_id = %d" % WebKit['nid'], True)
    if not len(operational) or not len(operational[0]): operational = None
    elif not operational[0][0]: operational = False
    else: operational = True
    if not operational: return 0
    # vid == 8 for project names defined in Drupal
    # qry = WebDB.db_query("SELECT name FROM taxonomy_term_data WHERE vid = 8", True)
    setSensors = setMembers('project','Sensors')
    setTTNtable = setMembers('project','TTNtable')
    if not WebKit['project'] in set(set(setSensors) & set(setTTNtable)):
        MyLogger.log(modulename,'WARNING','Unknown project "%s" for a kit. Insert it manually.' % WebKit['project'])
        if not interact: return 0
        try: line = raw_input("Insert new project %s serial %s in Sensors/TTNtable? (Y/n): " % (WebKit['project'],WebKit['serial']))
        except: line = 'no'
        line = line.strip()
        if line and (line.lower()[0] != 'y'): return 0
    try:
        t = WebKit['changed']-12*60*60 # make sure Drupal date time overrules AQ date time
        MyLogger.log(modulename,'ATTENT','Insert new entry project %s, serial %s in AQ DB tables from Drupal node %d dated: %s.' % (WebKit['project'],WebKit['serial'],WebKit['nid'],datetime.datetime.fromtimestamp(WebKit['changed']).strftime("%Y-%m-%d %H:%M")))
        MyDB.db_query("INSERT INTO Sensors (datum,project,serial,active) VALUES (FROM_UNISTIMESTAMP(%d),%s,%s,0)" % (t,WebKit['project'],WebKit['serial']),False)
        qry = MyDB.db_query("SELECT id FROM TTNtable WHERE project = %s AND serial = '%s'" % (WebKit['project'],WebKit['serial']), True)
        if len(qry) and len(qry[0]): return t
        MyDB.db_query("INSERT INTO TTNtable (datum,project,serial,active) VALUES (FROM_UNISTIMESTAMP(%d),%s,%s,0)" % (t,WebKit['project'],WebKit['serial']),False)
        return t
    except: return 0

def syncWebDB():
    global Conf, KitSelections, modulename
    global DustTypes, MeteoTypes, GpsTypes
    #if Conf['log']: 
    #    WebDB.Conf['log'] = MyDB.Conf['log'] = Conf['log']
    #    WebDB.Conf['print'] = MyDB.Conf['print'] = Conf['print']
    #    #ThreadStops.append(Conf['log'].stop)
    if not WebDB.db_connect(): # credentials from WEB ENV
        sys.stderr.write("Cannot connect to %s database" % Conf['WEBdatabase'])
        EXIT(1)
    if not MyDB.db_connect(): # credentials from DB ENV
        sys.stderr.write("Cannot connect to  %s database" % Conf['database'])
        EXIT(1)
    WebMeetkits = getMeetKits()
    for indx in range(len(WebMeetkits)):
        qry = MyDB.db_query("SELECT UNIX_TIMESTAMP(datum) FROM Sensors WHERE project = '%s' AND serial = '%s' ORDER BY active DESC, datum DESC LIMIT 1"% (WebMeetkits[indx]['project'],WebMeetkits[indx]['serial']), True)
        if not len(qry):
            MyLogger.log(modulename,'ATTENT','Sensor kit from Drupal node %d with project %s,serial %s is not defined in Sensors/TTNtable table(s).' % (WebMeetkits[indx]['nid'],WebMeetkits[indx]['project'],WebMeetkits[indx]['serial']))
            WebMeetkits[indx]['datum'] = insertNewKit(WebMeetkits[indx])
        else: WebMeetkits[indx]['datum'] = qry[0][0]
        # WebMeetkits list of dict nid, changed, project, serial, Sensors datum keys
        MyLogger.log(modulename,'DEBUG','Kit Drupal node nid %d dated %s AND data DB kit %s_%s dated %s.' % (WebMeetkits[indx]['nid'],datetime.datetime.fromtimestamp(WebMeetkits[indx]['changed']).strftime("%Y-%m-%d %H:%M"),WebMeetkits[indx]['project'],WebMeetkits[indx]['serial'],datetime.datetime.fromtimestamp(WebMeetkits[indx]['datum']).strftime("%Y-%m-%d %H:%M")))
        if WebMeetkits[indx]['datum'] and (abs(WebMeetkits[indx]['datum']-WebMeetkits[indx]['changed']) >= changeTime):
          try:
            # modification times bigger as 5 minutes
            WebInfo = {}
            # info fields:
            # "TTN_id", "project", "GPS", "coordinates", "label", "serial",
            # "street","pcode", "municipality", "village", "province",
            # "first", "comment",
            # "AppEui", "DevEui", "AppSKEY",
            # "DevAdd", "NwkSKEY",
            # "meteo", "dust", "gps", "description",
            # "notice",
            # "active", "luftdaten.info", "luftdaten", "luftdatenID",
            try:
                if not getFromWeb( WebMeetkits[indx]['nid'],WebInfo):
                    MyLogger.log(modulename,'WARNING',"Unable to get Drupal meta data info for nid %d." % nid)
            except: pass
            AQinfo = {}
            try:
                if not getFromAQ(WebMeetkits[indx]['project'],WebMeetkits[indx]['serial'],AQinfo):
                    MyLogger.log(modulename,'WARNING',"Unable to get AQ meta data info for kit projec %s serial %s." % (WebMeetkits[indx]['project'], WebMeetkits[indx]['serial']))
            except: pass
            if 'description' in AQinfo.keys():
                for item in AQinfo['description'].replace(';hw:','').strip().split(','):
                  if item.strip()[:3].upper() in DustTypes:
                    AQinfo['dust'] = item.strip().upper()
                  elif item.strip()[:3].upper() in MeteoTypes:
                    AQinfo['meteo'] = item.strip().upper()
                  elif item.strip()[:3].upper() in GpsTypes: # only one product
                    AQinfo['gps'] = 'NEO-6'

            if WebMeetkits[indx]['changed'] > WebMeetkits[indx]['datum']:
                (WebInfo,AQinfo) = diffInfos(WebInfo,AQinfo,True,'\033[32mweb Drupal DB\033[0m info (nid %d) >> \033[31mAQ data DB\033[0m info (%s,%s)' % (WebMeetkits[indx]['nid'],WebMeetkits[indx]['project'],WebMeetkits[indx]['serial']),"%34.34s >> %s" % (datetime.datetime.fromtimestamp(WebMeetkits[indx]['changed']).strftime("%Y-%m-%d %H:%M"),datetime.datetime.fromtimestamp(WebMeetkits[indx]['datum']).strftime("%Y-%m-%d %H:%M")))
            else:
                (WebInfo,AQinfo) = diffInfos(WebInfo,AQinfo,False,'\033[31mweb Drupal DB\033[0m info (nid %d) << \033[32mAQ data DB\033[0m info (%s,%s)' % (WebMeetkits[indx]['nid'],WebMeetkits[indx]['project'],WebMeetkits[indx]['serial']),"%34.34s << %s" % (datetime.datetime.fromtimestamp(WebMeetkits[indx]['changed']).strftime("%Y-%m-%d %H:%M"),datetime.datetime.fromtimestamp(WebMeetkits[indx]['datum']).strftime("%Y-%m-%d %H:%M")))
            # may need to return also a dict with fields/values which are not change but present
            if len(WebInfo):
                for (item,value) in WebInfo.items():
                    MyLogger.log(modulename,'INFO',"Synchronize web Drupal DB node %d: %s: '%s'." % (WebMeetkits[indx]['nid'],item,str(value)))
                    setWebValue(WebMeetkits[indx]['nid'],item,value,adebug=debug)
                if not debug:
                    WebDB.db_query("UPDATE node SET changed = UNIX_TIMESTAMP(now()) WHERE nid = %d" % WebMeetkits[indx]['nid'], False)
            if len(AQinfo):
                if not 'project' in AQinfo.keys(): AQinfo['project'] = WebMeetkits[indx]['project']
                if not 'serial' in AQinfo.keys(): AQinfo['serial'] = WebMeetkits[indx]['serial']
                MyLogger.log(modulename,'INFO',"Synchronize web Air Quality DB meta info: %s" % str(AQinfo))
                MyDB.putNodeInfo(AQinfo,adebug=debug)
          except Exception as e:
            sys.stderr.write("%s: While handling %s/%s, exception error: %s\n" % (modulename,WebMeetkits[indx]['project'],WebMeetkits[indx]['serial'],str(e)))
    return True


# test main loop
if __name__ == '__main__':
    from time import sleep
    MyDB.Conf['output'] = True
    MyDB.Conf['hostname'] = 'localhost'         # host InFlux server
    MyDB.Conf['database'] = 'luchtmetingen'     # the MySql db for test usage, must exists
    MyDB.Conf['user'] = 'IoS'                   # user with insert permission of InFlux DB
    MyDB.Conf['password'] = 'acacadabra'        # DB credential secret to use InFlux DB
    if not Conf['log']:
        Conf['print'] = True                    # print colored tty output
        Conf['log'] = MyLogger.log
        MyLogger.Conf['level'] = 'INFO'
        MyLogger.Conf['print'] = Conf['print']
        MyDB.Conf['log'] = Conf['log']
        WebDB.Conf['log'] = Conf['log']

    # get nodes info from a json file and update node info to DB
    nodes = False
    for i in range(1,len(sys.argv)):
        if sys.argv[i] in ['--help', '-h']:    # help, how to use CLI
            print(help); exit(0)
        if sys.argv[i] in ['--verbose', '-v']:    # show differences in DB's
            quiet =  False; continue
        if sys.argv[i] in ['--debug', '-d']:    # do not change DB values
            debug = True; continue
        if sys.argv[i] in ['--time', '-t']:     # minimal modification diff in time 
            if sys.argv[i].find('-t') == 0 and len(sys.argv[i]) > 2:
                changeTime = int(sys.argv[i][2:])
            else:
                changeTime = int(sys.argv[i+1]); i += 1
            continue
        if sys.argv[i] in ['--interact', '-i']: # interactive synchronization mode
            interact = True; continue
        if sys.argv[i] in ['--all', '-a']:      # if in interactive mode also interact on not different values
            interactAll = True; continue
        if sys.argv[i] and sys.argv[i][-5:].lower() == '.json':                      # import json node file into Air Quality DB
            nodes = True
            try: nodesImport(sys.argv[i])
            except: print("Failed to import json nodes file: " % sys.argv[i])
        else:
            KitSelections.append(sys.argv[i])
    if not nodes:
        if not len(KitSelections):
            KitSelections = [ '.*' ]
        else:
            MyLogger.log(modulename,'ATTENT',"Limit kit synchronisation to kits matching: %s" % ('('+'|'.join(KitSelections)+')')) 
        for i in range(len(KitSelections)):  # select which kits to synchronize
            KitSelections[i] = re.compile('^'+KitSelections[i]+'$', re.I)
        try: syncWebDB()                     # synchronize Drupal Web DB kit info with Air Qual
        except:
            print("FAIL to synchronize Drupal web kit info with Air Qual DB")
            EXIT(1)
    EXIT(0)
