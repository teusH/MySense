""" intercae to flshing led on PyCom controller
"""
# script origin from: https://github.com/TelenorStartIoT/lorawan-weather-station
from pycom import heartbeat, rgbled
from time import sleep

class LED(object):
  'Wrapper class for controlling the LED'
  
  def heartbeat(state=False):
    heartbeat(state)
      
  def on(color=0x00FF00):
    rgbled(color)

  def off():
    rgbled(0x000000)
      
  def blink(n = 0, d = 0.5, c = 0x0000ff, l = True):
    """
    Blink the LED.
    n = number of times to blink
    d = duration of the led OFF
    c = color
    l = leaves led ON/OFF
    """
    for x in range(n):
      rgbled(0x000000)
      sleep(d)
      rgbled(c)
      sleep(0.1)
    if not l: rgbled(0x000000)
