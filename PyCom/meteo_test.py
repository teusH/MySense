# Copyright 2019, Teus Hagen, GPLV3
''' simple test to see if meteo I2C device is present
Side effect: if device is found it is added to configuration file.
Next can be done before running this module.
Use update = False not to update meteo in json config file.
    debug = False to disable.
'''

from time import sleep_ms
import sys

__version__ = "0." + "$Revision: 6.2 $"[11:-2]
__license__ = 'GPLV3'

try: debug
except: debug=True
confFile = '/flash/MySenseConfig.json'
#try:
#    import os
#    os.remove(confFile)
#except: pass
try: update
except: update = True

abus = 'i2c'
atype = 'meteo'
print("%s %s MySense configuration." % ('Updating' if update else 'No update',atype))

import ConfigJson
config = {abus: {}}
MyConfig = ConfigJson.MyConfig(debug=debug)
config[abus] = MyConfig.getConfig(abus=abus)
FndDevices = []
if config[abus]:
  print("Found archived %s configuration for:" % abus)
  for dev in config[abus].keys():
    if dev is 'updated': continue
    FndDevices.append(dev)
    print("\t%s: " % dev, config[abus][dev])
  if not atype in FndDevices:
    print("Sensor %s not found in conf  %s file." % (atype, confFile))
  if atype in FndDevices and update:
    del config[abus][dev]; FndDevices.remove(atype)

import whichI2C as DEV
try:
  if config[abus] and (atype in config[abus].keys()):
    which = DEV.identification(identify=True,config=config[abus], debug=debug)
  else: # look for new devices
    which =  DEV.identification(identify=True, debug=debug)
    config[abus] = which.config
    for dev in which.devices.keys():
      FndDevices.append(dev)
      #config[abus][dev]['conf']['use'] = True
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
  i2c = device[abus]
  addr = device['conf']['address']
  name = which.METEO
  pins = which.Pins(atype)
except Exception as e:
  print("Error: %s" % e)
  sys.exit()

print("Using %s: device=%s, I2C=%s, address=0x%x, pins=%s." % (atype,name,str(i2c),addr,str(pins))) 

try:
  from Config import calibrate
except:
  calibrate = None

# Create library object using our Bus I2C port
try:
    if name == 'BME280':    import BME280 as MET
    elif name == 'BME680':  import BME680 as MET
    elif name[:3] == 'SHT': import SHT31 as MET
    else: raise ValueError(name)
    device['fd'] = MET.MyI2C(i2c, address=addr, probe=True, debug=False, lock=device['lock'], calibrate=calibrate)
except ImportError:
    raise ValueError("SHT or BME library not installed")
except Exception as e:
    raise ValueError("Fatal: meteo module %s" % e)
# change this to match the location's pressure (hPa) at sea level
device['fd'].sea_level_pressure = 1024.25 # 1013.25

print("Meteo I2C device: ", device)
prev =  which.Power(device['conf']['pins'], on=True)
max = 5
M_gBase = 0.0
print("Try %d measurements" % max)
for cnt in range(1,max+1):
  if cnt != 1:
    print("delay for 15 secs")
    sleep_ms(15*1000)
  try:
    if device['fd'].temperature != None:
      print("\nRun %d of %d\nTemperature: %0.1f oC" % (cnt,max,device['fd'].temperature))
    else: print("No temperature!")
    if  device['fd'].humidity != None:
      print("Humidity   : %0.1f%%" % device['fd'].humidity)
    else: print("No humidity!")
    if (name[:3] == 'BME') and (device['fd'].pressure != None):
        print("Pressure   : %0.1f hPa" % device['fd'].pressure)
        device['fd'].sea_level_pressure -= 0.5
        # print("Altitude = %0.2f meters with sea level pressure: %.2f hPa" % (device['fd'].altitude,device['fd'].sea_level_pressure))
    if name is 'BME680':
        if cnt == 1:
            try:
                from Config import M_gBase
                #print("Found gas base: %.1f in Config.py." % M_gBase)
            except: pass
            finally: device['fd'].gas_base = None
        if device['fd'].gas_base == None:
            gotBase = False
            print("%salculating stable gas base level. Can take max 5 minutes to calculate gas base." % ('Rec' if cnt else 'C'))
        else: gotBase = True
        AQI = device['fd'].AQI # first time can take a while
        if device['fd'].gas_base != None and not gotBase:
            print("Using gas base line: %.1f" % device['fd'].gas_base)
            if not (M_gBase*0.9 < device['fd'].gas_base < M_gBase*1.1):
              print("Update M_gBase (%.2f) in Config.py to %.2f!" % (M_gBase,device['fd'].gas_base))
              MyConfig.dump('gas_base',device['fd'].gas_base)
        gas = device['fd'].gas
        if gas != None: print("Gas        : %.2f KOhm" % (gas/1000.0))
        if (device['fd'].gas_base != None) and AQI:
            print("AQI        : %0.1f%%" % AQI)
        else:
            print("Was unable to calculate AQI. Will try again.")
            print("Allow 30 secs extra sleep")
            sleep_ms(30*1000)
  except OSError as e:
    print("Got OS error: %s. Will try again." % e)
    i2c.init(I2C.MASTER,pins=pins[:2])

which.Power(device['conf']['pins'], on=prev)
if MyConfig.dirty:
  print("Updating configuration json file %s:" % confFile)
  try:
    for dev in config[abus].keys():
      if dev is 'updated': continue
      if not dev in FndDevices:
        print("Found new %s device %s: " % (abus,dev), config[abus][dev])
    print("Add this gas base to Config.py: %.1f" % device['fd'].gas_base)
  except: pass
  # from machine import Pin
  # apin = 'P18'  # deepsleep pin
  # if not Pin(apin,mode=Pin.IN).value():
  if MyConfig.dirty and MyConfig.store:
    print("Updated config json file in %s." % confFile)
  else: print("Update config json file in %s NOT needed." % confFile)
print("DONE %s-bus test for %s sensor %s" % (abus.upper(),atype,name))
sys.exit()
