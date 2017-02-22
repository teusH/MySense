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

# $Id: MySensorTest.py,v 1.2 2017/02/18 14:50:41 teus Exp teus $

__version__ = "0." + "$Revision: 1.2 $"[11:-2]
__license__ = 'GPLV4'

# the values provided are rounded (3 decimals) of values in the
# thread buffer (max BUFSIZE). INTERVAL and the thread interval (TINTERV)
# are defining the window in the buffer.
""" Simpel standalone sensor module test
"""
    
import random
from time import time, sleep
import MyThreading

Conf = {
    'input': False,
    # multi-thread configuration
    'interval': 15, 'bufsize': 10,
    'sync': False, 'debug': False
}
# configurable options
__options__ = [
    'input','pin','type','calibrations',
    'interval','bufsize','sync'
]
            
def my_random(mx,rnd):
    return round(random.randint(0,mx)/4.5,rnd)

def my_waiting():
    global Conf
    sleep(random.randint(1,int(Conf['interval'])))

# get a value range. May be delayed, called by the MyThreading class
# Add defines the record layout
def Add():
    global Conf
    rec = { 'time': int(time()), 'pm1': my_random(100,1), 'pm2': my_random(135,2)}
    if Conf['debug']:
        print("Entered in buffer:")
        print(rec)
    my_waiting()
    return rec
    
# register the sensor thread in MyThreading class and start the sensor thread
MyThread = None
def registrate():
    global Conf, MyThread
    if (not Conf['input']):
        return False
    if MyThread == None: # only the first time
        # DEBUG == True, print logging in thread
        # if sync is True do not start the sensor thread
        MyThread = MyThreading.MyThreading(bufsize=Conf['bufsize'], interval=Conf['interval'], name='Sensor', callback=Add, sync=Conf['sync'], DEBUG=True)
        # first call is interval secs delayed by definition
        try:
            if not MyThread.start_thread():
                MyThread = None
                raise IOError("Unable to registrate for collecting data.")
        except:
            Conf['input'] = False
        return {}
    return True

# get data from the sensor buffer
def getdata():
    global MyThread
    global Conf
    if not registrate():
        return {}
    try:
        return MyThread.getRecord()
    except IOError as er:
        MyLogger.log('WARNING',"Sensor input failure: %s" % er)
    return {}

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['input'] = True
    Conf['debug'] = True
    Conf['sync'] = False
    for cnt in range(0,10):
        timing = time()
        try:
            data = getdata()
        except Exception as e:
            print("input sensor error was raised as %s" % e)
            break
        print("Getdata returned:")
        print(data)
        timing = 30 - (time()-timing)
        if timing > 0:
            sleep(timing)
    if (not Conf['debug']) and (MyThread != None):
        MyThread.stop_thread()
