# should be main.py
# some code comes from https://github.com/TelenorStartIoT/lorawan-weather-station
# $Id: sense.py,v 1.5 2018/03/04 15:12:10 teus Exp teus $
#
from LoRaConfig import dev_eui, app_eui, app_key
from lora import LORA
from time import sleep
from time import time
import pycom
import struct
from led import LED
# import base64

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
  global oled, LED
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
    sleep(myslp)
    if x > xe: continue
    rectangle(x,y,step,height)
    oled.show()
    x += step

# tiny display Adafruit 128 X 64 oled
use_oled = True
oled = None
if use_oled:
  from machine import SPI   # ssd1306 display via GPIO
  import ssd1306
  # red P24 3v3 and black P25 Gnd
  # SPI pins
  S_CLK  = 'P19'  # brown D0
  S_MOSI = 'P23'  # white D1
  S_MISO = 'P18'  # NC
  # SSD pins
  S_DC   = 'P20'  # purple DC
  S_RES  = 'P21'  # gray   RES
  S_CS   = 'P22'  # blew   CS
  try:
    # spi = SPI(0,SPI.MASTER, baudrate=100000, parity=0, phase=0, pins=('P10', 'P11', 'P14'))
    spi = SPI(0,SPI.MASTER, baudrate=100000,pins=(S_CLK, S_MOSI, S_MISO))
    # oled display: defaults dc = P5, res = P6, cs = P7
    oled = ssd1306.SSD1306_SPI(128,64,spi,S_DC, S_RES, S_CS)
  except:
    print("Failed to initiate oled display")
    oled = None ; use_oled = False

use_bme280 = True
# oled creates I2C bus errors
#if use_oled and use_bme280:
#  use_bme280 = False
#  display('BME280 -> OFF',0,0,True)
# Connect Sensors
sensor_bme280 = None
if use_bme280:
  try:
    # pins SDA P9/GPIO12, SCL P10/GPIO13
    from machine import I2C
    from BME280 import *
    i2c = I2C(0)  # master, dflt pins SDA P9/GPIO12, SCL P10/GPIO13
    sensor_bme280 = BME280(i2c=i2c) # default address

  except Exception as e:
    display("BME280 setup error", 5, 0, True)
    print(e)

use_sds011 = True
if use_sds011:
  try:
    import SDS011 as sensor_sds011
  except Exception as e:
    display("SDS011 setup error", 5, 0, True)
    use_sds011 = False

# LoRa setup
def setup():
  global n, sleep_time

  # Turn off hearbeat LED
  pycom.heartbeat(False)
  # Initial sleep time
  sleep_time = 5*60

  # Connect to LoRaWAN
  display("Try  LoRaWan", 0, 0, True)
  display("LoRa App EUI:", 0, 16, False)
  display(str(app_eui), 0, 30, False)
  n = LORA()
  if n.connect(dev_eui, app_eui, app_key):
     display("Joined LoRaWan", 0, 0, False)
  else:
     display("NOT joined LoRa!", 0, 0, False)
  display("Setup done", 0, 16, False)

def runMe():
  global i2c
  global sensor_sds011, sensor_bme280
  global use_oled
  global n, sleep_time
  # Setup network & sensors
  setup()

  toSleep = 0
  while True:
    display("Sensing...",0,0, True)

    if sensor_sds011 and (not sensor_sds011.SDSisRunning):
      sensor_sds011.startstopSDS(True)
      display('starting up fan', 5, 30, False)
      ProgressBar(0,44,128,14,15,0x004400)

    # Measure
    t = 0; h = 0; p = 0; meteo = False
    if sensor_bme280:
      try:
        LED.blink(3,0.1,0x002200)
        if use_oled: i2c.init(0)
        t = float(sensor_bme280.temperature) # string '20.12'
        h = float(sensor_bme280.humidity)    # string '25'
        p = float(sensor_bme280.pressure)    # string '1021.60'
        meteo = True
      except Exception as e:
        display("BME280 error",0,0,True)
        print(e)
        LED.blink(3,0.1,0xff0000)
        meteo = False

    p10 = 0; p25 = 0; dust = False
    if sensor_sds011:
      try:
        LED.blink(3,0.1,0x005500)
        p10,p25 = sensor_sds011.readSDSvalues() # float 11.2
        dust = True
      except Exception as e:
        display("SDS011 error",0,0,True)
        print(e)
        LED.blink(3,0.1,0xff0000)
        dust = False

    LED.blink(3,0.1,0x00ff00)
    #display(e,0,16,False)

    if dust:
      display("      PM2.5 PM10", 0,  0, True)
      display("ug/m3 %5.1f %4.1f" % (p25,p10),  0, 16, False)
    if meteo:
      display("   C  r.hum  pHa", 0, 34, False)
      display("  o",              0, 30, False,False)
      display(" %5.1f  %2d%% %4d" % (t,h,p),0, 48, False)
    toSleep = time.time()
    display("%2dh%2d" % (toSleep/3600,(toSleep%3600)/60), 0, 0, False,False)

    data = struct.pack('>HHHHH', int(round(t*10+300)), int(round(h*10)), int(round(p)), int(round(p10*10)), int(round(p25*10)))
    #data = base64.encodestring(data)
    # Send packet
    response = n.send(data)
    if not response:
      LED.off()
    else:
      display(" LoRa send ERROR",0,50,False)
      LED.blink(5,0.2,0x9c5c00,False)

    if sensor_sds011 and (sleep_time > (5*60-15)):
      sensor_sds011.startstopSDS(False)
      toSleep = sleep_time -15
    else:
      toSleep = sleep_time
    ProgressBar(0,63,128,2,toSleep,0xebcf5b,10)
    toSleep = 0

if __name__ == "__main__":
    runMe()
