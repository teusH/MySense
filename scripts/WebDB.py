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

# $Id: WebDB.py,v 1.1 2020/04/30 14:20:15 teus Exp teus $

# TO DO: write to file or cache
# reminder: MySQL is able to sync tables with other MySQL servers

""" Publish measurements to MySQL database
    Relies on Conf setting by main program
"""
modulename='$RCSfile: WebDB.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.1 $"[11:-2]

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
__options__ = ['output','hostname','port','db','user','password']

Conf = {
    'output': False,
    'hostname': 'localhost', # host MySQL server
    'user': None,        # user with insert permission of MySQL DB
    'password': None,    # DB credential secret to use MySQL DB
    'db': None,          # MySQL database name
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
        # get WEBUSER, WEBHOST, WEBPASS from process environment if present
        for credit in ['hostname','user','password','db']:
            if not credit in Conf.keys():
                Conf[credit] = None
            try:
                Conf[credit] = os.getenv('WEB'+credit[0:4].upper(),Conf[credit])
            except:
                pass
        Conf['log'](modulename,'INFO','Using database %s on host %s, user %s credits.' % (Conf['db'],Conf['hostname'],Conf['user']))
        if (Conf['hostname'] != 'localhost') and ((not net['module']) or (not net['connected'])):
            Conf['log'](modulename,'ERROR',"Access database %s / %s."  % (Conf['hostname'], Conf['db']))      
            Conf['output'] = False
            return False
        for M in ('user','password','hostname','db'):
            if (not M in Conf.keys()) or not Conf[M]:
                Conf['log'](modulename,'ERROR',"Define WEB details and credentials.")
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
                database=Conf['db'],
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

# do a query
Retry = False
# returns either True/False or an array of tuples
def db_query(query,answer):
    """ communicate in sql to database """
    global Conf, Retry
    if (not 'fd' in Conf.keys()) or not Conf['fd']: db_connect()
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

# check if table exists if not create it
def db_table(table):
    """ check if table exists in the database if not create it """
    global Conf
    if (not 'fd' in Conf.keys()) and not Conf['fd']:
        try: db_connect()
        except:
            Conf['log'](modulename,'FATAL','No MySQL WEB connection available')
            return False
    if (table) in Conf.keys():
        return True
    if table in [str(r[0]) for r in db_query("SHOW TABLES",True)]:
        Conf[table] = True
        return True
    return False

# test main loop
if __name__ == '__main__':
    from time import sleep
