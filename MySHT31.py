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

# $Id: MySHT31.py,v 1.1 2018/07/08 14:57:35 teus Exp teus $

""" Get measurements from SHT31 Sensirion chip via the I2C-bus.
    Measurements have a calibration factor (calibrated to Oregon weather station)
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MySHT31.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.1 $"[11:-2]
__license__ = 'GPLV4'

try:
    from time import time, sleep
    from types import ModuleType as module
    import MyThreading          # needed for multi threaded input
    import MyLogger
except ImportError:
    MyLogger.log(modulename,'FATAL',"Missing modules")

# configurable options
__options__ = [
    'input','i2c','type','calibrations',
    'fields','units',
    'raw',
    'interval','bufsize','sync']       # multithead buffer size and search for input secs

Conf ={
    'input': False,      # no temp/humidity sensors installed
    'type': 'SHT31',     # type of the chip eg BME280 Bosch
    'fields': ['temp','rh'], # temp, humidity
    'units' : ['C', '%'],    # C Celcius, K Kelvin, F Fahrenheit, % rh
    'calibrations' : [[0,1],[0,1]], # calibration factors, here order 1
    'i2c': '0x44',       # I2C-bus address
    'interval': 30,      # read dht interval in secs (dflt)
    'bufsize': 20,       # size of the window of values readings max
    'sync': False,       # use thread or not to collect data
    'debug': False,      # be more versatile
    'raw': False,        # no raw measurements displayed
    'Ada_import': None,  # Adafruit SHT31 imported module
#    'fd' : None          # input handler
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
# To Do: use alert settings for temp and/or hum of this chip
# To Do: use command error, crc and reset detection of the chip
def Add(conf):
    rec = {'time': int(time()),conf['fields'][0]:None,conf['fields'][1]:None}
    temp = None ; humidity = None
    # avoid condense in the chip
    if not 'alarm' in conf.keys(): conf['alarm'] = True
    try:
        if (conf['fd'] != None) and (conf['Ada_import'] != None):
            
            try:
                try:
                    if conf['alarm'] and (not conf['fd'].is_heater_active()):
                        conf['fd'].set_heater(True)
                        sleep(5)
                except:
                    pass
                temp = conf['fd'].read_temperature()
                humidity = conf['fd'].read_humidity()
                try:
                    if conf['fd'].is_heater_active():
                    	conf['fd'].set_heater(False)
			conf['alarm'] = False
                except:
                    pass
            except ValueError:
                MyLogger.log(modulename,'ATTENT',"Read error")
                return rec
        else:
            MyLogger.log(modulename,'ERROR',"Configuration error.")
            return rec
    except:
        MyLogger.log(modulename,'ERROR',"i2c access error. /dev/gpiomem permissions correct?")
        return rec
    if (temp == float("nan")) or (humidity == float("nan")):
        MyLogger.log(modulename,'Arning',"SHT31 read error, heating chip")
	conf['fd'].set_heater(True)
	return rec
    if (temp == None) or (humidity == None):
        MyLogger.log(modulename,'ERROR',"Access error. Connection problem?")
        raise IOError("SHT31 lost connection.")
        return rec
    if type(temp) is float:
        if conf['debug']:
            MyLogger.log(modulename,'DEBUG',"Temperature : %5.2f oC not calibrated" % temp)
	if (temp < -20) or (temp > 40.0): conf['alarm'] = True
    else:
        MyLogger.log(modulename,'DEBUG',"Temperature : None")
    if type(humidity) is float:
        if conf['debug']:
            MyLogger.log(modulename,'DEBUG',"Rel.Humidity: %5.2f %% not calibrated" % humidity)
	if humidity > 95.0: conf['alarm'] = True
    else:
        MyLogger.log(modulename,'DEBUG',"Rel.Humidity: None")
    if conf['fd'].is_command_error() or conf['fd'].is_data_crc_error() or conf['fd'].is_reset_detected():
        conf['fd'].reset()
        return rec
    if ('raw' in conf.keys()) and (type(Conf['raw']) is module):
        conf['raw'].publish(
            tag='%s' % conf['type'].lower(),
            data='temp=%.1f,rh=%.1f' % (temp*1.0,humidity*1.0))
    temp = calibrate(0,conf,temp)
    humidity = calibrate(1,conf,humidity)
    rec = {'time': int(time()),conf['fields'][0]:round(temp,2),conf['fields'][1]:int(humidity)}
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
    if (int(Conf['i2c'],0) != 0x44) and (int(Conf['i2c'],0) != 0x45):
        MyLogger.log(modulename,'ERROR',"I2C address %s not correct. Disabled." % Conf['i2c'])
        Conf['Ada_import'] = None
    else:
        try:
            Conf['Ada_import'] = __import__('Adafruit_SHT31')
        except ImportError:
            MyLogger.log(modulename,'ERROR',"Unable to import SHT Adafruit module. Disabled.")
            Conf['Ada_import'] = None
        try:
            Conf['fd'] = Conf['Ada_import'].SHT31(address=int(Conf['i2c'],0))
        except IOError:
            MyLogger.log(modulename,'WARNING','Try another I2C address.')
            if int(Conf['i2c'],0) == 0x44: Conf['i2c'] = '0x45'
            else: Conf['i2c'] = '0x44'
            Conf['fd'] = Conf['Ada_import'].SHT31(address=int(Conf['i2c'],0))
    if Conf['Ada_import'] == None:
        MyLogger.log(modulename,'ERROR',"Configuration error.")
        return False
    Conf['input'] = True
    if MyThread == None: # only the first time
        MyThread = MyThreading.MyThreading(
            bufsize=int(Conf['bufsize']),
            interval=int(Conf['interval']),
            name='SHT31 sensor',
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
    raise IOError("Unable to registrate/start SHT31 sensor thread.")
    Conf['input'] = False
    return False
       
# ============================================================
# meteo data from Adafruit Sensirion SHT31 e.g. temp, rh
# ============================================================
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
    Conf['type'] = 'SHT31'
    Conf['input'] = True
    Conf['i2c'] = '0x44'        # default I2C-bus address
    # Conf['sync'] = True         # True is in sync (not multi threaded)
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
