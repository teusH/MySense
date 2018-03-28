from time import sleep
from machine import I2C
Meteo = ['','DHT11','DHT22','BME280','BME680']
try:
    from Config import useMeteo, meteo, M_SDA, M_SCL, M_ID
except:
    print("Using default config")
    meteo = 3   # default BME280
    M_SDA = 'P7'
    M_SCL = 'P8'
    M_ID = 0
    useMeteo = True
try:
    if meteo == 4:
        import BME680 as BME
    elif meteo == 3:
        import BME280 as BME
    else: useMeteo = False
except:
    raise OSError("Missing library %s" % Meteo[meteo])

print("Using %s config I2C %d SDA on pin %s, SCL on pin %s" % (Meteo[meteo],M_ID,M_SDA,M_SCL))

# Create library object using our Bus I2C port
i2c = I2C(M_ID, pins=(M_SDA,M_SCL)) # master
useMeteo = BME.BME_I2C(i2c, address=0x76, debug=False)

# change this to match the location's pressure (hPa) at sea level
useMeteo.sea_level_pressure = 1014.25 # 1013.25

for cnt in range(15):
    print("\nTemperature: %0.1f C" % useMeteo.temperature)
    hum = useMeteo.humidity
    print("Humidity: %0.1f %%" % hum)
    useMeteo.sea_level_pressure -= 0.5
    print("Pressure: %0.3f hPa" % useMeteo.pressure)
    print("Altitude = %0.2f meters with sea level pressure: %.2f hPa" % (useMeteo.altitude,useMeteo.sea_level_pressure))
    if meteo == 4:
        if not cnt:
            useMeteo.gas_base = None # force recalculation gas base line
            print("First AQI call can take max 5 minutes to calculate gas base.")
        AQI = useMeteo.AQI # first time can take a while
        if not cnt:
            print("Gas base line calculated: %.1f" % useMeteo.gas_base)
        print("AQI: %0.1f %%" % AQI)
        gas = useMeteo.gas
        print("Gas: %.3f Kohm" % gas)

    sleep(30)
