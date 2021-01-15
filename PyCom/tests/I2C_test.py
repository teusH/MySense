# Copyright 2019, Teus Hagen, GPLV3
# search I2C busses for devices and check presence of installed support libs

__version__ = "0." + "$Revision: 6.2 $"[11:-2]
__license__ = 'GPLV3'

from time import sleep
from machine import I2C
# pins array of (SDA,SCL,Pwr), ...
pins = ('P23','P22') # (SDA pin, SCL pin)
pwr = None  # PCB V1.0 or no PCB
pwr = 'P21' # PCB V2.x power pin It does not hurt to try this

# identify I2C devices on I2C busses
class identifyI2C:
  def __init__(self,
      I2Cpins=[('P23','P22','P21')], # SDA,SCL,PWR dflt
      debug=False):
    self.I2Cpins=I2Cpins
    self.debug = debug
    I2Cdevices = [
            ('BME280',0x76),('BME280',0x77), # BME serie Bosch
            ('SHT31',0x44),('SHT31',0x45),   # Sensirion serie
            ('SSD1306',0x3c)                 # oled display
       ]
    self.I2Cdevices = []
    for one in range(len(I2Cpins)):
       if one > 2: raise OSError("No more I2C busses available")
       i2c = I2C(one, I2C.MASTER, pins=I2Cpins[one][:2])
       try:
         for addr in i2c.scan():
           for dev in I2Cdevices:
             if addr == dev[1]:
                self.I2Cdevices.append({'fd': i2c, 'name': dev[0],
                    'pins': I2Cpins[one][:2], 'pwr': I2Cpins[one][2],
                    'addr': addr})
       except: pass

if pwr: # Fontys PCB V2 board
    from machine import Pin
    if not Pin(pwr, mode=Pin.OUT, pull=None, alt=-1).value():
        Pin(pwr, mode=Pin.OUT, pull=None, alt=-1).value(1)

def BME_ID(i2c, address=0x77):
    BME_ID_ADDR = const(0xd0)
    # Create I2C device.
    if not type(i2c) is I2C:
      raise ValueError('An I2C object is required.')
    return int.from_bytes(
        i2c.readfrom_mem(address, BME_ID_ADDR, 1),'little') & 0xFF

i2c = I2C(0, I2C.MASTER, pins=pins)
# I2C sema
import _thread
lock = _thread.allocate_lock()
probe = True # test if hooked up


print("Find and install I2C devices via I2C bus scan")
addrs = i2c.scan()
devices = []
print("Registers of devices on I2C bus: ", addrs)

for addr in addrs:
    print("Try I2C addr: 0x%X" % addr)
    try:
        if addr in [0x77,0x76]:
          BME280_ID = const(0x60)
          BME680_ID = const(0x61)
          print("Try as BME280/680 device")
          try: bmeID = BME_ID(i2c, address=addr)
          except: bmeID = None
          if bmeID == BME680_ID:
            import BME680 as MET1
            devices.append(('BME680',MET1.MyI2C(i2c, address=addr, probe=probe, lock=lock, debug=False, calibrate=None),addr))
          elif bmeID == BME280_ID:
            import BME280 as MET2
            devices.append(('BME280',MET2.MyI2C(i2c, address=addr, probe=probe, lock=lock, debug=False, calibrate=None),addr))
          else:
            print("Unknown BME chip ID=0x%X" % bmeID)
            break
        elif addr in [0x44,0x45]:
          import SHT31 as MET3
          devices.append(('SHT31',MET3.MyI2C(i2c, address=addr, probe=probe, lock=lock, debug=False, calibrate=None),addr))
        elif addr in [0x3c]:
          import SSD1306 as OLED
          devices.append(('SSD1306',OLED.MyI2C(128,64,i2c,address=addr,probe=probe, lock=lock),addr))
        else:
          print("Unknown device at addr: 0x%X" % addr)
          continue
    except OSError as e:
        print("Error at addr 0x%X: %s" % (addr, e))
        i2c.init(0,pins=pins)
        sleep(1)
        continue
    except RuntimeError as e:
        print("Failure on device driver: %s" % e)
        continue

print("Try simple operation on connected I2C devices:")
for device in devices:
  try:
    if device[0][:3] == 'SSD':
        print("  - Oled %s display on address 0x%x is blinking?" % (device[0],device[2]))
        for i in range(2):
          sleep(1)
          device[1].fill(1) ; device[1].show()
          sleep(1)
          device[1].fill(0); device[1].show()
    elif device[0][:3] in ['BME','SHT']:
        print("  - Meteo %s on address 0x%x:" % (device[0],device[2]))
        print("\ttemp: %.2f oC," % device[1].temperature)
        print("\thumidity: %.2f%%," % device[1].humidity)
        print("\tair pressure: %.2f hPa." % (device[1].pressure if not device[1].pressure is None else 0))
    else: print("  - Unknown device %s on address 0x%x:" % (device[0],device[2]))
  except Exception as e: print("Device operation error: %s" % e)
