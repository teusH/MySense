# should be main.py
# some code comes from https://github.com/TelenorStartIoT/lorawan-weather-station
# $Id: MySense.py,v 1.20 2018/04/06 14:27:13 teus Exp teus $
#
__version__ = "0." + "$Revision: 1.20 $"[11:-2]
__license__ = 'GPLV4'

from time import sleep, time
from time import localtime, timezone
from machine import Pin # user button/led
from machine import unique_id
import binascii
import pycom
import struct
from micropython import const
PyCom = 'PyCom'
# identity PyCom SN
myID = binascii.hexlify(unique_id()).decode('utf-8')
# Turn off hearbeat LED
pycom.heartbeat(False)

try:
  from Config import Network
except:
  pass
if not Network: raise OSError("No network config found")
if Network == 'TTN':
  PyCom = 'LoPy'
  try:
    from Config import dev_eui, app_eui, app_key
    from lora import LORA
    lora = None
  except:
    pycom.rgbled(0xFF0000)
    raise OSError('LoRa config failure')

from led import LED

STOP = False
try:
  from Config import sampling
  sample_time = sampling
except:
  sample_time = 60        # 60 seconds sampling for dust
try:
  from Config import sleep_time
  sleep_time *= 60
  print("frequency of measurements: %d secs" % sleep_time)
except:
  sleep_time = 5*60       # 5 minutes between sampling

# # stop processing press user button
# button = Pin('P10',mode=Pin.IN, pull=Pin.PULL_UP)
# #led = Pin('P9',mode=Pin.OUT)
# #led.toggle()
# STOP = False
# myID = None
# 
# def pressed(what):
#   global STOP, LED
#   STOP = True
#   print("Pressed %s" % what)
#   LED.blink(5,0.1,0xff0000,False)
# 
#
# button.callback(Pin.IRQ_FALLING|Pin.IRQ_HIGH_LEVEL,handler=pressed,arg='STOP')

# oled display handling routines
nl = 16
LF = const(13)
def display(txt,xy=(0,None),clear=False, prt=True):
  ''' Display Text on OLED '''
  global use_oled, oled, nl
  if oled != None:
    offset = 0
    if xy[1] == None: y = nl
    elif xy[1] < 0: 
      if -xy[1] < LF:
        offset = xy[1]
        y = nl - LF
    else: y = xy[1]
    x = 0 if ((xy[0] == None) or (xy[0] < 0)) else xy[0]
    if clear:
      oled.fill(0)
    if y > 56:
      nl =  y = 16
    if (not offset) and (not clear):
      rectangle(x,y,128,LF,0)
    oled.text(txt,x,y+offset)
    oled.show()
    if y == 0: nl = 16
    elif not offset: nl = y + LF
  if prt:
    print(txt)

def rectangle(x,y,w,h,col=1):
  global oled
  if not oled: return
  ex = int(x+w); ey = int(y+h)
  for xi in range(int(x),ex):
    for yi in range(int(y),ey):
      oled.pixel(xi,yi,col)

def ProgressBar(x,y,width,height,secs,blink=0,slp=1):
  global oled, LED, STOP
  if not oled: return
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
      LED.blink(1,0.1,blink,False)
    sleep(myslp)
    if x > xe: continue
    rectangle(x,y,step,height)
    oled.show()
    x += step
  return True

STOPPED = False
def showSleep(secs=60,text=None,inThread=False):
  global nl, oled, STOP, STOPPED
  ye = y = nl
  if text:
    display(text)
    ye += LF
  if oled:
    ProgressBar(0,ye,128,LF,secs,0x004400)
    nl = y
    rectangle(0,y,128,ye-y+LF,0)
    oled.show()
  else: sleep(secs)
  if inThread:
    STOP = False
    STOPPED = True
    _thread.exit()
  return True

import _thread
# _thread.stack_size(6144)
NoThreading = False
def SleepThread(secs=60, text=None):
  global STOP, NoThreading
  if NoThreading:
    display('waiting ...')
    raise OSError
  STOP = False; STOPPED = False
  try:
    _thread.start_new_thread(showSleep,(secs,text,True))
  except Exception as e:
    print("threading failed: %s" % e)
    STOPPED=True
    NoThreading = True
  sleep(1)

LAT = const(0)
LON = const(1)
ALT = const(2)
# returns distance in meters between two GPS coodinates
# hypothetical sphere radius 6372795 meter
# courtesy of TinyGPS and Maarten Lamers
# should return 208 meter 5 decimals is diff of 11 meter
# GPSdistance((51.419563,6.14741),(51.420473,6.144795))
def GPSdistance(gps1,gps2):
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

# configure the MySense satellite sensor kit
i2c = []
i2cPINs = []
spi = []
spiPINs = []
uart = [-1]

def indexBus(pins,bus,lookup):
  if not lookup in pins:
    pins.append(lookup)
    bus.append(None)
  return pins.index(lookup)

# tiny display Adafruit 128 X 64 oled
try:
  from Config import useSSD
  if useSSD: use_oled = True
  else: use_oled = False
except:
  use_oled = False
oled = None
if use_oled:
  try:
    import SSD1306
    # red P24 3v3 and black P25 Gnd
    width = 128; height = 64  # display sizes
    if useSSD == 'I2C': # display may flicker on reload
      from Config import S_SDA, S_SCL # I2C pin config
      if not len(i2c): from machine import I2C
      nr = indexBus(i2cPINs,i2c,(S_SDA,S_SCL))
      if i2c[nr] == None: i2c[nr] = I2C(nr,I2C.MASTER,pins=i2cPINs[nr])
      oled = SSD1306.SSD1306_I2C(width,height,i2c[nr])
      print('Oled I2C %d:' % nr, ' SDA ~> %s, SCL ~> %s' % i2cPINs[nr])
    elif useSSD == 'SPI': # for fast display
      try:
        from Config import S_CLKI, S_MOSI, S_MISO  # SPI pins config
      except:
        S_SCKI = 'P10'; S_MOSI = 'P11'; S_MISO = 'P14'  # SPI defaults
      if not len(spi): from machine import SPI
      try:
        from Config import S_DC, S_RES, S_CS      # GPIO SSD pins
      except:
        S_DC = 'P5'; S_RES = 'P6'; S_CS = 'P7'    # SSD defaults
      nr = indexBus(spiPINs,spi,(S_DC,S_CS,S_RES,S_MOSI,S_CLKI))
      if spi[nr] == None:
        spi[nr] = SPI(nr,SPI.MASTER, baudrate=100000,pins=(S_CLKI, S_MOSI, S_MISO))
      oled = SSD1306.SSD1306_SPI(width,height,spi[nr],S_DC, S_RES, S_CS)
      print('Oled SPI %d' % nr, 'DC ~> %s, CS ~> %s, RES ~> %s, MOSI/D1 ~> %s, CLK/D0 ~> %s' % spiPINs[nr], ', MISO ~> %s' % S_MISO)
    else:
      oled = None
      print("Incorrect display bus %s" % useSSD)
    if oled:
      oled.fill(1) ; oled.show(); sleep(1)
  except Exception as e:
    oled = None
    print('Oled display failure: %s' % e)

display('config %s' % PyCom, (0,0),clear=True)

# calibrate dict with lists for sensors { 'temperature': [0,1], ...}
try:
  from Config import calibrate
except:
  calibrate = None

# oled on SPI creates I2C bus errors
#  display('BME280 -> OFF', (0,0),True)
# Connect Sensors

Meteo = ['None','DHT11','DHT22','BME280','BME680']
try:
  from Config import useMeteo
except:
  useMeteo = None
if useMeteo != 'I2C': useMeteo = None
if useMeteo:
  try:
    if not len(i2c): from machine import I2C
    from Config import meteo,  M_SDA, M_SCL
    nr = indexBus(i2cPINs,i2c,(M_SDA,M_SCL))
    if not i2c[nr]: i2c[nr] = I2C(nr,I2C.MASTER,pins=i2cPINs[nr])
    print('%s I2C %d:' % (Meteo[meteo],nr), ' SDA ~> %s, SCL ~> %s' % i2cPINs[nr])
  except Exception as e:
    useMeteo = None
    print("Meteo failure: %s" % e)
if useMeteo:
  try:
    if meteo == 3: # BME280
      import BME280 as BME
    elif meteo == 4: # BME680
      import BME680 as BME
      try:
        from Config import M_gBase
      except:
        M_gBase = None
    useMeteo = BME.BME_I2C(i2c[nr], address=0x76, debug=False, calibrate=calibrate)
    if meteo == 4:
      display('AQI wakeup')
      useMeteo.gas_base = M_gBase
      if useMeteo._gasBase: pass
      nl -= LF # undo lf
      # useMeteo.sea_level_pressure = 1011.25
    display('meteo: %s' % Meteo[meteo])
  except Exception as e:
    useMeteo = None
    display("%s failure" % Meteo[meteo], (0,0), clear=True)
    print(e)
else:
  display("No meteo")
  meteo = 0

Dust = ['None','PPD42NS','SDS011','PMS7003']
try:
  from Config import useDust
except:
  useDust = None
if useDust:
  try:
    from Config import dust, D_Tx, D_Rx
  except:
    useDust = None
if useDust:
  try:
    if dust == 2:
      from SDS011 import SDS011 as senseDust
    elif dust == 3:
      from PMSx003 import PMSx003 as senseDust
    else: raise OSError("unknown PM sensor")
    useDust = senseDust(port=len(uart), debug=False, sample=sample_time, interval=0, pins=(D_Tx,D_Rx), calibrate=calibrate)
    uart.append(len(uart))
    print("%s UART %d: Rx ~> Tx %s, Tx ~> Rx %s" % (Dust[dust],len(uart),D_Tx, D_Rx))
  except Exception as e:
    display("%s failure" % Dust[dust], (0,0), clear=True)
    print(e)
    useDust = None; dust = 0
  display('PM mod: %s' % Dust[dust])
else:
  display("No PM sensing")
  dust = 0

# GPS config tuple (LAT,LON,ALT)
try:
  from Config import thisGPS
except:
  thisGPS = [0.0,0.0,0.0]
try:
  try:
    from Config import useGPS, G_Tx, G_Rx
    import GPS_dexter as GPS
  except:
    useGPS = None
  if useGPS:
    useGPS = GPS.GROVEGPS(port=len(uart),baud=9600,debug=False,pins=(G_Tx,G_Rx))
    uart.append(len(uart))
    print("GPS UART %d: Rx ~> Tx %s, Tx ~> Rx %s" % (len(uart),G_Tx, G_Rx))
    if useGPS:
      if not useGPS.date:
        useGPS.UpdateRTC()
      if useGPS.date:
        now = localtime()
        if 3 < now[1] < 11: timezone(7200) # simple DST
        else: timezone(3600)
        display('%d/%d/%d %s' % (now[0],now[1],now[2],('mo','tu','we','th','fr','sa','su')[now[6]]))
        display('time %02d:%02d:%02d' % (now[3],now[4],now[5]))
        thisGPS[LON] = round(float(useGPS.longitude),5)
        thisGPS[LAT] = round(float(useGPS.latitude),5)
        thisGPS[ALT] = round(float(useGPS.altitude),1)
      else:
        display('GPS bad QA %d' % useGPS.quality)
        useGPS.ser.deinit()
        useGPS = None
  else:
    display('No GPS')
except Exception as e:
  display('GPS failure', (0,0), clear=True)
  print(e)
  useGPS = None

if Network: display('Network: %s' % Network)

HALT = False
# called via TTN response
def CallBack(port,what): 
  global sleep_time, HALT, oled, useDust, useMeteo
  if not len(what): return True
  if len(what) < 2:
    if what == b'?': return SendInfo(port)
    elif what == b'O': oled.poweroff()
    elif what == b'd':
      if useDust:
        useDust.raw = True # try: useDust.gase_base = None
    elif what == b'D':
      if useDust:
        useDust.raw = False # try: useDust.gase_base = None
    elif what == b'm':
        if useMeteo: Meteo.raw = True
    elif what == b'M':
        if Meteo: Meteo.raw = False
    elif what == b'S': HALT = True
    else: return False
    return True
  cmd = None; value = None
  try:
    cmd, value = struct.unpack('>BH',what)
  except:
    return False
  if cmd == b'i':  # interval
    if value > 60: sleep_time = value

# LoRa setup
lora = None
def setup():
  global Network, lora
  global sleep_time, STOP, myId
  global dust, meteo, thisGPS, useGPS

  display("MySense V %s" % __version__[:6], (0,0), clear=True)
  display("s/n " + myID)
  display("PM   : " + Dust[dust])
  display("meteo: " + Meteo[meteo])
  if useGPS:
    display('GPS %.3f/%.3f' % (thisGPS[LAT],thisGPS[LON]))
  sleep(15)

  if Network == 'TTN':
    # Connect to LoRaWAN
    display("Try  LoRaWan", (0,0), clear=True)
    display("LoRa App EUI:")
    display(str(app_eui))
    lora = LORA()
    if lora.connect(dev_eui,app_eui,app_key, ports=2, callback=CallBack):
       display("Joined LoRaWan")
       SendInfo()
    else:
       display("NOT joined LoRa!")
       lora = None
       Network = 'None'
    sleep(10)
  if Network == 'None':
    display("No network!", (0,0), clear=True)
    LED.blink(10,0.3,0xff00ff,True)
    # raise OSError("No connectivity")
  display("Setup done")

PM1 = const(0)
PM25 = const(1)
PM10 = const(2)
def DoDust():
  global useDust, Dust, dust, nl, STOP, STOPPED
  dData = {}
  display('PM sensing',(0,0),clear=True,prt=False)
  if useDust and (useDust.mode != useDust.NORMAL):
    useDust.Normal()
    if not showSleep(secs=15,text='starting up fan'):
      display('stopped SENSING', (0,0), clear=True)
      LED.blink(5,0.3,0xff0000,True,True)
      return [0,0,0]
    else:
      display('measure PM')
  if useDust:
    LED.blink(3,0.1,0x005500)
    # display('%d sec sample' % sample_time,prt=False)
    try:
      STOPPED = False
      try:
        SleepThread(sample_time,'%d sec sample' % sample_time)
      except:
        STOPPED = True
        display('%d sec sample' % sample_time)
      dData = useDust.getData()
      for cnt in range(10):
        if STOPPED: break
        STOP = True
        print('waiting for thread')
        sleep(2)
      STOP = False
    except Exception as e:
      display("%s ERROR" % Dust[dust])
      print(e)
      LED.blink(3,0.1,0xff0000)
      dData = {}
    LED.blink(3,0.1,0x00ff00)

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
  if not dData:
    display("No PM values")
    LED.blink(5,0.1,0xff0000,True)
    dData = [0,0,0]
  else:
    dData = [round(dData['pm1'],1),round(dData['pm25'],1),round(dData['pm10'],1)]
    LED.off()
  return dData

TEMP = const(0)
HUM = const(1)
PRES = const(2)
GAS = const(3)
AQI = const(4)
def DoMeteo():
  global useMeteo, nl
  global Meteo, meteo
  global M_SDA, M_SCL
  mData = [0,0,0,0,0]
  if not useMeteo or not meteo: return mData

  # Measure temp oC, rel hum %, pres pHa, gas Ohm, aqi %
  LED.blink(3,0.1,0x002200,False)
  try: 
    nr = indexBus(i2cPINs,i2c,(M_SDA,M_SCL))
    i2c[nr].init(nr, pins=i2cPINs[nr]) # SPI oled causes bus errors
    sleep(1)
    mData[TEMP] = float(useMeteo.temperature) # string '20.12'
    mData[HUM] = float(useMeteo.humidity)     # string '25'
    mData[PRES] = float(useMeteo.pressure)    # string '1021.60'
    if meteo == 4: # BME680
      mData[GAS] = float(useMeteo.gas)        # Ohm 29123
      mData[AQI] = round(float(useMeteo.AQI),1) # 0-100% ok
  except Exception as e:
    display("%s ERROR" % Meteo[meteo])
    print(e)
    LED.blink(5,0.1,0xff00ff,True)
    return [0,0,0,0,0]

  LED.off()
  nl += 6  # oled spacing
  if mData[GAS] > 0:
    display("  C hum% pHa AQI")
    display("o",(12,-5),prt=False)
    display("% 2.1f %2d %4d %2d" % (round(mData[TEMP],1),round(mData[HUM]),round(mData[PRES]),round(mData[AQI])))
  else:
    display("    C hum%  pHa")
    display("o",(24,-5),prt=False)
    display("% 3.1f  % 3d % 4d" % (round(mData[TEMP],1),round(mData[HUM]),round(mData[PRES])))
  return mData # temp, hum, pres, gas, aqia

def DoPack(dData,mData):
  global meteo, dust
  return struct.pack('>HHHHHHHHHl',int(dData[PM1]*10),int(dData[PM25]*10),int(dData[PM10]*10),int(mData[TEMP]*10+300),int(mData[HUM]*10),int(mData[PRES]),int(round(mData[GAS]/100.0)),int(mData[AQI]*10),time())

lastUpdate = 0
def SendInfo(port=3):
  global  lora, meteo, dust, useGPS, thisGPS, lastUpdate
  lastUpdate = time()
  if lora == None: return True
  if (not meteo) and (not dust) and (useGPS == None): return True
  if useGPS:
    # GPS 5 decimals: resolution 14 meters
    thisGPS[LAT] = round(float(useGPS.latitude),5)
    thisGPS[LON] = round(float(useGPS.longitude),5)
    thisGPS[ALT] = round(float(useGPS.altitude),1)
  version = int(__version__[0])*10+int(__version__[2])
  data = struct.pack('>BBlll',version,((meteo&07)<<4)|(dust&07), int(thisGPS[LAT]*100000),int(thisGPS[LON]*100000),int(thisGPS[ALT]*10))
  return lora.send(data,port=port)

updateMin = 7*60    # 7 minutes, kit moved
updateMax = 6*60*60 # 6 hours
updateStable = 5    # control freq of info
def LocUpdate():
  global lastUpdate, useGPS, thisGPS
  global  updateMin, updateMax, updateStable
  now = time()
  if now - lastUpdate > updateMax:
    updateStable = 2
    return SendInfo()
  if not useGPS: return False
  if now - lastUpdate < updateMin: return False
  if updateStable <= 0: return False
  location = [0.0,0.0]
  location[LAT] = round(float(useGPS.latitude),5)
  location[LON] = round(float(useGPS.longitude),5)
  if GPSdistance(location,thisGPS) > 50:
    updateStable = 5
    return SendInfo()
  updateStable -= 1
  return False

def runMe():
  global lora, sleep_time, oled
  global useDust

  setup() # Setup network & sensors

  while True:
    if LocUpdate():
      display("Sent info/GPS", (0,0), clear=True)
      sleep(10)
    #display("Sensing...", (0,0), clear=True)

    toSleep = time()
    dData = DoDust()
    mData = DoMeteo()

    # Send packet
    if lora != None:
      if  lora.send(DoPack(dData,mData)):
        LED.off()
      else:
        display(" LoRa send ERROR")
        LED.blink(5,0.2,0x9c5c00,False)

    toSleep = sleep_time - (time() - toSleep)
    if useDust:
      if toSleep > 30:
        toSleep -= 15
        useDust.Standby()   # switch off laser and fan
      elif toSleep < 15: toSleep = 15
    if not ProgressBar(0,63,128,2,toSleep,0xebcf5b,10):
      display('stopped SENSING', (0,0), clear=True)
      LED.blink(5,0.3,0xff0000,True,True)
    if STOP:
      sleep(60)
      oled.poweroff()
      # and put ESP in deep sleep: machine.deepsleep()
      return False

if __name__ == "__main__":
  runMe()
