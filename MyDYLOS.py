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

# $Id: MyDYLOS.py,v 2.20 2017/06/10 15:26:29 teus Exp teus $

# TO DO: open_serial function may be needed by other modules as well?
#       add version number, firmware number

# Defeat: output average PM count over 59(?) or 60 seconds:
#         continious mode: once per 59 minutes and 59 seconds!,
#         monitor mode: 60 times per hour 

""" Get sensor values: PM2.5 and PM10 from Dylos Particular Matter senor
    Relies on Conf setting by main program
    Output dict with PM2.5 (fields index 0) and PM10 (fields index 1) elements
    if units is not defined as pcs the values are converted to ug/m3 (report Philadelphia)
    MET/ONE BAM1020 = Dylos + 5.98 (rel.hum*corr see Dexel University report)
"""
modulename='$RCSfile: MyDYLOS.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.20 $"[11:-2]

# configurable options
__options__ = [
    'input','type','usbid','file','firmware', 'calibrations',
    'fields','units',            # one may change this as name and/or ug/m3 units
    'raw',                       # display raw measurements
    'interval','bufsize','sync'  # multithead buffer size and search for input
]

Conf = {
    'input': False,      # Dylos input sensor is required
    'fd': None,          # input handler
    'type': "Dylos DC1100",     # type of device
    'usbid': 'Prolific_Technology', # usb ID via lsusb
    'port': None,        # input com port number (depricated)
    'file': None,        # Debugging: read input from file -i option
    'firmware': 'V1.17i',# firmware number
    'serial': None,      # S/N number
    'fields': ['pm_25','pm_10'],   # types of pollutants
     # 'pcs/qf' particle count per qubic foot per minute
     #  spec: 0.01pcs/qf average per minute window
    'units' : ['pcs/qf','pcs/qf'],   # dflt type the measurement unit
    'calibrations': [[0,1],[0,1]], # per type calibration (Taylor polonium)
    'interval': 50,     # read dht interval in secs (dflt)
    'bufsize': 30,      # size of the window of values readings max
    'sync': False,      # use thread or not to collect data
    'raw': False,       # dflt display raw measurements
    'debug': False,     # be more versatile on input data collection

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
            MyLogger.log(modulename,'FATAL',"Missing module %s" % e)
    import re
    import subprocess           # needed to find the USB serial
    import MyThreading          # needed for multi threaded input
except ImportError as e:
    MyLogger.log(modulename,'FATAL',"Missing module %s" % e)

# convert pcs/qf (counter) to ug/m3 (weight)
# ref: https://github.com/andy-pi/weather-monitor/blob/master/air_quality.py
def convertPM(nr,conf,value):
    if conf['units'][nr][0:3] == 'pcs': return value
    r = 0.44            # diameter of PM2.5
    if nr: r = 2.60     # diameter of PM10
    # concentration * K * mass (mass=:density (=:1.65*10**12) * vol (vol=:4/3 * pi * r**3))
    return value * 3531.5 * ((1.65 * (10**12)) * ((4/3.0) * 3.14159 * (r * (10**-6))**3))

# calibrate as ordered function order defined by length calibration factor array
def calibrate(nr,conf,value):
    if (not 'calibrations' in conf.keys()) or (nr > len(conf['calibrations'])-1):
        return value
    if type(value) is int: value = value/1.0
    if not type(value) is float: return None
    value = convertPM(nr,conf,value)
    rts = 0; pow = 0
    for a in Conf['calibrations'][nr]:
        rts += a*(value**pow)
        pow += 1
    return round(rts,2)

# =======================================================================
# serial USB input or via (test) input file
# =======================================================================
def open_serial():
    global Conf
    #  scan for available ports. return a list of tuples (num, name)
    def scan_serial():
        available = []
        for i in range(256):
            try:
                s = serial.Serial(i)
                available.append( (i, "/dev/ttyUSB"+str(i) ) )
                s.close()   # explicit close 'cause of delayed GC in java
            except serial.SerialException:
                pass
        return available

    if Conf['fd'] != None:
        return True

    if (not Conf['file']) and (Conf['port'] or Conf['usbid']):
        serial_dev = None
        # if port number == 0 we read from stdin
        # if port number == None we try serial USB product:vender ID
        if (Conf['port'] == None) and (Conf['usbid'] != None):
            # try serial with product ID
            byId = "/dev/serial/by-id/"
            if not os.path.exists(byId):
                MyLogger.log(modulename,'FATAL',"There is no USBserial connected. Abort.")
            device_re = re.compile(".*-%s.*_USB-Serial.*(?P<device>ttyUSB\d+)$" % Conf['usbid'], re.I)
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
        if (Conf['port'] == None) and (serial_dev == None):
            MyLogger.log(modulename,'WARNING',"Please provide serial USB producer info.")
            for n,s in scan_serial():
                port=n+1
                MyLogger.log(modulename,'WARNING',"%d --> %s" % (port,s) )
            MyLogger.log(modulename,'FATAL',"No input stream defined.")
            return False
        #Initialize Serial Port for Dylos
        if serial_dev == None:
            serial_dev = "/dev/ttyUSB"+str(Conf['port']-1)
        try:
            Conf['fd'] = serial.Serial(  # for here tuned for Dylos
                serial_dev,
                baudrate=9600,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                writeTimeout = 1,   # only needed if there was a firm upgrade on dylos
                timeout=65*60)      # allow also monitor mode
            MyLogger.log(modulename,'INFO',"COM used for serial USB: %s" % serial_dev)
        except (Exception) as error:
            MyLogger.log(modulename,'FATAL',"%s" % error)
            return False
    else:
        # input is read from a file
        if not Conf['file']:
            Conf['file'] = "Dylos-test.input"
        Conf['sync'] = False # no multi threading
        try:
            Conf['fd'] = open(Conf['file'])
        except:
            MyLogger.log(modulename,'FATAL', "Failed top open input for %s" % sensor)
            return False
    return True

MyThread = None
def registrate():
    global Conf, MyThread
    if not Conf['input']: return False
    if Conf['fd'] != None: return True
    Conf['input'] = False
    if (Conf['type'] == None) or (Conf['type'][0:5].lower() != 'dylos'):
        MyLogger.log(modulename,'ERROR','Incorrect Dylos type: %s' % Conf['type'])
        return False
    if not open_serial():
        return False
    Conf['input'] = True
    if MyThread == None: # only the first time
        MyThread = MyThreading.MyThreading( # init the class
            bufsize=Conf['bufsize'],
            interval=Conf['interval'],
            name='Dylos PM sensor',
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
    raise IOError("Unable to registrate/start Dylos thread.")
    Conf['input'] = False
    return False

# ================================================================
# Dylos PM count per minute per cubic food input via serial USB
# Dylos upgraded: Modified Firmware (v1.16f2) MAX = 4
# Dylos MAX = 2 PM2.5 PM10 counts
# ================================================================
# get a record
Conf['Serial_Errors'] = 0
def Add(conf):
    MAX = 2     # non std Dylos firmware might generate 4 numbers
    PM25 = 0 ; PM10 = 1 # array index defs
    try:
        # Request Dylos Data only for non std firmware
        # conf['fd'].write(bytes("R\r\n",'ascii'))
        #line = ''
        #while 1:
        #    chr = conf['fd'].read(1) 
        #    line += chr
        #    if chr == '\n':
        #        break
        try:
            line = conf['fd'].readline()
            if not conf['file']:
                while conf['fd'].inWaiting():       # skip to latest record
                    line = conf['fd'].readline()
            Serial_Errors = 0
        except SerialException:
            conf['Serial_Errors'] += 1
            MyLogger.log(modulename,'ATTENT',"Serial exception. Close/Open serial.")
            try:
                conf['fd'].close()
            except:
                pass
            conf['fd'] = None
            if conf['Serial_Errors'] > 10:
                MyLogger.log(modulename,'ERROR',"To many serial errors. Disabled.")
                conf['output'] = False
                return {}
            return conf['getdata']()
        except:
            sleep(10)
            return {}
        line = str(line.strip().decode('utf-8'))
        bin_data = []
        try:
            bin_data = [int(x.strip()) for x in line.split(',')]
        except:
            # Dylos Error
            MyLogger('WARNING',"Dylos Data: Error - Dylos Bin data")
            bin_data = [None] * MAX
        if (len(bin_data) > MAX) or (len(bin_data) < MAX): 
            MyLogger.log(modulename,'WARNING',"Data error")
        while len(bin_data) > MAX:
            del bin_data[len(bin_data)]
        while len(bin_data) < MAX:
            bin_data.append(None)
    except (Exception) as error:
        # Some other Dylos Error
        MyLogger.log(modulename,'WARNING',error)
    # take notice: index 0 is PM2.5, index 1 is PM10 values
    if ('raw' in conf.keys()) and (Conf['raw'] != None):
        conf['raw'].publish(
            tag='dylos',
            data="pm25=%.1f,pm10=%.1f" % (bin_data[PM25]*1.0,bin_data[PM10]*1.0))
    return { "time": int(time()),
            conf['fields'][PM25]: calibrate(PM25,conf,bin_data[PM25]),
            conf['fields'][PM10]: calibrate(PM10,conf,bin_data[PM10]) }

def getdata():
    global Conf, MyThread
    if not registrate():                # start up input readings
        return {}
    try:
        return MyThread.getRecord()     # pick up a record
    except IOError as er:
        MyLogger.log(modulename,'WARNING',"Sensor input failure: %s" % er)
    return {}

Conf['getdata'] = getdata	# Add needs this global viariable

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['input'] = True
    # Conf['sync'] = True
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
        timing = 30 - (time()-timing)
        if timing > 0:
            sleep(timing)
    if MyThread != None:
        MyThread.stop_thread()

