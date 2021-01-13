# The MIT License (MIT)
#
# Copyright (c) 2017 Jerry Needell
# Copyright (c) 2019 Llewelyn Trahaearn
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
"""
`adafruit_sht31d` from github Adafruit 20201220
====================================================

This is a CircuitPython driver for the SHT31-D temperature and humidity sensor.

* Author(s): Jerry Needell, Llewelyn Trahaearn

Implementation Notes
--------------------

**Hardware:**

* Adafruit `Sensiron SHT31-D Temperature & Humidity Sensor Breakout
  <https://www.adafruit.com/product/2857>`_ (Product ID: 2857)

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the ESP8622 and M0-based boards:
  https://github.com/adafruit/circuitpython/releases
* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice

# MySense small changes for interfacing added by teus 2020-12-24
"""

# imports
try:
    import struct
except ImportError:
    import ustruct as struct

import time

from micropython import const
# from adafruit_bus_device.i2c_device import I2CDevice
from i2c_device import I2CDevice

__version__ = "0." + "$Revision: 6.2 $"[11:-2]
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_SHT31D.git" #


_SHT31_DEFAULT_ADDRESS = const(0x44)
_SHT31_SECONDARY_ADDRESS = const(0x45)

_SHT31_ADDRESSES = (_SHT31_DEFAULT_ADDRESS, _SHT31_SECONDARY_ADDRESS)

_SHT31_READSERIALNBR = const(0x3780)
_SHT31_READSTATUS = const(0xF32D)
_SHT31_CLEARSTATUS = const(0x3041)
_SHT31_HEATER_ENABLE = const(0x306D)
_SHT31_HEATER_DISABLE = const(0x3066)
_SHT31_SOFTRESET = const(0x30A2)
_SHT31_NOSLEEP = const(0x303E)
_SHT31_PERIODIC_FETCH = const(0xE000)
_SHT31_PERIODIC_BREAK = const(0x3093)

MODE_SINGLE = "Single"
MODE_PERIODIC = "Periodic"

_SHT31_MODES = (MODE_SINGLE, MODE_PERIODIC)

REP_HIGH = "High"
REP_MED = "Medium"
REP_LOW = "Low"

_SHT31_REP = (REP_HIGH, REP_MED, REP_LOW)

FREQUENCY_0_5 = 0.5
FREQUENCY_1 = 1
FREQUENCY_2 = 2
FREQUENCY_4 = 4
FREQUENCY_10 = 10

_SHT31_FREQUENCIES = (
    FREQUENCY_0_5,
    FREQUENCY_1,
    FREQUENCY_2,
    FREQUENCY_4,
    FREQUENCY_10,
)

_SINGLE_COMMANDS = (
    (REP_LOW, const(False), const(0x2416)),
    (REP_MED, const(False), const(0x240B)),
    (REP_HIGH, const(False), const(0x2400)),
    (REP_LOW, const(True), const(0x2C10)),
    (REP_MED, const(True), const(0x2C0D)),
    (REP_HIGH, const(True), const(0x2C06)),
)

_PERIODIC_COMMANDS = (
    (True, None, const(0x2B32)),
    (REP_LOW, FREQUENCY_0_5, const(0x202F)),
    (REP_MED, FREQUENCY_0_5, const(0x2024)),
    (REP_HIGH, FREQUENCY_0_5, const(0x2032)),
    (REP_LOW, FREQUENCY_1, const(0x212D)),
    (REP_MED, FREQUENCY_1, const(0x2126)),
    (REP_HIGH, FREQUENCY_1, const(0x2130)),
    (REP_LOW, FREQUENCY_2, const(0x222B)),
    (REP_MED, FREQUENCY_2, const(0x2220)),
    (REP_HIGH, FREQUENCY_2, const(0x2236)),
    (REP_LOW, FREQUENCY_4, const(0x2329)),
    (REP_MED, FREQUENCY_4, const(0x2322)),
    (REP_HIGH, FREQUENCY_4, const(0x2334)),
    (REP_LOW, FREQUENCY_10, const(0x272A)),
    (REP_MED, FREQUENCY_10, const(0x2721)),
    (REP_HIGH, FREQUENCY_10, const(0x2737)),
)

_DELAY = ((REP_LOW, 0.0045), (REP_MED, 0.0065), (REP_HIGH, 0.0155))


def _crc(data):
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc <<= 1
                crc ^= 0x131
            else:
                crc <<= 1
    return crc


def _unpack(data):
    length = len(data)
    crc = [None] * (length // 3)
    word = [None] * (length // 3)
    for i in range(length // 6):
        word[i * 2], crc[i * 2], word[(i * 2) + 1], crc[(i * 2) + 1] = struct.unpack(
            ">HBHB", data[i * 6 : (i * 6) + 6]
        )
        if crc[i * 2] == _crc(data[i * 6 : (i * 6) + 2]):
            length = (i + 1) * 6
    for i in range(length // 3):
        if crc[i] != _crc(data[i * 3 : (i * 3) + 2]):
            raise RuntimeError("CRC mismatch")
    return word[: length // 3]


#class SHT31D:
class MyI2C:
    """
    A driver for the SHT31-D temperature and humidity sensor.

    :param i2c_bus: The `busio.I2C` object to use. This is the only required parameter.
    :param int address: (optional) The I2C address of the device.
    """

    # changed def __init__(self, i2c_bus, address=_SHT31_DEFAULT_ADDRESS):
    def __init__(self, i2c, address=_SHT31_DEFAULT_ADDRESS, probe=False, lock=None, debug=False, calibrate=None, raw=None):
        if address not in _SHT31_ADDRESSES:
            raise ValueError("Invalid address: 0x%x" % (address))
        self.i2c_device = I2CDevice(i2c, address, lock=lock) #
        self.calibrate = { 'temperature': None, 'humidity': None}
        # added calibration
        self.raw = raw
        self.debug = debug
        if (not raw) and (type(calibrate) is dict):
          for k in calibrate.keys():
            if (not k in self.calibrate.keys()) or (not type(calibrate[k]) is list):
              continue
            self.calibrate[k] = calibrate[k]
        self._mode = MODE_SINGLE
        self._repeatability = REP_HIGH
        self._frequency = FREQUENCY_4
        self._clock_stretching = False
        self._art = False
        self._last_read = 0
        self._cached_temperature = None
        self._cached_humidity = None
        self._reset()

    # added: calibrate by length calibration factor (Taylor) array
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

    def _command(self, command):
        with self.i2c_device as i2c:
            i2c.write(struct.pack(">H", command))

    def _reset(self):
        """
        Soft reset the device
        The reset command is preceded by a break command as the
        device will not respond to a soft reset when in 'Periodic' mode.
        """
        self._command(_SHT31_PERIODIC_BREAK)
        time.sleep(0.001)
        self._command(_SHT31_SOFTRESET)
        time.sleep(0.0015)

    def _periodic(self):
        for command in _PERIODIC_COMMANDS:
            if self.art == command[0] or (
                self.repeatability == command[0] and self.frequency == command[1]
            ):
                self._command(command[2])
                time.sleep(0.001)
                self._last_read = 0

    def _data(self):
        if self.mode == MODE_PERIODIC:
            data = bytearray(48)
            data[0] = 0xFF
            self._command(_SHT31_PERIODIC_FETCH)
            time.sleep(0.001)
        elif self.mode == MODE_SINGLE:
            data = bytearray(6)
            data[0] = 0xFF
            for command in _SINGLE_COMMANDS:
                if (
                    self.repeatability == command[0]
                    and self.clock_stretching == command[1]
                ):
                    self._command(command[2])
            if not self.clock_stretching:
                for delay in _DELAY:
                    if self.repeatability == delay[0]:
                        time.sleep(delay[1])
            else:
                time.sleep(0.001)
        with self.i2c_device as i2c:
            i2c.readinto(data)
        word = _unpack(data)
        length = len(word)
        temperature = [None] * (length // 2)
        humidity = [None] * (length // 2)
        for i in range(length // 2):
            temperature[i] = -45 + (175 * (word[i * 2] / 65535))
            humidity[i] = 100 * (word[(i * 2) + 1] / 65535)
        if (len(temperature) == 1) and (len(humidity) == 1):
            return temperature[0], humidity[0]
        return temperature, humidity

    def _read(self):
        if (
            self.mode == MODE_PERIODIC
            and time.time() > self._last_read + 1 / self.frequency
        ):
            self._cached_temperature, self._cached_humidity = self._data()
            self._last_read = time.time()
        elif self.mode == MODE_SINGLE:
            self._cached_temperature, self._cached_humidity = self._data()
        return self._cached_temperature, self._cached_humidity

    @property
    def mode(self):
        """
        Operation mode
        Allowed values are the constants MODE_*
        Return the device to 'Single' mode to stop periodic data acquisition and allow it to sleep.
        """
        return self._mode

    @mode.setter
    def mode(self, value):
        if not value in _SHT31_MODES:
            raise ValueError("Mode '%s' not supported" % (value))
        if self._mode == MODE_PERIODIC and value != MODE_PERIODIC:
            self._command(_SHT31_PERIODIC_BREAK)
            time.sleep(0.001)
        if value == MODE_PERIODIC and self._mode != MODE_PERIODIC:
            self._periodic()
        self._mode = value

    @property
    def repeatability(self):
        """
        Repeatability
        Allowed values are the constants REP_*
        """
        return self._repeatability

    @repeatability.setter
    def repeatability(self, value):
        if not value in _SHT31_REP:
            raise ValueError("Repeatability '%s' not supported" % (value))
        if self.mode == MODE_PERIODIC and not self._repeatability == value:
            self._repeatability = value
            self._periodic()
        else:
            self._repeatability = value

    @property
    def clock_stretching(self):
        """
        Control clock stretching.
        This feature only affects 'Single' mode.
        """
        return self._clock_stretching

    @clock_stretching.setter
    def clock_stretching(self, value):
        self._clock_stretching = bool(value)

    @property
    def art(self):
        """
        Control accelerated response time
        This feature only affects 'Periodic' mode.
        """
        return self._art

    @art.setter
    def art(self, value):
        if value:
            self.frequency = FREQUENCY_4
        if self.mode == MODE_PERIODIC and not self._art == value:
            self._art = bool(value)
            self._periodic()
        else:
            self._art = bool(value)

    @property
    def frequency(self):
        """
        Periodic data acquisition frequency
        Allowed values are the constants FREQUENCY_*
        Frequency can not be modified when ART is enabled
        """
        return self._frequency

    @frequency.setter
    def frequency(self, value):
        if self.art:
            raise RuntimeError("Frequency locked to '4 Hz' when ART enabled")
        if not value in _SHT31_FREQUENCIES:
            raise ValueError(
                "Data acquisition frequency '%s Hz' not supported" % (value)
            )
        if self.mode == MODE_PERIODIC and not self._frequency == value:
            self._frequency = value
            self._periodic()
        else:
            self._frequency = value

    @property
    #def temperature(self):
    def temperature(self, raw=False):
        """
        The measured temperature in degrees celsius.
        'Single' mode reads and returns the current temperature as a float.
        'Periodic' mode returns the most recent readings available from the sensor's cache
        in a FILO list of eight floats. This list is backfilled with with the
        sensor's maximum output of 130.0 when the sensor is read before the
        cache is full.
        """
        temperature, _ = self._read()
        return self._calibrate(self.calibrate['temperature'],temperature,raw=raw)

    @property
    #def relative_humidity(self):
    def humidity(self, raw=False):
        """
        The measured relative humidity in percent.
        'Single' mode reads and returns the current humidity as a float.
        'Periodic' mode returns the most recent readings available from the sensor's cache
        in a FILO list of eight floats. This list is backfilled with with the
        sensor's maximum output of 100.01831417975366 when the sensor is read
        before the cache is full.
        """
        _, humidity = self._read()
        return self._calibrate(self.calibrate['humidity'],humidity,raw=raw)

    @property
    def pressure(self):
        """ not available """
        return None

    @property
    def heater(self):
        """Control device's internal heater."""
        return (self.status & 0x2000) != 0

    @heater.setter
    def heater(self, value=False):
        if value:
            self._command(_SHT31_HEATER_ENABLE)
            time.sleep(0.001)
        else:
            self._command(_SHT31_HEATER_DISABLE)
            time.sleep(0.001)

    @property
    def status(self):
        """Device status."""
        data = bytearray(2)
        self._command(_SHT31_READSTATUS)
        time.sleep(0.001)
        with self.i2c_device as i2c:
            i2c.readinto(data)
        status = data[0] << 8 | data[1]
        return status

    @property
    def serial_number(self):
        """Device serial number."""
        data = bytearray(6)
        data[0] = 0xFF
        self._command(_SHT31_READSERIALNBR)
        time.sleep(0.001)
        with self.i2c_device as i2c:
            i2c.readinto(data)
        word = _unpack(data)
        return (word[0] << 16) | word[1]
