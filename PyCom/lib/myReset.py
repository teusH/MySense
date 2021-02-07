# Copyright 2019, Teus Hagen MySense RPL-1.5
# Open Source Initiative  https://opensource.org/licenses/RPL-1.5
#
#   Unless explicitly acquired and licensed from Licensor under another
#   license, the contents of this file are subject to the Reciprocal Public
#   License ("RPL") Version 1.5, or subsequent versions as allowed by the RPL,
#   and You may not copy or use this file in either source code or executable
#   form, except in compliance with the terms and conditions of the RPL.
#
#   All software distributed under the RPL is provided strictly on an "AS
#   IS" basis, WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESS OR IMPLIED, AND
#   LICENSOR HEREBY DISCLAIMS ALL SUCH WARRANTIES, INCLUDING WITHOUT
#   LIMITATION, ANY WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
#   PURPOSE, QUIET ENJOYMENT, OR NON-INFRINGEMENT. See the RPL for specific
#   language governing rights and limitations under the RPL.

# script to catch main failures if running a while warn and reset
# else sleep forever and warn every 10 minutes
 
__version__ = "0." + "$Revision: 7.1 $"[11:-2]
__license__ = 'RPL-1.5'

# 
from machine import Timer, reset
from time import sleep_ms, ticks_ms
from pycom import rgbled, heartbeat, nvs_set

class LEDblink:
 def __init__(self,count=-5,alarm=60):
   self.__alarm = Timer.Alarm(self.__myHandler,alarm,periodic=True)
   self.max = count

 def __myHandler(self,alarm):
   ye = 0x008C00
   if self.max > 1: ye = 0xFF
   for i in range(10):
     rgbled(0xFF0000+(ye if i%2 else 0x0)); sleep_ms(300);
     rgbled(0x0); sleep_ms(600)
   self.max += 1
   if self.max == 0: alarm.cancel()

def myEnd(debug=False):
  heartbeat(False); nvs_set('myReset',ticks_ms()/1000)
  if debug or (ticks_ms() > 30*60*1000):
    myLed = LEDblink(alarm=15)
  else: myLed = LEDblink(count=1,alarm=(60*10))
  while True:
    if not myLed.max: break
    if myLed.max < 0: sleep_ms(15*1000)
    else: sleep_ms(60*60*1000)
  if debug: print("system reset"); sleep(1)
  reset()
    
