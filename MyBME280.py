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

# $Id: MyBME280.py,v 2.4 2017/03/01 16:26:24 teus Exp teus $

""" Get measurements from BME280 Bosch chip via the I2C-bus.
    Measurements have a calibration factor (calibrated to Oregon weather station)
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyBME280.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.4 $"[11:-2]
__license__ = 'GPLV4'

try:
    from time import time
    import MyThreading          # needed for multi threaded input
    import MyLogger
    import json
except ImportError:
    MyLogger.log('FATAL',"Missing modules for %s" % modulename)

# configurable options
__options__ = [
    'input','i2c','type','calibrations',
    'interval','bufsize','sync']       # multithead buffer size and search for input secs

Conf ={
    'input': False,      # no temp/humidity sensors installed
    'type': 'BME280',    # type of the chip eg BME280 Bosch
    'fields': ['temp','rh','hpa'], # temp, humidity, Pascal pressure
    'units' : ['C', '%','hPa'],    # C Celcius, K Kelvin, F Fahrenheit, % rh, hPa
    'calibrations' : [[-0.3,1],[-3,1],[0,1]], # calibration factors, here order 1
    'i2c': '0x77',       # I2C-bus address
    'interval': 30,      # read dht interval in secs (dflt)
    'bufsize': 20,       # size of the window of values readings max
    'sync': False,       # use thread or not to collect data
    'debug': False,      # be more versatile
    'Ada_import': None,      # Adafruit BME280 imported module
#    'fd' : None          # input handler
}

# get calibration factors
# convert calibration json string into array obect
def get_calibrations():
    global Conf
    if (not 'calibrations' in Conf.keys()) or (not type(Conf['calibrations']) is str):
        return
    Conf['calibrations'] = json.loads(Conf['calibrations'])

# calibrate as ordered function order defined by length calibraion factor array
def calibrate(nr,conf,value):
    if not type(value) is float:
        return None
    if (not 'calibrations' in conf.keys()) or (nr > len(conf['calibrations'])-1):
        return value
    rts = 0; pow = 0
    for a in Conf['calibrations'][nr]:
        rts += a*(value**pow)
        pow += 1
    return round(rts,1)

# get a record, called back from sensor thread with average of sliding window bufsize
def Add(conf):
    rec = {'time': int(time()),'temp':None,'rh':None, 'hpa': None}
    temp = None ; humidity = None ; pascals = None
    try:
        if (conf['fd'] != None) and (conf['Ada_import'] != None):
            
            try:
                temp = conf['fd'].read_temperature()
                pascals = conf['fd'].read_pressure()
                humidity = conf['fd'].read_humidity()
            except ValueError:
                MyLogger.log('ATTENT',"BME280 read error")
                return rec
        else:
            MyLogger.log('ERROR',"BME280 configuration error.")
            return rec
    except:
        MyLogger.log('ERROR',"BME280 i2c access error. /dev/gpiomem permissions correct?")
        return rec
    if (temp == None) or (humidity == None) or (pascals == None):
        MyLogger.log('ERROR',"BME280 access error. Connection problem?")
        raise IOError("BME280 lost connection.")
        return rec
    if type(temp) is float:
        if conf['debug']:
            MyLogger.log('DEBUG',"Temperature : %5.2f oC not calibrated" % temp)
    else:
        MyLogger.log('DEBUG',"Temperature : None")
    if type(humidity) is float:
        if conf['debug']:
            MyLogger.log('DEBUG',"Rel.Humidity: %5.2f %% not calibrated" % humidity)
    else:
        MyLogger.log('DEBUG',"Rel.Humidity: None")
    if type(pascals) is float:
        if conf['debug']:
            MyLogger.log('DEBUG',"Air pressure: %5.2f Pa not calibrated" % pascals)
    else:
        MyLogger.log('DEBUG',"Air pressure: None")
    if (temp == 0.0) and (humidity == 0.0) and (pascals == 0.0): return rec
    temp = calibrate(0,conf,temp)
    humidity = calibrate(1,conf,humidity)
    pascals = calibrate(2,conf,pascals)
    rec = {'time': int(time()),'temp':round(temp,2),'rh':int(humidity), 'hpa': int(pascals/100)}
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
    if (int(Conf['i2c'],0) != 0x77) and (int(Conf['i2c'],0) != 0x76):
        MyLogger.log('ERROR',"BME280 I2C address %s not correct. Disabled." % Conf['i2c'])
        Conf['Ada_import'] = None
    else:
        try:
            Conf['Ada_import'] = __import__('Adafruit_BME280')
        except ImportError:
            MyLogger.log('ERROR',"Unable to import BME Adafruit module. Disabled.")
            Conf['Ada_import'] = None
        Conf['fd'] = Conf['Ada_import'].BME280(mode=Conf['Ada_import'].BME280_OSAMPLE_8, address=int(Conf['i2c'],0))
    if Conf['Ada_import'] == None:
        MyLogger.log('ERROR',"BME280 configuration error.")
        return False
    get_calibrations()
    Conf['input'] = True
    if MyThread == None: # only the first time
        MyThread = MyThreading.MyThreading(
            bufsize=Conf['bufsize'],
            interval=Conf['interval'],
            name='BME280 sensor',
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
    raise IOError("Unable to registrate/start BME280 sensor thread.")
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
        MyLogger.log('WARNING',"Sensor BME280 input failure: %s" % er)
    return {}

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['type'] = 'BME280'
    Conf['input'] = True
    Conf['i2c'] = '0x77'        # default I2C-bus address
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
