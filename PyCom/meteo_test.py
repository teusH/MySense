# Copyright 2019, Teus Hagen, GPLV4
# simple test to see if meteo I2C device is present
from time import sleep_ms
from machine import I2C
import sys

__version__ = "0." + "$Revision: 5.4 $"[11:-2]
__license__ = 'GPLV4'

abus = 'i2c'
atype = 'meteo'

debug=False
import ConfigJson
config = {abus: {}}
myConfig = ConfigJson.MyConfig(debug=debug)
config[abus] = myConfig.getConfig(abus=abus)
FndDevices = []
if len(config[abus]): print("Found archived configuration for:")
for dev in config[abus].keys():
  FndDevices.append(dev)
  print("%s: " % dev, config[abus][dev])

import whichI2C
which = whichI2C.identification(config=config[abus], debug=debug)
for dev in config[abus].keys():
  if not dev in FndDevices:
    if dev != 'updated':
      print("Found device %s: " % dev, config[abus][dev])
      MyConfig.dump(dev,config[abus][dev],abus=abus)

if not config[abus][atype]['use']:
  print("%s config: not use %s" % (atype,config[abus]['name']))
  sys.exit()

print("Using %s: " % atype, which.Device(atype))

try:
  device = which.getIdent(atype=atype)
  nr = device['index']
  i2c = device[abus]
  addr = device['conf']['address']
  meteo = which.METEO
  pins = which.Pins(atype)
except Exception as e:
  print("Error: %s" % e)
finally:
  if not device:
    print("Unable to find %s device" % atype)
    sys.exit()

try:
  from Config import calibrate
except:
  calibrate = None

# Create library object using our Bus I2C port
try:
    which.PwrI2C(pins, on=True)
    if meteo == 'BME280':
      import BME280 as BME
      device['fd'] = BME.BME_I2C(i2c, address=addr, debug=False, calibrate=calibrate)
    elif meteo == 'BME680':
      import BME_I2C as BME
      device['fd'] = BME.BME_I2C(i2c, address=addr, debug=False, calibrate=calibrate)
    elif meteo[:3] == 'SHT':
        import Adafruit_SHT31 as SHT
        device['fd'] = SHT.SHT31(address=addr, i2c=i2c, calibrate=calibrate)
    else: raise ValueError(meteo)
except ImportError:
    raise ValueError("SHT or BME library not installed")
except Exception as e:
    raise ValueError("Fatal: meteo module %s" % e)
# change this to match the location's pressure (hPa) at sea level
device['fd'].sea_level_pressure = 1024.25 # 1013.25

print("Meteo I2C device: ", device)
max = 5
print("Try %d measurements" % max)
for cnt in range(1,max+1):
  if cnt != 1:
    print("sleep for 15 secs")
    sleep_ms(15*1000)
  try:
    if device['fd'].temperature != None:
      print("\nRun %d of %d\nTemperature: %0.1f oC" % (cnt,max,device['fd'].temperature))
    else: print("No temperature!")
    if  device['fd'].humidity != None:
      print("Humidity: %0.1f %%" % device['fd'].humidity)
    else: print("No humidity!")
    if (meteo[:3] == 'BME') and (device['fd'].pressure != None):
        print("Pressure: %0.3f hPa" % device['fd'].pressure)
        device['fd'].sea_level_pressure -= 0.5
        print("Altitude = %0.2f meters with sea level pressure: %.2f hPa" % (device['fd'].altitude,device['fd'].sea_level_pressure))
    if meteo is 'BME680':
        if not cnt:
            try:
              if 'M_gBase' in myConfig.config.keys():
                device['fd'].gas_base = config['M_gBase']
              else:
                  from Config import M_gBase  # if present do not recalculate
                  device['fd'].gas_base = M_gBase
                  myConfig.dump('M_gBase',M_gBase)
            except: device['fd'].gas_base = None # force recalculation gas base line
        if device['fd'].gas_base == None:
            gBase = False
            print("%salculating stable gas base level. Can take max 5 minutes to calculate gas base." % ('Rec' if cnt else 'C'))
        else: gBase = True
        AQI = device['fd'].AQI # first time can take a while
        if device['fd'].gas_base != None:
            print("Gas base line calculated: %.1f" % device['fd'].gas_base)
            if not gBase: myConfig.dump('M_gBase',device['fd'].gas_base)
            gBase = True
        gas = device['fd'].gas
        if gas != None: print("Gas: %.3f Kohm" % round(gas/1000.0,2))
        if (device['fd'].gas_base != None) and AQI:
            print("AQI: %0.1f %%" % AQI)
        else:
            print("Was unable to calculate AQI. Will try again.")
            print("Allow 30 secs extra sleep")
            sleep_ms(30*1000)
  except OSError as e:
    print("Got OS error: %s. Will try again." % e)
    i2c.init(I2C.MASTER,pins=pins[:2])

if myConfig.dirty: myConfig.store
sys.exit()
