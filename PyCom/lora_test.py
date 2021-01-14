# Copyright 2019, Teus Hagen, GPLV3
'''Simple test script for testing LoRa join connection with Spreadings Factor SF
'''

__version__ = "0." + "$Revision: 6.1 $"[11:-2]
__license__ = 'GPLV3'

# increase spreadings factor if gateway is further away
# SF can be defined before running this script
try: SF
except: SF=7 # LoRa spreadings factor may be one of 7(dflt) to 12(max)

def LoRaStatus(net):
   status = net.stats()
   print("Spreadings Factor used: %d" % SF)
   # status[0] last datagram time stamp msec
   print("RSSI           %d dBm" % status[1])
   print("SNR            %.1f dB" % status[2])
   print("Tx datarate    %d" % status[3])
   print("Rx datarate    %d" % status[4])
   print("Tx trials      %d" % status[5])
   print("Tx power       %d" % status[6])
   print("Tx time on air %d" % status[7])
   print("Tx count       %d" % status[8])
   print("Rx frequency   %d" % status[9])

from network import LoRa
lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868, sf=SF)
print('Using LoRa SF=%d\nReset/clear LoRa status in nvram' % SF)
lora.nvram_erase()
import time
import binascii
from Config import dev_eui, app_eui, app_key
print("app_eui: %s" % app_eui)
print("dev_eui: %s" % dev_eui)
print("app_key: %s" % app_key)
# OTAA authentication parameters
dev_eui = binascii.unhexlify(dev_eui)
app_eui = binascii.unhexlify(app_eui)
app_key = binascii.unhexlify(app_key)
# join a network using OTAA (Over the Air Activation)
lora.join(activation=LoRa.OTAA, auth=(dev_eui, app_eui, app_key), timeout=0)
# wait until the module has joined the network
for cnt in range(1,151):
   print('Join try %d: 15 secs waiting for join ' % cnt, end='')
   for i in range(5):
      time.sleep(3)
      print('.', end=''); cnt += 3
      if lora.has_joined():
         break
   else:
      print('Waited %d secs for join.' % cnt)
      break
   print('')

if cnt < 150:
   print('TTN LoRa JOIN success.')
   LoRaStatus(lora)
else:
   print("NOT JOINED!!!")

del lora
del dev_eui
del app_eui
del app_key
del cnt
import sys
sys.exit()
