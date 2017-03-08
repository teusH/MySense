# Adafruit BME280 temp/humidity/pressure I2C sensor
## STATUS
alpha test 2017/02/26

## DESCRIPTION
Adafruit BME280 rel. humidity (rh,%), temperature (temp,C) and pressure (hpa, hPa) sensor.
The chip is very precise (Bosch is manufacturer) and can give altitude if pressure at sea level is known (not used). It interfaces to the I2C-bus of eg the Pi.

* Kiwi Electronis € 22.50 (or Grove ready BME280 € 19.50)
* If you use GrovePi+ shield you need to add a Grove proto shield € 2.50.

## References
* https://www.adafruit.com/products/2652
* https://github.com/adafruit/Adafruit_Python_GPIO
* git clone https://github.com/adafruit/Adafruit_Python_BME280.git
* http://www.deviceplus.com/how-tos/raspberrypi-guide/reading-temperature-humidity-and-pressure-with-ae-bme280-and-raspberry-pi/

## Hardware installation
### Module libraries
From the Adafruit_Python_BME280.git you need to install the Adafruit_BME280.py as library in the (cloned) directory Adafruit_Python_BME280.

Ready the Pi for i2c-bus:
```bash
    sudo apt-get install i2c-tools
    sudo apt-get python-smbus
    git clone https://github.com/adafruit/Adafruit_Python_BME280.git
    cp ./Adafruit_Python_BME280/Adafruit_BME280.py .
    git clone https://github.com/adafruit/Adafruit_Python_GPIO.git
    cd Adafruit_Python_GPIO
    sudo python setup.py install
```
For MySense you need only to install the Adafruit python GPIO or use `INSTALL.sh BME280` script.

### HW Configuration
When selecting the I2C address, it defaults to [0x76] if the pin 5 on the circuit board (SDO) is connected to GND and [0x77] if connected to VDD (default).

GrovePi defines the pins to use if you use a GrovePi+ shield (€ 35.-).

signal   |Pi pin|GrovePi pin|BME280
---------|------|-----------|-------
V 5      |pin 2 |pin 2 V    |Vin pin
Data SDA |pin 3 |pin 3 S1   |SDI pin
Clock SCL|pin 5 |pin 4 S0   |SCK pin
GRND     |pin 6 |pin 1 G    |Gnd pin

Enable i2c in raspi-config (Interfacing Options) and run `sudo i2cdetect -y 1`
You should see eg '77' is new address in row '70' (the address 0x77)

### HW Test
```bash
    python ./Adafruit_BME280_Example.py
```
## MySense and BME280 configuration
Enable input for the section [bme280] in the configuration/init file MySense.conf.
Default the i2c address is 0x77. Set i2c in the section to another hex value if needed.
### TEST
Test with the command `python My_BME280.py` to see if it works within MySense. You can comment the Conf['sync'] (if true do not run in multi thread mode) and Conf['debug'] in the script if needed so. To kill the process use `<cntrl>Z and kill %1` in stead of console interrupt (`<cntrl>c`).

### TUNING
With Conf['interval'] one can fiddle with the frequency of sensor readings and as so with the sliding average calculation of the window (Conf['bufsize']).
