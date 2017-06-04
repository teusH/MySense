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

# $Id: MySDS011.py,v 1.11 2017/06/04 14:40:20 teus Exp $

# Defeat: output average PM count over 59(?) or 60 seconds:
#         continious mode: once per 59 minutes and 59 seconds!,
#         monitor mode: 60 times per hour 

""" Get sensor values: PM2.5 and PM10 from Dylos Particular Matter senor
    Relies on Conf setting by main program
    Output dict with PM2.5 (fields index 0) and PM10 (fields index 1) elements
    if units is not defined as pcs the values are converted to ug/m3 (report Philadelphia)
    MET/ONE BAM1020 = Dylos + 5.98 (rel.hum*corr see Dexel University report)
"""
modulename='$RCSfile: MySDS011.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.11 $"[11:-2]

# configurable options
__options__ = [
    'input','type','usbid','firmware', 'calibrations',
    'fields','units',                 # one may change this as name and/or ug/m3 units
    'raw',                            # display raw measurements on stderr
    'interval','sample', 'bufsize','sync',  # multithead buffer size and search for input
]

Conf = {
    'input': False,      # SDS011 input sensor is required
    'fd': None,          # input handler
    'type': "Nova SDS011",         # type of device
    'usbid': '-1a86.*-port',    # Qin Heng Electronics usb ID via lsusb
    'firmware': '161121',# firmware number
    'serial': 'ED56',    # ID number
    'fields': ['pm25','pm10'],     # types of pollutants
     # 'pcs/qf' particle count per qubic foot per minute
     #  spec: 0.01pcs/qf average per minute window
     # 'units' : ['pcs/qf','pcs/qf'],   # dflt type the measurement unit
    'units' : ['ug/m3','ug/m3'],   # dflt type the measurement unit
    'calibrations': [[0,1],[0,1]], # per type calibration (Taylor polonium)
    'interval': 120,    # read cycle interval in secs (dflt)
    'sample': 60,       # read interval: duty cycle
    'bufsize': 30,      # size of the window of values readings max
    'sync': False,      # use thread or not to collect data
    'debug': 0,         # level 0 .. 5, be more versatile on input data collection
    'raw': False,       # display raw measurement data with timestamps

}
#    from MySense import log
try:
    import os
    import sys
    from time import time
    from time import sleep
    from sds011 import SDS011
    import MyLogger
    import re
    import subprocess           # needed to find the USB serial
    import MyThreading          # needed for multi threaded input
except ImportError as e:
    print("FATAL: Missing module %s" % e)
    exit(1)

# convert pcs/qf (counter) to ug/m3 (weight)
# ref: https://github.com/andy-pi/weather-monitor/blob/master/air_quality.py
#def convertPM(nr,conf,value):
#    if conf['units'][nr][0:3] == 'pcs': return value
#    r = 0.44            # diameter of PM2.5
#    if nr: r = 2.60     # diameter of PM10
#    # concentration * K * mass (mass=:density (=:1.65*10**12) * vol (vol=:4/3 * pi * r**3))
#    return value * 3531.5 * ((1.65 * (10**12)) * ((4/3.0) * 3.14159 * (r * (10**-6))**3))

# calibrate as ordered function order defined by length calibration factor array
def calibrate(nr,conf,value):
    if (not 'calibrations' in conf.keys()) or (nr > len(conf['calibrations'])-1):
        return value
    if type(value) is int: value = value/1.0
    if not type(value) is float: return None
    thisnr = 0
    if nr == 0: thisnr = 1
    # value = convertPM(thisnr,conf,value)
    rts = 0; pow = 0
    for a in Conf['calibrations'][thisnr]:
        rts += a*(value**pow)
        pow += 1
    return round(rts,2)

# =======================================================================
# serial USB input or via (test) input file
# =======================================================================
def get_device():
    global Conf
    if Conf['fd'] != None:
        return True

    if Conf['usbid']:
        serial_dev = None
        if Conf['usbid'] != None:
            # try serial with product ID
            byId = "/dev/serial/by-id/"
            if not os.path.exists(byId):
                MyLogger.log(modulename,'FATAL',"There is no USBserial connected. Abort.")
            device_re = re.compile(".*%s\d.*(?P<device>ttyUSB\d+)$" % Conf['usbid'], re.I)
            devices = []
            try:
                df = subprocess.check_output(["/bin/ls","-l",byId])
                for i in df.split('\n'):
                    if i:
                        info = device_re.match(i)
                        if info:
                            dinfo = info.groupdict()
                            serial_dev = '/dev/%s' % dinfo.pop('device')
                            break
            except CalledProcessError:
                MyLogger.log(modulename,'ERROR',"No serial USB connected.")
            except (Exception) as error:
                MyLogger.log(modulename,'ERROR',"Serial USB %s not found, error:%s"%(Conf['usbid'], error))
                Conf['usbid'] = None
        if serial_dev == None:
            MyLogger.log(modulename,'WARNING',"Please provide serial USB producer info.")
            MyLogger.log(modulename,'FATAL',"No input stream defined.")
            return False
        # check operational arguments
        for item in ['sample','interval','debug']:
            if type(Conf[item]) is str:
                if not Conf[item].isdigit():
                    MyLogger.log(modulename,'FATAL','%s should be nr of seconds' % item)
                Conf[item] = int(Conf[item])
	    if type(Conf[item]) is bool:
		Conf[item] = 1 if Conf[item] else 0
        Conf['sample'] = 60 if Conf['sample'] < 60 else ((Conf['sample']+30)/60)*60
        if (Conf['sample'] <= 0 or Conf['sample'] >= 30*60) or Conf['sample'] > (Conf['interval']-2):
            MyLogger.log(modulename,"FATAL","Sample not 1..30 or sample > interval")
        MyLogger.log(modulename,'INFO',"Sample duty cycle is set to %d minutes." % (Conf['sample']/60))
        if Conf['units'][0][-2:].upper() != 'M3':
            concentration = True
            Conf['units'] = ['pcs/qf','pcs/qf']
        else:
            concentration = False
            Conf['units'] = ['ug/m3','ug/m3']
        MyLogger.log(modulename,'INFO',"(PM2.5,PM10) values are in (%s,%s)" % (Conf['units'][0],Conf['units'][1]))
        try:
            Conf['fd'] = SDS011(serial_dev, logger=MyLogger.log, debug=Conf['debug'], timeout=Conf['sample']*2, concentration=concentration)
            MyLogger.log(modulename,'INFO',"Serial used for USB: %s" % serial_dev)
            Conf['id'] = Conf['fd'].device_id
            Conf['firmware'] = Conf['fd'].firmware
            Conf['type'] += " (%s/%s)" % (Conf['id'],Conf['firmware'])
            MyLogger.log(modulename,'INFO','Device id %s, firmware %s' % (Conf['id'],Conf['firmware']))
            #Conf['fd'].workstate = SDS011.WorkStates.Sleeping # switch fan off
        except IOError as error:
            MyLogger.log(modulename,"WARNING","Connectivity: %s" % error)
            Conf['fd'].device.close()
            Conf['fd'] = SDS011(serial_dev, logger=MyLogger.log, debug=Conf['debug'], timeout=Conf['sample']*2, concentration=concentration)
            Conf['fd'].workstate = SDS011.WorkStates.Measuring
        except (Exception) as error:
            MyLogger.log(modulename,'FATAL',"%s" % error)
            return False
    else:
       Logger.log('ERROR', "Failed access SDS011 module")
       return False
    return True

MyThread = None
def registrate():
    global Conf, MyThread
    if not Conf['input']: return False
    if Conf['fd'] != None: return True
    Conf['input'] = False
    if (Conf['type'] == None) or (Conf['type'][-6:].lower() != 'sds011'):
        return False
    if not get_device():
        return False
    Conf['input'] = True
    if MyThread == None: # only the first time
        MyThread = MyThreading.MyThreading( # init the class
            bufsize=Conf['bufsize'],
            interval=Conf['interval'],
            name=Conf['type'],
            callback=Add,
            conf=Conf,
            sync=Conf['sync'],
            DEBUG=(True if Conf['debug'] > 0 else False))
        # first call is interval secs delayed by definition
        try:
            if MyThread.start_thread(): # start multi threading
                return True
        except:
            pass
        MyThread = None
    raise IOError("Unable to registrate/start Dylos thread.")
    Conf['input'] = False
    return False

# ================================================================
# Dylos PM count per minute per cubic food input via serial USB
# Dylos upgraded: Modified Firmware (v1.16f2) MAX = 4
# Dylos MAX = 2 PM2.5 PM10 counts
# ================================================================
# get a record
timing = 0
Conf['Serial_Errors'] = 0
def Add(conf):
    global timing
    PM25 = 0 ; PM10 = 1 # array index defs
    if conf['fields'][0][-2:] == '10':
        PM25 = 1; PM10 = 0
    timing = timing - time()
    if timing >= 1.0:
        # MyLogger.log(modulename,"DEBUG","Interval wait a bit for %d seconds" % timing)
        sleep(timing)
    timing = time()
    values = []
    skip = 0
    try:
        if conf['Serial_Errors'] > 10:
            conf['fd'].reset()
            conf['Serial_Errors'] = 0
            MyLogger("WARNING","SDS011 reset on errors.")
        if conf['fd'].workstate != SDS011.WorkStates.Measuring:
            conf['fd'].workstate = SDS011.WorkStates.Measuring
            # skip = 1  # seems we do not need to skip first reading
            if conf['fd'].dutycycle != conf['sample']/60:
                conf['fd'].dutycycle = conf['sample']/60 # in minutes
        for nr in range(skip+1):
            values = conf['fd'].get_values()
    except IOError:     # timeout
        conf['Serial_Errors'] += 1
    except (Exception) as error:
        conf['Serial_Errors'] += 1
        MyLogger.log(modulename,'WARNING',error)
    if conf['Serial_Errors'] > 20:
        conf['fd'].device.close()
        conf['fd'] = None
	MyLogger.log(modulename,"WARNING","Serial errors")
        return {}
    if len(values) != 2:
        conf['Serial_Errors'] += 1
	MyLogger.log(modulename,"WARNING","Serial error: only %d values" % len(values))
        return {}
    conf['Serial_Errors'] = 0
    timing = time()-timing
    timing = conf['interval'] - timing
    if timing < 0: timing = 0
    if timing > 20: # switch fan off
        conf['fd'].workstate = SDS011.WorkStates.Sleeping
    timing += time()
    # take notice: values 0 is PM10, 1 is PM2.5
    values = { "time": int(time()),
            conf['fields'][PM25]: calibrate(PM25,conf,values[1]),
            conf['fields'][PM10]: calibrate(PM10,conf,values[0]) }
    MyLogger.log(modulename,"DEBUG","Readings PM2.5:%5.1f PM10:%5.1f" % (values[conf['fields'][PM25]],values[conf['fields'][PM10]]))
    if ('raw' in conf.keys()) and conf['raw']:
        print("raw,sensor=%s PM25=%.1f,PM10=%.1f %d000\n" % ('sds011',values[conf['fields'][PM25]],values[conf['fields'][PM10]],int(time()*1000)))
    return values

def getdata():
    global Conf, MyThread
    if not registrate():                # start up input readings
        return {}
    try:
        return MyThread.getRecord()     # pick up a record
    except IOError:
        MyLogger.log(modulename,'WARNING',"Sensor input failure")
    return {}

Conf['getdata'] = getdata	# Add needs this global viariable

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['input'] = True
    Conf['sync'] = True         #multi threading on?
    Conf['debug'] = 1
    Conf['interval'] = 120      # sample once per 2 minutes
    Conf['sample'] = 60         # sample of 1 minute
    Conf['units'] = ['pcs/qf','pcs/qf'] # do values not in mass weight
    Conf['raw'] = True          # display raw data with timestamps

    for cnt in range(0,10):
        timings = time()
        try:
            data = getdata()
        except Exception as e:
            print("input sensor error was raised as %s" % e)
            break
        print("Getdata returned:")
        print(data)
        timings = 30 - (time()-timings)
        if timings > 0:
            print("Sleep for %d seconds" % timings)
            sleep(timings)
    if MyThread != None:
        MyThread.stop_thread()

