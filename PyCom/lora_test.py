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
for cnt in range(20):
   if lora.has_joined(): break
   time.sleep(1)
   print('Not yet joined... %d' % cnt)
if cnt < 19: print('Joined!!')
else:
   print("No join")
   import sys
   sys.exit()
