""" intercae to flshing led on PyCom controller
"""
# script origin from: https://github.com/TelenorStartIoT/lorawan-weather-station

class LED:
  'Wrapper class for controlling the LED'
  from pycom import heartbeat, rgbled
  from time import sleep
  def __init__(self,active=True):
    self.Active  =  active
  
  def heartbeat(self, state=False):
    heartbeat(state)
      
  def color(self, color=0x00FF00):
    if self.Active: rgbled(color)

  @property
  def off(self):
    rgbled(0x000000)
    self.Active = False
      
  @property
  def on(self):
    self.Active = True

  def blink(self,n = 0, d = 0.5, c = 0x0000ff, l = True, once=False):
    """
    Blink the LED.
    n = number of times to blink
    d = duration of the led OFF
    c = color
    l = leaves led ON/OFF
    """
    try:
      for x in range(n):
        if self.Active: rgbled(0x000000)
        sleep(d)
        if self.Active: rgbled(c)
        sleep(0.1)
      if not l: rgbled(0x000000)
    except OSError:
      heartbeat(False)
      if not once: self.blink,n,d,c,l,True)
