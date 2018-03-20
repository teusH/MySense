# from: http://circuitpython.readthedocs.io/projects/bme680/en/latest/examples.html
from time import time, sleep
from machine import I2C
import BME680

# Create library object using our Bus I2C port
B_SDA = 'P7'
B_SCL = 'P8'
i2c = I2C(0, pins=(B_SDA,B_SCL)) # master
bme680 = BME680.Adafruit_BME680_I2C(i2c, address=0x76, debug=False)

# change this to match the location's pressure (hPa) at sea level
bme680.sea_level_pressure = 1018.25 # 1013.25

# after https://github.com/pimoroni/bme680/examples
# burn in and calculate baseline
hum_base = 45.0 # 80.0 outdoor, 40.0-50.0  indoor best
hum_weight = 0.25 # calculation of air_quality_score (25:75, humidity:gas)
gas_base = None
def burnIn(bme):
    global gas_base
    BURN_TIME = const(300)  # 5 minutes
    print("Collecting gas resistance burn-in data for %d mins" % (BURN_TIME/60))
    strt_time = time(); cur_time = time()
    data = []; prev_gas = 0; stable = False; cnt = 0
    while cur_time - strt_time < BURN_TIME:
        cur_time = time()
        gas = bme.gas
        if (not stable ) and abs(gas - prev_gas) < 1000:
            if cnt > 3:
                stable = True
            else:
                cnt += 1
        elif not stable: cnt = 0
        if ((bme._status & 0x30) == 0x30) and stable:
            if len(data) < 50 :
                data.append(gas)
            else:
                data.pop() ; data.insert(0,gas)
            print("time: %dm%ds, gas: %d Ohms" % (int(cur_time-strt_time)/60,int(cur_time-strt_time)%60,gas))
            if len(data) >= 50: break
        else:
            print("time: %dm%ds: heating up %d" % (int(cur_time-strt_time)/60,int(cur_time-strt_time)%60,gas))
        prev_gas = gas
        sleep(1)
    gas_base = float(sum(data[0:]))/len(data)

def AQI(gas,hum):
    global gas_base, hum_base, hum_weight
    if not gas_base: return None
    hum_offset = hum - hum_base
    gas_offset = gas_base - gas
    if hum_offset > 0:
        hum_score = (100-hum_base-hum_offset)/(100-hum_base)*(hum_weight*100)
    else:
        hum_score = (hum_base + hum_offset) / hum_base * (hum_weight * 100)

    # Calculate gas_score as the distance from the gas_baseline.
    if gas_offset > 0:
        gas_score = (gas / gas_base) * (100 - (hum_weight * 100))
    else:
        gas_score = 100 - (hum_weight * 100)
    # Calculate gas_score as the distance from the gas_baseline.
    if gas_offset > 0:
        gas_score = (gas / gas_base) * (100 - (hum_weight * 100))
    else:
        gas_score = 100 - (hum_weight * 100)
    # Calculate air_quality_score. 
    return hum_score + gas_score

burnIn(bme680) # detect gas baseline
while True:
    print("\nTemperature: %0.1f C" % bme680.temperature)
    hum = bme680.humidity
    gas = bme680.gas
    print("Humidity: %0.1f %%" % hum)
    print("Pressure: %0.3f hPa" % bme680.pressure)
    print("Altitude = %0.2f meters" % bme680.altitude)
    print("Gas: %d ohm" % gas)
    print("AQI: %0.1f %%" % AQI(gas,hum))

    sleep(30)
