# Copyright 2019, Teus Hagen, GPLV3
''' simple test to see if display I2C device is present
Side effect: if device is found it is added to configuration file.
Next can be done before running this module.
Use update = False not to update meteo in json config file.
    debug = False to disable.
'''

from time import sleep_ms
import sys

__version__ = "0." + "$Revision: 6.2 $"[11:-2]
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

abus='i2c'
atype='display'
print("%s %s MySense configuration." % ('Updating' if update else 'No update',atype))

import ConfigJson
config = {abus: {}}
MyConfig = ConfigJson.MyConfig(debug=debug)
config[abus] = MyConfig.getConfig(abus=abus)
FndDevices = []
if config[abus]:
  print("Found archived %s configuration for:" % abus)
  for dev in config[abus].keys():
    if dev is 'updated': continue
    FndDevices.append(dev)
    print("\t%s: " % dev, config[abus][dev])
  if not atype in FndDevices:
    print("Sensor %s not found in conf  %s file." % (atype, confFile))
  if atype in FndDevices and update:
    del config[abus][dev]; FndDevices.remove(atype)

import whichI2C as DEV
try:
  if config[abus] and (atype in config[abus].keys()):
    which = DEV.identification(identify=True,config=config[abus], debug=debug)
  else: # look for new devices
    which =  DEV.identification(identify=True, debug=debug)
    config[abus] = which.config
    for dev in which.devices.keys():
      FndDevices.append(dev)
      #config[abus][dev]['conf']['use'] = True
      print("New %s: " % dev, config[abus][dev])
      MyConfig.dump(dev,config[abus][dev],abus=abus)
except Exception as e:
  print("%s indentification error: %s" % (abus.upper(),str(e)))
  print("%s configuration error in Config.py?" % abus.upper())
  sys.exit()

if not atype in config[abus].keys() or not config[abus][atype]['use']:
  print("No %s found on bus %s or use is disabled." % (atype,abus))
  sys.exit()

device = {}
try:
  device = which.getIdent(atype=atype, power=True)
  nr = device['index']
  i2c = device[abus]
  addr = device['conf']['address']
  name = which.DISPLAY
  pins = which.Pins(atype)
except Exception as e:
  print("Error: %s" % e)
  sys.exit()

print("Using %s: device=%s, I2C=%s, address=0x%x, pins=%s." % (atype,name,str(i2c),addr,str(pins)))

prev = None
try:
  try: import SSD1306
  except: raise ImportError("library SSD1306 missing")
  width = 128; height = 64  # display sizes
  oled = device['lib'] = SSD1306.MyI2C(width,height,device['i2c'],address=config[abus][atype]['address'], probe=True, lock=None)
  if not oled: raise IOError("Oled SSD1306 lib failure")

  prev =  which.Power(device['conf']['pins'], on=True)
  oled.fill(1) ; oled.show(); sleep_ms(1000)
  oled.fill(0); oled.show()
except Exception as e:
  print('Oled display failed with %s' % e)
  if not prev is None: which.Power(device['conf']['pins'], on=prev)
  sys.exit()

# found oled, try it and blow RGB led wissle
try:
  import led
  LED = led.LED()
except:
  raise OSError("Install library led")

#button = Pin('P18',mode=Pin.IN, pull=Pin.PULL_DOWN)
#led = Pin('P9',mode=Pin.OUT)
#
#def pressed(what):
#  # global LED
#  print("Pressed %s" % what)
#  LED.blink(5,0.1,0xff0000,False)
#
#button.callback(Pin.IRQ_FALLING|Pin.IRQ_HIGH_LEVEL,handler=pressed,arg='SLEEP')

def display(txt,x,y,clear, prt=True):
  ''' Display Text on OLED '''
  global config
  if oled:
    if clear: oled.fill(0)
    oled.text(txt,x,y)
    oled.show()
  if prt: print(txt)

def rectangle(x,y,w,h,col=1):
  global oled
  if not oled: return
  ex = int(x+w); ey = int(y+h)
  for xi in range(int(x),ex):
    for yi in range(int(y),ey):
      oled.pixel(xi,yi,col)

def ProgressBar(x,y,width,height,secs,blink=0,slp=1):
  global oled
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
    if blink:
      LED.blink(1,0.1,blink,False)
    sleep_ms(int(myslp*1000))
    if x > xe: continue
    rectangle(x,y,step,height)
    if oled: oled.show()
    x += step
  return True

import pycom
pycom.heartbeat(False)
try:
    # Turn off hearbeat LED
    display("MySense PyCom",0,0,True)
    display('test bar',0,0,True)
    if not ProgressBar(0,34,128,10,12,0xebcf5b,1):
        LED.blink(5,0.3,0xff0000,True)
    else: LED.blink(5,0.3,0x00ff00,False)
    display("Oled test DONE",0,0,True)
    sleep_ms(1000)
    oled.fill(0); oled.show()
except Exception as e:
    print("Failure: %s" % e)

which.Power(device['conf']['pins'], on=prev)
pycom.heartbeat(True)

if MyConfig.dirty:
  print("Updating configuration json file %s:" % confFile)
  try:
    for dev in config[abus].keys():
      if dev is 'updated': continue
      if not dev in FndDevices:
        print("Found new %s device %s: " % (abus,dev), config[abus][dev])
  except: pass
  # from machine import Pin
  # apin = 'P18'  # deepsleep pin
  # if not Pin(apin,mode=Pin.IN).value():
  if MyConfig.dirty and MyConfig.store:
    print("Updated config json file in %s." % confFile)
  else:
    print("Update config json file in %s NOT needed." % confFile)
print("DONE %s-bus test for %s sensor %s" % (abus.upper(),atype,name))
sys.exit()
