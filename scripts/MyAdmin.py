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

# $Id: MyAdmin.py,v 1.3 2021/03/18 14:08:22 teus Exp teus $

__license__   = 'RPL-1.5'
__modulename__='$RCSfile: MyAdmin.py,v $'[10:-4]
__version__   = "0." + "$Revision: 1.3 $"[11:-2]

# script to add  and visualize meta info
#    from json admin file into Sensors and TTNtable measurements database table
#    of collect meta info from database Sensors and TTNtable into json format.
#
# the measurement kit may update meta data automatically for sensors, ordinates
# json admin file should be something like:
# Nominatum Open Streetmap is used to search for missing entries
#
# Example and explanation of info for a device node
#{                                        // optional
#"bwlvc-9cd5": {                          // TTN topic id
JsonBeatyPrt = [
     # sorted, (key,example,comment)
     (None,None,"// project and serial are keys in data base to search and store data"),
     ("project","SAN","\t// required project name"),
     ("serial","b4e6d2f94dcc","\t// required serial nr measurement kit"),
     (None,None,None),
     (None,None,"// Sensors table info"),
     ("label","bwlvc-9cd5","\t// optional for ref uses"),
     ("first","28-05-2020","\t// optional first date kit operational"),
     ("comment","MySense V0.5.76","\t// optional usual MySense version"),
     (None,None,"// event and notices methods: via email and/or Slack notices. Comma separated"),
     ("notice","email:sensor <sensor@mail.com>","\t// optional"),
     (None,None,None),
     (None,None,"// sensors types may be overwritten by measurement kit first use"),
     (None,None,"// support for: BME280, BME680, SHT31, SDS011, SPS30, PMS?003i"),
     ("meteo","BME680","\t// optional type of meteo sensor"),
     ("dust","PMSx003","\t// optional type of dust sensor"),
     ("gps","NEO-6","\t// optional type of GPS chip eg NEO-6"),
     ("net","TTN","\t// optional type of connectivity TTN, WIFI"),
     ("description","temp(degrees celsius","\t// ... automatically updated, optional"),
     (None,None,None),
     (None,None,"// measurement kit home information is valid (Sensors table)"),
     ("active",'true',"\t// optional"),
     (None,None,None),
     (None,None,'// measurement kit home location details'),
     (None,None,'// home kit GPS coordinates may be overwritten by first measurements kit'),
     (None,None,'// optional if missing street nr, village will be used to define GPS'),
     (None,None,'// internally only geohash (max precision 10) is used for ordinates.'),
     (None,None,'// deprecated ("GPS",{ "altitude":13, "latitude":51.6040722, "longitude":5.02053}'),
     ("altitude","8","\t// in meters, optional"),
     (None,None,"// GPS is search for via street, village if defined. geohash will be calculated from long/lat ordinates."),
     ("longitude","5.8702053","\t// optional, -180,180 degrees in decimal"),
     ("latitude","51.604740722","\t// optional, -90,90 degrees in decimal"),
     ("geohash","u124ghi7","\t// optional, geohash precision used is max 10"),
     (None,None,"// searched for via Nominated via GPS"),
     ("street","Vletweg 7","\t// optional may need to find GPS"),
     ("village","Oploo","\t// optional may need to find GPS"),
     ("pcode","5481AS","\t// optional, Nominatum search"),
     ("province","Brabant","\t// optional"),
     ("municipality","Oploo","\t// optional, searched for via Nominatum"),
     (None,None,None),
     (None,None,"// TTNtable info"),
     (None,None,"// The Things Network details:"),
     ("TTNactive",'true',"\t// accept data from TTN"),
     ("TTN_id","bwlvc-9cd5","\t// optional overwrites TTN topic id"),
     (None,None,"// TTN keys ABP or OTAA only for administrative/archiving needs"),
     ("DevEui","AAAAB46EF24DC9D5","\t// optional TTN, usualy based on serial"),
     ("NwkSKEY","AC93B59540749288CF75A06084E95550","\t// ABP key optional"),
     ("DevAdd","70B3D57ED000A4D3","\t// ABP optional"),
     (None,None,"// OTAA LoRa keys:"),
     ("AppEui","70B3D57ED000A4D3","\t// optional TTN app id"),
     ("AppSKEY","C93B59540749288CF75A06084E95550E","\t// optional TTN secret key"),
     (None,None,None),
     (None,None,"// data and graphs forwarding details"),
     ("website",'false',"\t// optional, publisize data on website"),
     (None,None,"// valid False: no output to database, None kit is in repair"),
     ("valid",'true',"\t// optional, validate measurements in DB"),
     (None,None,"// sensors.community forwarding"),
     ("luftdaten.info",'false',"\t// optional, forwarding measurements"),
     ("luftdatenID","1234567","\t// optional if dflt kit serial differs"),
     ]
#    }
#}

try:
    import sys
    import MyDB
except ImportError as e:
    sys.exit("FATAL: One of the import modules not found: %s"% e)

# columns needed for meta info per DB table of measurement kit
JsonKeys = {
    "Sensors": [
           "project", "serial", "label", "first", "comment", "notice",
           "description", "sensors", "comment",
           "coordinates", # deprecated
           "longitude", "latitude", "altitude", "geohash",
           "street", "village", "pcode", "province", "municipality", "region",
           "active",
        ],
    "TTNtable": [
           "valid", # previously called active
           "TTN_id", "DevEui", "NwkSKEY", "AppEui", "AppSKEY", "DevAdd",
           "luftdaten.info", "luftdatenID", "TTNactive",
           "website",
        ],
    }
_JsonKeys = None # columns in tables have been checked?
_JsonSkip = ["sensors","coordinates","geohash"]

# detect sensor type from hw description and push it to admin json dict
def HW2Chip(admin,value, verbose=False):
    global _JsonSkip
    chipTypes = {  # types of data producers and communication
        'dust': ['SPS','SDS','PMS',],
        'meteo': ['BME','SHT','DHT',],
        'gps': ['NEO',],  # TIME is implicit
        'net': ['TTN','WIFI',],
    }
    hasOnly = None
    indx = value.find(';hw: ')
    if not indx: hasOnly = True
    if indx < 0: return False
    indx = value[indx+5:]
    try:
        indx = indx[:indx.index(';')]
        hasOnly = False
    except: pass
    indx = indx.split(',')
    rts = False
    for item, types in chipTypes.items():
        for one in types:
          for i in indx:
            if i[:3].lower() == one.lower():
              if not item in _JsonSkip:
                admin[item] = i
                if verbose:
                  sys.stderr.write("    %s: %s (sensor type)\n" % (item,i))
              rts = True
              break
        else: continue
        break
    if not hasOnly: rts = False  # there is more info do not skip description
    return rts

def CheckTables(verbose=False, db=None):
    global _JsonKeys
    if _JsonKeys: return
    if not db: db = MyDB
    if db.Conf['fd'] == None and not db.db_connect():
        db.Conf['log'](__modulename__,'FATAL','Unable to connect to DB')
        raise IOError("Database connection fialure")

    for tbl in JsonKeys.keys():
      cols = []
      rslts = db.db_query("DESCRIBE %s" % tbl, True)
      for col in rslts:
        if str(col[0]) in JsonKeys[tbl]: cols.append(str(col[0]))
      if verbose:
        sys.stderr.write("Deprecated columns in table %s: %s\n" % (tbl, ', '.join(list(set(JsonKeys[tbl]).difference(set(cols)))) ))
      JsonKeys[tbl] = cols
    _JsonKeys = True

#o collect meta info from Sensors and TTNtable for a measurement kit
# returns with dict in admin json style
def getCurInfo(project,serial,db=None, verbose=False):
    global _JsonSkip
    import datetime
    if not db: db = MyDB
    if db.Conf['fd'] == None and not db.db_connect():
        db.Conf['log'](__modulename__,'FATAL','Unable to connect to DB')
        raise IOError("Database connection failure")
    CheckTables(verbose=verbose,db=db)
    Admin = {}; TTN_id = ''
    bools = ['active','website','TTNactive','valid'] # boolean column cell values
    for tbl in sorted(JsonKeys.keys()):
        qry = ', '.join(JsonKeys[tbl])
        add = []
        if 'geohash' in JsonKeys[tbl]:
            # JsonKeys[tbl].remove('geohash')
            if not 'longitude' in JsonKeys[tbl]:
                add = ['longitude','latitude']
                qry += ', longitude, latitude'
            qry = qry.replace('longitude','(IF(ISNULL(geohash),NULL,ST_LongFromGeoHash(geohash)))')
            qry = qry.replace('latitude','(IF(ISNULL(geohash),NULL,ST_LatFromGeoHash(geohash)))')
        Rslt = db.db_query("SELECT %s FROM %s WHERE project = '%s' AND serial = '%s' ORDER BY datum DESC, %s DESC LIMIT 1" % (qry, tbl, project, serial,('active' if tbl == 'Sensors' else 'valid')),True)
        if not Rslt:
          if verbose: sys.stderr.write("Attent: No database values found in table %s  for project %s, serial %s\n" % (tbl,project,serial))
          continue
        if tbl == 'Sensors':
            TTN_id = Rslt[0][JsonKeys[tbl].index('label')]
            if verbose:
              sys.stderr.write('Measurement kit label "%s": label may be overwritten by TTN_id value defined in TTNtable.\n' % str(TTN_id))
        if verbose: sys.stderr.write("Update info for table %s." % tbl)
        for key, value in zip(JsonKeys[tbl]+add,Rslt[0]):
            if value == None and not key in bools: continue
            if key == 'geohash': # this will hide geohash
               if verbose: sys.stderr.write("Skip geohash value = %s\n" % str(value))
               continue
            if type(value) is datetime.datetime:
               value = str(value).replace(' 00:00:00','')
            else: value = str(value) # DB float, int, unicode string, None
            if key in bools and not value is None: # tinyint conversion to bool
                value = True if value else False
            if key == 'TTN_id': TTN_id = value
            if verbose: sys.stderr.write('    %s: %s\n' % (key,str(value)) )
            if key == 'description': # ;hw: will indicate sensor types definitions
                if HW2Chip(Admin,value, verbose=verbose): continue
                # else output description
            if not value == None:
                if not key in _JsonSkip: Admin[key] = value
            elif key == 'valid': Admin[key] = None  # None says in repair
    if not Admin: return {}
    return { TTN_id: Admin }
            
# push info dict into tables of DB: Sensors (Sensor kit location info) and TTN LoRa info
# only used once to ship json info to database
def putNodeInfo(info,db=None, adebug=False):
    import MyGPS
    if not db:
        db = MyDB
        # use default Conf. if defined DBUSER, DBHOST, DBPASS, DB will overwrite
    if db.Conf['fd'] == None and not db.db_connect():
        db.Conf['log'](__modulename__,'FATAL','Unable to connect to DB')
        raise IOError("Database connection fialure")
    for item in ['project','serial']:
        if not item in info.keys():
            db.Conf['log'](__modulename__,'ERROR','Node info has no key item %s: %s' % (item,str(info)))
            return False

    # convert special cases
    from dateutil.parser import parse
    from time import mktime, sleep
    if 'date' in info.keys():
        if not 'first' in info.keys(): info['first'] = info['date']
        elif not 'datum' in info.keys(): info['datum'] = info['date']
    for item in ('first','datum'): # convert human timestamp to POSIX timestamp
        if (item in info.keys()) and (not type(info[item]) is int):
          try:
            info[item] = int(mktime(parse(info[item], dayfirst=True, yearfirst=False).timetuple()))
          except ValueError:
            db.Conf['log'](__modulename__,'ERROR', 'Unable to parse date %s from node info: %s. SKIPPED.' % (info[item],str(info)))
            return False

    # handle home location, search missing info location items
    LocationBackup = {}
    if 'GPS' in info.keys():       # convert GPS to coordinates string
        info['coordinates'] = ["0","0","0"]
        for oord in info['GPS'].keys():
            if oord.lower().find('lon') >= 0:
                info['longitude'] = info['coordinates'][0] = str(info['GPS'][oord]) # longitude
            elif oord.lower().find('lat') >= 0:
                info['latitude'] = info['coordinates'][1] = str(info['GPS'][oord]) # latitude
            elif oord.lower().find('alt') >= 0:
                info['altitude'] = info['coordinates'][2] = str(info['GPS'][oord]) # altitude
        LocationBackup = MyGPS.GeoQuery("%s,%s" % (info['longitude'],info['latitude']))
    elif 'street' in info.keys():
        address = ''
        for item in ['street','village']: # may need more items to improve discrimination
          if item in info.keys():
            address += ', ' + info[item]
          else:
            address = ''; break
        if address: Location =  MyGPS.GeoQuery(address)
    for item in LocationBackup.keys():
        if not item in info.keys(): info[item] = LocationBackup[item]

    # handle sensors description: type, product, unit
    sensors = []; descript = []    # convert sensor types to ;hw: string
    if 'description' in info.keys():
        descript = info['description'].split(';')
    for item in ('dust','meteo','gps','net'):
        try:
          sensors.append(info[item].upper().strip())
          if item == 'gps' and info[item]: sensors.append('TIME')
        except: pass
    if len(sensors):  # add used sensor types into Sensors description
        sensors.sort()
        for i in range(len(descript)-1,-1,-1):
            descript[i] = descript[i].strip()
            if descript[i].find('hw:') >= 0  or not descript[i]:
              del descript[i]
        info['description'] = ';hw: ' + ','.join(sensors)
        if len(descript): info['description'] += ';'+';'.join(descript)

    # sensors.community or Luftdaten access info handling
    if 'luftdaten.info' in info.keys(): # convert to newer handling
        if info['luftdaten.info']:
            info['luftdaten'] = True
            if type(info['luftdaten']) is str: info['luftdatenID'] = info['luftdaten.info']
        else: info['luftdaten'] = False

    # update the info
    # To Do: lock Sensors table while updating "LOCK TABLES Sensors, TTNtable READ LOCAL"
    # export info dict to DB tables update, if table not exists create it
    for table in ['Sensors','TTNtable']:
        if not db.db_table(table): continue
        extra = ''
        if table == 'Sensors':
            # coordinates column is deprecated
            #extra = ', pcode, street, active, coordinates, longitude, latitude, altitude, geohash'
            extra = ', pcode, street, active, geohash, altitude'

        # get latest info from database to check need to update meta and access info
        rts = db.db_query("SELECT UNIX_TIMESTAMP(id)%s FROM %s WHERE project = '%s' AND serial = '%s' ORDER BY %s DESC, datum DESC LIMIT 1" % (extra,table,info['project'],info['serial'],('active' if table == 'Sensors' else 'valid')), True)
        # only for Sensors database table, there is an entry in the Sensors table
        if len(rts) and table == 'Sensors':
            # may need new entry if location changed (use geohash for aproximate)
            try:
              dist = None
              try:
                id = rts[0][0]; active = rts[0][3]
                dist = MyGPS.GPS2Aproximate(info['geohash'],rts[0][4])
                #info['coordinates'] = ','.join([x.rstrip('.0') if x.rstrip('.0') else '0' for x in info['coordinates'].split(',')])
                #dist = MyGPS.GPSdistance(info['coordinates'],rts[0][4])
                if dist and (dist > 118): # locations differ more as 118 meters
                  dist = True
                elif dist != None: dist = False
                else: dist = None
              except: pass
              if dist == None:
                if not rts[0][1]: rts[0][1] = ''
                if not rts[0][2]: rts[0][2] = ''
                # may need to check on geolocation first
                if not 'street' in info.keys():
                  try:
                    address = MyGPS.GPS2Addres([str(info['longitude']),str(info['latitude'])], verbose=adebug)
                    for item in ['street','pcode','village','municipality','province']:
                      if item in address.keys(): info[item] = address[item]
                  except: pass
                if 'pcode' in info.keys() and rts[0][1] != info['pcode']:
                  dist = True
                elif 'street' in info.keys() and rts[0][2][-3:] != info['street'][-3:]:
                  dist = True
                else: dist = False

              if (dist != False) and active: # home location changed
                # deactivate previous entry
                query = "UPDATE Sensors set active = 0 WHERE id = FROM_UNIXTIME(%s)" % id
                if adebug:
                  sys.stderr.write("Could update DB Sensors qry: %s\n" % query)
                else:
                  db.db_query(query, False)
                  flds = ','.join(list(set(db.TableColumns('Sensors')) - set(['street','pcode','village','municipality','region','geohash','altitude','active','datum','id']))) # default active = True
                  query = "INSERT INTO Sensors (%s) SELECT %s FROM Sensors WHERE id = FROM_UNIXTIME(%s)" % (flds, flds, id)
                  db.db_query(query, False)
                  # and copy part of it: no location, active
                  rts = db.db_query("SELECT UNIX_TIMESTAMP(id) FROM %s WHERE project = '%s' AND serial = '%s' ORDER BY active DESC, datum DESC LIMIT 1" % ('Sensors',info['project'],info['serial']), True)
            except: pass  

        if not len(rts): # insert a new row entry
            db.Conf['log'](__modulename__,'ATTENT','Insert new entry in %s table for %s/%s.' % (table,info['project'],info['serial']))
            query = "INSERT INTO %s (datum, project, serial, active) VALUES(now(),'%s','%s',%d)" % (table,info['project'],info['serial'], 1 if 'active' in info.keys() and info['active'] else 0)
            if adebug:
              sys.stderr.write("Could change DB with: %s\n" % query); rts = [(1001,)]
            else:
              sleep(2) # make sure id timestamp is unique
              # TO DO: new entry in TTNtable with default values?
              if not db.db_query(query, False):
                db.Conf['log'](__modulename__,'ERROR','Cannot insert new row in table %s for project %s, serial %s' % (table,info['project'],info['serial']))
                continue
              rts = db.db_query("SELECT UNIX_TIMESTAMP(id) FROM %s WHERE project = '%s' AND serial = '%s' ORDER BY %s DESC, datum DESC LIMIT 1" % (table,info['project'],info['serial'],('active' if table == 'Sensors' else 'valid')), True)

        qry = []
        for item in (set(db.TableColumns(table)) & set(info.keys())) - set(['project','serial','id']):
            if item in ('first','datum'):
                qry.append("%s = FROM_UNIXTIME(%d)" % (item,info[item]))
            #elif item in ['coordinates']:
            #    qry.append("%s = NULL" % item)  # deprecated
            #    continue
            elif type(info[item]) is int:
              qry.append( "%s = %d" % (str(item),info[item]))
            elif type(info[item]) is bool:
              qry.append( "%s = %d" % (str(item), (1 if info[item] else 0)))
            elif type(info[item]) is list:
              qry.append("%s = '%s'" % (str(item),','.join(info[item])))
            elif info[item]: 
              qry.append("%s = '%s'" % (str(item),info[item]))
            else: qry.append("%s = NULL" % str(item))
        if not len(qry): continue
        update = "UPDATE %s SET %s WHERE UNIX_TIMESTAMP(id) = %d" % (table,', '.join(qry),rts[0][0])
        if adebug: sys.stderr.write("Could update DB Sensors qry: %s\n" % update)
        else:
          if not db.db_query(update, False):
            db.Conf['log'](__modulename__,'ERROR','Updating node info (%s) for %s SN %s' % (', '.join(qry),info['project'],info['serial']))
    # To Do: "UNLOCK TABLES"
    return True
    
# get a list of measurement kits which match a pattern by project/serial or label
def getList(pattern,db=None,active=False,label=False):
    if not db: db = MyDB
    if db.Conf['fd'] == None and not db.db_connect():
        db.Conf['log'](__modulename__,'FATAL','Unable to connect to DB')
        raise IOError("Database connection fialure")
    Rts = []
    import re
    ptrn = re.compile(pattern, re.I)
    for one in db.db_query("SELECT CONCAT(project,'_',serial), label FROM Sensors%s" % (' WHERE active' if active else ''),True):
      if label: match = ptrn.match(one[1])
      else: match = ptrn.match(one[0])
      if match and not one[0] in Rts: Rts.append(one[0])
    return Rts

# show difference between two json admin dicts for a device node
def showDifference(prev, updated):
    if not updated: return False
    rts = False
    for node in updated.keys():
        if not node in prev.keys():
          sys.stderr.write("**** New entry: %s\n" % node)
          for item, value in sorted(updated[node].items()):
            sys.stderr.write("    %s: %s\n" % (item, value))
            rts = True
          continue
        sys.stderr.write("---- Updated entry: %s\n" % node)
        for item in list(set(prev[node].keys())|set(updated[node].keys())):
          val1 = None; val2 = None
          if item in prev[node].keys(): val1 = str(prev[node][item])
          if item in updated[node].keys(): val2 = str(updated[node][item])
          if val1 == val2: continue
          sys.stderr.write("  %s: '%15.15s' -> '%s'\n" % (item,val1,val2))
          rts = True
    return rts

# test main loop
if __name__ == '__main__':
   from os import path
   verbose = False
   jsonOut = False
   active = True
   label = False
   showDiff = True
   help = """
   Command: python %s [arg] ...
   --help    | -h       This message
   --verbose | -v       Be more verbose (std err channel)
   --output  | -o       Output json records on stdout in pretty print
   --output=filename    Output json records on file in pretty print
   --all     | -a       Also List not active measurement kits in search
   --label   | -l       Search by label not by PROJECTid_SERIALnr
   --nodiff  | -n       Do not show update json admin diffs (default: show)

   Import meta information from so called json admin file into Sensors and TTNtable
   of measurements database.
   Or if not a file show meta info from meta info tables as json admin.
   In this case use argument <project expresion>_<serial expression>.
   E,g. SAN_123.* (all 12.* serials in project SAN, or .* (all kit info.

   Output json records are in pretty print. Default (None/NULL) database
   values are not defined in the json file.
""" % __modulename__
   argv = []
   for i in range(1,len(sys.argv)):
     if sys.argv[i] in ['--help', '-h']:      # help, how to use CLI
       sys.stderr.write(help)
       sys.stderr.write('Example of json admin record:\n{ "TTN_ID": {\n')
       for key, example, comment in JsonBeatyPrt:
         try:
           if key: sys.stderr.write('    "'+key+'": ')
           if example: sys.stderr.write('"'+example+'",')
           if comment: sys.stderr.write(comment)
           sys.stderr.write("\n")
         except: pass
       sys.stderr.write("\n\tnull }\n")
       exit(0)
     elif sys.argv[i] in ['--verbose', '-v']: # be more verbose
       verbose = True
     elif sys.argv[i][:9] == '--output=': # be more verbose
       jsonOut = sys.argv[i][10:]
     elif sys.argv[i] in ['--output', '-o']:  # output json records
       jsonOut = True
     elif sys.argv[i] in ['--all', '-a']:     # only json Sensors active records
       active = False
     elif sys.argv[i] in ['--nodiff', '-n']:  # show admin json differences on update
       showDiff = False
     elif sys.argv[i] in ['--label', '-l']:  # json records with label search
       label = True
     elif sys.argv[i][0] == '-':             # unsupported option
       sys.exit("Unsupported option %s. Try: %s --help" % (sys.argv[i],sys.argv[0]))
     else: argv.append(sys.argv[i])

   # MyDB.Conf['output'] = True
   # MyDB.Conf['hostname'] = 'localhost'         # host InFlux server
   if not MyDB.Conf['database']:
     MyDB.Conf['database'] = 'luchtmetingen'     # the MySql db for test usage, must exists
   # MyDB.Conf['user'] = 'IoS'                   # user with insert permission of InFlux DB
   # MyDB.Conf['password'] = 'acacadabra'        # DB credential secret to use InFlux DB
   if not verbose: MyDB.Conf['level'] = 'WARNING' # log level less verbose

   output = {}
   for one in argv:
     if path.exists(one):
       # get nodes info from a json file and update node info to DB
       from jsmin import jsmin     # tool to delete comments and compress json
       import json
       try:
         new = {}
         with open(one) as _typeOfJSON:
           sys.stderr.write('Importing nodes from json file %s\n' % sys.argv[1:][0])
           new = jsmin(_typeOfJSON.read())
         if new[0] != '{': new = '{' + new + '}'
         new = new.replace(",}","}") # python style dict to json style
         new = json.loads(new)
       except IOError:
         sys.stderr.write('WARNING No node json file %s found\n' % sys.argv[1:][0])
         continue
       except ValueError as e:
         sys.stderr.write('ERROR Json error in admin nodes file %s: %s\n' % (sys.argv[1:][0],e))
         continue
       # if not MyDB.db_connect():
       #     sys.exit('ERROR Unable to connect to DB via Conf: %s\n' % str(Conf))
       for item in new.items():
         sys.stderr.write('Importing node info for node %s\n' % item[0])
         if not 'TTN_id' in item[1].keys(): item[1]['TTN_id'] = item[0]
         if not 'project' in item[1].keys() or not 'serial' in item[1].keys():
           sys.stderr.write("No project/serial of measurekit labeled as '%s' defined. Skipped." % item[0])
           continue
         prev = {}
         if verbose: sys.stderr.write("Most Recent entry for '%s':\n" % item[0])   
         if showDiff or verbose:
           prev = getCurInfo(item[1]['project'],item[1]['serial'],db=MyDB, verbose=verbose)
         if not putNodeInfo(item[1],db=MyDB):
           sys.stderr.write('ERROR importing node %s info to DB\n' % item[0])
         elif verbose:
           sys.stderr.write("Updated entry for '%s':\n" % item[0])   
         if verbose or jsonOut or showDiff:
           updated = getCurInfo(item[1]['project'],item[1]['serial'],db=MyDB, verbose=verbose)
           if not updated:
             sys.stderr.write("ATTENT: empty json info for %s/%s\n" % (item[1]['project'],item[1]['serial']))
             continue
           if jsonOut: output.update(updated)
           if showDiff and not showDifference(prev,updated):
             try:
               sys.stderr.write("ATTENT: no changes in DB for project %s, serial %s with label %s\n" % (item[1]['project'],item[1]['serial'],item[1]['label']))
             except: pass
           updated = {}
       continue
     else: # information is needed for a measurement(s) kit defined as pattern
       for item in getList(one,db=MyDB,active=active,label=label):
         output.update(getCurInfo(item.split('_')[0],item.split('_')[1],db=MyDB, verbose=verbose))
         if not jsonOut: output = {}

   if output:
     import json
     if type(jsonOut) is str:
       jsonOut = open(jsonOut,'w')
       jsonOut.write(json.dumps(output, indent=2, sort_keys=True))
       jsonOut.close()
     else: # to stdout
       print(json.dumps(output, indent=2, sort_keys=True))
        
