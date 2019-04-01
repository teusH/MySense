# test kit with copy(<cntrl>shiftC)/paste(<cntrl>v) via REPL
# test suite helps to detect hw configuration and software problems
# one by one
# Copyright 2019, Teus Hagen, GPLV4
# xyz_test is operational test for xyz
# other parts are functional tests for MySense.py wrapper

# global settings
power = False       # use power management
doSleep = False     # use deepsleep function

from time import sleep

########## check I2C part
import oled_test
import meteo_test

# I2C devices
import whichI2C
I2Cobj = whichI2C.identifyI2C(identify=True,debug=True)

# check basic display init and fie functions
Display = { 'use': None, 'enabled': False, 'fd': None}
I2Cobj.DISPLAY
Display = I2Cobj.i2cDisplay
Display
import SSD1306 as DISPLAY
Display['fd'] = DISPLAY.SSD1306_I2C(128,64,Display['i2c'], addr=Display['address'])
print('Oled %s:' % Display['name'] + ' SDA~>%s, SCL~>%s, Pwr~>%s' % Display['pins'][:3], ' is %d' % I2Cobj.PwrI2C(Display['pins']))

Display['fd'].fill(1); Display['fd'].show()
sleep(1)
Display['fd'].fill(0); Display['fd'].show()
import sys
sys.exit() # reset

# I2C devices
import whichI2C
I2Cobj = whichI2C.identifyI2C(identify=True,debug=True)

# check basic meteo init and operational functions
Meteo   = { 'use': None, 'enabled': False, 'fd': None}
I2Cobj.METEO
Meteo = I2Cobj.i2cMeteo
Meteo
import BME_I2C as BME
Meteo['fd'] = BME.BME_I2C(Meteo['i2c'], address=Meteo['address'], debug=True, calibrate={})
# expect bus errors
Meteo['fd'].AQI
Meteo['fd'].temperature
import sys
sys.exit() # reset

########### check UART part
import dust_test
import gps_test

# UART devices
import whichUART
UARTobj = whichUART.identifyUART(identify=True,debug=True)
uarts = [None,'gps','dust']

# check dust device functions for MySense
Dust = { 'use': None, 'enabled': False, 'fd': None}
Dust = UARTobj.devs['dust']
Dust
from PMSx003 import PMSx003 as senseDust
print('%s UART:' % Dust['name'] + ' SDA~>%s, SCL~>%s, Pwr~>%s' % Dust['pins'][:3], ' is ', UARTobj.PwrTTL(Dust['pins']))
sample_time = 60    # 60 seconds sampling for dust
# Dust['uart'] = UARTobj.openUART('dust') this did not work
Dust['uart'] = uarts.index('dust')
Dust['fd'] = senseDust(port=Dust['uart'], debug=True, sample=sample_time, interval=0, pins=Dust['pins'][:2], calibrate={}, explicit=False)
UARTobj.PwrTTL(Dust['pins'],on=True)
Dust['fd'].Normal()
Dust['fd'].Standby()
Dust['fd'].getData(debug=True)
UARTobj.PwrTTL(Dust['pins'],on=False)
import sys
sys.exit() # reset

# test with MySense
# depends on initDisplay(debug=True)
import MySense
MySense.initDust(debug=True)
# ignore I2C bus errors
MySense.DoDust(debug=True)

# UART devices
import whichUART
UARTobj = whichUART.identifyUART(identify=True,debug=True)
UARTobj = whichUART.identifyUART(identify=True,debug=True)
uarts = [None,'gps','dust']

# check GPS functions for MySense
Gps     = { 'use': None, 'enabled': False, 'fd': None}
Gps = UARTobj.devs['gps']
Gps
import GPS_dexter as GPS
print('%s UART:' % Gps['name'] + ' SDA~>%s, SCL~>%s, Pwr~>%s' % Gps['pins'][:3], ' is ', UARTobj.PwrTTL(Gps['pins']))
Gps['uart'] = uarts.index('gps')
Gps['fd'] = GPS.GROVEGPS(port=Gps['uart'],baud=9600,debug=True,pins=Gps['pins'][:2])
UARTobj.PwrTTL(Gps['pins'],on=True)
Gps['fd'].date
Gps['fd'].UpdateRTC()
round(float(Gps['fd'].longitude),5)
round(float(Gps['fd'].latitude),5)
round(float(Gps['fd'].altitude),1)
UARTobj.PwrTTL(Gps['pins'],on=False)

import sys
sys.exit() # reset

# test with MySense
# depends on initDisplay(debug=True)
import MySense
MySense.initGPS(debug=True)

######## LoRa tests
import lora_test
Network = { 'use': None, 'enabled': False, 'fd': None}
import MySense
MySense.initNetwork(debug=True)
# depends on initNetwork(), initGps() and 'name' in Meteo and Dust dict
# Meteo = {'name':'','enabled': True} Dust = {'name':'None','enabled': True}
# Gps = {'enabled': True}
MySense.SendInfo(3)

Accu    = { 'use': None, 'enabled': False, 'fd': None}

