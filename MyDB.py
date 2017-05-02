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

# $Id: MyDB.py,v 2.19 2017/05/02 08:45:48 teus Exp teus $

# TO DO: write to file or cache
# reminder: MySQL is able to sync tables with other MySQL servers

""" Publish measurements to MySQL database
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyDB.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.19 $"[11:-2]

try:
    import MyLogger
    import sys
    import mysql
    import mysql.connector
    import datetime
    from time import time
except ImportError as e:
    MyLogger.log("FATAL","One of the import modules not found: %s" % e)

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
    'omit' : ['time','geolocation','rssi']        # fields not archived
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
    if (Conf['fd'] == None) or (not Conf['fd']):
        if (Conf['hostname'] != 'localhost') and ((not net['module']) or (not net['connected'])):
            MyLogger.log('ERROR',"Local access database %s / %s."  % (Conf['hostname'], Conf['database']))      
            Conf['output'] = False
            return False
        for M in ('user','password','hostname','database'):
            if (not M in Conf.keys()) or not Conf[M]:
                MyLogger.log('ERROR','Define DB details and credentials.')
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
                database=Conf['database'])
            Conf['last'] = 0 ; Conf['waiting'] = 5 * 30 ; Conf['waitCnt'] = 0
            return True
        except IOError:
            Conf['last'] = time() ; Conf['fd'] = 0 ; Conf['waitCnt'] += 1
            if not (Conf['waitCnt'] % 5): Conf['waiting'] *= 2
            raise IOError
        except:
            Conf['output'] = False; del Conf['fd']
            MyLogger.log('ERROR',"MySQL Connection failure type: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
            return False
    else:
        return Conf['output']

# registrate the sensor to the Sensors table and update location/activity
def db_registrate(ident):
    """ create or update identification inf to Sensors table in database """
    global Conf
    if ("registrated") in Conf.keys():
        return Conf['registrated']
    if len(ident['fields']) == 0:
        return False
    if not db_table(ident,'Sensors'):
        return False
    def db_WhereAmI(ident):
        query = []
        for fld in ("label","description","street","village","province","municipality"):
            if (fld in ident.keys()) and (ident[fld] != None):
                query.append("%s = '%s'" % (fld,ident[fld]))
        if not len(query): return
        db_query("UPDATE Sensors SET %s WHERE project = '%s' AND serial = '%s' AND active" % (','.join(query),ident['project'],ident['serial']),False)
        return

    if not ('label',) in db_query("SELECT column_name FROM information_schema.columns WHERE  table_name = 'Sensors' AND table_schema = '%s'" % Conf['database'],True):
        if not db_query("""ALTER TABLE Sensors
            ADD COLUMN coordinates VARCHAR(25) DEFAULT NULL,
            ADD COLUMN label VARCHAR(50) DEFAULT NULL,
            ADD COLUMN sensors VARCHAR(128) DEFAULT NULL,
            ADD COLUMN description VARCHAR(128) DEFAULT NULL,
            ADD COLUMN first DATETIME DEFAULT '2001-01-01 00:00:00',
            ADD COLUMN active TINYBIT(1) DEFAULT 1,
            ADD COLUMN project VARCHAR(10) DEFAULT NULL,
            ADD COLUMN serial VARCHAR(15) DEFAULT NULL,
            ADD COLUMN street VARCHAR(50) DEFAULT NULL,
            ADD COLUMN village VARCHAR(50) DEFAULT NULL,
            ADD COLUMN province VARCHAR(50) DEFAULT NULL,
            ADD COLUMN municipality VARCHAR(50) DEFAULT NULL,
            ADD COLUMN last_check DATETIME DEFAULT CURRENT_TIMESTAMP
        """):
            return False
    Rslt =  db_query("SELECT first,coordinates FROM Sensors WHERE project = '%s' AND serial = '%s' AND active" % (ident['project'],ident['serial']), True)
    if not type(Rslt) is list:
        return False
    first = 'now()'
    fld_types = ''
    if ('description' in ident.keys()) and (ident['description'] != None):
        fld_types = ident['description']
    if ('types' in ident.keys()) and len(ident['types']):
        fld_types  += ";hw: %s" % ', '.join(ident['types'])
    if len(fld_types):
        fld_types ="'"+fld_types+"'"
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
            if item[1] == ident['geolocation']:
                db_query("UPDATE Sensors SET last_check = now(), active = 1, sensors = %s, description = %s WHERE coordinates like '%s%%'  AND serial = '%s'" % (fld_units,fld_types,','.join(ident['geolocation'].split(',')[0:2]),ident['serial']) , False)
                Conf["registrated"] = True
                MyLogger.log('ATTENT',"Registrated to database table Sensors.")
                db_WhereAmI(ident)
                return True
    db_query("UPDATE Sensors SET active = 0 WHERE project = '%s' AND serial = '%s'" % (ident['project'],ident['serial']),False)
    try:
        db_query("INSERT INTO Sensors (project,serial,coordinates,sensors,description,last_check,first) VALUES ('%s','%s','%s',%s,%s,now(),%s)" % (ident['project'],ident['serial'],ident['geolocation'],fld_units,fld_types,first),False)
    except:
        pass
    MyLogger.log('ATTENT',"New registration to database table Sensors.")
    Conf["registrated"] = True
    db_WhereAmI(ident)
    return True

# do a query
def db_query(query,answer):
    """ communicate in sql to database """
    global Conf
    # testCnt = 0 # just for testing connectivity failures
    # if testCnt > 0: raise IOError
    MyLogger.log('DEBUG',"DB query: %s" % query)
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
        MyLogger.log('ERROR',"MySQL Failure type: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
        return False
    return True

# check if table exists if not create it
def db_table(ident,table):
    """ check if table exists in the database if not create it """
    global Conf
    if (table) in Conf.keys():
        return True
    if (table,) in db_query("SHOW TABLES",True):
        Conf[table] = True
        return True
    # create database: CREATE DATABASE  IF NOT EXISTS mydb; by super user
    if not db_query("""CREATE TABLE %s_%s (
        id TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            COMMENT 'date/time latest change',
        datum datetime UNIQUE default NULL
            COMMENT 'date/time measurement'
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1
            COMMENT='Sensor located at: %s'""" % (ident['project'],ident['serial'],ident['geolocation']),False):
        Conf[table] = False
        MyLogger.log('ERROR',"Unable to create sensor table in database.")
    else:
        MyLogger.log('ATTENT',"Created table %s_%s" % (ident['project'],ident['serial']))
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
            MyLogger.log('FATAL',"Broker publish call missing argument %s." % key)

    # translate MySense filed names into MySQL column field names
    # TO DO: get the transaltion table from the MySense.conf file
    def db_name(my_name):
        DBnames = {
            'rh': 'rv',
            'pa': 'luchtdruk',  # deprecated
            'hpa': 'luchtdruk',
            'geo': 'geolocation',
            'wd':  'wr',
        }
        if my_name in DBnames.keys(): return DBnames[my_name]
        return my_name

    # check if fields in table exists if not add them
    def db_fields(types):
        global Conf
        if ("fields") in Conf.keys():
            return True
        Sensor_fields = {
            'geo':         "VARCHAR(25) default NULL",
            'pa':          "INT(11) default NULL",
            'hpa':         "INT(11) default NULL",
            'wd':          "SMALLINT(4) default NULL",
            'default':     "DECIMAL(7,2) default NULL",
            "_valid":      "BOOL default 1"
        }
        fields = types['fields']
        units = types['units']
        add = []
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
                MyLogger.log('ATTENT',"Added new field to table %s_%s" % (args['ident']['project'],args['ident']['serial']))
            except IOError:
                raise IOError
            except:
                MyLogger.log('FATAL',"Unable to add columns: %s" % ', '.join(add))
                Conf['output'] = False
                return False
        Conf["fields"] = fields
        return True

    if not db_connect(args['internet']):
        return False
    if not db_registrate(args['ident']):
        MyLogger.log('WARNING',"Unable to registrate the sensor.")
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
        if (not Fld in Args['data'].keys()) or (args['data'][Fld] == None):
            cols.append(Nm); vals.append("NULL")
        elif type(args['data'][Fld]) is str:
            cols.append(Nm); vals.append("'%s'" % args['data'][Fld])
        elif type(args['data'][Fld]) is list:
            # TO DO: this needs more thought
            MyLogger.log('WARNING',"Found list for sensor %s." % Fld)
            for i in range(0,len(args['data'][Fld])):
                nwe = "%s_%d" % (Nm,i,args['data'][Fld][i])
                if  not nwe in Fields:
                    # to do add column in database!
                    Fields.append(nwe)
                    Units.append('unit')
                cols.append("%s_%d" % (Nm,i)); vals.append(args['data'][Fld][i])
        else:
            cols.append(Nm)
            strg = "%6.2f" % args['data'][Fld]
            strg = strg.rstrip('0').rstrip('.') if '.' in strg else strg
            # strg = strg + '.0' if not '.' in strg else strg
            vals.append(strg)
    query += "(%s) " % ','.join(cols)
    query += "VALUES (%s)" % ','.join(vals)
    try:
        if db_query(query,False): ErrorCnt = 0
        else: ErrorCnt += 1
    except IOError:
        raise IOError
    except:
        MyLogger.log('ERROR','MySQL error in qry %s' % query)
        ErrorCnt += 1
    if ErrorCnt > 10:
        return False
    return True
