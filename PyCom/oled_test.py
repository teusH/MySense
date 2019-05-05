# Copyright 2019, Teus Hagen, GPLV3
# simple test to see if display I2C device is present
from time import sleep_ms
from machine import I2C
import sys

__version__ = "0." + "$Revision: 5.8 $"[11:-2]
__license__ = 'GPLV3'

abus='i2c'
atype='display'

debug = False
import ConfigJson
MyConfig = ConfigJson.MyConfig(debug=debug)
config = { abus: {} }
config[abus] = MyConfig.getConfig(abus=abus)
FndDevices = []
if config[abus]:
  print("Found archived configuration for:")
  for dev in config[abus].keys():
    FndDevices.append(dev)
    print("%s: " % dev, config[abus][dev])

import whichI2C
if config[abus] and (atype in config[abus].keys()):
  which = whichI2C.identification(identify=True,config=config[abus], debug=debug)
else: # look for new devices
  which =  whichI2C.identification(identify=True, debug=debug)
  config[abus] = which.config
  FndDevices = []
# which.config =
# {'updated': True, 'meteo': {'use': True, 'pins': ('P23', 'P22', 'P21'), 'name': 'BME680', 'address': 118}, 'display': {'address': 60, 'pins': ['P23', 'P22', 'P21'], 'use': True, 'name': 'SSD1306'}}
for dev in config[abus].keys():
  if not dev in FndDevices:
    if dev != 'updated':
      print("Found device %s: " % dev, config[abus][dev])
      MyConfig.dump(dev,config[abus][dev],abus=abus)

device = which.getIdent(atype=atype, power=True)
# which.Devices('display')
# {'lib': None, 'conf': which.config['display'], 'index': 0, 'enabled': None, 'i2c': I2C(0, I2C.MASTER, baudrate=100000)}
print("Using %s: " % atype, which.devices[atype])

if config[abus][atype]['use']:
  try:
    try: import SSD1306
    except: raise ImportError("library SSD1306 missing")
    width = 128; height = 64  # display sizes
    if True: # display may flicker on reload
      if (not device) or (not len(device)):
        raise ValueError("No I2C oled display found.")
      print("Found I2C[%d] device %s" % (device['index'],config[abus][atype]['name']))
      which.Power(device['conf']['pins'], on=True)
      oled = device['lib'] = SSD1306.SSD1306_I2C(width,height,device['i2c'],addr=config[abus][atype]['address'])
    #elif False:  # 'SPI': # for fast display
    #  try:
    #    from Config import S_CLKI, S_MOSI, S_MISO  # SPI pins config
    #  except:
    #    S_DC = 'P10'; S_MOSI = 'P11'; S_MISO = 'P14'  # SSD defaults
    #  try:
    #    from Config import S_DC, S_RES, S_CS      # GPIO SSD pins
    #  except:
    #    S_DC = 'P5'; S_RES = 'P6'; S_CS = 'P7'    # SSD default pins
    #  from machine import SPI
    #  print('Oled SPI: DC ~> %s, CS ~> %s, RST ~> %s, D1/MOSI ~> %s, D0/CLK ~> %s' % (S_DC,S_CS,S_RES,S_MOSI,S_CLKI))
    #  spi = SPI(0,SPI.MASTER, baudrate=100000,pins=(S_CLKI, S_MOSI, S_MISO))
    #  device['lib'] = SSD1306.SSD1306_SPI(width,height,spi,S_DC, S_RES, S_CS)
    else:
      oled = device['lib'] = None
      raise ValueError("Incorrect display lib" % config[abus][atype]['name'] )
    if oled:
      oled.fill(1) ; oled.show(); sleep_ms(1000)
      oled.fill(0); oled.show()
  except Exception as e:
    oled = None
    print('Oled display failed: %s' % e)
    import sys
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

try:
    import pycom
    # Turn off hearbeat LED
    pycom.heartbeat(False)
    display("MySense PyCom",0,0,True)
    display('test bar',0,0,True)
    if not ProgressBar(0,34,128,10,12,0xebcf5b,1):
        LED.blink(5,0.3,0xff0000,True)
    else: LED.blink(5,0.3,0x00ff00,False)
except Exception as e:
    print("Failure: %s" % e)

if MyConfig.dirty:
  print("Found new I2C devices. Will archive.")
  MyConfig.store
print("DONE. Soft reset.")
sys.exit()
