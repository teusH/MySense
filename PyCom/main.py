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

try:
  setWiFi()
  # import MySense
  # MySense.runMe()
  from machine import Pin
  if not Pin('P18',mode=Pin.IN).value():
    import MySense
    MySense.runMe()
except: pass
