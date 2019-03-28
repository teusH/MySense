# PyCom Micro Python / Python 3
# some code comes from https://github.com/TelenorStartIoT/lorawan-weather-station
# $Id: MySense.py,v 4.9 2019/03/28 21:25:17 teus Exp teus $
#
__version__ = "0." + "$Revision: 4.9 $"[11:-2]
__license__ = 'GPLV4'

from time import sleep, time
from time import localtime, timezone
from machine import Pin # user button/led
from machine import I2C
import struct
from micropython import const
from led import LED
import _thread
# _thread.stack_size(6144)
NoThreading = False
import os
PyCom = 'PyCom %s' % os.uname()[1]
del os
# Turn off hearbeat LED
import pycom
pycom.heartbeat(False)
del pycom

# enabled devices
# devices:
Display = { 'use': None, 'enabled': False, 'fd': None}
Meteo   = { 'use': None, 'enabled': False, 'fd': None}
Dust    = { 'use': None, 'enabled': False, 'fd': None}
Gps     = { 'use': None, 'enabled': False, 'fd': None}
Network = { 'use': None, 'enabled': False, 'fd': None}

LAT = const(0)
LON = const(1)
ALT = const(2)
lastGPS = [0.0,0.0,0.0]
thisGPS = [0.0,0.0,0.0] # configured GPS

# LoRa ports
# data port 2 old style and ug/m3, 4 new style grain, pm4/5 choice etc
Dprt = (2,4)    # data ports
Iprt = const(3) # info port, meta data

# oled is multithreaded
STOP = False
STOPPED = False

HALT = False  # stop by remote control
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
sleep_time -= sample_time
if sleep_time <= 0: sleep_time = 0.1

# calibrate dict with lists for sensors { 'temperature': [0,1], ...}
calibrate = {}
try:
  from Config import calibrate
except: pass

# # stop processing press user button
# button = Pin('P11',mode=Pin.IN, pull=Pin.PULL_UP)
# #led = Pin('P9',mode=Pin.OUT)
# #led.toggle()
#
# def pressed(what):
#   global STOP, LED
#   STOP = True
#   print("Pressed %s" % what)
#   LED.blink(5,0.1,0xff0000,False)
#
#
# button.callback(Pin.IRQ_FALLING|Pin.IRQ_HIGH_LEVEL,handler=pressed,arg='STOP')

# bus bookkeeping for devices
i2c = [ # {'pins': (SDA,SCL), 'fd': None}
    ]
I2Cdevices = [ # dflts
    ('BME280',0x76),('BME280',0x77), # BME serie Bosch
    ('SHT31',0x44),('SHT31',0x45),   # Sensirion serie
    ('SSD1306',0x3c)                 # oled display
    ]
spi = [ # {'pins': (SCKI,MOSI,MISO)}
    ]
uart = [-1]  # default number from 1
try:
    from Config import uart # allow P0,P1 pins?
except: pass

def chip_ID(i2c, address=0x77): # I2C dev optional ID
    chip_ID_ADDR = const(0xd0)
    # Create I2C device.
    if not type(i2c) is I2C:
      raise ValueError('An I2C object is required.')
    ID = 0 # 12 bits name, 9 bits part nr, 3 bits rev
    try: ID = i2c.readfrom_mem(address, chip_ID_ADDR, 3)
    except: pass
    # print("ID: ", ID)
    return int.from_bytes( ID,'little') & 0xFF

BME280_ID = const(0x60)
BME680_ID = const(0x61)
SSD1306_ID = const(0x3)

# hw search for I2C devices
def I2Cdevs(names=['BME','SHT','SSD'], debug=False):
    global I2Cdevices
    global Meteo, Display  # I2C devices
    if len(i2c) <= 0:
        try: from Config import I2Cpins
        except: I2Cpins = [('P23','P22')] # I2C pins [(SDA,SCL), ...]
        try: from Config import I2Cdevices
        except: pass
        for index in range(0,len(I2Cpins)):
            i2c.append({'fd': I2C(index, I2C.MASTER, pins=I2Cpins[index]), 'pins': I2Cpins[index]})
        names=['BME','SHT','SSD'] # initially get all
    fnd = False
    for index in range(0,len(i2c)):
        regs = i2c[index]['fd'].scan()
        for item in I2Cdevices:
            if item[1] in regs:
                if not item[0][:3] in names:
                    continue
                ID = chip_ID(i2c[index]['fd'], item[1])
                name = item[0]
                if (name[:3] == 'BME') and (ID == BME680_ID): name = 'BME680'
                if debug: print('%s id(0x%X) I2C[%d]:' % (name,ID,index), ' SDA ~> %s, SCL ~> %s' % i2c[index]['pins'], 'address 0x%2X' % item[1])
                if name[:3] in ['BME','SHT']:
                  fnd = True
                  if not 'i2c' in Meteo.keys():
                    Meteo.update({ 'i2c': i2c[index], 'name': name, 'addr': item[1] })
                    try: from Config import useMeteo
                    except: useMeteo = True
                    Meteo['use'] = True if useMeteo else False
                if name[:3] in ['SSD']:
                  fnd = True
                  if not 'i2c' in Display.keys():
                    Display.update({ 'i2c': i2c[index], 'name': name, 'addr': item[1] })
                    useDisplay = True; useSSD = True
                    try:
                        from Config import useSSD  # deprecated
                        if not useSSD: useDisplay = False
                    except:  pass
                    try: from Config import useDisplay
                    except: pass
                    Display['use'] = True if useDisplay else False
            # elif debug:
            #   print('sensor %s/%X not in I2C[%d]: %s' % (item[0][:3],item[1], index, ', '.join(names)))
    return fnd

def SPIdevs(pins,lookup): # collect SPI pins
  global spi
  if not lookup in pins:
    pins.append(lookup)
    spi.append(None)
  return pins.index(lookup)

# oled display on I2C bus error try again
def oledShow():
  global Display
  if not Display['fd']: return
  for cnt in range(0,3):
    try:
      Display['fd'].show()
      break
    except OSError:
      print("BusError: Init I2C bus")
      try: Display['i2c']['fd'].init(I2C.MASTER, pins=Display['i2c']['pins'])
      except: pass
      sleep(0.5)

nl = 16 # line height
LF = const(13)
# width = 128; height = 64  # display sizes
def display(txt,xy=(0,None),clear=False, prt=True):
  ''' Display Text on OLED '''
  global Display, nl
  if Display['fd']:
    offset = 0
    if xy[1] == None: y = nl
    elif xy[1] < 0:
      if -xy[1] < LF:
        offset = xy[1]
        y = nl - LF
    else: y = xy[1]
    x = 0 if ((xy[0] == None) or (xy[0] < 0)) else xy[0]
    if clear:
      Display['fd'].fill(0)
    if y > 56:
      nl =  y = 16
    if (not offset) and (not clear):
      rectangle(x,y,128,LF,0)
    Display['fd'].text(txt,x,y+offset)
    oledShow()
    if y == 0: nl = 16
    elif not offset: nl = y + LF
    if nl >= (64-13): nl = 16
  if prt: print(txt)

def rectangle(x,y,w,h,col=1):
  global Display
  dsp = Display['fd']
  if not dsp: return
  ex = int(x+w); ey = int(y+h)
  if ex > 128: ex = 128
  if ey > 64: ey = 64
  for xi in range(int(x),ex):
    for yi in range(int(y),ey):
      dsp.pixel(xi,yi,col)

def ProgressBar(x,y,width,height,secs,blink=0,slp=1):
  global Display, LED, STOP
  if not Display['fd']: return False
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

def showSleep(secs=60,text=None,inThread=False):
  global nl, STOP, STOPPED
  global Display
  ye = y = nl
  if text:
    display(text)
    ye += LF
  if Display['fd']:
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

# tiny display Adafruit 128 X 64 oled driver
def initDisplay(debug=False):
  global Display
  if Display['fd']: return True
  if Display['use'] == None:
      try:
        if not I2Cdevs(names=['SSD'], debug=debug):
          useDisplay = None
          try:
            from Config import useSSD  # deprecated
            useDisplay = useSSD
          except: pass
          try: from Config import useDisplay
          except: pass
          if useDisplay: Display['use'] = True
          if useDisplay.upper() == 'SPI': Display['spi'] = True
      except: pass
  if not Display['use']: return True  # initialize only once
  try:
      import SSD1306 as DISPLAY
      width = 128; height = 64  # display sizes
      if 'i2c' in Display.keys(): # display may flicker on reload
        Display['fd'] = DISPLAY.SSD1306_I2C(width,height,Display['i2c']['fd'], addr=Display['addr'])
        if debug: print('Oled %s:' % Display['name'] + ' SDA ~> %s, SCL ~> %s' % Display['i2c']['pins'])
      elif 'spi' in Display.keys(): # for fast display This needs rework for I2C style
        global spi, spiPINS
        try:
          from Config import S_CLKI, S_MOSI, S_MISO  # SPI pins config
        except:
          S_SCKI = 'P10'; S_MOSI = 'P11'; S_MISO = 'P14'  # SPI defaults
        if not len(spi): from machine import SPI
        try:
          from Config import S_DC, S_RES, S_CS      # GPIO SSD pins
        except:
          S_DC = 'P5'; S_RES = 'P6'; S_CS = 'P7'    # SSD defaults
        nr = SPIdevs(spiPINs,(S_DC,S_CS,S_RES,S_MOSI,S_CLKI))
        if spi[nr] == None:
          spi[nr] = SPI(nr,SPI.MASTER, baudrate=100000,pins=(S_CLKI, S_MOSI, S_MISO))
        Display['fd'] = DISPLAY.SSD1306_SPI(width,height,spi[nr],S_DC, S_RES, S_CS)
        if debug: print('Oled SPI %d: ' % nr + 'DC ~> %s, CS ~> %s, RES ~> %s, MOSI/D1 ~> %s, CLK/D0 ~> %s ' % spiPINs[nr] + 'MISO ~> %s' % S_MISO)
      else:
        Display['fd'] = None
        print("No SSD display or bus found")
      if Display['fd']:
        Display['enabled'] = True
        Display['fd'].fill(1); oledShow(); sleep(0.2)
        Display['fd'].fill(0); oledShow()
  except Exception as e:
      Display['fd'] = None
      print('Oled display failure: %s' % e)
      return False
  return True

# oled on SPI creates I2C bus errors
#  display('BME280 -> OFF', (0,0),True)

# start meteo sensor
def initMeteo(debug=False):
  global Meteo
  global calibrate
  if Meteo['enabled']: return True
  meteo = ''
  if I2Cdevs(names=['BME','SHT'],debug=debug) and (type(Meteo['i2c']) is dict):
    meteo = Meteo['name']
    try:
      if debug: print("Try %s" % meteo)
      if meteo == 'BME280':
          import BME280 as BME
          Meteo['fd'] = BME.BME_I2C(Meteo['i2c']['fd'], address=Meteo['addr'], debug=debug, calibrate=calibrate)
      elif meteo == 'BME680':
          import BME_I2C as BME
          Meteo['fd'] = BME.BME_I2C(Meteo['i2c']['fd'], address=Meteo['addr'], debug=debug, calibrate=calibrate)
          if not 'gas_base' in Meteo.keys():
            try:
               from Config import M_gBase
               Meteo['gas_base'] = int(M_gBase)
            except: pass
          if 'gas_base' in Meteo.keys():
              Meteo['fd'].gas_base = Meteo['gas_base']
          if not Meteo['fd'].gas_base:
              display('AQI wakeup')
              Meteo['fd'].AQI # first time can take a while
              Meteo['gas_base'] = Meteo['fd'].gas_base
          display("Gas base: %0.1f" % Meteo['fd'].gas_base)
          # Meteo['fd'].sea_level_pressure = 1011.25
      elif meteo[:3] == 'SHT':
        import Adafruit_SHT31 as SHT
        meteo = 'SHT31'
        Meteo['fd'] = SHT.SHT31(address=Meteo['addr'], i2c=Meteo['i2c']['fd'], calibrate=calibrate)
      else: # DHT serie not yet supported
        LED.blink(5,0.3,0xff0000,True)
        raise ValueError("Unknown meteo %s type" % meteo)
      Meteo['enabled'] = True
      Meteo['name'] = meteo
      if debug: print('meteo: %s' % Meteo['name'])
    except Exception as e:
      Meteo['use'] = False
      display("meteo %s failure" % meteo, (0,0), clear=True)
      print(e)
  if not Meteo['use']:
    if debug: print("No meteo in use")
    return False
  return True

# which devices use which UART pins
def UARTdevs(debug=False):
  global Dust, Gps # uart devices
  if Dust['use'] != None: return True
  auto = False
  useDust = True
  try: from Config import useDust
  except: pass
  try: from Config import dust
  except: dust = 'PMS'
  Dust['name'] = dust
  try:
    if useDust:
        Dust['use'] = True
        from Config import D_Tx, D_Rx
        Dust['pins'] = (D_Tx,D_Rx)
  except:
    if debug: print("Dust auto configured")
    auto = True
  useGPS = False
  try: from Config import useGPS
  except: useGPS = True
  Gps['name'] = 'NEO 6'
  try:
    if useGPS:
        Gps['use'] = True
        from Config import G_Tx, G_Rx
        Gps['pins'] = (G_Tx,G_Rx)
  except:
    if debug: print("GPS auto configured")
    auto = True
  if auto:
    UARTpins=[('P4','P3'),('P11','P10')] # dflt
    try: from Config import UARTpins
    except: pass
    import whichUART
    which = whichUART.identifyUART(uart=uart, UARTpins=UARTpins, debug=debug)
    try:
      Dust['pins'] = (which.D_TX, which.D_Rx)
      Dust['name'] = which.DUST
    except: Dust['use'] = False
    try:
      Gps['pins'] = (which.G_Tx, which.G_Rx)
      Gps['name'] = which.GPS if which.GPS.upper() != 'UART' else 'NEO 6'
    except: Gps['use'] = False
    del whichUART
  return True

def initDust(debug=False):
  global calibrate, sample_time, uart
  global Dust
  if Dust['enabled']: return True
  if Dust['use'] == None: UARTdevs(debug=debug)
  if Dust['use']:
    # initialize dust: import relevant dust library
    Dust['cnt'] = False # dflt do not show PM cnt
    try:
      if Dust['name'][:3] == 'SDS':    # Nova
        from SDS011 import SDS011 as senseDust
      elif Dust['name'][:3] == 'SPS':  # Sensirion
        from SPS30 import SPS30 as sensedust
      elif Dust['name'][:3] == 'PMS':  # Plantower
        from PMSx003 import PMSx003 as senseDust
      else:
        LED.blink(5,0.3,0xff0000,True)
        raise ValueError("Unknown dust sensor")
      try:
        from Config import Dext # show also pm counts
        if Dext: Dust['cnt'] = True
      except: pass
      # #pcs=range(PM0.3-PM) + average grain size, True #pcs>PM
      Dust['expl'] = False
      try:
        from Config import Dexplicit
        if Dexplicit:  Dust['expl'] = True
      except: pass
      Dust['fd'] = senseDust(port=len(uart), debug=debug, sample=sample_time, interval=0, pins=Dust['pins'], calibrate=calibrate, explicit=Dust['expl'])
      uart.append(len(uart))
      if debug:
        print("%s UART %d: " % (Dust['name'],len(uart)) + "Rx ~> Tx %s, Tx ~> Rx %s" % Dust['pins'])
    except Exception as e:
      display("%s failure" % Dust['name'], (0,0), clear=True)
      print(e)
      useDust = None; Dust['name'] = ''
    if debug: print('dust: %s' % Dust['name'])
  elif debug: print("No dust in use")
  Dust['enabled'] = True if Dust['fd'] else False
  return Dust['use']

# initialize GPS: GPS config tuple (LAT,LON,ALT)
def initGPS(debug=False):
  global thisGPS, lastGPS, uart
  global Gps
  if Gps['enabled']: return True
  if Gps['use'] == None: UARTdevs(debug=debug)
  Gps['enabled'] = False
  if not Gps['use']:
      display('No GPS')
      return False
  try: from Config import thisGPS # predefined GPS coord
  except: pass
  try:
      import GPS_dexter as GPS
      Gps['fd'] = GPS.GROVEGPS(port=len(uart),baud=9600,debug=debug,pins=Gps['pins'])
      uart.append(len(uart))
      if debug: print("GPS UART %d: " % len(uart) + "Rx ~> Tx %s, Tx ~> Rx %s" % Gps['pins'])
      Gps['enabled'] = True
      if debug: print("Try date/RTC update")
      if not Gps['fd'].date:
        Gps['fd'].UpdateRTC()
      if Gps['fd'].date:
        now = localtime()
        if 3 < now[1] < 11: timezone(7200) # simple DST
        else: timezone(3600)
        display('%d/%d/%d %s' % (now[0],now[1],now[2],('mo','tu','we','th','fr','sa','su')[now[6]]))
        display('time %02d:%02d:%02d' % (now[3],now[4],now[5]))
        if debug: print("Get coordinates")
        thisGPS[LON] = round(float(Gps['fd'].longitude),5)
        thisGPS[LAT] = round(float(Gps['fd'].latitude),5)
        thisGPS[ALT] = round(float(Gps['fd'].altitude),1)
      else:
        display('GPS bad QA %d' % Gps['fd'].quality)
        Gps['fd'].ser.deinit(); Gps['fd'] = None
        Gps['enabled'] = False
  except Exception as e:
      display('GPS failure', (0,0), clear=True)
      print(e)
      Gps['enabled'] = False; Gps['fd'].ser.deinit(); Gps['fd'] = None
  lastGPS = thisGPS[0:]
  return Gps['enabled']

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

def LocUpdate():
  global Gps, lastGPS, LAT, LON, ALT
  if not Gps['use']: return None
  location = [0.0,0.0,0.0]
  if (not Gps['enabled']) or (not Gps['fd']): return None
  location[LAT] = round(float(Gps['fd'].latitude),5)
  location[LON] = round(float(Gps['fd'].longitude),5)
  location[ALT] = round(float(Gps['fd'].altitude),1)
  if GPSdistance(location,lastGPS) <= 50.0:
    return None
  lastGPS = location
  return location

# called via TTN response
# To Do: make the remote control survive a reboot
def CallBack(port,what):
  global sleep_time, HALT
  global Display, Dust, Meteo
  if not len(what): return True
  if len(what) < 2:
    if what == b'?': return SendInfo(port)
    elif what == b'O': Display['fd'].poweroff()
    elif what == b'd':
      if Dust['use']:
        Dust['raw'] = True # try: Dust['fd'].gase_base = None
    elif what == b'D':
      if Dust['use']:
        Dust['raw'] = False # try: Dust['fd'].gase_base = None
    elif what == b'm':
        if Meteo['use']: Meteo['raw'] = True
    elif what == b'M':
        if Meteo['use']: Meteo['raw'] = False
    elif what == b'S': HALT = True
    elif what == b'#':  # send partical cnt
        if Dust['name'][:3] != 'SDS': Dust['cnt'] = True
    elif what == b'w': # send partical weight
        Dust['cnt'] = False
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
def initNetwork(debug=False):
  global Network

  def whichNet(debug=False):
    global Network
    Network['use'] = False
    Network['enabled'] = False
    try:
      from Config import Network as net
      Network['name'] = net
      Network['use'] = True
    except:
      net = None
    if Network['name'] == 'TTN':
      Network['keys'] = {}
      try:
          from Config import dev_eui, app_eui, app_key
          Network['keys']['OTAA'] = (dev_eui, app_eui, app_key)
      except: pass
      try:
          from Config import dev_addr, nwk_swkey, app_swkey
          Network['keys']['ABP'] = (dev_addr, nwk_swkey, app_swkey)
      except: pass
      if not len(Network['keys']):
        pycom.rgbled(0xFF0000)
        display('LoRa config failure')
        return False
      if debug: print("LoRa: ", Network['keys'])
      return True
    print("No network found")
    return False

  if Network['enabled']: return True   # init only once
  if not whichNet(debug=debug): return False
  if Network['name'] == 'TTN':
    if not len(Network['keys']): return False
    from lora import LORA
    Network['fd'] = LORA()
    # Connect to LoRaWAN
    display("Try  LoRaWan", (0,0), clear=True)
    # need 2 ports: data on 4, info/ident on 3
    if Network['fd'].connect(Network['keys'], ports=(len(Dprt)+1), callback=CallBack):
       display("Using LoRaWan")
       Network ['enabled'] = True
    else:
       display("NO LoRaWan")
       Network['fd'] = None
       Network ['enabled'] = False
    sleep(10)
  if Network == 'None':
    display("No network!", (0,0), clear=True)
    LED.blink(10,0.3,0xff00ff,True)
    # raise OSError("No connectivity")
  else: enNetwork = True
  return enNetwork

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
  global Dust, nl, STOP, STOPPED, Gps, lastGPS
  dData = {}; rData = [None,None,None]
  # if Meteo['use'] == None: initMeteo(debug=debug)
  if (not Dust['use']) or (not Dust['enabled']): return rData

  display('PM sensing',(0,0),clear=True,prt=False)
  if Dust['enabled'] and (Dust['fd'].mode != Dust['fd'].NORMAL):
    Dust['fd'].Normal()
    if not showSleep(secs=15,text='starting up fan'):
      display('stopped SENSING', (0,0), clear=True)
      LED.blink(5,0.3,0xff0000,True)
      return rData
    else:
      if Gps['enabled']:
        display("G:%.4f/%.4f" % (lastGPS[LAT],lastGPS[LON]))
      display('measure PM')
  if Dust['enabled']:
    LED.blink(3,0.1,0x005500)
    # display('%d sec sample' % sample_time,prt=False)
    try:
      STOPPED = False
      try:
        SleepThread(sample_time,'%d sec sample' % sample_time)
      except:
        STOPPED = True
        display('%d sec sample' % sample_time)
      dData = Dust['fd'].getData()
      for cnt in range(10):
        if STOPPED: break
        STOP = True
        print('waiting for thread')
        sleep(2)
      STOP = False
    except Exception as e:
      display("%s ERROR" % Dust['name'])
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
  if (not dData) or (not len(dData)):
    display("No PM values")
    LED.blink(5,0.1,0xff0000,True)
  else:
    rData = []
    for k in ['pm1','pm25','pm10']:
      rData.append(round(dData[k],1) if k in dData.keys() else None)
    
    if Dust['cnt']:
      cnttypes = ['03','05','1','25','5','10']
      if Dust['name'][:3] == 'SPS': cnttypes[4] = '4'
      for k in cnttypes:
        if 'pm'+k+'_cnt' in dData.keys():
            rData.append(round(dData['pm'+k+'_cnt'],1))
        else: rData.append(0.0) # None
      if not Dust['expl']:  # PM0.3 < # pcs <PMi
        rData[3] = round(dData['grain'],2) # PM0.3 overwritten
        # print('pm grain: %0.2f' % dData['grain'])
    LED.off()
  return rData

TEMP = const(0)
HUM  = const(1)
PRES = const(2)
GAS  = const(3)
AQI  = const(4)
def DoMeteo(debug=False):
  global Meteo, nl, LF
  global i2c

  def convertFloat(val):
    return (0 if val is None else float(val))

  mData = [None,None,None,None,None]
  if Meteo['use'] == None: initMeteo(debug=debug)
  if (not Meteo['use']) or (not Meteo['enabled']): return mData

  # Measure BME280/680: temp oC, rel hum %, pres pHa, gas Ohm, aqi %
  LED.blink(3,0.1,0x002200,False)
  try:
    if (Meteo['name'] == 'BME680') and (not Meteo['fd'].gas_base): # BME680
      display("AQI base: wait"); nl -= LF
    #Meteo['i2c']['fd'].init(nr, pins=Meteo['i2c']['pins']) # SPI oled causes bus errors
    #sleep(1)
    mData = []
    for item in range(0,5):
        mData.append(0)
        for cnt in range(0,5): # try 5 times to avoid null reads
            try:
                if item == TEMP: # string '20.12'
                    mData[TEMP] = convertFloat(Meteo['fd'].temperature)
                elif item == HUM: # string '25'
                    mData[HUM] = convertFloat(Meteo['fd'].humidity)
                elif Meteo['name'][:3] != 'BME': break
                elif item == PRES: # string '1021'
                    mData[PRES] = convertFloat(Meteo['fd'].pressure)
                elif Meteo['name'] == 'BME680':
                    if item == GAS: mData[GAS] = convertFloat(Meteo['fd'].gas)
                    elif item == AQI:
                        mData[AQI] = round(convertFloat(Meteo['fd'].AQI),1)
                        if not 'gas_base' in Meteo.keys():
                            Meteo['gas_base'] = Meteo['fd'].gas_base
                break
            except OSError as e: # I2C bus error, try to recover
                print("OSerror %s on data nr %d" % (e,item))
                Meteo['i2c']['fd'].init(I2C.MASTER, pins=Meteo['i2c']['pins'])
                LED.blink(1,0.1,0xff6c00,False)
    # work around if device corrupts the I2C bus
    # Meteo['i2c']['fd'].init(I2C.MASTER, pins=Meteo['i2c']['pins'])
    sleep(0.5)
    rectangle(0,nl,128,LF,0)
  except Exception as e:
    display("%s ERROR" % Meteo['name'])
    print(e)
    LED.blink(5,0.1,0xff00ff,True)
    return [None,None,None,None,None]

  LED.off()
  # display results
  nl += 6  # oled spacing
  if Meteo['name'] == 'BME680':
    title = "  C hum% pHa AQI"
    values = "% 2.1f %2d %4d %2d" % (round(mData[TEMP],1),round(mData[HUM]),round(mData[PRES]),round(mData[AQI]))
  elif Meteo['name'] == 'BME280':
    title = "    C hum%  pHa"
    values = "% 3.1f  % 3d % 4d" % (round(mData[TEMP],1),round(mData[HUM]),round(mData[PRES]))
  else:
    title = "    C hum%"
    values = "% 3.1f  % 3d" % (round(mData[TEMP],1),round(mData[HUM]))
  display(title)
  display("o",(12,-5),prt=False)
  display(values)
  return mData # temp, hum, pres, gas, aqi

# denote a null value with all ones
# denote which sensor values present in data package
def DoPack(dData,mData,gps=None,debug=False):
  global Dust
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
  if ('cnt' in Dust.keys()) and Dust['cnt']: # add counts
    # defeat: Plantower PM5c == Sensirion PM4c: to do: set flag in PM5c
    flg = 0x8000 if Dust['name'][:3] in ['SPS',] else 0x0
    try:
      if Dust['expl']:
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
      LED.blink(5,0.2,0xFF0000,False)
    t += 2
  m = struct.pack('>HHH',int(mData[TEMP]*10+300),int(mData[HUM]*10),int(mData[PRES]))
  if len(mData) > 3:
    m += struct.pack('>HH',int(round(mData[GAS]/100.0)),int(mData[AQI]*10))
    t += 4
  if (type(gps) is list) and (gps[LAT] > 0.01):
    l = struct.pack('>lll', int(round(gps[LAT]*100000)),int(round(gps[LON]*100000)),int(round(gps[ALT]*10)))
    t += 8
  else: l = ''
  # return d+m+l
  t = struct.pack('>B', t | 0x80) # flag the package
  return t+d+m+l # flag the package

# send kit info to LoRaWan
def SendInfo(port=Iprt):
  global Meteo, Dust, Network
  global Gps, lastGPS, thisGPS
  meteo = ['','DHT11','DHT22','BME280','BME680','SHT31']
  dust = ['None','PPD42NS','SDS011','PMSx003','SPS30']
  print("meteo: %s, dust: %s" %(Meteo['name'],Dust['name']))
  if Network['fd'] == None: return False
  if (not Meteo['enabled']) and (not Dust['enabled']) and (not Gps['enabled']):
    return True
  sense = ((meteo.index(Meteo['name'])&0xf)<<4) | (dust.index(Dust['name'])&0x7)
  gps = 0
  if Gps['enabled']:
    # GPS 5 decimals: resolution 14 meters
    try:
      thisGPS[LAT] = round(float(Gps['fd'].latitude),5)
      thisGPS[LON] = round(float(Gps['fd'].longitude),5)
      thisGPS[ALT] = round(float(Gps['fd'].altitude),1)
      lastGPS = thisGPS[0:]
    except: pass
    sense |= 0x8
  version = int(__version__[0])*10+int(__version__[2])
  data = struct.pack('>BBlll',version,sense, int(thisGPS[LAT]*100000),int(thisGPS[LON]*100000),int(thisGPS[ALT]*10))
  return Network['fd'].send(data,port=port)

# startup info
def Info(debug=False):
  global sleep_time, STOP
  global Network
  global Dust
  global lastGPS
  global Meteo

  try:
    # connect I2C devices
    initDisplay(debug=debug)

    import os
    display('%s' % PyCom, (0,0),clear=True)
    display("MySense %s" % __version__[:8], (0,0), clear=True)
    from machine import unique_id
    import binascii
    # identity PyCom SN
    display("s/n " + binascii.hexlify(unique_id()).decode('utf-8'))
    del unique_id, binascii

    if initDust(debug=debug):
        if Dust['cnt']: display("PM pcs:" + Dust['name'])
        else: display("PM   : " + Dust['name'])
    else: display("No dust sensor")

    if initMeteo(debug=debug):
        display("meteo: " + Meteo['name'])
    else: display("No meteo sensor")

    sleep(15)
    if not initGPS(debug=debug):
        display("No GPS")
    display('G:%.4f/%.4f' % (lastGPS[LAT],lastGPS[LON]))

    if initNetwork(debug=debug):
        display('Network: %s' % Network['name'])
    else: display("No network")
    if Network['enabled']: SendInfo()

  except Exception as e:
    # pycom.rgbled(0xFF0000)
    display("ERROR %s" % e)
    return False
  return True

# main loop
def runMe(debug=False):
  global sleep_time
  global Dust
  global Meteo

  if not Info(debug=debug): # initialize devices and show initial info
    print("FATAL ERROR")
    return False

  while True: # LOOP forever

    toSleep = time()
    if Dust['enabled']: dData = DoDust(debug=debug)
    if Meteo['enabled']: mData = DoMeteo(debug=debug)

    # Send packet
    if Network['enabled']:
        if (Network['name'] == 'TTN'):
          if ('cnt' in Dust.keys()) and Dust['cnt']: port=Dprt[1]
          else: port=Dprt[0]
          if  Network['fd'].send(DoPack(dData,mData,LocUpdate(),debug=debug),port=port):
            LED.off()
          else:
            display(" LoRa send ERROR")
            LED.blink(5,0.2,0x9c5c00,False)
        else: LED.blink(2,0.2,0xFF0000,False)

    toSleep = sleep_time - (time() - toSleep)
    if Dust['enabled']:
      if toSleep > 30:
        toSleep -= 15
        Dust['fd'].Standby()   # switch off laser and fan
      elif toSleep < 15: toSleep = 15
    if not ProgressBar(0,62,128,1,toSleep,0xebcf5b,10):
      display('stopped SENSING', (0,0), clear=True)
      LED.blink(5,0.3,0xff0000,True)
    if STOP:
      sleep(60)
      Display['fd'].poweroff()
      # and put ESP in deep sleep: machine.deepsleep()
      return False

if __name__ == "__main__":
  runMe(debug=True)
