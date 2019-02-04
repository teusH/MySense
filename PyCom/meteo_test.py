from time import sleep
from machine import I2C

__version__ = "0." + "$Revision: 3.5 $"[11:-2]
__license__ = 'GPLV4'

def searchDev(names=['BME','SHT','SSD']):
    try:
        from Config import I2Cpins, I2Cdevices
    except:
        raise ValueError("Define I22Pins, I2Cdevices in Config.py")
    print("Wrong wiring may hang I2C address scan search...")
    bus = None
    device = None
    address = None
    nr = None
    for index in range(0,len(I2Cpins)):
        cur_i2c = I2C(index, I2C.MASTER, pins=I2Cpins[index]) # master
        regs = cur_i2c.scan()
        for item in I2Cdevices:
            if item[1] in regs:
                print('%s I2C[%d]:' % (item[0],index), ' SDA ~> %s, SCL ~> %s' % I2Cpins[index], 'address 0x%2X' % item[1])
                if not item[0][:3] in names: continue
                if device: continue  # first one we use
                device = item[0]; bus = cur_i2c; nr = index
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
    if meteo[:3] == 'BME':
        meteo = 'BME280'
        import BME280 as BME
        useMeteo = BME.BME_I2C(i2c, address=addr, debug=False, calibrate=calibrate)
        if (useMeteo.temperature < -40.0) or (useMeteo.pressure < 0.0):
            # this is not a BME280 but a BME680
            del BME
            meteo = 'BME680'
            import BME_I2C as BME
            useMeteo = BME.BME_I2C(i2c, address=addr, debug=False, calibrate=calibrate)
    elif meteo[:3] == 'SHT':
        import Adafruit_SHT31 as SHT
        useMeteo = SHT.SHT31(address=addr, i2c=i2c, calibrate=calibrate)
except:
    raise ValueError("No meteo module connected")

print("Found I2C device %s" % meteo)
# change this to match the location's pressure (hPa) at sea level
useMeteo.sea_level_pressure = 1024.25 # 1013.25
for cnt in range(15):
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
        if useMeteo.gas_base != None and not gBase:
            print("Gas base line calculated: %.1f" % useMeteo.gas_base)
            gBase = True
        if (useMeteo.gas_base != None) and (AQI != None):
            print("AQI: %0.1f %%" % AQI)
        else: print("Was unable to calculate AQI. Will try again.")
        gas = useMeteo.gas
        print("Gas: %.3f Kohm" % round(gas/1000.0,2))
  except OSError as e:
    print("Got OS error: %s. Will try again." % e)
    i2c.init(I2C.MASTER,pins=I2Cpins[nr])
    sleep(1)
    continue
  sleep(30)
