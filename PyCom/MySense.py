# should be main.py
# some code comes from https://github.com/TelenorStartIoT/lorawan-weather-station
# $Id: MySense.py,v 1.1 2018/03/28 15:11:27 teus Exp teus $
#
try:
  from Config import Network
except:
  pass
if not Network: raise OSError("No network config found")
if Network == 'TTN':
  from Config import dev_eui, app_eui, app_key
  from lora import LORA
  lora = None

from led import LED

from time import sleep, time
from time import gmtime, localtime, timezone
from machine import Pin # user button/led
from machine import unique_id
import binascii
import pycom
import struct
from micropython import const

STOP = False
sample_time = 60        # 60 seconds sampling for dust
sleep_time = 5*60       # 5 minutes between sampling
# identity PyCom SN
myID = binascii.hexlify(unique_id()).decode('utf-8')
# Turn off hearbeat LED
pycom.heartbeat(False)

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
def display(txt,x,y,clear, prt=True):
  ''' Display Text on OLED '''
  global use_oled, oled
  if oled != None:
    if clear:
      oled.fill(0)
    oled.text(txt,x,y)
    oled.show()
  if prt:
    print(txt)

def rectangle(x,y,w,h,col=1):
  global oled
  ex = int(x+w); ey = int(y+h)
  for xi in range(int(x),ex):
    for yi in range(int(y),ey):
      oled.pixel(xi,yi,col)

def ProgressBar(x,y,width,height,secs,blink=0,slp=1):
  global oled, LED, STOP
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

# configure the MySense satellite sensor kit
i2c = [None,None,None]
psi = [None,None,None]
uart = [-1]

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
      from Config import S_ID, S_SDA, S_SCL # I2C pin config
      from machine import I2C
      print('Oled I2C: SDA~%s, SCL~%s' % (S_SDA,S_SCL))
      if not i2c[S_ID]: i2c[S_ID] = I2C(S_ID,I2C.MASTER,pins=(S_SDA,S_SCL))
      oled = SSD1306.SSD1306_I2C(width,height,i2c[S_ID])
    elif useSSD == 'SPI': # for fast display
      try:
        from Config import S_CLKI, S_MOSI, S_MISO  # SPI pins config
      except:
        S_SCKI = 'P10'; S_MOSI = 'P11'; S_MISO = 'P14'  # SPI defaults
      try:
        from Config import S_DC, S_RES, S_CS      # GPIO SSD pins
      except:
        S_DC = 'P5'; S_RES = 'P6'; S_CS = 'P7'    # SSD defaults
      from machine import SPI
      print('Oled SPI: DC~%s, CS~%s, RST~%s, D1~%s, D0~%s' % (S_DC,S_CS,S_RES,S_MOSI,S_CLKI))
      spi[0] = SPI(0,SPI.MASTER, baudrate=100000,pins=(S_CLKI, S_MOSI, S_MISO))
      oled = SSD1306.SSD1306_SPI(width,height,spi[0],S_DC, S_RES, S_CS)
    else:
      oled = None
      print("Incorrect display bus %s" % useSSD)
    if oled:
      oled.fill(1) ; oled.show(); sleep_ms(1000)
      oled.fill(0); oled.show()
  except:
    oled = None
    print('Oled display failed')
display('MySense config',0,0,True)

# oled on SPI creates I2C bus errors
#  display('BME280 -> OFF',0,0,True)
# Connect Sensors

Meteo = ['','DHT11','DHT22','BME280','BME680']
try:
  from Config import useMeteo
except:
  useMeteo = None
if useMeteo != 'I2C': useMeteo = None
if useMeteo:
  try:
    from Config import meteo, M_ID, M_SDA, M_SCL
  except:
    useMeteo = None
if useMeteo:
  try:
    if not i2c[S_ID]: i2c[S_ID] = I2C(S_ID,I2C.MASTER,pins=(M_SDA,M_SCL))
    if meteo == 3: # BME280
      import BME280
      useMeteo = BME280(i2c=i2c[S_ID],address=0x76)
    elif meteo == 4: # BME680
      import BME680
      useMeteo = BME680.Adafruit_BME680_I2C(i2c[S_ID], address=0x76, debug=False)
      display('AQI wakeup',0,16,False)
      if useMeteo._gasBase: display('          ',0,0,16)
      # useMeteo.sea_level_pressure = 1011.25
  except Exception as e:
    useMeteo = None
    display("%s setup error" % Meteo[meteo], 5, 16, False)
    print(e)
if useMeteo: display('meteo: %s' % Meteo[meteo],0,16, False)

Dust = ['','PPD42NS','SDS011','PMS7003']
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
      import SDS011 as senseDust
    elif dust == 3:
      from PMSx003 import PMSx003 as senseDust
      useDust = senseDust(port=len(uart), debug=True, sample=60, interval=0, pins=(D_Tx,D_Rx))
      uart.append(len(uart))
    else: raise OSError("Dust index")
  except Exception as e:
    display("%s setup error" % Dust[dust], 5, 30, False)
    useDust = None
if useDust: display('dust: %s' % Dust[dust],0, 30, False)

# GPS config
lonGPS = 0.0; latGPS = 0.0
try:
  from Config import useGPS, G_Tx, G_Rx
  import GPS_dexter as GPS
  useGPS = GPS.GROVEGPS(port=len(uart),baud=9600,debug=False,pins=(G_Tx,G_Rx))
  if useGPS.UpdateRTC():
    timezone(3600)
    now = gmtime(localtime())
    display('%d/%d/%d %d:%d' % (now[0],now[1],now[2],now[3],now[4]), 0, 44, False)
    lonGPS = useGPS.longitude; latGPS = useGPS.latitude
    sleep(30)
except:
  display('No GPS', 0,44,False)
  useGPS = 0

# called via TTN response
def CallBack(port,what): 
  global sleep_time, STOP, oled
  if not len(what): return True
  if len(what) < 2:
    if what == b'?': return SendInfo(port)
    if what == b'O': oled.poweroff()
    if what == b'S':
      STOP = TRUE
      return
    return False
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
  global lora, sleep_time, STOP, myId, dust, meteo

  display("MySense %s" % Network,0,0,True)
  display("s/n " + myID, 0, 16, False)
  display("dust:  " + Dust[dust], 0, 30, False)
  display("meteo: " + Meteo[meteo], 0, 44, False)
  if useGPS: display('GPS %.3f/%.3f' % (lonGPS.latGPS), 0, 54, False)
  sleep(30)

  if Network == 'TTN':
    # Connect to LoRaWAN
    display("Try  LoRaWan", 0, 0, True)
    display("LoRa App EUI:", 0, 16, False)
    display(str(app_eui), 0, 30, False)
    lora = LORA()
    if lora.connect(dev_eui, app_eui, app_key, ports=2, callback=CallBack):
       display("Joined LoRaWan", 0, 44, False)
       SendInfo()
    else:
       display("NOT joined LoRa!", 0, 44, False)
       raise OSError("No connectivity")
    sleep(10)
  else:
    display("No network!", 0, 0, True)
    raise OSError("No connectivity")
  display("Setup done", 0, 0, True)

PM1 = const(0)
PM25 = const(1)
PM10 = const(2)
def DoDust():
  global useDust, Dust, dust
  dData = {}
  if useDust and (useDust.mode != useDust.ACTIVE):
    useDust.Go_Active()
    display('starting up fan', 5, 30, False)
    if not ProgressBar(0,44,128,14,15,0x004400):
      display('stopped SENSING',0,0,True)
      LED.blink(5,0.3,0xff0000,True,True)
      return [0,0,0]
  if useDust:
    LED.blink(3,0.1,0x005500)
    try:
      dData = useDust.getData()
    except Exception as e:
      display("Dust %s error" % Dust[dust],0,0,True)
      print(e)
      LED.blink(3,0.1,0xff0000)
      dData = {}
    LED.blink(3,0.1,0x00ff00)

  if dData:
    for k in dData.keys():
        if dData[k] == None: dData[k] = 0
    try:
      if 'pm1' in dData.keys() and dData['pm1'] > 0:
        display(" PM1 PM2.5 PM10", 0,  0, True)
        display("% 3.1f % 4.1f% 4.1f" % (dData['pm1'],dData['pm25'],dData['pm10']),  0, 16, False)
      else:
        display("ug/m3 PM2.5 PM10", 0,  0, True)
        display("     % 5.1f % 5.1f" % (dData['pm25'],dData['pm10']),  0, 16, False)
        dData['pm1'] = 0
    except:
      dData = {}
  if not dData:
    display("No dust values", 0, 0, True)
    LED.blink(5,0.1,0xff0000,True)
    dData = [0,0,0]
  else:
    dData = [int(round(dData['pm1'])),int(round(dData['pm25'])),int(round(dData['pm10']))]
  return dData

TEMP = const(0)
HUM = const(1)
PRES = const(2)
GAS = const(3)
AQI = const(4)
def DoMeteo():
  global useMeteo  
  global Meteo, meteo
  mData = [0,0,0,0,0]
  if not useMeteo or not meteo: return mData

  # Measure temp oC, rel hum %, pres pHa, gas Ohm, aqi %
  LED.blink(3,0.1,0x002200)
  try: 
    if oled: i2c[S_ID].init(S_ID, pins=(S_SDA,S_SCL))
    mData[TEMP] = float(useMeteo.temperature) # string '20.12'
    mData[HUM] = float(useMeteo.humidity)    # string '25'
    mData[PRES] = float(useMeteo.pressure)    # string '1021.60'
    if meteo == 4: # BME680
      mData[GAS] = float(useMeteo.gas)
      mData[AQI] = round(float(useMeteo.AQI),1)
  except Exception as e:
    display("Meteo %s error" % Meteo[meteo],0,0,True)
    print(e)
    LED.blink(5,0.1,0xff00ff,True)
    return [0,0,0,0,0]

  if mData[gas] > 0:
    display(" C hum pHa AQI", 0, 34, False)
    display("o",              0, 30, False,False)
    display("% 3d % 2d % 4d % 2d" % (int(round(mData[TEMP])),int(round(mData[HUM])),int(round(mData[PRES])),int(round(mData[AQI]))),0, 48, False)
  else:
    display("   C hum pHa", 0, 34, False)
    display("  o",              0, 30, False,False)
    display("% 3.1 % 2d % 4d" % (round(mData[TEMP],1),int(round(mData[HUM])),int(round(mData[PRES]))),0, 48, False)
  return mData

def DoPack(dData,mData):
  global meteo, dust
  return struct.pack('>HHHHHHHHH',int(dData[PM1]*10),int(dData[PM25]*10),int(dData[PM10]*10),int(mData[TEMP]*10+30),int(mData[HUM]*10),int(mData[PRES]),int(round(mData[GAS]/100.0)),int(mData[AQI]*10))

LATITUDE = const(0)
LONGITUDE = const(1)
def SendInfo(port=3):
  global  lora, meteo, dust, useGPS
  location = [0,0]
  if (not meteo) and (not dust) and (type(useGPS) is None): return [0,0]
  if not type(useGPS) is None:
    location[LONGITUDE] = float(useGPS.longitude)
    location[LATITUDE] = float(useGPS.latitude)
  if lora:
    data = struct.pack('>BHH',((meteo&07)<<4)|(dust&07), int(location[LATITUDE]*100000),int(location[LONGITUDE]*100000))
    lora.send(data,port=port)
  return location

def runMe():
  global lora, sleep_time, oled
  global useDust
  # Setup network & sensors
  setup()

  while True:
    display("Sensing...",0,0, True)

    toSleep = time()
    dData = DoDust()
    mData = DoMeteo()

    # Send packet
    if lora.send(DoPack(dData,mData)):
      LED.off()
    else:
      display(" LoRa send ERROR",0,50,False)
      LED.blink(5,0.2,0x9c5c00,False)

    toSleep = sleep_time - (time() - toSleep)
    if toSleep > 30:
      toSleep -= 15
      useDust.Standby()   # switch off laser and fan
    elif toSleep < 15: toSleep = 15
    if not ProgressBar(0,63,128,2,toSleep,0xebcf5b,10):
      display('stopped SENSING',0,0,True,True)
      LED.blink(5,0.3,0xff0000,True,True)
    if STOP:
      sleep(60)
      oled.poweroff()
      # and put ESP in deep sleep: machine.deepsleep()
      return False

if __name__ == "__main__":
  runMe()
