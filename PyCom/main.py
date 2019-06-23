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
try:
  import MySense
  from machine import Pin
  sleepPin = 'P18'
  try: from Config import sleepPin
  except: pass
  if Pin(sleepPin,mode=Pin.IN).value(): # deepsleep disabled
    MySense.runMe() # MySense and sleep
  else: # deepsleep enabled
    accuPin = 'P17'
    try: from Config import accuPin
    except: pass
    from machine import ADC
    # WARNING: on PyCom expansion board sleeppin is low and accupin is high!
    if (ADC(0).channel(pin=accuPin, attn=ADC.ATTN_11DB).value())*0.004271845 > 4.8:
      MySense.runMe() # MySense and deepsleep
except: pass
# REPL modus
