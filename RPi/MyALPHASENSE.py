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

# $Id: MyALPHASENSE.py,v 1.6 2018/07/11 13:04:13 teus Exp teus $

""" Get measurements from AlphaSense gas sensor NH3 using
    Digital Transmitter Borad ISB rev4 and
    AD 4 channel 8-bit converter PCF8591
    Measurements have a calibration factor.
    Relies on Conf setting by main program.
"""
modulename='$RCSfile: MyALPHASENSE.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.6 $"[11:-2]
__license__ = 'GPLV4'

try:
    from time import time
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
    'sensitivity',             # conversion algorithm sensor sensitivity
    'interval','bufsize','sync']       # multithead buffer size and search for input secs

Conf ={
    'input': False,      # no temp/humidity sensors installed
    'type': 'AlphaSense',# type of the chip eg BME280 Bosch
    'fields': ['nh3'],   # gas nh3, co, no2, o3, ...
    'units' : ['ppm'],   # PPM, mA, or mV
    'calibrations' : [[0,1]], # calibration factors, here order 1
    'sensitivity': [[4,20,100]], # 4 - 20 mA -> 100 ppm
    'i2c': ['0x48'],     # I2C-bus addresses
    'interval': 30,      # read dht interval in secs (dflt)
    'meteo': None,       # current meteo values
    'bufsize': 20,       # size of the window of values readings max
    'sync': False,       # use thread or not to collect data
    'debug': False,      # be more versatile
    'raw': False,        # no raw measurements displayed
    'fd' : None          # input handler
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

# PVF8591 A/D 4 channel, 8-bit controller
#     delete light, temp, pot straps to disable these sensors
#     https://www.nxp.com/docs/en/data-sheet/PCF8591.pdf
# AlphaSense NH3 B1 sensor
#     http://www.isweek.com/product/ammonia-sensor-nh3-sensor-nh3-b1_1712.html
# AlphaSense Digital Transmitter Board ISB
#     http://www.isweek.com/product/4-20-ma-digital-transmitter-board-alphasense-type-a-and-b-toxic-gas-sensors-digital-transmitter-board_1835.html
#     http://www.alphasense.com/WEB1213/wp-content/uploads/2013/11/Alphasense-Digital-Transmitter.zip

class ADC:
    #i2cdetect -y 1 gives address
    address = None

    def __init__(self,address=0x48):
        import RPi.GPIO as GPIO
        from smbus import SMBus
        self.bus = SMBus(1 if GPIO.RPI_REVISION in [2,3] else 0)
        self.address=address

    def adc_read(self):
        data = self.bus.read_i2c_block_data(self.address, 4)[4:8]
        #reference voltage should stay stable (3.45V)
        # 4 mA -> 0 ppm, 20 mA -> 100 ppm and is lineair (...)
        # sensitivity 25-45 nA/ppm in 50 ppm NH3
        # NH3 limit performance 100 ppm
        # linearity 0 and 20 ppm +5,-5
        # max 200 ppm for stable response
        # data=((data/20)*100)-4 ???
        reference = data[1]-data[0]
        value = data[3]-data[2]
        return (value,reference)

# get a record,
# called back from sensor thread with average of sliding window bufsize
def Add(conf):
  def PPB2ugm3(gas,ppb,temp):
    mol = {
        'so2': 64.0,   # RIVM 2.71, ?
        'no2': 46.0,   # RIVM 1.95, ?
        'no':  30.01,  # RIVM 1.27, ?
        'o3':  48.0,   # RIVM 2.03, ?
        'co':  28.01,  # RIVM 1.18, ?
        'co2': 44.01,  # RIVM 1.85, ?
        'nh3': 17.031,
    }
    if not gas in mol.keys(): raise ValueError, "%s unknown gas" % gas
    if ppb < 0: return 0
    return round(ppb*12.187*mol[gas]/(273.15+temp),2)

  rec = {'time': int(time())}
  try: temp = conf['meteo']['temp']
  except: temp = 25.0  # default temp
  if (conf['fd'] == None) or (not len(conf['fd'])): return rec
  rawData = []
  for gas in range(0,len(conf['fd'])):
    value = None
    if conf['fd'][gas] != None:
      try:
        (value,reference) = conf['fd'][gas].adc_read()
        rawData.append("%s=%d/%d" % (conf['fields'][gas],value,reference))
        mAval = value*conf['sensitivity'][gas][1]/reference-conf['sensitivity'][gas][0]
        if mAval < 0: mAval = 0
        # V=I2R -> I = sqrt(V/R) ???
        # R = 400/reference ???
        ppmval = (mAval/conf['sensitivity'][gas][1])*conf['sensitivity'][gas][2]
        if conf['debug']:
          print("%s: %d/%d (%.3f mV)" % (conf['fields'][gas].upper(),value, reference,1000.0*float(value)/reference))
          print("%s converted: %.1f mA, %.1f PPM" % (conf['fields'][gas].upper(),mAval,ppmval))
        if conf['units'][gas].lower() == 'ppm':
          value = calibrate(gas,conf,ppmval)
        elif conf['units'][gas].lower() == 'ug/m3':
          value = calibrate(gas,conf,ppmval)
          value = PPB2ugm3(conf['units'][gas].lower(),value,temp)
        elif conf['units'][gas].lower() == 'ma': value = mAval
	elif type(value) is int: value = float(value)
      except ValueError:
        MyLogger.log(modulename,'ERROR',"Read or config error")
        continue
    else:
      MyLogger.log(modulename,'ERROR',"Configuration error.")
      continue
    if value == None:
      MyLogger.log(modulename,'ERROR',"Access error. Connection problem?")
      raise IOError("AlphaSense lost AD connection.")
      return rec
    if type(value) is float:
      if conf['debug']:
        MyLogger.log(modulename,'DEBUG',"%s : %5.2f %s not calibrated" % (conf['fields'][gas],value,conf['units'][gas]))
    else:
      MyLogger.log(modulename,'DEBUG',"%s : None" % conf['fields'][gas])
    rec[conf['fields'][gas]] = round(value,2)
  if ('raw' in conf.keys()) and (type(conf['raw']) is module):
    conf['raw'].publish(
       tag='%s' % conf['type'].lower(),
       data=','.join(rawData))
  return rec

# check the options
MyThread = []         # ref to sensor thread, thread may run in parallel
def registrate():
    global Conf, MyThread
    if (not Conf['input']):
        return False
    if ('fd' in Conf.keys()) and (Conf['fd'] != None):
        return True
    for key in ['i2c','sensitivity']: # handle configured arrays of values
        if (key in Conf.keys()) and (type(Conf[key]) is str):
            Conf[key] = Conf[key].replace(' ','')
            Conf[key] = Conf[key].replace('],[','#')
            Conf[key] = Conf[key].replace('[','')
            Conf[key] = Conf[key].replace(']','')
            if key == 'i2c': Conf[key] = Conf[key].split(',')
            else:
                Conf[key] = Conf[key].split('#')
                for i in range(0,len(Conf[key])):
                    Conf[key][i] = [int(a) for a in Conf[key][i].split(',')]
    Conf['input'] = False; Conf['fd'] = []
    for gas in range(0,len(Conf['i2c'])):
      Conf['fd'].append(None)
      if not int(Conf['i2c'][gas],0) in [0x48]: # address pin 0-2 to null, read
        MyLogger.log(modulename,'ERROR',"I2C address %s not correct. Disabled." % Conf['i2c'][gas])
        return False
      else:
        try:
          Conf['fd'][gas] = ADC(address=int(Conf['i2c'][gas],0))
        except IOError:
          MyLogger.log(modulename,'WARNING','Try another I2C address.')
          continue
    Conf['input'] = True
    cnt = 0
    if not len(MyThread): # only the first time
      for thread in range(0,len(Conf['fd'])):
	if Conf['fd'][thread] == None: continue
        MyThread.append(MyThreading.MyThreading(
            bufsize=int(Conf['bufsize']),
            interval=int(Conf['interval']),
            name='Alpha Sense %s sensor' % Conf['fields'][gas].upper(),
            callback=Add,
            conf=Conf,
            sync=Conf['sync'],
            DEBUG=Conf['debug']))
        # first call is interval secs delayed by definition
        try:
          if MyThread[gas].start_thread():
            cnt += 1
            continue
        except:
          MyThread[gas] = None
    if not cnt:
      MyLogger.log(modulename,'ERROR',"Unable to registrate/start AlphaSsense sensors thread(s).")
      Conf['input'] = False
      return False
    return True
       
# ============================================================
# ALpha Sense sensor data
# ============================================================
# to do: allow different AD converter types,
# not sure about measurement conversion algorithm use from ADC
def getdata(meteo=None):
    global Conf, MyThread
    Conf['meteo'] = meteo
    if not registrate():                # start up input readings
      return {}
    data = {}
    for thread in range(0,len(MyThread)):  
      try:
        values =  MyThread[thread].getRecord()     # pick up a record
        for key in values.keys():
          if key in Conf['fields'] + ['time']:
            data[key] = values[key]
      except IOError as er:
        MyLogger.log(modulename,'WARNING',"Sensor %s input failure: %s" % (Conf['fields'][thread],er))
    return data

# test main loop
if __name__ == '__main__':
    from time import sleep
    # Conf['type'] = 'AlphaSense'
    Conf['input'] = True
    # Conf['i2c'] = ['0x48']        # default I2C-bus address
    # Conf['sync'] = True         # True is in sync (not multi threaded)
    # Conf['debug'] = True        # print collected sensor values
    Conf['units'] = ['mV']
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
    if (not Conf['sync']) and len(MyThread):
      for thread in range(0,len(MyThread)):
        if MyThread[thread] != None:
          MyThread[thread].stop_thread()
