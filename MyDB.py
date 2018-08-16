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

# $Id: MyDB.py,v 2.34 2018/08/16 12:09:15 teus Exp teus $

# TO DO: write to file or cache
# reminder: MySQL is able to sync tables with other MySQL servers

""" Publish measurements to MySQL database
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyDB.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.34 $"[11:-2]

try:
    import MyLogger
    import sys
    import os
    import mysql
    import mysql.connector
    import datetime
    from time import time
except ImportError as e:
    MyLogger.log(modulename,'FATAL',"One of the import modules not found: %s"% e)

# configurable options
__options__ = ['output','hostname','port','database','user','password']

Conf = {
    'output': False,
    'hostname': 'localhost', # host MySQL server
    'user': None,        # user with insert permission of MySQL DB
    'password': None,    # DB credential secret to use MySQL DB
    'database': None,    # MySQL database name
    'port': 3306,        # default mysql port number
    'fd': None,           # have sent to db: current fd descriptor, 0 on IO error
    'omit' : ['time','geolocation','version','meteo','dust']        # fields not archived
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
def db_connect(net):
    """ Connect to MYsql database and save filehandler """
    global Conf
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
        MyLogger.log(modulename,'INFO','Using database %s on host %s, user %s credits.' % (Conf['database'],Conf['hostname'],Conf['user']))
        if (Conf['hostname'] != 'localhost') and ((not net['module']) or (not net['connected'])):
            MyLogger.log(modulename,'ERROR',"Access database %s / %s."  % (Conf['hostname'], Conf['database']))      
            Conf['output'] = False
            return False
        for M in ('user','password','hostname','database'):
            if (not M in Conf.keys()) or not Conf[M]:
                MyLogger.log(modulename,'ERROR',"Define DB details and credentials.")
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
            MyLogger.log(modulename,'ERROR',"MySQL Connection failure type: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
            return False
    else:
        return Conf['output']

# registrate the sensor to the Sensors table and update location/activity
serials = {}     # remember serials of sensor kits checked in into table Sensors
def db_registrate(ident):
    """ create or update identification inf to Sensors table in database """
    global Conf
    if not 'serial' in ident.keys():
        MyLogger.log(modulename,'DEBUG','serial missing in identification record')
        return False
    if ident['serial'] in serials.keys():
        if cmp(ident,serials[ident['serial']]) == 0: return True
        del serials[ident['serial']]
    if len(ident['fields']) == 0:
        return False
    if not db_table(ident,'Sensors'):
        return False
    def db_WhereAmI(ident,desc=True):
        query = []
        for fld in ("label","description","street","village","province","municipality"):
            if (fld == "description") and (not desc): continue
            if (fld in ident.keys()) and (ident[fld] != None):
                query.append("%s = '%s'" % (fld,ident[fld]))
        if not len(query): return
        db_query("UPDATE Sensors SET %s WHERE project = '%s' AND serial = '%s' AND active" % (','.join(query),ident['project'],ident['serial']),False)
        return

    if not 'label' in [str(r[0]) for r in db_query("SELECT column_name FROM information_schema.columns WHERE  table_name = 'Sensors' AND table_schema = '%s'" % Conf['database'],True)]:
        if not db_query("""ALTER TABLE Sensors
            ADD COLUMN coordinates VARCHAR(25) DEFAULT NULL,
            ADD COLUMN label VARCHAR(50) DEFAULT NULL,
            ADD COLUMN sensors VARCHAR(192) DEFAULT NULL,
            ADD COLUMN description VARCHAR(256) DEFAULT NULL,
            ADD COLUMN first DATETIME DEFAULT '2001-01-01 00:00:00',
            ADD COLUMN active BOOL DEFAULT 1,
            ADD COLUMN project VARCHAR(10) DEFAULT NULL,
            ADD COLUMN serial VARCHAR(15) DEFAULT NULL,
            ADD COLUMN street VARCHAR(50) DEFAULT NULL,
            ADD COLUMN village VARCHAR(50) DEFAULT NULL,
            ADD COLUMN province VARCHAR(50) DEFAULT NULL,
            ADD COLUMN municipality VARCHAR(50) DEFAULT NULL,
            ADD COLUMN last_check DATETIME DEFAULT CURRENT_TIMESTAMP,
            CHANGE datum datum datetime DEFAULT current_timestamp ON UPDATE current_timestamp
        """, False):
            return False
    Rslt =  db_query("SELECT first,coordinates,datum,active FROM Sensors WHERE project = '%s' AND serial = '%s' ORDER BY datum DESC" % (ident['project'],ident['serial']), True)
    if not type(Rslt) is list:
        return False
    serials[ident['serial']] = ident       # remember we know this one
    first = 'now()'
    fld_types = []
    try:
        ident['description'].index('hw:')
        flds = ident['description'].split(';')
        temp = []
        for i in range(0,len(flds)):
            if flds[i].find('hw:') >= 0:
                flds[i] = flds[i].replace('hw:','').upper()
                flds[i] = flds[i].replace(' ','')
                temp += flds[i].split(',')
        for i in temp:
            if not i in fld_types: fld_types.append(i)
    except: pass
    try:
        for i in ident['types']:
            if not i.upper() in fld_types: fld_types.append(i.upper())
    except: pass
    if len(fld_types):
        fld_types.sort()
        fld_types  = "'"+ ";hw: %s" % ','.join(fld_types) + "'"
    else:
        fld_types = 'NULL'
    fld_units = '' ; gotIts = []
    for i in range(0,len(ident['fields'])):
        if (ident['fields'][i] in Conf['omit']) or (ident['fields'][i] in gotIts):
            continue
        gotIts.append(ident['fields'][i])
        if len(fld_units): fld_units += ','
        fld_units += "%s(%s)" %(ident['fields'][i],ident['units'][i])
    if len(fld_units):
        fld_units ="'"+fld_units+"'"
    else:
        fld_units = 'NULL'

    if len(Rslt):
        first = "'%s'" % Rslt[0][0]
        for item in Rslt:
            if item[1] == ident['geolocation']: # same location, update info
                db_query("UPDATE Sensors SET last_check = now(), active = 1, sensors = %s, description = %s WHERE coordinates like '%s%%'  AND serial = '%s' AND datum = '%s'" % (fld_units,fld_types,','.join(ident['geolocation'].split(',')[0:2]),ident['serial'],item[2]) , False)
                # MyLogger.log(modulename,'ATTENT',"Registrated (renew last access) %s  to database table Sensors." % ident['serial'])
                db_WhereAmI(ident,desc=False)
                Conf["registrated"] = True
                return True
            elif item[3]:  # deactivate this one
                db_query("UPDATE Sensors SET active = 0 WHERE serial = '%s' AND datum = '%s' and active" % (ident['serial'],item[2]) , False)
    # new entry or sensor kit moved
    db_query("UPDATE Sensors SET active = 0 WHERE project = '%s' AND serial = '%s'" % (ident['project'],ident['serial']),False)
    try:
        db_query("INSERT INTO Sensors (project,serial,coordinates,sensors,description,last_check,first) VALUES ('%s','%s','%s',%s,%s,now(),%s)" % (ident['project'],ident['serial'],ident['geolocation'],fld_units,fld_types,first),False)
    except:
        pass
    MyLogger.log(modulename,'ATTENT',"New registration to database table Sensors.")
    db_WhereAmI(ident,True)
    return True

# do a query
Retry = False
def db_query(query,answer):
    """ communicate in sql to database """
    global Conf
    # testCnt = 0 # just for testing connectivity failures
    # if testCnt > 0: raise IOError
    MyLogger.log(modulename,'DEBUG',"Query: %s" % query)
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
        MyLogger.log(modulename,'ERROR',"Failure type: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
        MyLogger.log(modulename,'ERROR',"On query: %s" % query)
        # try once to reconnect
        try:
            Conf['fd'].close
            Conf['fd'] = None
            db_connect(Conf['net'])
        except:
            MyLogger.log(modulename,'ERROR','Failed to reconnect to MySQL DB.')
            return False
        if Retry:
            return False
        Retry = True
        MyLogger.log(modulename,'INFO',"Retry the query")
        if dp_query(query,answer):
            Retry = False
            return True
        MyLogger.log(modulename,'ERROR','Failed to redo query.')
        return False
    return True

# check if table exists if not create it
def db_table(ident,table):
    """ check if table exists in the database if not create it """
    global Conf
    if (table) in Conf.keys():
        return True
    if table in [str(r[0]) for r in db_query("SHOW TABLES",True)]:
        Conf[table] = True
        return True
    # create database: CREATE DATABASE  IF NOT EXISTS mydb; by super user
    if table in ('Sensors'):
        comment = 'Collection of sensor kits and locations'
        table_name = table
    else:
        comment = 'Sensor located at: %s' % ident['geolocation']
        table_name = '%s_%s' % (ident['project'],ident['serial'])
    if not db_query("""CREATE TABLE %s (
        id TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            COMMENT 'date/time latest change',
        datum datetime UNIQUE default NULL
            COMMENT 'date/time measurement'
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1
            COMMENT='%s'""" % (table_name,comment),False):
        Conf[table] = False
        MyLogger.log(modulename,'ERROR',"Unable to create sensor table %s in database." % table_name)
    else:
        MyLogger.log(modulename,'ATTENT',"Created table %s" % table_name)
    Conf[table] = True
    return Conf[table]

ErrorCnt = 0
# column names which are subjected to value validation with min, max value
# To Do: use sample of database, using Z-score or Grubs test (not advised),
# or using mean of variation
tresholds = [False,('^[a-z]?temp$',-40,40,None),('^[a-z]?rv$',0,100,None),('^pm_?[12][05]?$',0,200,None)]

def publish(**args):
    """ add records to the database,
        on the first update table Sensors with ident info """
    global Conf, ErrorCnt
    if (not 'output' in Conf.keys()) or (not Conf['output']):
        return
    for key in ['data','internet','ident']:
        if not key in args.keys():
            MyLogger.log(modulename,'FATAL',"Publish call missing argument %s." % key)

    # translate MySense filed names into MySQL column field names
    # TO DO: get the transaltion table from the MySense.conf file
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

    def regression(name,value,table,time,treshold=0):
        if not treshold: return 1
        return  1

    # to do: https://stackoverflow.com/questions/11686720/is-there-a-numpy-builtin-to-reject-outliers-from-a-list
    # http://codegist.net/snippet/python/grubbspy_leggitta_python
    def validate(name,value,table=None, time=None):
        import re
        if not tresholds[0]:
            for i in range(1,len(tresholds)):
                tresholds[i][0] = re.compile(tresholds[i][0])
        if (not type(value) is int) and (not type(value) is float): return 1
        if (value is None) or (value = float('nan')): return 0
        for i in range(1,len(tresholds)):
            if tresholds[i][0].match(name):
                if tresholds[i][1] <= value <= tresholdis[i][2]:
                    return regression(name,value,table,time,thresholds[i][3])
                return 0
        return 1

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
            'pa':          "INT(11) default NULL",
            'hpa':         "INT(11) default NULL",
            'wd':          "SMALLINT(4) default NULL",
            'pm1':         "DECIMAL(9,2) default NULL",
            'pm1_atm':     "DECIMAL(9,2) default NULL",
            'pm1_cnt':     "DECIMAL(9,2) default NULL",
            'pm03_cnt':    "DECIMAL(9,2) default NULL",
            'pm05_cnt':    "DECIMAL(9,2) default NULL",
            'rssi':        "SMALLINT(4) default NULL",
            'longitude':   "DECIMAL(9,6) default NULL",
            'latitude':    "DECIMAL(8,6) default NULL",
            'altitude':    "DECIMAL(7,2) default NULL",
            'gas':         "DECIMAL(9,3) default NULL",
            'aqi':         "DECIMAL(4,2) default NULL",
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
                MyLogger.log(modulename,'ATTENT',"Added new field to table %s_%s" % (args['ident']['project'],args['ident']['serial']))
            except IOError:
                raise IOError
            except:
                MyLogger.log(modulename,'FATAL',"Unable to add columns: %s" % ', '.join(add))
                Conf['output'] = False
                return False
        Conf["fields"][table] = fields
        return True

    if not db_connect(args['internet']):
        return False
    if not db_registrate(args['ident']):
        MyLogger.log(modulename,'WARNING',"Unable to registrate the sensor.")
        return False
   
    if not db_table(args['ident'],args['ident']["project"]+'_'+args['ident']["serial"]) or \
        not db_fields(args['ident']):
        return False
    query = "INSERT INTO %s_%s " % (args['ident']['project'],args['ident']['serial'])
    cols = ['datum']
    vals = ["FROM_UNIXTIME(%s)" % args['data']["time"]]
    gotIts = []
    for Fld in args['ident']['fields']:
        if (Fld in Conf['omit']) or (Fld in gotIts):
            continue
        gotIts.append(Fld)
        Nm = db_name(Fld)
        if (not Fld in args['data'].keys()) or (args['data'][Fld] == None):
            cols.append(Nm); vals.append("NULL")
            # cols.append(Nme + '_valid'); vals.append("NULL")
        elif type(args['data'][Fld]) is str:
            cols.append(Nm); vals.append("'%s'" % args['data'][Fld])
        elif type(args['data'][Fld]) is list:
            # TO DO: this needs more thought
            MyLogger.log(modulename,'WARNING',"Found list for sensor %s." % Fld)
            for i in range(0,len(args['data'][Fld])):
                nwe = "%s_%d" % (Nm,i,args['data'][Fld][i])
                if  not nwe in Fields:
                    # To Do add column in database!
                    Fields.append(nwe)
                    Units.append('unit')
                cols.append("%s_%d" % (Nm,i)); vals.append(args['data'][Fld][i])
                # cols.append("%s_%d_valid" % (Nm,i)); vals.append(validate(Nm,args['data'][Fld][i],time=args['data']["time"],table=args['ident']['project']+'_'+args['ident']['serial']))
        else:
            cols.append(Nm)
            # cols.append(Nm + '_valid')
            strg = "%6.2f" % args['data'][Fld]
            strg = strg.rstrip('0').rstrip('.') if '.' in strg else strg
            # strg = strg + '.0' if not '.' in strg else strg
            vals.append(strg)
            # vals.append(validate(Nm,args['data'][Fld],time=args['data']["time"],table=args['ident']['project']+'_'+args['ident']['serial']))
    query += "(%s) " % ','.join(cols)
    query += "VALUES (%s)" % ','.join(vals)
    try:
        (cnt,) = db_query("SELECT count(*) FROM %s_%s WHERE datum = from_unixtime(%s)" % (args['ident']['project'],args['ident']['serial'],args['data']["time"]),True)
        if cnt[0] > 0: # overwrite old values
            db_query("DELETE FROM %s_%s where datum = from_unixtime(%s)" % (args['ident']['project'],args['ident']['serial'],args['data']["time"]), False)
        if db_query(query,False): ErrorCnt = 0
        else: ErrorCnt += 1
    except IOError:
        raise IOError
    except:
        MyLogger.log(modulename,'ERROR',"Error in query: %s" % query)
        ErrorCnt += 1
    if ErrorCnt > 10:
        return False
    return True

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['output'] = True
    Conf['hostname'] = 'localhost'         # host InFlux server
    Conf['database'] = 'luchtmetingen' # the MySql db for test usage, must exists
    Conf['user'] = 'IoS'              # user with insert permission of InFlux DB
    Conf['password'] = 'acacadabra'     # DB credential secret to use InFlux DB
    net = { 'module': True, 'connected': True }
    Output_test_data = [
        { 'ident': {'geolocation': '?', 'description': 'MQTT AppID=pmsensors MQTT DeviceID=pmsensor2', 'fields': ['time', 'pm25', 'pm10', 'temp', 'rv'], 'project': 'VW2017', 'units': ['s', 'ug/m3', 'ug/m3', 'C', '%'], 'serial': 'XXXXXXX', 'types': ['time', u'SDS011', u'SDS011', 'DHT22', 'DHT22']},
           'data': {'pm10': 3.6, 'rv': 39.8, 'pm25': 1.4, 'temp': 25, 'time': int(time())-24*60*60}},
        { 'ident': {'description': 'MQTT AppID=pmsensors MQTT DeviceID=pmsensor1', 'fields': ['time', 'pm25', 'pm10', 'temp', 'rv'], 'project': 'VW2017', 'units': ['s', 'ug/m3', 'ug/m3', 'C', '%'], 'serial': 'XXXXXXX', 'types': ['time', u'SDS011', u'SDS011', 'DHT22', 'DHT22']},
           'data': {'pm10': 3.6, 'rv': 39.8, 'pm25': 1.6, 'temp': 24, 'time': int(time())-23*60*60}},
        { 'ident': { 'geolocation': '51.420635,6.1356117,22.9',
            'version': '0.2.28', 'serial': 'test_sense',
            'fields': ['time', 'pm_25', 'pm_10', 'dtemp', 'drh', 'temp', 'rh', 'hpa'],
            'extern_ip': ['83.161.151.250'], 'label': 'alphaTest', 'project': 'BdP',
            'units': ['s', 'pcs/qf', u'pcs/qf', 'C', '%', 'C', '%', 'hPa'],
            'intern_ip': ['192.168.178.49', '2001:980:ac6a:1:83c2:7b8d:90b7:8750', '2001:980:ac6a:1:17bf:6b65:17d2:dd7a'],
            'types': ['time','Dylos DC1100', 'Dylos DC1100', 'DHT22', 'DHT22', 'BME280', 'BME280', 'BME280'],
            },
        'data': {'drh': 29.3, 'pm_25': 318.0, 'temp': 28.75,
            'time': 1494777772, 'hpa': 712.0, 'dtemp': 27.8,
            'rh': 25.0, 'pm_10': 62.0 },
        },
        ]
    #try:
    #    import Output_test_data
    #except:
    #    print("Please provide input test data: ident and data.")
    #    exit(1)

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

