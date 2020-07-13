# Copyright 2019, Teus Hagen, GPLV3
# search I2C busses for devices and check presence of installed support libs

__version__ = "0." + "$Revision: 1.2 $"[11:-2]
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

print("Find and install I2C devices via I2C bus scan")
addrs = i2c.scan()
print("Registers of devices on I2C bus: ", addrs)

for addr in addrs:
    print("Try I2C addr: 0x%X" % addr)
    try:
        if (addr == 0x77) or (addr == 0x76):
          BME280_ID = const(0x60)
          BME680_ID = const(0x61)
          print("Try as BME280/680 device")
          try: bmeID = BME_ID(i2c, address=addr)
          except: bmeID = None
          if bmeID == BME680_ID:
            name = 'BME680'
            import BME_I2C as LIB
            device = LIB.BME_I2C(i2c, address=addr, debug=False, calibrate=None)
          elif bmeID == BME280_ID:
            name = 'BME280'
            import BME280 as LIB
            device = LIB.BME_I2C(i2c, address=addr, debug=False, calibrate=None)
          else:
            print("Unknown BME chip ID=0x%X" % bmeID)
            break
        elif (addr == 0x44) or (addr == 0x45):
          name = 'SHT31'
          import Adafruit_SHT31 as LIB
          device = LIB.SHT31(address=addr, i2c=i2c, calibrate=None)
        elif (addr == 0x3c):
          name = 'SSD1306'
          import SSD1306
          device = SSD1306.SSD1306_I2C(128,64,i2c,addr=addr)
        else:
          print("Unknown addr: 0x%X" % addr)
          continue
    except OSError as e:
        print("Error at addr 0x%X: %s" % (addr, str(e)))
        i2c.init(0,pins=pins)
        sleep(1)
        continue
    except RuntimeError as e:
        print("Failure on devive driver: %s" % str(e))
        continue
    print("Try simple operation on device %s" % name)
    try:
        if name[:3] == 'SSD':
            print("Oled SSD1306")
            device.fill(1) ; device.show()
            sleep(1)
            device.fill(0); device.show()
        else:
            print("Meteo %s: temp: %.2f oC" % (name,device.temperature))
    except Exception as e:
        print("Device operation error: %s" % str(e))
