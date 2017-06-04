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

# $Id: MyDHT.py,v 2.24 2017/06/04 14:40:20 teus Exp $

# TO DO: make a threat to read every period some values
# DHT import module can delay some seconds

""" Get measurements from DHT family of meteo chips
    Measurements have a calibration factor (calibrated to Oregon weather station)
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyDHT.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.24 $"[11:-2]
__license__ = 'GPLV4'

try:
    from time import time
    import MyThreading          # needed for multi threaded input
    import MyLogger
except ImportError:
    MyLogger.log(modulename,'FATAL',"Missing modules for %s" % modulename)

# configurable options
__options__ = [
    'input','pin','port','type','calibrations',
    'fields','units',
    'raw', 
    'interval','bufsize','sync']       # multithead buffer size and search for input secs

Conf ={
    'input': False,      # no temp/humidity sensors installed
    'type': None,        # type of the humidity/temp chip eg AM2302,DHT22,DHT11
    'fields': ['temp','rh'], # temp, rh, pa
    'units' : ['C', '%'],    # C Celcius, K Kelvin, F Fahrenheit, % rh, hPa
    'calibrations' : [[0.0,1],[-3.3,1]], # calibration factors, here order 1
    'pin': None,         # GPIO pin of PI e.g. 4, 22
    'port': None,        # GrovePi+ digital port
    'interval': 30,      # read dht interval in secs (dflt)
    'bufsize': 20,       # size of the window of values readings max
    'sync': False,       # use thread or not to collect data
    'debug': False,      # be more versatile
    'raw': False,        # no raw measurements displayed by dflt
    'Ada_import': None,      # imported module either DHT or Grove
#    'fd' : None          # input handler
}

DHT_types = {
    'DHT11': 0,        # DHT11 Adafruit, needs 4K7 resistor
    'DHT22': 1,        # DHT22 more precise as DHT11, needs 4K7 resistor
    'AM2302': 1,       # Adafruit AM2302, wired DHT22
}

# calibrate as ordered function order defined by length calibraion factor array
def calibrate(nr,conf,value):
    if (not 'calibrations' in conf.keys()) or (nr > len(conf['calibrations'])-1):
        return value
    if type(value) is int: value = value/1.0
    if not type(value) is float:
        return None
    rts = 0; pow = 0
    for a in Conf['calibrations'][nr]:
        rts += a*(value**pow)
        pow += 1
    return round(rts,1)

# get a record, called back from sensor thread with average of sliding window bufsize
def Add(conf):
    rec = {'time': int(time()),conf['fields'][0]:None,conf['fields'][1]:None}
    try:
        if (conf['pin'] != None) and (conf['Ada_import'] != None):
            humidity, temp = conf['Ada_import'].read_retry(conf['fd'], conf['pin'])
        elif (conf['port'] != None) and (conf['Ada_import'] != None):
            temp, humidity = conf['Ada_import'].dht(conf['port'],conf['fd'])
        else:
            MyLogger.log(modulename,'ERROR',"Configuration error.")
            return rec
    except:
        MyLogger.log(modulename,'ERROR',"GPIO access error. /dev/gpiomem permissions correct?")
        return {'time': int(time()),conf['fields'][0]:None,conf['fields'][1]:None}
    if (temp == None) or (humidity == None):
        MyLogger.log(modulename,'ERROR',"Access error. Connection problem?")
        raise IOError("DHT lost connection.")
        return rec
    if type(temp) is float:
        if conf['debug']:
            MyLogger.log(modulename,'DEBUG',"Temperature : %5.2f oC not calibrated" % temp)
    else:
        MyLogger.log(modulename,'DEBUG',"Temperature : None")
    if type(humidity) is float:
        if conf['debug']:
            MyLogger.log(modulename,'DEBUG',"Rel.Humidity: %5.2f %% not calibrated" % humidity)
    else:
        MyLogger.log(modulename,'DEBUG',"Rel.Humidity: None")
    if (temp == 0.0) and (humidity == 0.0): return rec
    if ('raw' in conf.keys()) and conf['raw']:
        print("raw,sensor=%s temp=%.1f,rh=%.1f %d000\n" % ('dht',temp,humidity,int(time()*1000)))
    temp = calibrate(0,conf,temp)
    humidity = calibrate(1,conf,humidity)
    rec = {'time': int(time()),conf['fields'][0]:temp,conf['fields'][1]:humidity}
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
        MyLogger.log(modulename,'ERROR',"Type or pin/port not defined. Disabled.")
    elif not Conf['type'].upper() in DHT_types.keys():
        MyLogger.log(modulename,'ERROR',"Type %s not correct. Disabled." % Conf['type'])
    elif Conf['pin'] != None: 
        if not int(Conf['pin']) in [4,5,6,12,13,17,18,22,23,24,25,26,27]:
            MyLogger.log(modulename,'ERROR',"GPIO pin number %s not correct. Disabled." % Conf['pin'])
        else:
            Conf['Ada_import'] = __import__('Adafruit_DHT')
            DHT_types = {
                'DHT11': Conf['Ada_import'].DHT11,
                'DHT22': Conf['Ada_import'].DHT22,        # more precise as DHT11
                'AM2302': Conf['Ada_import'].AM2302       # wired DHT22
            }
            Conf['fd'] = DHT_types[Conf['type'].upper()]
    elif Conf['port'] != None:
        if (Conf['port'][0].upper() != 'D') or (not int(Conf['port'][1]) in range(0,8)):
            MyLogger.log(modulename,'ERROR',"Grove port number %s not correct. Disabled." % Conf['port'])
        else:
            Conf['Ada_import'] = __import__('grovepi')
            Conf['fd'] = 0 if Conf['type'].upper() == 'DHT11' else 1
            Conf['port'] = int(Conf['port'][1])
    if Conf['Ada_import'] == None:
        MyLogger.log(modulename,'ERROR',"Pin or port configuration error.")
        return False
    Conf['input'] = True
    if MyThread == None: # only the first time
        MyThread = MyThreading.MyThreading(
            bufsize=Conf['bufsize'],
            interval=Conf['interval'],
            name='DHT sensor',
            callback=Add,
	    conf=Conf,
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
        MyLogger.log(modulename,'WARNING',"Sensor input failure: %s" % er)
    return {}

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['type'] = 'DHT22'
    #Conf['pin'] = 4            # GPIO pin of Pi
    Conf['port'] = 'D3'         # Digital port D3 of GrovePi+
    Conf['input'] = True
    Conf['sync'] = True         # True is in sync (not multi threaded)
    Conf['debug'] = True        # print collected sensor values
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
