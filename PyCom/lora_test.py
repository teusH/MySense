def LoRaStatus(net):
   status = net.stats()
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
lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868)
print('Reset LoRa status in nvram')
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
for cnt in range(10):
   for i in range(5):
      print('.', end='')
   print('')
   if lora.has_joined():
      break
   print('Not yet joined... %d' % cnt)
   print('Retry after 15 secs ', end='')
   for i in range(10):
      time.sleep(1)
      print('.', end='')

if cnt < 19:
   print('TTN LoRa JOIN')
   LoRaStatus(lora)

else:
   print("NOT JOINED!!!")
   import sys
   sys.exit()
