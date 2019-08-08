# PyCom Micro Python / Python 3
# Copyright 2018, Teus Hagen, ver. Behoud de Parel, GPLV3
# some code comes from https://github.com/TelenorStartIoT/lorawan-weather-station
# $Id: MySense.py,v 5.58 2019/08/08 09:29:08 teus Exp teus $

__version__ = "0." + "$Revision: 5.58 $"[11:-2]
__license__ = 'GPLV3'

import sys
from time import sleep_ms, time
myTicks_ms = 0
myTicks = 0
# Turn off hearbeat LED
from pycom import heartbeat, nvs_set, nvs_get, nvs_erase
heartbeat(False)
import os
PyCom = 'PyCom %s' % os.uname().nodename
del os
LED = None
try:
  import led
  LED = led.LED()
except: pass
debug = True  # enable print dictionary
wokeUP = False
from machine import WDT
wdt    = None # watch dog

MyConfig = None      # handle to ConfigJson object
MyConfiguration = {} # configuration stable between deepsleeps and power cycle
MyDevices = {} # dyn. part, has bus refs to device dict with conf
MyTypes = {}   # dyn. part, has type refs to device dict with conf
MyNames = [('meteo','i2c'),('display','i2c'),('dust','ttl'),('gps','ttl'),('accu','pin'),('deepsleep','pin')]
lastGPS = [0,0,0]
Alarm = None              # tuple (nr,value)
AlarmAccu = const(13)     # event on empty accu, has accu level
AlarmWDT = const(14)      # watchdog sensor event, has marks
AlarmReset = const(15)    # unexpected exit of runMe()

import struct
from micropython import const
Threading = True
if Threading:
  import _thread
  # _thread.stack_size(6144)

# LoRa ports
# data port 2 old style and ug/m3, 4 new style grain, pm4/5 choice etc
Dprt = (2,4)    # data ports
Iprt = const(3) # info port, meta data, events

# oled is multithreaded
STOP = False
STOPPED = False
HALT = False  # stop by remote control
LAT = const(0)
LON = const(1)
ALT = const(2)

def MyMark(mark): # watchdog: sensor timeout mark
  global MyConfiguration
  global wdt
  try:
    if not wdt:
      wdt = WDT(timeout=(MyConfiguration['interval']['interval']*3*1000))
    else: wdt.feed()
  except: pass
  nvs_set('AlarmWDT',mark)

# return bus or if bus [type(s)]
def Type2Bus(atype): # and visa versa
  global MyNames
  rts = []
  for item in MyNames:
    if (atype == item[1]) and (not atype in rts): rts.append(item[0])
    elif atype == item[0]: return item[1]
  return rts

def Type2Dev(atype):
  global MyTypes, MyDevices
  try: return MyDevices[Type2Bus(atype)][atype]
  except: return None

def PrintDict(adict = None, header=''):
  global debug
  if not debug: return
  global MyConfiguration, MyDevices
  if adict != None:
    print("dict '%s'->" % header)
    for item in adict.items():
      try: print("    '%s'-> %s" % (item[0], str(item[1])))
      except: pass
  else:
    PrintDict(MyConfiguration,'MyConfiguration')
    PrintDict(MyDevices,'MyDevices')

# identity PyCom SN
def getSN():
  from machine import unique_id
  import binascii
  SN = binascii.hexlify(unique_id()).decode('utf-8')
  return SN

def ticks(): # wrap in Jan 2038
  global myTicks, myTicks_ms
  from time import ticks_ms, ticks_diff
  now = ticks_ms()
  if not myTicks:
    myTicks_ms = now
    myTicks = int((now+500)/1000)
  else:
    myTicks += int((ticks_diff(myTicks_ms,now)+500)/1000)
    myTicks_ms = now
  return myTicks

def getSavedGPS():
  # global LAT, LON, ALT
  try:
    return [nvs_get('LAT')/1000000.0,nvs_get('LON')/1000000.0,nvs_get('ALT')/10.0]
  except: return [0,0,0]

def saveGPS(curGPS):
  global LAT, LON, ALT
  nvs_set('LAT',int(curGPS[LAT]*1000000))
  nvs_set('LON',int(curGPS[LON]*1000000))
  nvs_set('ALT',int(curGPS[ALT]*10))
  return curGPS[0:]

# Read accu voltage out
def getVoltage(debug=False): # range 0 (None) and 11.4 (88% low) - 12.5 (high)
  global MyDevices, MyConfig, MyDevices, MyTypes
  if not MyConfig: initConfig()
  atype = 'accu'
  try:
    if not 'accuPin' in MyConfiguration.keys():
      accuPin = 'P17'
      try: from Config import accuPin
      except: pass
      MyConfig.dump('accuPin',accuPin)
      MyConfiguration['accuPin'] = accuPin
    else: accuPin = MyConfiguration['accuPin']
    if not atype in MyDevices.keys():
      from machine import ADC
      MyTypes[atype] = MyDevices[atype] = {
        'max': None,
        'lib': ADC(0).channel(pin=accuPin, attn=ADC.ATTN_11DB)}
    volts = [MyDevices[atype]['lib'].value()*0.004271845]
    if volts[0] > 0.1:  # accu attached
      for i in range(9): # 10 sec sample
        sleep_ms(1000)
        volts.append(MyDevices[atype]['lib'].value()*0.004271845)
      volts = (min(volts),sum(volts)/len(volts),max(volts))
      if debug: print('volts: %s' % str(volts))
      mmax = MyTypes[atype]['max']
      if mmax == None:
        try: mmax = nvs_get('Vmax')/10.0
        except: pass
        if mmax == None: mmax = 0
      if volts[1] > (mmax + 0.09):
        MyTypes[atype]['max'] = volts[1]
        nvs_set('Vmax', int(volts[1]*10.0+0.5))
        # if not max: MyConfig.dump('Vmax',max)
      mmin = None
      try: mmin = nvs_get('Vmin')/10.0
      except: pass
      if mmin == None: mmin = 100
      if volts[1] < (mmin - 0.09):
        nvs_set('Vmin', int(volts[1]*10.0-0.5))
      if debug: print("Accu V: %.2f [%.2f - %.2f]" % (volts[1],mmin,mmax))

      if volts[1] < 10.9:
        global Alarm, AlarmAccu
        Alarm = (AlarmAccu,int(volts[1]*10))
      return volts
  except Exception as e:
    print(str(e))
  return (0,0,0)

# sleep phases all active till config done after cold start, then:
#    sleep pin not set & power sleep False: sleep, rgb led, wifi
#    pin set & power sleep False: deepsleep, while active: rgb led, wifi on
#    pin set & power sleep True: deepsleep, while active: no rgb led, wifi off
# clear config in flash on: cold start & no accu attached & no sleep pin

# get deepsleep pin value
def deepsleepMode():
  global MyDevices, MyConfig, MyConfiguration, MyTypes
  if not MyConfig: initConfig()
  atype = 'deepsleep'
  try:
    if not 'sleepPin' in MyConfiguration.keys():
      sleepPin = 'P18'
      try: from Config import sleepPin
      except: pass
      MyConfig.dump('sleepPin',sleepPin)
      MyConfiguration['sleepPin'] = sleepPin
    else: sleepPin = MyConfiguration['sleepPin']
    if not atype in MyDevices.keys():
      from machine import Pin
      MyTypes[atype] = MyDevices[atype] = { 'lib': Pin(sleepPin,mode=Pin.IN), 'type': atype}
    return not MyDevices[atype]['lib'].value()
  except: return False

def setWiFi(reset=False,debug=False):
  global MyConfiguration
  cnt = None
  try: cnt = nvs_get('count')
  except: pass
  if not cnt: cnt = 0
  cntHour = 4
  try: cntHour = int(4500/MyConfiguration['interval']['interval'])
  except: pass
  if reset:
    nvs_set('count',0)
    if cnt > cntHour: cnt == cntHour # enable wifi
    else: cnt = 0
  else: nvs_set('count',cnt+1)
  if cnt == cntHour: # after ca 1 Hr turn wifi off or give it new ssid/pass
    try:
      W_SSID = 'MySense-AAAA'; W_PASS = 'www.mycom.io'
      if not reset:
        if MyConfiguration['power']['wifi']:
          wlan.deinit() # switch wifi off
          display("WiFi AP: off")
          return False
        try: from Config import W_SSID
        except: pass
        try: from Config import W_PASS
        except: pass
      if W_SSID[-4:] == 'AAAA': W_SSID = W_SSID[:-4]+getSN()[-4:].lower()
      from network import WLAN
      wlan = WLAN()
      display("WiFi AP: %s" % W_SSID)
      display("pass: %s" % W_PASS)
      sleep_ms(5*1000)
      wlan.init(mode=WLAN.AP,ssid=W_SSID, auth=(WLAN.WPA2,W_PASS), channel=7, antenna=WLAN.INT_ANT)
    except: return False
  return True

## configuration from flash
def initConfig(debug=False):
  global MyConfiguration, MyConfig
  global wokeUp, Alarm, AlarmWDT

  if MyConfig: return

  from machine import wake_reason, RTC_WAKE, reset_cause, WDT_RESET
  from pycom import nvs_get, nvs_set
  wokeUp = wake_reason()[0] == RTC_WAKE # deepsleep wake up
  Alarm = None; AlarmT = None           # look for alarm event
  try: Alarm = nvs_get('myReset')
  except: pass
  if Alarm:
    nvs_erase('myReset')
    AlarmT = AlarmReset
  elif reset_cause() == WDT_RESET:
    AlarmT = AlarmWDT
  if AlarmT:
    try: Alarm = nvs_get('AlarmWDT') # where?
    except: pass
    Alarm = (AlarmT,Alarm) # got WDT timeout or runMe() fail
  else: Alarm = None
  nvs_set('AlarmWDT',0)

  import ConfigJson
  MyConfig = ConfigJson.MyConfig(archive=(not wokeUp), debug=debug)
  MyConfiguration = MyConfig.getConfig()
  if not wokeUp: # check startup mode
    modus = None
    try: modus = nvs_get('modus')
    except: pass
    if not modus:
      if MyConfiguration: MyConfig.clear # not def or 0: no archived conf
      MyConfiguration = dict()
      from pycom import nvs_erase_all
      nvs_erase_all()
    elif modus  == 1: # reset only discovered devices
      for abus in ['ttl','i2c']:
        try: MyConfiguration[abus] = dict()
        except: pass
    nvs_set('gps',-1)
    nvs_set('count',0)

def DEEPSLEEP(secs):
   nvs_set('AlarmSlp', secs)
   if secs <= 30:
     print("May not happen")
     return
   from machine import deepsleep
   print('Deepsleep of %d secs' % secs)
   deepsleep(secs*1000)
   # never arrive here: warm reboot

## CONF pins
def getPinsConfig(debug=False):
  global MyConfiguration, MyConfiguration, wokeUp
  global MyConfig
  if not MyConfig: initConfig()
  ## CONF accu
  deepsleepMode() # pins init
  ## CONF clear
  volts = getVoltage()
  if (not volts[0]) and deepsleepMode(): # reset config
    if not wokeUp: # cold restart
      print("Clear config disabled")
      # specal case: no accu & deepsleep pin present
      # print("Clear config in flash")
      # MyConfig.clear; MyConfig = None; MyConfiguration = {}
      # initConfig(debug=debug) 
      # MyDevices = {}
      # getVoltage(); deepsleepMode();
  if volts[0] and (volts[0] > 1.0):
    # Vmax = None
    # try:
    #   Vmax = nvs_get('Vmax')/10.0
    # except: pass
    # if not Vmax: Vmax = 12.6
    if volts[2] < 10.8: # 12V accu class 6%
      nvs_set('Accu',int(volts[1]*10.0+0.5))
      from pycom import rgbled
      pycom.rgbled(0x990000); sleep_ms(1*1000)
      DEEPSLEEP(15*60)

## CONF busses
def getBusConfig(busses=['i2c','ttl'], devices=None, debug=False):
  global MyConfig
  global MyConfiguration, MyDevices, MyTypes

  if not MyConfig: initConfig()
  if debug:
    PrintDict(MyConfiguration,'Start: Archived configuration')
    PrintDict(MyDevices,'My Devices')
  for abus in busses:
    if not abus in MyConfiguration.keys(): MyConfiguration[abus] = {}
    FndDevices = []
    if devices == None: busdevices = Type2Bus(abus) # use dflt
    else: busdevices = devices
    if debug: print("bus %s with devices: %s" % (abus, str(busdevices)))
    for dev in MyConfiguration[abus].keys():
      if not dev in busdevices: continue
      FndDevices.append(dev)
      if debug: print("Reuse dev %s config: %s" % (dev, str(MyConfiguration[abus][dev]))) 
    if abus == 'i2c': import whichI2C as which
    elif abus == 'ttl': import whichUART as which
    # PrintDict(MyConfiguration[abus],'MyConfiguration[%s]' % abus)
    if MyConfiguration[abus]:
      which = which.identification(identify=True, config=MyConfiguration[abus], debug=debug)
    else:
      which = which.identification(identify=True, debug=debug)
      MyConfiguration[abus] = which.config
      if debug: print("Bus %s: found %s types of devices" % (abus,str(MyConfiguration[abus].keys()) ))
    for atype in MyConfiguration[abus].keys():
      if not atype in busdevices: continue
      if not atype in FndDevices:
        if debug: print("New dev %s config: %s" % (atype, str(MyConfiguration[abus][atype])))
        MyConfig.dump(atype, MyConfiguration[abus][atype],abus=abus)
      if not abus in MyDevices.keys(): MyDevices[abus] = {}
      MyDevices[abus][atype] = which.getIdent(atype=atype)
      MyDevices[abus][atype]['type'] = atype
      MyTypes[atype] = MyDevices[abus][atype]
      # PrintDict(MyDevices[abus][atype],'MyDevices[%s][%s]' % (abus,atype))
      if 'conf' in MyDevices[abus].keys():
        print("WARNING found 'conf' in MyDevices[%s]" % abus)
        del MyDevices[abus] # strange

## CONF network
def getNetConfig(debug=False):
  global MyConfiguration, MyConfig, MyDevices, MyTypes
  global wokeUp

  if not MyConfig: initConfig()
  Network = 'TTN' # dflt
  if 'LoRa' in MyConfiguration.keys(): Network = 'TTN'
  if not wokeUp:
    try: from Config import Network
    except: pass
  if not Network in ['TTN', None]: raise ValueError("%s not supported" % Network)
  
  if Network == 'TTN':
    atype = 'lora'
    MyDevices[atype] = { 'name': Network, 'type': atype, 'enabled': False, 'lib': None }
    # 'LoRa' in config: use lora nvram
    if MyConfig.getConfig('LoRa') in ['ABP','OTAA']:
      if debug: print("Use LoRa nvram")
    #else: MyDevices[atype]['lib'].cleanup # will clear LoRa
  
    info = None
    MyDevices[atype]['method'] = {}
    if not wokeUp: # no keys in nvram or set them
      # lora routine will first try nvram restore and join (for ABP and cold start)
      if not 'LoRa' in MyConfiguration.keys():
        try: # OTAA keys preceeds ABP
          from Config import dev_eui, app_eui, app_key
          MyDevices[atype]['method']['OTAA'] = (dev_eui, app_eui, app_key)
          MyConfig.dump('LoRa','OTAA')
        except: pass
        try: # ABP keys
          from Config import dev_addr, nwk_swkey, app_swkey
          MyDevices[atype]['method']['ABP'] = (dev_addr, nwk_swkey, app_swkey)
          MyConfig.dump('LoRa','ABP')
        except: pass
        if not len(MyDevices[atype]['method']):
          raise ValueError("No LoRa keys configured or LoRa config error")
        if debug: print("Init LoRa methods: %s." % ', '.join(MyDevices[atype]['method'].keys()))
        MyConfiguration['LoRa'] = MyConfig.getConfig('LoRa')
      else:
        if debug: print("Using LoRa %s info from nvram" % MyConfiguration['LoRa'])
        MyDevices[atype]['method'][MyConfiguration['LoRa']] = (None,None,None)
    MyTypes['network'] = MyDevices[atype]
    if wokeUp: info = True # no need to send meta data
  else: None # no output
  
def getGlobals(debug=False):
  global MyConfiguration, MyConfig, wokeUp
  if not MyConfig: initConfig()
  global lastGPS
  ## CONF interval
  if not 'interval' in MyConfiguration:
    MyConfiguration['interval'] = {
       'sample': 60,      # dust sample in secs
       'interval': 15,    # sample interval in minutes
       'gps':      3*60,  # location updates in minutes
       'info':     24*60, # send kit info in minutes
    }
    try:
      from Config import interval
      if type(interval) is dict: MyConfiguration['interval'].update(interval)
    except: pass
    for item in ['interval','gps','info']:
      MyConfiguration['interval'][item] *= 60
      if MyConfiguration['interval']['interval'] <= 0:
        MyConfiguration['interval']['interval'] = 0.1
    MyConfig.dump('interval',MyConfiguration['interval'])
  if not wokeUp:
    # item for next time to send info: wrap around on 19 jan 2038!
    for item in ['gps_next','info_next']: # secs next send, reset to 0
      value = None
      try: value = nvs_get(item)
      except: pass
      if not value: nvs_set(item,0)
    nvs_set('gps',-1)
  
  ## CONF power mgt
  # device power management dflt: do not unless pwr pins defined
  # power mgt of ttl/uarts OFF/on, i2c OFF/on
  # deepsleep mode: deep sleep OFF/on, ON with deepsleep pin
  # display: None (always on), False: always off, True on and off during sleep
  # Warning: sleep pin P18 with no voltage on accu pin: clear config json file
  if not 'power' in MyConfiguration.keys():
    try:
      from Config import Power
      MyConfiguration['power'] = Power
    # deflt: no power mgt on ttl, i2c, display power mngt is used
    except:
      MyConfiguration['power'] = { 'ttl': False, 'i2c': False, 'sleep': False, 'display': None, 'led': False, 'wifi': False }
    if not wokeUp: MyConfig.dump('power', MyConfiguration['power'])
  if deepsleepMode():
    MyConfiguration['power']['ttl'] = MyConfiguration['power']['i2c'] = True
  # sleep dflt True: listen to pin mode
  
  ## CONF calibrate
  if not 'calibrate' in MyConfiguration.keys():
    # calibrate dict with lists for sensors { 'temperature': [0,1], ...}
    try: from Config import calibrate
    except: MyConfiguration['calibrate'] = {}      # sensor calibration Tayler array
    if not wokeUp: MyConfig.dump('calibrate',MyConfiguration['calibrate'])
  
  ## CONF dflt location
  if not 'thisGPS' in MyConfiguration.keys():
    thisGPS = [0.0,0.0,0.0]
    try: from Config import thisGPS # predefined GPS coord
    # location
    except: pass
    finally:
      MyConfiguration['thisGPS'] = thisGPS # completed by GPS
      MyConfig.dump('thisGPS',MyConfiguration['thisGPS'])
      lastGPS = getSavedGPS() # from nvs
      if not lastGPS[0]:
        lastGPS = MyConfiguration['thisGPS'][0:]
      nvs_set('gps_next',0)

## oled display routines
def oledShow():
  global MyTypes
  try:
    Display = MyTypes['display']
    if not Display['conf']['use'] or not Display['enabled']: return
    if not Display['lib']: return
  except: return
  for cnt in range(0,4):
    try:
      Display['lib'].show()
      break
    except OSError as e: # one re-show helps
      if cnt: print("show err %d: " % cnt,e)
      sleep_ms(500)

nl = 16 # line height
LF = const(13)
# text display, width = 128; height = 64  # display sizes
def display(txt,xy=(0,None),clear=False, prt=True):
  global MyTypes, nl
  if not MyTypes: getMyConfig()
  Display = None
  try:
    Display = MyTypes['display']
    if not Display['lib']:
      if not initDisplay(): Display = None
  except: pass
  if Display and Display['enabled'] and Display['conf']['use'] and Display['lib']:
    offset = 0
    if xy[1] == None: y = nl
    elif xy[1] < 0:
      if -xy[1] < LF:
        offset = xy[1]
        y = nl - LF
    else: y = xy[1]
    x = 0 if ((xy[0] == None) or (xy[0] < 0)) else xy[0]
    if clear:
      Display['lib'].fill(0)
    if y > 56:
      nl =  y = 16
    if (not offset) and (not clear):
      rectangle(x,y,128,LF,0)
    Display['lib'].text(txt,x,y+offset)
    oledShow()
    if y == 0: nl = 16
    elif not offset: nl = y + LF
    if nl >= (64-13): nl = 16
  if prt: print(txt)

def rectangle(x,y,w,h,col=1):
  global MyTypes
  try: Display = MyTypes['display']
  except: return
  if not Display['conf']['use'] or not Display['enabled']: return
  dsp = Display['lib']
  if not dsp: return
  ex = int(x+w); ey = int(y+h)
  if ex > 128: ex = 128
  if ey > 64: ey = 64
  for xi in range(int(x),ex):
    for yi in range(int(y),ey):
      dsp.pixel(xi,yi,col)

def ProgressBar(x,y,width,height,secs,blink=0,slp=1):
  global LED, STOP
  if x+width >= 128: width = 128-x
  if y+height >= 64: height = 64-y
  rectangle(x,y,width,height)
  if (height > 4) and (width > 4):
    rectangle(x+1,y+1,width-2,height-2,0)
    x += 2; width -= 4;
    y += 2; height -= 4
  elif width > 4:
    rectangle(x+1,y,width-2,height,0)
    x += 2; width -= 4;
  else:
    rectangle(x,y,width,height,0)
  step = width/(secs/slp); xe = x+width; myslp = slp
  if blink: myslp -= (0.1+0.1)
  for sec in range(int(secs/slp+0.5)):
    if STOP:
      return False
    if blink:
      if LED: LED.blink(1,0.1,blink,l=False)
    sleep_ms(int(myslp*1000))
    if x > xe: continue
    rectangle(x,y,step,height)
    oledShow()
    x += step
  return True

def showSleep(secs=60,text=None,inThread=False):
  global nl, STOP, STOPPED
  global MyTypes
  try:
    Display = MyTypes['display']
    ye = y = nl
    if text:
      display(text)
      ye += LF
    if Display['lib'] and Display['enabled'] and Display['conf']['use']:
      ProgressBar(0,ye-3,128,LF-3,secs,0x004400)
      nl = y
      rectangle(0,y,128,ye-y+LF,0)
      oledShow()
    else: raise ValueError()
  except: sleep_ms(int(secs*1000))
  if inThread:
    STOP = False
    STOPPED = True
    _thread.exit()
  return True

def DisplayInThread(secs=60, text=None):
  global STOP, STOPPED, Threading
  if not Threading:
    STOPPED=True
    raise ValueError('No threading')
  STOP = False; STOPPED = False
  try:
    _thread.start_new_thread(showSleep,(secs,text,True))
  except Exception as e:
    STOPPED=True
    Threading = False
    raise ValueError("threading failed: %s" % e)
  sleep_ms(1000)
# end of display routines

# check/set power on device
def PinPower(atype=None,on=None,debug=False):
  global MyConfiguration
  if not atype: return False
  if type(atype) is list:
    for item in atype:
      PinPower(atype=item, on=on, debug=debug)
  else:
    abus = Type2Bus(atype)
    try:
      if not MyConfiguration[abus][atype]['use']: return None
      pins = MyConfiguration[abus][atype]['pins']
      len(pins) == 3
      if debug: print("Use %s power pins %s, on=%s" % (atype,pins,str(on)))
    except:
      if debug: print("Power pin %s missing" % atype)
      return None
    if not type(pins[2]) is str: return None
    from machine import Pin
    pin = Pin(pins[2], mode=Pin.OUT)
    if on == None: return pin.value()
    elif on:
      if pin.value(): return True
      if debug: print("Activate %s chan (Tx,Rx,Pwr)=%s: " % (abus,str(pins)))
      pin.value(1); sleep_ms(200); return False
    elif pin.value():
      try:
        # if true powercycle the bus. with GPS power cycling costs delays; dflt false
        if not MyConfiguration['power'][abus]: return True
      except: pass
      if debug: print("Deactivate %s chan (Tx,Rx,Pwr)=%s: " % (abus,str(pins)))
      pin.value(0); return True
    else: return False

def PinPowerRts(atype,prev,rts=None,debug=False):
  PinPower(atype,on=prev,debug=debug)
  return rts

## I2C devices
## DISPLAY
# tiny display Adafruit SSD1306 128 X 64 oled driver
def initDisplay(debug=False):
  global MyTypes, wokeUp
  atype = 'display'
  if not MyTypes: getMyConfig()
  try: Display = MyTypes[atype]
  except: return False
  abus = Type2Bus(atype)
  if Display['lib']: return True
  try:
    if not Display[abus]: return False
    if not Display['conf']['name'][:3] in ['SSD',]: return False
  except: return False
  if PinPower(atype=atype,on=True, debug=debug) == None: return False
  if not Display['conf']['use']: return True  # initialize only once
  Display['enable'] = False
  try:
      if 'i2c' in Display.keys():
        import SSD1306 as DISPLAY
        width = 128; height = 64  # display sizes
        # display may flicker on reload
        Display['lib'] = DISPLAY.SSD1306_I2C(width,height,
                             Display['i2c'], addr=Display['conf']['address'])
        if debug:
          print('Oled %s: (SDA,SCL,Pwr)=%s pwr is %s' % (Display['conf']['name'],str(Display['conf']['pins'][:3]),PinPower('display')))
      #elif 'spi' in Display.keys(): # for fast display This needs rework for I2C style
      #  global spi, spiPINS
      #  try:
      #    from Config import S_CLKI, S_MOSI, S_MISO  # SPI pins config
      #  except:
      #    S_SCKI = 'P10'; S_MOSI = 'P11'; S_MISO = 'P14'  # SPI defaults
      #  if not len(spi): from machine import SPI
      #  try:
      #    from Config import S_DC, S_RES, S_CS      # GPIO SSD pins
      #  except:
      #    S_DC = 'P5'; S_RES = 'P6'; S_CS = 'P7'    # SSD defaults
      #  nr = SPIdevs(spiPINs,(S_DC,S_CS,S_RES,S_MOSI,S_CLKI))
      #  if spi[nr] == None:
      #    spi[nr] = SPI(nr,SPI.MASTER, baudrate=100000,
      #                  pins=(S_CLKI, S_MOSI, S_MISO))
      #  Display['lib'] = DISPLAY.SSD1306_SPI(width,height,spi[nr],
      #                  S_DC, S_RES, S_CS)
      #  if debug: print('Oled SPI %d: ' % nr + 'DC ~> %s, CS ~> %s, RES ~> %s,
      #                   MOSI/D1 ~> %s,
      #                   CLK/D0 ~> %s ' % spiPINs[nr] + 'MISO ~> %s' % S_MISO)
      else:
        Display['lib'] = None; Display['conf']['use'] = False
        if not wokeUp: print("No SSD display or bus found")
      if Display['lib']:
        Display['enabled'] = True
        Display['lib'].fill(1); oledShow(); sleep_ms(200)
        Display['lib'].fill(0); oledShow()
  except Exception as e:
      Display['lib'] = None
      print('Oled display failure: %s' % e)
      return False
  return True

## METEO
# oled on SPI creates I2C bus errors
#  display('BME280 -> OFF', (0,0),True)

# start meteo sensor
def initMeteo(debug=False):
  global MyTypes, MyConfiguration, wokeUp, MyConfig
  if not MyTypes: getMyConfig()
  try:
    atype = 'meteo'
    Meteo = MyTypes[atype]
    abus = Type2Bus(atype)
    if Meteo['lib']: return True
    if not Meteo[abus]: return False
    if not Meteo['conf']['name'][:3] in ['BME','SHT']: return False
    if not Meteo['conf']['use']: return False
  except: return False
  try:
    if Meteo['lib']: return True
  except: pass
  if debug: print("Try %s" % Meteo['conf']['name'])
  Meteo['enabled'] = False
  try: # get lib
    if Meteo['conf']['name'][:3] == 'BME':
      if Meteo['conf']['name'] == 'BME280':
        import BME280 as BME
        Meteo['lib'] = BME.BME_I2C(Meteo[abus], address=Meteo['conf']['address'], debug=debug, calibrate=MyConfiguration['calibrate'])
      elif Meteo['conf']['name'] == 'BME680':
        import BME_I2C as BME
        Meteo['lib'] = BME.BME_I2C(Meteo[abus], address=Meteo['conf']['address'], debug=debug, calibrate=MyConfiguration['calibrate'])
        if not 'gas_base' in Meteo['conf'].keys():
          global MyConfig
          try:
            from Config import M_gBase
            Meteo['conf']['gas_base'] = int(M_gBase)
            MyConfig.dirty = True
          except: pass
        if 'gas_base' in Meteo['conf'].keys():
          Meteo['lib'].gas_base =  Meteo['conf']['gas_base']
        if not Meteo['lib'].gas_base:
          display('AQI wakeup')
          Meteo['lib'].AQI # first time can take a while
          Meteo['conf']['gas_base'] = Meteo['lib'].gas_base
          MyConfig.dirty = True
        display("Gas base: %0.1f" % Meteo['lib'].gas_base)
        # Meteo['lib'].sea_level_pressure = 1011.25
      else: return False
    elif Meteo['conf']['name'][:3] == 'SHT':
      import Adafruit_SHT31 as SHT
      Meteo['lib'] = SHT.SHT31(address=Meteo['address'], i2c=Meteo[abus], calibrate=MyConfiguration['calibrate'])
    else: # DHT serie deprecated
      if LED: LED.blink(5,0.3,0xff0000,l=True,force=True)
      raise ValueError("Unknown meteo %s type" % meteo)
    Meteo['enabled'] = True
    if debug:
      print('Meteo %s: (SDA,SCL,Pwr)=%s, Pwr %s' % (Meteo['conf']['name'],Meteo['conf']['pins'][:3], PinPower(atype=atype)))
  except Exception as e:
    Meteo['conf']['use'] = False
    display("meteo %s failure" % Meteo['conf']['name'], (0,0), clear=True)
    print(e)
  if (not Meteo['enabled']) or (not Meteo['conf']['use']):
    if not wokeUp: display("No meteo in use")
    return False
  return True

TEMP = const(0)
HUM  = const(1)
PRES = const(2)
GAS  = const(3)
AQI  = const(4)
def DoMeteo(debug=False):
  global MyTypes, LED
  global nl, LF
  mData = [None,None,None,None,None]
  if not MyTypes:
    getMyConfig(debug=debug)
    initMeteo(debug=debug)
  atype = 'meteo'
  try: Meteo = MyTypes[atype]
  except: return mData

  def convertFloat(val):
    return (0 if val is None else float(val))

  if Meteo['lib'] == None: initMeteo(debug=debug)
  if (not Meteo['conf']['use']) or (not Meteo['enabled']): return mData

  # Measure BME280/680: temp oC, rel hum %, pres pHa, gas Ohm, aqi %
  if LED: LED.blink(3,0.1,0x002200,l=False); prev = 1
  try:
    prev = PinPower(atype=atype,on=True, debug=debug)
    if (Meteo['conf']['name'] == 'BME680') and (not Meteo['lib'].gas_base): # BME680
      display("AQI base: wait"); nl -= LF
    #Meteo['i2c'].init(nr, pins=Meteo['conf']['pins']) # SPI oled causes bus errors
    #sleep_ms(100)
    mData = []
    for item in range(0,5):
        mData.append(0)
        for cnt in range(0,5): # try 5 times to avoid null reads
            try:
                if item == TEMP: # string '20.12'
                    mData[TEMP] = convertFloat(Meteo['lib'].temperature)
                elif item == HUM: # string '25'
                    mData[HUM] = convertFloat(Meteo['lib'].humidity)
                elif Meteo['conf']['name'][:3] != 'BME': break
                elif item == PRES: # string '1021'
                    mData[PRES] = convertFloat(Meteo['lib'].pressure)
                elif Meteo['conf']['name'] == 'BME680':
                    if item == GAS: mData[GAS] = convertFloat(Meteo['lib'].gas)
                    elif item == AQI:
                        mData[AQI] = round(convertFloat(Meteo['lib'].AQI),1)
                        if not 'gas_base' in Meteo.keys():
                            Meteo['gas_base'] = Meteo['lib'].gas_base
                break
            except OSError as e: # I2C bus error, try to recover
                print("OSerror %s on data nr %d" % (e,item))
                Meteo['i2c'].init(I2C.MASTER, pins=Meteo['conf']['pins'])
                if LED: LED.blink(1,0.1,0xff6c00,l=False,force=True)
    # work around if device corrupts the I2C bus
    # Meteo['i2c'].init(I2C.MASTER, pins=Meteo['conf']['pins'])
    sleep_ms(500)
    rectangle(0,nl,128,LF,0)
  except Exception as e:
    display("%s ERROR: " % Meteo['conf']['name'])
    print(e)
    if LED: LED.blink(5,0.1,0xff00ff,l=True,force=True)
    return [None,None,None,None,None]

  if LED: LED.off
  # display results
  nl += 6  # oled spacing
  if Meteo['conf']['name'] == 'BME680':
    title = "  C hum% pHa"
    values = "% 2.1f %2d %4d" % (round(mData[TEMP],1),round(mData[HUM]),round(mData[PRES]))
    if mData[AQI] > 0:
      title += ' AQI'
      values += " %2d" % round(mData[AQI])
  elif Meteo['conf']['name'] == 'BME280':
    title = "    C hum%  pHa"
    values = "% 3.1f  % 3d % 4d" % (round(mData[TEMP],1),round(mData[HUM]),round(mData[PRES]))
  else:
    title = "    C hum%"
    values = "% 3.1f  % 3d" % (round(mData[TEMP],1),round(mData[HUM]))
  display(title)
  display("o",(12,-5),prt=False)
  display(values)
  if not prev: PinPower(atype=atype,on=prev,debug=debug)
  return mData # temp, hum, pres, gas, aqi

# UART devices
## DUST
def initDust(debug=False):
  global MyConfig, MyConfiguration, wokeUp
  global MyTypes
  if not MyTypes: getMyConfig()
  atype = 'dust'; abus = Type2Bus(atype)
  try: Dust = MyTypes[atype]
  except: return False

  try:
    if Dust['lib']: return True
    if not Dust[abus]: return False
    if not Dust['conf']['name'][:3] in ['SDS','PMS','SPS']: return False
  except: return False
  try: sample = MyConfiguration['interval']['sample']
  except: sample = 60
  Dust['enabled'] = False; Dust['cnt'] = True
  if Dust['conf']['use']:
    # initialize dust: import dust library module
    try:
      if Dust['conf']['name'][:3] == 'SDS':    # Nova
        from SDS011 import SDS011 as senseDust
        Dust['cnt'] = False
      elif Dust['conf']['name'][:3] == 'SPS':  # Sensirion
        from SPS30 import SPS30 as senseDust
      elif Dust['conf']['name'][:3] == 'PMS':  # Plantower
        from PMSx003 import PMSx003 as senseDust
      else:
        if LED: LED.blink(5,0.3,0xff0000,l=True,force=True)
        raise ValueError("Unknown dust sensor")
      for item in ['Dext','explicit']:
        value = None # dflt do show PM cnt
        try:
          value = MyConfiguration[item]
          break
        except:
          try:
            if item == 'Dext': from Config import Dext as value
            elif item == 'explicit': from Config import Dexplicit as value
            else: continue
            MyConfig.dump('explicit',value)
            MyConfiguration['explicit'] = value
            break
          except: pass
      if value == None: # dflt
        MyConfiguration['explicit'] = False
        MyConfig.dump('explicit',False)
      # #pcs=range(PM0.3-PM) + average grain size, True #pcs>PM
      if Dust[abus] == None: return False
      Dust['lib'] = senseDust(port=Dust[abus], debug=debug, sample=sample, interval=0, pins=Dust['conf']['pins'][:2], calibrate=MyConfiguration['calibrate'], explicit=MyConfiguration['explicit'])
      if debug:
        print('Dust %s: (Tx,Rx,Pwr)=%s, Pwr %s' % (Dust['conf']['name'],Dust['conf']['pins'][:3], PinPower(atype=atype)))
    except Exception as e:
      display("%s failure" % Dust['conf']['name'], (0,0), clear=True)
      print(e)
      Dust['conf']['name'] = ''
    if debug: print('dust: %s' % Dust['conf']['name'])
  elif not wokeUp: print("No dust in use")
  if Dust['lib']: Dust['enabled'] = True
  return Dust['conf']['use']

# PM weights
PM1 = const(0)
PM25 = const(1)
PM10 = const(2)
# PM count >= size
PM03c = const(3)
PM05c = const(4)
PM1c = const(5)
PM25c = const(6)
PM5c = const(7)
PM10c = const(8)
def DoDust(debug=False):
  global nl, STOP, STOPPED, lastGPS
  global MyConfiguration, MyTypes
  dData = {}; rData = [None,None,None]
  atype = 'dust'
  if not MyTypes:
    getMyConfig(debug=debug)
    initDust(debug=debug)
  try: Dust = MyTypes[atype]
  except: return rData


  if Dust['lib'] == None: initDust(debug=debug)
  if (not Dust['conf']['use']) or (not Dust['enabled']): return rData

  display('PM sensing',(0,0),clear=True,prt=False)
  prev = False
  if Dust['enabled']:
    prev = PinPower(atype=atype,on=True, debug=debug)
    if not prev:
        sleep_ms(1000)
        Dust['lib'].Standby()
    if Dust['lib'].mode != Dust['lib'].NORMAL:
      Dust['lib'].Normal()
      if not showSleep(secs=15,text='starting up fan'):
        display('stopped SENSING', (0,0), clear=True)
        if LED: LED.blink(5,0.3,0xff0000,l=True,force=True)
        return rData
      else:
        if lastGPS[LON]:
          display("G:%.4f/%.4f" % (lastGPS[LAT],lastGPS[LON]))
        display('measure PM')
  if Dust['enabled']:
    sampleT = MyConfiguration['interval']['sample']
    if LED: LED.blink(3,0.1,0x005500,l=False)
    # display('%d sec sample' % sampleT,prt=False)
    try:
      STOPPED = False
      try:
        DisplayInThread(sampleT,'%d sec sample' % sampleT)
      except Exception as e:
        STOPPED = True
        display('%d sec sample' % sampleT)
        print("Dust: %s" % str(e))
      dData = Dust['lib'].getData()
      for cnt in range(10):
        if STOPPED: break
        STOP = True
        print('waiting for thread')
        if LED: LED.blink(5,0.2,0x175826,l=False)
        else: sleep_ms(1000)
        sleep_ms(1000)
      STOP = False
    except Exception as e:
      display("%s ERROR" % Dust['conf']['name'])
      print(e)
      if LED: LED.blink(3,0.1,0xff0000)
      dData = {}
    if LED: LED.blink(3,0.1,0x00ff00)
    try:
      if MyConfiguration['power'][Type2Bus(atype)]:
        PinPower(atype=atype,on=prev,debug=debug)
    except: pass

  if len(dData):
    for k in dData.keys():
        if dData[k] == None: dData[k] = 0
    try:
      if 'pm1' in dData.keys():   #  and dData['pm1'] > 0:
        display(" PM1 PM2.5 PM10", (0,0), clear=True)
        display("% 2.1f % 5.1f% 5.1f" % (dData['pm1'],dData['pm25'],dData['pm10']))
      else:
        display("ug/m3 PM2.5 PM10", (0,0), clear=True)
        display("     % 5.1f % 5.1f" % (dData['pm25'],dData['pm10']))
        dData['pm1'] = 0
    except:
      dData = {}
  if (not dData) or (not len(dData)):
    display("No PM values")
    if LED: LED.blink(5,0.1,0xff0000,l=True,force=True)
  else:
    rData = []
    for k in ['pm1','pm25','pm10']:
      rData.append(round(dData[k],1) if k in dData.keys() else None)

    if Dust['cnt']:
      cnttypes = ['03','05','1','25','5','10']
      if Dust['conf']['name'][:3] == 'SPS': cnttypes[4] = '4'
      for k in cnttypes:
        if 'pm'+k+'_cnt' in dData.keys():
            rData.append(round(dData['pm'+k+'_cnt'],1))
        else: rData.append(0.0) # None
      if not Dust['conf']['explicit']:  # PM0.3 < # pcs <PMi
        rData[3] = round(dData['grain'],2) # PM0.3 overwritten
        # print('pm grain: %0.2f' % dData['grain'])
    if LED: LED.off
  return rData

## GPS
# initialize GPS: GPS config tuple (LAT,LON,ALT)
def initGPS(debug=False):
  global lastGPS
  global MyTypes
  if not MyTypes: getMyConfig()
  atype = 'gps'; abus = Type2Bus(atype)
  try: Gps = MyTypes[atype]
  except: return False

  try:
    if Gps['lib']: return True
    if not Gps[abus]: return False
    if (not Gps['conf']['use']) and not wokeUp:
      display('No GPS'); return False
    if not Gps['conf']['name'][:3] in ['GPS','NEO',]: return False
  except: return False

  Gps['enabled'] = False; Gps['lib'] = None; Gps['rtc'] = None
  prev = PinPower(atype=atype,on=True,debug=debug)
  try:
      import GPS_dexter as GPS
      # may cause 1 minute delay
      display("init GPS wait")
      Gps['lib'] = GPS.GROVEGPS(port=Gps[abus],baud=9600,debug=debug,pins=Gps['conf']['pins'][:2])
      if debug:
        print('GPS %s: (Tx,Rx,Pwr)=%s, Pwr %s' % (Gps['conf']['name'],Gps['conf']['pins'][:3], PinPower(atype='gps')))
      Gps['enabled'] = True
      # myGPS = DoGPS(debug=debug)
      # if myGPS and myGPS[0]: lastGPS = myGPS[0:]
      # Gps['rtc'] = None
  except Exception as e:
      display('GPS failure', (0,0), clear=True)
      print(e)
      Gps['enabled'] = False; Gps[abus].ser.deinit(); Gps['lib'] = None
  PinPower(atype=atype,on=prev,debug=debug)
  return Gps['enabled']

# returns distance in meters between two GPS coodinates
# hypothetical sphere radius 6372795 meter
# courtesy of TinyGPS and Maarten Lamers
# should return 208 meter 5 decimals is diff of 11 meter
# GPSdistance((51.419563,6.14741),(51.420473,6.144795))
def GPSdistance(gps1,gps2):
  global LAT, LON
  from math import sin, cos, radians, pow, sqrt, atan2
  delta = radians(gps1[LON]-gps2[LON])
  sdlon = sin(delta)
  cdlon = cos(delta)
  lat = radians(gps1[LAT])
  slat1 = sin(lat); clat1 = cos(lat)
  lat = radians(gps2[LAT])
  slat2 = sin(lat); clat2 = cos(lat)

  delta = pow((clat1 * slat2) - (slat1 * clat2 * cdlon),2)
  delta += pow(clat2 * sdlon,2)
  delta = sqrt(delta)
  denom = (slat1 * slat2) + (clat1 * clat2 * cdlon)
  return int(round(6372795 * atan2(delta, denom)))

def LocUpdate(debug=False):
  global MyConfiguration, MyConfig
  global lastGPS  # thisGPS = start location
  try:
    myGPS = DoGPS(debug=debug)
    if (not myGPS) or (not myGPS[0]):
      return None
    if GPSdistance(myGPS,lastGPS) <= 50.0:
      return lastGPS[0:]
    if not MyConfiguration['thisGPS'][1]:
      MyConfiguration['thisGPS'] = myGPS[0:]
      MyConfig.dump('thisGPS',MyConfiguration['thisGPS'])
    lastGPS = myGPS[0:]
    saveGPS(lastGPS) # save in nvram
  except: pass
  return lastGPS[0:]

# TO DO: next should go in a thread
def DoGPS(debug=False):
  global MyConfiguration, MyConfig, MyTypes
  global lastGPS
  if not MyTypes:
    getMyConfig(debug=debug)
  atype = 'gps'; abus = Type2Bus(atype)
  try: Gps = MyTypes[atype]
  except: return None

  if not MyTypes: getMyConfig(debug=debug)
  interval = MyConfiguration['interval']
  from time import localtime, timezone
  try:
    if ticks() < nvs_get('gps_next'):
      if debug: print("No GPS update")
      rts = getSavedGPS()
      if rts[0]: return rts
      else: return None
  except: nvs_set('gps_next',0)

  prev = PinPower(atype=atype,on=True,debug=debug)
  if not Gps['lib']: initGPS(debug=False)
  if not Gps['lib'] or not Gps['enabled']:
    return PinPowerRts(atype,prev,debug=debug)
  if debug: print("Try date/RTC update")
  myGPS = [0.0,0.0,0.0]; prev = None
  fixate = None
  try: fixate = nvs_get(atype)
  except: pass
  if fixate == None:
    nvs_set(atype,-1); fixate = -1
  myGPS = [0,0,0]
  try:
    myTime = False
    if Gps['lib'].quality < 1:
      if fixate == None: display('wait GPS fixate')
      else: print('wait GPS fixate') # maybe 10 minutes
    for cnt in range(1,5):
      Gps['lib'].read(debug=debug)
      if Gps['lib'].quality > 0: break
    if Gps['lib'].satellites > 3:
      prev = time(); Gps['lib'].UpdateRTC()
      if prev != time(): myTime = True
      print("%d GPS sats, time set" % Gps['lib'].satellites)
    else:
      if fixate < 0: display('no GPS fixate')
      else: print('no GPS fixate')
      # return PinPowerRts(atype,prev,rts=[0,0,0],debug=debug)
      return myGPS # leave power on
    if myTime: # RTC is adjusted
      now = localtime()
      if 3 < now[1] < 11: timezone(7200) # a very simple MET DST
      else: timezone(3600)
      display('%d/%d/%d %s' % (now[0],now[1],now[2],('mo','tu','we','th','fr','sa','su')[now[6]]))
      display('time %02d:%02d:%02d' % (now[3],now[4],now[5]))
    if Gps['lib'].longitude > 0:
      if debug: print("Update GPS coordinates")
      myGPS[LON] = round(float(Gps['lib'].longitude),5)
      myGPS[LAT] = round(float(Gps['lib'].latitude),5)
      myGPS[ALT] = round(float(Gps['lib'].altitude),1)
      if (MyConfiguration['thisGPS'][0] < 0.1) and (myGPS[0] > 0.1):
        MyConfiguration['thisGPS'] = myGPS[0:]
        MyConfig.dump('thisGPS', MyConfiguration['thisGPS'])
      lastGPS = myGPS[0:]; saveGPS(lastGPS)
      fixate = True; nvs_set(atype,Gps['lib'].satellites)
    if debug and myGPS[0]:
      print("GPS: lon %.5f, lat %.5f, alt %.2f" % (myGPS[LON],myGPS[LAT],myGPS[ALT]))
  except:
    Gps['enabled'] = False; Gps['lib'].ser.deinit(); Gps['lib'] = None
    display('GPS error')
    return PinPowerRts(atype,False,rts=myGPS,debug=debug)
  nvs_set('gps_next',ticks()+interval[atype])
  # Pwr on till fixate
  if MyConfiguration['power']['ttl'] and (fixate > 0): prev = False
  return PinPowerRts(atype,prev,rts=myGPS, debug=debug)

## Pin devices
def initAccu():
  global MyDevices, MyConfig
  if not MyConfig: initConfig()
  if not 'accu' in MyDevices.keys(): return (getVoltage()[0] != 0)
  else: return True

def DoAccu(debug=False):
  if not 'accu' in MyDevices.keys(): initAccu()
  try:
    if MyDevices['accu']: return getVoltage()[1]
  except: return 0

## LoRa
# called via TTN response
# TO DO: make the remote control survive a reboot
def CallBack(port,what):
  global HALT
  global MyConfiguration, MyConfig
  global MyTypes
  def ChangeConfig(atype,key,value):
    global MyConfiguration, MyConfig
    try:
      MyConfiguration[atype][key] = value
      MyConfig.dump(atype=atype,avalue=MyConfiguration[atype])
      MyConfig.store
    except: return True
    return True

  try:
    if not what: return True
    if len(what) < 2:
      SendEvent(event=2,value=what) # ack
      if what == b'?':
        nvs_set('info_next',0)
        SendMeta(); return True
      elif what == b'O':
        if Display['conf']['use']:
          Display['lib'].poweroff()
          ChangeConfig('power','display',False)
      elif what == b'o':
        if Display['conf']['use']:
          Display['lib'].poweron()
          ChangeConfig('power','display',None)
      elif what == b'S':
        ChangeConfig('interval','sleep',True)
      elif what == b's':
        ChangeConfig('interval','sleep',False)
      elif what == b'd':
        if MyTypes['dust']['conf']['use']:
          ChangeConfig('dust','raw',True)
          MyTypes['dust']['raw'] = True # try: MyTypes['dust']['lib'].gase_base = None
      elif what == b'D':
        if MyTypes['dust']['conf']['use']:
          MyTypes['dust']['raw'] = False # try: MyTypes['dust']['lib'].gase_base = None
      elif what == b'm':
        if MyTypes['meteo']['conf']['use']: MyTypes['meteo']['raw'] = True
      elif what == b'M':
        if MyTypes['meteo']['conf']['use']: MyTypes['meteo']['raw'] = False
      elif what == b'S': HALT = True
      elif what == b'#':  # send partical cnt
        if MyTypes['dust']['conf']['name'][:3] != 'SDS': MyTypes['dust']['cnt'] = True
      elif what == b'w': # send partical weight
        MyTypes['dust']['cnt'] = False
      elif what == b'W': # enable WiFi
        return setWiFi(reset=True)
      else: return

    cmd = None; value = None
    try:
      cmd, value = struct.unpack('>BH',what)
      SendEvent(event=2,value=cmd) # ack
    except:
      return False
    if cmd == b'i':  # interval
      if value*60 > MyConfiguration['interval']['sample']:
        value = value*60 - MyConfiguration['interval']['sample']
      ChangeConfig('interval','interval',value)
  except: pass
  return

# LoRa setup
def initNetwork(debug=False):
  global MyTypes, LED, Dprt, wokeUp
  if not MyTypes: getMyConfig()
  if not 'network' in MyTypes.keys(): getNetConfig(debug=debug)
  try: Network = MyTypes['network']
  except: return False
  if Network['enabled'] and Network['lib']: return True

  if not Network['name'] in 'TTN': return False
  Network['enabled'] = False
  try:
    from lora import LORA
    Network['lib'] = LORA()
    # resume is handled by driver
    if not Network['lib'].connect(method=Network['method'], ports=(len(Dprt)+1), callback=CallBack, myLED=LED, debug=debug):
      display("NO LoRaWan")
      Network['lib'] = None
      return False
  except Exception as e:
    print("Error: %s" % e)
    return None
  Network['enabled'] = True
  if not wokeUp:
    display("Using LoRaWan")
    sleep_ms(5*1000)
  return True

# denote a null value with all ones
# denote which sensor values present in data package
def DoPack(dData,mData,gps=None,wData=[],aData=None,debug=False):
  global MyTypes
  t = 0
  for d in dData, mData:
    for i in range(1,len(d)):
      if d[i] == None: d[i] = 0
  if mData[0] == None: mData[0] = 0
  if dData[PM1] == None: # PM2.5 PM10 case
    d = struct.pack('>HH',int(dData[PM25]*10),int(dData[PM10]*10))
    # print("PM 2.5, 10 cnt: ", dData[1:3])
  else:
    d = struct.pack('>HHH',int(dData[PM1]*10),int(dData[PM25]*10),int(dData[PM10]*10))
    t += 1
  if ('cnt' in MyTypes['dust'].keys()) and MyTypes['dust']['cnt']: # add counts
    # defeat: Plantower PM5c == Sensirion PM4c: to do: set flag in PM5c
    flg = 0x8000 if MyTypes['dust']['conf']['name'][:3] in ['SPS',] else 0x0
    try:
      if MyTypes['dust']['conf']['explicit']:
        # 9 decrementing bytes, may change this
        d += struct.pack('>HHHHHH',
          int(dData[PM10c]*10+0.5),
          int(dData[PM05c]*10+0.5),
          int(dData[PM1c]*10+0.5),
          int(dData[PM25c]*10+0.5),
          int(dData[PM5c]*10+0.5)|flg,
          int(dData[PM03c]*10+0.5))
      else:
        # 9 bytes, ranges, average grain size  >0.30*100
        d += struct.pack('>HHHHHH',
          int((dData[PM10c]-dData[PM5c])*10+0.5)|0x8000,
          int(dData[PM05c]*10+0.5),
          int((dData[PM1c]-dData[PM05c])*10+0.5),
          int((dData[PM25c]-dData[PM1c])*10+0.5),
          int((dData[PM5c]-dData[PM25c])*10+0.5)|flg,
          int(dData[PM03c]*100+0.5))
    except:
      d += struct.pack('>HHHHHH',0,0,0,0,0,0)
      display("Error dust fan",clear=True)
      if LED: LED.blink(5,0.2,0xFF0000,l=False,force=True)
    t += 2
  m = struct.pack('>HHH',int(mData[TEMP]*10+300),int(mData[HUM]*10),int(mData[PRES]))
  if len(mData) > 3:
    m += struct.pack('>HH',int(round(mData[GAS]/100.0)),int(mData[AQI]*10))
    t += 4
  if (type(gps) is list) and (gps[LAT] > 0.01):
    l = struct.pack('>lll', int(round(gps[LAT]*100000)),int(round(gps[LON]*100000)),int(round(gps[ALT]*10)))
    t += 8
  else: l = ''
  w = ''
  if len(wData) == 2: # wind = [speed,direction]
    wData[1] = (int(round(wData[1])+2))%360
    w = struct.pack('>H', (int(round(wData[0]*10.0))<<7) | ((wData[1]+1)/3))
    t += 16
  a = ''
  if aData: # accu
    a = struct.pack('>B', int(round(aData*10.0)))
    t += 32
  # return d+m+l+w+a
  t = struct.pack('>B', t | 0x80) # flag the package
  return t+d+m+l+w+a # flag the package

def SendEvent(port=Iprt, event=None, value=0):
  global LED, MyTypes, __version__
  if not event: return True
  try:
    version = int(__version__[0])*10+int(__version__[2])
    if LED: LED.blink(1,0.2,0xFF0000,l=True) # red
    data = struct.pack('>BBBB',version, 0, value,event)
    MyTypes['network']['lib'].send(data,port=port)
    if LED: LED.blink(1,0.2,0x0054FF,l=False) # blue
  except:
    if LED: LED.blink(1,0.2,0xFF00AA,l=False) # purple
    return False
  return True

# send kit info to LoRaWan
def SendMeta(port=Iprt):
  global LED, MyTypes, MyConfiguration, __version__
  if ticks() < nvs_get('info_next'): return False
  meteo = ['','DHT11','DHT22','BME280','BME680','SHT31','WASP'] # max 16
  dust = ['None','PPD42NS','SDS011','PMSx003','SPS30']          # max 8
  thisGPS = [0,0,0]
  try: thisGPS = MyConfiguration['thisGPS']
  except: pass
  sense = 0
  try:
    version = int(__version__[0])*10+int(__version__[2])
    if MyTypes['network']['lib'] == None: raise ValueError()
    else:
      print("meteo: %s, dust: %s" %(MyTypes['meteo']['conf']['name'],MyTypes['dust']['conf']['name']))
      for atype in ['meteo','dust','gps']:
        if not atype in MyTypes.keys():
          print("No %s sensor configured!" % atype); MyTypes[atype] = {'enabled': False }
        if not MyTypes[atype]['enabled']: continue
        if atype == 'meteo':
          sense |= ((meteo.index(MyTypes['meteo']['conf']['name'])&0xf)<<4)
        elif atype == 'dust':
          sense |= (dust.index(MyTypes['dust']['conf']['name'])&0x7)
        elif atype == 'gps':
          sense |= 0x8
      LocUpdate()
      data = struct.pack('>BBlll',version,sense, int(thisGPS[LAT]*100000),int(thisGPS[LON]*100000),int(thisGPS[ALT]*10))

    MyTypes['network']['lib'].send(data,port=port)
    display("Sent Meta info")
    if LED: LED.blink(1,0.2,0x0054FF,l=False) # blue
  except:
    if LED: LED.blink(1,0.2,0xFF00AA,l=False) # purple
    return False
  nvs_set('info_next',ticks() + MyConfiguration['interval']['info'])
  return True

# startup info
def initDevices(debug=False):
  global MyTypes, wokeUp
  global STOP
  if not MyTypes: getMyConfig()

  try:
    # connect I2C devices
    initDisplay(debug=debug)

    try:
      if initDust(debug=debug):
        if not wokeUp:
          if MyTypes['dust']['cnt']: display("PM pcs:" + MyTypes['dust']['conf']['name'])
          else: display("PM   : " + MyTypes['dust']['conf']['name'])
      else: raise ValueError()
    except: display("No dust sensor")

    try:
      if initMeteo(debug=debug):
        if not wokeUp: display("meteo: " +  MyTypes['meteo']['conf']['name'])
      else: raise ValueError()
    except: display("No meteo sensor")

    # sleep_ms(15000)
    if not wokeUp:
      gps = DoGPS(debug=debug)
      if not gps: display("No GPS")
      elif gps[0]:
         global lastGPS
         display('G:%.4f/%.4f' % (lastGPS[LAT],lastGPS[LON]))

    try:
      net = initNetwork(debug=debug)
      if net == None:
        raise ValueError("LoRa keys")
      elif net:
        if not wokeUp:
          display('network: %s' % MyTypes['network']['name'])
      else: raise ValueError("init network")
    except Exception as e: raise ValueError(e)

  except Exception as e:
    # pycom.rgbled(0xFF0000)
    display("ERROR %s" % e)
    return False

  if debug and not wokeUp:
    for item in MyTypes.keys():
      print("MyDevices[bus] ", end='')
      PrintDict(MyTypes[item],'MyTypes[%s]' % item)
  return True

def getMyConfig(debug=False):
  global MyConfig, MyTypes
  #global MyDevices, MyConfiguration

  ## INIT config
  initConfig(debug=False)
  getPinsConfig(debug=False)
  getBusConfig(debug=debug)
  if debug: PrintDict(MyDevices,'MyDevices:')
  getNetConfig(debug=False)
  getGlobals(debug=False)
  ## CONF archive all if dirty
  if MyConfig.dirty:
    MyConfig.store
    MyConfiguration = MyConfig.getConfig()
    if LED: LED.blink(5,0.3,0x00ff00,l=False)
  #if debug:
  #  PrintDict(MyConfiguration,'MyConfiguration: ')
  #  PrintDict(MyDevices,'MyDevices: ')

  if debug:
    for item in MyTypes.keys():
      print("MyDevices[bus] ", end='')
      PrintDict(MyTypes[item],'MyTypes[%s]' % item)

########   main loop
def runMe(debug=False):
  global MyConfiguration, MyTypes, wlan
  global wokeUp    # power cycle
  global Alarm     # watch dog

  if not MyTypes:
    getMyConfig(debug=debug) 
    MyMark(1) # init WatchDogTimer
    # initialize devices and show initial info
    if not initDevices(debug=debug): # initNet does LoRa nvram restore
      print("FATAL ERROR")
      if LED: LED.blink(25,0.2,0xFF0000,l=True,force=True)
      return False
    if debug:
      global MyConfig
      if MyConfig.dirty: print("Configuration is dirty")

  # short cuts
  interval = MyConfiguration['interval']
  Power = MyConfiguration['power']
  Dust = None
  try: Dust = MyTypes['dust']
  except: pass
  Network = None
  try: Network = MyTypes['network']
  except: pass
  Display = None
  try: Display = MyTypes['display']
  except: pass

  if not wokeUp: # cold restart
    import os
    display('%s' % PyCom, (0,0),clear=True)
    display("MySense %s" % __version__[:8], (0,0), clear=True)
    display("s/n " + getSN())
    if not wokeUp:
      if deepsleepMode(): display("energy saving")
      else: display("active mode")
    display("probes: %ds/%dm" % (interval['sample'], interval['interval']/60))
  elif wokeUp and LED:
    if ('led' in Power.keys()) and Power['led']: LED.disable

  while True: # LOOP forever
    MyMark(10)
    if Alarm:  # event on empty accu
      if LED: LED.blink(3,0.1,0xF99B15,l=False,force=True)
      try:
        SendEvent(port=Iprt, event=Alarm[0], value=int(Alarm[1])) # send event
      except: pass
      Alarm = False
    elif LED: LED.blink(1,0.2,0x00FF00,l=False,force=True)
    toSleep = ticks()
    try:
      if (toSleep+interval['sample']+30) > nvs_get('gps'):
        PinPower(atype='gps',on=True, debug=debug) # wakeup GPS dev
    except: pass
    setWiFi(debug=debug)
    SendMeta()
    # Power management ttl is done by DoXYZ()
    try:
      if Display['enabled'] and Power['display']: Display['lib'].poweron()
    except: pass

    MyMark(20)
    try:
      dData = DoDust(debug=debug)
      if Dust and Dust['conf']['use']:
        Dust['lib'].Standby()   # switch off laser and fan
        PinPower(atype='dust',on=False,debug=debug)
    except Exception as e: print("dData except: %s" % str(e))

    MyMark(30)
    try: mData = DoMeteo(debug=debug)
    except Exception as e: print("mData except: %s" % str(e))

    MyMark(40)
    try: aData = {}; aData = DoAccu(debug=debug)
    except Exception as e: print("aData except: %s" % str(e))

    MyMark(50)
    # Send packet
    if Network and Network['enabled']:
        if (Network['name'] == 'TTN'):
          if aData or (('cnt' in Dust.keys()) and Dust['cnt']): port=Dprt[1]
          else: port=Dprt[0]
          # LocUpdate -> DoGPS()
          if  Network['lib'].send(DoPack(dData,mData,LocUpdate(),aData=aData, debug=debug),port=port):
            if LED: LED.off
          else:
            display("LoRa send ERROR")
            if LED: LED.blink(5,0.2,0x9c5c00,l=False)
        elif LED: LED.blink(2,0.2,0xFF0000,l=False,force=True)

    MyMark(60)
    if STOP:
      SendEvent(port=Iprt, event=1) # send stopped
      sleep_ms(60*1000)
      try:
        if Display['enabled']: Display['lib'].poweroff()
      except: pass
      PinPower(atype=['dust','gps','meteo','display'],on=False,debug=debug)
      # and put ESP in deep sleep: DEEPSLEEP()
      MyMark(61)
      return False

    MyMark(70)
    toSleep = interval['interval'] - (ticks()-toSleep)
    if Dust and Dust['enabled']:
      if toSleep > 30:
        toSleep -= 15
        Dust['lib'].Standby()   # switch off laser and fan
    if toSleep < 15: toSleep = 15
    else: # save energy
      PinPower(atype=['gps','dust'],on=False,debug=debug) # auto on/off next time
      if Display and Display['enabled'] and (Power['display'] != None):
         Display['lib'].poweroff()
      # RGB led off?
    if MyConfig.dirty: MyConfig.store # update config flash?
    # LoRa nvram done via send routine

    MyMark(80)
    if Power['sleep'] or deepsleepMode():
      toSleep -= 1
      DEEPSLEEP(toSleep) # deep sleep
      # will never arrive here

    MyMark(90)
    if not Power['i2c']:
      if not ProgressBar(0,62,128,1,toSleep,0xebcf5b,10):
        display('stopped SENSING', (0,0), clear=True)
        if LED: LED.blink(5,0.3,0xff0000,l=True)
    elif toSleep > 15:
      sleep_ms((toSleep-1)*1000)
      # restore config and LoRa
      if LED: LED.blink(5,0.3,0x748ec1,l=False)
    PinPower(atype=['display','meteo'],on=True,debug=debug)
    if Display and Display['enabled'] and (Power['display'] != None):
       Display['lib'].poweron()
    if deepsleepMode(): wokeUp = True
    else: wokeUp = False

if __name__ == "__main__":
  runMe(debug=True)
  sys.exit() # reset
