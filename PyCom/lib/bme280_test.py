from time import sleep
from machine import I2C
import BME280

# Create library object using our Bus I2C port
B_SDA = 'P7'
B_SCL = 'P8'
i2c = I2C(0, pins=(B_SDA,B_SCL)) # master
bme280 = BME280(i2c=i2c,address=0x76)

# change this to match the location's pressure (hPa) at sea level
#bme280.sea_level_pressure = 1018.25 # 1013.25

for cnt in range(10):
    print("\nTemperature: %0.1f C" % bme280.temperature)
    print("Humidity: %0.1f %%" % bme280.humidity)
    print("Pressure: %0.3f hPa" % bme280.pressure)
    print("Altitude = %0.2f meters" % bme280.altitude)
    sleep(30)
