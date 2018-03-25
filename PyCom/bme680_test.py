# from: http://circuitpython.readthedocs.io/projects/bme680/en/latest/examples.html
from time import time, sleep
from machine import I2C
import BME680

try:
   from Config import Meteo, useMeteo, meteo, M_ID, M_SDA, M_SCL
   if meteo != 4: OSError("Not configured as BME680")
except:
   print("Use default config")
   M_ID=0; M_SDA = 'P7'; M_SCL = 'P8'

print("Use config I2C BME SDA on pin %s, SCL on pin %s" % (M_SDA,M_SCL))

# Create library object using our Bus I2C port
i2c = I2C(M_ID, pins=(M_SDA,M_SCL)) # master
bme680 = BME680.Adafruit_BME680_I2C(i2c, address=0x76, debug=False)

# change this to match the location's pressure (hPa) at sea level
bme680.sea_level_pressure = 1014.25 # 1013.25

for cnt in range(15):
    print("\nTemperature: %0.1f C" % bme680.temperature)
    hum = bme680.humidity
    print("Humidity: %0.1f %%" % hum)
    bme680.sea_level_pressure -= 0.5
    print("Pressure: %0.3f hPa" % bme680.pressure)
    print("Altitude = %0.2f meters with sea level pressure: %.2f hPa" % (bme680.altitude,bme680.sea_level_pressure))
    if not cnt:
        bme680.gas_base = None # force recalculation gas base line
        print("First AQI call can take max 5 minutes to calculate gas base.")
    AQI = bme680.AQI # first time can take a while
    if not cnt:
        print("Gas base line calculated: %.1f" % bme680.gas_base)
    print("AQI: %0.1f %%" % AQI)
    gas = bme680.gas
    print("Gas: %d ohm" % gas)

    sleep(30)
