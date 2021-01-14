# The MIT License (MIT)
#
# Copyright (c) 2017 ladyada for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# We have a lot of attributes for this complex sensor.
# pylint: disable=too-many-instance-attributes

"""
`adafruit_bme680`
================================================================================

CircuitPython library for BME680 temperature, pressure and humidity sensor.


* Author(s): Limor Fried

Implementation Notes
--------------------

**Hardware:**

* `Adafruit BME680 Temp, Humidity, Pressure and Gas Sensor <https://www.adafruit.com/product/3660>`_

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases
* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
# MySense interface adaptations changes by teus 2020-12-24
"""


import time
import math
from micropython import const

try:
    import struct
except ImportError:
    import ustruct as struct

__version__ = "0." + "$Revision: 6.2 $"[11:-2]
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_BME680.git"


#    I2C ADDRESS/BITS/SETTINGS
#    -----------------------------------------------------------------------
_BME680_CHIPID = const(0x61)

_BME680_REG_CHIPID = const(0xD0)
_BME680_BME680_COEFF_ADDR1 = const(0x89)
_BME680_BME680_COEFF_ADDR2 = const(0xE1)
_BME680_BME680_RES_HEAT_0 = const(0x5A)
_BME680_BME680_GAS_WAIT_0 = const(0x64)

_BME680_REG_SOFTRESET = const(0xE0)
_BME680_REG_CTRL_GAS = const(0x71)
_BME680_REG_CTRL_HUM = const(0x72)
_BME680_REG_STATUS = const(0x73)
_BME680_REG_CTRL_MEAS = const(0x74)
_BME680_REG_CONFIG = const(0x75)

_BME680_REG_MEAS_STATUS = const(0x1D)
_BME680_REG_PDATA = const(0x1F)
_BME680_REG_TDATA = const(0x22)
_BME680_REG_HDATA = const(0x25)

_BME680_SAMPLERATES = (0, 1, 2, 4, 8, 16)
_BME680_FILTERSIZES = (0, 1, 3, 7, 15, 31, 63, 127)

_BME680_RUNGAS = const(0x10)

_LOOKUP_TABLE_1 = (
    2147483647.0,
    2147483647.0,
    2147483647.0,
    2147483647.0,
    2147483647.0,
    2126008810.0,
    2147483647.0,
    2130303777.0,
    2147483647.0,
    2147483647.0,
    2143188679.0,
    2136746228.0,
    2147483647.0,
    2126008810.0,
    2147483647.0,
    2147483647.0,
)

_LOOKUP_TABLE_2 = (
    4096000000.0,
    2048000000.0,
    1024000000.0,
    512000000.0,
    255744255.0,
    127110228.0,
    64000000.0,
    32258064.0,
    16016016.0,
    8000000.0,
    4000000.0,
    2000000.0,
    1000000.0,
    500000.0,
    250000.0,
    125000.0,
)


def _read24(arr):
    """Parse an unsigned 24-bit value as a floating point and return it."""
    ret = 0.0
    # print([hex(i) for i in arr])
    for b in arr:
        ret *= 256.0
        ret += float(b & 0xFF)
    return ret


class Adafruit_BME680:
    """Driver from BME680 air quality sensor

       :param int refresh_rate: Maximum number of readings per second. Faster property reads
         will be from the previous reading."""

    # def __init__(self, *, refresh_rate=10):
    def __init__(self, raw=False, calibrate=None, debug=False, refresh_rate=10):
        """Check the BME680 was found, read the coefficients and enable the sensor for continuous
           reads."""
        self._write(_BME680_REG_SOFTRESET, [0xB6])
        time.sleep_ms(5)

        # Check device ID.
        chip_id = self._read_byte(_BME680_REG_CHIPID)
        if chip_id != _BME680_CHIPID:
            raise RuntimeError("Failed to find BME680! Chip ID 0x%x" % chip_id)

        self._read_calibration()

        # set up heater
        self._write(_BME680_BME680_RES_HEAT_0, [0x73])
        self._write(_BME680_BME680_GAS_WAIT_0, [0x65])

        self.sea_level_pressure = 1013.25
        """Pressure in hectoPascals at sea level. Used to calibrate ``altitude``."""
        # added
        self.raw = raw
        self.calibrate = { 'temperature': None, 'pressure': None, 'humidity': None, 'altitude': None, 'gas': None, 'AQI': None, 'gas_base': None}
        if (not raw) and (type(calibrate) is dict):
          for k in calibrate.keys():
            if not k in self.calibrate.keys(): continue
            if (not k is 'gas_base') and (not type(calibrate[k]) is list):
              continue
            self.calibrate[k] = calibrate[k]

        self._debug = debug
        # Default oversampling and filter register values.
        self._pressure_oversample = 0b011
        self._temp_oversample = 0b100
        self._humidity_oversample = 0b010
        self._filter = 0b010

        self._adc_pres = None
        self._adc_temp = None
        self._adc_hum = None
        self._adc_gas = None
        self._gas_range = None
        self._t_fine = None
        self.hum_base = 80.0 # 80.0 outdoor best, 40.0-50.0  indoor best
        self.hum_weight = 0.25 # calculation of AQ score (25:75, humidity:gas)
        self._t_fine = None
        self._status = 0
        self.gas_base = self.calibrate['gas_base']

        self._last_reading = 0
        self._min_refresh_time = int(1 / refresh_rate * 1000) # in milli secs

    @property
    def pressure_oversample(self):
        """The oversampling for pressure sensor"""
        return _BME680_SAMPLERATES[self._pressure_oversample]

    # calibrate by length calibration factor (Taylor) array
    def _calibrate(self,cal,value):
      if self.raw: return value
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

    @pressure_oversample.setter
    def pressure_oversample(self, sample_rate):
        if sample_rate in _BME680_SAMPLERATES:
            self._pressure_oversample = _BME680_SAMPLERATES.index(sample_rate)
        else:
            raise RuntimeError("Invalid oversample")

    @property
    def humidity_oversample(self):
        """The oversampling for humidity sensor"""
        return _BME680_SAMPLERATES[self._humidity_oversample]

    @humidity_oversample.setter
    def humidity_oversample(self, sample_rate):
        if sample_rate in _BME680_SAMPLERATES:
            self._humidity_oversample = _BME680_SAMPLERATES.index(sample_rate)
        else:
            raise RuntimeError("Invalid oversample")

    @property
    def temperature_oversample(self):
        """The oversampling for temperature sensor"""
        return _BME680_SAMPLERATES[self._temp_oversample]

    @temperature_oversample.setter
    def temperature_oversample(self, sample_rate):
        if sample_rate in _BME680_SAMPLERATES:
            self._temp_oversample = _BME680_SAMPLERATES.index(sample_rate)
        else:
            raise RuntimeError("Invalid oversample")

    @property
    def filter_size(self):
        """The filter size for the built in IIR filter"""
        return _BME680_FILTERSIZES[self._filter]

    @filter_size.setter
    def filter_size(self, size):
        if size in _BME680_FILTERSIZES:
            self._filter = _BME680_FILTERSIZES.index(size)
        else:
            raise RuntimeError("Invalid size")

    @property
    def temperature(self):
        """The compensated temperature in degrees celsius."""
        self._perform_reading()
        calc_temp = ((self._t_fine * 5) + 128) / 256
        return self._calibrate(self.calibrate['temperature'],calc_temp / 100) #

    @property
    def pressure(self):
        """The barometric pressure in hectoPascals"""
        self._perform_reading()
        var1 = (self._t_fine / 2) - 64000
        var2 = ((var1 / 4) * (var1 / 4)) / 2048
        var2 = (var2 * self._pressure_calibration[5]) / 4
        var2 = var2 + (var1 * self._pressure_calibration[4] * 2)
        var2 = (var2 / 4) + (self._pressure_calibration[3] * 65536)
        var1 = (
            (((var1 / 4) * (var1 / 4)) / 8192)
            * (self._pressure_calibration[2] * 32)
            / 8
        ) + ((self._pressure_calibration[1] * var1) / 2)
        var1 = var1 / 262144
        var1 = ((32768 + var1) * self._pressure_calibration[0]) / 32768
        calc_pres = 1048576 - self._adc_pres
        calc_pres = (calc_pres - (var2 / 4096)) * 3125
        calc_pres = (calc_pres / var1) * 2
        var1 = (
            self._pressure_calibration[8] * (((calc_pres / 8) * (calc_pres / 8)) / 8192)
        ) / 4096
        var2 = ((calc_pres / 4) * self._pressure_calibration[7]) / 8192
        var3 = (((calc_pres / 256) ** 3) * self._pressure_calibration[9]) / 131072
        calc_pres += (var1 + var2 + var3 + (self._pressure_calibration[6] * 128)) / 16
        return self._calibrate(self.calibrate['pressure'],calc_pres/100) #

    @property
    def relative_humidity(self):
        """The relative humidity in RH %"""
        return self.humidity

    @property
    def humidity(self):
        """The relative humidity in RH %"""
        self._perform_reading()
        temp_scaled = ((self._t_fine * 5) + 128) / 256
        var1 = (self._adc_hum - (self._humidity_calibration[0] * 16)) - (
            (temp_scaled * self._humidity_calibration[2]) / 200
        )
        var2 = (
            self._humidity_calibration[1]
            * (
                ((temp_scaled * self._humidity_calibration[3]) / 100)
                + (
                    (
                        (
                            temp_scaled
                            * ((temp_scaled * self._humidity_calibration[4]) / 100)
                        )
                        / 64
                    )
                    / 100
                )
                + 16384
            )
        ) / 1024
        var3 = var1 * var2
        var4 = self._humidity_calibration[5] * 128
        var4 = (var4 + ((temp_scaled * self._humidity_calibration[6]) / 100)) / 16
        var5 = ((var3 / 16384) * (var3 / 16384)) / 1024
        var6 = (var4 * var5) / 2
        calc_hum = (((var3 + var6) / 1024) * 1000) / 4096
        calc_hum /= 1000  # get back to RH

        if calc_hum > 100:
            calc_hum = 100
        if calc_hum < 0:
            calc_hum = 0
        return self._calibrate(self.calibrate['humidity'],calc_hum) #

    @property
    def altitude(self):
        """The altitude based on current ``pressure`` vs the sea level pressure
           (``sea_level_pressure``) - which you must enter ahead of time)"""
        pressure = self.pressure  # in Si units for hPascal
        pressure =  44330 * (1.0 - math.pow(pressure / self.sea_level_pressure, 0.1903)) #
        return self._calibrate(self.calibrate['altitude'],pressure) #

    @property
    def gas(self):
        """The gas resistance in ohms"""
        self._perform_reading()
        var1 = (
            (1340 + (5 * self._sw_err)) * (_LOOKUP_TABLE_1[self._gas_range])
        ) / 65536
        var2 = ((self._adc_gas * 32768) - 16777216) + var1
        var3 = (_LOOKUP_TABLE_2[self._gas_range] * var1) / 512
        calc_gas_res = (var3 + (var2 / 2)) / var2
        return int(self._calibrate(self.calibrate['gas'],calc_gas_res)) #

    # after https://github.com/pimoroni/bme680-python/tree/master/examples # added
    # burn in and calculate baseline
    def gasBase(self, redo=False, debug=False):
        if redo: self.gas_base = None
        if not self.gas_base is None: return self.gas_base
        BURN_TIME = const(300)  # 5 minutes
        if self._debug: debug = True
        if debug:
          print("Gas resistance burn-in max: %d minutes" % (BURN_TIME/60))
        strt_time = time.time(); cur_time = time.time()
        data = []; prev_gas = 0
        stable = False; cnt = 0
        while cur_time - strt_time < BURN_TIME:
          cur_time = time.time()
          gas = self.gas
          if (not stable ) and abs(gas - prev_gas) < 3000:
            if cnt > 3: stable = True
            else: cnt += 1
          elif not stable: cnt = 0
          if ((self._status & 0x30) == 0x30) and stable: # STABLE+GAS VALID
            if len(data) >= 49: data.pop(0)
            data.append(gas)
            if debug: print("time: %dm%ds, gas: %d Ohms" % (int(cur_time-strt_time)/60,int(cur_time-strt_time)%60,gas))
            if len(data) >= 49: break
          else:
            if debug: print("time: %dm%ds: heating up %d" % (int(cur_time-strt_time)/60,int(cur_time-strt_time)%60,gas))
          prev_gas = gas
          time.sleep_ms(800)
        if len(data):
          self.gas_base = float(sum(data[-25:]))/len(data)
          return self.gas_base
        return None

    @property
    def AQI(self):  # added
      # calculate gas base line. Can take 5 minutes
      if not self.gas_base:
        if not self.gasBase(): return None
      hum_offset = self.humidity - self.hum_base
      gas_offset = self.gas_base - self.gas
      if hum_offset > 0:
        hum_score = (100-self.hum_base-hum_offset)/(100-self.hum_base)*(self.hum_weight*100)
      else:
        hum_score = (self.hum_base + hum_offset) / self.hum_base * (self.hum_weight * 100)
      # Calculate gas_score as the distance from the gas_baseline.
      if gas_offset > 0:
        gas_score = (self.gas / self.gas_base) * (100 - (self.hum_weight * 100))
      else:
        gas_score = 100 - (self.hum_weight * 100)
      # Calculate air_quality_score.
      return hum_score + gas_score

    def _perform_reading(self):
        """Perform a single-shot reading from the sensor and fill internal data structure for
           calculations"""
        # if time.monotonic() - self._last_reading < self._min_refresh_time:
        if time.ticks_ms()  < time.ticks_add(self._last_reading,self._min_refresh_time):
            return

        # set filter
        self._write(_BME680_REG_CONFIG, [self._filter << 2])
        # turn on temp oversample & pressure oversample
        self._write(
            _BME680_REG_CTRL_MEAS,
            [(self._temp_oversample << 5) | (self._pressure_oversample << 2)],
        )
        # turn on humidity oversample
        self._write(_BME680_REG_CTRL_HUM, [self._humidity_oversample])
        # gas measurements enabled
        self._write(_BME680_REG_CTRL_GAS, [_BME680_RUNGAS])

        ctrl = self._read_byte(_BME680_REG_CTRL_MEAS)
        ctrl = (ctrl & 0xFC) | 0x01  # enable single shot!
        self._write(_BME680_REG_CTRL_MEAS, [ctrl])
        new_data = False
        while not new_data:
            data = self._read(_BME680_REG_MEAS_STATUS, 15)
            new_data = data[0] & 0x80 != 0
            time.sleep_ms(5)
        self._last_reading = time.ticks_ms()  # time.monotonic()
        self._status = data[0] & 0xF #

        self._adc_pres = _read24(data[2:5]) / 16
        self._adc_temp = _read24(data[5:8]) / 16
        self._adc_hum = struct.unpack(">H", bytes(data[8:10]))[0]
        self._adc_gas = int(struct.unpack(">H", bytes(data[13:15]))[0] / 64)
        self._gas_range = data[14] & 0x0F
        self._status |= data[14] & 0x30   # GASM VALID + HEAT STABLE mask #

        var1 = (self._adc_temp / 8) - (self._temp_calibration[0] * 2)
        var2 = (var1 * self._temp_calibration[1]) / 2048
        var3 = ((var1 / 2) * (var1 / 2)) / 4096
        var3 = (var3 * self._temp_calibration[2] * 16) / 16384
        self._t_fine = int(var2 + var3)

    def _read_calibration(self):
        """Read & save the calibration coefficients"""
        coeff = self._read(_BME680_BME680_COEFF_ADDR1, 25)
        coeff += self._read(_BME680_BME680_COEFF_ADDR2, 16)

        coeff = list(struct.unpack("<hbBHhbBhhbbHhhBBBHbbbBbHhbb", bytes(coeff[1:39])))
        # print("\n\n",coeff)
        coeff = [float(i) for i in coeff]
        self._temp_calibration = [coeff[x] for x in [23, 0, 1]]
        self._pressure_calibration = [
            coeff[x] for x in [3, 4, 5, 7, 8, 10, 9, 12, 13, 14]
        ]
        self._humidity_calibration = [coeff[x] for x in [17, 16, 18, 19, 20, 21, 22]]
        self._gas_calibration = [coeff[x] for x in [25, 24, 26]]

        # flip around H1 & H2
        self._humidity_calibration[1] *= 16
        self._humidity_calibration[1] += self._humidity_calibration[0] % 16
        self._humidity_calibration[0] /= 16

        self._heat_range = (self._read_byte(0x02) & 0x30) / 16
        self._heat_val = self._read_byte(0x00)
        self._sw_err = (self._read_byte(0x04) & 0xF0) / 16

    def _read_byte(self, register):
        """Read a byte register value and return it"""
        return self._read(register, 1)[0]

    def _read(self, register, length):
        raise NotImplementedError()

    def _write(self, register, values):
        raise NotImplementedError()


# class Adafruit_BME680_I2C(Adafruit_BME680):
class MyI2C(Adafruit_BME680):

    """Driver for I2C connected BME680.

        :param int address: I2C device address
        :param bool debug: Print debug statements when True.
        :param int refresh_rate: Maximum number of readings per second. Faster property reads
          will be from the previous reading."""

    # def __init__(self, i2c, address=0x77, debug=False, *, refresh_rate=10):
    def __init__(self, i2c, address=0x77, refresh_rate=10, probe=False, lock=None, debug=False, raw=False, calibrate=None):
        """Initialize the I2C device at the 'address' given"""
        #from adafruit_bus_device import (  # pylint: disable=import-outside-toplevel
        #    i2c_device,
        #)
        from i2c_device import I2CDevice

        self._i2c = I2CDevice(i2c, address, probe=probe, lock=lock) #
        self._debug = debug
        super().__init__(raw=raw,calibrate=calibrate, debug=debug, refresh_rate=refresh_rate) #

    def _read(self, register, length):
        """Returns an array of 'length' bytes from the 'register'"""
        with self._i2c as i2c:
            i2c.write(bytes([register & 0xFF]))
            result = bytearray(length)
            i2c.readinto(result)
        if self._debug:
            print("\t$%02X => %s" % (register, [hex(i) for i in result]))
        return result

    def _write(self, register, values):
        """Writes an array of 'length' bytes to the 'register'"""
        buffer = bytearray(2 * len(values))
        for i, value in enumerate(values):
            buffer[2 * i] = register + i
            buffer[2 * i + 1] = value
        with self._i2c as i2c:
            i2c.write(buffer)
        if self._debug:
            print("\t$%02X <= %s" % (values[0], [hex(i) for i in values[1:]]))


# deleted class Adafruit_BME680_SPI(Adafruit_BME680):
