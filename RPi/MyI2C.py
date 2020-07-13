#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
# 
# Copyright (C) 2017, Behoud de Parel, Teus Hagen, the Netherlands
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# $Id: MyGAS.py,v 2.3 2017/02/01 12:47:13 teus Exp teus $

# TO DO: write to file or cache

""" Get measurements from AphaSense connected (gas) sensors
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyGAS.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.3 $"[11:-2]

import MyLogger
from time import time

# configurable options
__options__ = ['input','type','pin']

Conf = {
    'input': False,      # no ADC installed
    'type': None,        # type of gas sensors
    'unit': None,        # ugm3/h or ppb/h
    'pin': None,         # GPIO pin of PI
}
# ===============================================================
# read (gas) values via Delta Sigma ADC (AB Electronics)
# ===============================================================
# Clairity reports says: ppb = (OP1-Z1)-(OP2-Z2))/S where:
# OP[1,2] 2 voltage outputs, Z[1,2] 2 zero offsets (manufacturer spec)
# S sensibility factor (manufacturer spec)
# to do: ask for calibration data from a campus test
# pollutants: CO, NO, NO2, O3 NH3?
# add: NH3, light, audio?
def getdata():
    global Conf
    adc_address1 = 0x68
    adc_address2 = 0x69
    adc_channel1 = 0x98
    adc_channel2 = 0xB8
    adc_channel3 = 0xD8
    adc_channel4 = 0xF8
    i2c_bus = 1 #Version 2 of RPi
    # TO DO: add list of types and gas ID's and bind to addresses/channels
    # Based on Delta Sigma Version 1 Architecture (Current is Version 2)
    if (Conf['type'] == None):
        return {}
    try:
        Fields.index('asense_1')
    except ValueError:
        for adc in range(1,8):
            try:
                Fields.index('asense_'+adc)
            except ValueError:
                Fields.append('asense_'+adc)
                Units.append(Conf['unit'])
    with i2c.I2CMaster(i2c_bus) as bus:
        def getadcreading(address, channel):
            bus.transaction(i2c.writing_bytes(address, channel))
            sleep(0.05)
            h, l, r = bus.transaction(i2c.reading(address,3))[0]
            sleep(0.05)
            h, l, r = bus.transaction(i2c.reading(address,3))[0]
            t = (h << 8) | l
            v = t * 0.000154
            if v < 5.5:
                return 1000* v
            else: # must be a floating input
                return 0.00

        #asense_1=getadcreading(adc_address1, adc_channel1)
        #asense_2=getadcreading(adc_address1, adc_channel2)
        #asense_3=getadcreading(adc_address1, adc_channel3)
        #asense_4=getadcreading(adc_address1, adc_channel4)
        #asense_5=getadcreading(adc_address2, adc_channel1)
        #asense_6=getadcreading(adc_address2, adc_channel2)
        #asense_7=getadcreading(adc_address2, adc_channel3)
        #asense_8=getadcreading(adc_address2, adc_channel4)
        # print("Alphasense Data: ",asense_1,",",asense_2,",",asense_3,",",asense_4,",",asense_5,",",asense_6,",",asense_7,",",asense_8)
        # data = {}
        # for adc in range(0,7):
        #     data["asense_"+(adc+1)]=getadcreading(0x68+(adc//4),0x98+(0x20*(adc%4))
        # return data
        return { 
            'time': int(time()),
            "asense_1" : getadcreading(adc_address1, adc_channel1),
            "asense_2" : getadcreading(adc_address1, adc_channel2),
            "asense_3" : getadcreading(adc_address1, adc_channel3),
            "asense_4" : getadcreading(adc_address1, adc_channel4),
            "asense_5" : getadcreading(adc_address2, adc_channel1),
            "asense_6" : getadcreading(adc_address2, adc_channel2),
            "asense_7" : getadcreading(adc_address2, adc_channel3),
            "asense_8" : getadcreading(adc_address2, adc_channel4)
            }

