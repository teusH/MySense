# Copyright 2019, Teus Hagen MySense GPLV3
''' simple test to identify dust and GPS TTL devices.
Side effect: if device is found it is added to configuration file.
Next can be done before running this module.
Use update = False not to update meteo in json config file.
    debug = False to disable.
'''

from time import time, sleep_ms
import sys

__version__ = "0." + "$Revision: 6.3 $"[11:-2]
__license__ = 'GPLV3'

try: debug
except: debug=True
abus = 'ttl'
atype = 'gps'
confFile = '/flash/MySenseConfig.json'
#try:
#    import os
#    os.remove(confFile)
#except: pass
try: update
except: update = True
finally:
  print("%s %s MySense configuration." % ('Updating' if update else 'No update',atype))

import ConfigJson
config = {abus: {}}
MyConfig = ConfigJson.MyConfig(debug=debug)
config[abus] = MyConfig.getConfig(abus=abus)
FndDevices = []
if config[abus]:
  print("Found archived %s configuration for:" % abus)
  for dev in config[abus].keys():
    if dev == 'updated': continue
    FndDevices.append(dev)
    print("\t%s: " % dev, config[abus][dev])
  if not atype in FndDevices:
    print("Sensor %s not found in conf  %s file." % (atype, confFile))
  if atype in FndDevices and update:
    del config[abus][dev]; FndDevices.remove(atype)

import whichUART as DEV
try:
  if config[abus] and (atype in config[abus].keys()):
    which = DEV.identification(identify=True,config=config[abus], debug=debug)
  else: # look for new devices
    which =  DEV.identification(identify=True, debug=debug)
    config[abus] = which.config
    for dev in which.devices.keys():
      FndDevices.append(dev)
      # config[abus][dev]['conf']['use'] = True
      print("New %s: " % dev, config[abus][dev])
      MyConfig.dump(dev,config[abus][dev],abus=abus)
except Exception as e:
  print("%s identification error: %s" % (abus.upper(),str(e)))
  print("%s configuration error in Config.py?" % abus.upper())
  sys.exit()

if not atype in config[abus].keys() or not config[abus][atype]['use']:
  print("No %s found on bus %s or use is disabled." % (atype,abus))
  sys.exit()

device = {}
#sys.exit()
try:
  device = which.getIdent(atype=atype, power=True)
  nr = device['index']
  #ser = which.openUART(atype)
  ser =  device[abus]
  baud = device['conf']['baud']
  pins = which.Pins(atype)
  name = which.GPS
  print("%s on %s is actived" % (name,abus))
except Exception as e:
  print("Error: %s" % e)
  sys.exit()

print('Using %s: device=%s, TTL=%d, %d baud: Rx->pin %s, Tx->pin %s, Pwr-> %s' % (atype,name,nr,baud,pins[0],pins[1],str(pins[2])))

try:
    print("Next can wait several minuets."); print("GPS raw data:")
    for cnt in range(20):
       if ser.any(): break
       if cnt > 19: raise OSError("GPS not active")
       if not cnt: print("Waiting for satelites in sight.")
       sleep_ms(2000); print('.',end='')
    for cnt in range(10):
      try:
        x = ser.readline()
      except:
        print("Cannot read GPS data")
        break
      if not x is None: print(x)
      else: print('.',end='')
      sleep_ms(1000)

    # which.closeUART(atype)
    #which.Power(pins, on=False)
    #print("%s powered OFF for 2 secs." % name)
    #sleep_ms(2000)

    from time import ticks_ms
    prev = which.Power(pins, on=True)
    print("Next can take several minutes...")
    print("Using GPS Dexter for location fit:")
    import GPS_dexter as GPS
    # gps = GPS.GROVEGPS(port=nr,baud=baud,debug=debug,pins=pins[:2])
    gps = GPS.GROVEGPS(port=ser,debug=False)
    device['lib'] = gps
    timing = ticks_ms()
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
        print('Turn on GPS debugging')
        gps.debug = True

except ImportError:
    print("Missing Grove GPS libraries")
except Exception as e:
    print("Unable to get GPS data on port with pins", pins, "Error: %s" % e)

which.Power(pins, on=False)
ser.deinit(); del ser
#which.closeUART(atype)
if MyConfig.dirty:
  print("Updating configuration json file %s:" % confFile)
  try:
    for dev in config[abus].keys():
      if dev is None or dev is 'updated': continue
      if not dev in FndDevices:
        print("Found new %s device %s: " % (abus,dev), config[abus][dev])
  except: pass
  # from machine import Pin
  # apin = 'P18'  # deepsleep pin
  # if not Pin(apin,mode=Pin.IN).value():
  if MyConfig.dirty and MyConfig.store:
    print("Updated config json file in %s." % confFile)
  else: print("Update config json file in %s NOT needed." % confFile)
del MyConfig
del which
del device
del config
print("DONE %s-uart test for %s sensor %s" % (abus.upper(),atype,name))
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
