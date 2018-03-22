try:
  from Config import Network
  if Network != 'TTN':
     raise OSError('No LoRa defined')
  from Config import dev_eui, app_eui, app_key
  from lora import LORA
except:
  raise OSError('No LoRa config or libs defined')

import sys
import struct
from time import sleep

# Turn off hearbeat LED
import pycom
pycom.heartbeat(False)

n = LORA()
if not n.connect(dev_eui, app_eui, app_key,ports=2):
  print("Failed to connect to LoRaWan TTN")
  sys.exit(0)

# send first some info
# dust (None,Shiney,Nova,Plantower, ...) 4 low bits
# meteo (None,DHT11,DHT22,BME280,BME680, ...) 4 high bits
# GPS (longitude,latitude, altitude) float
# send 17 bytes
try:
  from Config import useGPS
except:
  useGPS = False
try:
  from Config import meteo
except:
  meteo = 0
try:
  from Config import dust
except:
  dust = 0

try:
  from Config import latitude, longitude, altitude
except:
  latitude = 0
  if useGPS:
    latitude = 50.12345; longitude = 6.12345; altitude = 12.34
if latitude:
  info = struct.pack('>Blll',dust|(meteo<<4),int(latitude*100000),int(longitude*100000),int(24.5*100000))
else:
  info = struct.pack('>Bl',dust|(meteo<<4),0)
response = n.send(info,port=3)
print('Sent info')
if response == b'?':
  print('Got request to send info')
  n.send(info,port=3)

for cnt in range(5):
  data = struct.pack('>HHHHH', 100+cnt, 150+cnt, 200+cnt, 300+cnt, 250+cnt)
  #data = base64.encodestring(data)
  # Send packet
  response = n.send(data)  # send to LoRa port 2
  print('Sent data')
  if response:
    if response == b'?':
      print("info requested, send info")
      n.send(info,port=3)
    else:
      print('Response was %s. Quit' % response)
      break
  sleep(60)
