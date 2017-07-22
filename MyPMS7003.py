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

# $Id: MyPMS7003.py,v 1.2 2017/07/22 10:28:49 teus Exp teus $

# Defeat: output average PM count over 59(?) or 60 seconds:
#         continious mode: once per 59 minutes and 59 seconds!,
#         monitor mode: 60 times per hour 

""" Get sensor values: PM1, PM2.5 and PM10 from Plantower Particular Matter sensor
    Relies on Conf setting by main program
    if units is not defined as pcs the values are converted to ug/m3 (report Philadelphia)
"""
modulename='$RCSfile: MyPMS7003.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.2 $"[11:-2]

# configurable options
__options__ = [
    'input','type','usbid','firmware', 'calibrations',
    'fields','units',                 # one may change this as name and/or ug/m3 units
    'raw',                            # display raw measurements on stderr
    'sample',                         # collect the data from the module during N seconds
    'interval','bufsize','sync',  # multithead buffer size and search for input
]

Conf = {
    'input': False,      # SDS011 input sensor is required
    'fd': None,          # input handler
    'type': "Plantower PMS7003",         # type of device
    'usbid': 'Prolific.*-port',    # Qin Heng Electronics usb ID via lsusb
    'firmware': '',      # firmware number comes from module
    'serial': 'ED56',    # ID number
    'fields': ['pm1','pm25','pm10'],     # types of pollutants
     # 'pcs/qf' particle count per 0.01 qubic foot per minute
     #  spec: 0.01pcs/qf average per minute window
     # 'units' : ['pcs/qf','pcs/qf','pcs/qf'],   # dflt type the measurement unit
    'units' : ['ug/m3','ug/m3','ug/m3'],   # dflt type the measurement unit
    'calibrations': [[0,1],[0,1],[0,1]], # per type calibration (Taylor polonium)
    'sample': 60,        # get average of measurments per sample seconds from module
    'interval': 120,    # read cycle interval in secs (dflt)
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
    import MyLogger
    import re
    import subprocess           # needed to find the USB serial
    import MyThreading          # needed for multi threaded input
    import serial
    import struct               # needed for unpack data telegram
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

# conversion parameters come from:
# http://ir.uiowa.edu/cgi/viewcontent.cgi?article=5915&context=etd
def Mass2Con(pm,value):
    """Convert pm size from ug/m3 back to concentration pcs/0.01sqf"""
    pi = 3.14159
    density = 1.65 * pow (10, 12)
    if pm == 'pm25': radius = 0.44
    elif pm == 'pm10': radius = 2.60
    elif pm == 'pm1': radius = 0.17         # not sure this is correct
    else: return value
    radius *= pow(10,-6)
    volume = (4.0/3.0) * pi * pow(radius,3)
    mass = density * volume
    K = 3531.5
    concentration = value / (K * mass)
    return int(concentration+0.5)

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
        for item in ['interval','debug']:
            if type(Conf[item]) is str:
                if not Conf[item].isdigit():
                    MyLogger.log(modulename,'FATAL','%s should be nr of seconds' % item)
                Conf[item] = int(Conf[item])
	    if type(Conf[item]) is bool:
		Conf[item] = 1 if Conf[item] else 0
        MyLogger.log(modulename,'INFO',"Sample interval cycle is set to %d seconds." % Conf['interval'])
        MyLogger.log(modulename,'INFO',"(%s) values are in (%s)" % (','.join(Conf['fields']),','.join(Conf['units'])))
        try:
            Conf['fd'] = serial.Serial(serial_dev,
                                    baudrate=9600, stopbits=serial.STOPBITS_ONE,
                                    parity=serial.PARITY_NONE,
                                    bytesize=serial.EIGHTBITS,
                                    timeout=2)   # read timeout 2 seconds
            if not Conf['fd'].isOpen(): raise IOError("Unable to open USB to PMS7003")
            MyLogger.log(modulename,'INFO',"Serial used for USB: %s" % serial_dev)
            Conf['firmware'] = ''       # completed by first reading
        except IOError as error:
            MyLogger.log(modulename,"WARNING","Connectivity: %s" % error)
            Conf['fd'].device.close()
            return False
        except (Exception) as error:
            MyLogger.log(modulename,'FATAL',"%s" % error)
            return False
    else:
       Logger.log('ERROR', "Failed access PMS7003 module")
       return False
    return True

# index of list
PMS7003_FRAME_LENGTH = 0
PMS7003_PM1P0 = 1
PMS7003_PM2P5 = 2
PMS7003_PM10P0 = 3
PMS7003_PM1P0_ATM = 4
PMS7003_PM2P5_ATM = 5
PMS7003_PM10P0_ATM = 6
PMS7003_PCNT_0P3 = 7
PMS7003_PCNT_0P5 = 8
PMS7003_PCNT_1P0 = 9
PMS7003_PCNT_2P5 = 10
PMS7003_PCNT_5P0 = 11
PMS7003_PCNT_10P0 = 12
PMS7003_VER = 13
PMS7003_ERR_CODE = 14
PMS7003_CHECK_CODE = 15
PM_fields = [
            ('pm1','ug/m3',PMS7003_PM1P0),
            ('pm25','ug/m3'PMS7003_PM2P5),
            ('pm10','ug/m3',PMS7003_PM10P0),
            # concentration (generic atmosphere conditions) in ug/m3
            ('pm1_atm','ug/m3',PMS7003_PM1P0_ATM),
            ('pm25_atm','ug/m3',PMS7003_PM2P5_ATM),
            ('pm10_atm','ug/m3',PMS7003_PM10P0_ATM),
            # number of particles with diameter N in 0.1 liter air
            # 0.1 liter = 0.00353147 cubic feet -> pcs / 0.01qf
            ('pm03_cnt','pcs/0.1dm3',PMS7003_PCNT_0P3),
            ('pm05_cnt','pcs/0.1dm3',PMS7003_PCNT_0P5),
            ('pm1_cnt','pcs/0.1dm3',PMS7003_PCNT_1P0),
            ('pm25_cnt','pcs/0.1dm3',PMS7003_PCNT_2P5),
            ('pm5_cnt','pcs/0.1dm3',PMS7003_PCNT_5P0),
            ('pm10_cnt','pcs/0.1dm3',PMS7003_PCNT_10P0),
    ]

# read routine comes from irmusy@gmail.com http://http://irmus.tistory.com/
def PMSread(conf):
    ''' read data telegrams from the serial interface (32 bytes)
        and calculate average during sample seconds
        Omit a bit outliers by one measurment per second
    '''
    ErrorCnt = 0
    StrtTime = 0; cnt = 0; PM_sample = {}
    for fld in PM_fields: PM_sample[fld[0]] = 0.0
    while True:
        # clear the input buffer first so we get latest reading
        conf['fd'].flushInput()
        while True:     # search header of data telegram
            c = conf['fd'].read(1)         # 1st header
            if len(c) >= 1:
                if ord(c[0]) == 0x42:
                    c = conf['fd'].read(1) # 2nd header
                    if len(c) >= 1:
                        if ord(c[0]) == 0x4d:
                            break;

        if not cnt:
            StrtTime = time()
        buff = conf['fd'].read(30)         # packet remaining. fixed length packet structure
        # one measurement every second in configured sample time
        if cnt and (StrtTime+cnt < time()): continue   # skip measurement if time < 1 sec

        # calculate check code. Sum every byte from HEADER to ERR_CODE
        check = 0x42 + 0x4d
        for c in buff[0:28]: check += ord(c)
        # parsing
        pms7003_data = struct.unpack('!HHHHHHHHHHHHHBBH', buff)
        # compare check code
        if check != pms7003_data[PMS7003_CHECK_CODE]:
            MyLogger.log(modulename,"ERROR","Incorrect check code: received : 0x%04X, calculated : 0x%04X" % (pms7003_data[PMS7003_CHECK_CODE],check))
            ErrorCnt += 1
            if ErrorCnt > 10: raise IOError("Too many incorrect dataframes")
            continue
        if pms7003_data[PMS7003_ERR_CODE]:
            MyLogger.log(modulename,"WARNING","Module returned error: %s" % str(pms7003_data[PMS7003_ERR_CODE]))
            ErrorCnt += 1
            if ErrorCnt > 10: raise ValueError("Module errors %s" % str(pms7003_data[PMS7003_ERR_CODE]))
            continue
    
        if not conf['firmware']:
            conf['firmware'] = str(pms7003_data[PMS7003_VER])
            MyLogger.log(modulename,'INFO','Device %s, firmware %s' % (conf['type'],conf['firmware']))

        if conf['debug']:
            print 'Frame len [byte]            :', str(pms7003_data[PMS7003_FRAME_LENGTH])
            print 'Version                     :', str(pms7003_data[PMS7003_VER])
            print 'Error code                  :', str(pms7003_data[PMS7003_ERR_CODE])
            print 'Check code                  : 0x%04X' % (pms7003_data[PMS7003_CHECK_CODE])
        sample = {}
        for fld in PM_fields:
            # concentrations in unit ug/m3
            # concentration (generic atmosphere conditions) in ug/m3
            # number of particles with diameter N in 0.1 liter air pcs/0.1dm3
            sample[fld[0]] = pms7003_data[fld[2]]
            if conf['debug']:
                print '%s [%s]\t: ' % (fld[0],'ug/m3' if fld[0][-4:] != '_cnt' else 'pcs/0.1dm3'), str(sample[fld[0])
        cnt += 1
        for fld in PM_fields: PM_sample[fld[0]] += sample[fld[0]]
        if time() >= StrtTime + conf['sample']: break  
    if cnt:
        for fld in PM_fields: PM_sample[fld[0]] /= cnt
    return PM_sample

MyThread = None
def registrate():
    global Conf, MyThread
    if not Conf['input']: return False
    if Conf['fd'] != None: return True
    Conf['input'] = False
    # pms5003 or pms7003
    if (Conf['type'] == None) or (not Conf['type'][-7:].lower() in ('pms7003','pms5003')):
        return False
    cnt = 0
    for fld in Conf['fields']:  # make sure fields and units are defined
        fnd = False
        for pm in PM_fields:
            if fld != pm[0]: continue
            fnd = True
            try:
                if Conf['units'][cnt][-2:] != 'qf': 
                    Conf['units'][cnt] = pm[1]
            except:
                Conf['units'].append(pm[1])
            break
        if not fnd:
            MyLogger.log(modulename,'FATAL','Unknown field: %s' % fld)
            return False
    if not get_device():        # identify USB serial device
        return False
    if Conf['sample'] > Conf['interval']: Conf['sample'] = Conf['interval']
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
    raise IOError("Unable to registrate/start SDS011 thread.")
    Conf['input'] = False
    return False

# ================================================================
# Plantower PMS5003/7003 PM count per minute per ug/m3 input via serial USB
# ================================================================
# get a record
Conf['Serial_Errors'] = 0
def Add(conf):
    sample = {}
    while True:
        try:
            # if sleeping will have waited 30 secs
            conf['workstate'](conf,True)         # push module in working state
            sample = conf['serial'](conf)   # collect data telegram
            if conf['interval'] > 60: conf['workstate'](conf,False)      # go sleeping
            conf['Serial_Errors'] = 0
        except IOError:     # timeout
            MyLogger.log(modulename,'ERROR','serial error (timeout)')
            conf['Serial_Errors'] += 1
        except Exception:
            conf['Serial_Errors'] += 1
            MyLogger.log(modulename,'ERROR','error on reading serial.')
        if conf['Serial_Errors'] > 20:
            conf['fd'].device.close()
            conf['fd'] = None
	    MyLogger.log(modulename,"WARNING","Serial errors limit of 20 errors reached")
            raise IOError("SDS011 serial errors")
        if not conf['Serial_Errors']: break
    values = { "time": int(time())}; index = 0
    for fld in conf['fields']:
        value = sample[fld]
        if (fld in ['pm1','pm25','pm10']) and conf['units'][cnt] == 'pcs/qf':
            value = Mass2Con(fld,value)
        # 0.1 liter = 0.00353147 cubic feet -> pcs / 0.01qf
        if (fld[-4:] == '_cnt') and (conf['units'][cnt] == 'pcs/qf'):
            value *= 0.353147   # convert from liter to 0.01 qubic feet 
        values[fld] = calibrate(cnt,conf,value)
        index += 1
    data=[]
    if ('raw' in conf.keys()) and (Conf['raw'] != None):
        for fld in PM_fields:
            if fld[0] in ('pm1','pm25','pm10'):
                data.append('%s=%.1f' % (fld[0],Mass2Con(fld[0],sample[fld[0]])))
            elif fld[-4:] == '_cnt':
                # convert: pcs count in raw is pcs/0.01qf
                data.append('%s=%.1f' % (fld[0],0.353147*sample[fld[0]]))
            else:
                data.append('%s=%.1f' % (fld[0],sample[fld[0]]))
    if len(data):
        if conf['debug']:
            print("raw,sensor=%s %s %d000" % (conf['type'][-7:],','.join(data),values['time']*1.0))
        else:
            conf['raw'].publish(tag=conf['type'][-7:].lower(),data=','.join(data))
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

def PMSstate(conf,work):
    if work and not conf['state']:
        print("Put in work state")  # TO DO: add the serial command for this
        time.sleep(30)  # need 30 secs to stabilize air flow from fan
    elif Conf['state'] and not work:
        print("Put in sleep state")
    Conf['state'] = work

Conf['state'] = True            # Keep track of workstate module is in
Conf['workstate'] = PMSstate	# Add needs this global variable
Conf['serial'] = PMSread	# Add needs this global variable

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['input'] = True
    # Conf['sync'] = True         #multi threading off?
    Conf['debug'] = 1
    Conf['interval'] = 10       # sample once per 2 minutes
    Conf['units'] = ['pcs/qf','pcs/qf','pcs/qf'] # do values not in mass weight
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

