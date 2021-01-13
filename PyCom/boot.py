# Copyright 2021, Teus Hagen, ver. Behoud de Parel, GPLV3
# $Id: boot.py,v 6.2 2021/01/13 14:02:08 teus Exp teus $

# disable pybytes and smart config
import pycom
try:
  if pycom.pybytes_on_boot(): pycom.pybytes_on_boot(False)
  if pycom.smart_config_on_boot(): pycom.smart_config_on_boot(False)
except: pass

def set_wifi():
  from machine import unique_id
  import binascii
  ssid = 'MySense-' + binascii.hexlify(unique_id()).decode('utf-8')[-4:].lower()
  pwd = 'www.pycom.io'
  from network import WLAN
  try:
    WLAN().scan()
  except: # mode AP
    if (pycom.wifi_ssid_ap() is ssid) and (pycom.wifi_pwd_ap() is pwd): return
  from time import sleep
  try:
    WLAN().deinit(); sleep(2)
  except: pass
  pycom.wifi_ssid_ap(ssid); pycom.wifi_pwd_ap(pwd)
  # turn on wifi on power on
  WLAN().init(mode=WLAN.AP, ssid=ssid, auth=(WLAN.WPA2,pwd), channel=7, antenna=WLAN.INT_ANT)
  sleep(2)

try: # MySense wifi AP
  from machine import wake_reason, RTC_WAKE
  if wake_reason()[0] != RTC_WAKE:
    if not pycom.wifi_on_boot(): pycom.wifi_on_boot(True)
    set_wifi()
except: pass
