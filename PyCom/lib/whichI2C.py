# Copyright 2019, Teus Hagen, GPLV4
# search for I2C devices and get supporting libraries loaded
# maintain a i2c dict config with name, use, pins, address
#          and i2c devices with lib, i2c ref, index, and pins
from time import sleep_ms
from machine import I2C

__version__ = "0." + "$Revision: 5.4 $"[11:-2]
__license__ = 'GPLV4'

# Config.py definitions preceed
# if MyPins array of [(SDA,SCL[,Pwr]) tuples to identify pins for devices
class identification:
  def __init__(self, i2c=0, MyPins=[], identify=True, config={}, devs={}, debug=False):
    self.myTypes = { 'meteo': ['BME','SHT'], 'display': ['SSD']}
    if not type(MyPins) is list: MyPins = []
    self.pins = []
    self.devices = devs
    max = 3 # max 3 busses
    if config: # import config
      for item in config.keys():
        if len(self.pins) == max: break
        try:
          config[item]['pins'] = tuple(config[item]['pins'])
          if not config[item]['pins'] in self.pins:
            self.pins.append(config[item]['pins'])
          max -= 1
        except: pass
      self.conf = config
    else: self.conf = dict()
    self.conf['updated'] = False
    if not self.pins: # more?
      try: from Config import I2Cpins as MyPins
      except: pass
      for i in range(0,len(MyPins)):
        if len(self.pins) == max: break
        if len(MyPins[i]) < max:
          MyPins[i] = list(MyPins[i])+[None]
        MyPins[i] = tuple(MyPins[i])
        if not MyPins[i] in self.pins:
          self.pins.append(MyPins[i])
    if not self.pins: self.pins=[('P23','P22',None)] # dflt
    self.debug = debug
    if identify: self.identify()
    if self.debug:
      print("I2C config: ", self.conf)
      print("I2C devs: ", self.devices)
    return None

  # power on/off on TTL, return prev value
  def Power(self, pins, i2c=None, on=None):
    if not type(pins[2]) is str: return None
    from machine import Pin
    pin = Pin(pins[2], mode=Pin.OUT)
    if on:
      if pin.value(): return True
      if self.debug: print("Activate I2C chan (Tx,Rx,Pwr): ", pins)
      pin.value(1)
      if i2c:
        i2c.init(I2C.MASTER, pins=tuple(pins[:2]))
        sleep_ms(200)
      return False
    elif on == None: return pin.value()
    elif pin.value():
      if self.debug: print("Deactivate I2C chan (Tx,Rx,Pwr): ", pins)
      pin.value(0); return True
    else: return False

  # obtain I2C dev optional ID
  def chip_ID(self, pins, i2c=None, address=0x77):
    if i2c == None: return None
    chip_ID_ADDR = const(0xd0)
    # Create I2C device.
    if not type(i2c) is I2C:
      raise ValueError('An I2C object is required.')
    ID = 0 # 12 bits name, 9 bits part nr, 3 bits rev
    prev = None
    if type(pins[2]) is str:
        prev = self.Power(pins,on=True)
        sleep_ms(200)
    try:
        ID = i2c.readfrom_mem(address, chip_ID_ADDR, 3)
    except Exception as e:
        print("Unable to read I2C chip ID: %s" % e)
    if prev != None: self.Power(pins,on=prev)
    # print("ID: ", ID)
    return int.from_bytes( ID,'little') & 0xFF

  BME280_ID = const(0x60)
  BME680_ID = const(0x61)
  SSD1306_ID = const(0x3)
  def getUnknown(self, atype='meteo', power=True):
    I2Cdevices = [
          ('BME280',0x76),('BME280',0x77), # BME serie Bosch
          ('SHT31',0x44),('SHT31',0x45),   # Sensirion serie
          ('SSD1306',0x3c)                 # oled display
       ]
    if self.debug:
      print("Search for device %s I2C: " % atype, I2Cdevices)
    rts = False
    for index in range(0,len(self.pins)):
      previous = self.Power(self.pins[index], on=True)
      sleep_ms(100)
      cur_i2c = I2C(index, I2C.MASTER, pins=self.pins[index][:2]) # master
      regs = cur_i2c.scan(); sleep_ms(200)
      if self.debug: print("I2C regs: ", regs)
      for item in I2Cdevices:  # collect all
        if item[1] in regs:
          ID = self.chip_ID(self.pins[index], cur_i2c, item[1])
          if item[0][:3] == 'BME':
            if ID == BME680_ID: item = ('BME680',item[1])
            elif ID != BME280_ID: raise ValueError("Unknown BME id 0x%X" % ID)
          this = None
          for device in self.myTypes.items():
            if device[0] in self.conf.keys(): continue
            if item[0][:3] in device[1]:
              this = device[0]; break
          if not this: continue
          if self.debug:
            print('add %s: %s ID=0x%X I2C[%d]:' % (this, item[0],ID,index),end='')
            print(' SDA~>%s, SCL~>%s, Pwr->' % tuple(self.pins[index][:2]),end='')
            print(self.pins[index][2], ', reg 0x%2X' % item[1])
          # will overwrite previous values and devices
          self.conf[this] = {}; self.conf['updated'] = True
          self.conf[this]['address'] = item[1]
          self.conf[this]['pins'] = tuple(self.pins[index][:3])
          self.conf[this]['name'] = item[0]
          self.conf[this]['use'] = True
          if item[0][:3] == 'SSD':
            try:
              from Config import useDisplay
              if not useDisplay: self.conf[this]['use'] = False
            except: pass
          elif not 'calibrate' in self.conf.keys():
             calibrate = None
             try: from Config import calibrate
             except: pass
             self.conf['calibrate'] = calibrate
          if this == atype: rts = True
          if self.debug: print("I2C new %s found: " % this, self.conf[this])
      cur_i2c.deinit()
      self.Power(self.pins[index], cur_i2c, on=power)
    return rts

  # side effect will enable power, on end: power dflt enabled
  def getIdent(self, atype='meteo', power=True):
    if self.debug:
      print("Using I2C SDA/SCL/Pwr pins: ", self.pins)
      # print("Wrong wiring may hang I2C address scan search...")
    if not atype in self.conf.keys():
      if not self.getUnknown(atype=atype,power=power):
        print("Unable to find config for %s" % atype)
        return None
    if atype in self.devices.keys():
      if self.debug: print("%s device: " % atype, self.devices[atype])
      return self.devices[atype]
    self.devices[atype] = {'i2c': None, 'index': None, 'lib': None,
                           'enabled': None, 'conf': self.conf[atype]}
    self.conf[atype]['pins'] = tuple(self.conf[atype]['pins'])
    try: index = self.pins.index(self.conf[atype]['pins'])
    except: raise ValueError("Unknown I2C pins: %s" % str())
    for item in self.devices.items():
      try:
        if item[1]['index'] == index: # on same bus
          self.devices[atype]['i2c'] = item[1]['i2c'] ; break
      except: pass
    if self.devices[atype]['i2c'] == None:
      self.devices[atype]['i2c'] = I2C(index, I2C.MASTER, pins=tuple(self.pins[index][:2])) # master
    self.devices[atype]['index'] = index
    self.devices[atype]['enabled'] = self.conf[atype]['use']
    self.Power(self.conf[atype]['pins'], self.devices[atype]['i2c'], on=power)
    if self.debug: print("%s device: " % atype, self.devices[atype])
    return self.devices[atype]

  # search I2C for sensor types
  def identify(self,types=None):
    if types == None: types = self.myTypes
    for atype in types:
      if not atype in self.devices.keys():
        self.getIdent(atype=atype)
    # self.devices['oled'] = self.devices['display']
    return self.devices

  def Device(self,atype='meteo'):
    try:
      if not atype in self.conf.keys():
        self.getIdent(atype=atype,power=True)
      return self.devices[atype]
    except: return None

  def Pins(self,atype='meteo'):
    try:
      if not atype in self.conf.keys():
        self.getIdent(atype=atype,power=True)
      return self.conf[atype]['pins']
    except: return None

  def NAME(self,atype='meteo'):
    try:
      if not atype in self.conf.keys():
        self.getIdent(atype=atype,power=True)
      return self.conf[atype]['name']
    except: return None

  @property
  def Meteo(self): return self.Device(atype='meteo')

  @property
  def METEO(self): return self.NAME(atype='meteo')

  @property
  def Display(self): return self.Device(atype='display')

  @property
  def Oled(self): return self.Device(atype='display')

  @property
  def DISPLAY(self): return self.NAME(atype='display')

  @property
  def OLED(self): return self.DISPLAY()

  @property
  def config(self): return self.conf

  @property
  def Devices(self): return self.devices

  @property
  def calibrate(self):
    if 'calibrate' in self.conf.keys(): return self.conf['calibrate']
    return None
