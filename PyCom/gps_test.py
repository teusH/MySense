# test script for GPS location sensor
# Copyright 2019, Teus Hagen MySense GPLV3

import sys
from time import sleep_ms, ticks_ms

__version__ = "0." + "$Revision: 5.10 $"[11:-2]
__license__ = 'GPLV3'

# dflt pins=(Tx-pin,Rx-pin,Pwr-pin): wiring Tx-pin -> Rx GPS module
# Pwr dflt None (not switched) 3V3 DC
# dflt: for gps pins = ('P4','P3','P19' or None)
# default UART(port=1,baudrate=9600,timeout_chars=2,pins=('P3','P4',None))

# useGPS and pins overwrite via Config (wichUART), or json conf (ConfigJson)
abus = 'ttl'
atype = 'gps'

debug = True
import ConfigJson
config = {abus: {}}
MyConfig = ConfigJson.MyConfig(debug=debug)
config[abus] = MyConfig.getConfig(abus=abus)
FndDevices = []
if config[abus]:
  print("Found archived configuration for:")
  for dev in config[abus].keys():
    FndDevices.append(dev)
    print("%s: " % dev, config[abus][dev])

import whichUART
if config[abus] and (atype in config[abus].keys()):
  which = whichUART.identification(identify=True,config=config[abus], debug=debug)
else: # look for new devices
  which =  whichUART.identification(identify=True, debug=debug)
  config[abus] = which.config
  FndDevices = []
for dev in config[abus].keys():
  if not dev in FndDevices:
    if dev != 'updated':
      print("Found device %s: " % dev, config[abus][dev])
      if dev == atype:
        MyConfig.dump(dev,config[abus][dev],abus=abus)
if MyConfig.dirty: print("Store %s config in flash" % dev)
MyConfig.store

print("config[%s] devices: %s" % (abus,str(config[abus].keys())))
print("which.config[%s]: %s" % (abus,str(which.config)))
if not config[abus][atype]['use']:
  print("%s/%s config: not use" % (atype,config[abus]['name']))
  sys.exit()

print("Using %s: device %s" % (atype, str(which.devices[atype])))

device = None
try:
  device = which.getIdent(atype=atype)
  if debug: print("Found %s device, type %s on bus %s: " % (which.GPS,atype,abus), device)
  name = which.GPS
  pins = which.Pins(atype=atype)
except Exception as e:
  print("Error: %s" % e)
finally:
  if not device:
    print("Unable to find %s device" % atype)
    sys.exit()

print('GPS: using %s nr 1: Rx->pin %s, Tx->pin %s, Pwr->' % (which.GPS,pins[0],pins[1]),pins[2])

try:
    print("Next can wait several minuets."); print("GPS raw:")
    prev = which.Power(pins, on=True)
    if not prev: print("Power ON pin %s." % pins[2])
    #ser = which.openUART(atype)
    ser = device[abus]
    for cnt in range(20):
       if ser.any(): break
       if cnt > 19: raise OSError("GPS not active")
       sleep_ms(200); print('.',end='')
    print("%s on %s is active" % (name,abus))
    for cnt in range(10):
      try:
        x = ser.readline()
      except:
        print("Cannot read GPS data")
        break
      print(x)
      sleep_ms(200)
    # which.closeUART(atype)
    which.Power(pins, on=prev)
    if not prev: print("powered OFF")

    prev = which.Power(pins, on=True)
    print("Next can take several minutes...")
    print("Using GPS Dexter for location fit:")
    import GPS_dexter as GPS
    #gps = GPS.GROVEGPS(port=1,baud=9600,debug=False,pins=pins[:2])
    timing = ticks_ms()
    gps = device['lib'] = GPS.GROVEGPS(port=device[abus],debug=debug)
    # for cnt in range(0,20):
    #    if ser.any(): break
    #    if cnt > 19: raise OSError("GPS not active")
    #    sleep_ms(200); print('.',end='')
    # print("%s on %s is active" & (name,abus))
    for cnt in range(2):
      if cnt:
        print("Try again. Sleep 30 seconds")
        sleep_ms(30*1000)
      if debug: print("Get GPS and time. Can take several minutes.")
      data = gps.MyGPS()
      timing = int((ticks_ms()-timing+500)/1000)
      if data:
        print("satellites (%d) qualified (%d) fit time: %d min, %d secs" % (gps.satellites,gps.quality,timing/60,timing%60))
        hours = int(float(data['timestamp']))
        days = int(float(data['date']))
        millies = int(float(data['timestamp'])*1000)%1000
        #print("Date-time: %s/%s" % (data['date'],data['timestamp']))
        print("Date %d/%d/%d, time %d:%d:%d.%d" % (2000+(days%100),(days//100)%100,days//10000,hours//10000,(hours//100)%100,hours%100,millies))
        print("lon %.6f, lat %.6f, alt %.2f m" % (data['longitude'],data['latitude'],data['altitude']))
        # print(data)
        gps.debug = False
      else:
        print("Satellite search time: %d min, %d secs" % (timing/60,timing%60))
        print('No satellites (%d) found for a qualified (%d) fit' % (gps.satellites,gps.quality))
        print('Turn on debugging')
        gps.debug = True

except ImportError:
    print("Missing Grove GPS libraries")
except Exception as e:
    print("Unable to get GPS data on port with pins", pins, "Error: %s" % e)
device[abus].deinit()
which.Power(pins, on=prev)
if not prev: print("Power OFF pin %s." % pins[2])
#which.closeUART(atype)
if MyConfig.dirty: MyConfig.store
import sys
sys.exit()

# raw  GPS output something like
'''
$GPTXT,01,01,02,u-blox ag - www.u-blox.com*50
$GPGGA,001929.799,,,,,0,0,,,M,,M,,*4C
$GPGSA,A,1,,,,,,,,,,,,,,,*1E
$GPGSV,1,1,00*79
$GPRMC,001929.799,V,,,,,0.00,0.00,060180,,,N*46
$GPGGA,001930.799,,,,,0,0,,,M,,M,,*44
$GPGSA,A,1,,,,,,,,,,,,,,,*1E
'''
