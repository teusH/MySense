# Copyright 2018, Teus Hagen, ver. Behoud de Parel, GPLV3
# $Id: main.py,v 1.14 2019/09/01 10:37:30 teus Exp teus $

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

def runMySense():
  import MySense
  MySense.runMe()  # should never return
  import myReset   # cold reboot or sleep forever
  myReset.myEnd()

setWiFi()

from machine import wake_reason, PWRON_WAKE
if wake_reason()[0] != PWRON_WAKE: runMySense()
else: # work around fake wakeup
  try:
    from pycom import nvs_get
    from time import ticks_ms
    if nvs_get('AlarmSlp')*1000 < ticks_ms(): runMySense()
  except: pass

# Use True to force REPL mode. use False: REPL depends on sleeppin and accu voltage
if True:
  print("No auto MySense start\nTo start MySense loop (reset config, cleanup nvs):")
  print("import MySense\nMySense.runMe(reset=True)")
else: # deepsleep pin set and no accu voltage: go into REPL mode
  try:
    from machine import Pin
    sleepPin = 'P18'
    try: from Config import sleepPin
    except: pass
    # WARNING: PyCom expansion board will show deepsleep pin enabled!
    if Pin(sleepPin,mode=Pin.IN).value(): # deepsleep disabled
      runMySense()
    else: # deepsleep enabled, check for PyCom expansion board looks like accu!
      accuPin = 'P17'
      try: from Config import accuPin
      except: pass
      from machine import ADC
      # WARNING: on PyCom expansion board sleeppin is low and accupin is high!
      if (ADC(0).channel(pin=accuPin, attn=ADC.ATTN_11DB).value())*0.004271845 > 4.8:
        runMySense()
  except: pass
# go into REPL mode
