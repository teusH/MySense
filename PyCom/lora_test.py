__version__ = "0." + "$Revision: 1.11 $"[11:-2]
__license__ = 'GPLV4'

Network = ''
method = {}
try:
  from lora import LORA
  from Config import Network
  # OTAA keys
  from Config import dev_eui, app_eui, app_key
except: print('No network or LoRa OTAA keys defined')
if Network != 'TTN': raise ValueError("No LoRa network defined")
else: method['OTAA'] = (dev_eui, app_eui, app_key)
try:
  # ABP keys
  from Config import dev_addr, nwk_swkey, app_swkey
except: print('No LoRa ABP keys defined')
else: method['ABP'] = (nwk_swkey, nwk_swkey, app_swkey)
if not len(method): raise ValueError("No LoRa keys configured or LoRa config error")

import sys
import struct
from time import time, sleep

# Turn off hearbeat LED
import pycom
pycom.heartbeat(False)

info = None
n = None
def SendInfo(port,data):
  print("info requested")
  if not data: return
  if (not info) or (not n): return
  print("Sent info")
  sleep(30)
  n.send(info,port=3)

n = LORA()
if not n.connect(method, ports=2):
  print("Failed to connect to LoRaWan TTN")
  sys.exit(0)

# send first some info
# dust (None,Shiney,Nova,Plantower, ...) 4 low bits
# meteo (None,DHT11,DHT22,BME280,BME680, ...) 4 high bits
# GPS (longitude,latitude, altitude) float
# send 17 bytes

useGPS = False
thisGPS = [50.12345,6.12345,12.34]
try: from Config import useGPS, thisGPS
except: pass

Dust = ['unknown','PPD42NS','SDS011','PMS7003']
Meteo = ['unknown','DHT11','DHT22','BME280','BME680']
try:
  from Config import meteo
except:
  meteo = 'unknown'
try:
  from Config import dust
except:
  dust = 'unknown'

sense = ((Meteo.index(meteo)&0xf)<<4) | (Dust.index(dust)&0x7)
if useGPS: sense |= 0x8
info = struct.pack('>BBlll',0,sense,int(thisGPS[0]*100000),int(thisGPS[1]*100000), int(thisGPS[2]*10))
print("Sending version 0, meteo %s, dust %s, configured GPS: " % (meteo,dust), thisGPS)

if not n.send(info,port=3): print("send error")
else: print('Info is sent')

for cnt in range(3):
  # old style
  # data = struct.pack('>HHHHHHHHl', 10+cnt, 15+cnt, 20+cnt, 25+cnt, 30+cnt, 35+cnt, 40+cnt, 45+cnt, time())
  # packaged as: type, PM25*10, PM10*10, temp*10+300, hum*10
  if cnt%2:
    data = struct.pack('>BHHHHHlll', 0x88, int(250+cnt), int(100+cnt), 300+cnt, cnt, 1000+cnt, int(thisGPS[0]*100000),int(thisGPS[1]*100000), int(thisGPS[2]*10))
  else:
    data = struct.pack('>BHHHHH', 0x80, int(250+cnt), int(10+cnt), 300+cnt, cnt,0)
  # Send packet
  if not n.send(data):  # send to LoRa port 2
    print("send error")
  else: print('Data is sent')
  sleep(60)
print('Done')
import sys
sys.exit()
