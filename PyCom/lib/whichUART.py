# Copyright 2020, Teus Hagen, GPLV4
# identify which UART device is c nnected to which TTL connector
# to do?: from ucollections import namedtuple
#        pins = namedtuple('pins',('Tx','Rx,'Pwr'))
#        dustPins = pins('P11','P10','P20'); dustPins.Pwr etc

from time import sleep_ms
from machine import UART

__version__ = "0." + "$Revision: 5.6 $"[11:-2]
__license__ = 'GPLV4'

# Config.py definitions preceed
# if MyPins array of (Tx,Rx[,Pwr]) tuples is defined try to identify UART device
# if MyPins is defined dust or useGPS + pins maybe overwritten
class identification:
  def __init__(self, uart=1, MyPins=[], identify=True, config={}, devs={}, debug=False):
    self.myTypes = { 'dust': ['PMS','SDS','SPS'], 'gps': ['GPS','NEO-6']}
    if not type(MyPins) is list: MyPins = []
    self.pins = []       # available TTL pins
    self.allocated = []  # TTL pins in use
    if uart == 1:
      self.pins.append(('P1','P0','P20'))
      self.allocated.append(self.pins[0])
    self.index = uart
    self.devices = devs  # file descrs of ttl devices
    if config:      # import config
      for item in config.keys():
        if len(self.pins) == 3: break
        try:
          config[item]['pins'] = tuple(config[item]['pins'])
          if not config[item]['pins'] in self.pins:
            self.pins.append(config[item]['pins'])
        except: pass
      self.conf = config   # configs of ttl devices
    else: self.conf = dict()
    self.conf['updated'] = False
    if len(self.pins) == 1: # more pins?
      try: from Config import UARTpins as MyPins
      except: pass
      for item in MyPins + [('P4','P3'),('P11','P10')]:
        if len(self.pins) == 3: break
        if len(item) < 3:
          item = list(item)+[None]
        item = tuple(item)
        if item[0] in self.pins[0]:
          self.pins[0] =  item
        elif not item in self.pins: self.pins.append(item)
    if len(self.pins) == uart:
       self.pins += [('P4','P3',None),('P11','P10',None)] # dflt
    self.debug = debug
    if debug: print("Pins %s, allocated: %s" %(str(self.pins),str(self.allocated))) 
    if identify: self.identify()
    if self.debug:
      print("UART config: ", self.conf)
      print("UART devs: ", self.devices)
    return None

  # power on/off on TTL, return prev value
  def Power(self, pins, on=None):
    if not type(pins[2]) is str: return None
    from machine import Pin
    pin = Pin(pins[2], mode=Pin.OUT)
    if on:
      if pin.value(): return True
      if self.debug: print("Activate TTL chan (Tx,Rx,Pwr): ", pins)
      pin.value(1); sleep_ms(200); return False
    elif on == None: return pin.value()
    elif pin.value():
      if self.debug: print("Deactivate TTL chan (Tx,Rx,Pwr): ", pins)
      pin.value(0); return True
    else: return False

    # unclear if next 2 fie do work work properly
  def openUART(self, atype='dust'):
    if not atype in self.devices.keys(): self.identify(atype=atype)
    if not atype in self.devices.keys(): raise ValueError("%s: not identified" % atype)
    if self.devices[atype]['ttl'] == None:
      if self.devices[atype]['index'] == None:
        free = [1,2]
        for item in self.devices.keys():
           try: free.remove(item['index'])
           except: pass
        if not free: return False
      self.devices[atype]['index'] = free[0]
      self.devices[atype]['ttl'] = UART(self.devices[atype]['index'], baudrate=self.conf[atype]['baud'], timeout_chars=20)
      # self.devices[atype]['enabled'] = self.conf[atype]['use']
    self.Power(self.conf[atype]['pins'], on=True)
    return self.devices[atype]['ttl']

  def closeUART(self, atype='dust'):
    if not atype in self.devices.keys(): return False
    self.Power(self.devices[atype]['pins'], on=False)
    if self.devices[atype]['ttl'] != None:
      self.devices[atype]['ttl'].deinit()
      self.devices[atype]['ttl'] = None
      self.devices[atype]['index'] = None
      # self.devices[atype]['ttl']['enabled'] = False
    return True

 # config a TTL channel and search which sensor is attached
  def getConf(self, atype, pins, pwr=None):
    #self.conf = { # PCB TTL defaults example
    #    'usb':  {'name':'usb',    'pins':('P1','P0','P20'),  'use':False, 'baud':None},
    #    'dust': {'name':'PMSx003','pins':('P11','P10','P9'), 'use':None,  'baud':9600},
    #    'gps':  {'name':'NEO-6',  'pins':('P4'.'P3','P19'),  'use':None,  'baud':9600},
    #    }
    pins = tuple(pins)
    try:
      if self.conf[atype]['pins'] == pins:
        if self.conf[atype]['name']: return self.conf[atype]
    except: pass
    data = [
      b'\x42\x4D\xE1\x00\x01\x01\x71',     # PMS
      b'\x7E\x00\x00\x02\x01\x03\xF9\x7E', # SPS start
      b'\xAA\xB4\x06\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF\x06\xAB', # SDS
      ]
    for baudrate in [9600, 115200]:
      if self.debug: print("Try uart (baud=%d) pins: " % baudrate, pins)
      if not (0 <= self.index < 3): raise ValueError("UART index %d fail" % nr)
      prev = self.Power(pins, on=True)
      if not prev: sleep_ms(500)
      ser = UART(self.index, baudrate=baudrate, pins=pins[:2], timeout_chars=20)
      fnd = None
      if self.debug: print("getIdent type %s" % atype)
      for i in range(0,2*len(data)):
        sleep_ms(5*500 if atype == 'dust' else 500)
        try:
          line = ser.readall()
          # if self.debug: print("Read: ", line)
        except Exception as e:
          if self.debug: print("TTL dev search %s" % e)
          continue
        if (atype == 'dust') and ((line == None) or (not len(line))):   # try to wake up
          activate = data[i % len(data)]
          if self.debug: print("%d: Try a wakeup, send: " % i, activate)
          ser.write(activate)
          continue
        else:
          if not line: continue
          if line.count(b'u-blox'): fnd = 'NEO-6'
          elif line.count(b'$GPG'): fnd = 'GPS'
          elif line.count(b'\x42\x4D') or line.count(b'BM\x00\x1C'): fnd = 'PMSx003'
          elif line.count(b'\xAA') and line.count(b'\xC0'): fnd = 'SDS011'
          elif line.count(b'~\x00\x00') or line.count(b'\x00\xFF~'): fnd = 'SPS30'
          if fnd: break
      ser.readall(); ser.deinit(); del ser; self.Power(pins,on=prev)
      use = True; Dexplicit = None; calibrate = None
      if atype == 'dust':
        try: from Config import useDust as use
        except: pass
        Dexplicit = False
        try: from Config import Dexplicit
        except: pass
        if not 'calibrate' in self.conf.keys():
          calibrate = None
          try: from Config import calibrate
          except: pass
          self.config['calibrate'] = calibrate
      elif atype.lower() == 'gps':
        try: from Config import useGPS as use
        except: pass
      if fnd:
        thisConf = { 'name': fnd, 'baud':  baudrate, 'pins': pins, 'use': use }
        if Dexplicit != None: thisConf['explicit'] = Dexplicit
        if calibrate != None: thisConf['calibrate'] = calibrate
        self.conf[atype] = thisConf; self.conf['updated'] = True
        self.allocated.append(pins)
        return self.conf[atype]
    if (not pins[2]) and pwr:
      for dlf in 'P19','P20': # try dflts: P1? in V2.1
        fnd = self.getConf(atype,(pins[0],pins[1],dlf),baudrate=baudrate)
        if fnd: return fnd
    return None

  # side effect will enable power, on end: power dflt enabled
  def getIdent(self, atype='dust', power=True):
    if self.debug: print("Using UART/pins (Tx/Rx/Pwr): ", self.pins)
      # print("Wrong wiring may hang UART sensor scan search...")
    if atype in self.devices.keys():
      if self.debug: print("%s device: " % atype, self.devices[atype])
      return self.devices[atype]
    if (not atype in self.conf.keys()) or (self.conf[atype]['name'] == None):
      fnd = None
      for pins in self.pins:
         if pins in self.allocated: continue
         fnd = self.getConf(atype, pins)
         if fnd: break
      if not fnd:
        print("Unable to find config for %s" % atype)
        return None
    self.devices[atype] = {'lib': None, 'enabled': None, 'conf': self.conf[atype]}
    if 0 <= self.index < 3:
      # 'lib': not completed in this name space
      self.devices[atype]['index'] = self.index
      self.devices[atype]['ttl'] = UART(self.index, baudrate=self.conf[atype]['baud'], pins=tuple(self.conf[atype]['pins'][:2]), timeout_chars=500)
      self.index += 1
      self.devices[atype]['enabled'] = self.conf[atype]['use']
      self.Power(self.conf[atype]['pins'], on=power)
      if self.debug: print("%s device: " % atype, self.devices[atype])
    return self.devices[atype]

  # search UARTs for sensor types
  def identify(self,types=None):
    if types == None: types = self.myTypes
    for atype in types:
      if not atype in self.devices.keys():
        self.getIdent(atype=atype, power=None)
    return self.devices

  def Device(self,atype='dust'):
    try:
      if not atype in self.conf.keys():
        self.getIdent(atype=atype,power=True)
      return self.devices[atype]
    except: return None

  def Pins(self,atype='dust'):
    try:
      if not atype in self.conf.keys():
        self.getIdent(atype=atype,power=True)
      return self.conf[atype]['pins']
    except: return None

  def NAME(self,atype='dust'):
    try:
      if not atype in self.conf.keys():
        self.getIdent(atype=atype,power=True)
      return self.conf[atype]['name']
    except: return None

  @property
  def Dust(self): return self.Device(atype='dust')

  @property
  def DUST(self): return self.NAME(atype='dust')

  @property
  def Gps(self): return self.Device(atype='gps')

  @property
  def GPS(self): return self.NAME(atype='gps')

  @property
  def config(self): return self.conf

  @property
  def Devices(self): return self.devices

  @property
  def calibrate(self):
    if 'calibrate' in self.conf.keys(): return self.conf['calibrate']
    return None
