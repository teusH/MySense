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

# $Id: MyGPS.py,v 2.14 2018/05/12 09:27:59 teus Exp teus $

# TO DO:
#

""" Get geo location and time from GPSD daemon
    Works with a thread to collect geo data
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyGPS.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.14 $"[11:-2]

import os
from time import time, sleep
from types import ModuleType as module
import threading
try:
    import MyLogger
except ImportError as e:
    MYLogger.log('FATAL',"Missing module %s" %e)

# configurable options
__options__ = [
        'input',
        'host','port',
        'raw',
        'interval','sync'
]

Conf = {
    'input': False,     # no GPS installed
    'type': 'GPSd',     # type of geolocator module
    'fields': ['geo','time'],
    'units': ['r,r,m','s'],# radials or d (degrees)
    'host': '127.0.0.1',# default gspd service
    'port': 2947,       # default unix socket port for gpsd
    'interval': 60,     # read location every interval seconds
    'sync': False,	# get geo info in sync with main process
    'raw': False,       # print raw measurements
    'debug': False,     # be more versatile
}

MyThread = None         # ref to GPS class, may run asynchronous
GPSthreads = None       # geo multi thread if activated

class GPSthread(threading.Thread):
    from gps3 import gps3
    from time import time, sleep

    STOP = False
    threadLock = threading.Lock() # lock to be used for average of values in buffer

    def __init__(self, **args):
        threading.Thread.__init__(self)
        inits = {}                  # defaults
        inits['interval'] = 5       # internal max minutes interval for new values
        inits['DEBUG'] = False      # be more versatile
        inits['host'] = '127.0.0.1' # localhost gpsd socket
        inits['port'] = '2947'      # default GPS daemon port
        inits['sync'] = False       # run in multi threaded modus
        inits['raw'] = False        # display raw geo values
        for key in args.keys():
            inits[key] = args[key]
        self.TINTERV = inits['interval']  # internal max interval for new values
        self.DEBUG = inits['DEBUG']       # debug modus
        self.host = inits['host']
        self.port = inits['port']
        self.name = 'GPS client'
        self.sync = inits['sync']
        self.raw = inits['raw']
        self.cur_val = {}                 # current location record

    def getRecord(self):
        for i in range(0,5):
            with self.threadLock:
                if len(self.cur_val):
                    return {
                       'time': self.cur_val['time'],
                       'geo': self.cur_val['geo'],
                       }
            self.sleep(1)
        return {}

    def GPSstart(self):
        prev_t = int(self.time()) ; prev_l = ['lat','lon','alt']
        GPSdata = None
        GPSsock = None
        GPSdata = self.gps3.DataStream()
        GPSsock = self.gps3.GPSDSocket()
        GPSsock.connect()
        GPSsock.watch()
        for new_data in GPSsock:
            if self.STOP: return
            if new_data:
                GPSdata.unpack(new_data)
	        if GPSdata.TPV['device'] == 'n/a':
		        continue
                rec = { 'time': int(self.time()) }
                geo = []
                rvals = []
                for item in ['lat','lon','alt']:
                    if GPSdata.TPV[item] != 'n/a':
                        try:
                            val = float(GPSdata.TPV[item])
                            # altitude is +- 5 meters
                            # TO DO: add distance calculation
                            if item != 'alt': strg = '%8.5f' % val
                            else: strg = '%8.1f' % val
                            strg = strg.rstrip('0').rstrip('.') if '.' in strg else strg
                            strg = strg + '.0' if not '.' in strg else strg
                            strg = strg.strip(' ')
                            geo.append(strg)
                            rvals.append('%s=%s' % (item, strg.replace(' ','')))
                        except:
                            pass
                    elif self.DEBUG:
                        print("Got for %s geo 'n/a'" % item)
                if len(geo) == 3:
                    rec['geo'] = ','.join(geo)
                    if self.DEBUG:
                        print("Got new GPS rec: %s (lat,lon,alt)" % rec['geo'])
                    if (prev_l[0] != geo[0]) or (prev_l[1] != geo[1]):
                        prev_t = rec['time']; prev_l = geo
                        with self.threadLock: self.cur_val = rec
                        if (type(self.raw) is module) and len(geo):
                            self.raw.publish(
                                tag='geo',
                                data='lat=%s,lon=%s,alt=%s' % (geo[0],geo[1],geo[2])
                                )
                        if self.sync:
                            GPSsock.close()
                            GPSsock = None
                            return
                    # slow down if no change in TINTERV minutes
                    elif rec['time'] - prev_t > self.TINTERV:
                        if not self.sync:
                            with self.threadLock: self.cur_val['time'] = 0
                            GPSsock.close();
                            return

    def GPSclient(self):
        while not self.STOP:
            try:
                self.GPSstart()
                self.sleep(0.5)	# allow client time to start collecting
            except:
                raise IOError("GPS daemon is disconnected")
                self.STOP = True
            if self.sync:
                return
            if self.DEBUG:
                print("Long time sleep")
            if not self.STOP: self.sleep(self.TINTERV)
        return

# initialize
def start_thread():
    from time import sleep
    global Conf, MyThread, GPSthreads
    if MyThread.STOP:
        return True
    if not Conf['sync']:
        try:
            GPSthreads = threading.Thread(target=MyThread.GPSclient)
            GPSthreads.start()
        except StandardError as e:
            MyLogger.log(modulename,'ERROR',"Unable to start thread." % e)
            return False
        sleep(1)      # allow some data to come in
    return True

def stop_thread():
    MyThread.STOP = True        # ask self threads to stop
    try:
        threading.join()
    except:
        pass
    MyLogger.log(modulename,'WARNING',"Stopped thread.")
    return

# set inital configuration values and ready GPSD thread
def registrate():
    global Conf, MyThread
    if not Conf['input']: return False
    if MyThread != None:
        return True
    Conf['input'] = True
    if MyThread == None:        # only once
        try:
            MyThread = GPSthread(
                interval=Conf['interval'],
                port = Conf['port'],
                host=['host'],
                sync=Conf['sync'],
                raw=Conf['raw'],
                DEBUG=Conf['debug'])
            # first call is interval secs delayed by definition
            if Conf['sync']: return True
            if start_thread():
                return True
        except:
            pass
        MyThread = None
    raise IOError("Unable to registrate/start GPS thread.")
    Conf['input'] = False
    return False

# get data from GPSD thread
def getdata():
    """ getdata() is interface to collect GPS data:
	{time(long:seconds), geo(string:lat,lon,alt) }
    """
    global Conf, MyThread
    if not registrate():                # start up input readings
        return {}
    try:
        if Conf['sync']: MyThread.GPSclient()
        rec = MyThread.getRecord()     # pick up a record
        if not 'geo' in rec.keys():
            return {}                  # for 5 minutes no geo change
        return rec
    except IOError as er:
        MyLogger.log(modulename,'WARNING',"Sensor input failure: %s" % er)
    return {}

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['input'] = True
    # Conf['sync'] = True      # sync = False will start async collect
    Conf['debug'] = True       # True will print GPSD collect info from thread
    Conf['raw'] = True
    for cnt in range(0,10):
        timing = time()
        try:
            data = getdata()  # get geo info from thread
        except Exception as e:
            print("input sensor error was raised as %s" % e)
            break
        print("Getdata returned:")
        print(data)
        timing = 15 - (time()-timing)
        if timing > 0:
            if Conf['debug']:
                print("Slowing down for %d/15 seconds for new cycle." % timing)
            sleep(timing)
    if (not Conf['sync']) and (MyThread != None):
        MyThread.stop_thread()
