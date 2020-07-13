# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
# Copyright (C) 2017, Behoud de Parel, Teus Hagen, the Netherlands
# $Id: PMSx003.py,v 5.5 2020/03/12 19:50:27 teus Exp teus $
# the GNU General Public License the Free Software Foundation version 3

# Defeat: output (moving) average PM count in period sample time seconds (dflt 60 secs)
# for python2:
# from __future__ import print_function
# for micropython:
try:
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

import struct         # needed for unpack data telegram
def ORD(val):
  if type(val) is str:
    return ord(val) & 0xFF
  return val & 0xFF

""" Get sensor values: PM1, PM2.5 and PM10 from Plantower Particular Matter sensor
  Types: 7003, x003 or 5003
  units: pcs/0.01qf, pcs/0.1dm3, ug/m3
  class inits:
    port=1 port number
    debug=False show measurements
    sample=60   sample time in seconds
    interval=1200 sleep time-sample / fan off after sampling if 0 no interval
"""



class PMSx003:
  # index of list
  PMS_FRAME_LENGTH = const(0)
  PMS_PM1P0_PAR1 = const(1)
  PMS_PM2P5_PAR2 = const(2)
  PMS_PM10P0_PAR3 = const(3)
  PMS_PM1P0 = const(4)
  PMS_PM2P5 = const(5)
  PMS_PM10P0 = const(6)
  PMS_PCNT_0P3 = const(7)
  PMS_PCNT_0P5 = const(8)
  PMS_PCNT_1P0 = const(9)
  PMS_PCNT_2P5 = const(10)
  PMS_PCNT_5P0 = const(11)
  PMS_PCNT_10P0 = const(12)
  PMS_VER = const(13)
  PMS_ERROR = const(14)
  PMS_SUMCHECK = const(15)

  ACTIVE  = const(0)   # mode active, default mode on power ON
  PASSIVE = const(1)   # mode passive, similar as NORMAL mode
  NORMAL  = const(3)   # mode passive state normal   fan is ON
  STANDBY = const(4)   # mode passive, state standby fan is OFF
  # idle time minimal time to switch fan OFF
  IDLE  = const(120000)   # minimal idle time between sample time and interval
  def __init__(self, port=1, debug=False, sample=60, interval=1200, raw=False, calibrate=None,pins=('P3','P4'), clean=None, explicit=False):
    # read from UART1 V5/Gnd, PMS/Rx - GPIO P3/Tx, PMS/Tx - GPIO P4/Rx
    # measure average in sample time, interval freq. of samples in secs
    # explicit True: Plantower way of count (>PMi), False: Sensirion way (PM0.3-PMi) (dflt=False)
    try:
      if type(port) is str: # no PyCom case
        import serial
        self.ser = serial.Serial(port, 9600, bytesize=8, parity='N', stopbits=1, timeout=20, xonxoff=0, rtscts=0)
        self.ser.any = self.in_waiting
      elif type(port) is int: # micro python case
        from machine import UART
        self.ser = UART(port,baudrate=9600,pins=pins,timeout_chars=10)
      else: self.ser = port # fd
    except: raise OSError("PMS serial failed")

    self.firmware = None
    self.debug = debug
    self.interval = interval * 1000 # if interval == 0 no auto fan switching
    self.sample =  sample *1000
    self.mode = self.STANDBY
    self.raw = raw
    self.explicit = explicit        # counts are > PM size or < PM size

    # list of name, units, index in measurments, calibration factoring
    # pm1=[20,1] adds a calibration offset of 20 to measurement
    self.PM_fields = [
      # the Plantower conversion algorithm is unclear!
      # internal parameters per size (not of use)
      ['pm1_par1','par',self.PMS_PM1P0_PAR1,None],
      ['pm25_par2','par',self.PMS_PM2P5_PAR2,None],
      ['pm10_par3','par',self.PMS_PM10P0_PAR3,None],
      # concentration (generic atmosphere conditions) in ug/m3
      ['pm1','ug/m3',self.PMS_PM1P0,[0,1]],
      ['pm25','ug/m3',self.PMS_PM2P5,[0,1]],
      ['pm10','ug/m3',self.PMS_PM10P0,[0,1]],
      # number of particles with diameter N in 0.1 liter air
      # 0.1 liter = 0.00353147 cubic feet, convert -> pcs / 0.01qf
      # std used here pcs/0.1dm3 (Plantower style)
      # grain: average particle size
      ['pm03_cnt','pcs/0.1dm3',self.PMS_PCNT_0P3,None],
      ['pm05_cnt','pcs/0.1dm3',self.PMS_PCNT_0P5,None],
      ['pm1_cnt','pcs/0.1dm3',self.PMS_PCNT_1P0,None],
      ['pm25_cnt','pcs/0.1dm3',self.PMS_PCNT_2P5,None],
      ['pm5_cnt','pcs/0.1dm3',self.PMS_PCNT_5P0,None],
      ['pm10_cnt','pcs/0.1dm3',self.PMS_PCNT_10P0,None],
      ['grain','um',0,None],
    ]
    if type(calibrate) is dict:
      for key in calibrate.keys():
        if calibrate[key] and type(calibrate[key]) != list: continue
        for pm in range(len(self.PM_fields)):
          if self.PM_fields[pm][0] == key:
            self.PM_fields[pm][3] = calibrate[key]
            break

  def in_waiting(self): # for non PyCom python
    try: return self.ser.in_waiting
    except: raise ValueError

  # calibrate by length calibration factor (Taylor) array
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

  # send mode/state change to PMS sensor
  # check answer
  def SendMode(self,cmd,ON):
    ''' send 42 4D cmd (E2,E4,E1) 00 ON (On=1,Off=0) chckH chckL
      no answer on cmd: E2 (read telegram) and E4 On (active mode)
      answer 42 4D 00 04 cmd 00 chckH chckL
    '''
    if not cmd in (0xE1,0xE2,0xE4): return False
    if ON: ON = 0x1
    if self.debug:
      if cmd == 0xE2: CMD = 'READ'
      elif cmd == 0xE1:
        CMD = 'ACTIVE' if ON else 'PASSIVE fan ON'
      else: CMD = 'NORMAL fan ON' if ON else 'STANDBY fan OFF'
      print("Send command %s" % CMD)
    ChckSum = 0x42+0x4D+cmd+0x0+ON
    data = struct.pack('!BBBBBH',0x42,0x4D,cmd,0x0,ON,ChckSum)
    while self.ser.any(): self.ser.read()
    try:
      self.ser.write(data)
      # print("Send command 0x%X 0x%X 0x%X 0x%X 0x%X 0x%x 0x%x" % struct.unpack('!BBBBBBB',data))
    except:
      print('Unable to send mode/state change.')
      raise OSError("mode/state")
    if (cmd == 0xE2) or (cmd == 0xE4):
      return True
    # check the answer
    ChckSum += 4
    try:
      c = []; err = 0
      while True:
        if err > 20:
            print("PMS response failed")
            self.GoPassive()
            return False
        err += 1
        if not self.ser.any():
            sleep_ms(200)
            continue
        c = self.ser.read(1)
        if ORD(c[0]) != 0x42:
            continue
        c = self.ser.read(1)
        if c == None or ORD(c[0]) != 0x4D:
            continue
        check = 0x42+0x4D
        c = self.ser.read(6)
        for ch in c[:4]:
            check += ORD(ch)
        if (ORD(c[1]) == 0x4) and (ORD(c[2]) == cmd) and ((ORD(c[4])*256 + ORD(c[5]))== check):
          return True
        print("Checksum 0X%x 0X%x != 0X%x" %(ChkSum,check,ORD(c[4])*256 + ORD(c[5])))
        return False
    except:
      pass
    return False

    # passive mode, go into standby state / sleep: fan OFF
  def Standby(self, debug=False):
    if debug: print("Go standby from 0X%X" % self.mode)
    if self.mode != self.STANDBY:
      if self.mode == self.ACTIVE: self.GoPassive()
      self.mode = self.STANDBY
      return self.SendMode(0xE4,0)
    return True

  # passive mode, go into normal state: fan ON, allow data telegrams reading
  def Normal(self, debug=False):
    if debug: print("Go normal from 0x%X" % self.mode)
    if self.mode != self.NORMAL:
      if self.mode == self.ACTIVE: self.GoPassive()
      if self.mode != self.NORMAL:
        self.mode = self.NORMAL
        return self.SendMode(0xE4,1)
    return True

  # from passive mode go in active mode (same as with power on)
  def GoActive(self, debug=False):
    if debug: print("Go active from 0X%X" % self.mode)
    if self.mode == self.STANDBY:
      self.Normal()
      if self.debug: print("wait 30 secs")
      sleep_ms(30000)
    if self.interval - self.sample >= self.IDLE:
      return self.GoPassive()
    else:
      self.mode = self.ACTIVE
      #print("Active")
      return self.SendMode(0xE1,1)

  # from active mode go into passive mode (passive normal state ?)
  def GoPassive(self, debug=False):
    if debug: print("Go Passive from 0X%X" % self.mode)
    if self.mode != self.PASSIVE:
      self.ser.read()
      return self.SendMode(0xE1,0)
    self.mode = self.PASSIVE
    return True

  # in passive mode do one data telegram reading
  def PassiveRead(self):
    if self.mode == self.STANDBY:
      self.Normal()
      for cnt in range(30):
        self.ser.read()
        sleep_ms(1000)    # wait 30 seconds to establish air flow
    if self.mode != self.PASSIVE: self.GoPassive()
    return self.SendMode(0xE2,0)


  # check data array is decreasing and #pcs >10
  def decreasing(self,data):
    tmp = data[0]
    if max(data) <= 10: return False
    for item in data[1:]:
      if tmp >= item: tmp = item
      else:
        print("found non decreasing data: ", data)
        return False
    return True

  # original read routine comes from irmusy@gmail.com http://http://irmus.tistory.com/
  # added active/passive and fan on/off handling
  # data telegram struct for PMS5003 and PMS7003 (32 bytes)
  # PMS1003/PMS4003 the data struct is similar (24 bytes)
  # Hint: use pmN_atm (atmospheric) data values in stead of pmN values
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
    StrtTime = ticks_ms(); LastTime = ticks_ms()
    buff = []; inStartup = 4
    if self.mode == self.STANDBY: self.GoActive()
    self.ser.read()
    while True:
      # self.ser.read()
      if self.mode != self.ACTIVE or self.mode != self.NORMAL:
        # in PASSIVE mode we wait one second per read
        if cnt:
          wait = ticks_ms()-LastTime
          if (wait < 1000) and wait:
            sleep_ms(wait)
        # passive?:if fan off switch it on, initiate read
        if not self.PassiveRead():
          return {}
      while True:       # search header (0x42 0x4D) of data telegram
        if ErrorCnt >= 20:
            return {}
        waitcnt = 0
        while waitcnt < 10 and self.ser.any() < 2:
            sleep_ms(1000)
            waitcnt += 1
        if self.ser.any() < 2:
          ErrorCnt += 1
          if self.debug: print("reactivate PMS")
          if self.mode == self.ACTIVE or self.mode == self.NORMAL:
            self.mode = self.PASSIVE
            if self.GoActive(): continue
          else:
            self.PassiveRead()
          continue
        try:
          buff = self.ser.read(1)  # 1st byte header
          if ORD(buff[0]) == 0x42:
            buff = self.ser.read(1) # 2nd byte header
            if buff and ORD(buff[0]) == 0x4d:
                break
        except:
          ErrorCnt += 1
          continue           # try next data telegram

      if not cnt: StrtTime = ticks_ms()
      # packet remaining. fixed length packet structure
      for w in range(40):
        if self.ser.any() >=30: break
        if w > 39: raise OSError("read telegram timeout")
        if (self.debug or debug) and (w%2): print("wait %d on sensor data" % w)
        sleep_ms(200)
      buff = self.ser.read(30)
      # one measurement 200-800ms or every second in sample time
      if cnt and (LastTime+1000 > ticks_ms()):
        print("Skip %d dust measurement" % cnt)
        self.ser.read()
        continue   # skip measurement if time < 1 sec
      LastTime = ticks_ms()

      check = 0x42 + 0x4d # sum check every byte from HEADER to ERROR byte
      for b in buff[0:28]: check += ORD(b)
      data = list(struct.unpack('!HHHHHHHHHHHHHBBH', buff))
      if not sum(data[self.PMS_PCNT_0P3:self.PMS_VER]):
        # first reads show 0 particle counts, skip telegram
        if self.debug: print("null data, skipped")
        continue
      # compare check code
      if check != data[self.PMS_SUMCHECK]:
        if self.debug or debug:
          print("Incorrect check code check 0X%x != data check 0x%x" % (check,data[self.PMS_SUMCHECK]))
        ErrorCnt += 1
        if ErrorCnt >= 20:
            raise OSError("too many sum check")
        # self.ser.readall()
        continue
      if inStartup > 0: # skip first measurements
        inStartup -= 1; sleep_ms(500); continue
      if max(data[self.PMS_PM1P0:self.PMS_PM10P0+1]) > 500: # del 1st spikes
        if self.debug: print("Skip spike = %0.1f" %  data[self.PMS_PM1P0])
        continue # first 2 reads
      if data[self.PMS_ERROR]:
        print("PMS device error: %s" % str(data[self.PMS_ERROR]))
        ErrorCnt += 1
        if ErrorCnt > 20: raise ValueError("Module errors %s" % str(data[self.PMS_ERROR]))
        continue

      ErrorCnt = 0
      if not self.firmware:
        self.firmware = str(data[self.PMS_VER])
        #print("firmware: %s" % self.firmware)

      sample = {}
      for i in range(self.PMS_PM1P0_PAR1,self.PMS_PCNT_10P0+1):
        data[i] = float(data[i]) # make them all float
      if not self.decreasing(data[self.PMS_PCNT_0P3:self.PMS_PCNT_10P0+1]): continue
      # estimate avg PM size
      grain = (0.4*(data[self.PMS_PCNT_0P3]-data[self.PMS_PCNT_0P5])+0.75*(data[self.PMS_PCNT_0P5]-data[self.PMS_PCNT_1P0])+1.75*(data[self.PMS_PCNT_2P5]-data[self.PMS_PCNT_1P0])+3.75*(data[self.PMS_PCNT_2P5]-data[self.PMS_PCNT_5P0])+7.5*(data[self.PMS_PCNT_5P0]-data[self.PMS_PCNT_10P0]))/(data[self.PMS_PCNT_0P3]-data[self.PMS_PCNT_10P0])
      if self.debug: print("Raw data: ", data)
      if debug:
        print("Sample data")
        if not cnt:
          for fld in self.PM_fields:
            print("%8.8s " % fld[0],end='')
          print()
          for fld in self.PM_fields:
            print("%8.8s " % fld[1],end='')
          print()
        for fld in self.PM_fields:
          print("%8.2f " % data[fld[2]],end='')
        print()
      for fld in self.PM_fields:
        if fld[2] != 0:
          PM_sample[fld[0]] = PM_sample.setdefault(fld[0],0.0)+data[fld[2]]
        else:
          PM_sample[fld[0]] = PM_sample.setdefault(fld[0],0.0)+grain
      cnt += 1
      # average read time is 0.85 secs. Plantower specifies 200-800 ms
      # Plantower: in active smooth mode actual data update is 2 secs.
      sleep_ms(5*1000)
      if ticks_ms() > StrtTime + self.sample:
        break
    SampleTime = ticks_ms() - StrtTime
    if SampleTime < 0: SampleTime = 0
    if cnt:   # average count during the sample time
      for fld in self.PM_fields:
        PM_sample[fld[0]] /= cnt
        if self.raw or (fld[3] == None):
          PM_sample[fld[0]] = round(PM_sample[fld[0]]+0.05,2)
        else:
          PM_sample[fld[0]] = round(self.calibrate(fld[3],PM_sample[fld[0]])+0.05,2)
        
      if not self.explicit:
        for item in '05','1','25','5','10':
          PM_sample['pm%s_cnt'%item] = PM_sample['pm03_cnt'] - PM_sample['pm%s_cnt'%item]
        del PM_sample['pm03_cnt']

    # turn fan off?
    if self.interval - SampleTime > 60*1000:
      self.Standby()    # switch fan OFF
    # print("Sample PM: ",PM_sample)
    return PM_sample

if __name__ == "__main__":
    import sys
    from time import time, sleep
    interval = 5*60
    sample = 60
    debug = True
    explicit = False   # True: Plantower way of count, False: Sensirion way (dflt=False)
    pmsx003 = PMSx003(port=sys.argv[1], debug=debug, sample=sample, interval=interval, explicit=explicit)
    for i in range(4):
        lastTime = time()
        print(pmsx003.getData(debug=debug))
        now = interval + time() -lastTime
        if now > 0: sleep(now)
