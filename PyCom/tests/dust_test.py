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
atype = 'dust'
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

# dflt pins=(Tx-pin,Rx-pin,Pwr-pin): wiring Tx-pin -> Rx dust module
# Pwr dflt None (not switched) 5V DC
# dflt: for gps pins = ('P11','P10','P20' or None)
# default UART(port=1,baudrate=9600,timeout_chars=2,pins=('P11','P10',None))
# useDust, (Tx,Rx{,None/Pwr}) overwrite via Config (wichUART), or json conf (ConfigJson)

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
try:
  device = which.getIdent(atype=atype, power=True)
  nr = device['index']
  ser =  device[abus]
  name = which.DUST
  baud = device['conf']['baud']
  pins = which.Pins(atype)
except Exception as e:
  print("Error: %s" % e)
  sys.exit()

print('Using %s: device=%s, TTL=%d, %d baud: Rx->pin %s, Tx->pin %s, Pwr-> %s' % (atype,name,nr,baud,pins[0],pins[1],str(pins[2])))

try:
  if name[:3] == 'SDS':
    from SDS011 import SDS011 as senseDust
  elif name[:3] == 'PMS':
    from PMSx003 import PMSx003 as senseDust
  elif name[:3] == 'SPS':
    from SPS30 import SPS30 as senseDust
  else: raise OSError("Unknown dust sensor %s" % str(name))
except Exception as e:
  raise OSError("Error with %s: %s" % (str(name),e))

sampling = 60    # each sampling time take average of values
interval = 3*60  # take very 5 minutes a sample over 60 seconds
print("Dust module sampling %d secs, interval of measurement %d minutes" % (sampling, interval/60))

if 'Dexplicit' in config.keys(): Dexplicit = config['Dexplicit']
else: Dexplicit = False # Sensirion count style
print("PM pcs (count) values: %s pcs " %("larger PM (Plantower style)" if Dexplicit else "smaller PM (Sensirion style)"))

calibrate = which.calibrate # all calibrate info
print("Calibrate info: ",calibrate)

from machine import UART
sensor = senseDust(port=ser, debug=debug, sample=sampling, interval=0, pins=pins[:2], calibrate=calibrate, explicit=Dexplicit)

errors = 0
max = 3
prev = which.Power(pins, on=True)
if sensor and (sensor.mode != sensor.NORMAL): sensor.Normal()
for cnt in range(max):
    print("Run %d of %d for %s test" % (cnt,max,atype))
    timings = time()
    try:
      # sensor.GoActive() # fan on wait 60 secs
      data = sensor.getData(debug=debug)
      # debug = False
    except Exception as e:
      print("%s/%s read error raised as: %s" % (atype,name,e))
      if errors > 20: break
      errors += 1
      sleep_ms(30*1000)
      sensor.ser.read()
      continue
    errors = 0
    print("%s/%s record:" % (atype,name))
    print(data)
    timings = interval -(time()-timings)
    if timings > 0:
        print("Sleep now for %d secs with %s Off" % (timings, 'power On and fan' if cnt < (max/2) else 'fan controlled by power'))
        try:
            if cnt < (max/2): sensor.Standby()
            else: which.Power(pins, on=False)
            if timings > 60: sleep_ms((timings-60)*1000)
            print("Dust sensor start up")
            if cnt >= (max/2):
                which.Power(pins, on=True)
                sleep_ms(200)
            sensor.Normal() # fan on measuring
            sleep_ms(30*1000) # fan start up
            sensor.mode = 0 # active
        except:
            errors += 1
            sleep_ms(60*1000)

which.Power(pins, on=False)
ser.deinit(); del ser
#which.closeUART(atype)
if MyConfig.dirty:
  print("Updating configuration json file %s:" % confFile)
  try:
    for dev in config[abus].keys():
      if dev is None or dev == 'updated': continue
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
