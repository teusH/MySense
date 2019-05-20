# simple test script for dust sensors
# Copyright 2019, Teus Hagen MySense GPLV3

# standalone test loop

__version__ = "0." + "$Revision: 5.10 $"[11:-2]
__license__ = 'GPLV3'

from time import time, sleep_ms

# dflt pins=(Tx-pin,Rx-pin,Pwr-pin): wiring Tx-pin -> Rx dust module
# Pwr dflt None (not switched) 5V DC
# dflt: for gps pins = ('P11','P10','P20' or None)
# default UART(port=1,baudrate=9600,timeout_chars=2,pins=('P11','P10',None))

# useDust, (Tx,Rx{,None/Pwr}) overwrite via Config (wichUART), or json conf (ConfigJson)
abus = 'ttl'
atype = 'dust'

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
        print("Store %s config in flash" % dev)

if not atype in config[abus].keys() or not config[abus][atype]['use']:
  import sys
  print("No %s found on bus %s or use turned off." % (atype,abus))
  sys.exit()

print("Using %s: " % atype, which.devices[atype])

device = None
try:
  device = which.getIdent(atype=atype)
  if debug: print("Found %s device, type %s on bus %s: " % (which.NAME(atype),atype,abus), device)
  name = which.NAME(atype)
  pins = which.Pins(atype)
except Exception as e:
  print("Error: %s" % e)
finally:
  if not device:
    print("Unable to find %s device" % atype)
    sys.exit()

print('%s sensor: using %s nr 1: Rx->pin %s, Tx->pin %s, Pwr->' % (atype,which.NAME(atype=atype),pins[0],pins[1]),pins[2])

name = which.DUST
baud = config[abus][atype]['baud']
pins = which.Pins('dust')
print('%s sensor: using %s nr 1, %d baud: Rx->pin %s, Tx->pin %s, Pwr->' % (atype,name,baud,config[abus][atype]['pins'][0],config[abus][atype]['pins'][1]),config[abus][atype]['pins'][2])

try:
  if name[:3] == 'SDS':
    from SDS011 import SDS011 as senseDust
  elif name[:3] == 'PMS':
    from PMSx003 import PMSx003 as senseDust
  elif name[:3] == 'SPS':
    from SPS30 import SPS30 as sensedust
  else: raise OSError("Unknown dust sensor %s" % dust)
except Exception as e:
  raise OSError("Error with %s: %s" % (dust,e))

sampling = 60    # each sampling time take average of values
interval = 5*60  # take very 5 minutes a sample over 60 seconds

if 'Dexplicit' in config.keys(): Dexplicit = config['Dexplicit']
else: Dexplicit = False # Sensirion count style
calibrate = which.calibrate # all calibrate info

which.Power(pins, on=True)
from machine import UART
print("Baudrate: %d" % baud)
#ser = UART(1,baudrate=baud,timeout_chars=80,pins=pins[:2])
#ser = which.openUART('dust')
ser =  device['ttl']
debug=False
sensor = senseDust(port=ser, debug=debug, sample=sampling, interval=0, pins=pins[:2], calibrate=calibrate, explicit=Dexplicit)

print("Dust: using sensor %s, UART %d, " % (name,device['index']), "Rx~>%s, Tx~>%s, Pwr~>%s" % pins)
print("Dust module sampling %d secs, interval of measurement %d minutes" % (sampling, interval/60))
print("PM pcs (count) values: %s pcs " %(">PMn (a la Plantower)" if Dexplicit else "<PMn (a la Sensirion)"))

if sensor and (sensor.mode != sensor.NORMAL): sensor.Normal()
errors = 0
max = 6
prev =  which.Power(pins, on=True)
for cnt in range(max):
    timings = time()
    try:
      # sensor.GoActive() # fan on wait 60 secs
      data = sensor.getData()
    except Exception as e:
      print("%s/%s read error raised as: %s" % (atype,name,e))
      if errors > 20: break
      errors += 1
      sleep_ms(30*1000)
      sensor.ser.readall()
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
which.Power(pins, on=prev)
ser.deinit()
#which.closeUART('dust')
MyConfig.store # update archive config if needed
import sys
sys.exit()
