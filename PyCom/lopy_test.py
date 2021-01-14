# Copyright 2019, Teus Hagen, GPLV3

''' basis PyCom LoPy controller and PCB test.
    get: S/N, json config file, RGB led, accu and voltage, Hall (REPL modus),
    sleep modus, LoRa and some LoRa tries.
    if deepsleep pin not is enabled, no update of config file will be done.
    If no accu is attached and deepsleep pin is enabled flashed config file will be cleared.
'''

__version__ = "0." + "$Revision: 6.1 $"[11:-2]
__license__ = 'GPLV3'

try: debug
except: debug=True
confFile = '/flash/MySenseConfig.json'
#try:
#    import os
#    os.remove(confFile)
#except: pass
try: update
except: update = True

atype = 'lopy'

from machine import deepsleep, wake_reason, PWRON_WAKE
wokeUp = wake_reason()[0] != PWRON_WAKE
if wokeUp: print("Woke up from deepsleep.")
else: print("Cold reboot")

################## json flashed configuration
# roll in archive configuration
import ConfigJson
MyConfig = ConfigJson.MyConfig(archive=(not wokeUp), debug=debug)
config = {}
config = MyConfig.getConfig() # configuration
if config:
  print("Got config from flash: %s" % str(config))
  for abus in ['ttl','i2c']:
    if not abus in config.keys(): continue
    print("Found archived %s configuration for:" % abus)
    for dev in config[abus].keys():
      if dev is 'updated': continue
      print("\t%s: " % dev, config[abus][dev])
else: print("No json configuration file found")

####################### RGB led
import sys
from time import time, sleep
# Turn off hearbeat LED
import pycom
pycom.heartbeat(False)
LED = None
try:
  import led # show errors
  LED = led.LED()
except: pass

####3333############## S/N number
import os
uname = os.uname()
print("Pycom %s" % uname.machine)
from machine import unique_id
import binascii
try:
    myID = binascii.hexlify(unique_id()).decode('utf-8')
    print("s/n " + myID)
except Exception as e:
    print("Failure: %s" % e)
print("Firmware version: %s" % uname.version)

##################### accu
# Read accu voltage out
adc_bat = None
def getBatVoltage():
  global adc_bat
  if adc_bat == None:
    global config, MyConfig
    if not 'accuPin' in config.keys():
      accuPin = 'P17'
      try: from Config import accuPin
      except: pass
      MyConfig.dump('accuPin',accuPin); config['accupin'] = accuPin
    else: accuPin = config['accuPin']
    from machine import ADC
    adc = ADC(0)
    adc_bat = adc.channel(pin=accuPin, attn=ADC.ATTN_11DB)
  return adc_bat.value()*0.004271845

accu = getBatVoltage()
if accu > 0.1:
  print("Accu voltage: %f Vdc" % accu)
  if 0.1 < accu < 11.2:
    print("Low accu voltage, charge accu")
    if LED: LED.blink(5,0.1,0x00ffff,False)
  elif LED: LED.blink(5,0.1,0x00ff00,False)
else: print("No accu (management pin %s) connected." % MyConfig.config['accuPin'])

################ hall pin (force REPL modus)
REPL = None
try:
  from Config import replPin # if not in config act in old style
  from machine import Pin
  print("Pin %s: REPL mode is %s" % (replPin,str(Pin(replPin,mode=Pin.IN).value() )) )
except: print('No REPL mode pin (P13?) defined in Config.py')

################ sleep
sleeping = None
def sleepMode():
  global sleeping
  if sleeping == None:
    global config, MyConfig
    sleepPin = 'P18'
    if not 'sleepPin' in config.keys():
      try: from Config import sleepPin
      except: pass
      MyConfig.dump('sleepPin',sleepPin); config['sleepPin'] = sleepPin
    else: sleepPin = config['sleepPin']
    from machine import Pin
    sleeping = Pin(sleepPin,mode=Pin.IN)
  return sleeping.value()

sleepMode()

print("Sleep button (pin %s) state: %s." % (config['sleepPin'],
                                   'NO strap' if not sleepMode() else 'strap placed'))
if sleepMode():
  print("Will do DEEPSLEEP")
  if LED: LED.blink(5,0.1,0xffffff,False)
else:
  if LED: LED.blink(1,0.5,0xffffff,False)
  print("Will NOT do deepsleep")

#button = Pin('P18',mode=Pin.IN, pull=Pin.PULL_DOWN)
#led = Pin('P9',mode=Pin.OUT)
#
#def pressed(what):
#  print("Pressed %s" % what)
#  LED.blink(5,0.1,0xff0000,False)
#
#button.callback(Pin.IRQ_FALLING|Pin.IRQ_HIGH_LEVEL,handler=pressed,arg='SLEEP')

#  global led
#  led.toggle()
#
# found oled, try it and blow RGB led wissle

##################### LoRa
oldStat = [-1,-1,-1,-1,-1,-1,-1,-1,-1,-1]
def LoRaStatus(net): # print LoRa status
   global oldStat
   try:
      if not net.lora.has_joined():
          print("LoRa not joined!")
          return
      status = net.lora.stats()
   except:
      print("LoRa status error")
      return
   print('LoRaWan status:')
   # status[0] last datagram time stamp msec
   if status[1] != oldStat[1]: print("  RSSI           %d dBm" % status[1])
   if status[2] != oldStat[2]: print("  SNR            %.1f dB" % status[2])
   if status[3] != oldStat[3]: print("  Tx datarate    %d" % status[3])
   if status[4] != oldStat[4]: print("  Rx datarate    %d" % status[4])
   if status[5] != oldStat[5]: print("  Tx trials      %d" % status[5])
   if status[6] != oldStat[6]: print("  Tx power       %d" % status[6])
   if status[7] != oldStat[7]: print("  Tx time on air %d msec" % status[7])
   if status[8] != oldStat[8]: print("  Tx count       %d" % status[8])
   if status[9] != oldStat[9]: print("  Rx frequency   %.1f MHz" % (status[9]/1000000.0))
   oldStat = status

if not wokeUp:
  Network = ''
  from Config import Network
  if Network != 'TTN': raise ValueError("%s not supported" % Network)

initLoRa = not wokeUp
if MyConfig.getConfig('LoRa') in ['ABP','OTAA']:
  print("Using %s LoRa info from flash" % MyConfig.getConfig('LoRa'))
  initLoRa = False

from lora import LORA
myLoRa = LORA()
# myLoRa.cleanup will clear LoRa nvram

info = None
method = {}
dr = 5 # sf=7 default LoRa
if initLoRa:
  # OTAA keys
  try:
    from Config import dev_eui, app_eui, app_key
    method['OTAA'] = (dev_eui, app_eui, app_key)
    MyConfig.dump('LoRa','OTAA')
  except: pass
  # ABP keys
  try:
    from Config import dev_addr, nwk_swkey, app_swkey
    method['ABP'] = (dev_addr, nwk_swkey, app_swkey)
    MyConfig.dump('LoRa','ABP')
  except: pass
  if not len(method): raise ValueError("No LoRa keys configured or LoRa config error")
  dr = 0
  try:
    from Config import DR_join
    if 0 <= DR_join <= 5: dr = DR_join # 0=SF12, 5=SF7 (dflt)
  except: pass
  print("Using %s LoRa methods from Config with sf=%d." % (', '.join(method.keys()),12-dr))

if not myLoRa.connect(method, ports=2, myLED=LED, dr=dr, debug=debug):
  print("Failed to connect to LoRaWan TTN")
  if LED: LED.blink(5,0.3,0xff0000,False)
  sys.exit(0)
elif LED:
  sleep(2)
  LED.blink(5,0.3,0x0000FF,False)
else: pycom.heartbeat(True)

################### LoRa
def SendInfo(port,data):
  print("info requested")
  if not data: return
  if (not info) or (not n): return
  print("Sent info")
  sleep(30)
  myLoRa.send(info,port=3)

# send first some info
# dust (None,Shiney,Nova,Plantower, ...) 4 low bits
# meteo (None,DHT11,DHT22,BME280,BME680, ...) 4 high bits
# GPS (longitude,latitude, altitude) float
# send 17 bytes
import struct
thisGPS = [50.12345,6.12345,12.34]
try: from Config import useGPS, thisGPS
except: pass

if not wokeUp: # no need to send meta data again
  useGPS = False

  Meteo = ['unknown','DHT11','DHT22','BME280','BME680']
  try: from Config import meteo
  except: meteo = 'unknown'
  Dust = ['unknown','PPD42NS','SDS011','PMS7003']
  try: from Config import dust
  except: dust = 'unknown'

  sense = ((Meteo.index(meteo)&0xf)<<4) | (Dust.index(dust)&0x7)
  if useGPS: sense |= 0x8
  info = struct.pack('>BBlll',0,sense,int(thisGPS[0]*100000),int(thisGPS[1]*100000), int(thisGPS[2]*10))
  print("Sending version 0, meteo %s, dust %s, configured GPS: " % (meteo,dust), thisGPS)

  if not myLoRa.send(info,port=3):
    print("Info send error")
    if LED: LED.blink(5,0.3,0xff0000,False)
  else:
    print('Info is sent')
    if LED: LED.blink(5,0.3,0x00ff00,False)
    LoRaStatus(myLoRa)

# send some data
for cnt in range(3):
  if cnt:
    if LED:
      for i in range(1,60,4):
        LED.blink(6,0.5,(0x111111*i),False)
    else: sleep(60)
  # old style
  # data = struct.pack('>HHHHHHHHl', 10+cnt, 15+cnt, 20+cnt, 25+cnt, 30+cnt, 35+cnt, 40+cnt, 45+cnt, time())
  # packaged as: type, PM25*10, PM10*10, temp*10+300, hum*10
  if cnt%2:
    data = struct.pack('>BHHHHHlll', 0x88, int(250+cnt), int(100+cnt), 300+cnt, cnt, 1000+cnt, int(thisGPS[0]*100000),int(thisGPS[1]*100000), int(thisGPS[2]*10))
  else:
    data = struct.pack('>BHHHHH', 0x80, int(250+cnt), int(10+cnt), 300+cnt, cnt,0)
  # Send packet
  if not myLoRa.send(data):  # send to LoRa port 2
    if LED: LED.blink(5,0.3,0xff0000,False)
    print("send error")
  else:
    print('Fake data nr %d of 3 is sent. Tx count %d. Joined: %s' % ((cnt+1),myLoRa.status,str(myLoRa.lora.has_joined())))
    if LED: LED.blink(5,0.3,0x00ff00,False)
    LoRaStatus(myLoRa)
print("Clearing LoRa nvs ram.")
myLoRa.clear
del myLoRa
del data

if sleepMode() and not wokeUp: # woke up from deepsleep or no deepsleep pin strap
  if LED: LED.blink(5,0.3,0x0000ff,True)
  print("Go into deepsleep for 3 secs")
  deepsleep(3000)
  ####################
  print("Should not arrive here")

# Reset flashed configuration
if MyConfig.dirty:
  print("Updating configuration json file %s:" % confFile)
  try:
    for dev in config[abus].keys():
      if dev is 'updated': continue
      if not dev in FndDevices:
        print("Found new %s device %s: " % (abus,dev), config[abus][dev])
    print("Add this gas base to Config.py: %.1f" % device['fd'].gas_base)
  except: pass
  # from machine import Pin
  # apin = 'P18'  # deepsleep pin
  # if not Pin(apin,mode=Pin.IN).value():
  if MyConfig.dirty and MyConfig.store:
    print("Updated config json file in %s." % confFile)
  else: print("Update config json file in %s NOT needed." % confFile)

del MyConfig
del config
pycom.heartbeat(True)
print("DONE LoPy test: MySense LoRa, pins, etc.")
sys.exit()

