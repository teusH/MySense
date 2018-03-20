# for test purposes only under python

import serial
from time import time, sleep

def const(val):
  return val

def UART(port, baudrate=9600):
  return serial.Serial("/dev/ttyUSB" + str(port), baudrate)

def ticks_ms():
  return int(round(time() * 1000))

def sleep_ms(msecs):
  return sleep(msecs/1000.0)
