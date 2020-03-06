# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
# Copyright (C) 2019, Behoud de Parel, Teus Hagen, the Netherlands
# $Id: SPS30.py,v 5.9 2020/03/06 20:25:19 teus Exp teus $
# the GNU General Public License the Free Software Foundation version 3

# Defeat: output (moving) average PM count in period sample time seconds (dflt 60 secs)

# implements Sensirion SPS30 device driver for MySense

# refs
# details: https://www.sensirion.com/fileadmin/user_upload/customers/sensirion/Dokumente/0_Datasheets/Particulate_Matter/Sensirion_PM_Sensors_SPS30_Datasheet.pdf
# datasheet is beta version and may not be complete (nor this driver).

# see also: https://github.com/Sensirion/embedded-uart-sps
#           https://github.com/KVital/SPS30/blob/master/dust.ino
#           https://smarthome-work.com/download/sps30-i2c-mini.ino
# thanks to Michael Pruefer for his Arduino ino version V1.0 19.01.2019

# for python2:
# from __future__ import print_function
from time import sleep
try:
  # for micropython:
  from micropython import const
  from time import ticks_ms, sleep_ms
except:
  try:
    from const import const, ticks_ms, sleep_ms
  except:
    from time import time
    def sleep_ms(ms): sleep(ms/1000.0)
    def ticks_ms(): return int(time()*1000)
    def const(a): return a

""" Get sensor values: PM1, PM2.5 and PM10 from Sensirion Particular Matter sensor
  units: pcs/0.01qf, pcs/0.1dm3, ug/m3
  class inits:
    port=1 port number
    debug=False show measurements
    sample=60   sample time in seconds
    interval=1200 sleep time-sample / fan off after sampling if 0 no interval
"""

import struct         # needed for unpack data telegram, big-endian


class SPS30:
  # index of list
  # I2C address: 0x69
  SPS_ADDR = const(0x00)
  # float array of values
  SPS_PM1P0 = const(0)
  SPS_PM2P5 = const(1)
  SPS_PM4P0 = const(2)
  SPS_PM10P0 = const(3)
  SPS_PCNT_0P5 = const(4)
  SPS_PCNT_1P0 = const(5)
  SPS_PCNT_2P5 = const(6)
  SPS_PCNT_4P0 = const(7)
  SPS_PCNT_10P0 = const(8)
  SPS_TYP_SIZE = const(9)

  # status PM sensor: STANDBY (fan off) or NORMAL (fan ON, sampling)
  ACTIVE  = const(0)   # mode active, has allowed to fan startup
  PASSIVE = const(1)   # mode passive, same as NORMAL
  NORMAL  = const(3)   # mode normal, fan is ON, sampling measurements
  STANDBY = const(4)   # mode passive, state standby fan is OFF

  # idle time minimal time to switch fan OFF
  IDLE  = const(120000)   # msecs, minimal idle time between sample time and interval

  def __init__(self, port=1, debug=False, sample=60, interval=1200, raw=False, calibrate=None, pins=('P3','P4'), addr=SPS_ADDR, clean=0, explicit=False):
    # read from port=UART1 V5/Gnd, PMS/Rx - GPIO P3/Tx, PMS/Tx - GPIO P4/Rx
    # or port=/dev/ttyUSB?
    # measure average in sample time, interval freq. of samples in secs
    # explicit True: Plantower way of count (>PMi), False: Sensirion way (PM0.3-PMi) (dflt=False)
    # idle <8 mA, operation 60 mA, max 5.5V, count/mass: 0.3 - size um
    # SPS pin nr:
    #     1=VCC, 2=Rx/SDA, 3=Tx/SCL, 4= sel(Gnd,I2C), 5=Gnd, 5 is corner side
    # clean > 0: secs interval autoclean, 0 (dflt): weekly, None: clean initial
    try:
      if type(port) is str: # no PyCom case
        import serial
        self.ser = serial.Serial(port, 115200, bytesize=8, parity='N', stopbits=1, timeout=20, xonxoff=0, rtscts=0)
        self.ser.any = self.in_waiting
      elif type(port) is int: # micro python case
        from machine import UART
        self.ser = UART(port,baudrate=115200,pins=pins,timeout_chars=10)
      else: self.ser = port # fd
    except: raise ValueError("SPS serial failed")

    self.debug = debug
    self.addr = addr
    self.mode = self.PASSIVE
    self.started = None

    self.interval = interval * 1000 # if interval == 0 no auto fan switching
    self.sample =  sample * 1000
    self.raw = raw
    self.clean = clean  # clean fan after clean secs dflt: None (weekly)
    self.explicit = explicit # counts are > PM size or < PM size

    # dflts are from sample label. Try later again
    self.name = 'SPS30'; self.firmware = '117118'; self.code = 'SEN-15103'
    self.clean = clean

    # list of name, units, index in measurments, calibration factoring
    # eg pm1=[20,1] adds a calibration offset of 20 to measurement
    self.PM_fields = [
      ['pm1','ug/m3',self.SPS_PM1P0,[0,1]], # 0.3 upto 1
      ['pm25','ug/m3',self.SPS_PM2P5,[0,1]],# 0.3 upto 2.5
      ['pm4','ug/m3',self.SPS_PM4P0,[0,1]],
      ['pm10','ug/m3',self.SPS_PM10P0,[0,1]],
      # 0.1 liter = 0.00353147 cubic feet, convert -> pcs / 0.01qf
      # std used here pcs/0.1dm3 (Plantower style)
      ['pm05_cnt','pcs/0.1dm3',self.SPS_PCNT_0P5,[0,100]],
      ['pm1_cnt','pcs/0.1dm3',self.SPS_PCNT_1P0,[0,100]],
      ['pm25_cnt','pcs/0.1dm3',self.SPS_PCNT_2P5,[0,100]],
      ['pm4_cnt','pcs/0.1dm3',self.SPS_PCNT_4P0,[0,100]],
      ['pm10_cnt','pcs/0.1dm3',self.SPS_PCNT_10P0,[0,100]],
      ['grain','mu',self.SPS_TYP_SIZE,None],
      # grain: average particle size
      ['grain','mu',self.SPS_TYP_SIZE,None] if not explicit else ['pm03_cnt','pcs/0.1dm3',self.SPS_TYP_SIZE,[0,100]],
    ]
    if type(calibrate) is dict:
      for key in calibrate.keys():
        if calibrate[key] and type(calibrate[key]) != list: continue
        for pm in range(len(self.PM_fields)):
          if self.PM_fields[pm][0] == key:
            self.PM_fields[pm][3] = calibrate[key]
            break

  def isStarted(self, debug=False):
    if self.started: return
    self.started = 0
    # dflts are from sample label
    try:
      self.started = True
      if self.reset(debug=debug):
        RuntimeError("Reset failed with %d" % stat)
      # collect meta info
      tmp = self.device_info('name')
      if tmp: self.name = tmp
      tmp = self.device_info('serial')
      if tmp: self.firmware = tmp
      tmp = self.device_info('code')
      if tmp: self.code = tmp
      if debug: print("name: '%s', S/N '%s', article: '%s'" % (self.name, self.firmware, self.device_info('code')))
      if self.clean:
        self.auto_clean(self.clean, debug=debug)
        self.clean = 0
      elif self.clean == None: self.fan_clean(debug=debug)
    except Exception as e: RuntimeError(e)

  def in_waiting(self): # for non PyCom python
    try: return self.ser.in_waiting
    except: raise OSError

  def read_until(self,char=chr(0x7E)):
    try:
      cnt = 0
      while True:
        cnt += 1
        if cnt > 20: return None
        if not self.ser.any():
          sleep_ms(200); continue
        try:
          if self.ser.read(1) != char: continue
        except: pass
        return char
    except: return None

  # calibrate by length calibration (Taylor) factor array
  def calibrate(self,cal,value):
    if self.raw: return value
    if (not cal) or (type(cal) != list):
      return round(value,2)
    if type(value) is int: value = float(value)
    if not type(value) is float:
      return None
    rts = 0; pow = 0
    for a in cal:
      rts += a*(value**pow)
      pow += 1
    return rts

  error = {
    0x0: 'ok', 0x1: 'data length err', 0x2: 'fan off',
    0x4: 'illegal cmd param', 0x28: 'internal fie arg range error',
    0x43: 'cmd not allowed in this state',
  }

  stuff = { # byte stuffing with 0x7D
    0x7E: 0x5E, 0x7D: 0x5D,
    0x11: 0x31, 0x13: 0x33,
  }
  # just before sending, returns byte array
  def stuffing(self,arr):
    rslt = [0x7E]
    for b in arr:
       if b in self.stuff.keys():
         rslt += [0x7D,stuff[b]]
       else: rslt.append(b)
    rslt += [0x7E]
    return bytearray(rslt)

  # just after reading, returns int array
  def unstuff(self,data): # to do unstuffing
    rslt = []
    for i in range(0,len(data)):
       if data[i] == 0x7D:
         try:
           for val in self.stuff.items():
             if val[1] == data[i+1]:
               rslt.append(val[0])
               break
           i += 1
         except: pass
       else: rslt.append(data[i])
    return rslt

  # adds addr and append checksum, send stuffed bytearray
  def send(self,cmd,data, debug=False):
    self.isStarted(debug=debug)
    s = [self.addr,cmd,len(data)] + data
    s.append((~(sum(s) & 0xFF)) & 0xFF)
    s = self.stuffing(s)   
    if debug: print("Send: ", s)
    return self.ser.write(s)

  # get data from uart, return tuple(status,data[])
  def receive(self, cmd, debug=False):
    strt = True; buf = bytearray()
    for cnt in range(1,6):
      if self.ser.any():
        cnt = 0
        break
      if debug: print("SPS wait...")
      sleep_ms(1000)
    if cnt: return (0x2, [])
    while True:
      try: char = self.ser.read(1)
      except: return (0x2, [])
      if char == b'': raise OSError("No data")
      elif strt:
        if (char == b'\x7E'): strt = False
        continue
      if char == b'\x7E': break
      buf += char
    buf = self.unstuff(buf)
    # to do: add sum chk, cmd check: buf[1] == cmd
    if len(buf[4:-1]) != buf[3]: raise ValueError("length rcv")
    if debug: print("Received: %s" % str(buf))
    if (~sum(buf) & 0xFF): raise ValueError("checksum")
    if buf[1] != cmd: raise ValueError("sensor reply error")
    return (buf[2],buf[4:4+buf[3]]) # status, data

  # UART / Sensirion SPS30 SHDLC commands
  SPS_START = const(0x00)
  SPS_STOP  = const(0x01)
  SPS_READ  = const(0x03)
  SPS_FAN_SPEED = const(0x04)
  SPS_AUTO_CLEAN = const(0x80)
  SPS_FAN_CLEAN  = const(0x56)
  SPS_INFO  = const(0xD0)
  SPS_RESET = const(0xD3)

  def start_measurement(self,debug=False):
     if debug: print("Start SPS")
     # subcmd=0x01, mode=0x03
     self.send(self.SPS_START,[0x01,0x03],debug=debug)
     return self.receive(self.SPS_START)[0]

  def stop_measurement(self,debug=False):
     # to idle state
     if debug: print("Stop SPS")
     self.send(self.SPS_STOP,[], debug=debug)
     return self.receive(self.SPS_STOP, debug=debug)[0]

  # mass ug/m3: PM1.0, PM2.5, PM4.0, PM10
  # count pcs/cm3: PM0.5, PM1.0, PM2.5, PM4.0, PM10
  # typical pm size
  def read_measurement(self, debug=False): # default 1 sec sample, empty if no value yet
    if debug: print("Read SPS values")
    self.send(self.SPS_READ,[])
    (status, data) = self.receive(self.SPS_READ,debug=debug)
    if status:
      try:
        print("SPS error: %d (%s)" % (status,self.error[status]))
      except: print("SPS unknown error: %d" % status)
      return []
    rslts = []
    for i in range(0,len(data),4):
        if (i+4) > len(data): break
        rslts.append(struct.unpack('>f',bytearray((data[i:i+4])))[0])
    if debug: print("Read: ",rslts)
    return rslts

  # routine is from Sensirion sample. Gives status 2, no speed
  def fan_speed(self,debug=False):
    if debug: print("Get fan speed")
    self.send(self.SPS_FAN_SPEED,[],debug=debug)
    rslts = self.receive(self.SPS_FAN_SPEED,debug=debug)
    if debug: print(rslts)
    if not rslts[0]: return rslts[1][0]
    else: return self.error[rslts[0]]

  # read/write auto cleaning interval, 10 secs clean air boost
  # interval=0 disable auto clean, dflt 604.800 secs/one week
  # poweroff will reset next clean
  def auto_clean(self, interval=None, debug=False):
    if interval == None:
      if debug: print("Auto clean, no interval")
      self.send(self.SPS_AUTO_CLEAN,[0x0,],debug=debug)
    else:
      if debug: print("Auto clean, interval %d" % interval)
      b = bytearray(struct.pack('>L',interval))
      self.send(self.SPS_AUTO_CLEAN,[0x0,b[0],b[1],b[2],b[4]],debug=debug)
    return self.receive(self.SPS_AUTO_CLEAN)[0]

  # forced fan cleaning
  def fan_clean(self,debug=False):
    if debug: print("Clean fan")
    self.send(self.SPS_FAN_CLEAN,[],debug=debug)
    return self.receive(self.SPS_FAN_CLEAN)[0]

  # get information from sensor. Sample gives empty string
  def device_info(self, info='serial', debug=False):
    cmds = { 'name': 0x01, 'code': 0x2, 'serial': 0x03 }
    try:
      if (not info) or (info == 'all'):
        rslt = []
        for cmd in cmds.keys():
            rslt.append(cmd + ': ' + self.device_info(cmd))
        return ', '.join(rslt)
      elif info in cmds.keys():
        self.send(self.SPS_INFO,[cmds[info]], debug=debug)
        strg = self.receive(self.SPS_INFO)[1][:-1]
        strg = str(strg[:-1].decode("ascii"))
        if debug: print("Got info \"%s\"" % strg)
        return strg
    except: pass
    return ''
  
  # soft reset similar as power reset
  def reset(self,debug=False):
    if debug: print("SPS reset")
    try:
      self.send(self.SPS_RESET,[],debug=debug)
      stat = self.receive(self.SPS_RESET)[0]
      if not stat: self.mode = self.STANDBY
      if debug: print("reset status: %d" % stat)
    except Exception as e: raise RuntimeError(e)
    return stat

    # passive mode, go into standby state / sleep: fan OFF
  def Standby(self, debug=False):
    if debug: print("Go standby from 0X%X" % self.mode)
    if self.mode != self.STANDBY:
      try: self.stop_measurement(debug=debug)
      except: return False
      self.mode = self.STANDBY
    return True

  # passive mode, go into normal state: fan ON, allow data telegrams reading
  def Normal(self,debug=False):
    if debug: print("Go normal from 0x%X" % self.mode)
    return self.GoPassive(debug=debug)

  # passive mode wait on read request
  def GoPassive(self,debug=False):
    if debug: print("Go Passive from 0X%X" % self.mode)
    if self.mode == self.STANDBY:
      try:
        self.start_measurement(debug=debug)
        sleep_ms(30000)
      except: return False
    self.mode = self.PASSIVE
    return True

  # from passive mode go in active mode (same as with power on)
  def GoActive(self,debug=False):
    if debug: print("Go active from 0X%X" % self.mode)
    return self.GoPassive(debug=debug)

  # in passive mode do one data telegram reading
  def PassiveRead(self,debug=False):
    if self.mode == self.STANDBY:
      if not self.GoPassive(debug=debug): return []
    return self.read_measurement(debug=debug)

  def getData(self,debug=False):
    ''' read data telegrams from the serial interface (32 bytes)
      before actual read flush all pending data first
      during the period sample time: active (200-800 ms), passive read cmd 1 sec
      calculate average during sample seconds
      if passive mode fan off: switch fan ON and wait 30 secs.
    '''
    ErrorCnt = 0
    cnt = 0; PM_sample = {}
    # clear the input buffer first so we get latest reading
    if self.mode == self.STANDBY: self.GoPassive(debug=debug)
    StrtTime = ticks_ms(); LastTime = StrtTime+self.sample-1000
    while True:
        buff = []
        try:
          buff = self.PassiveRead(debug=debug)
        except: pass
        if len(buff) == self.SPS_TYP_SIZE+1: # must be all
          for fld in self.PM_fields:
            PM_sample[fld[0]] = PM_sample.setdefault(fld[0],0.0)+buff[fld[2]]
          cnt += 1
        elif not len(PM_sample):
          self.mode = self.STANDBY # wake it up
          return self.getData(debug=debug)
        if ticks_ms() >= LastTime: break
        sleep_ms(5000)
    # turn fan off?
    if self.interval - (ticks_ms()-StrtTime) > 60*1000:
      self.Standby(debug=debug)    # switch fan OFF
    if cnt:   # average count during the sample time
      for fld in self.PM_fields:
        PM_sample[fld[0]] /= cnt
        if self.raw:
          PM_sample[fld[0]] = round(PM_sample[fld[0]],2)
        else:
          PM_sample[fld[0]] = round(self.calibrate(fld[3],PM_sample[fld[0]]),2)
    if self.explicit:
        PM10 = PM_sample["pm10_cnt"]
        for pmCnt in PM_sample.keys():
            if pmCnt.find('_cnt') < 0: continue
            if pmCnt.find('03_cnt') > 0: PM_sample['pm03_cnt'] = PM10
            else: PM_sample[pmCnt] = PM10 - PM_sample[pmCnt]
    return PM_sample

if __name__ == "__main__":
    from time import time, sleep
    interval = 5*60
    sample = 60
    debug = True
    try:
      from machine import UART, Pin
      pins = ('P4','P3','P19')
      print("Using pins: %s" % str(pins))
      Pin(pins[2],mode=Pin.OUT).value(1); sleep(1)
      port = UART(1,baudrate=115200,pins=pins[:2],timeout_chars=20)
    except:
      import sys
      port = sys.argv[1]
    sps30 = SPS30(port=port, debug=debug, sample=sample, interval=interval)
    for i in range(4):
        lastTime = time()
        print(sps30.getData(debug=debug))
        now = interval + time() -lastTime
        if now > 0: sleep(now)
