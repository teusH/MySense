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

# $Id: MyGPS.py,v 2.8 2017/02/22 09:50:10 teus Exp teus $

# TO DO:
#

""" Get geo location and time from GPSD daemon
    Works with a thread to collect geo data
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyGPS.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.8 $"[11:-2]

import os
from time import time, sleep
import threading
try:
    import MyLogger
except ImportError as e:
    MYLogger.log('FATAL',"Missing module %s" %e)

# configurable options
__options__ = [
        'input',
        'interval','sync'
]

Conf = {
    'input': False,     # no GPS installed
    'type': 'GPSd',     # type of geolocator module
    'fields': ['geo','time'],
    'units': ['r,r,m','s'],# radials or d (degrees)
    'host': '127.0.0.1',# default gspd service
    'port': 2947,       # default unix socket port for gpsd
    'interval': 1,      # read location every interval seconds
    'sync': False,	# get geo info in sync with main process
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
        for key in args.keys():
            inits[key] = args[key]
        self.TINTERV = inits['interval']  # internal max interval for new values
        self.DEBUG = inits['DEBUG']       # debug modus
        self.host = inits['host']
        self.port = inits['port']
        self.name = 'GPS client'
        self.sync = inits['sync']
        self.cur_val = {}                 # current location record

    def getRecord(self):
        for i in range(0,3):
            with self.threadLock:
                if len(self.cur_val):
                    return {
                       'time': self.cur_val['time'],
                       'geo': self.cur_val['geo'],
                       }
            self.sleep(1)
        return {}

    def GPSstart(self):
        prev_t = int(time()) ; prev_l = '0.0,0.0,0'
        GPSdata = None
        GPSsock = None
        GPSsock = self.gps3.GPSDSocket()
        GPSdata = self.gps3.DataStream()
        GPSsock.connect()
        GPSsock.watch()
        for new_data in GPSsock:
            if self.STOP: return
            if new_data:
                GPSdata.unpack(new_data)
	        if GPSdata.TPV['device'] == 'n/a':
		        continue
                rec = { 'time': int(time()) }
                geo = []
                for item in ['lat','lon','alt']:
                    if GPSdata.TPV[item] != 'n/a':
                       strg = '%13.7f' % float(GPSdata.TPV[item])
                       strg = strg.rstrip('0').rstrip('.') if '.' in strg else strg
                       strg = strg + '.0' if not '.' in strg else strg
                       strg = strg.strip(' ')
                       geo.append(strg)
                    elif self.DEBUG:
                        print("Got for %s geo 'n/a'" % item)
                if len(geo) == 3:
                    geo = ','.join(geo)
                    rec['geo'] = geo
                    if prev_l != rec['geo']:
                        prev_t = rec['time']
                        if self.DEBUG:
                            print("Got GPS rec: %s (lat,lon,alt)" % rec['geo'])
                        with self.threadLock: self.cur_val = rec
                        if self.sync:
                            GPSsock.close()
                            return
                    # slow down for an hour if no change in TINTERV minutes
                    elif rec['time'] - prev_t > self.TINTERV*60:
                        with self.threadLock: self.cur_val['time'] = 0
                        GPSsock.close()
                        GPSsock = None

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
            if forever and (not self.STOP): self.sleep(60*60)
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
            MyLogger.log('ERROR',"Unable to start GPS thread." % e)
            return False
        sleep(1)      # allow some data to come in
    return True

def stop_thread():
    MyThread.STOP = True        # ask self threads to stop
    try:
        threading.join()
    except:
        pass
    MyLogger.log('WARNING',"Stopped GPS thread.")
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
        if rec['time'] == 0:
            return {}                  # for 5 minutes no geo change
        return rec
    except IOError as er:
        MyLogger.log('WARNING',"Sensor GPS input failure: %s" % er)
    return {}

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['input'] = True
    #Conf['sync'] = True      # sync = False will start async collect
    #Conf['debug'] = True     # True will print GPSD collect info from thread
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
