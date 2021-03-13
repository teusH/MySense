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

# $Id: MyAdmin.py,v 1.1 2021/03/13 14:33:28 teus Exp teus $

# script to add meta info from json admin file into Sensors and TTNtable
# measurements database table.
#
# the measurement kit may update meta data automatically for sensors, ordinates
# json admin file should be something like:
# Nominatum Open Streetmap is used to search for missing entries
#{                                        // optional
#"bwlvc-9cd5": {                          // TTN topic id
#    // project and serial are keys in data base to search and store data
#    "project": "SAN",                    // required project name
#    "serial": "b4e6d2f94dcc",            // required serial nr measurement kit
#    "label":"bwlvc-9cd5",                // optional for ref uses
#    "first": "28-05-2020",               // optional first date kit operational
#    "comment": "MySense V0.5.76",        // optional usual MySense version
#    // event and notices methods: via email and/or Slack notices. Comma separated
#    "notice": "email:sensor <sensor@mail.com>", // optional
#
#    // sensors types may be overwritten by measurement kit first use
#    // support for: BME280, BME680, SHT31, SDS011, SPS30, PMS?003
#    "meteo": "BME680", "dust": "PMSx003", "gps": "NEO-6", // optional
#    "description": "hw: abcdefh, automatically updated", // optional
#
#    // The Things Network details:
#    "TTN_id": "bwlvc-9cd5",              // optional overwrites TTN topic id
#    // TTN keys ABP or OTAA only for administrative/archiving needs
#    "DevEui": "AAAAB46EF24DC9D5",        // optional TTN, usualy based on serial
#    "NwkSKEY": "A...", "DevAdd": "A...", // ABP case, optional for TTN ABP use
#    // OTAA LoRa keys
#    "AppEui": "70B3D57ED000A4D3",        // optional TTN app id
#    "AppSKEY": "C93B59540749288CF75A06084E95550E", // optional TTN secret key
#
#    // measurement kit home location details:
#    // home kit GPS coordinates may be overwritten by first measurements kit
#    // optional if missing street nr, village will be used to define GPS
#    // internally only geohash (max precision 10) is used for ordinates.
#    "GPS": { "altitude":18, "latitude":51.604740722, "longitude":5.8702053},
#    // or
#    "altitude":18, "latitude":51.604740722, "longitude":5.8702053,
#    // or "geohash": "u124ghi7",         // geohash precision used is max 10
#    "street": "Vletweg 7",              // optional may need to find GPS
#    "village": "Oploo", "pcode": "5481AS", // optional, Nominatum search
#    "province": "Brabant", "municipality": "Oploo", // optional, Nominatum search
#
#    // data and graphs forwarding details
#    "website": false,                    // optional, publisize data on website
#    "active": false,                     // optional, measurements push in DB
#    "luftdaten.info": false              // optional, forwarding measurements
#    "luftdatenID": "1234567"             // optional if dflt kit serial differs
#    }
#}                                        // optional

modulename='$RCSfile: MyAdmin.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.1 $"[11:-2]

try:
    import sys
    import os
    import datetime
    from time import time
    import MyGPS
except ImportError as e:
    sys.exit("FATAL: One of the import modules not found: %s"% e)

# push info dict into tables of DB: Sensors (Sensor kit location info) and TTN LoRa info
# only used once to ship json info to database
def putNodeInfo(info,db=None, adebug=False):
    if not hasattr(putNodeInfo,"DB"):
        import MyDB    # to di: make MyDB a python class
        putNodeInfo.DB = MyDB
        # use default Conf. if defined DBUSER, DBHOST, DBPASS, DB will overwrite
        MyDB.Conf['output'] = True
        MyDB.Conf['hostname'] = 'localhost'         # host InFlux server
        MyDB.Conf['database'] = 'luchtmetingen'     # the MySql db for test usage, must exists
        MyDB.Conf['user'] = 'IoS'                   # user with insert permission of InFlux DB
        MyDB.Conf['password'] = 'acacadabra'        # DB credential secret to use InFlux DB
    if not db:
        db = putNodeInfo.DB
    # if db is None: raise ValueError("No dabase access routines defined")
    if db.Conf['fd'] == None and not db.db_connect():
        db.Conf['log'](modulename,'FATAL','Unable to connect to DB')
        exit(1)
    for item in ['project','serial']:
        if not item in info.keys():
            db.Conf['log'](modulename,'ERROR','Node info has no key item %s: %s' % (item,str(info)))
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
            db.Conf['log'](modulename,'ERROR', 'Unable to parse date %s from node info: %s. SKIPPED.' % (info[item],str(info)))
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
    for item in ('dust','meteo','gps'):
        try:
          sensors.append(info[item].upper().strip())
          if item == 'gps' and info[item]: sensors.append('TIME')
        except: pass
        sensors.sort()
    if len(sensors):
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
        rts = db.db_query("SELECT UNIX_TIMESTAMP(id)%s FROM %s WHERE project = '%s' AND serial = '%s' ORDER BY active DESC, datum DESC LIMIT 1" % (extra,table,info['project'],info['serial']), True)
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
                  print("Could update DB Sensors qry: %s" % query)
                else:
                  db.db_query(query, False)
                  flds = ','.join(list(set(db.TableColumns('Sensors')) - set(['street','pcode','village','municipality','region','geohash','altitude','active','datum','id']))) # default active = True
                  query = "INSERT INTO Sensors (%s) SELECT %s FROM Sensors WHERE id = FROM_UNIXTIME(%s)" % (flds, flds, id)
                  db.db_query(query, False)
                  # and copy part of it: no location, active
                  rts = db.db_query("SELECT UNIX_TIMESTAMP(id) FROM %s WHERE project = '%s' AND serial = '%s' ORDER BY active DESC, datum DESC LIMIT 1" % ('Sensors',info['project'],info['serial']), True)
            except: pass  

        if not len(rts): # insert a new row entry
            db.Conf['log'](modulename,'ATTENT','Insert new entry in %s table for %s/%s.' % (table,info['project'],info['serial']))
            query = "INSERT INTO %s (datum, project, serial, active) VALUES(now(),'%s','%s',%d)" % (table,info['project'],info['serial'], 1 if 'active' in info.keys() and info['active'] else 0)
            if adebug:
              print("Could change DB with: %s" % query); rts = [(1001,)]
            else:
              sleep(2) # make sure id timestamp is unique
              # TO DO: new entry in TTNtable with default values?
              if not db.db_query(query, False):
                db.Conf['log'](modulename,'ERROR','Cannot insert new row in table %s for project %s, serial %s' % (table,info['project'],info['serial']))
                continue
              rts = db.db_query("SELECT UNIX_TIMESTAMP(id) FROM %s WHERE project = '%s' AND serial = '%s' ORDER BY active DESC, datum DESC LIMIT 1" % (table,info['project'],info['serial']), True)

        qry = []
        for item in (set(db.TableColumns(table)) & set(info.keys())) - set(['project','serial','id']):
            if item in ('first','datum'):
                qry.append("%s = FROM_UNIXTIME(%d)" % (item,info[item]))
            #elif item in ['coordinates']:
            #    qry.append("%s = NULL" % item)  # deprecated
            #    continue
            elif type(info[item]) is int:
              qry.append( "%s = %d" % (item,info[item]))
            elif type(info[item]) is bool:
              qry.append( "%s = %d" % (item, (1 if info[item] else 0)))
            elif info[item]: 
              qry.append("%s = '%s'" % (item,info[item]))
            else: qry.append("%s = NULL" % item)
        if not len(qry): continue
        update = "UPDATE %s SET %s WHERE UNIX_TIMESTAMP(id) = %d" % (table,', '.join(qry),rts[0][0])
        if adebug: print("Could update DB Sensors qry: %s" % update)
        else:
          if not db.db_query(update, False):
            db.Conf['log'](modulename,'ERROR','Updating node info (%s) for %s SN %s' % (', '.join(qry),info['project'],info['serial']))
    # To Do: "UNLOCK TABLES"
    return True
    
# test main loop
if __name__ == '__main__':
    from time import sleep
    if not len(sys.argv) > 1: exit(0)

    # get nodes info from a json file and update node info to DB
    if  sys.argv[1:][0] != 'test':
        from jsmin import jsmin     # tool to delete comments and compress json
        import json
        try:
            new = {}
            with open(sys.argv[1:][0]) as _typeOfJSON:
                print('Importing nodes from json file %s' % sys.argv[1:][0])
                new = jsmin(_typeOfJSON.read())
            if new[0] != '{': new = '{' + new + '}'
            new = new.replace(",}","}") # python style dict to json style
            new = json.loads(new)
        except IOError:
            print('WARNING No node json file %s found' % sys.argv[1:][0])
            exit(1)
        except ValueError as e:
            print('ERROR Json error in admin nodes file %s: %s' % (sys.argv[1:][0],e))
            exit(1)
        # if not MyDB.db_connect():
        #     print('ERROR Unable to connect to DB via Conf: %s' % str(Conf))
        #     exit(1)
        for item in new.items():
            print('Importing node info for node %s' % item[0])
            if not 'TTN_id' in item[1].keys(): item[1]['TTN_id'] = item[0]
            if not putNodeInfo(item[1]):
                print('ERROR importing node %s info to DB' % item[0])
        exit(0)

    print("TEST modus with test measurement data.")

    for i in range(1,len(sys.argv)):
        if sys.argv[i] == 'TTN':
            print(Topic2IDs("applicaties/gtl-kipster-k1"))
            continue
        if sys.argv[i] == 'Sensors':
            print(getNodeFields(0,['street','municipality'], project="KIP", serial="788d27294ac5"))
            print(getNodeFields(0,['TTN_id','datum'], table='TTNtable', project="KIP", serial="788d27294ac5"))
            continue
    
