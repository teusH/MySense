# Copyright 2018, Teus Hagen, ver. Behoud de Parel, GPLV3
# $Id: main.py,v 6.2 2021/01/14 12:07:41 teus Exp teus $

from machine import wake_reason, PWRON_WAKE, RTC_WAKE

def setWiFi():
  import time
  from pycom import wifi_pwd_ap, wifi_ssid_ap
  try:
    W_SSID =  'MySense-AAAA'
    try: from Config import W_SSID
    except: pass
    if W_SSID[-4:] == 'AAAA':
        from machine import unique_id
        import binascii
        W_SSID = W_SSID[:-4]+binascii.hexlify(unique_id()).decode('utf-8')[-4:].lower()
    PASS = 'www.pycom.io' # only for 1 hr, then powered off (dflt) or changed
    if (not PASS is wifi_pwd_ap()) or (not W_SSID is wifi_ssid_ap()): 
      from network import WLAN
      wlan = WLAN()
      wlan.deinit(); time.sleep(5)
      wifi_pwd_ap(W_SSID); wifi_ssid_ap(PASS)
      wlan.init(mode=WLAN.AP,ssid=W_SSID, auth=(WLAN.WPA2,PASS), channel=7, antenna=WLAN.INT_ANT)
  except: pass

def ReplMode():
  REPL = False
  from machine import Pin
  # change next to False in operational modus
  try:
    from Config import REPL
  except: pass
  try:
    from Config import replPin # if not in config act in old style
    if not Pin(replPin,mode=Pin.IN).value():
      print("REPL enforced, pin %s" % str(REPL))
      return True
  except: pass
  return REPL

def runMySense():
  import MySense
  MySense.runMe()  # should never return
  import myReset   # cold reboot or sleep forever
  myReset.myEnd()

def WatchAccu():
  accuPin = 'P17'
  try: from Config import accuPin
  except: pass
  if not accuPin: return
  from machine import ADC, Pin
  sleep_ms(100)
  volt = ADC(0).channel(pin=accuPin, attn=ADC.ATTN_11DB).value()*0.004271845
  if volt < 1.0: return
  accuLevel = 11.8
  try: from Config import accuLevel
  except: pass
  from machine import deepsleep
  if volt < accuLevel-1.0: # long wait for sun
    deepsleep(60*60*1000)
  elif volt < accuLevel: # wait for sun
    deepsleep(15*60*1000)

if not ReplMode():
  if wake_reason()[0] == RTC_WAKE:  # wokeup from deepsleep
    WatchAccu()
    runMySense()
  elif wake_reason()[0] != PWRON_WAKE:
    runMySense()
  else: # work around fake wakeup
    try:
      from pycom import nvs_get
      from time import ticks_ms
      if nvs_get('AlarmSlp')*1000 < ticks_ms():
        runMySense() # reboot from deepsleep
    except: pass
  # run from power cycle
  runMySense()

# go into REPL mode, wifi On
try:
  setWiFi() # might be switched off after 60 min
except: pass

print("No auto MySense start\nTo start MySense loop (reset config, cleanup nvs):")
print("  import MySense; MySense.runMe(debug=False,reset=True)")
try:
  from pycom import heartbeat, rgbled, wifi_on_boot
  from time import sleep
  if not wifi_on_boot(): wifi_on_boot(True)
  heartbeat(False)
  for x in range(3):
    rgbled(0xf96015); sleep(0.1)
    rgbled(0x0); sleep(0.1)
    rgbled(0x0000ff); sleep(0.1)
    rgbled(0x0); sleep(0.4)
  heartbeat(True)
except: pass
