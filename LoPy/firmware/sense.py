# should be main.py
# some code comes from https://github.com/TelenorStartIoT/lorawan-weather-station
#
from LoRaConfig import dev_eui, app_eui, app_key
from lora import LORA
from machine import I2C  # needed for BME280
from BME280 import *
import SDS011 as sensor_sds011
from time import sleep
from time import time
import pycom
import struct
from led import LED
# import base64

def setup():
  global n, sensor_bme280, sleep_time, last_time

  # Turn off hearbeat LED
  pycom.heartbeat(False)
  # Initial sleep time
  sleep_time = 5*60

  # Connect to LoRaWAN
  n = LORA()
  n.connect(dev_eui, app_eui, app_key)

  # Connect Sensors
  try:
    i2c = I2C(0)
    sensor_bme280 = BME280(i2c=i2c)
  except Exception as e:
    print("Error: ", e)
  print("Setup... done")

def runMe():
  global sensor_sds011, sensor_bme280, n, sleep_time
  # Setup network & sensors
  setup()

  toSleep = 0
  while True:
    if (not sensor_sds011.SDSisRunning) and (toSleep <= 30):
      sensor_sds011.startstopSDS(True)
      LED.blink(1,0.2,0xebcf5b)
      LED.blink(1,0.1,0x000000)
      sleep(30)

    # Measure
    try:
      LED.blink(3,0.1,0x004400)
      t = float(sensor_bme280.temperature) # string '20.12'
      p = float(sensor_bme280.humidity)    # string '25'
      h = float(sensor_bme280.pressure)    # string '1021.60'
      LED.blink(3,0.1,0x008800)
      p10,p25 = sensor_sds011.readSDSvalues() # float 11.2


      toSleep = int(time())
      print("%dd %dh %dm %ds\n%.1f oC, %d%%, %d pHa, PM10 %.1f ug/m3, PM2.5 %.1f ug/m3" % (toSleep/(24*60*60),toSleep/(60*60),toSleep/60,toSleep%60, t, p, h, p10, p25))
      data = struct.pack('>HHHHH', int(round(t*10+300)), int(round(p*10)), int(round(h)), int(round(p10*10)), int(round(p25*10)))
      #data = base64.encodestring(data)
    except Exception as e:
      print("Measure error: ", e)

    # Send packet
    response = n.send(data)
    LED.blink(1,0.1,0x000000)

    if sleep_time > (5*60-30):
      sensor_sds011.startstopSDS(False)
      toSleep = time() + sleep_time -30
    else:
      toSleep = time() + sleep_time
    while time() < toSleep:
      LED.blink(1,0.2,0xebcf5b)
      LED.blink(1,0.1,0x000000)
      sleep(9)
    toSleep = 0

if __name__ == "__main__":
    runMe()
