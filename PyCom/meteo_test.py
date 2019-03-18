# Copyright 2019, Teus Hagen, GPLV4
# simple test to see if meteo I2C device is present
from time import sleep_ms
from machine import I2C

__version__ = "0." + "$Revision: 3.11 $"[11:-2]
__license__ = 'GPLV4'

def chip_ID(pins, i2c, address=0x77): # I2C dev optional ID
    chip_ID_ADDR = const(0xd0)
    # Create I2C device.
    if not type(i2c) is I2C:
      raise ValueError('An I2C object is required.')
    ID = 0 # 12 bits name, 9 bits part nr, 3 bits rev
    try: ID = i2c.readfrom_mem(address, chip_ID_ADDR, 3)
    except: # enable pwr?
      if type(pins[2]) is str:
        from machine import Pin
        # print("Try to wakeup pin %s" % pins[2])
        if not Pin(pins[2], mode=Pin.OUT, pull=None, alt=-1).value():
          print("Activate I2C bus")
          Pin(pins[2], mode=Pin.OUT, pull=None, alt=-1).value(1)
          sleep_ms(200)
          i2c.init(I2C.MASTER, pins=pins[:2])
          sleep_ms(200)
        ID = i2c.readfrom_mem(address, chip_ID_ADDR, 3)
    # print("ID: ", ID)
    return int.from_bytes( ID,'little') & 0xFF

BME280_ID = const(0x60)
BME680_ID = const(0x61)
SSD1306_ID = const(0x3)

I2Cpins = []
# side effect: I2C pwr/gnd enabled
def searchDev(names=['BME','SHT','SSD']):
    global I2Cpins
    I2Cpins = [('P23','P22',None)] # I2C pins [(SDA,SCL,Pwr), ...]
    I2Cdevices = [
            ('BME280',0x76),('BME280',0x77), # BME serie Bosch
            ('SHT31',0x44),('SHT31',0x45),   # Sensirion serie
            ('SSD1306',0x3c)                 # oled display
       ]
    try: from Config import I2Cpins
    except: pass
    print(" Using I2C pins: ", I2Cpins)
    try: from Config import I2Cdevices
    except: pass
    print("Search for I2C meteo devices", I2Cdevices)
    # print("Wrong wiring may hang I2C address scan search...")
    bus = None; device = None; address = None; nr = None
    for index in range(0,len(I2Cpins)):
        if len(I2Cpins[index]) == 2:
          I2Cpins[index] = tuple(list(I2Cpins[index])+[None])
        cur_i2c = I2C(index, I2C.MASTER, pins=I2Cpins[index][:2]) # master
        regs = cur_i2c.scan(); sleep_ms(200)
        for item in I2Cdevices:
            if type(item) is tuple: item = list(item)
            if item[1] in regs:
                ID = chip_ID(I2Cpins[index], cur_i2c, item[1])
                if item[0][:3] == 'BME':
                  if ID == BME680_ID: item[0] = 'BME680'
                  elif ID != BME280_ID: raise IOError("Unknown BME id 0x%X" % ID)
                print('%s ID=0x%X I2C[%d]:' % (item[0],ID,index), ' SDA~>%s, SCL~>%s, Pwr->' % I2Cpins[index][:2], I2Cpins[index][2], ', reg 0x%2X' % item[1])
                if device: continue  # first one is shown
                device = item[0]
                if not device[:3] in names: continue
                bus = cur_i2c; nr = index
                address = item[1]
    return(nr,bus,device,address)

(nr,i2c,meteo,addr) = searchDev(names=['BME','SHT'])
if not i2c: raise ValueError("No meteo module found")

try:
  from Config import calibrate
except:
  calibrate = None

# Create library object using our Bus I2C port
try:
    if meteo == 'BME280':
      import BME280 as BME
      useMeteo = BME.BME_I2C(i2c, address=addr, debug=False, calibrate=calibrate)
    elif meteo == 'BME680':
      import BME_I2C as BME
      useMeteo = BME.BME_I2C(i2c, address=addr, debug=False, calibrate=calibrate)
    elif meteo[:3] == 'SHT':
        import Adafruit_SHT31 as SHT
        useMeteo = SHT.SHT31(address=addr, i2c=i2c, calibrate=calibrate)
    else: raise ValueError(meteo)
except ImportError:
    raise ValueError("SHT or BME library not installed")
except Exception as e:
    raise ValueError("Fatal: meteo module %s" % e)

print("Found I2C meteo device %s" % meteo)
# change this to match the location's pressure (hPa) at sea level
useMeteo.sea_level_pressure = 1024.25 # 1013.25
for cnt in range(5):
  try:
    print("\nTemperature: %0.1f C" % useMeteo.temperature)
    hum = useMeteo.humidity
    print("Humidity: %0.1f %%" % hum)
    if meteo[:3] == 'BME':
        useMeteo.sea_level_pressure -= 0.5
        print("Pressure: %0.3f hPa" % useMeteo.pressure)
        print("Altitude = %0.2f meters with sea level pressure: %.2f hPa" % (useMeteo.altitude,useMeteo.sea_level_pressure))
    if meteo is 'BME680':
        if not cnt:
            try:
              from Config import M_gBase  # if present do not recalculate
              useMeteo.gas_base = M_gBase
              gBase = True
            except: useMeteo.gas_base = None # force recalculation gas base line
        if useMeteo.gas_base == None:
            gBase = False
            print("%salculating stable gas base level. Can take max 5 minutes to calculate gas base." % ('Rec' if cnt else 'C'))
        else: gBase = True
        AQI = useMeteo.AQI # first time can take a while
        if useMeteo.gas_base != None:
            print("Gas base line calculated: %.1f" % useMeteo.gas_base)
            gBase = True
        gas = useMeteo.gas
        print("Gas: %.3f Kohm" % round(gas/1000.0,2))
        if (useMeteo.gas_base != None) and (AQI != None):
            print("AQI: %0.1f %%" % AQI)
        else:
            print("Was unable to calculate AQI. Will try again.")
            sleep_ms(30*1000)
            continue
        break
  except OSError as e:
    print("Got OS error: %s. Will try again." % e)
    i2c.init(I2C.MASTER,pins=I2Cpins[nr][:2])
    sleep_ms(1000)
import sys
sys.exit()
