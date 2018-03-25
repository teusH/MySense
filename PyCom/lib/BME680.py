# from: http://circuitpython.readthedocs.io/projects/bme680/en/latest/_modules/adafruit_bme680.html
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
`adafruit_bme680` - Adafruit BME680 - Temperature, Humidity, Pressure & Gas Sensor
===================================================================================

CircuitPython driver from BME680 air quality sensor

* Author(s): ladyada
* Changes by: teus
"""

from time import time, sleep_ms
import math
from micropython import const
try:
    import struct
except ImportError:
    import ustruct as struct

#    I2C ADDRESS/BITS/SETTINGS
#    -----------------------------------------------------------------------
_BME680_CHIPID = const(0x61)

_BME680_REG_CHIPID = const(0xD0)
_BME680_BME680_COEFF_ADDR1 = const(0x89)
_BME680_BME680_COEFF_ADDR2 = const(0xE1)
_BME680_BME680_RES_WAIT_0 = const(0x5A)

_BME680_REG_SOFTRESET = const(0xE0)
_BME680_REG_CTRL_GAS = const(0x71)
_BME680_REG_CTRL_HUM = const(0x72)
_BME280_REG_STATUS = const(0xF3)
_BME680_REG_CTRL_MEAS = const(0x74)
_BME680_REG_CONFIG = const(0x75)

_BME680_REG_STATUS = const(0x1D)
_BME680_REG_PDATA = const(0x1F)
_BME680_REG_TDATA = const(0x22)
_BME680_REG_HDATA = const(0x25)

_BME680_SAMPLERATES = (0, 1, 2, 4, 8, 16)
_BME680_FILTERSIZES = (0, 1, 3, 7, 15, 31, 63, 127)

_BME680_RUNGAS = const(0x10)

_LOOKUP_TABLE_1 = (2147483647.0, 2147483647.0, 2147483647.0, 2147483647.0, 2147483647.0,
                   2126008810.0, 2147483647.0, 2130303777.0, 2147483647.0, 2147483647.0,
                   2143188679.0, 2136746228.0, 2147483647.0, 2126008810.0, 2147483647.0,
                   2147483647.0)

_LOOKUP_TABLE_2 = (4096000000.0, 2048000000.0, 1024000000.0, 512000000.0, 255744255.0, 127110228.0,
                   64000000.0, 32258064.0, 16016016.0, 8000000.0, 4000000.0, 2000000.0, 1000000.0,
                   500000.0, 250000.0, 125000.0)


def _read24(arr):
    """Parse an unsigned 24-bit value as a floating point and return it."""
    ret = 0.0
    #print([hex(i) for i in arr])
    for b in arr:
        ret *= 256.0
        ret += float(b & 0xFF)
    return ret

# calibrate by length calibration factor (Taylor) array
def _calibrate(cal,value,raw=False):
    if raw: return value
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


class Adafruit_BME680:
    """Driver from BME680 air quality sensor"""
    def __init__(self,raw=False,calibrate=None, debug=False):
        """Check the BME680 was found, read the coefficients and enable the sensor for continuous
           reads"""
        self._write(_BME680_REG_SOFTRESET, [0xB6])
        sleep_ms(400)

        # Check device ID.
        chip_id = self._read_byte(_BME680_REG_CHIPID)
        if _BME680_CHIPID != chip_id:
            raise RuntimeError('Failed to find BME680! Chip ID 0x%x' % id)

        self._read_calibration()

        # set up heater
        self._write(_BME680_BME680_RES_WAIT_0, [0x73, 0x64, 0x65])
        self.sea_level_pressure = 1010.25
        """Pressure in hectoPascals at sea level. Used to calibrate ``altitude``."""
        self.calibrate = { 'temperature': None, 'pressure': None, 'humidity': None, 'altitude': None, 'gas': None, 'gas base': 178644.6}
        if (not raw) and (type(calibrate) is dict):
            for k in calibrate.keys():
                if (not k in self.calibrate.keys()) or (not type(calibrate[k]) is list):
                    continue
                self.calibrate[k] = calibrate[k]
        self._debug = debug
        self._pressure_oversample = 4
        self._temp_oversample = 8
        self._humidity_oversample = 2
        self._filter = 3

        self._adc_pres = None
        self._adc_temp = None
        self._adc_hum = None
        self._adc_gas = None
        self._gas_range = None
        self.hum_base = 45.0 # 80.0 outdoor best, 40.0-50.0  indoor best
        self.hum_weight = 0.25 # calculation of AQ score (25:75, humidity:gas)
        self._t_fine = None
        self._status = 0
        self.gas_base = self.calibrate['gas base']

    @property
    def pressure_oversample(self):
        """The oversampling for pressure sensor"""
        return _BME680_SAMPLERATES[self._pressure_oversample]

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
            self._filter = _BME680_FILTERSIZES[size]
        else:
            raise RuntimeError("Invalid size")

    @property
    def temperature(self):
        """The compensated temperature in degrees celsius."""
        self._perform_reading()
        calc_temp = (((self._t_fine * 5) + 128) / 256)
        return _calibrate(self.calibrate['temperature'],calc_temp / 100)

    @property
    def pressure(self):
        """The barometric pressure in hectoPascals"""
        self._perform_reading()
        var1 = (self._t_fine / 2) - 64000
        var2 = ((var1 / 4) * (var1 / 4)) / 2048
        var2 = (var2 * self._pressure_calibration[5]) / 4
        var2 = var2 + (var1 * self._pressure_calibration[4] * 2)
        var2 = (var2 / 4) + (self._pressure_calibration[3] * 65536)
        var1 = ((var1 / 4) * (var1 / 4)) / 8192
        var1 = (((var1 * self._pressure_calibration[2] * 32) / 8) +
                ((self._pressure_calibration[1] * var1) / 2))
        var1 = var1 / 262144
        var1 = ((32768 + var1) * self._pressure_calibration[0]) / 32768
        calc_pres = 1048576 - self._adc_pres
        calc_pres = (calc_pres - (var2 / 4096)) * 3125
        calc_pres = (calc_pres / var1) * 2
        var1 = (self._pressure_calibration[8] * (((calc_pres / 8) * (calc_pres / 8)) / 8192)) / 4096
        var2 = ((calc_pres / 4) * self._pressure_calibration[7]) / 8192
        var3 = (((calc_pres / 256) ** 3) * self._pressure_calibration[9]) / 131072
        calc_pres += ((var1 + var2 + var3 + (self._pressure_calibration[6] * 128)) / 16)
        return _calibrate(self.calibrate['pressure'],calc_pres/100)

    @property
    def humidity(self):
        """The relative humidity in RH %"""
        self._perform_reading()
        temp_scaled = ((self._t_fine * 5) + 128) / 256
        var1 = ((self._adc_hum - (self._humidity_calibration[0] * 16)) -
                ((temp_scaled * self._humidity_calibration[2]) / 200))
        var2 = (self._humidity_calibration[1] *
                (((temp_scaled * self._humidity_calibration[3]) / 100) +
                 (((temp_scaled * ((temp_scaled * self._humidity_calibration[4]) / 100)) /
                   64) / 100) + 16384)) / 1024
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
        return _calibrate(self.calibrate['humidity'],calc_hum)

    @property
    def altitude(self):
        """The altitude based on current ``pressure`` vs the sea level pressure
           (``sea_level_pressure``) - which you must enter ahead of time)"""
        pressure = self.pressure # in Si units for hPascal
        pressure =  44330 * (1.0 - math.pow(pressure / self.sea_level_pressure, 0.1903))
        return _calibrate(self.calibrate['altitude'],pressure)

    @property
    def gas(self):
        """The gas resistance in ohms"""
        self._perform_reading()
        var1 = ((1340 + (5 * self._sw_err)) * (_LOOKUP_TABLE_1[self._gas_range])) / 65536
        var2 = ((self._adc_gas * 32768) - 16777216) + var1
        var3 = (_LOOKUP_TABLE_2[self._gas_range] * var1) / 512
        calc_gas_res = (var3 + (var2 / 2)) / var2
        return int(_calibrate(self.calibrate['gas'],calc_gas_res))

    # after https://github.com/pimoroni/bme680/examples
    # burn in and calculate baseline
    def _gasBase(self):
        self.gas_base = None
        BURN_TIME = const(300)  # 5 minutes
        if self._debug:
            print("Gas resistance burn-in max: %d minutes" % (BURN_TIME/60))
        strt_time = time(); cur_time = time()
        data = []; prev_gas = 0; stable = False; cnt = 0
        while cur_time - strt_time < BURN_TIME:
            cur_time = time()
            gas = self.gas
            if (not stable ) and abs(gas - prev_gas) < 1000:
                if cnt > 3:
                    stable = True
                else:
                    cnt += 1
            elif not stable: cnt = 0
            if ((self._status & 0x30) == 0x30) and stable:
                if len(data) < 50:
                    data.append(gas)
                else:
                    data.pop(); data.insert(0,gas)
                if self._debug: print("time: %dm%ds, gas: %d Ohms" % (int(cur_time-strt_time)/60,int(cur_time-strt_time)%60,gas))
                if len(data) >= 50: break
            else:
                if self._debug: print("time: %dm%ds: heating up %d" % (int(cur_time-strt_time)/60,int(cur_time-strt_time)%60,gas))
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

        # set filter
        self._write(_BME680_REG_CONFIG, [self._filter << 2])
        # turn on temp oversample & pressure oversample
        self._write(_BME680_REG_CTRL_MEAS,
                    [(self._temp_oversample << 5)|(self._pressure_oversample << 2)])
        # turn on humidity oversample
        self._write(_BME680_REG_CTRL_HUM, [self._humidity_oversample])
        # gas measurements enabled
        self._write(_BME680_REG_CTRL_GAS, [_BME680_RUNGAS])

        ctrl = self._read(_BME680_REG_CTRL_MEAS, 1)[0]
        ctrl = (ctrl & 0xFC) | 0x01  # enable single shot!
        self._write(_BME680_REG_CTRL_MEAS, [ctrl])
        sleep_ms(400)
        data = self._read(_BME680_REG_STATUS, 15)
        self._status = data[0] & 0x80
        #gas_idx = data[0] & 0x0F
        #meas_idx = data[1]
        #print("status 0x%x gas_idx %d meas_idx %d" % (self._status, gas_idx, meas_idx))

        #print([hex(i) for i in data])
        self._adc_pres = _read24(data[2:5]) / 16
        self._adc_temp = _read24(data[5:8]) / 16
        self._adc_hum = struct.unpack('>H', bytes(data[8:10]))[0]
        self._adc_gas = int(struct.unpack('>H', bytes(data[13:15]))[0] / 64)
        self._gas_range = data[14] & 0x0F
        #print(self._adc_hum)
        #print(self._adc_gas)
        self._status |= data[14] & 0x30     # VALID + STABILITY mask

        var1 = (self._adc_temp / 8) - (self._temp_calibration[0] * 2)
        var2 = (var1 * self._temp_calibration[1]) / 2048
        var3 = ((var1 / 2) * (var1 / 2)) / 4096
        var3 = (var3 * self._temp_calibration[2] * 16) / 16384
        self._t_fine = int(var2 + var3)

    def _read_calibration(self):
        """Read & save the calibration coefficients"""
        coeff = self._read(_BME680_BME680_COEFF_ADDR1, 25)
        coeff += self._read(_BME680_BME680_COEFF_ADDR2, 16)

        coeff = list(struct.unpack('<hbBHhbBhhbbHhhBBBHbbbBbHhbb', bytes(coeff[1:])))
        #print("\n\n",coeff)
        coeff = [float(i) for i in coeff]
        self._temp_calibration = [coeff[x] for x in [23, 0, 1]]
        self._pressure_calibration = [coeff[x] for x in [3, 4, 5, 7, 8, 10, 9, 12, 13, 14]]
        self._humidity_calibration = [coeff[x] for x in [17, 16, 18, 19, 20, 21, 22]]
        self._gas_calibration = [coeff[x] for x in [25, 24, 26]]

        # flip around H1 & H2
        self._humidity_calibration[1] *= 16
        self._humidity_calibration[1] += self._humidity_calibration[0] % 16
        self._humidity_calibration[0] /= 16

        self._heat_range = (self._read(0x02, 1)[0] & 0x30) / 16
        self._heat_val = self._read(0x00, 1)[0]
        self._sw_err = (self._read(0x04, 1)[0] & 0xF0) / 16

    def _read_byte(self, register):
        """Read a byte register value and return it"""
        return self._read(register, 1)[0]

    def _read(self, register, length):
        raise NotImplementedError()

    def _write(self, register, values):
        raise NotImplementedError()


class Adafruit_BME680_I2C(Adafruit_BME680):
    """Driver for I2C connected BME680."""
    def __init__(self, i2c, address=0x77, debug=False, raw=False, calibrate=None):
        """Initialize the I2C device at the 'address' given"""
        #import adafruit_bus_device.i2c_device as i2c_device
        from i2c_device import I2CDevice
        #self._i2c = i2c_device.I2CDevice(i2c, address)
        self._i2c = I2CDevice(i2c, address)
        #from Device import *
        #self._i2c = Device(address, i2c)
        self._debug = debug
        super().__init__(raw=raw,calibrate=calibrate, debug=debug)

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
        with self._i2c as i2c:
            values = [(v & 0xFF) for v in [register]+values]
            i2c.write(bytes(values))
            if self._debug:
                print("\t$%02X <= %s" % (values[0], [hex(i) for i in values[1:]]))
