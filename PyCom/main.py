# 12 maart 2019 Teus
def setWiFi():
  try:
    from machine import unique_id
    import binascii
    SSID = 'MySense-' + binascii.hexlify(unique_id()).decode('utf-8')[-4:].lower()
    PASS = 'www.pycom.io'
    from network import WLAN
    wlan = WLAN()
    wlan.init(mode=WLAN.AP,ssid=SSID, auth=(WLAN.WPA2,PASS), channel=7, antenna=WLAN.INT_ANT)
  except: pass

setWiFi()
startMe = False
from machine import wake_reason, PWRON_WAKE
if wake_reason()[0] != PWRON_WAKE: startMe = True
else: # work around fake wakeup
  try:
    from pycom import nvs_get
    from time import ticks_ms
    if nvs_get('AlarmSlp')*1000 < ticks_ms(): startMe = True
  except: pass
if startMe:
  import MySense
  MySense.runMe()

# uncomment to force REPL mode.
if True: print('No MySense start')
else: # deepsleep pin set and no accu voltage connected force REPL mode
  try:
    from machine import Pin
    sleepPin = 'P18'
    try: from Config import sleepPin
    except: pass
    # WARNING: PyCom expansion board will show deepsleep pin enabled!
    if Pin(sleepPin,mode=Pin.IN).value(): # deepsleep disabled
      import MySense
      MySense.runMe() # MySense and sleep
    else: # deepsleep enabled, avoid PyCom expansion board diff
      accuPin = 'P17'
      try: from Config import accuPin
      except: pass
      from machine import ADC
      # WARNING: on PyCom expansion board sleeppin is low and accupin is high!
      if (ADC(0).channel(pin=accuPin, attn=ADC.ATTN_11DB).value())*0.004271845 > 4.8:
        import MySense
        MySense.runMe() # MySense and deepsleep
  except: pass
# REPL modus
