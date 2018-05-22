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

# $Id: MySPEC.py,v 1.9 2018/05/22 10:35:32 teus Exp teus $

# specification of HW and serial communication:
# http://www.spec-sensors.com/wp-content/uploads/2017/01/DG-SDK-968-045_9-6-17.pdf

""" Get sensor values from Spec sensors using Cygnal Integrated USB interfaces
    Relies on Conf setting by main program
    Output dict with gasses: NO2, CO, O3
"""
modulename='$RCSfile: MySPEC.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.9 $"[11:-2]

# configurable options
__options__ = [
    'input','type','usbid','calibrations',
    'fields','units',            # one may change this as name and/or ug/m3 units
    'raw',                       # display raw measurements
    'is_stable',                 # start measurements after # seconds
    'omits',                     # omit these sensors
    'serial',                    # serials nr to gas id of fields
    'dataFlds',                  # list of names to measure for sensor
    'interval','bufsize','sync'  # multithead buffer size and search for input
]

Conf = {
    'input': False,      # Spec gas sensors measuring is required
    'type': "Spec ULPSM",# type of device
    'usbid': 'SPEC',     # name as defined by udev rules, e.g. /dev/SPEC1
    'serial': ['022717020254','030817010154','110816020533','030817010154','111116010138'],# S/N number
    'fields': ['o3','no2','co','so2','no2'],   # types of pollutants
    'units' : ['ppb','ppb','ppb','ppb','ppb'], # dflt type the measurement unit
    'calibrations': [[0,1],[0,1],[0,1],[0,1],[0,1]], # per type calibration (Taylor polonium)
    'interval': 60,     # read interval in secs (dflt)
    'bufsize': 30,      # size of the window of values readings max
    'sync': False,      # use thread or not to collect data
    'raw': False,       # dflt display raw measurements
    'debug': False,     # be more versatile on input data collection
    'is_stable': 3600,  # seconds after measuments are stable (dflt 1 hour)
    # 'serials': [],    # conf variables fpr threads measurement data
    'omits': ['nh3'],   # sensors to be omitted
    # list of show data: (data format of input)
    # 'sn','ppb','temp','rh','raw','traw','hraw','day','hour','min','sec'
    'dataFlds': [None,'ppb','temp','rh',None,None,None,None,None,None,None],
}
#    from MySense import log
try:
    try:
        import os
        from time import time
        from time import sleep
        from types import ModuleType as module
        import MyLogger
        import serial
    except:
        try:
            import Serial as serial
        except ImportError as e:
            MyLogger.log(modulename,'FATAL',"Missing module %s" % e)
    import re
    import subprocess           # needed to find the USB serial
    import MyThreading          # needed for multi threaded for input
except ImportError as e:
    MyLogger.log(modulename,'FATAL',"Missing module %s" % e)

# try to read from EEProm the gas ID
# on failure use serial nr of measurement from configuration as gas ID
def ReadEEprom(serial,cnt=0):
    global Conf
    if cnt > 3: return None
    cnt += 1
    # TO DO: add interval for average by sensor
    serial.write(bytes("e")) # require eeprom info
    sleep(1); nr = 0; eeprom = {}
    while serial.inWaiting():
        if nr > 25: break
        nr += 1
        try:
          line = serial.readline()
          line = str(line.strip().decode('utf-8'))
          line = line.split('=')
          if len(line) != 2:
            line = line[0].split(',')
            if len(line) == 11: # we have measurement data
              try:
                eeprom['gas'] = Conf['fields'][Conf['serial'].index(line[0])]
              except: pass
              continue
          eeprom[line[0].lower()] = line[1].lower()
        except:
          break
    if (not len(eeprom)) or (not 'gas' in eeprom.keys()):
        return ReadEEprom(serial, cnt=cnt)
    if Conf['debug']:
        for key in eeprom.keys():
            MyLogger.log(modulename,'INFO','Spec sensor eeprom %s: %s' % (key,eeprom[key].upper()))
    return eeprom['gas']

# =======================================================================
# serial USB input or via (test) input file
# =======================================================================
def open_serial():
    global Conf

    # TO DO: support a reopen of serial
    if ('serials' in Conf.keys()) and len(Conf['serials']):
        return True
    else: Conf['serials'] = []

    if not Conf['usbid']:
        return False
    # try serial with product ID
    byId = "/dev/"
    if not os.path.exists(byId):
        MyLogger.log(modulename,'FATAL',"There is no USBserial connected. Abort.")
    device_re = re.compile(".*%s\d+ .*(?P<device>ttyUSB\d+)$" % Conf['usbid'], re.I)
    try:
        df = subprocess.check_output(["/bin/ls","-l",byId])
        for i in df.split('\n'):
            if i:
                info = device_re.match(i)
                if info:
                    dinfo = info.groupdict()
                    Conf['serials'].append({ 'device': '/dev/%s' % dinfo.pop('device')})
        if not len(Conf['serials']): raise CalledProcessError
    except CalledProcessError:
        MyLogger.log(modulename,'ERROR',"No serial USB connected.")
        return False
    except (Exception) as error:
        MyLogger.log(modulename,'ERROR',"Serial USB %s not found, error:%s"%(Conf['usbid'], error))
        Conf['usbid'] = None
        return False
    for one in range(len(Conf['serials'])-1,-1,-1):
        try:
          Conf['serials'][one]['fd'] = serial.Serial(
            Conf['serials'][one]['device'],
            baudrate=9600,
            # parity=serial.PARITY_ODD,
            # stopbits=serial.STOPBITS_TWO,
            # bytesize=serial.SEVENBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            writeTimeout = 1,
            timeout=5)
          Conf['serials'][one]['gas'] = ReadEEprom(Conf['serials'][one]['fd'])
          if Conf['serials'][one]['gas'] == None:
            raise Exception, 'sensor not supported'
          else:
            try:
              Conf['omits'].index(Conf['serials'][one]['gas'])
              MyLogger.log(modulename,'INFO',"Omit gas %s measurements" % Conf['serials'][one]['gas'])
              Conf['serials'][one]['fd'].close()
              Conf['serials'].pop(one)
              continue
            except: pass
          Conf['serials'][one]['start'] = time() + Conf['is_stable']
          MyLogger.log(modulename,'INFO',"Gas %s sensor at serial USB: %s" % (Conf['serials'][one]['gas'].upper(),Conf['serials'][one]['device']))
          try:
            Conf['serials'][one]['index'] = Conf['fields'].index(Conf['serials'][one]['gas'])
          except:
            MyLogger.log(modulename,'WARNING','Gas sensor %s not in Spec config fields, skipped')
            raise Exception, 'sensor not configured'
          Conf['serials'][one]['calibrations'] = Conf['calibrations']
        except (Exception) as error:
          MyLogger.log(modulename,'ERROR',"Cannot connect to %s: %s" % (Conf['serials'][one],error))
          if Conf['serials'][one]['fd']: Conf['serials'][one]['fd'].close()
          Conf['serials'].pop(one)
          continue
        
    if not len(Conf['serials']):
        MyLogger.log(modulename,'ERROR',"No serial gas USB connected")
        return False
    # MyLogger.log(modulename,'INFO',"Connected %d Spec gas sensors" % len(Conf['serials']))
    return True

# calibrate as ordered function order defined by length calibration factor array
def calibrate(nr,factors,value):
    try:
        if type(factors[nr]) != list: return value
    except:
        return value
    if type(value) is int: value = value/1.0
    if not type(value) is float: return None
    thisnr = 0
    if nr == 0: thisnr = 1
    rts = 0; pow = 0
    for a in factors[thisnr]:
        rts += a*(value**pow)
        pow += 1
    return round(rts,2)


MyThread = []
def registrate():
    global Conf, MyThread
    if not Conf['input']: return False
    if ('serials' in Conf.keys()) and len(Conf['serials']): return True
    Conf['input'] = False
    # if (Conf['type'] == None) or (Conf['type'][6:].upper() != 'ULPSM'):
    #     MyLogger.log(modulename,'ERROR','Incorrect Spec type: %s' % Conf['type'])
    #     return False
    for key in ['serial','omits']:
        if (key in Conf.keys()) and (type(Conf[key]) is str):
            Conf[key] = Conf[key].replace(' ','').split(',')
    if not open_serial():
        return False
    if not len(MyThread): # only the first time
        for thread in range(0,len(Conf['serials'])):
          try:
            MyThread.append(MyThreading.MyThreading( # init the class
              bufsize=Conf['bufsize'],
              interval=Conf['interval'],
              name='%s' % Conf['serials'][thread]['gas'].upper(),
              callback=Add,
              conf=Conf['serials'][thread],
              sync=Conf['sync'],
              DEBUG=Conf['debug']))
            # first call is interval secs delayed by definition
            try:
              if MyThread[thread].start_thread(): # start multi threading
                continue
            except:
              MyThread.pop()
              MyLogger.log(modulename,'ERROR','failed to start Spec thread %d' % thread)
          except: pass
    if not len(MyThread): return False
    Conf['input'] = True
    return True

# get a record from serial by thread
def Add(conf):
    global Conf
    # ref: aqicn.org/faq/2015-09-06/ozone-aqi-using-concentrations-in-milligrams-or-ppb/
    # ref:  samenmetenaanluchtkwaliteit.nl/zelf-meten
    def PPB2ugm3(gas,ppb,temp):
        mol = {
            'so2': 64.0,   # RIVM 2.71, ?
            'no2': 46.0,   # RIVM 1.95, ?
            'no':  30.01,  # RIVM 1.27, ?
            'o3':  48.0,   # RIVM 2.03, ?
            'c0':  28.01,  # RIVM 1.18, ?
            'co2': 44.01,  # RIVM 1.85, ?
            'nh3': 17.031,
        }
        if not gas in mol.keys(): raise ValueError, "%s unknown gas" % gas
        if ppb < 0: return 0
        return round(ppb*12.187*mol[gas]/(273.15+temp),2)

    # serial line data: SN,PPB,temp oC,RH%,ADCraw,Traw,RHraw,day,hour,min,sec
    MAX = len(Conf['dataFlds'])
    if conf['fd'] == None:
        sleep(0)   # sleep for ever thread
        return {}
    if not 'Serial_Errors' in conf.keys(): conf['Serial_Errors'] = 0
    if conf['Serial_Errors'] > 10:
        MyLogger.log(modulename,'ERROR',"To many serial errors. Disabled.")
        conf['fd'].close(); conf['fd'] = None
        sleep(0)   # thread sleeps forever. Should reset sensor and serial
        return {}
    line = ''; bin_data = []
    try:
        try:
            while conf['fd'].inWaiting():       # skip to latest record
                line = conf['fd'].readline()
            Serial_Errors = 0
            conf['fd'].write(bytes("\r"))   # request measurement
            sleep(2)
            line = conf['fd'].readline()
            line = str(line.strip().decode('utf-8'))
        except SerialException:
            conf['Serial_Errors'] += 1
            MyLogger.log(modulename,'ATTENT',"Serial exception. Close/Open serial.")
            return {}
        except:
            conf['Serial_Errors'] += 1
            sleep(10)
            return Add(conf)
        now = time()
        if conf['start'] - now > 0:
            sleep (conf['start'] - now)
            return Add(conf)
        try:
            bin_data = [int(x.strip()) for x in line.split(',')]
        except:
            # Spec Error
            MyLogger('WARNING',"Spec Data: Error - Spec Bin data")
            bin_data = [None] * MAX
        if len(bin_data) != MAX:
            MyLogger.log(modulename,'WARNING',"Data length error")
            conf['Serial_Errors'] += 1
            return Add(conf)
        conf['Serial_Errors'] = 0
    except (Exception) as error:
        # Some other sensor Error
        MyLogger.log(modulename,'WARNING',str(error))
    values = { "time": int(now) }; rawData = []
    for i in range(0,MAX):
        if Conf['dataFlds'][i] == None: continue
        rawData.append('%s=%.1f' % (conf['gas'].lower() if i == 0 else Conf['dataFlds'][i],bin_data[i]))
        if Conf['dataFlds'][i] == 'ppb':
          idx = Conf['fields'].index(conf['gas'])
          values[conf['gas']] = calibrate(idx,Conf['calibrations'],bin_data[i])
          if Conf['units'][idx] == 'ug/m3':
            try:
                tempVal = float(bin_data[Conf['dataFlds'].index('temp')])
            except:
                tempVal = 25.0
            values[conf['gas']] = PPB2ugm3(conf['gas'],values[conf['gas']],tempVal)
        elif Conf['dataFlds'][i][-3:] == 'raw':
          values[conf['gas']+Conf['dataFlds'][i]] = int(bin_data[i])
        else:
          try:
            values[Conf['dataFlds'][i]] = calibrate(Conf['fields'].index(Conf['dataFlds'][i]),Conf['calibrations'],bin_data[i])
          except:
            values[Conf['dataFlds'][i]] = int(bin_data[i])
    if ('raw' in Conf.keys()) and (type(Conf['raw']) is module):
        Conf['raw'].publish(
            tag='Spec%s' % conf['gas'].upper(),
            data=','.join(rawData))
    return values

def getdata():
    global Conf, MyThread
    if not registrate():                # start up input readings
        return {}
    try:
        values = { 'time': time(), }
        for i in range(0,len(MyThread)):
            thisSensor = MyThread[i].getRecord()
            for key in thisSensor.keys():
                if key in Conf['fields'] + ['time']: values[key] = thisSensor[key]
    except IOError as er:
        MyLogger.log(modulename,'WARNING',"Sensor input failure: %s" % er)
    return values

Conf['getdata'] = getdata	# Add needs this global viariable

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['input'] = True
    Conf['sync'] = True
    Conf['debug'] = True
    Conf['raw'] = None
    Conf['is_stable'] = 0
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
    for Thread in MyThread:
      if Thread != None:
        Thread.stop_thread()

