# PyCom Micro Python / Python 3
# some code comes from https://github.com/TelenorStartIoT/lorawan-weather-station
# $Id: MySense.py,v 3.5 2018/11/08 20:37:15 teus Exp teus $
#
__version__ = "0." + "$Revision: 3.5 $"[11:-2]
__license__ = 'GPLV4'

from time import sleep, time
from time import localtime, timezone
from machine import Pin # user button/led
from machine import unique_id
from machine import I2C
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
    LoRaMethod = {}
    try:
       from Config import dev_eui, app_eui, app_key
       LoRaMethod['OTAA'] = (dev_eui, app_eui, app_key)
    except: pass
    try:
       from Config import dev_addr, nwk_swkey, app_swkey
       LoRaMethod['ABP'] = (dev_addr, nwk_swkey, app_swkey)
    except: pass
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

useSSD = None   # enable display
try: from Config import useSSD
except: pass
useMeteo = None   # enable meteo
try: from Config import useMeteo
except: pass

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
def oledShow():
  global i2c, i2cPINs, S_SDA, S_SCL, useSSD
  global oled
  if type(useSSD) is dict:
    for cnt in range(0,2):
      try:
        oled.show()
        break
      except OSError:
        print("BusError: Init I2C bus")
        useSSD['i2c']['fd'].init(I2C.MASTER, pins=useSSD['i2c']['pins'])
        sleep(0.5)
    # useSSD['i2c']['fd'].init(I2C.MASTER, pins=useSSD['i2c']['pins'])
    # sleep(0.5)
  else: oled.show()

nl = 16
LF = const(13)
# width = 128; height = 64  # display sizes
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
    oledShow()
    if y == 0: nl = 16
    elif not offset: nl = y + LF
    if nl >= (64-13): nl = 16
  if prt:
    print(txt)

def rectangle(x,y,w,h,col=1):
  global oled
  if not oled: return
  ex = int(x+w); ey = int(y+h)
  if ex > 128: ex = 128
  if ey > 64: ey = 64
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
    oledShow()
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
    ProgressBar(0,ye-3,128,LF-3,secs,0x004400)
    nl = y
    rectangle(0,y,128,ye-y+LF,0)
    oledShow()
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

# configure the MySense devices where is which device
i2c = [ # {'pins': (SDA,SCL), 'fd': None}
    ]
spi = [ # {'pins': (SCKI,MOSI,MISO)}
    ]
uart = [-1]  # default number from 1
try:
    from Config import uart # allow P0,P1 pins?
except: pass

# search for I2C devices
def searchDev(names=['BME','SHT','SSD']):
    global useMeteo, useSSD
    try: from Config import BME
    except: BME=280
    try:
        from Config import I2Cpins, I2Cdevices
    except:
        return False
    for index in range(0,len(I2Cpins)):
        i2c.append({'fd': I2C(index, I2C.MASTER, pins=I2Cpins[index]), 'pins': I2Cpins[index]})
        regs = i2c[-1]['fd'].scan()
        for item in I2Cdevices:
            if item[1] in regs:
                print('%s I2C[%d]:' % (item[0],index), ' SDA ~> %s, SCL ~> %s' % I2Cpins[index], 'address 0x%2X' % item[1])
                if not item[0][:3] in names: continue
                if (item[0] == 'BME280') and (BME == 680): item[0] = 'BME680'
                if (item[0][:3] in ['BME','SHT']) and (not type(useMeteo) is dict) and useMeteo:
                    useMeteo = { 'i2c': i2c[index], 'name': item[0], 'addr': item[1] }
                if (item[0][:3] in ['SSD']) and (not type(useSSD) is dict) and useSSD:
                    useSSD = { 'i2c': i2c[index], 'name': item[0], 'addr': item[1] }
    return len(i2c) > 0

def indexBus(pins,lookup): # SPI only
  global spi
  if not lookup in pins:
    pins.append(lookup)
    spi.append(None)
  return pins.index(lookup)

# connect I2C devices
if not searchDev(names=['BME','SHT','SSD']): print("No I2C devices found")
# tiny display Adafruit 128 X 64 oled driver
oled = None
if useSSD:
  try:
    import SSD1306
    # red P24 3v3 and black P25 Gnd
    width = 128; height = 64  # display sizes
    if type(useSSD) is dict: # display may flicker on reload
      oled = SSD1306.SSD1306_I2C(width,height,useSSD['i2c']['fd'], addr=useSSD['addr'])
      # print('Oled I2C:', ' SDA ~> %s, SCL ~> %s' % useSSD['i2c']['pins'])
    elif useSSD == 'SPI': # for fast display This needs rework for I2C style
      try:
        from Config import S_CLKI, S_MOSI, S_MISO  # SPI pins config
      except:
        S_SCKI = 'P10'; S_MOSI = 'P11'; S_MISO = 'P14'  # SPI defaults
      if not len(spi): from machine import SPI
      try:
        from Config import S_DC, S_RES, S_CS      # GPIO SSD pins
      except:
        S_DC = 'P5'; S_RES = 'P6'; S_CS = 'P7'    # SSD defaults
      nr = indexBus(spiPINs,(S_DC,S_CS,S_RES,S_MOSI,S_CLKI))
      if spi[nr] == None:
        spi[nr] = SPI(nr,SPI.MASTER, baudrate=100000,pins=(S_CLKI, S_MOSI, S_MISO))
      oled = SSD1306.SSD1306_SPI(width,height,spi[nr],S_DC, S_RES, S_CS)
      print('Oled SPI %d' % nr, 'DC ~> %s, CS ~> %s, RES ~> %s, MOSI/D1 ~> %s, CLK/D0 ~> %s' % spiPINs[nr], ', MISO ~> %s' % S_MISO)
    else:
      oled = None
      print("No SSD display or bus found")
    if oled:
      oled.fill(1) ; oledShow(); sleep(1)
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

# start meteo sensor
meteo = ''
if not type(useMeteo) is dict:
  useMeteo = None
else:
  meteo = useMeteo['name']
  try:
    if meteo == 'BME280':
      import BME280 as BME
    elif meteo == 'BME680':
      import BME_I2C as BME
      try:
        from Config import M_gBase
      except:
        M_gBase = None
    elif meteo == 'SHT31':
      import Adafruit_SHT31 as SHT
      useMeteo = SHT.SHT31(address=useMeteo['addr'], i2c=useMeteo['i2c']['fd'], calibrate=calibrate)
    else: # DHT serie not yet supported
      LED.blink(5,0.3,0xff0000,True)
      raise ValueError("Unknown meteo %s type" % meteo)
    if meteo[:3] == 'BME':
      useMeteo = BME.BME_I2C(useMeteo['i2c']['fd'], address=useMeteo['addr'], debug=False, calibrate=calibrate)
    if meteo == 'BME680':
      display('AQI wakeup')
      useMeteo.gas_base = M_gBase
      if useMeteo._gasBase: pass
      nl -= LF # undo lf
      # useMeteo.sea_level_pressure = 1011.25
    display('meteo: %s' % meteo)
  except Exception as e:
    useMeteo = None; meteo = ''
    display("meteo %s failure" % meteo, (0,0), clear=True)
    print(e)
if not useMeteo: display("No meteo")

# which UARTs are used for what
auto = False
try: from Config import useDust
except: useDust = True
try:
  if useDust: from Config import dust, D_Tx, D_Rx
except:
  print("Dust auto configured")
  auto = True
try: from Config import useGPS
except: useGPS = True
try:
  if useGPS: from Config import G_Tx, G_Rx
except:
  print("GPS auto configured")
  auto = True
if auto:
  import whichUART
  which = whichUART.identifyUART(uart=uart, debug=True)
  try:
    D_Tx = which.D_TX; D_Rx = which.D_Rx
    dust = which.DUST; useDust = True
  except: useDust = False
  try:
    G_Tx = which.G_Tx; G_Rx = which.G_Rx
    useGPS = which.GPS
  except: pass
  del auto; del which; del whichUART

if useDust:
  Dext = ''     #  count or weight display
  try:
    if dust[:3] == 'SDS':
      from SDS011 import SDS011 as senseDust
    elif dust[:3] == 'PMS':
      try: from Config import Dext
      except: pass
      from PMSx003 import PMSx003 as senseDust
    else:
      LED.blink(5,0.3,0xff0000,True)
      raise ValueError("Unknown dust sensor")
    useDust = senseDust(port=len(uart), debug=False, sample=sample_time, interval=0, pins=(D_Tx,D_Rx), calibrate=calibrate)
    uart.append(len(uart))
    print("%s UART %d: Rx ~> Tx %s, Tx ~> Rx %s" % (dust,len(uart),D_Tx, D_Rx))
  except Exception as e:
    display("%s failure" % dust, (0,0), clear=True)
    print(e)
    useDust = None; dust = ''
  display('dust: %s' % dust)
else:
  display("No PM sensing")
  dust = ''

# GPS config tuple (LAT,LON,ALT)
try:
  from Config import thisGPS
except:
  thisGPS = [0.0,0.0,0.0]
try:
  from Config import useGPS, G_Tx, G_Rx
except: pass
if not useGPS: display('No GPS')
else:
  try:
    import GPS_dexter as GPS
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
  except Exception as e:
    display('GPS failure', (0,0), clear=True)
    print(e)
    useGPS = None

lastGPS = thisGPS

if Network: display('Network: %s' % Network)

HALT = False
# called via TTN response
def CallBack(port,what):
  global sleep_time, HALT, oled, useDust, useMeteo, dust, Dext
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
    elif what == b'#':  # send partical cnt
        if dust[:3] == 'PMS': Dext = '_cnt'
    elif what == b'w': # send partical weight
        Dext = ''
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
  global Network, lora, LoRaMethod
  global sleep_time, STOP, myId
  global dust, meteo, thisGPS, useGPS, Dext

  display("MySense V %s" % __version__[:6], (0,0), clear=True)
  display("s/n " + myID)
  if Dext: display("PM pcs:" + dust)
  else: display("PM   : " + dust)
  display("meteo: " + meteo)
  if useGPS:
    display('G:%.4f/%.4f' % (thisGPS[LAT],thisGPS[LON]))
  sleep(15)

  if Network == 'TTN':
    # Connect to LoRaWAN
    display("Try  LoRaWan", (0,0), clear=True)
    lora = LORA()
    if lora.connect(LoRaMethod, ports=2, callback=CallBack):
       display("Using LoRaWan")
       SendInfo()
    else:
       display("NO LoRaWan")
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
  global useDust, dust, nl, STOP, STOPPED, useGPS, lastGPS, Dext
  dData = {}
  display('PM sensing',(0,0),clear=True,prt=False)
  if useDust and (useDust.mode != useDust.NORMAL):
    useDust.Normal()
    if not showSleep(secs=15,text='starting up fan'):
      display('stopped SENSING', (0,0), clear=True)
      LED.blink(5,0.3,0xff0000,True)
      return [0,0,0]
    else:
      if useGPS != None:
        display("G:%.4f/%.4f" % (lastGPS[LAT],lastGPS[LON]))
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
      display("%s ERROR" % dust)
      print(e)
      LED.blink(3,0.1,0xff0000)
      dData = {}
    LED.blink(3,0.1,0x00ff00)

  if len(dData):
    for k in dData.keys():
        if dData[k] == None: dData[k] = 0
    if not 'pm25'+Dext in dData.keys(): Dext = ''
    try:
      if 'pm1' in dData.keys():   #  and dData['pm1'] > 0:
        display(" PM1 PM2.5 PM10", (0,0), clear=True)
        display("% 2.1f % 5.1f% 5.1f" % (dData['pm1'],dData['pm25'],dData['pm10']))
      else:
        display("ug/m3 PM2.5 PM10", (0,0), clear=True)
        display("     % 5.1f % 5.1f" % (dData['pm25'],dData['pm10']))
        dData['pm1'+Dext] = 0
    except:
      dData = {}
  if (not dData) or (not len(dData)):
    display("No PM values")
    LED.blink(5,0.1,0xff0000,True)
    dData = [0,0,0]
  else:
    dData = [round(dData['pm1'+Dext],1),round(dData['pm25'+Dext],1),round(dData['pm10'+Dext],1)]
    LED.off()
  return dData

TEMP = const(0)
HUM  = const(1)
PRES = const(2)
GAS  = const(3)
AQI  = const(4)
def DoMeteo():
  global useMeteo, nl, LF
  global meteo,i2c
  mData = [0,0,0,0,0]
  if not useMeteo or not meteo: return mData

  # Measure BME280/680: temp oC, rel hum %, pres pHa, gas Ohm, aqi %
  LED.blink(3,0.1,0x002200,False)
  try:
    if (meteo == 'BME680') and (not useMeteo.gas_base): # BME680
      display("AQI base: wait"); nl -= LF
    #i2c[nr].init(nr, pins=i2cPINs[nr]) # SPI oled causes bus errors
    #sleep(1)
    mData = []
    for item in range(0,5):
        mData.append(0)
        for cnt in range(0,5): # try 5 times to avoid null reads
            try:
                if item == TEMP: # string '20.12'
                    mData[TEMP] = float(useMeteo.temperature)
                elif item == HUM: # string '25'
                    mData[HUM] = float(useMeteo.humidity)
                elif meteo[:3] != 'BME': break
                elif item == PRES: # string '1021'
                    mData[PRES] = float(useMeteo.pressure)
                elif meteo == 'BME680':
                    if item == GAS: mData[GAS] = float(useMeteo.gas)
                    elif item == AQI: mData[AQI] = round(float(useMeteo.AQI),1)
                break
            except OSError as e: # I2C bus error, try to recover
                print("OSerror %s on data nr %d" % (e,item))
                useMeteo['i2c']['fd'].init(I2C.MASTER, pins=useMeteo['i2c']['pins'])
                LED.blink(1,0.1,0xff6c00,False)
    # work around if device corrupts the I2C bus
    # useMeteo['i2c']['fd'].init(I2C.MASTER, pins=useMeteo['i2c']['pins'])
    sleep(0.5)
    rectangle(0,nl,128,LF,0)
  except Exception as e:
    display("%s ERROR" % meteo)
    print(e)
    LED.blink(5,0.1,0xff00ff,True)
    return [0,0,0,0,0]

  LED.off()
  # display results
  nl += 6  # oled spacing
  if meteo == 'BME680':
    title = "  C hum% pHa AQI"
    values = "% 2.1f %2d %4d %2d" % (round(mData[TEMP],1),round(mData[HUM]),round(mData[PRES]),round(mData[AQI]))
  elif meteo == 'BME280':
    title = "    C hum%  pHa"
    values = "% 3.1f  % 3d % 4d" % (round(mData[TEMP],1),round(mData[HUM]),round(mData[PRES]))
  else:
    title = "    C hum%"
    values = "% 3.1f  % 3d" % (round(mData[TEMP],1),round(mData[HUM]))
  display(title)
  display("o",(12,-5),prt=False)
  display(values)
  return mData # temp, hum, pres, gas, aqi

def DoPack(dData,mData,gps=None):
  if (type(gps) is list) and (gps[LAT] > 0.01):
    return struct.pack('>HHHHHHHHHlll',int(dData[PM1]*10),int(dData[PM25]*10),int(dData[PM10]*10),int(mData[TEMP]*10+300),int(mData[HUM]*10),int(mData[PRES]),int(round(mData[GAS]/100.0)),int(mData[AQI]*10),int(round(gps[LAT]*100000)),int(round(gps[LON]*100000)),int(round(gps[ALT]*10)))
  else:
    return struct.pack('>HHHHHHHHH',int(dData[PM1]*10),int(dData[PM25]*10),int(dData[PM10]*10),int(mData[TEMP]*10+300),int(mData[HUM]*10),int(mData[PRES]),int(round(mData[GAS]/100.0)),int(mData[AQI]*10))

def SendInfo(port=3):
  global  lora, meteo, dust, useGPS, thisGPS, lastGPS
  Meteo = ['','DHT11','DHT22','BME280','BME680','SHT31']
  Dust = ['None','PPD42NS','SDS011','PMSx003']
  if lora == None: return True
  if (not meteo) and (not dust) and (useGPS == None): return True
  sense = ((Meteo.index(meteo)&0xf)<<4) | (Dust.index(dust)&0x7)
  gps = 0
  if useGPS:
    # GPS 5 decimals: resolution 14 meters
    thisGPS[LAT] = round(float(useGPS.latitude),5)
    thisGPS[LON] = round(float(useGPS.longitude),5)
    thisGPS[ALT] = round(float(useGPS.altitude),1)
    lastGPS = thisGPS
    sense |= 0x8
  version = int(__version__[0])*10+int(__version__[2])
  data = struct.pack('>BBlll',version,sense, int(thisGPS[LAT]*100000),int(thisGPS[LON]*100000),int(thisGPS[ALT]*10))
  return lora.send(data,port=port)

def LocUpdate():
  global useGPS, lastGPS, LAT, LON, ALT
  if useGPS == None: return None
  location = [0.0,0.0,0.0]
  location[LAT] = round(float(useGPS.latitude),5)
  location[LON] = round(float(useGPS.longitude),5)
  location[ALT] = round(float(useGPS.altitude),1)
  if GPSdistance(location,lastGPS) <= 50.0:
    return None
  lastGPS = location
  return location

def runMe():
  global lora, sleep_time, oled
  global useDust

  setup() # Setup network & sensors

  while True:

    toSleep = time()
    dData = DoDust()
    mData = DoMeteo()

    # Send packet
    if lora != None:
      if  lora.send(DoPack(dData,mData,LocUpdate())):
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
    if not ProgressBar(0,62,128,1,toSleep,0xebcf5b,10):
      display('stopped SENSING', (0,0), clear=True)
      LED.blink(5,0.3,0xff0000,True)
    if STOP:
      sleep(60)
      oled.poweroff()
      # and put ESP in deep sleep: machine.deepsleep()
      return False

if __name__ == "__main__":
  runMe()
