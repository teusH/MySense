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

# $Id: MyDB.py,v 5.10 2021/10/30 12:03:04 teus Exp teus $

# reminder: MySQL is able to sync tables with other MySQL servers

""" Publish measurements to MySQL database
    Relies on Conf setting by main program
"""
__modulename__='$RCSfile: MyDB.py,v $'[10:-4]
__version__ = "0." + "$Revision: 5.10 $"[11:-2]
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
    import os
    import mysql
    import mysql.connector
    import datetime
    from time import time, sleep
    import atexit
    import re
except ImportError as e:
    sys.exit("FATAL: One of the import modules not found: %s"% e)

# configurable options
__options__ = ['output','hostname','port','database','user','password','DEBUG']

# close socket connection on exit
def db_exit( conf=None):
   global Conf
   if not conf: conf = Conf
   try:
     # if conf['fd']: conf['fd'].close()
     if conf['fd']: conf['fd'].shutdown()
     return True
   except: pass
   return False

Conf = {
    'hostname': 'localhost', # host MySQL server
    'user': None,        # user with insert permission of MySQL DB
    'password': None,    # DB credential secret to use MySQL DB
    'database': 'luchtmetingen',    # dflt MySQL database name
    'port': 3306,        # default mysql port number
    'fd': None,          # have sent to db: current fd descriptor, 0 on IO error
    'log': None,         # MyLogger log routine
    'level': None,       # MyLogger log level, default INFO
    'tables': ['Sensors','TTNtable','SensorTypes'], # allow columns cache for these tables
    'STOP': db_exit,     # close connection to MySQL server
    'DEBUG': False       # debugging printout
}

# supported column names in measurements table.
# columns are added on the fly.
# To Do: use a DB table for this
# list: [DB colum width, decimals 0 for int, None string or [min,max], unit or -1 for bool]
Sensor_fields = {
    # 'id':        TIMESTAMP default CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP,
    # 'datum':     DATETIME default NULL UNIQUE,
    # 'sensors':   VARCHAR(64) DEFAULT NULL COMMENT 'active sensor types in measurement row',

    # network      network statistics wifi/LoRaWan is not yet supported
    # 'rssi':      ["SMALLINT(4) default NULL COMMENT 'dB'",0,None,'dB'],          # not used
    # dust
    'pm1':         ["DECIMAL(9,2) default NULL COMMENT 'ug/m3'",2,[0,450],'ug/m3'],
    'pm25':        ["DECIMAL(9,2) default NULL COMMENT 'ug/m3'",2,[0,450],'ug/m3'],
    'pm10':        ["DECIMAL(9,2) default NULL COMMENT 'ug/m3'",2,[0,450],'ug/m3'],
    'pm03_cnt':    ["DECIMAL(9,2) default NULL COMMENT 'pcs/0.1dm3'",2,[1,15000],'pcs/0.1dm3'],
    'pm05_cnt':    ["DECIMAL(9,2) default NULL COMMENT 'pcs/0.1dm3'",2,[1,15000],'pcs/0.1dm3'],
    'pm1_atm':     ["DECIMAL(9,2) default NULL COMMENT 'pcs/0.1dm3'",2,[1,15000],'pcs/0.1dm3'],
    'pm1_cnt':     ["DECIMAL(9,2) default NULL COMMENT 'pcs/0.1dm3'",2,[1,15000],'pcs/0.1dm3'],
    'pm4_cnt':     ["DECIMAL(9,2) default NULL COMMENT 'pcs/0.1dm3'",2,[1,15000],'pcs/0.1dm3'],
    'pm25_cnt':    ["DECIMAL(9,2) default NULL COMMENT 'pcs/0.1dm3'",2,[1,15000],'pcs/0.1dm3'],
    'pm4_cnt':     ["DECIMAL(9,2) default NULL COMMENT 'pcs/0.1dm3'",2,[1,15000],'pcs/0.1dm3'], # Sensirion
    'pm5_cnt':     ["DECIMAL(9,2) default NULL COMMENT 'pcs/0.1dm3'",2,[1,15000],'pcs/0.1dm3'], # Plantower
    'pm10_cnt':    ["DECIMAL(9,2) default NULL COMMENT 'pcs/0.1dm3'",2,[1,15000],'pcs/0.1dm3'],
    'grain':       ["DECIMAL(3,2) default NULL COMMENT 'pcs/0.1dm3'",2,[0.02,1.0],'um'],        # avg um
    # location
    'geohash':     ["VARCHAR(12) default NULL COMMENT 'grid'",None,None,'grid'],
    'longitude':   ["DECIMAL(9,6) default NULL COMMENT 'degrees'",6,[4.5,6.5],'degrees'],    # DEPRECATED
    'latitude':    ["DECIMAL(8,6) default NULL COMMENT 'degrees'",6,[48.5,60.0],'degrees'],  # DEPRECATED
    'altitude':    ["DECIMAL(7,2) default NULL COMMENT 'm'",2,[0,500],'m'],
    # meteo
    'temp':        ["DECIMAL(3,2) default NULL COMMENT 'C'",2,[-25,48.0],'C'],         # 0.0 is error
    'rv':          ["DECIMAL(3,2) default NULL COMMENT '%'",2,[3.0,100.0],'%%'],       # RH, 100% is error
    'luchtdruk':   ["INT(5) default NULL COMMENT 'hPa'",0,[850.0,1200.0],'hPa'],
    'gas':         ["DECIMAL(9,3) default NULL COMMENT 'kOhm'",3,[7.5,7500.0],'kOhm'], # Bosch BME680
    'aqi':         ["DECIMAL(5,2) default NULL COMMENT '%%'",2,[1.0,100.0],'%%'],      # Bosch BME680
    # gas
    'NO2':         ["INT(5) default NULL COMMENT 'ppm'",0,[0,10000],'ppm'],
    'NOx':         ["INT(5) default NULL COMMENT 'ppm'",0,[0,10000],'ppm'],
    'O3':          ["INT(5) default NULL COMMENT 'ppm'",0,[0,10000],'ppm'],
    'NH3':         ["INT(5) default NULL COMMENT 'ppm'",0,[0,10000],'ppm'],
    'CO2':         ["INT(5) default NULL COMMENT 'ppm'",0,[0,10000],'ppm'],
    'SO2':         ["INT(5) default NULL COMMENT 'ppm'",0,[0,10000],'ppm'],
    # weather
    'ws':          ["DECIMAL(4,1) default NULL COMMENT 'm/sec'",1,[0.0,95.0],'m/sec'],
    'wr':          ["DECIMAL(4,1) default NULL COMMENT 'degrees'",1,[0,360],'degrees'],
    'rain':        ["DECIMAL(4,1) default NULL COMMENT 'mm/h'",1,[0,1000],'mm/h'],
    'prevrain':    ["DECIMAL(4,1) default NULL COMMENT 'mm'",1,[0,1000],'mm/h'],   # WASPMOTE
    'dayrain':     ["DECIMAL(4,1) default NULL COMMENT 'mm'",1,[0,1000],'mm'],     # WASPMOTE
    # energy
    'accu':        ["DECIMAL(4,1) default NULL COMMENT 'V'",1,[0,250],'V'],        # voltage
    'level':       ["DECIMAL(4,1) default NULL COMMENT '%%'",1,[0,150],'%%'],       # level

    'default':     ["DECIMAL(7,2) default NULL",2,None,None],         # deprecated

    # valid: None will say 'in repair', False: incorrect value
    "_valid":      ["BOOL default 1 COMMENT 'NULL: in repair'",-1,None,None]
}
# fields/columns suppoprted in measurement tables
# if matched, can be called with group(): category
SupportedFields = re.compile(r'^((?P<dust>(pm[0-9]+(_cnt)?|grain))|(?P<location>(geohash|longitude|latitude|altitude))|(?P<meteo>(temp|rv|luchtdruk|gas|aqi))|(?P<gas>(NO[2x]|O3|NH3|[CS]O2))|(?P<weather>(w[sr]|(prev|day)?rain)|(?P<energy>(accu|level))))$', re.I)

# optain database DB info list:
#   column info, or precision info, or value range (None for string or bool), sensor value unit
def getFieldInfo(field):
    global Sensor_fields
    try:
      return Sensor_fields[field]
    except:
      if not info:
        Conf['log'](WHERE(True),'ATTENT',"Unknown sensor field: %s"  % field)
      return Sensor_fields['default']

# ========================================================
# write data directly to a database
# ========================================================
# create table <ProjectID_Serial>, record columns,
#       registration Sensors table on the fly
def attributes(**t):
    global Conf
    Conf.update(t)

# connect to db and keep connection as long as possible
def db_connect():
    """ Connect to MYsql database and save filehandler """
    global Conf
    if not Conf['log']:
        try: from lib import MyLogger
        except: import MyLogger
        Conf['log'] = MyLogger.log
        if Conf['level']: MyLogger.Conf['level'] = Conf['level'] # set log level
    if not 'fd' in Conf.keys(): Conf['fd'] = None
    if not 'last' in Conf.keys():
        Conf['waiting'] = 5 * 30 ; Conf['last'] = 0 ; Conf['waitCnt'] = 0
    elif Conf['waitCnt']: sleep(Conf['waiting'])
    if (Conf['fd'] == None) or (not Conf['fd']):
        # get DBUSER, DBHOST, DBPASS from process environment if present
        for credit in ['hostname','user','password','database']:
            if not credit in Conf.keys():
                Conf[credit] = None
            if Conf[credit] == None:  # if not provided eg via configuration init file
              try:
                Conf[credit] = os.getenv('DB'+(credit[0:4].upper() if credit != 'database' else ''),Conf[credit])
              except:
                pass
        Conf['log'](WHERE(),'INFO',"Using database '%s' on host '%s', user '%s' credentials." % (Conf['database'],Conf['hostname'],Conf['user']))
        if (Conf['hostname'] != 'localhost'): # just a reminder
            Conf['log'](WHERE(True),'CRITICAL',"THIS IS NOT A LOCALHOST ACCESS! Database host %s / %s."  % (Conf['hostname'], Conf['database']))      
        for M in ('user','password','hostname','database'):
            if (not M in Conf.keys()) or not Conf[M]:
                Conf['log'](WHERE(True),'FATAL',"Define DB details and credentials!")
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
            atexit.register(db_exit,Conf)
            Conf['last'] = 0 ; Conf['waiting'] = 5 * 30 ; Conf['waitCnt'] = 0
            return True
        except IOError:
            Conf['last'] = time() ; Conf['fd'] = 0 ; Conf['waitCnt'] += 1
            if not (Conf['waitCnt'] % 5): Conf['waiting'] *= 2
            if Conf['waitCnt'] > 5: raise IOError
            else: return db_connect()
        except:
            del Conf['fd']
            Conf['log'](WHERE(True),'ERROR',"MySQL Connection failure type: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
            return False
    else:
        return True

# create table Sensors
       # id      timestamp       CURRENT_TIMESTAMP       timestamp last change row
       # datum   datetime        CURRENT_TIMESTAMP       on update CURRENT_TIMESTAMP
       # ADD COLUMN coordinates  VARCHAR(25)     DEFAULT NULL COMMENT 'latitude,longitude,altitude DEPRECATED',
def CreateSensors():
    try:
        if db_query("""ALTER TABLE Sensors
        ADD COLUMN project      VARCHAR(20)     DEFAULT NULL COMMENT 'project id, measurement reference',
        ADD COLUMN serial       VARCHAR(15)     DEFAULT NULL COMMENT 'kit serial identifier, measurement reference',
        ADD COLUMN label        VARCHAR(50)     DEFAULT NULL COMMENT 'location name',
        ADD COLUMN sensors      VARCHAR(384)    DEFAULT NULL COMMENT 'sensor manufacturer types',
        ADD COLUMN first        DATETIME        DEFAULT '2001-01-01 00:00:00' COMMENT 'first activation',
        ADD COLUMN active       TINYINT(1)      DEFAULT 1    COMMENT 'sensor is active',
        ADD COLUMN last_check   DATETIME        DEFAULT CURRENT_TIMESTAMP COMMENT 'last date/time check location',

        ADD COLUMN description  VARCHAR(512)    DEFAULT NULL COMMENT 'software, configution, ',
        ADD COLUMN comment      VARCHAR(128)    DEFAULT NULL COMMENT 'version numbers, extra
        ADD COLUMN notice       VARCHAR(128)    DEFAULT NULL COMMENT 'email/slack address',

        ADD COLUMN geohash      VARCHAR(12)     DEFAULT NULL COMMENT 'geo hash home location',
        ADD COLUMN altitude     DECIMAL(7,2)    DEFAULT NULL COMMENT 'meters above sea level',
        ADD COLUMN street       VARCHAR(50)     DEFAULT NULL COMMENT 'location road name',
        ADD COLUMN housenr      VARCHAR(6)      DEFAULT NULL COMMENT 'house nr in street',
        ADD COLUMN village      VARCHAR(50)     DEFAULT NULL COMMENT 'location village name',
        ADD COLUMN pcode        VARCHAR(10)     DEFAULT NULL COMMENT 'post code location
        ADD COLUMN municipality VARCHAR(50)     DEFAULT NULL COMMENT 'location municipality name',
        ADD COLUMN province     VARCHAR(50)     DEFAULT NULL COMMENT 'location state name',
        ADD COLUMN region       VARCHAR(20)     DEFAULT NULL COMMENT 'name of the regio',

          CHANGE datum datum datetime DEFAULT current_timestamp ON UPDATE current_timestamp
        """, False):
            return True
    except: pass
    return False

# try to correct database for missing columns in table
def db_tableColError(failureType,query):
    try:
        col = failureType[failureType.lower().index('unknown column ')+16:]
        col = col[:col.index("'")]
        tbl = query[query.lower().index('insert into ')+12:]
        tbl = tbl[:tbl.index(' ')]
        tbl.index('_') # check on sensor table name
        if not db_table(tbl): return False
        Conf['log'](WHERE(),'ATTENT',"Added for table %s column %s and %s_valid" % (tbl,col,col))
        return db_query("ALTER TABLE %s ADD COLUMN %s %s, ADD COLUMN %s_valid %s" % (tbl,col,getFieldInfo(col)[0],col,getFieldInfo('_valid'))[0],False)
    except: return False
    return True

# do a query
Retry = False
# returns either True/False or an array of tuples
def db_query(query,answer):
    """ communicate in sql to database """
    global Conf, Retry
    if Conf['fd'] == None and not db_connect():
        Conf['log'](WHERE(True),'FATAL','Unable to connect to DB')
        exit(1)
    # testCnt = 0 # just for testing connectivity failures
    # if testCnt > 0: raise IOError
    Conf['log'](WHERE(True),'DEBUG',"MySQL query: %s" % query)
    try:
        c = Conf['fd'].cursor()
        c.execute (query)
        if answer:
            return c.fetchall()     
        else:
            Conf['fd'].commit()
    except IOError:
        Conf['fd'].close; Conf['fd'] = None; Conf['waitCnt'] += 1
        db_connect()
    except mysql.connector.Error as err:
        if err.errno == 2006: # try to reconnect
          try:
            Conf['fd'].close; Conf['fd'] = None; Conf['waitCnt'] += 1
            if not db_connect(): raise IOError("Connection broke down.")
          except:
            Conf['log'](WHERE(True),'FATAL','Failed to reconnect to MySQL DB.')
            # raise IOError("Connection broke down.")
            return False
        else:
          FailType = sys.exc_info()[1]
          Conf['log'](WHERE(True),'ERROR',"Failure type: %s; value: %s" % (sys.exc_info()[0],FailType) )
          Conf['log'](WHERE(True),'ERROR',"On query: %s" % query)
          db_tableColError(FailType,query)  # maybe we can correct this
        if Retry:
            return False
        Retry = True
        Conf['log'](WHERE(True),'INFO',"Retry the query")
        if db_query(query,answer):
            Retry = False
            return True
        Conf['log'](WHERE(True),'ERROR','Failed to redo query.')
        return False
    except:
        FailType = sys.exc_info()[1]
        Conf['log'](WHERE(True),'ERROR',"Failure type: %s; value: %s" % (sys.exc_info()[0],FailType) )
        Conf['log'](WHERE(True),'ERROR',"On query: %s" % query)
        return False
    return True

def CreateLoRaTable(table):
    if not db_query("""CREATE TABLE %s (
        id      datetime        DEFAULT CURRENT_TIMESTAMP COMMENT 'date/time creation',
        datum   timestamp       DEFAULT CURRENT_TIMESTAMP COMMENT 'on update CURRENT_TIMESTAMP',

        project varchar(16)     DEFAULT NULL              COMMENT 'project id, reference to measurements',
        serial  varchar(16)     DEFAULT NULL              COMMENT 'serial kit hex, reference to measurements',
        active  tinyint(1)      DEFAULT 0                 COMMENT 'DB values enabled',
        refresh datetime        DEFAULT NULL              COMMENT 'date from which kit is in repair',
        valid   tinyint(1)      DEFAULT 1                 COMMENT 'validate measurements, if NULL in repair, False omit in DB',

        TTN_app varchar(32)     DEFAULT '20108225197a1z'  COMMENT 'TTN application ID',
        TTN_id  varchar(32)     DEFAULT NULL              COMMENT 'TTN device topic name',
        AppEui  varchar(16)     DEFAULT NULL              COMMENT 'OTAA application id TTN',
        DevEui  varchar(16)     DEFAULT NULL              COMMENT 'OTAA device eui Hex',

        AppSKEY varchar(32)     DEFAULT NULL              COMMENT 'OTAA/ABP secret key Hex',
        DevAdd  varchar(10)     DEFAULT NULL              COMMENT 'ABP device id Hex',
        NwkSKEY varchar(32)     DEFAULT NULL              COMMENT 'ABP network secret key Hex',

        website tinyint(1)      DEFAULT 0                 COMMENT 'publish measurements on website',

        luftdatenID varchar(16) DEFAULT NULL              COMMENT 'if null use TTN-serial',
        luftdaten   tinyint(1)  DEFAULT 0                 COMMENT 'POST to luftdaten',

        UNIQUE kit_id (project,serial)
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='TTN info input table, output'""" % table,False):
        Conf['log'](WHERE(True),'ERROR', 'Failed to create LoRa node table %s' % table)
        return False
    return True

def CreateSensorTypesTable(table):
    if not db_query("""CREATE TABLE %s (
        id      datetime        DEFAULT CURRENT_TIMESTAMP COMMENT 'date/time creation',
        datum   timestamp       DEFAULT CURRENT_TIMESTAMP COMMENT 'on update CURRENT_TIMESTAMP',
        product  varchar(16)    DEFAULT NULL COMMENT 'sensor product name',
        name     varchar(16)    DEFAULT NULL COMMENT 'other product name',
        producer varchar(16)    DEFAULT NULL COMMENT 'manufacturer',
        category varchar(16)    DEFAULT NULL COMMENT 'dust meteo,location,gas,LoRa,controller,IoS, energy etc.',
        fields   varchar(512)   DEFAULT NULL COMMENT 'supported measurements field or column names',
        UNIQUE kit_id (project,serial)
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='TTN info input table, output'""" % table,False):
        Conf['log'](WHERE(True),'ERROR', 'Failed to create LoRa node table %s' % table)
        return False
    return True

# table columns cache for global tables eg Sensors, TTNtable
def TableColumns(table):
    global Conf
    try:
      if not table in Conf['tables']: return []
    except: return []
    if not 'columns' in TableColumns.__dict__: TableColumns.columns = {}
    if not table in TableColumns.columns.keys():
        TableColumns.columns[table] = [str(r[0]) for r in db_query("DESCRIBE %s" % table, True)]
    return TableColumns.columns[table]

# get a field/column value from a table. Fields maybe (prefeable) be a list
def getNodeFields(id,fields,table='Sensors',project=None,serial=None):
    global Conf
    if Conf['fd'] == None and not db_connect():
        Conf['log'](WHERE(True),'FATAL','Unable to connect to DB')
        exit(1)
    if project and serial:
        try:
            if table == 'Sensors':
              qry = "SELECT UNIX_TIMESTAMP(id) FROM %s WHERE project = '%s' AND serial = '%s' AND active ORDER BY active DESC, datum DESC LIMIT 1" % (table,project,serial)
            else:
              qry = "SELECT UNIX_TIMESTAMP(id) FROM %s WHERE project = '%s' AND serial = '%s' AND active ORDER BY id DESC LIMIT 1" % (table,project,serial)
            qry = db_query(qry, True)
        except: pass
        if not len(qry): return None
        id = qry[0][0]
    if (type(fields) is str) and (fields == '*'): # wild card: all available
        fields = TableColumns(table)
    else: 
        fld = []
        if not type(fields) is list:
            fields = fields.split(',')
        for item in fields:
            item = item.strip()
            if not ('geohash' if item in ['longitude','latitude','coordinates'] else item) in TableColumns(table):
              Conf['log'](WHERE(True),'ERROR','Field %s not in table %s. SKIPPED.' % (item,table))
            else: fld.append(item)
        fields = fld
    values = []
    for i in range(0,len(fields)):
        if fields[i] in ['id','datum','first','last_check']: values.append('UNIX_TIMESTAMP(%s)' % fields[i])
        elif fields[i] in ['longitude', 'latitude']:
          values.append('ST_%sFromGeoHash(geohash)' % ('Long' if fields[i][:3] == 'lon' else 'Lat'))
        elif fields[i] == 'coordinates': # coordinates column in DB is deprecated
          values.append("CONCAT(ST_LongFromGeoHash(geohash),',',ST_LatFromGeoHash(geohash),',',altitude)")
        else: values.append(fields[i])
    qry = db_query("SELECT %s FROM %s WHERE UNIX_TIMESTAMP(id) = %d LIMIT 1" % (','.join(values),table,int(id)),True)
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
            Conf['log'](WHERE(True),'ERROR','Set field %s not in table %s. SKIPPED.' % (fields[i],table))
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
        Conf['log'](WHERE(True),'ERROR','Unable to update table %s. Error %s.' % (table,str(e)))
        return False

# check if table exists if not create it
def db_table(table,create=True):
    """ check if table exists in the database if not create it """
    global Conf
    if (not 'fd' in Conf.keys()) and not Conf['fd']:
        try: db_connect()
        except:
            Conf['log'](WHERE(True),'FATAL','No MySQL connection available')
            return False
    if (table) in Conf.keys():
        return True
    if table in [str(r[0]) for r in db_query("SHOW TABLES LIKE '%s'" % table,True)]:
        Conf[table] = True
        return True
    if not create: return False
    # create database: CREATE DATABASE  IF NOT EXISTS mydb; by super user
    if table in ('Sensors'):
        comment = 'Collection of sensor kits and locations'
        table_name = table
    elif table == 'TTNtable':
        Conf[table] = CreateLoRaTable(table); return Conf[table]
    elif table == 'SensorTypes':
        Conf[table] = CreateSensorTypesTable(table); return Conf[table]
    if table.find('_') >= 0 and not db_query("""CREATE TABLE IF NOT EXISTS %s (
        id TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            COMMENT 'date/time latest change',
        datum datetime UNIQUE default NULL
            COMMENT 'date/time measurement',
        sensors varchar(64) default NULL
            COMMENT 'sensor types in this measurement'
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1
            COMMENT='measurements table created at %s'""" % (table,datetime.datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M")),False):
        Conf[table] = False
        Conf['log'](WHERE(True),'ERROR',"Unable to create sensor table %s in database." % table)
    else:
      Conf['log'](WHERE(),'ATTENT',"Created table %s in DB" % table)
    Conf[table] = True
    return Conf[table]

# test main loop. Will create tables Sensors, SensorTypes, TTNtable if needed.
if __name__ == '__main__':
    from time import sleep
    Conf['hostname'] = 'localhost'         # host InFlux server
    Conf['database'] = 'luchtmetingen'     # the MySql db for test usage, must exists
    Conf['user'] = 'IoS'                   # user with insert permission of InFlux DB
    Conf['password'] = 'acacadabra'        # DB credential secret to use InFlux DB
    # Conf['level'] = 'DEBUG'                # log level

    # add all routine calls with some test arguments
    if not db_connect():
      print("Could not connect to database %s on host %s as user %s\n" % (Conf['database'],Conf['hostname'],Conf['user']))
      exit(1)

    for tbl in ('Sensors','TTNtable','SensorTypes'): # check meta tables in database
      if db_table(tbl,False):
        print("Table '%s' exists." % tbl)
        print("    columns: %s" % ', '.join(TableColumns(tbl)))
      elif db_table(tbl,True):
        print("Table '%s' created." % tbl)
        print("    columns: %s" % ', '.join(TableColumns(tbl)))
      else:
        print("ERROR on check for table '%s'" % tbl)

    # check measurent kits existance
    try:
        print("Max 5 most recent active measurements tables:")
        for (project,serial,) in db_query("SELECT project,serial FROM Sensors WHERE active ORDER BY datum DESC LIMIT 5", True):
           print("  Measurement table %s_%s" %(project,serial))
           print("    Some location info of the kit of the 'Sensors' table: %s" % str(getNodeFields(None,['datum','project','serial','label','geohash','street','village'],project=project,serial=serial)))
    except Exception as e: print("FAILED: %s" % str(e))

   #setNodeFields(id,['datum'],['datum'],table='Sensors',project=project,serial=serial,adebug=True)

    # get some info about range and precision van sensors in a measurement
    print("Measurements table info: list of DB column width, decimals, [min,max] range, measurement unit")
    for col in ('pm10','temp','NO2'):
      print("    For field %s: %s" % (col,', '.join([(str(a) if not type(a) is str else '"'+a+'"') for a in getFieldInfo(col)])))

    # try to exit without hanging up
    #try:
    #  Conf['STOP']()
    #  print("Stopped db connection")
    #except: print("Failed to stop db connection")
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

