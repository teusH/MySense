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

# $Id: MyDB.py,v 3.21 2020/05/29 19:26:25 teus Exp teus $

# TO DO: write to file or cache
# reminder: MySQL is able to sync tables with other MySQL servers

""" Publish measurements to MySQL database
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyDB.py,v $'[10:-4]
__version__ = "0." + "$Revision: 3.21 $"[11:-2]

try:
    import sys
    import os
    import mysql
    import mysql.connector
    import datetime
    from time import time
except ImportError as e:
    sys.exit("FATAL: One of the import modules not found: %s"% e)

# configurable options
__options__ = ['output','hostname','port','database','user','password']

Conf = {
    'output': False,
    'hostname': 'localhost', # host MySQL server
    'user': None,        # user with insert permission of MySQL DB
    'password': None,    # DB credential secret to use MySQL DB
    'database': None,    # MySQL database name
    'port': 3306,        # default mysql port number
    'fd': None,          # have sent to db: current fd descriptor, 0 on IO error
    'log': None,         # MyLogger log routiune
    'omit' : ['time','geolocation','coordinates','version','gps','meteo','dust','gwlocation','event','value']        # fields not archived
}
# ========================================================
# write data directly to a database
# ========================================================
# create table <ProjectID_Serial>, record columns,
#       registration Sensors table on the fly
def attributes(**t):
    global Conf
    Conf.update(t)

# connect to db and keep connection as long as possible
def db_connect(net = { 'module': True, 'connected': True }):
    """ Connect to MYsql database and save filehandler """
    global Conf
    if not Conf['log']:
        import MyLogger
        Conf['log'] = MyLogger.log
    if not 'fd' in Conf.keys(): Conf['fd'] = None
    if not 'last' in Conf.keys():
        Conf['waiting'] = 5 * 30 ; Conf['last'] = 0 ; Conf['waitCnt'] = 0
    if not 'net' in Conf.keys(): Conf['net'] = net
    if (Conf['fd'] == None) or (not Conf['fd']):
        # get DBUSER, DBHOST, DBPASS from process environment if present
        for credit in ['hostname','user','password']:
            if not credit in Conf.keys():
                Conf[credit] = None
            try:
                Conf[credit] = os.getenv('DB'+credit[0:4].upper(),Conf[credit])
            except:
                pass
        Conf['log'](modulename,'INFO','Using database %s on host %s, user %s credits.' % (Conf['database'],Conf['hostname'],Conf['user']))
        if (Conf['hostname'] != 'localhost') and ((not net['module']) or (not net['connected'])):
            Conf['log'](modulename,'ERROR',"Access database %s / %s."  % (Conf['hostname'], Conf['database']))      
            Conf['output'] = False
            return False
        for M in ('user','password','hostname','database'):
            if (not M in Conf.keys()) or not Conf[M]:
                Conf['log'](modulename,'ERROR',"Define DB details and credentials.")
                Conf['output'] = False
                return False
        if (Conf['fd'] != None) and (not Conf['fd']):
            if ('waiting' in Conf.keys()) and ((Conf['waiting']+Conf['last']) >= time()):
                raise IOError
                return False
        try:
            Conf['fd'] = mysql.connector.connect(
                charset='utf8',
                user=Conf['user'],
                password=Conf['password'],
                host=Conf['hostname'],
                port=Conf['port'],
                database=Conf['database'],
                connection_timeout=2*60)
            Conf['last'] = 0 ; Conf['waiting'] = 5 * 30 ; Conf['waitCnt'] = 0
            return True
        except IOError:
            Conf['last'] = time() ; Conf['fd'] = 0 ; Conf['waitCnt'] += 1
            if not (Conf['waitCnt'] % 5): Conf['waiting'] *= 2
            raise IOError
        except:
            Conf['output'] = False; del Conf['fd']
            Conf['log'](modulename,'ERROR',"MySQL Connection failure type: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
            return False
    else:
        return Conf['output']

# create table Sensors
def CreateSensors():
    try:
        if db_query("""ALTER TABLE Sensors
          ADD COLUMN coordinates VARCHAR(30) DEFAULT NULL COMMENT 'latitude,longitude[,altitude]',
          ADD COLUMN label VARCHAR(50) DEFAULT NULL,
          ADD COLUMN sensors VARCHAR(192) DEFAULT NULL COMMENT 'sensor types',
          ADD COLUMN description VARCHAR(256) DEFAULT NULL COMMENT 'sensor value types',
          ADD COLUMN comment VARCHAR(128) DEFAULT NULL,
          ADD COLUMN first DATETIME DEFAULT '2001-01-01 00:00:00' COMMENT 'installation date',
          ADD COLUMN active BOOL DEFAULT 1,
          ADD COLUMN project VARCHAR(10) DEFAULT NULL,
          ADD COLUMN serial VARCHAR(15) DEFAULT NULL,
          ADD COLUMN notice VARCHAR(128) DEFAULT NULL,
          ADD COLUMN street VARCHAR(50) DEFAULT NULL,
          ADD COLUMN village VARCHAR(50) DEFAULT NULL,
          ADD COLUMN pcode VARCHAR(10) DEFAULT NULL,
          ADD COLUMN province VARCHAR(50) DEFAULT NULL,
          ADD COLUMN municipality VARCHAR(50) DEFAULT NULL,
          ADD COLUMN region VARCHAR(20) DEFAULT NULL,
          ADD COLUMN last_check DATETIME DEFAULT CURRENT_TIMESTAMP,
          CHANGE datum datum datetime DEFAULT current_timestamp ON UPDATE current_timestamp
        """, False):
            return True
    except: pass
    return False


# registrate the sensor to the Sensors table and update location/activity
serials = {}     # remember serials of sensor kits checked in into table Sensors
def db_registrate(ident, adebug=False):
    """ create or update identification inf to Sensors table in database """
    global Conf
    try: tableID = '%s_%s' % (ident['project'],ident['serial'])
    except:
        Conf['log'](modulename,'DEBUG','project or serial missing in identification record')
        return False
    try: # new identity?
        if ident['count'] == 1: del serials[tableID]
    except: pass
    if tableID in serials.keys(): return True
    if len(ident['fields']) == 0: return False

    if not db_table('Sensors') and not CreateSensors():
        Conf['log'](modulename,'FATAL','Unable to access Sensors table in DB')
        exit(1)

    def db_WhereAmI(ident,desc=True,adebug=False):
        query = []
        # [str(r[0]) for r in db_query("SELECT column_name FROM information_schema.columns WHERE  table_name = 'Sensors' AND table_schema = '%s'" % Conf['database'],True)]
        for fld in ("label","description","street","village","province","municipality","region","coordinates"):
            if (fld == "description") and (fld in ident.keys()):
                if (not desc): continue
                if ident[fld].find('DFLTs') >= 0: continue   # do not update
            if (fld in ident.keys()) and (ident[fld] != None):
                query.append("%s = '%s'" % (fld,ident[fld]))
        if not len(query): return
        try:
            update = "UPDATE Sensors SET %s WHERE project = '%s' AND serial = '%s' AND active" % (','.join(query),ident['project'],ident['serial'])
            if adebug: print("Could update DB table Sensors qry: %s" % update)
            else:
              db_query(update, False)
        except: pass
        return

    if not db_table(tableID): return False
    serials[tableID] = True
    # serials[tableID] = {}       # remember we know this one
    # for item in ['fields','units','calibrations','types']: # no need to maintain this one
    #     try: serials[tableID][item] = ident[item]
    #     except: pass

    # may need to update in Sensors table from ident:
    # first, coordinates, description ?
    mayUpdate = ['first','coordinates','active','sensors']
    # do not update guessed hardware
    if ('description' in ident.keys()) and (ident['description'].find('DFLTs') < 0):
        mayUpdate.append('description')
    # else: del ident['description']
    Rslt = getNodeFields(None,mayUpdate,table='Sensors',project=ident['project'],serial=ident['serial'])
    if not type(Rslt) is dict: return True
    # collect description of sensors if new in this run
    gotIts = [] # data fields to store in DB sensor table on column sensors
    fld_units = ''
    if ('fields' in ident.keys()) and ('units' in ident.keys()):
        for i in range(len(ident['fields'])):
            if (ident['fields'][i] in Conf['omit']) or (ident['fields'][i] in gotIts):
                continue
            gotIts.append(ident['fields'][i])
            if len(fld_units): fld_units += ','
            fld_units += "%s(%s)" %(ident['fields'][i],ident['units'][i])
    ident['sensors'] = (fld_units if len(fld_units) else 'NULL')
    if ('geolocation' in ident.keys()) and (not 'coordinates' in ident.keys()): # naming clash
        ident['coordinates'] = ','.join([x.rstrip('.0') if x.rstrip('.0') else '0' for x in ident['geolocation'].split(',')])

    for item in mayUpdate:
        try:
            if not item in Rslt.keys(): Rslt[item] = ident[item]
            elif Rslt[item] != ident[item]: Rslt[item] = ident[item]
            else: del Rslt[item]
        except: pass

    # Sensors entry diffs from ident info on keys
    mayUpdate = []; values = []
    for item in Rslt.keys():
        if len(str(Rslt[item])):
            mayUpdate.append(item); values.append(Rslt[item])
    if len(mayUpdate):
        mayUpdate.append('last_check'); values.append('now()')
        setNodeFields(None,mayUpdate,values,table='Sensors',project=ident['project'],serial=ident['serial'], adebug=adebug)
        Conf['log'](modulename,'INFO',"Updated registration proj %s: SN %s in database table 'Sensors' with %s." % (ident['project'],ident['serial'],str(values)))
        # Conf['log'](modulename,'INFO',"Updated registration proj %s: SN %s in database table 'Sensors'." % (ident['project'],ident['serial']))
    return True

# do a query
Retry = False
# returns either True/False or an array of tuples
def db_query(query,answer):
    """ communicate in sql to database """
    global Conf, Retry
    if Conf['fd'] == None and not db_connect():
        Conf['log'](modulename,'FATAL','Unable to connect to DB')
        exit(1)
    # testCnt = 0 # just for testing connectivity failures
    # if testCnt > 0: raise IOError
    Conf['log'](modulename,'DEBUG',"MySQL query: %s" % query)
    try:
        c = Conf['fd'].cursor()
        c.execute (query)
        if answer:
            return c.fetchall()     
        else:
            Conf['fd'].commit()
    except IOError:
        raise IOError
    except:
        Conf['log'](modulename,'ERROR',"Failure type: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
        Conf['log'](modulename,'ERROR',"On query: %s" % query)
        # try once to reconnect
        try:
            Conf['fd'].close
            Conf['fd'] = None
            db_connect(Conf['net'])
        except:
            Conf['log'](modulename,'ERROR','Failed to reconnect to MySQL DB.')
            return False
        if Retry:
            return False
        Retry = True
        Conf['log'](modulename,'INFO',"Retry the query")
        if db_query(query,answer):
            Retry = False
            return True
        Conf['log'](modulename,'ERROR','Failed to redo query.')
        return False
    return True

# create LoRa info table
def CreateLoRaTable(table):
    if not db_query("""CREATE TABLE %s (
        id datetime UNIQUE  DEFAULT CURRENT_TIMESTAMP COMMENT 'date/time creation',
        project VARCHAR(16) DEFAULT NULL COMMENT 'project id',
        serial  VARCHAR(16) DEFAULT NULL COMMENT 'serial kit hex',
        TTN_id  VARCHAR(32) DEFAULT NULL COMMENT 'TTN device topic name',
        active  BOOLEAN     DEFAULT 0    COMMENT 'DB values enabled',
        luftdatenID VARCHAR(16) DEFAULT NULL COMMENT 'if null use TTN-serial',
        luftdaten BOOLEAN   DEFAULT 0    COMMENT 'POST to luftdaten',
        datum   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP COMMENT 'last time changed',
        DevAdd  VARCHAR(10) DEFAULT NULL COMMENT 'ABP device id Hex',
        NwkSKEY VARCHAR(32) DEFAULT NULL COMMENT 'ABP network secret key Hex',
        AppEui  VARCHAR(16) DEFAULT NULL COMMENT 'OTAA application id TTN',
        DevEui  VARCHAR(16) DEFAULT NULL COMMENT 'OTAA device eui Hex',
        AppSKEY VARCHAR(32) DEFAULT NULL COMMENT 'OTAA/ABP secret key Hex',
        UNIQUE kit_id (project,serial)
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='TTN info input table, output'""" % table,False):
        Conf['log'](modulename,'ERROR', 'Failed to create LoRa node table %s' % table)
        return False
    return True

# table columns cache for global tables eg Sensors, TTNtable
def TableColumns(table):
    global Conf
    if not table in Conf.keys(): return []
    if not 'columns' in TableColumns.__dict__: TableColumns.columns = {}
    if not table in TableColumns.columns.keys():
        TableColumns.columns[table] = [str(r[0]) for r in db_query("DESCRIBE %s" % table, True)]
    return TableColumns.columns[table]

# push info dict into tables of DB: Sensors (Sensor kit location info) and TTN LoRa info
# only used once to ship json info to database
def putNodeInfo(info,adebug=False):
    global Conf
    LAT = 0
    LON = 1
    ALT = 2
    def GPSdistance(gps1,gps2): # returns None on a not valid GPS oordinate
        from math import sin, cos, radians, pow, sqrt, atan2
        def str2list(val):
            if type(val) is list:
                rts = [float(x) for x in val]
            elif val == None: return None
            else: rts = [float(x) for x in val.split(',')]
            if len(rts) < 2: return None
            if rts[0] < 0.1 or rts[1] < 0.1: return None
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
    
    if Conf['fd'] == None and not db_connect():
        Conf['log'](modulename,'FATAL','Unable to connect to DB')
        exit(1)
    for item in ['project','serial']:
        if not item in info.keys():
            Conf['log'](modulename,'ERROR','Node info has no key item %s: %s' % (item,str(info)))
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
            Conf['log'](modulename,'ERROR', 'Unable to parse date %s from node info: %s. SKIPPED.' % (info[item],str(info)))
            return False
    if 'GPS' in info.keys():       # convert GPS to coordinates string
        info['coordinates'] = ["0","0","0"]
        for oord in info['GPS'].keys():
            if oord.lower().find('lon') >= 0:
                info['coordinates'][LON] = str(info['GPS'][oord])
            elif oord.lower().find('lat') >= 0:
                info['coordinates'][LAT] = str(info['GPS'][oord])
            elif oord.lower().find('alt') >= 0:
                info['coordinates'][ALT] = str(info['GPS'][oord])
        info['coordinates'] = ','.join([x.rstrip('.0') if x.rstrip('.0') else '0' for x in info['coordinates']])

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

    if 'luftdaten.info' in info.keys(): # convert to newer handling
        if info['luftdaten.info']:
            info['luftdaten'] = True
            if type(info['luftdaten']) is str: info['luftdatenID'] = info['luftdaten.info']
        else: info['luftdaten'] = False
    # for item in ['pcode','street','coordinates','region']:
    #     if not item in info.keys(): info[item] = ''

    # To Do: lock Sensors table while updating "LOCK TABLES Sensors, TTNtable READ LOCAL"
    # export info dict to DB tables update, if table not exists create it
    for table in ['Sensors','TTNtable']:
        if not db_table(table): continue
        extra = ''
        if table == 'Sensors':
            extra = ', pcode, street, active, coordinates'
        rts = db_query("SELECT UNIX_TIMESTAMP(id)%s FROM %s WHERE project = '%s' AND serial = '%s' ORDER BY active DESC, datum DESC LIMIT 1" % (extra,table,info['project'],info['serial']), True)
        if len(rts) and extra: # may need new entry if location changed
            try:
              dist = None
              try:
                id = rts[0][0]; active = rts[0][3]
                info['coordinates'] = ','.join([x.rstrip('.0') if x.rstrip('.0') else '0' for x in info['coordinates'].split(',')])
                dist = GPSdistance(info['coordinates'],rts[0][4])
                if adebug: print("Distance %s - %s: %d" % (info['coordinates'],rts[0][4],dist))
                if dist and (50 < dist < 100000): # locations differ more as 50 meters
                  dist = True
                elif dist != None: dist = False
                # else: dist = None
              except: pass
              if dist == None:
                if not rts[0][1]: rts[0][1] = ''
                if not rts[0][2]: rts[0][2] = ''
                # may need to check on geolocation first
                if 'pcode' in info.keys() and rts[0][1] != info['pcode']:
                  dist = True
                elif 'street' in info.keys() and rts[0][2][-3:] != info['street'][-3:]:
                  dist = True
                else: dist = False
              if (dist != False) and active: # deactivate
                query = "UPDATE Sensors set active = 0 WHERE id = FROM_UNIXTIME(%s)" % id
                if adebug:
                  print("Could update DB Sensors qry: %s" % query)
                else:
                  db_query(query, False)
                  flds = ','.join(list(set(TableColumns('Sensors')) - set(['street','pcode','village','municipality','region','coordinates','active','datum','id']))) # default active = True
                  query = "INSERT INTO Sensors (%s) SELECT %s FROM Sensors WHERE id = FROM_UNIXTIME(%s)" % (flds, flds, id)
                  db_query(query, False)
                  # and copy part of it: no location, active
                  rts = db_query("SELECT UNIX_TIMESTAMP(id) FROM %s WHERE project = '%s' AND serial = '%s' ORDER BY active DESC, datum DESC LIMIT 1" % ('Sensors',info['project'],info['serial']), True)
            except: pass  
        if not len(rts): # insert a new row entry
            Conf['log'](modulename,'ATTENT','Insert new entry in %s table for %s/%s.' % (table,info['project'],info['serial']))
            query = "INSERT INTO %s (datum, project, serial, active) VALUES(now(),'%s','%s',%d)" % (table,info['project'],info['serial'], 1 if 'active' in info.keys() and info['active'] else 0)
            if adebug:
              print("Could change DB with: %s" % query); rts = [(1001,)]
            else:
              sleep(2) # make sure id timestamp is unique
              # TO DO: new entry in TTNtable with default values?
              if not db_query(query, False):
                Conf['log'](modulename,'ERROR','Cannot insert new row in table %s for project %s, serial %s' % (table,info['project'],info['serial']))
                continue
              rts = db_query("SELECT UNIX_TIMESTAMP(id) FROM %s WHERE project = '%s' AND serial = '%s' ORDER BY active DESC, datum DESC LIMIT 1" % (table,info['project'],info['serial']), True)
        qry = []
        for item in (set(TableColumns(table)) & set(info.keys())) - set(['project','serial','id']):
            if item in ('first','datum'):
                qry.append("%s = FROM_UNIXTIME(%d)" % (item,info[item]))
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
          if not db_query(update, False):
            Conf['log'](modulename,'ERROR','Updating node info (%s) for %s SN %s' % (', '.join(qry),info['project'],info['serial']))
    # To Do: "UNLOCK TABLES"
    return True
    
# get TTN_id's with changes later then timestamp in tables Sensors and TTNtable
def UpdatedIDs(timestamp, field='TTN_id', table='TTNtable'):
    global Conf
    if Conf['fd'] == None and not db_connect():
        Conf['log'](modulename,'FATAL','Unable to connect to DB')
        exit(1)
    if not db_table('TTNtable') or not db_table('Sensors'):
        Conf['log'](modulename,'FATAL','Missing Sensors or TTNtable in DB')
        exit(1)
    rts = []
    try:
        qry = db_query('SELECT DISTINCT project, serial FROM %s WHERE UNIX_TIMESTAMP(datum) > %d' % (('Sensors' if table == 'TTNtable' else 'Sensors'),int(timestamp)), True)
        sql = []
        for one in qry:
            sql.append("(project = '%s' and serial = '%s')" % (one[0],one[1]))
        sql = ' or '.join(sql)+' or '        
        qry = db_query('SELECT DISTINCT %s FROM %s WHERE %s UNIX_TIMESTAMP(datum) > %d' % (field,table,int(timestamp)), True)
        for one in qry: rts.append(one[0])
    except: pass
    return rts

# get TTNtable id for a node
def Topic2IDs(topic, active=None):
    global Conf
    if Conf['fd'] == None and not db_connect():
        Conf['log'](modulename,'FATAL','Unable to connect to DB')
        exit(1)
    if not db_table('TTNtable') or not db_table('Sensors'):
        Conf['log'](modulename,'FATAL','Missing Sensors or TTNtable in DB')
        exit(1)
    if active == None: active = ''
    elif active: active = 'AND TTNtable.active'
    else: active = 'AND not TTNtable.active'
    indx = 0
    try: indx = topic.index('/')+1
    except: pass
    # [SensorsTbl id,TTNtable id,POSIX time last measurement,measurements DB table]
    rts = [0,0,0,'']
    try:
        qry = db_query("SELECT UNIX_TIMESTAMP(id) FROM TTNtable WHERE TTN_id = '%s' %s ORDER BY id DESC LIMIT 1" % (topic[indx:],active), True)
        if len(qry) and qry[0][0]:
            rts[1] = qry[0][0]
            qry = db_query("SELECT UNIX_TIMESTAMP(Sensors.id), concat(TTNtable.project,'_',TTNtable.serial) FROM Sensors, TTNtable WHERE Sensors.project = TTNtable.project AND Sensors.serial = TTNtable.serial AND UNIX_TIMESTAMP(TTNtable.id) = %d %s ORDER BY Sensors.datum DESC, Sensors.active DESC LIMIT 1" % (rts[1],active), True)
            if len(qry) and qry[0][0]: rts[0] = qry[0][0]
            if len(qry) and len(qry[0][1]) and db_table(qry[0][1],create=False): # last datum measurements
                qry = db_query("SELECT UNIX_TIMESTAMP(datum),'%s' FROM %s ORDER BY datum DESC LIMIT 1" % (qry[0][1],qry[0][1]), True)
                if len(qry) and qry[0][0]:
                    rts[2] = qry[0][0]
                    rts[3] = qry[0][1]
    except: pass
    # UNIX timestamp Sensors id, UNIX timestamp TTNtable id, UNIX timestamp last measurement
    return tuple(rts)

# get a field/column value from a table. Fields maybe (prefeable) be a list
def getNodeFields(id,fields,table='Sensors',project=None,serial=None):
    if project and serial:
        try:
            qry = db_query("SELECT UNIX_TIMESTAMP(id) FROM %s WHERE project = '%s' AND serial = '%s' AND active ORDER BY active DESC, datum DESC LIMIT 1" % (table,project,serial), True)
        except: pass
        if not len(qry): return None
        id = qry[0][0]
    if (type(fields) is str) and (fields == '*'): # wild card: all available
        fields = TableColumns(table)
    else: 
        if not type(fields) is list:
            fields = fields.split(',')
        for item in fields:
            item = item.strip()
            if not item in TableColumns(table):
                raise ValueError("DB table %s has no column %s" % (table,item))
    values = []
    for i in range(0,len(fields)):
        if fields[i] in ['id','datum','first','last_check']: values.append('UNIX_TIMESTAMP(%s)' % fields[i])
        else: values.append(fields[i])
    qry = db_query("SELECT %s FROM %s WHERE UNIX_TIMESTAMP(id) = %d LIMIT 1" % (','.join(values),table,id),True)
    if not len(qry):
       return {}
       # raise ValueError("No value for field %s in table %s found." % (','.join(fields),table))
    elif len(qry[0]) == 1: return qry[0][0]
    else:
        rts = {}
        for i in range(0,len(fields)): # check for Null, bool, number ???
            if qry[0][i] != None:
                rts[fields[i]] = qry[0][i]
        return rts

# update a list of fields and values in a DB table
def setNodeFields(id,fields,values,table='Sensors',project=None,serial=None,adebug=False):
    if project and serial:
        try:
            qry = db_query("SELECT UNIX_TIMESTAMP(id) FROM %s WHERE project = '%s' AND serial = '%s' AND active ORDER BY datum DESC LIMIT 1" % (table,project,serial), True)
        except: pass
        if not len(qry): return None
        id = qry[0][0]
    if not type(fields) is list: fields = fields.split(',')
    if not type(values) is list: values = fields.split(',')
    if len(fields) != len(values):
        raise ValueError("Set fields/values not same size for table %s." % table)
    import re
    Exp = re.compile('^([0-9]+(\.[0-9]+)?$|(FROM_UNIXTIME|from_unixtime|now|NOW)\(.*\))', re.I)
    qry = []
    for i in range(len(values)):
        if not fields[i] in TableColumns(table):
            Conf['log'](modulename,'ERROR','Set field %s not in table %s. SKIPPED.' % (fields[i],table))
            continue
        if type(values[i]) is bool: values[i] = ('1' if values[i] else '0')
        elif values[i] == None: values[i] = 'NULL'
        elif not Exp.match(values[i]): values[i] = "'%s'" % values[i]
        qry.append('%s = %s' % (fields[i],values[i]))
    if not len(qry): return True
    try:
        update = 'UPDATE %s SET %s WHERE UNIX_TIMESTAMP(id) = %d' % (table, ', '.join(qry), id)
        if adebug:
          print("Could update DB with: %s" % update); return True
        else:
          return(db_query('UPDATE %s SET %s WHERE UNIX_TIMESTAMP(id) = %d' % (table, ', '.join(qry), id),False))
    except Exception as e:
        Conf['log'](modulename,'ERROR','Unable to update table %s. Error %s.' % (table,str(e)))
        return False

# check if table exists if not create it
def db_table(table,create=True):
    """ check if table exists in the database if not create it """
    global Conf
    if (not 'fd' in Conf.keys()) and not Conf['fd']:
        try: db_connect()
        except:
            Conf['log'](modulename,'FATAL','No MySQL connection available')
            return False
    if (table) in Conf.keys():
        return True
    if table in [str(r[0]) for r in db_query("SHOW TABLES",True)]:
        Conf[table] = True
        return True
    if not create: return False
    # create database: CREATE DATABASE  IF NOT EXISTS mydb; by super user
    if table in ('Sensors'):
        comment = 'Collection of sensor kits and locations'
        table_name = table
    elif table == 'TTNtable':
        Conf[table] = CreateLoRaTable(table); return Conf[table]
    if not db_query("""CREATE TABLE %s (
        id TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            COMMENT 'date/time latest change',
        datum datetime UNIQUE default NULL
            COMMENT 'date/time measurement'
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1
            COMMENT='sensor table created at %s'""" % (table,datetime.datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M")),False):
        Conf[table] = False
        Conf['log'](modulename,'ERROR',"Unable to create sensor table %s in database." % table)
    else:
        Conf['log'](modulename,'ATTENT',"Created table %s" % table)
    Conf[table] = True
    return Conf[table]

ErrorCnt = 0
def publish(**args):
    """ add records to the database,
        on the first update table Sensors with ident info """
    global Conf, ErrorCnt
    if (not 'output' in Conf.keys()) or (not Conf['output']):
        return
    for key in ['data','internet','ident']:
        if not key in args.keys():
            Conf['log'](modulename,'FATAL',"Publish call missing argument %s." % key)

    # translate MySense field names into MySQL column field names
    # TO DO: get the translation table from the MySense.conf file
    def db_name(my_name):
        DBnames = {
            'rh': 'rv',
            'humidity': 'rv',
            'pa': 'luchtdruk',  # deprecated
            'hpa': 'luchtdruk',
            'pressure': 'luchtdruk',
            'geo': 'geolocation',
            'wd':  'wr',
            'temperature': 'temp',
        }
        if my_name in DBnames.keys(): return DBnames[my_name]
        return my_name

    # check if fields in table exists if not add them
    def db_fields(my_ident):
        global Conf, ErrorCnt
        table = my_ident['project']+'_'+my_ident['serial']
        if not 'fields' in Conf.keys(): Conf['fields'] = {}
        missing = False
        if table in Conf['fields'].keys():
            for fld in Conf['fields'][table]:
                if not fld in my_ident['fields']: missing = True
        else: missing = True
        if not missing:
            return True
        Sensor_fields = {
            'geo':         "VARCHAR(25) default NULL",
            'TTNversion':  "VARCHAR(15) default NULL",
            'pa':          "INT(11) default NULL",
            'hpa':         "INT(11) default NULL",
            'wd':          "SMALLINT(4) default NULL",
            'pm1':         "DECIMAL(9,2) default NULL",
            'pm1_atm':     "DECIMAL(9,2) default NULL",
            'pm1_cnt':     "DECIMAL(9,2) default NULL",
            'pm4_cnt':     "DECIMAL(9,2) default NULL",
            'pm5_cnt':     "DECIMAL(9,2) default NULL",
            'pm03_cnt':    "DECIMAL(9,2) default NULL",
            'pm05_cnt':    "DECIMAL(9,2) default NULL",
            'rssi':        "SMALLINT(4) default NULL",
            'longitude':   "DECIMAL(9,6) default NULL",
            'latitude':    "DECIMAL(8,6) default NULL",
            'altitude':    "DECIMAL(7,2) default NULL",
            'gas':         "DECIMAL(9,3) default NULL",
            'aqi':         "DECIMAL(5,2) default NULL",
            'default':     "DECIMAL(7,2) default NULL",
            "_valid":      "BOOL default 1"
        }

        fields = my_ident['fields']
        units = my_ident['units']
        add = []
        # we rely on the fact that fields in ident denote all fields in data dict
        table_flds = db_query("SELECT column_name FROM information_schema.columns WHERE  table_name = '%s_%s' AND table_schema = '%s'" % (args['ident']['project'],args['ident']['serial'],Conf['database']),True)
        gotIts = []     # avoid doubles
        for i in range(0,len(fields)):
            if (fields[i] in Conf['omit']) or (fields[i] in gotIts):
                continue
            gotIts.append(fields[i])
            Nme = db_name(fields[i])
            if not (Nme,) in table_flds:
                table_flds.append(Nme)
                Col = Sensor_fields['default']
                if fields[i] in Sensor_fields.keys():
                    Col = Sensor_fields[fields[i]]
                add.append("ADD COLUMN %s %s COMMENT 'type: %s; added on %s'" % (Nme, Col, units[i], datetime.datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M")))
                add.append("ADD COLUMN %s_valid %s COMMENT 'value validated'" % (Nme,Sensor_fields['_valid']))
        if len(add):
            try:
                db_query("ALTER TABLE %s_%s %s" % (args['ident']['project'],args['ident']['serial'],','.join(add)),False)
                Conf['log'](modulename,'ATTENT',"Added new field to table %s_%s" % (args['ident']['project'],args['ident']['serial']))
            except IOError:
                raise IOError
            except:
                Conf['log'](modulename,'FATAL',"Unable to add columns: %s" % ', '.join(add))
                Conf['output'] = False
                return False
        Conf["fields"][table] = fields
        return True

    # returns distance in meters between two GPS coodinates
    # hypothetical sphere radius 6372795 meter
    # courtesy of TinyGPS and Maarten Lamers
    # should return 208 meter 5 decimals is diff of 11 meter
    # GPSdistance((51.419563,6.14741),(51.420473,6.144795))
    LAT = 0
    LON = 1
    ALT = 2
    def GPSdistance(gps1,gps2):
        from math import sin, cos, radians, pow, sqrt, atan2
        delta = radians(float(gps1[LON])-float(gps2[LON]))
        sdlon = sin(delta)
        cdlon = cos(delta)
        lat = radians(float(gps1[LAT]))
        slat1 = sin(lat); clat1 = cos(lat)
        lat = radians(float(gps2[LAT]))
        slat2 = sin(lat); clat2 = cos(lat)
     
        delta = pow((clat1 * slat2) - (slat1 * clat2 * cdlon),2)
        delta += pow(clat2 * sdlon,2)
        delta = sqrt(delta)
        denom = (slat1 * slat2) + (clat1 * clat2 * cdlon)
        return int(round(6372795 * atan2(delta, denom)))

    try: kitTableName = args['ident']['project']+'_'+args['ident']['serial']
    except: return False
    if not db_connect(args['internet']): return False
    if not db_registrate(args['ident']):
        Conf['log'](modulename,'WARNING',"Unable to registrate the sensor.")
        return False
   
    if not db_table(kitTableName) or not db_fields(args['ident']):
        return False

    try: # save on same ordinates in sensed GPS, most kits are static
        geolocation = []
        for item in ['geolocation','coordinates']:
            if item in args['ident'].keys():
                geolocation = args['ident'][item].split(',')
                break
        ordinates = ['latitude','longitude','altitude']
        ordVal = []
        for i in range(len(ordinates)):
            try: ordVal.append(args['data'][ordinates[i]])
            except: break
        # static is less 100m
        if (len(ordinates) == len(geolocation)) and (GPSdistance(geolocation,ordinates) < 100):
            for item in ordinates: args['data'][item] = None
    except: pass

    query = "INSERT INTO %s " % kitTableName
    cols = ['datum']
    vals = ["FROM_UNIXTIME(%s)" % args['data']["time"]]
    gotIts = []
    for Fld in args['ident']['fields']:
        if (Fld in Conf['omit']) or (Fld in gotIts):
            continue
        gotIts.append(Fld)
        Nm = db_name(Fld)
        if (not Fld in args['data'].keys()) or (args['data'][Fld] == None):
            continue  # cols.append(Nm); vals.append("NULL")
        elif type(args['data'][Fld]) is str:
            cols.append(Nm); vals.append("'%s'" % args['data'][Fld])
        elif type(args['data'][Fld]) is list:
            # TO DO: this needs more thought
            Conf['log'](modulename,'WARNING',"Found list for sensor %s." % Fld)
            for i in range(0,len(args['data'][Fld])):
                nwe = "%s_%d" % (Nm,i,args['data'][Fld][i])
                if  not nwe in Fields:
                    # to do add column in database!
                    Fields.append(nwe)
                    Units.append('unit')
                cols.append("%s_%d" % (Nm,i)); vals.append(args['data'][Fld][i])
        else:
            cols.append(Nm)
            strg = "%6.5f" % args['data'][Fld]
            strg = strg.rstrip('0').rstrip('.') if '.' in strg else strg
            # strg = strg + '.0' if not '.' in strg else strg
            vals.append(strg)
    query += "(%s) " % ','.join(cols)
    query += "VALUES (%s)" % ','.join(vals)
    try:
        (cnt,) = db_query("SELECT count(*) FROM %s WHERE datum = from_unixtime(%s)" % (kitTableName,args['data']["time"]),True)
        if cnt[0] > 0: # overwrite old values
            db_query("DELETE FROM %s where datum = from_unixtime(%s)" % (kitTableName,args['data']["time"]), False)
        if db_query(query,False): ErrorCnt = 0
        else: ErrorCnt += 1
    except IOError:
        raise IOError
    except:
        Conf['log'](modulename,'ERROR',"Error in query: %s" % query)
        ErrorCnt += 1
    if ErrorCnt > 10:
        return False
    return True

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['output'] = True
    Conf['hostname'] = 'localhost'         # host InFlux server
    Conf['database'] = 'luchtmetingen'     # the MySql db for test usage, must exists
    Conf['user'] = 'IoS'                   # user with insert permission of InFlux DB
    Conf['password'] = 'acacadabra'        # DB credential secret to use InFlux DB

    if not len(sys.argv) > 1: exit(0)
    # get nodes info from a json file and update node info to DB
    if  sys.argv[1:] != 'test':
        from jsmin import jsmin     # tool to delete comments and compress json
        import json
        try:
            new = {}
            with open(sys.argv[1:][0]) as _typeOfJSON:
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
        #try:
        #    import Output_test_data
        #except:
        #    print("Please provide input test data: ident and data.")
        #    exit(1)
        Output_test_data = [
            { 'ident': {'coordinates': '0,0,0', 'description': 'MQTT AppID=pmsensors MQTT DeviceID=pmsensor2', 'fields': ['time', 'pm25', 'pm10', 'temp', 'rv'], 'DB': { 'kitTable': 'VW2017_XXXXXX' }, 'units': ['s', 'ug/m3', 'ug/m3', 'C', '%'], 'serial': 'XXXXXXX', 'types': ['time', u'SDS011', u'SDS011', 'DHT22', 'DHT22']},
               'data': {'pm10': 3.6, 'rv': 39.8, 'pm25': 1.4, 'temp': 25, 'time': int(time())-24*60*60}},
            { 'ident': {'description': 'MQTT AppID=pmsensors MQTT DeviceID=pmsensor1', 'fields': ['time', 'pm25', 'pm10', 'temp', 'rv'], 'DB': { 'kitTable': 'VW2017_XXXXXXX'}, 'units': ['s', 'ug/m3', 'ug/m3', 'C', '%'], 'serial': 'XXXXXXX', 'types': ['time', u'SDS011', u'SDS011', 'DHT22', 'DHT22']},
               'data': {'pm10': 3.6, 'rv': 39.8, 'pm25': 1.6, 'temp': 24, 'time': int(time())-23*60*60}},
            { 'ident': { 'coordinates': '6.1356117,51.420635,22.9',
                'version': '0.2.28', 'DB': { 'kitTable': 'test_sense'},
                'fields': ['time', 'pm_25', 'pm_10', 'dtemp', 'drh', 'temp', 'rh', 'hpa'],
                'extern_ip': ['83.161.151.250'], 'label': 'alphaTest', 'project': 'BdP',
                'units': ['s', 'pcs/qf', u'pcs/qf', 'C', '%', 'C', '%', 'hPa'],
                'types': ['time','Dylos DC1100', 'Dylos DC1100', 'DHT22', 'DHT22', 'BME280', 'BME280', 'BME280'],
                },
            'data': {'drh': 29.3, 'pm_25': 318.0, 'temp': 28.75,
                'time': 1494777772, 'hpa': 712.0, 'dtemp': 27.8,
                'rh': 25.0, 'pm_10': 62.0 },
            },
            ]
        for cnt in range(0,len(Output_test_data)):
            timings = time()
            try:
                publish(
                    ident = Output_test_data[cnt]['ident'],
                    data  = Output_test_data[cnt]['data'],
                    internet = net
                )
            except Exception as e:
                print("output channel error was raised as %s" % e)
                break
            timings = 30 - (time()-timings)
            if timings > 0:
                print("Sleep for %d seconds" % timings)
                sleep(timings)
    
