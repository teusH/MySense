from pycom import heartbeat, rgbled
from time import sleep

class LED(object):
  'Wrapper class for controlling the LED'
  
  def heartbeat(state):
    heartbeat(state)
      
  def on():
    rgbled(0x00FF00)

  def off():
    rgbled(0x000000)
      
  def blink(n = 0, d = 0.5, c = 0x0000ff):
    """
    Blink the LED.
    n = number of times to blink
    d = duration of the light
    c = color
    """
    for x in range(n):
      rgbled(0x000000)
      sleep(d)
      rgbled(c)
      sleep(0.1)
