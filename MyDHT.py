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

# $Id: MyDHT.py,v 2.11 2017/02/22 11:56:31 teus Exp teus $

# TO DO: make a threat to read every period some values
# DHT import module can delay some seconds

""" Get measurements from DHT family of meteo chips
    Measurements have a calibration factor (calibrated to Oregon weather station)
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyDHT.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.11 $"[11:-2]
__license__ = 'GPLV4'

try:
    from time import time
    import MyThreading          # needed for multi threaded input
    import MyLogger
    import math
    import json
except ImportError:
    MyLogger.log('FATAL',"Missing modules for %s" % modulename)

# configurable options
__options__ = [
    'input','pin','type','calibrations',
    'interval','bufsize','sync']       # multithead buffer size and search for input secs

Conf ={
    'input': False,      # no temp/humidity sensors installed
    'type': None,        # type of the humidity/temp chip eg AM2302,DHT22,DHT11
    'fields': ['temp','rh'], # temp, rh, pa
    'units' : ['C', '%'],    # C Celcius, K Kelvin, F Fahrenheit, % rh, hPa
    'calibrations' : [[-0.45,1],[0.5,1]], # calibration factors, here order 1
    'pin': None,         # GPIO pin of PI e.g. 4, 22
    'interval': 30,      # read dht interval in secs (dflt)
    'bufsize': 20,       # size of the window of values readings max
    'sync': False,       # use thread or not to collect data
    'debug': False,      # be more versatile
    'import': None,      # imported module either DHT or Grove
#    'fd' : None          # input handler
}

DHT_types = {
    'DHT11': 0,        # DHT11 Adafruit, needs 4K7 resistor
    'DHT22': 1,        # DHT22 more precise as DHT11, needs 4K7 resistor
    'AM2302': 1,       # Adafruit AM2302, wired DHT22
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
        if (Conf['pin'] != None) and (Conf['import'] != None):
            humidity, temp = Conf['import'].read_retry(Conf['fd'], Conf['pin'])
        elif (Conf['port'] != None) and (Conf['import'] != None):
            temp, humidity = Conf['import'].dht(Conf['port'],Conf['fd'])
        else:
            MyLogger.log('ERROR',"DHT configuration error.")
            return {'time': int(time()),'temp':None,'rh':None}
    except:
        MyLogger.log('ERROR',"DHT gpio access error. /dev/gpiomem permissions correct?")
        return {'time': int(time()),'temp':None,'rh':None}
    if (temp == None) or (humidity == None):
        MyLogger.log('ERROR',"DHT access error. Connection problem?")
        raise IOError("DHT lost connection.")
        return {'time': int(time()),'temp':None,'rh':None}
    if not math.isnan(temp):
        MyLogger.log('DEBUG',"Temperature : %5.2f oC not calibrated" % temp)
    else:
        MyLogger.log('DEBUG',"Temperature : None")
    if not math.isnan(humidity):
        MyLogger.log('DEBUG',"Rel.Humidity: %5.2f %% not calibrated" % humidity)
    else:
        MyLogger.log('DEBUG',"Rel.Humidity: None")
    temp = calibrate(0,temp)
    humidity = calibrate(1,humidity)
    rec = {'time': int(time()),'temp':temp,'rh':humidity}
    return rec

# check the options
MyThread = None         # ref to sensor thread, thread may run in parallel
def registrate():
    global Conf, MyThread, DHT_types
    if (not Conf['input']):
        return False
    if 'fd' in Conf.keys():
        return True
    Conf['input'] = False
    if (Conf['type'] == None) or ((Conf['pin'] == None) and (Conf['port'] == None)):
        MyLogger.log('ERROR',"DHT type or pin/port not defined. Disabled.")
    elif not Conf['type'].upper() in DHT_types.keys():
        MyLogger.log('ERROR',"DHT type %s not correct. Disabled." % Conf['type'])
    elif Conf['pin'] != None: 
        if not int(Conf['pin']) in [4,5,6,12,13,17,18,22,23,24,25,26,27]:
            MyLogger.log('ERROR',"DHT GPIO pin number %s not correct. Disabled." % Conf['pin'])
        else:
            Conf['import'] = __import__('Adafruit_DHT')
            DHT_types = {
                'DHT11': Adafruit_DHT.DHT11,
                'DHT22': Adafruit_DHT.DHT22,        # more precise as DHT11
                'AM2302': Adafruit_DHT.AM2302       # wired DHT22
            }
            Conf['fd'] = DHT_types[Conf['type'].upper()]
    elif Conf['port'] != None:
        if (Conf['port'][0].upper() != 'D') or (not int(Conf['port'][1]) in range(0,8)):
            MyLogger.log('ERROR',"DHT Grove port number %s not correct. Disabled." % Conf['port'])
        else:
            Conf['import'] = __import__('grovepi')
            Conf['fd'] = 0 if Conf['type'].upper() == 'DHT11' else 1
            Conf['port'] = int(Conf['port'][1])
    if Conf['import'] == None:
        MyLogger.log('ERROR',"DHT pin or port configuration error.")
        return False
    get_calibrations()
    Conf['input'] = True
    if MyThread == None: # only the first time
        MyThread = MyThreading.MyThreading(
            bufsize=Conf['bufsize'],
            interval=Conf['interval'],
            name='DHT sensor',
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
    raise IOError("Unable to registrate/start DHT sensor thread.")
    Conf['input'] = False
    return False
       
# ============================================================
# meteo data from Adafruit DHT e.g. DHT11/22, AM2302: temp, rh
# ============================================================
# to do: add Adafruit BME280: temp, rh, hPa
def getdata():
    global Conf, MyThread
    if not registrate():                # start up input readings
        return {}
    try:
        return MyThread.getRecord()     # pick up a record
    except IOError as er:
        MyLogger.log('WARNING',"Sensor DHT input failure: %s" % er)
    return {}

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['type'] = 'DHT22'
    #Conf['pin'] = 4            # GPIO pin of Pi
    Conf['port'] = 'D3'         # Digital port D3 of GrovePi+
    Conf['input'] = True
    #Conf['sync'] = True         # True is in sync (not multi threaded)
    #Conf['debug'] = True        # print collected sensor values
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
    if (not Conf['sync']) and (MyThread != None):
        MyThread.stop_thread()
