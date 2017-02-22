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

# $Id: MyDBGROVE.py,v 2.1 2017/02/21 19:19:03 teus Exp teus $

# TO DO: make a threat to read every period some values
# DHT import module can delay some seconds

""" Get loudness measurements from Grove family of Adafruit chips
    Measurements have a calibration factor (calibrated to dB meter?)
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyDBGROVE.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.1 $"[11:-2]
__license__ = 'GPLV4'

try:
    from time import time
    import MyThreading          # needed for multi threaded input
    import MyLogger
    import grovepi
    import math
    import json
except ImportError:
    MyLogger.log('FATAL',"Missing modules for %" % modulename)

# configurable options
__options__ = [
    'input','port','type','calibrations',
    'interval','bufsize','sync']       # multithead buffer size and search for input secs

Conf ={
    'input': False,      # no loudnes sensors installed
    'type': None,        # type of the lodness chip eg Grove dB
    'fields': ['db'],    # filtered audio loudness
    'units' : ['dB'],    # dB
    'calibrations' : [[0,1]], # calibration factors, here order 1
    'port': None,        # Analog port of GrovePi
    'interval': 30,      # read lodness interval in secs (dflt)
    'bufsize': 20,       # size of the window of values readings max
    'sync': False,       # use thread or not to collect data
    'debug': False,      # be more versatile
#    'fd' : None         # input handler
}

# get calibration factors
# convert calibration json string into array obect
def get_calibrations():
    global Conf
    if (not 'calibrations' in Conf.keys()) or (not type(Conf['calibrations']) is str):
        return
    Conf['calibrations'] = json.loads(Conf['calibrations'])

# calibrate as ordered function order defined by length calibraion factor array
def calibrate(nr,value):
    global Conf
    if math.isnan(value):
        return None
    if (not 'calibrations' in Conf.keys()) or (nr > len(Conf['calibrations'])-1):
        return value
    rts = 0; pow = 0
    for a in Conf['calibrations'][nr]:
        rts += a*(value**pow)
        pow += 1
    return round(rts,1)

# get a record, called back from sensor thread with average of sliding window bufsize
def Add():
    global Conf
    try:
        db = grovepi.analogRead(Conf['fd'])
        if Conf['debug']:
            print("Grove dB: %d" % db)
    except:
        MyLogger('ERROR',"Grove dB access error.")
        return {'time': int(time()),'db':None}
    #MyLogger.log('DEBUG',"Loudness (dB) : {0:0.1f} not calibrated".format(db))
    db = calibrate(0,db)
    rec = {'time': int(time()),'db':db}
    return rec

# check the options
MyThread = None         # ref to sensor thread, thread may run in parallel
def registrate():
    global Conf, MyThread
    if (not Conf['input']):
        return False
    if 'fd' in Conf.keys():
        return True
    Conf['input'] = False
    if Conf['port'] == None:
        MyLogger.log('ERROR',"Grove port not defined. Disabled.")
    elif Conf['port'].upper()[0] != 'A': 
        MyLogger.log('ERROR',"Grove port %s not correct. Disabled." % Conf['port'])
    elif not int(Conf['port'][1]) in [0,1,2]:
        MyLogger.log('ERROR',"Grove Loudness port nr number %s. Disabled." % Conf['port'])
    else:
        Conf['input'] = True
        Conf['fd'] = int(Conf['port'][1])
        get_calibrations()
        if MyThread == None: # only the first time
            MyThread = MyThreading.MyThreading(
                bufsize=Conf['bufsize'],
                interval=Conf['interval'],
                name='dB sensor',
                callback=Add,
                sync=Conf['sync'],
                DEBUG=Conf['debug'])
            # first call is interval secs delayed by definition
            try:
                if MyThread.start_thread():
                    return True
            except:
                pass
            MyThread = None
    raise IOError("Unable to registrate/start Grove dB sensor thread.")
    Conf['input'] = False
    return False
       
# ============================================================
# Loudness measurement with Grove Lodness sensor (no good quality?)
# ============================================================
# TO DO: calibrate the sensor with a dB meter
def getdata():
    global Conf, MyThread
    if not registrate():                # start up input readings
        return {}
    try:
        rec = MyThread.getRecord()     # pick up a record
        rec['db'] = int(rec['db'])
	return rec
    except IOError as er:
        MyLogger.log('WARNING',"Sensor Grove dB input failure: %s" % er)
    return {}

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['input'] = True
    Conf['debug'] = True
    Conf['sync'] = True
    Conf['port'] = 'A0'		# analogue socket A0 GrovePi+ board
    Conf['interval'] = 15
    for cnt in range(0,10):
        timing = time()
        try:
            data = getdata()
        except Exception as e:
            print("Input sensor error was raised as %s" % e)
            break
        print("Getdata returned:")
        print(data)
        timing = 30 - (time()-timing)
        if timing > 0:
            sleep(timing)
    if (not Conf['sync']) and (MyThread != None):
        MyThread.stop_thread()
