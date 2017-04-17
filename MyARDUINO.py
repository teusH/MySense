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

# $Id: MyARDUINO.py,v 1.11 2017/04/17 12:58:21 teus Exp teus $

# TO DO: open_serial function may be needed by other modules as well?
#       add more sensors

# Defeat: output average PM count over 59(?) or 60 seconds:
#         monitor mode: 60 times per hour of 30 seconds samples per PM

"""
    Get sensor values via the Arduino board serial USB interface.
    Relies on Conf setting by main program
    Output dict with Shinyei PPD42NS and maybe other sensors
    Arduino produces lines output (json string) like (format: <type>_<unit>):
    {
    "version": "1.05","type": "PPD42NS",
    "pm25_count":null,"pm25_ratio":null,"pm25_pcs/cf":null,"pm25_ug/m3":null,
    "pm10_count":2435471,"pm10_ratio":8.02,"pm10_pcs/cf":4490,"pm10_ug/m3":7.00
    } EOL-char
    Arduino firmware can operate in two modes:
        driven on send values requests (send any char not 'C')
        every interval (dftl 60 secs) a sample (flt 15 secs)
    Firmware config Options: interval, sample and mode. Send command line::
    'C interval sample R<EOL>'
    where interval/sample is a number (in secs), R (request mode) is optional
    Request mode timeout is 1 hour.
"""
modulename='$RCSfile: MyARDUINO.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.11 $"[11:-2]

# configurable options
__options__ = [
    'input','type','usbid','firmware',
    'fields','units',
    'calibrations',      # calibration per sensor
    'interval','sample', # report interval in secs, sample timing in secs
    'bufsize', 'sync',   # multithead buffer size and search for input
    'fields','units',    # values collected
    'file',              # records input file for debugging
]

Conf = {
    'input': False,      # Dylos input sensor is required
    'fd': None,          # input handler
    'type': "Arduino Uno",   # type of sensor(s) controller
    'usbid': 'usb-Arduino_srl_', # usb ID via lsusb
    'firmware': '1.05',  # firmware number
    'fields': ['pm25','pm10'], # types of pollutants
     # 'pcs/qf' particle count per qubic foot per sample timing
     # 'ug/m3' particle count per qubic foot per sample timing per minute
     # 'count' and 'ratio' (0-100) per sample timing
    'units' : ['pcs/qf','pcs/qf'], # per type the measurment unit
    'calibrations': [[0,1],[0,1]], # per type calibration (Taylor serie)
    'interval': 45,     # read interval in secs (dflt)
    'sample': 10,       # sample timing for the count (seconds)
    'bufsize': 30,      # size of the window of values readings max
    'sync': False,      # use thread or not to collect data
    'debug': False,     # be more versatile on input data collection
    'keys': [],         # set of keys from firmware to be exported
    'file': None,       # debug records from input file

}
#    from MySense import log
try:
    try:
        import os
        from time import time
        from time import sleep
        import MyLogger
        import serial
    except:
        try:
            import Serial as serial
        except ImportError as e:
            MyLogger.log('FATAL',"Missing module %s" % e)
    import re
    import subprocess           # needed to find the USB serial
    import MyThreading          # needed for multi threaded input
    import json                 # Arduino will export json data
except ImportError as e:
    MyLogger.log('FATAL',"Missing module %s" % e)

# calibrate as ordered function order defined by length calibration factor array
def calibrate(nr,conf,value):
    if (not 'calibrations' in conf.keys()) or (nr > len(conf['calibrations'])-1):
        return value
    if type(value) is int:
        value = value/1.0
    if not type(value) is float:
        return None
    rts = 0; pow = 0
    for a in Conf['calibrations'][nr]:
        rts += a*(value**pow)
        pow += 1
    return round(rts,1)

# =======================================================================
# serial USB input or via (test) input file
# =======================================================================
def open_serial():
    global Conf
    #  scan for available ports. return a list of tuples (num, name)
    if Conf['fd'] != None:
        return True

    if (not Conf['file']) and Conf['usbid']:
        serial_dev = None
        if Conf['usbid'] != None:
            # try serial with product ID
            byId = "/dev/serial/by-id/"
            if not os.path.exists(byId):
                MyLogger.log('FATAL',"There is no USBserial connected. Abort.")
            device_re = re.compile(".*\s%s.*(?P<device>ttyACM\d+)$" % Conf['usbid'], re.I)
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
                MyLogger.log('ERROR',"No serial USB connected.")
            except (Exception) as error:
                MyLogger.log('ERROR',"Serial USB %s not found, error:%s"%(Conf['usbid'], error))
                Conf['usbid'] = None
        if Conf['usbid'] == None:
            MyLogger.log('WARNING',"Please provide serial USB producer info.")
            MyLogger.log('FATAL',"No USB Arduino input stream defined.")
            return False
        #Initialize Serial Port
        try:
            Conf['fd'] = serial.Serial(  # for here tuned for Dylos
                serial_dev,
                baudrate=9600,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=65*60)  # allow also monitor mode
            MyLogger.log('INFO',"Arduino serial USB: %s" % serial_dev)
        except (Exception) as error:
            MyLogger.log('FATAL',"%s" % error)
            return False
        # configure the Arduino with interval and sample timing
        if type(Conf['interval']) is str: Conf['interval'] = int(Conf['interval'])
        if (Conf['interval'] < 0) or (Conf['interval'] > 3600):
            Conf['interval'] = 60
        if type(Conf['sample']) is str: Conf['sample'] = int(Conf['sample'])
        if Conf['sample'] <= 10:
            Conf['sample'] = 10
            MyLogger.log('WARNING','Shinyei dust adjusted sample time to 10 secs')
        if Conf['sample'] > Conf['interval']/2:
            Conf['interval'] = 2 * Conf['sample']
            MyLogger.log('WARNING','Shinyei dust adjusted interval time to %d secs' % Conf['interval'])
        cnt = 0
        while 1:
            if (cnt%3) == 0:    # configure Arduino firmware
                Conf['fd'].write("C %d %d\n" % (Conf['interval'],Conf['sample'])) 
            cnt += 1
            line = Conf['fd'].readline()
            if (len(line) < 20) or (cnt > 10): break
    elif Conf['file']:
        try:
            Conf['fd'] = open(Conf['file'])
            Conf['sync'] = True
        except:
            MyLogger.log('FATAL', "Failed top open Arduino test input from %s" % Conf['file'])
            return False
    else: return False
    return True

MyThread = None
def registrate():
    global Conf, MyThread
    if not Conf['input']: return False
    if Conf['fd'] != None: return True
    Conf['input'] = False
    if (Conf['type'] == None) or (Conf['type'][0:7].lower() != 'arduino'):
        return False
    if type(Conf['fields']) is str:
        Conf['fields'] = Conf['fields'].split(',')
    if type(Conf['units']) is str:
        Conf['units'] = Conf['units'].split(',')
    Conf['keys'] = []
    for i in range(0,len(Conf['fields'])):
        Conf['keys'].append("%s_%s" % (Conf['fields'][i],Conf['units'][i].replace('#','')))
    if not open_serial():
        return False
    Conf['input'] = True
    if MyThread == None: # only the first time
        MyThread = MyThreading.MyThreading( # init the class
            bufsize=Conf['bufsize'],
            interval=Conf['interval'],
            name='Arduino PM sensors',
            callback=Add,
            conf=Conf,
            sync=Conf['sync'],
            DEBUG=Conf['debug'])
        # first call is interval secs delayed by definition
        try:
            if MyThread.start_thread(): # start multi threading
                return True
        except:
            pass
        MyThread = None
    raise IOError("Unable to registrate/start Arduino input thread.")
    Conf['input'] = False
    return False

# ================================================================
# Arduino Shinyei PDD42 PM count per minute per cubic food input via serial USB
# Arduino may handle more sensors as eg DHT, gas etc.
# ================================================================
# get a record
Conf['Serial_Errors'] = 0
def Add(conf):
    bin_data = {}
    try:
        try:
            if (not Conf['file']) and (conf['interval'] == 0):
                # request a json string
                conf['fd'].write("\n")
            line = conf['fd'].readline()
            if not Conf['file']:
                while conf['fd'].inWaiting():       # skip to latest record
                    line = conf['fd'].readline()
            Serial_Errors = 0
        except SerialException:
            conf['Serial_Errors'] += 1
            MyLogger.log('ATTENT',"ARduino serial exception. Close/Open serial.")
            try:
                conf['fd'].close()
            except:
                pass
            conf['fd'] = None
            if conf['Serial_Errors'] > 10:
                MyLogger.log('ERROR',"Arduino to many serial errors. Disabled.")
                sleep(1)
                conf['output'] = False
                return bin_data
            return conf['getdata']()
        except:
            pass
        line = str(line.strip().decode('utf-8'))
        s = line.find('{') ; l = line.find('}')
        if (s < 0) or (l < 0):
            # MyLogger('WARNING','Not a json input value: %s' % line)
            sleep(1)
            return bin_data
        try:
            bin_data = json.loads(line[s:(l+1)])
        except:
            # Arduino Error
            MyLogger('WARNING',"Arduino Data: Error - Arduino Bin data")
        if len(bin_data) <= 0:
            sleep(1)
            return bin_data
    except (Exception) as error:
        # Some other Arduino Error
        MyLogger.log('WARNING','Some Arduine error in Add routine')
        sleep(1)
        return {}
    if ('firmware' in conf.keys()) and ('version' in bin_data.keys()):
        if conf['firmware'][0] != bin_data['version'][0]:
            MyLogger.log('FATAL','Arduino version/firmware incompatible')
        del bin_data['version']
    if 'type' in bin_data.keys():
        if conf['type'] != bin_data['type']:
            MyLogger.log('ATTENT','%s sensor(s) type: %s' % (conf['type'],bin_data['type']));
            conf['type'] = bin_data['type']
        del bin_data['type']
    if len(conf['keys']):
        for key in bin_data.keys():
            if not key in conf['keys']:
                del bin_data[key]
                if not 'keys_skipped' in conf.keys(): conf['keys_skipped'] = []
                if not key in conf['keys_skipped']:
                    MyLogger.log('ATTENT','Skip Arduino sensor %s value.' % key)
                    conf['keys_skipped'].append(key)
    else:       # at start: denote all record names/units from Arduino firmware
        conf['keys'] = []
        conf['fields'] = []; conf['units'] = []; conf['calibrations'] = []
        for key in bin_data.keys():
            conf['keys'].append(key)
            id_un = key.split('_')
            conf['fields'].append(id_un[0])
            conf['units'].append(id_un[1].replace('#',''))
            conf['calibrations'].append = [0,1]
    for i in range(0,len(conf['fields'])):
        dataKey = '%s_%s' % (conf['fields'][i],conf['units'][i])
        if dataKey in bin_data.keys():
            bin_data.update( {conf['fields'][i]:calibrate(i,conf,bin_data[dataKey])})
            del bin_data[dataKey]
    bin_data.update( {"time": int(time())} )
    return bin_data

def getdata():
    global Conf, MyThread
    if not registrate():                # start up input readings
        return {}
    try:
        return MyThread.getRecord()     # pick up a record
    except IOError as er:
        MyLogger.log('WARNING',"Sensor Dylos input failure: %s" % er)
    return {}

Conf['getdata'] = getdata	# Add needs this global viariable

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['input'] = True
    Conf['sync'] = True
    Conf['debug'] = True
    for cnt in range(0,10):
        timing = time()
        try:
            data = getdata()
        except Exception as e:
            print("input sensor error was raised as %s" % e)
            break
        print("Getdata returned:")
        print(data)
        timing = 60 - (time()-timing)
        if timing > 0:
            sleep(timing)
    if MyThread != None:
        MyThread.stop_thread()

