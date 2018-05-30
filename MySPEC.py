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

# $Id: MySPEC.py,v 1.21 2018/05/30 19:55:36 teus Exp teus $

# specification of HW and serial communication:
# http://www.spec-sensors.com/wp-content/uploads/2017/01/DG-SDK-968-045_9-6-17.pdf

""" Get sensor values from Spec sensors using Cygnal Integrated USB interfaces
    Relies on Conf setting by main program
    Output dict with gasses: NO2, CO, O3
"""
modulename='$RCSfile: MySPEC.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.21 $"[11:-2]

# configurable options
__options__ = [
    'input','type','usbid','calibrations',
    'fields','units',            # one may change this as name and/or ug/m3 units
    'raw',                       # display raw measurements
    'is_stable',                 # start measurements after # seconds
    'omits',                     # omit these sensors
    'serials',                   # serials nr to gas id of fields
    'dataFlds',                  # list of names to measure for sensor
    'prefix',                    # boolean prefix field names with 3 type chars
    'debug',                     # debugging flag
    'interval','bufsize','sync'  # multithead buffer size and search for input
    # may need to add rename
]

Conf = {
    'input': False,      # Spec gas sensors measuring is required
    'type': "Spec ULPSM",# type of device
    'usbid': 'SPEC',     # name as defined by udev rules, e.g. /dev/SPEC1
    'serials': ['022717020254','110816020533','030817010154','111116010138','123456789'],# S/N number
    'fields': ['o3','no2','so2','co','eth'],   # types of pollutants
    'units' : ['ug/m3','ug/m3','ug/m3','ug/m3','ug/m3'], # dflt type the measurement unit
    'calibrations': [[0,1],[0,1],[0,1],[0,1],[0,1]], # per type calibration (Taylor polonium)
    'interval': 15,     # read interval in secs (dflt)
    'bufsize': 30,      # size of the window of values readings max
    'sync': False,      # use thread or not to collect data
    'raw': False,       # dflt display raw measurements
    'debug': False,     # be more versatile on input data collection
    'is_stable': 3600,  # seconds after measuments are stable (dflt 1 hour)
    # 'mySerials': [],    # conf variables fpr threads measurement data
    'omits': ['nh3','temp','rh','unkown'],   # sensors to be omitted
    # list of show data: (data format of input)
    # 'sn','ppb','temp','rh','raw','traw','hraw','day','hour','min','sec'
    'dataFlds': [None,'ppb','temp','rh',None,None,None,None,None,None,None],
    # 'rename' : { 'temp': 'stemp', 'rh': 'srh' },  # rename a field name
    'prefix':  False,   # prefix field name with first 3 chars of type.lower()
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
    sleep(1); nr = 0; eeprom = { 'sn': '0' }
    while serial.inWaiting():
        if nr > 25: break
        nr += 1
        try:
          line = serial.readline()
          line = str(line.strip().decode('utf-8'))
          line = line.split('=')
          if len(line) != 2:
            line = line[0].split(',')
            if len(line) == 11: # len(Conf['dataFlds']) measurement data
              try:
                eeprom['gas'] = Conf['fields'][Conf['serials'].index(line[0])]
                eeprom['sn'] = line[0]
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
    return eeprom

# =======================================================================
# serial USB input or via (test) input file
# =======================================================================
def open_serial():
    global Conf

    # TO DO: support a reopen of serial
    if ('mySerials' in Conf.keys()) and len(Conf['mySerials']):
        return True
    else: Conf['mySerials'] = []

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
                    Conf['mySerials'].append({ 'device': '/dev/%s' % dinfo.pop('device')})
        if not len(Conf['mySerials']): raise CalledProcessError
    except CalledProcessError:
        MyLogger.log(modulename,'ERROR',"No serial USB connected.")
        return False
    except (Exception) as error:
        MyLogger.log(modulename,'ERROR',"Serial USB %s not found, error:%s"%(Conf['usbid'], error))
        Conf['usbid'] = None
        return False
    for one in range(len(Conf['mySerials'])-1,-1,-1):
        try:
          Conf['mySerials'][one]['fd'] = serial.Serial(
            Conf['mySerials'][one]['device'],
            baudrate=9600,
            # parity=serial.PARITY_ODD,
            # stopbits=serial.STOPBITS_TWO,
            # bytesize=serial.SEVENBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            writeTimeout = 1,
            timeout=15)
          Conf['mySerials'][one]['eeprom'] = ReadEEprom(Conf['mySerials'][one]['fd'])
          Conf['mySerials'][one]['gas'] = Conf['mySerials'][one]['eeprom']['gas']
          if Conf['mySerials'][one]['gas'] == None:
            raise Exception, 'sensor not supported'
          else:
            try:
              Conf['omits'].index(Conf['mySerials'][one]['gas'])
              MyLogger.log(modulename,'INFO',"Omit gas %s measurements" % Conf['mySerials'][one]['gas'])
              Conf['mySerials'][one]['fd'].close()
              Conf['mySerials'].pop(one)
              continue
            except: pass
          Conf['mySerials'][one]['start'] = time() + Conf['is_stable']
          MyLogger.log(modulename,'INFO',"Gas %s sensor S/N %s at serial USB: %s" % (Conf['mySerials'][one]['gas'].upper(),Conf['mySerials'][one]['eeprom']['sn'],Conf['mySerials'][one]['device']))
          try:
            Conf['mySerials'][one]['index'] = Conf['fields'].index(Conf['mySerials'][one]['gas'])
          except:
            MyLogger.log(modulename,'WARNING','Gas sensor %s not in Spec config fields, skipped')
            raise Exception, 'sensor not configured'
          Conf['mySerials'][one]['calibrations'] = Conf['calibrations']
          if 'raw' in Conf.keys(): Conf['mySerials'][one]['raw'] = Conf['raw']
          else: Conf['mySerials'][one]['raw'] = False
        except (Exception) as error:
          MyLogger.log(modulename,'ERROR',"Cannot connect to %s: %s" % (Conf['mySerials'][one],error))
          if Conf['mySerials'][one]['fd']: Conf['mySerials'][one]['fd'].close()
          Conf['mySerials'].pop(one)
          continue
        
    if not len(Conf['mySerials']):
        MyLogger.log(modulename,'ERROR',"No serial gas USB connected")
        return False
    # MyLogger.log(modulename,'INFO',"Connected %d Spec gas sensors" % len(Conf['mySerials']))
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
    if ('mySerials' in Conf.keys()) and len(Conf['mySerials']): return True
    Conf['input'] = False
    # if (Conf['type'] == None) or (Conf['type'][6:].upper() != 'ULPSM'):
    #     MyLogger.log(modulename,'ERROR','Incorrect Spec type: %s' % Conf['type'])
    #     return False
    for key in ['serials','omits']:
        if (key in Conf.keys()) and (type(Conf[key]) is str):
            Conf[key] = Conf[key].replace(' ','').split(',')
    if not open_serial():
        return False
    if not len(MyThread): # only the first time
        for thread in range(0,len(Conf['mySerials'])):
          try:
            MyThread.append(MyThreading.MyThreading( # init the class
              bufsize=Conf['bufsize'],
              interval=Conf['interval'],
              name='%s' % Conf['mySerials'][thread]['gas'].upper(),
              callback=Add,
              conf=Conf['mySerials'][thread],
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
# in stand alone mode the serial input is read well
# within MySense there is on a second get record a serial problem, reason unknown
# if so disable gps in MySense.conf
def Add(conf, cnt=0):
    global Conf
    # ref: aqicn.org/faq/2015-09-06/ozone-aqi-using-concentrations-in-milligrams-or-ppb/
    # ref:  samenmetenaanluchtkwaliteit.nl/zelf-meten
    # ToDo: ppb clearly is < 0: what does that mean? For now: no measurement
    def PPB2ugm3(gas,ppb,temp):
        mol = {
            'so2': 64.0,   # RIVM 2.71 using fixed 15 oC
            'no2': 46.0,   # RIVM 1.95 using fixed 15 oC
            'no':  30.01,  # RIVM 1.27 using fixed 15 oC
            'o3':  48.0,   # RIVM 2.03 using fixed 15 oC
            'co':  28.01,  # RIVM 1.18 using fixed 15 oC
            'co2': 44.01,  # RIVM 1.85 using fixed 15 oC
            'nh3': 17.031,
        }
        if not gas in mol.keys(): raise ValueError, "%s unknown gas" % gas
        if ppb < 0: return 0
        return round(ppb*12.187*mol[gas]/(273.15+temp),2)

    def Close(conf):
        if conf['fd'] == None: return
        conf['fd'].close()
        conf['fd'] = None

    def Open(conf):
        if conf['fd'] != None: return True
        try:
            conf['fd'] = serial.Serial(
                conf['device'],
                baudrate=9600,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                writeTimeout = 1,
                timeout=15)
        except:
            MyLogger.log(modulename,'ERROR','failed to open %s for %s' %  (conf['device'],conf['gas']))
            return False
        sleep(1)
        return True

    if cnt > 5:   # stop recursion
        Close(conf)
        return {}
    cnt += 1
    # serial line data: SN,PPB,temp oC,RH%,ADCraw,Traw,RHraw,day,hour,min,sec
    MAX = 11  # len(Conf['dataFlds'])
    if not 'Serial_Errors' in conf.keys(): conf['Serial_Errors'] = 0
    if conf['Serial_Errors'] > 10:
        Close(conf)
        MyLogger.log(modulename,'FATAL',"To many serial errors. Disabled.")
        sleep(0)   # to do: improve this!
        return {}
    line = ''; bin_data = []
    try:
        now = time()
        if conf['start'] - now > 0:
            Close(conf)
            sleep (conf['start'] - now)
        try:
            if not Open(conf):
                raise Exception
            while conf['fd'].inWaiting():       # skip to latest record
                conf['fd'].flushInput()
                sleep(1)
            Serial_Errors = 0
            for i in range(3,-1,-1):
              if not i: return Add(conf,cnt)
              conf['fd'].write(bytes("\r"))   # request measurement
              line = conf['fd'].readline()
              line = str(line.strip())
              if Conf['debug']:
                  print("Got %s sensor line: %s" % (conf['gas'].upper(),line))
              bin_data = []
              try:
                  bin_data = [int(x.strip()) for x in line.split(',')]
              except:
                  # Spec Error
                  MyLogger('WARNING',"Spec Data: Error - Spec Bin data")
              if len(bin_data) != MAX:
                  MyLogger.log(modulename,'WARNING',"Data length error")
                  conf['Serial_Errors'] += 1
                  continue
              break
        # except SerialException:
        #     conf['Serial_Errors'] += 1
        #     MyLogger.log(modulename,'ATTENT',"Serial exception. Close/Open serial.")
        #     return {}
        except (Exception) as error:
            MyLogger.log(modulename,'WARNING',"Serial read %s" % str(error))
            conf['Serial_Errors'] += 1
            Close(conf)
            sleep(10)
            return Add(conf,cnt)
        conf['Serial_Errors'] = 0
    except (Exception) as error:
        # Some other sensor Error
        MyLogger.log(modulename,'WARNING',str(error))
    values = { "time": int(time()) }; rawData = []
    for i in range(0,MAX):
        if Conf['dataFlds'][i] == None: continue
        try:
            rawData.append('%s=%.1f' % (conf['gas'].lower() if i == 0 else Conf['dataFlds'][i],bin_data[i]))
        except:
            MyLogger('WARNING',"Error on index %d" % i)
            #print("dataFlds",Conf['dataFlds'])
            #print("bin_data",bin_data)
        if Conf['dataFlds'][i] == 'ppb':
          try:
            idx = Conf['fields'].index(conf['gas'])
            values[conf['gas']] = calibrate(idx,Conf['calibrations'],bin_data[i])
            if values[conf['gas']] < 0:  # on negative Spec sensor has seen no gas
                values[conf['gas']] = None
                continue
          except:
            #print("conf",conf)
            MyLogger('WARNING',"index error on index %d" % i)
            #print("bin_data",bin_data)
          if Conf['units'][idx] == 'ug/m3':
            try:
                tempVal = float(bin_data[Conf['dataFlds'].index('temp')])
            except:
                tempVal = 25.0
            if not conf['gas'] in values.keys():
                MyLogger('WARNING',"Error on index %d in values on %s" % (i,conf['gas']))
                # print(values)
            values[conf['gas']] = PPB2ugm3(conf['gas'],values[conf['gas']],tempVal)
        elif Conf['dataFlds'][i][-3:] == 'raw':
          values[conf['gas']+Conf['dataFlds'][i]] = int(bin_data[i])
        else:
          try:
            values[Conf['dataFlds'][i]] = calibrate(Conf['fields'].index(Conf['dataFlds'][i]),Conf['calibrations'],bin_data[i])
          except:
            values[Conf['dataFlds'][i]] = int(bin_data[i])
    if ('raw' in conf.keys()) and (conf['raw'] != None) and (not type(conf['raw']) is bool):
        Conf['raw'].publish(
            tag='Spec%s' % conf['gas'].upper(),
            data=','.join(rawData))
    # print("Got values: ", values)
    # Close(conf)
    return values

def avg(values):
    if values == None: return None
    if not type(values) is list: return values
    if not len(values): return None
    sum = 0.0; cnt = 0
    for i in values:
        if i != None:
            cnt += 1
            sum += i
    if not cnt: return 0   # on no gas sensed return 0
    return sum/cnt

# rename a key and prepend name with 3 type chars lowered if needed
# e.g. o3 -> spe_o3, temp -> spe_temp or temp -> temperature
def rename(key):
    global Conf
    prefix = ''
    try:
        if Conf['prefix']: prefix = Conf['type'][0:3].lower() + '_'
    except: pass
    try:
        return prefix + Conf['rename'][key]
    except:
        return prefix + key

# get input values from threaded sensor module interface
def getdata():
    global Conf, MyThread
    if not registrate():                # start up threads of sensor readings
        return {}
    values = { 'time': [time()], }
    for i in range(0,len(MyThread)):
        try:
            thisSensor = MyThread[i].getRecord()
        except IOError as er:
            MyLogger.log(modulename,'WARNING',"thread %d: Sensor getRecord input failure: %s" % (i,str(er)))
        for key in thisSensor.keys():
            if key in Conf['omits']: continue  # e.g. temp value not published
            name = rename(key)
            if not name in values.keys(): values[name] = []
            values[name].append(thisSensor[key])
    for key in values.keys(): values[key] = avg(values[key])
    return values

Conf['getdata'] = getdata	# Add needs this global viariable

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['input'] = True
    # Conf['sync'] = True
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

