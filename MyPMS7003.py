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

# $Id: MyPMS7003.py,v 1.4 2017/07/28 11:51:56 teus Exp teus $

# Defeat: output (moving) average PM count in period sample time seconds (dflt 60 secs)
#         active (monitor) mode: continues read (200-600 msec) during sample time
#         passive mode: every second one read in period sample time
#         interval time (dflt 120 secs) defines one sample time per interval
#         passive mode: if idle time (interval - sample) > IDLE (120 secs)
#               fan will be switched OFF
# Hi8nt: use PM atm values (ug/m3 or particle count values, unit: pcs/0.1l or pcs/0.01qf

""" Get sensor values: PM1, PM2.5 and PM10 from Plantower Particular Matter sensor
    Types: 7003 or 5003
    Relies on Conf setting by main program
    if units is not defined as pcs the values are converted to ug/m3 (report Philadelphia)
    sensor: default on power on: active mode, in passive mode per second reading
        if effective fan will be switched off,
        after fan is switched on: reading delay is 30 seconds
    units: pcs/0.01qf, pcs/0.1dm3, ug/m3
"""
modulename='$RCSfile: MyPMS7003.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.4 $"[11:-2]

# configurable options
__options__ = [
    'input','type','usbid','firmware', 'calibrations',
    'prepend',                        # prepend field names with this string
    'fields','units',                 # one may change this as name and/or ug/m3 units
    'raw', 'rawCnt',                  # display raw measurements on stderr
    'sample',                         # collect the data from the module during N seconds
    'interval','bufsize','sync',  # multithead buffer size and search for input
]

Conf = {
    'input': False,      # SDS011 input sensor is required
    'fd': None,          # input handler
    'type': "Plantower PMS7003",         # type of device
    'usbid': 'Prolific.*-port',    # Qin Heng Electronics usb ID via lsusb
    'firmware': '',      # firmware number comes from module
    'prepend': '',       # prepend field name on output with this string
    'fields': ['pm1_atm','pm25_atm','pm10_atm'],     # types of pollutants
     # 'pcs/qf' particle count per 0.01 qubic foot per minute
     #  spec: 0.01pcs/qf average per minute window
     # 'units' : ['pcs/qf','pcs/qf','pcs/qf'],   # dflt type the measurement unit
    'units' : ['ug/m3','ug/m3','ug/m3'],   # dflt type the measurement unit
    'calibrations': [[0,1],[0,1],[0,1]], # per type calibration (Taylor polonium)
    'sample': 60,        # get average of measurments per sample seconds from module
     # see also IDLE time to witch off fan
    'interval': 120,    # read cycle interval in secs (dflt)
    'bufsize': 30,      # size of the window of values readings max
    'sync': False,      # use thread or not to collect data
    'debug': 0,         # level 0 .. 5, be more versatile on input data collection
    'raw': False,       # display raw measurement data with timestamps
    'rawCnt': True,     # convert raw mass (ug/m3) to pcs/0.01qf units

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
        for item in ['interval','sample','debug','rawCnt']:
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
            ('pm25','ug/m3',PMS7003_PM2P5),
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


ACTIVE  = 0     # mode active, default mode from power on
PASSIVE = 1     # mode passive
NORMAL  = 3     # mode passive state normal fan ON
STANDBY = 4     # mode passive, state standby fan OFF
# idle time to switch fan off
IDLE    = 120   # minimal idle time between sample time and interval

# send mode/state change to PMS sensor
# check answer
def SendMode(conf,cmd,ON):
    ''' send 42 4D cmd (E2,E4,E1) 00 ON (On=1,Off=0) chckH chckL
        no answer on cmd: E2 (read telegram) and E4 On (active mode)
        answer 42 4D 00 04 cmd 00 chckH chckL
    '''
    if not cmd in (0xE1,0xE2,0xE4): return
    if ON: ON = 0x1
    ChckSum = 0x42+0x4D+cmd+0x0+ON
    data = struct.pack('!BBBBBH',0x42,0x4D,cmd,0x0,ON,ChkSum)
    try:
        conf['fd'].write(data)
        if conf['debug']:
            print("Send command 0x%X 0x%X 0x%X 0x%X 0x%X 0x%x 0x%x" % struct.unpack('!BBBBBBB',data))
    except:
        MyLogger(modulename,'ERROR','Unable to send mode/state change.')
        raise IOError("Unable to set mode/state")
    if (cmd == 0xE2) or ((cmd == 0xE4) and ON):
        return True
    # check the answer
    ChckSum += 4
    try:
        while True:
            c = conf['fd'].read(1)
            if not len(c): raise IOError("Failure mode/state change")
            if ord(c[0]) != 0x42: continue
            c = conf['fd'].read(1)
            if not len(c): raise IOError("Failure mode/state change")
            if ord(c[0]) != 0x4D: continue
            data = conf['fd'].read(6)
            check = 0x42+0x4D
            for c in data[0:6]: check += ord(c)
            if conf['debug']:
                print("Send command 0x42 0x4D 0x%X 0x%X 0x%X 0x%x 0x%x" % struct.unpack('!BBBBB',data))
            buf = struct.unpack('!BBBBH', data)
            # if (buf[4] == ChckSum):
            if (ord(data[1]) == 0x4) and (ord(data[2]) == cmd) and (buf[4] == ChckSum):
                return True
            MyLogger.log(modulename,'ERROR','Mode/state change received wrong answer 0x42 0x4D 0x%X 0x%X 0x%X 0x%x 0x%x' % struct.unpack('!BBBBB',data))
            return False
    except:
        pass
    return False
    
# passive mode, go into standby state / sleep: fan OFF
# 42 4D E4 00 00 01 73 - standby mode  answer: 42 4D 00 04 E4 00 01 77
def Standby(conf):
    global STANDBY
    if conf['mode'] != STANDBY:
        if conf['mode'] == ACTIVE: GoPassive(conf)
        # send 42 4D E4 00 00 01 73
        # receive 42 4D 00 04 E4 00 01 77
        if not SendMode(conf,0xE4,0): return False
        conf['mode'] = STANDBY
    return True

# passive mode, go into normal state: fan ON, allow data telegrams reading
# 42 4D E4 00 01 01 74 - standby wakeup answer: data 32 byte telegrams
def Normal(conf):
    global NORMAL, ACTIVE
    if conf['mode'] != NORMAL:
        if conf['mode'] == ACTIVE: GoPassive(conf)
        if conf['mode'] != NORMAL:
            # send 42 4D E4 00 01 01 74
            if not SendMode(conf,0xE4,1): return False
            conf['mode'] = NORMAL
    return True

# from passive mode go in active mode (same as with power on)
# 42 4D E1 00 01 01 71 - active mode   answer: 42 4D 00 04 E1 01 01 75
def GoActive(conf):
    ''' go in power ON, active mode, start sending data telegrams of 32 bytes '''
    global STANDBY, IDLE
    if conf['mode'] == STANDBY:
        Normal(conf)
        sleep(30)      # wait 30 seconds to establish air flow
    # send 42 4D E1 00 01 01 71
    # receive 42 4D 00 04 E1 01 01 75
    if not SendMode(conf,0xE1,1): return False
    conf['mode'] = ACTIVE
    if conf['interval'] - conf['sample'] >= IDLE:
        GoPassive(conf)
    return True

# from active mode go into passive mode (passive normal state ?)
# 42 4D E1 00 00 01 70 - passive mode  answer: 42 4D 00 04 E1 00 01 74
def GoPassive(conf):
    ''' go in passive mode, normal state '''
    global ACTIVE, PASSIVE
    if conf['mode'] == ACTIVE:
        # send 42 4D E1 00 00 01 70
        # receive 42 4D 00 04 E1 00 01 74
        if not SendMode(conf,0xE1,0): return False
    conf['mode'] = PASSIVE      # state NORMAL?
    return Normal(conf)

# in passive mode do one data telegram reading
# 42 4D E2 00 00 01 71 - passive mode read instruction
def PassiveRead(conf):
    global ACTIVE, STANDBY
    if conf['mode'] == ACTIVE: return
    if conf['mode'] == STANDBY:
        Normal(conf)
        sleep(30)      # wait 30 seconds to establish air flow
    # send 42 4D E2 00 00 01 71
    return SendMode(conf,0xE2,0)


# read routine comes from irmusy@gmail.com http://http://irmus.tistory.com/
def PMSread(conf):
    ''' read data telegrams from the serial interface (32 bytes)
        for the period sample time
        # and calculate average during sample seconds
        # Omit a bit outliers by one measurment per second
        Calculate sum of measurements during the sample time
    '''
    global ACTIVE, PASSIVE
    ErrorCnt = 0
    StrtTime = 0; cnt = 0; PM_sample = {}
    if not 'wait' in conf.keys(): conf['wait'] = 0
    if conf['wait'] > 0: sleep(conf['wait'])
    for fld in PM_fields: PM_sample[fld[0]] = 0.0
    # clear the input buffer first so we get latest reading
    conf['fd'].flushInput()
    StrtTime = 0; LastTime = 0
    while True:
        if (conf['mode'] != ACTIVE):
            # in PASSIVE mode we wait one second per read
            if cnt:
                wait = time()-LastTime
                if (wait < 1) and (wait > 0):
                    sleep(wait)
            PassiveRead(conf)   # if fan off switch it on, if passive initiate read
        while True:     # search header of data telegram 0x42 0x4D
            while True:
                try:
                    c = conf['fd'].read(1)         # 1st header
                except:   # time out on read, try wake it up
                    ErrorCnt += 1
                    if ErrorCnt >= 10:
                        raise IOError("Sensor PMS connected?")
                    MyLogger.log(modulename,'WARNING','Try to wakeup sensor')
                    if conf['mode'] == ACTIVE:
                        conf['mode'] = PASSIVE
                        if GoActive(conf): continue
                    else:
                        PassiveRead(conf)
                        continue
                break
            if len(c) >= 1:
                if ord(c[0]) == 0x42:
                    c = conf['fd'].read(1) # 2nd header
                    if len(c) >= 1:
                        if ord(c[0]) == 0x4d:
                            break;

        if not cnt: StrtTime = time()
        LastTime = time()
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

        # if conf['debug']:
        #     print 'Frame len [byte]            :', str(pms7003_data[PMS7003_FRAME_LENGTH])
        #     print 'Version                     :', str(pms7003_data[PMS7003_VER])
        #     print 'Error code                  :', str(pms7003_data[PMS7003_ERR_CODE])
        #     print 'Check code                  : 0x%04X' % (pms7003_data[PMS7003_CHECK_CODE])
        sample = {}
        for fld in PM_fields:
            # concentrations in unit ug/m3
            # concentration (generic atmosphere conditions) in ug/m3
            # number of particles with diameter N in 0.1 liter air pcs/0.1dm3
            sample[fld[0]] = float(pms7003_data[fld[2]]) # make it float
        if conf['debug']:
            if not cnt:
                for fld in PM_fields:
                    sys.stderr.write("%8.8s " % fld[0])
                sys.stderr.write("\n")
                for fld in PM_fields:
                    sys.stderr.write("%8.8s " % ('ug/m3' if fld[0][-4:] != '_cnt' else 'pcs/0.1dm3'))
                sys.stderr.write("\n")
            for fld in PM_fields:
                sys.stderr.write("%8.8s " % str(sample[fld[0]]))
            sys.stderr.write("\n")
            #print("%s [%s]\t: " % (fld[0],'ug/m3' if fld[0][-4:] != '_cnt' else 'pcs/0.1dm3'), str(sample[fld[0]]))
        cnt += 1
        for fld in PM_fields: PM_sample[fld[0]] += sample[fld[0]]
        if time() >= StrtTime + conf['sample']: break  
    SampleTime = time() - StrtTime
    if SampleTime < 0: SampleTime = 0
    if cnt:     # average count during the sample time
        for fld in PM_fields:
            # PM_sample[fld[0]] *= SampleTime / conf['sample']
            PM_sample[fld[0]] /= cnt
        if conf['debug']:
            print("Average read time: %.2f secs, # reads %d,sample time %.1f seconds" % (SampleTime/cnt,cnt,SampleTime))
    conf['wait'] = conf['interval'] - SampleTime
    if conf['wait'] < 0: conf['wait'] = 0
    if conf['wait']  >= 60:
        if conf['mode'] != ACTIVE:
            Standby(conf)        # switch fan OFF
    return PM_sample

MyThread = None
def registrate():
    global Conf, MyThread, IDLE, ACTIVE
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
    Conf['Serial_Errors'] = 0
    if not get_device():        # identify USB serial device
        return False
    if Conf['sample'] > Conf['interval']: Conf['sample'] = Conf['interval']
    # go passive mode and switch fan on more as IDLE secs idle reading time
    # default on start put sensor module in active mode
    Conf['mode'] = ACTIVE
    if Conf['interval'] - Conf['sample'] >= IDLE: GoPassive(Conf)
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
def Add(conf):
    sample = {}
    while True:
        try:
            # if sleeping will have waited 30 secs
            sample = conf['serial'](conf)   # collect data telegram
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
        # e.g. pm1 and pm1_atm are in units of ug/m3
        if (fld.replace('_atm','') in ['pm1','pm25','pm10']) and conf['units'][cnt] == 'pcs/qf':
            value = Mass2Con(fld.replace('_atm',''),value)
        # 0.1 liter = 0.00353147 cubic feet -> pcs / 0.01qf
        if (fld[-4:] == '_cnt') and (conf['units'][cnt] == 'pcs/qf'):
            value *= 0.353147   # convert from liter to 0.01 qubic feet 
        values[conf['prepend']+fld] = calibrate(cnt,conf,value)
        index += 1
    data=[]
    if ('raw' in conf.keys()) and (Conf['raw'] != None):
        for fld in PM_fields:
            if fld[-4:] == '_cnt':
                # convert: pcs count in raw is pcs/0.01qf
                data.append('%s=%.1f' % (fld[0],0.353147*sample[fld[0]]))
            elif not conf['rawCnt']:  # want raw values in ug/m3
                data.append('%s=%.1f' % (fld[0],sample[fld[0]]))
            else:                     # convert values to pcs/0.01qf units
                data.append('%s=%.1f' % (fld[0],Mass2Con(fld[0].replace('_atm',''),sample[fld[0]])))
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

Conf['serial'] = PMSread	# Add needs this global variable

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['input'] = True
    Conf['sync'] = True         # multi threading off?
    Conf['debug'] = 1           # print intermediate values
    # Conf['interval'] = 180     # sample once per 3 minutes, causes passive mode
    Conf['fields'] = ['pm1','pm25','pm10'] # do values not in mass weight
    Conf['units'] = ['pcs/qf','pcs/qf','pcs/qf'] # do values not in mass weight
    Conf['raw'] = True          # display raw data with timestamps
    Conf['prepend'] = 'pt_'     # prepend fields name with plantower id

    for cnt in range(0,10):
        timings = time()
        try:
            data = getdata()
        except Exception as e:
            print("input sensor error was raised as %s" % e)
            break
        print("Getdata returned:")
        print(data)
        timings = 5*60 - (time()-timings)
        if timings > 0:
            print("Sleep for %d seconds" % timings)
            sleep(timings)
    if MyThread != None:
        MyThread.stop_thread()

