__version__ = "0." + "$Revision: 5.4 $"[11:-2]
__license__ = 'GPLV3'

from machine import deepsleep, wake_reason, PWRON_WAKE
wokeUp = wake_reason()[0] != PWRON_WAKE
if wokeUp: print("Woke up from deepsleep.")
else: print("Cold reboot")

################## json flashed configuration
# roll in archive configuration
try:
  import ConfigJson
except:
  print("Missing library led and/or ConfigJson")
  sys.exit()
MyConfig = ConfigJson.MyConfig(debug=False)
config = MyConfig.getConfig() # configuration
if config: print("Got config from flash: %s" % str(config))

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

################# S/N number
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

################## accu
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
  return not sleeping.value()

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
    method['ABP'] = (nwk_swkey, nwk_swkey, app_swkey)
    MyConfig.dump('LoRa','ABP')
  except: pass
  if not len(method): raise ValueError("No LoRa keys configured or LoRa config error")
  print("Using %s LoRa methods from Config." % ', '.join(method.keys()))

if MyConfig.dirty: 
  print("Store LoRa method in flash")
  MyConfig.store
  config = MyConfig.getConfig()
  if LED: LED.blink(5,0.3,0x00ff00,False)

if not myLoRa.connect(method, ports=2, myLED=LED, debug=True):
  print("Failed to connect to LoRaWan TTN")
  if LED: LED.blink(5,0.3,0xff0000,False)
  sys.exit(0)

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

if (not sleepMode()) or wokeUp: # woke up from deepsleep or no deepsleep pin strap
  print('Done')
else:
  if LED: LED.blink(5,0.3,0x0000ff,True)
  print("Go into deepsleep for 3 secs")
  deepsleep(3000)
  ####################
  print("Should not arrive here")
  # myLoRa.restore

if (accu < 0.1) and sleepMode():
  if LED: LED.blink(10,0.3,0xff0000,False)
  print("strap on pin %s and NO accu attached:" % MyConfig.config['sleepPin'])
  print("WARNING: RESET config in mem and LoRa nvram")
  MyConfig.clear; config = MyConfig.getConfig()
  # myLoRa.clear
pycom.heartbeat(True)
sys.exit()
