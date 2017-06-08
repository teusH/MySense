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

# $Id: MyRAW.py,v 1.7 2017/06/08 19:29:11 teus Exp teus $

# TO DO: write to file or cache
# reminder: InFlux is able to sync tables with other MySQL servers

""" Publish raw measurements to InFlux time series database or file
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyRAW.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.7 $"[11:-2]

try:
    import MyLogger
    import sys
    import os
    from influxdb import InfluxDBClient
    import datetime
    import threading
    from time import time
except ImportError as e:
    MyLogger.log(modulename,"FATAL","One of the import modules not found: %s" % e)

# configurable options
__options__ = ['raw','hostname','port','database','user','password','file']

# dict is defined in MySense.py instance as Conf['raw']
Conf = {
     'raw': False,        # raw output enabled?
     'hostname': 'localhost', # host InFlux server
     'user': None,        # user with insert permission of InFlux DB
     'password': None,    # DB credential secret to use InFlux DB
     'database': None,    # InFlux database/table name
     'port': 8086,        # default mysql port number
     'file': None,        # file to write to
     'fd': None,          # have sent to db: current fd descriptor, 0 on IO error
}

# ========================================================
# write data directly to a database
# ========================================================

# connect to db and keep connection as long as possible
# argument refers to MySense.py Conf['raw']
# TO DO: add lock on Conf as threading is used
def raw_connect():
    """ Connect to InFlux database and create filehandler """
    global Conf
    if (not 'database' in Conf.keys()) or (Conf['database'] == None):
        MyLogger.log(modulename,'FATAL', 'Database name not defined.')
    if not 'fd' in Conf.keys(): Conf['fd'] = None
    if (Conf['fd'] == None) or (not Conf['fd']):
        if (not 'file' in Conf.keys()) or (Conf['file'] == None): # to InFlux server
            for M in ('user','password','hostname'):
                if (not M in Conf.keys()) or not Conf[M]:
                    MyLogger.log(modulename,'FATAL','Please define details and credentials for InFlux host.')
            try:
                Conf['fd'] = InfluxDBClient(
                    Conf['hostname'],
                    8086 if not 'port' in Conf.keys() else Conf['port'],
                    Conf['user'], Conf['password'],
                    Conf['database'], timeout=2*60
                )
            except:
                MyLogger.log(modulename,'FATAL',"Publish admin failure type: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
        elif 'file' in Conf.keys():     # output to file
            if not Conf['file'][0] == '/': Conf['file'] = './' + Conf['file']
            if Conf['file'][0:5] != '/dev/':
                Conf['file'] += "_" + Conf['database'] + '.influx'
            if os.path.isdir(os.path.dirname(Conf['file'])):
                mode = 'w'
                if os.path.isfile(Conf['file']):
                    mode = 'a'
                try:
                    Conf['fd'] = open(Conf['file'],mode)
                except:
                    MyLogger.log(modulename,'FATAL',"Open raw measurements file, type: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
            else: MyLogger.log(modulename,'FATAL',"Unable to open raw measurements file %s" % Conf['file'])
    return True

def raw_write(data, tags, timing):
    ''' send telegram to InFlux server. Parameters came from reverse engineering
        of the http request
        tags are strings, data is int/float values
        measurement is type: info or data
        telegram structure: measurement,column=string,... column=int_float,...
    '''
    global Conf
    if not len(data): return True
    if len(tags): tags = 'type="%s"' % tags
    data = 'raw%s %s %d' % (tags,data,timing)
    if type(Conf['fd']) is file:
        try:
            # TO DO: add lock on write as threading is used
            Conf['fd'].write("%s\n" % data)
            Conf['fd'].flush()
            return True
        except:
            MyLogger.log(modulename,'ERROR',"Failed to wite record to raw InFluxDB file. Error: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
        return False
    else:
        try:
            return Conf['fd'].request('write','POST',{'db':Conf['database'],'precision':'ms'},data,204)
        except:
            MyLogger.log(modulename,'ERROR',"Publish raw data request error: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
    return False

# registrate the sensor to the Sensors table and update location/activity
def raw_registrate():
    global Conf
    """ get access for raw measurements to file or InFlux DB """
    Conf['lock'].acquire()
    if ("DoRaw" in Conf.keys()) and (Conf['DoRaw'] != None):
        Conf['lock'].release()
        return Conf['DoRaw']
    if (not 'database' in Conf.keys()) or (Conf['database'] == None):
        if ('project' in Conf.keys()) and ('serial' in Conf.keys()):
            Conf['database'] = Conf['project'] + '_' + Conf['serial']
        else:
            Conf['lock'].release()
            return False
    if not raw_connect():
        Conf['lock'].release()
        return False
    Conf["DoRaw"] = True
    Conf['ErrorCnt'] = 0
    Conf['lock'].release()
    return True

# simple way to check correctness of field record for InFlux query data format
def checkData(field):
    if not len(field): return ''
    fields = field.split(',')
    for i in range(len(fields)-1,-1,-1):
        if fields[i].count('=') != 1:
            fields.pop(i)
        (unused,v) = fields[i].split('=')    # v should be int or float
        if not v.replace('.','').isdigit(): fields.pop(i)
    fields = ','.join(fields)
    if len(field) != len(fields):
        MyLogger.log(modulename,'ATTENT','Changed raw measurements data %s -> %s.' % (field,fields))
    return fields

def publish(**args):
    global Conf
    """ add raw measurement records to the database or file,
        on the first update table Sensors with ident info.
        arguments:
        data=string(sensor1=value1,...), tag=string(sensor type name)
    """
    for key in ['data','tag']:
        if not key in args.keys():
            MyLogger.log(modulename,'FATAL',"Publish call missing argument %s." % key)
            return False
    args['data'] = checkData(args['data'])
    if not len(args['data']): return True       # no record to publish
    if not 'lock' in Conf.keys(): Conf['lock'] = threading.Lock()
    if Conf['fd'] == None: Conf['DoRaw'] = None
    if not raw_registrate():
        MyLogger.log(modulename,'WARNING',"Unable to registrate for raw measurements.")
        return False
    if Conf['fd'] == None: return False
    timing = time()
   
    Conf['lock'].acquire()
    if Conf['ErrorCnt'] > 10:
        if  (Conf['ErrorCnt']%10) == 1:
            MyLogger.log(modulename,'ERROR','Raw measurements write errors.')
        if timing - Conf['last'] < 5*60*60:     # wait 5 minutes
            Conf['lock'].release()
            return False
    if not raw_write(
            args['data'],
            args['tag'],
            int(timing*1000)
          ):
        Conf['ErrorCnt'] += 1
        if not 'last' in Conf.keys(): Conf['last'] = timing
        Conf['lock'].release()
        MyLogger.log(modulename,"ATTENT","Writing data records to failed.")
        return False
    if 'last' in Conf.keys(): del Conf['last']
    Conf['ErrorCnt'] = 0
    Conf['lock'].release()
    return True

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['database'] = 'BdP_f46d04af97ab'  # make sure InFluxdb server has the database
    Conf['hostname'] = 'localhost'         # host InFluxdb server
    Conf['user'] = 'ios'                   # user with insert permission of InFlux DB
    Conf['password'] = 'acacadabra'        # DB credential secret to use InFlux DB
    #Conf['file'] = 'raw_test'

    data = [ # test data
        'pm10=20.1,pm25=1002.0,rh=20',
        'pm10=15.3,rh=80.1',
    ]

    for cnt in range(0,len(data)):
        try:
            publish(
                tag='sensor', data=data[cnt],
            )
        except Exception as e:
            print("output channel error was raised as %s" % e)
            break
        sleep(2)

