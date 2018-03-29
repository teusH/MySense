"""@package docstring
asdfasdfsadf"""
# comes from Adafruit
# Changes by teus "$Revision: 2.1 $"

from micropython import const
from Device import *
import time
import math

# BME280 default address.
BME280_I2CADDR = const(0x76)

# Operating Modes
BME280_OSAMPLE_1 = const(1)
BME280_OSAMPLE_2 = const(2)
BME280_OSAMPLE_4 = const(3)
BME280_OSAMPLE_8 = const(4)
BME280_OSAMPLE_16 = const(5)

# BME280 Registers

BME280_REGISTER_DIG_T1 = const(0x88)  # Trimming parameter registers
BME280_REGISTER_DIG_T2 = const(0x8A)
BME280_REGISTER_DIG_T3 = const(0x8C)

BME280_REGISTER_DIG_P1 = const(0x8E)
BME280_REGISTER_DIG_P2 = const(0x90)
BME280_REGISTER_DIG_P3 = const(0x92)
BME280_REGISTER_DIG_P4 = const(0x94)
BME280_REGISTER_DIG_P5 = const(0x96)
BME280_REGISTER_DIG_P6 = const(0x98)
BME280_REGISTER_DIG_P7 = const(0x9A)
BME280_REGISTER_DIG_P8 = const(0x9C)
BME280_REGISTER_DIG_P9 = const(0x9E)

BME280_REGISTER_DIG_H1 = const(0xA1)
BME280_REGISTER_DIG_H2 = const(0xE1)
BME280_REGISTER_DIG_H3 = const(0xE3)
BME280_REGISTER_DIG_H4 = const(0xE4)
BME280_REGISTER_DIG_H5 = const(0xE5)
BME280_REGISTER_DIG_H6 = const(0xE6)
BME280_REGISTER_DIG_H7 = const(0xE7)

BME280_REGISTER_CHIPID = const(0xD0)
BME280_REGISTER_VERSION = const(0xD1)
BME280_REGISTER_SOFTRESET = const(0xE0)

BME280_REGISTER_CONTROL_HUM = const(0xF2)
BME280_REGISTER_CONTROL = const(0xF4)
BME280_REGISTER_CONFIG = const(0xF5)
BME280_REGISTER_PRESSURE_DATA = const(0xF7)
BME280_REGISTER_TEMP_DATA = const(0xFA)
BME280_REGISTER_HUMIDITY_DATA = const(0xFD)

class BME_I2C:
  def __init__(self, mode=BME280_OSAMPLE_1, address=BME280_I2CADDR, i2c=None, raw=False, calibrate=None
         **kwargs):
    # Check that mode is valid.
    if mode not in [BME280_OSAMPLE_1, BME280_OSAMPLE_2, BME280_OSAMPLE_4,
            BME280_OSAMPLE_8, BME280_OSAMPLE_16]:
      raise ValueError(
        'Unexpected mode value {0}. Set mode to one of '
        'BME280_ULTRALOWPOWER, BME280_STANDARD, BME280_HIGHRES, or '
        'BME280_ULTRAHIGHRES'.format(mode))
    self._mode = mode
    # Create I2C device.
    if i2c is None:
      raise ValueError('An I2C object is required.')
    self._device = Device(address, i2c)
    # Load calibration values.
    self._load_calibration()
    self._device.write8(BME280_REGISTER_CONTROL, 0x3F)
    self.t_fine = 0
    self.sea_level_pressure = 1010.25
    """Pressure in hectoPascals at sea level. Used to calibrate ``altitude``."""
    self.raw = raw
    self.calibrate = { 'temperature': None, 'pressure': None, 'humidity': None, 'altitude': None}
    if (not raw) and (type(calibrate) is dict):
      for k in calibrate.keys():
        if (not k in self.calibrate.keys()) or (not type(calibrate[k]) is list):
          continue
        self.calibrate[k] = calibrate[k]

  # calibrate by length calibration factor (Taylor) array
  def _calibrate(self, cal,value,raw=False):
    if raw or self.raw: return value
    if (not cal) or (type(cal) != list):
      return round(value,2)
    if type(value) is int: value = float(value)
    if not type(value) is float:
      return None
    rts = 0; pow = 0
    for a in cal:
      rts += a*(value**pow)
      pow += 1
    return rts

  def _load_calibration(self):

    self.dig_T1 = self._device.readU16LE(BME280_REGISTER_DIG_T1)
    self.dig_T2 = self._device.readS16LE(BME280_REGISTER_DIG_T2)
    self.dig_T3 = self._device.readS16LE(BME280_REGISTER_DIG_T3)

    self.dig_P1 = self._device.readU16LE(BME280_REGISTER_DIG_P1)
    self.dig_P2 = self._device.readS16LE(BME280_REGISTER_DIG_P2)
    self.dig_P3 = self._device.readS16LE(BME280_REGISTER_DIG_P3)
    self.dig_P4 = self._device.readS16LE(BME280_REGISTER_DIG_P4)
    self.dig_P5 = self._device.readS16LE(BME280_REGISTER_DIG_P5)
    self.dig_P6 = self._device.readS16LE(BME280_REGISTER_DIG_P6)
    self.dig_P7 = self._device.readS16LE(BME280_REGISTER_DIG_P7)
    self.dig_P8 = self._device.readS16LE(BME280_REGISTER_DIG_P8)
    self.dig_P9 = self._device.readS16LE(BME280_REGISTER_DIG_P9)

    self.dig_H1 = self._device.readU8(BME280_REGISTER_DIG_H1)
    self.dig_H2 = self._device.readS16LE(BME280_REGISTER_DIG_H2)
    self.dig_H3 = self._device.readU8(BME280_REGISTER_DIG_H3)
    self.dig_H6 = self._device.readS8(BME280_REGISTER_DIG_H7)

    h4 = self._device.readS8(BME280_REGISTER_DIG_H4)
    h4 = (h4 << 24) >> 20
    self.dig_H4 = h4 | (self._device.readU8(BME280_REGISTER_DIG_H5) & 0x0F)

    h5 = self._device.readS8(BME280_REGISTER_DIG_H6)
    h5 = (h5 << 24) >> 20
    self.dig_H5 = h5 | (
      self._device.readU8(BME280_REGISTER_DIG_H5) >> 4 & 0x0F)

  def read_raw_temp(self):
    """Reads the raw (uncompensated) temperature from the sensor."""
    meas = self._mode
    self._device.write8(BME280_REGISTER_CONTROL_HUM, meas)
    meas = self._mode << 5 | self._mode << 2 | 1
    self._device.write8(BME280_REGISTER_CONTROL, meas)
    sleep_time = 1250 + 2300 * (1 << self._mode)
    sleep_time = sleep_time + 2300 * (1 << self._mode) + 575
    sleep_time = sleep_time + 2300 * (1 << self._mode) + 575
    time.sleep_us(sleep_time)  # Wait the required time
    msb = self._device.readU8(BME280_REGISTER_TEMP_DATA)
    lsb = self._device.readU8(BME280_REGISTER_TEMP_DATA + 1)
    xlsb = self._device.readU8(BME280_REGISTER_TEMP_DATA + 2)
    raw = ((msb << 16) | (lsb << 8) | xlsb) >> 4
    return raw

  def read_raw_pressure(self):
    """Reads the raw (uncompensated) pressure level from the sensor."""
    """Assumes that the temperature has already been read """
    """i.e. that enough delay has been provided"""
    msb = self._device.readU8(BME280_REGISTER_PRESSURE_DATA)
    lsb = self._device.readU8(BME280_REGISTER_PRESSURE_DATA + 1)
    xlsb = self._device.readU8(BME280_REGISTER_PRESSURE_DATA + 2)
    raw = ((msb << 16) | (lsb << 8) | xlsb) >> 4
    return raw

  def read_raw_humidity(self):
    """Assumes that the temperature has already been read """
    """i.e. that enough delay has been provided"""
    msb = self._device.readU8(BME280_REGISTER_HUMIDITY_DATA)
    lsb = self._device.readU8(BME280_REGISTER_HUMIDITY_DATA + 1)
    raw = (msb << 8) | lsb
    return raw

  def read_temperature(self):
    """Get the compensated temperature in 0.01 of a degree celsius."""
    adc = self.read_raw_temp()
    var1 = ((adc >> 3) - (self.dig_T1 << 1)) * (self.dig_T2 >> 11)
    var2 = ((
      (((adc >> 4) - self.dig_T1) * ((adc >> 4) - self.dig_T1)) >> 12) *
      self.dig_T3) >> 14
    self.t_fine = var1 + var2
    return (self.t_fine * 5 + 128) >> 8

  def read_pressure(self):
    """Gets the compensated pressure in Pascals."""
    adc = self.read_raw_pressure()
    var1 = self.t_fine - 128000
    var2 = var1 * var1 * self.dig_P6
    var2 = var2 + ((var1 * self.dig_P5) << 17)
    var2 = var2 + (self.dig_P4 << 35)
    var1 = (((var1 * var1 * self.dig_P3) >> 8) +
        ((var1 * self.dig_P2) >> 12))
    var1 = (((1 << 47) + var1) * self.dig_P1) >> 33
    if var1 == 0:
      return 0
    p = 1048576 - adc
    p = (((p << 31) - var2) * 3125) // var1
    var1 = (self.dig_P9 * (p >> 13) * (p >> 13)) >> 25
    var2 = (self.dig_P8 * p) >> 19
    return ((p + var1 + var2) >> 8) + (self.dig_P7 << 4)

  def read_humidity(self):
    adc = self.read_raw_humidity()
    # print 'Raw humidity = {0:d}'.format (adc)
    h = self.t_fine - 76800
    h = (((((adc << 14) - (self.dig_H4 << 20) - (self.dig_H5 * h)) +
       16384) >> 15) * (((((((h * self.dig_H6) >> 10) * (((h *
                self.dig_H3) >> 11) + 32768)) >> 10) + 2097152) *
                self.dig_H2 + 8192) >> 14))
    h = h - (((((h >> 15) * (h >> 15)) >> 7) * self.dig_H1) >> 4)
    h = 0 if h < 0 else h
    h = 419430400 if h > 419430400 else h
    return h >> 12

  @property
  def temperature(self,raw=False):
    "Return the temperature in degrees."
    t = self.read_temperature() / 100.0
    return self._calibrate(self.calibrate['temperature'],t,raw=raw)
    #ti = t // 100
    #td = t - ti * 100
    #time.sleep(2)
    #return "{}.{:02d}".format(ti, td)

  @property
  def pressure(self,raw=False):
    "Return the pressure in hPa."
    p = self.read_pressure() // 256
    return self._calibrate(self.calibrate['pressure'],p,raw=raw)
    #pi = p // 100
    #pd = p - pi * 100
    #return "{}.{:1d}".format(pi, pd)

  @property
  def humidity(self,raw=False):
    "Return the humidity in percent."
    h = self.read_humidity() // 1024
    return self._calibrate(self.calibrate['humidity'],h,raw=raw)
    #hi = h // 1024
    #hd = h * 100 // 1024 - hi * 100
    #if hd >= 50:
	#    hi = hi + 1
    #return "{}".format(hi)

  @property
  def altitude(self,raw=False):
    """The altitude based on current ``pressure`` vs the sea level pressure
       (``sea_level_pressure``) - which you must enter ahead of time)"""
    pressure = self.pressure # in Si units for hPascal
    pressure =  44330 * (1.0 - math.pow(pressure / self.sea_level_pressure, 0.1903))
    return self._calibrate(self.calibrate['altitude'],pressure, raw=raw)


