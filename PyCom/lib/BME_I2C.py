# TO DO: allow disable/enable gas, RII filter, etc.
from time import time, sleep_ms, ticks_ms
import bme680
import math
from bme680.constants import I2C_ADDR_PRIMARY,OS_2X,OS_4X,OS_8X,FILTER_SIZE_3,ENABLE_GAS_MEAS

class BME_I2C:
  def __init__(self, i2c_device, address=I2C_ADDR_PRIMARY, debug=False, calibrate=None, raw=False):
    self.sensor = bme680.BME680(i2c_addr=address, i2c_device=i2c_device)
    self.gas_base = None
    self.debug = debug
    # These oversampling settings can be tweaked to
    # change the balance between accuracy and noise in
    # the data.

    self.sensor.set_humidity_oversample(OS_2X)
    self.sensor.set_pressure_oversample(OS_4X)
    self.sensor.set_temperature_oversample(OS_8X)
    self.sensor.set_filter(FILTER_SIZE_3)
    self.sensor.set_gas_status(ENABLE_GAS_MEAS)

    self.sensor.set_gas_heater_temperature(320)
    self.sensor.set_gas_heater_duration(150)
    self.sensor.select_gas_heater_profile(0)

    self.calibrate = { 'temperature': None, 'pressure': None, 'humidity': None, 'altitude': None, 'gas': None, 'gas base': None}
    if type(calibrate) is dict:
      for k in calibrate.keys():
        if (not k in self.calibrate.keys()) or (not type(calibrate[k]) is list):
          continue
        self.calibrate[k] = calibrate[k]
    self.raw = raw
    self.updated = 0 # millis of last BME680 data update


    self.sea_level_pressure = 1010.0
    # Set the humidity baseline to 40%, an optimal outdoor humidity.
    self.hum_base = 80.0
    # This sets the balance between humidity and gas reading in the
    # calculation of air_quality_score (25:75, humidity:gas)
    self.hum_weight = 0.25
    self.gas_base = self.calibrate['gas base']

  # calibrate by length calibration factor (Taylor) array
  def _calibrate(self,cal,value):
    if self.raw: return value
    if type(value) is int: value = float(value)
    elif not type(value) is float: return None
    if (not cal) or (type(cal) != list):
      return round(value,2)
    rts = 0; pow = 0
    for a in cal:
      rts += a*(value**pow)
      pow += 1
    return rts

  def get_data(self):
    if (ticks_ms() - self.updated) > 500:
      for i in range(0,5):
        if self.sensor.get_sensor_data(): break
        if i == 4: return False
        self.updated = ticks_ms()
    return True

  @property
  def temperature(self):
    if not self.get_data(): return None
    val = self._calibrate(self.calibrate['temperature'],self.sensor.data.temperature)
    if (val < -50) or (val > 80): return None
    return val

  @property
  def pressure(self):
    if not self.get_data(): return None
    val = self._calibrate(self.calibrate['pressure'],self.sensor.data.pressure)
    if (val < 200) or (val > 2000): return None
    return val

  @property
  def humidity(self):
    if not self.get_data(): return None
    val = self._calibrate(self.calibrate['humidity'],self.sensor.data.humidity)
    if (val < 0) or (val > 100): return None
    return val

  @property
  def altitude(self):
    return 44330 * (1.0 - math.pow(self.pressure / self.sea_level_pressure, 0.1903))

  @property
  def gas(self):
    if not self.get_data(): return None
    return self._calibrate(self.calibrate['gas'],self.sensor.data.gas_resistance)

    # after https://github.com/pimoroni/bme680/examples
  # burn in and calculate baseline
  def _gasBase(self):
    self.gas_base = None
    BURN_TIME = const(300)  # 5 minutes
    if self.debug:
      print("Gas resistance burn-in max: %d minutes" % (BURN_TIME/60))
    strt_time = time(); cur_time = time()
    data = []; prev_gas = 0; stable = False; cnt = 0
    while cur_time - strt_time < BURN_TIME:
      cur_time = time()
      if self.get_data():
        gas = self._calibrate(self.calibrate['gas'],self.sensor.data.gas_resistance)
        if (not stable ) and abs(gas - prev_gas) < 1000:
          if cnt > 3:
            stable = True
          else:
            cnt += 1
        elif not stable: cnt = 0
        if self.sensor.data.heat_stable and stable:
          if len(data) < 50:
            data.append(gas)
          else:
            data.pop(); data.insert(0,gas)
          if self.debug: print("time: %dm%ds, gas: %d Ohms" % (int(cur_time-strt_time)/60,int(cur_time-strt_time)%60,gas))
          if len(data) >= 50: break
        else:
          if self.debug: print("time: %dm%ds: heating up %d" % (int(cur_time-strt_time)/60,int(cur_time-strt_time)%60,gas))
        prev_gas = gas
      sleep_ms(800)
    if len(data):
      self.gas_base = float(sum(data[0:]))/len(data)
      return True
    return False

  @property
  def AQI(self):
    # calculate gas base line. Can take 5 minutes
    if not self.gas_base:
      if  not self._gasBase(): return None
    if not (self.get_data() and self.sensor.data.heat_stable): return None
    hum_offset = self._calibrate(self.calibrate['humidity'],self.sensor.data.humidity) - self.hum_base
    gas_offset = self.gas_base - self.sensor.data.gas_resistance
    if hum_offset > 0:
      hum_score = (100-self.hum_base-hum_offset)/(100-self.hum_base)*(self.hum_weight*100)
    else:
      hum_score = (self.hum_base + hum_offset) / self.hum_base * (self.hum_weight * 100)
    # Calculate gas_score as the distance from the gas_baseline.
    if gas_offset > 0:
      gas_score = (self._calibrate(self.calibrate['gas'],self.sensor.data.gas_resistance) / self.gas_base) * (100 - (self.hum_weight * 100))
    else:
      gas_score = 100 - (self.hum_weight * 100)
    # Calculate air_quality_score.
    val = hum_score + gas_score
    if (val < 0) or (val > 100): return None
    return val
