'''
Created on 24 Apr 2017

@author: rxf
'''
# comes from https://github.com/rexfue/Feinstaub_LoPy
# changes by teus license GPLV3
# Frank Heuer wrote a better and more extensive script
# $Id: SDS011.py,v 1.5 2018/04/18 08:55:29 teus Exp teus $

try:
  from machine import  UART
  from micropython import const
  from time import ticks_ms, sleep_ms
except:
  from const import const, UART, ticks_ms, sleep_ms

""" Get sensor values: PM2.5 and PM10 from Nova Particular Matter sensor
  Types: 7003 or 5003
  units: pcs/0.01qf, pcs/0.1dm3, ug/m3
  class inits:
  port=1 port number
  debug=False show measurements
  sample=60   sample time in seconds
  interval=1200 sleep time-sample / fan off after sampling if 0 no interval
"""

# read from UART1 V5,Gnd, SDS011/Rx - GPIO P3/Tx, SDS011/Tx - GPIO P4/Rx

class SDS011:
  ACTIVE  = const(0)   # default mode on power ON
  PASSIVE = const(1)   # fan ON, values on request, not supported yet
  NORMAL  = const(3)   # state normal   fan is ON
  STANDBY = const(4)   # state standby fan is OFF
  # idle time minimal time to switch fan OFF
  IDLE  = const(120000)   # minimal idle time between sample time and interval

  def __init__(self, port=1, debug=False, sample=60, interval=1200, raw=False, calibrate=None,pins=('P3','P4'), explicit=None):
    # explicit (pm count style) not used
    self.ser = UART(1,baudrate=9600,pins=pins)
    self.firmware = None
    self.debug = debug
    self.interval = interval * 1000 # if interval == 0 no auto fan switching
    self.sample =  sample *1000
    self.mode = self.STANDBY
    self.raw = raw
    self.deviceID = None
    # list of name, units, index in measurments, calibration factoring
    # pm1=[20,1] adds a calibration offset of 20 to measurement
    self.PM_fields = [
      # the Plantower conversion algorithm is unclear!
      ['pm25','ug/m3',0,[0,1]],
      ['pm10','ug/m3',1,[0,1]],
    ]
    if type(calibrate) is dict:
      for key in calibrate.keys():
        if calibrate[key] and type(calibrate[key]) != list: continue
        for pm in range(0,len(self.PM_fields)):
          if self.PM_fields[pm][0] == key:
            self.PM_fields[pm][3] = calibrate[key]
            break
    # decomment if not micropython
    try:
      self.ser.any
    except:
      self.ser.readall = self.ser.flushInput # reset_input_buffer
      self.ser.any = self.ser.inWaiting

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
  
  def readSDSvalues(self):
    ''' read PM values '''
    while True:
      n = self.ser.any()
      if n == 0:
        continue
      if n > 10:
        self.ser.read(n)
        continue
      rcv = self.ser.read(10)
      if len(rcv) != 10:
        continue
      if rcv[0] != 170 and rcv[1] != 192:
        # print("try to sychronize")
        continue
      i = 0
      chksm = 0
      while i < 10:
        if i >= 2 and i <= 7:
          chksm = (chksm + rcv[i]) & 255
        i = i+1
      if chksm != rcv[8]:
        print("*** Checksum-Error")
        return -1,-1
      pm25 = (rcv[3]*256+rcv[2])
      pm10 = (rcv[5]*256+rcv[4])
      if not self.deviceID: self.deviceID = '%X%X' % (rcv[6],rcv[7])
      return pm25/10.0, pm10/10.0
      
  # SDS anhalten bzw starten
  def startstopSDS(self,was):
    """ den SDS011 anhalten bzw. starten:
    was = NORMAL  --> fan start, wait 15 secs
    was = ACTIVE  --> fan was started, power on
    was = STANDBY --> fan stop
    """
    if was == ACTIVE or was == NORMAL:
      start_SDS_cmd = bytearray(b'\xAA\xB4\x06\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF\x06\xAB')
      self.ser.write(start_SDS_cmd)
      if self.debug: print("SDS fan/laser start.")
    elif was == STANDBY:
      stop_SDS_cmd =  bytearray(b'\xAA\xB4\x06\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF\x05\xAB')
      self.ser.write(stop_SDS_cmd)
      if self.debug: print("SDS fan/laser off")
    else: raise OSError("mode not supported")
    self.mode = was
      
  # passive mode, go into standby state / sleep: fan OFF
  def Standby(self):
    if self.mode != self.STANDBY:
      # if self.mode == self.ACTIVE: self.GoPassive()
      return self.startstopSDS(self.STANDBY)
    return True

  # passive mode, go into normal state: fan ON, allow data telegrams reading
  def Normal(self):
    if self.mode != self.NORMAL:
      #if self.mode == self.ACTIVE: self.GoPassive()
      if self.mode != self.NORMAL:
        return self.startstopSDS(self.NORMAL)
    return True

  # from passive mode go in active mode (same as with power on)
  def GoActive(self):
    if self.mode == self.STANDBY:
      self.Normal()
      if self.debug: print("wait 30 secs")
      sleep_ms(30000)
    self.startstopSDS(self.ACTIVE)
    return True

  # from active mode go into passive mode (passive normal state ?)
  #def GoPassive(self):
  #  self.mode = self.PASSIVE    # state NORMAL?
  #  if self.mode == self.ACTIVE:
  #    return self.startstopSDS(self.PASSIVE)
  #  return True

  # in passive mode do one data telegram reading
  def PassiveRead(self):
    if self.mode == self.ACTIVE: return
    if self.mode == self.STANDBY:
      self.Normal()
      sleep_ms(30000)    # wait 30 seconds to establish air flow
    return self.startstopSDS(self.ACTIVE)

  # original read routine comes from irmusy@gmail.com http://http://irmus.tistory.com/
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
    # to do: allow sampling data to be done by sensor module
    StrtTime = ticks_ms(); LastTime = ticks_ms(); buff = []
    if self.mode == self.STANDBY: self.GoActive()
    self.ser.readall()
    while True:
      # self.ser.readall()
      if self.mode != self.ACTIVE or self.mode != self.NORMAL:
        # in PASSIVE mode we wait one second per read
        if cnt:
          wait = ticks_ms()-LastTime
          if (wait < 1000) and wait:
            sleep_ms(wait)
        self.PassiveRead()   # passive?:if fan off switch it on, initiate read
      data = self.readSDSvalues()
      if not cnt: StrtTime = ticks_ms()
      # one measurement 200-800ms or every second in sample time
      if cnt and (LastTime+1000 > ticks_ms()):
        continue   # skip measurement if time < 1 sec
      LastTime = ticks_ms()

      ErrorCnt = 0
      sample = {}
      for fld in self.PM_fields:
        # concentrations in unit ug/m3
        # concentration (generic atmosphere conditions) in ug/m3
        # number of particles with diameter N in 0.1 liter air pcs/0.1dm3
        sample[fld[0]] = float(data[fld[2]]) # make it float
      if self.debug or debug:
        if not cnt:
          for fld in self.PM_fields:
            print("%8.8s " % fld[0],end='')
          print()
          for fld in self.PM_fields:
            print("%8.8s " % ('ug/m3' if fld[0][-4:] != '_cnt' else 'pcs/0.1dm3'),end='')
          print()
        for fld in self.PM_fields:
          print("%8.8s " % str(sample[fld[0]]),end='')
        print()
      cnt += 1

      for fld in self.PM_fields:
        PM_sample[fld[0]] = PM_sample.setdefault(fld[0],0.0)+sample[fld[0]]
      if ticks_ms() > StrtTime + self.sample:
        break
    SampleTime = ticks_ms() - StrtTime
    if SampleTime < 0: SampleTime = 0
    if cnt:   # average count during the sample time
      for fld in self.PM_fields:
        PM_sample[fld[0]] /= cnt
        PM_sample[fld[0]] = round(self.calibrate(fld[3],PM_sample[fld[0]]),2)

    # turn fan off?
    if self.interval - SampleTime > 60*1000:
      self.Standby()    # switch fan OFF
    return PM_sample
