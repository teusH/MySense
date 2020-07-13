# Copyright 2019, Teus Hagen MySense GPLV3
# script to catch main failures if running a while warn and reset
# else sleep forever and warn every 10 minutes

__version__ = "0." + "$Revision: 1.2 $"[11:-2]
__license__ = 'GPLV3'

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
    
