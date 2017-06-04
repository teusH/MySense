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

# $Id: MyINFLUXSUB.py,v 1.4 2017/06/04 09:40:55 teus Exp teus $

"""
    Get sensor values from InFlux server. Needs influxdb python client module.
    Relies on Conf setting by main program
    InFluxDB versions differ and are not downwards compatible,  so check the API!
    This version is based on InFluxDB version V1.2
"""
# due to some unknown reason some influxdb do not work, so we use lower support
# functions sometimes

# TO DO: we should keep track on latest records in order a restart will not start all over

modulename='$RCSfile: MyINFLUXSUB.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.4 $"[11:-2]

# configurable options
__options__ = [
    'input',
    'hostname',          # server host name of server
    'port',              # port number
    'user',              # username for access
    'password',          # user password for access
    'projects',          # projects match expression
    'serials',           # serial number match expression
    'bufsize',           # multithead buffer size and search for input
    'update',            # interval to update current databases list from server
    'state',             # file with saved state of InFlux subscriber
]

Conf = {
    'input': False,      # Dylos input sensor is required
    'fd': None,          # input handler
    'hostname': 'localhost', # InFlux server hostname
    'port': 8086,        # InFlux server port number
    'user': None,        # username of credentials
    'password': None,    # user password for access cvredentials
    'projects': '.*',    # string match expression projects
    'serials': '.*',     # string match expression serial numbers
    'bufsize': 100,      # size of the window of values readings max
    'debug': False,      # be more versatile on input data collection
    'update': 60*60,     # interval in secs to update current db list from server, dflt 1h
    'state': None,       # file with saved InFlux subscriber state in JSON

}
#    from MySense import log
try:
    import os
    import re
    import sys
    import atexit
    import json
    from time import time
    from time import sleep
    from time import strptime # InFlux uses RFC 339 time format Zulu timezone
    from time import mktime
    import datetime
    import socket
    socket.setdefaulttimeout(60)
    import MyLogger
    from influxdb import InfluxDBClient
    import subprocess           # needed to find the USB serial
    import MyThreading          # needed for multi threaded input
except ImportError as e:
    MyLogger.log(modulename,'FATAL',"Missing module %s" % e)

# module data records info and buffer space
# Conf['databases'] is used as resource, filled with databases to be subscribed to
# DBlist is ordered row of databases to be visited
DBlist = []             # ordered (the to-do) list of DBs to be visited
lastDB = None           # database name last used
DataRecords = []        # measurement records for lastDB
# InfoRecords is list of databases and current ident info record
# keys: infoStamp last handled ident info InFlux timestamp
#       dataStamp last handled data record InFlux time stamp
#       ident current ident info record linked to data record
#       new: flag from data record to renew info ident record
InfoRecords = {}        # keys: database name and latest time of records
StateInJson = None      # Info state (InfoRecords)  in json string format

def create_list(projects,serials):
    if projects[0] == '(': projects = projects[1:]
    if projects[-1] == ')': projects = projects[:-1]
    projects = projects.split('|')
    if serials[0] == '(': serials = serials[1:]
    if serials[-1] == ')': serials = serials[:-1]
    serials = serials.split('|')
    databases = []
    for pr in projects:
        for sr in serials: databases.append(pr + '_' + sr)
    return databases

def db_exists(name):
    ''' database should have data and info series '''
    global Conf
    try:
        # on failure it is not my database, returns something like:
        # [{'name': 'results',
        #           'tags':
        #            [{u'key': u'data,geolocation="41.2134\\,5.121\\,23",new=0'},
        #             {u'key': u'data,geolocation="41.2134\\,5.121\\,23",new=1'},
        #             {u'key': u'info'}
        #            ]}
        #]
        response = Conf['fd'].get_list_series(name)
    except:
        return False
    try:
        for item in response:
            needs = ['data','info']
            for db in item['tags']:
                try:
                    needs.remove(db['key'].split(',')[0])
                except:
                    pass
                if not len(needs): return True
    except:
        pass
    return False

# routines to notify if we should slow down in a new server access try
def waitReset():
    global Conf
    Conf['waiting'] = 5*30; Conf['last'] = 0; Conf['waitCnt'] = 0

def wait():
    global Conf
    Conf['waitCnt'] += 1
    if not Conf['waitCnt']%5: Conf['waiting'] *= 2
    if not Conf['last']: Conf['last'] = int(time())

def shouldWait():
    global Conf
    if not 'waitCnt' in Conf.keys(): waitReset()
    if not Conf['waitCnt']: return False
    if int(time()) - Conf['last'] >= 24*60*60:    # one day wait is max
        raise IOError('Cannot get connection in one day time')
    return int(time()) - Conf['last'] < Conf['waiting']

def db_list():
    global Conf
    try:
        db_re = re.compile(Conf['projects'] + "_" + Conf['serials'], re.I)
        if not 'databases' in Conf.keys(): Conf['databases'] = []
        # on failure no admin right
        response = Conf['fd'].get_list_database()
        # returns [{ u'name': u'this db name'}, ...]
        for item  in response:
            if item['name'][0] == '_': continue
            if db_re.match(item['name']):
                if not item in Conf['databases']: Conf['databases'].append(item['name'])
    except:     # error on no admin acces on Influ DB, guess a list of names from ('name1'|..)
        if not len(Conf['databases']):
            MyLogger.log(modulename,'ATTENT',"Publish admin failure type: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
        for item in create_list(Conf['projects'],Conf['serials']):
            if not item in Conf['databases']: Conf['databases'].append(item)
    for i in range(len(Conf['databases'])-1,-1,-1):
        if not db_exists(Conf['databases'][i]): Conf['databases'].pop(i)
    Conf['updated'] = time()
    if len(Conf['databases']):
        MyLogger.log(modulename,'ATTENT','Has access to: %s' % ', '.join(Conf['databases']))
        return True
    MyLogger.log(modulename,'ERROR','%s server, user %s: no databases with allowed access.' % (Conf['hostname'],Conf['user']))
    return False

def InFluxConnect():
    """ Connect to InFlux database and save filehandler """
    global Conf
    for item in ['fd','updated']:
        if not item in Conf.keys(): Conf[item] = None
    if Conf['fd'] != None: return True
    waitReset()
    for key in ['user','password','hostname']:
        if (not key in Conf.keys()) or (Conf[key] == None):
            Conf['input'] = False
            MyLogger.log(modulename,'FATAL',"Missing login %s credentials." % key)
            return False
    try:
        Conf['fd'] = InfluxDBClient(
            Conf['hostname'], Conf['port'],
            Conf['user'], Conf['password'],
            timeout=2*60)
        return db_list()
    except:
        MyLogger("FATAL","InFlux subscription failed")
    return True

#MyThread = None
def registrate():
    global Conf, StateInJson
    if not Conf['input']: return False
    if Conf['fd'] != None: return True
    if shouldWait(): return False
    Conf['input'] = False
    if not InFluxConnect(): return False
    if (StateInJson == None) and Conf['state']:
        InitInfo()  # try to load state
        atexit.register(SaveState, Conf['state'],StateInJson)
    Conf['input'] = True
    return True

# remember where we were while reading records from InFlux server
def SaveState(path,jsonString):
    ''' write current subscribe state into a file '''
    if jsonString == None or path == None: return True
    try:
        fd = open(path,'w')
        fd.write(jsonString)
        fd.close()
        # print('ATTENT: InFlux subscriber: saved state into %s' % path)
    except:
        MyLogger.log(modulename,'ERROR','Failed to write state into %s.' % path)
        pass

nextSave = 0
def RememberInfo():
    ''' turn current info state into json string '''
    global Conf, InfoRecords, StateInJson, modulename, __version__, nextSave
    if len(InfoRecords):
        StateInJson = json.dumps({
                'from': modulename,
                'version': __version__,
                'time': int(time()),
                'InfoRecords': InfoRecords,
             })
    if time() >= nextSave:
        nextSave = time() + Conf['update']         # once per hour we save state
        SaveState(Conf['state'],StateInJson)
    else: StateInJson = None
    return True

from os.path import exists
def InitInfo():
    ''' load saved state for InFlux subscribe, so we start from last records '''
    global InfoRecords, lastDB, StateInJson
    if Conf['state'] == None: return True
    try:
        fd = open(Conf['state'],'r')
        state = fd.read()
        state = json.loads(state)
        if (not 'from' in state.keys()) or (state['from'] != modulename):
            raise ValueError
        if (not 'version' in state.keys()) or (state['version'][0] != __version__[0]):
            raise ValueError
        InfoRecords =  state['InfoRecords']
        MyLogger.log(modulename,'ATTENT','Loaded subscriber state file: %s (d.d. %s)' % (Conf['state'],datetime.datetime.fromtimestamp(state['time']).strftime('%Y-%m-%d %H:%M:%S')))
        StateInJson = None
        RememberInfo()
    except:
        if exists(Conf['state']):
            MyLogger.log(modulename,'ERROR','Failed to load state file: %s' % Conf['state'])
            return False
        else:
            MyLogger.log(modulename,'ATTENT','Will save state in new file: %s' % Conf['state'])
    return True

def initInfo(database):
    global InfoRecords
    InfoRecords[database] = {
        'ident': {},
        'infoStamp': 0, 'dataStamp': 0,
        'lastTime': int(time()) - Conf['update'],
    }

def doQuery(database,query):
    global InfoRecords
    # expect info response as:
    # [{
    #   u'time': u'2017-05-23T14:13:38Z',
    #   u'geolocation': u'41.134\\,15.121\\,23',
    #   u'fields': u'time\\,pm25\\,pm10\\,spm25\\,spm10',
    #   u'extern_ip': u'38.116.115.20',
    #   u'project': u'BdP',
    #   u'units': u's\\,pcs/qf\\,pcs/qf\\,pcs/qf\\,pcs/qf',
    #   u'serial': u'33004d45',
    #   u'types': u'PPD42NS\\,Nova SDS011'
    # }]
    # expect data response as:
    # [{u'spm25': 866, u'geolocation': u'"31.1234,30.112,23"', u'pm10': None,
    #   u'timestamp': None, u'spm10': 6.5, u'time': u'2017-05-19T21:24:15Z',
    #   u'new': u'1', u'pm25': 375},
    # {u'spm25': 882, u'geolocation': u'"31.1234,30.112,26"', u'pm10': None,
    #   u'timestamp': 1.495998546e+9, u'spm10': 6.667, u'time': u'2017-05-19T21:30:36Z',
    #   u'new': u'0', u'pm25': 162}, ... ]
    try:
        response = list(Conf['fd'].query(query,database=database,expected_response_code=200).get_points())
        waitReset()
    except:
        MyLogger.log(modulename,'ERROR',"Query data request error: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
        wait()
        return []
    timing = None
    if not database in InfoRecords.keys():
        MyLogger('FATAL','InFlux sub script internal error')
    if len(response): # no explode needed
        for i in range(0,len(response)):
            if 'time' in response[i].keys():
                timing = int(mktime(strptime(response[i]['time'].replace('Z','UTC'),'%Y-%m-%dT%H:%M:%S%Z')))
                response[i]['InFluxStamp'] = timing   # keep track of InFlux timestamp
                del response[i]['time']
            if 'timestamp' in response[i].keys():
                if response[i]['timestamp'] == None:
                    response[i]['timestamp'] = timing
                if not type(response[i]['timestamp']) is str:
                    response[i]['time'] = int(response[i]['timestamp'])
                if not 'time' in response[i].keys():
                    response[i]['time'] = timing
                del response[i]['timestamp']
            if 'new' in response[i].keys():
                if response[i]['new'] == '1':
                    if (not i) and (timing-10 > InfoRecords[database]['infoStamp']):
                        getIdent(database,timing-10)
                    elif i:
                        del response[i:]
                        break
                del response[i]['new']
    if timing == None:
        timing = time()
    InfoRecords[database]['lastTime'] = int(timing)
    return response

import pytz
def Time2RFC3339(timing):
    return pytz.utc.localize(datetime.fromtimestamp(timing)).strftime('%Y-%m-%dT%H:%M:%SZ')

def getIdent(database,timing):
    global Conf, InfoRecords
    ''' get meta info for this database from InFlux server '''
    query = 'SELECT * FROM "info"'
    if not timing or InfoRecords[database]['infoStamp'] == 0:
         query += ' ORDER BY "time" DESC'
    elif timing:
        query += ' WHERE "time" > %d' % timing
    else:
         # query += ' WHERE "time" > "%s"' % Time2RFC3339(InfoRecords[database]['infoStamp'])
         query += ' WHERE "time" > %d' % InfoRecords[database]['infoStamp']
    query += ' LIMIT 1'
    rts = doQuery(database,query)
    if not len(rts):
        MyLogger.log(modulename,'ERROR','Unable to get ident info')
        return False
    if 'InFluxStamp' in rts[0].keys(): # for recovery need InFlux time stamp
        InFluxTime = rts[0]['InFluxStamp']
        del rts[0]['InFluxStamp']
    else: InFluxTime = None
    InfoRecords[database].update({
                              'ident': rts[0],
                              'infoStamp': InFluxTime,
                              'dataStamp': InFluxTime,
                              'lastTime': InFluxTime,
                                })
    return True

def getData(database):
    global Conf, InfoRecords, DataRecords
    if len(DataRecords): return True
    if not database in InfoRecords.keys():
        MyLogger.log(modulename,'WARNING','No ident info for db: %s' % database)
        initInfo(database)
        getIdent(database,0)
    ''' get an array of data values from the InFlux server '''
    query = 'SELECT * FROM "data"'
    timestamp = InfoRecords[database]['lastTime']
    if InfoRecords[database]['dataStamp'] and timestamp:
        if timestamp < InfoRecords[database]['dataStamp']:
            timestamp = InfoRecords[database]['dataStamp']
    if timestamp:
        # query += ' WHERE "time" > "%s"' % Time2RFC3339(timestamp)
        query += ' WHERE "time" > %d' % timestamp
    query += ' LIMIT %d' % Conf['bufsize']
    DataRecords = doQuery(database,query)
    if not len(DataRecords):
        return False
    return True

def GetNextRecord():
    ''' get next record from DataRecords and InfoRecords.
        if DataRecords is empty find next database and download DataRecords
        from last time downloaded. On first download try from InfoRecord time
    '''
    global DataRecords, InfoRecords, lastDB, DBlist, Conf
    identTried = 0
    while True:
        if Conf['updated'] + Conf['update'] < time():    # (re)download list of DBs
            db_list()      # get list of databases
            # update internal cache of idents
            for item in InfoRecords.keys():
                if not item in Conf['databases']:
                    if lastDB == item:
                        lastDB = None
                        DataRecords = []
                        del InfoRecords[item]
            for item in InfoRecords.keys():
                if not item in Conf['databases']:
                    if item == lastDB:
                        lastDB = None; DataRecords = []
                    del InfoRecords[item]
            for item in Conf['databases']:
                if not item in InfoRecords.keys():   # initialise info struct
                    initInfo(item)
                if not len(DataRecords): lastDB = item
        if not len(DataRecords):                 # download data records to bufsize
            if not len(DBlist):
                DBlist = list(Conf['databases']) # init working list of waiting DBs
            if not len(DBlist):
                MyLogger('ERROR','No Influx database to subscribe to')
                Conf['input'] = False
                return {}
            for item in DBlist:                  # pickup oldest in row waiting
                if lastDB == None: lastDB = item
                if not item in InfoRecords.keys():  # initialize info struct
                    initInfo(item)
                if InfoRecords[item]['lastTime'] < InfoRecords[lastDB]['lastTime']:
                    lastDB = item
            # not handled: buffer empty and new ident records just collected
            if not len(InfoRecords[lastDB]['ident']):
                if not getIdent(lastDB,0): # nothing there yet
                    DBlist.remove(lastDB); lastDB = None
                    continue
            # there is at least one db with identication info
            if not getData(lastDB):
                DBlist.remove(lastDB); lastDB = None
                continue
        if 'InFluxStamp' in DataRecords[0].keys():
            InfoRecords[lastDB]['dataStamp'] = DataRecords[0]['InFluxStamp']
            del DataRecords[0]['InFluxStamp']
        else:
            InfoRecords[lastDB]['dataStamp'] = 0
        RememberInfo()
        return { 'register': InfoRecords[lastDB]['ident'], 'data': DataRecords.pop(0) }
        
def getdata():
    global Conf, MyThread, ErrorCnt
    if (not Conf['input']):
        sleep(10)
        return {}
    if not registrate():                # start up input readings
        return {}
    try:
        return GetNextRecord()
    except IOError:
        raise IOError("Unable to contact InFlux server %s" % Conf['host'])
    except:
        MyLogger('DEBUG','InFlux sub should wait for  %d seconds' % Conf['waiting'])
        shouldWait()
        return {}

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['input'] = True
    Conf['hostname'] = 'lunar'
    Conf['user'] = 'teus'
    Conf['password'] = 'live4ever'
    Conf['projects'] = 'BdP'
    Conf['serials'] = '3.{7}'
    Conf['bufsize'] = 5
    Conf['debug'] = True
    Conf['state'] = './InFluxSubscriber_state.json'
    for cnt in range(0,25):
        timing = time()
        try:
            data = getdata()
        except Exception as e:
            print("input sensor error was raised as %s" % e)
            break
        print("Getdata returned:")
        print(data)
        timing = 2 - (time()-timing)
        if timing > 0:
            sleep(timing)
    SaveState(Conf['state'],StateInJson)

