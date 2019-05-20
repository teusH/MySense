# Copyright 2019, Teus Hagen, GPLV3
# search 2 TTL busses for devices
'''Simple test script for searching on TTL/UART channels for UART devices
'''

__version__ = "0." + "$Revision: 1.1 $"[11:-2]
__license__ = 'GPLV3'

from time import sleep
from machine import UART, Pin
import sys

# pins arrays per TTL channel TTL1 and TTL2 (TTL = usb console)
TTL = [
   { 'name':'TTL3','pins':('P1','P0','P20'), 'baud':(None,None)},
   { 'name':'TTL2','pins':('P4','P3','P19'),  'baud':(9600,115200)},
   { 'name':'TTL1','pins':('P11','P10','P9'),'baud':(9600,115200)},
]
activations = [
      (None,'NEO-6',9600,'gps'),                                   # GPS NEO-6
      (b'\x42\x4D\xE1\x00\x01\x01\x71','PMSx003',9600,'dust'),     # PMS
      (b'\x7E\x00\xD0\x01\x01\x2D\x7E','SPS30',115200,'dust'),     # SPS info
      (b'\x7E\x00\x00\x02\x01\x03\xF9\x7E','SPS30',115200,'dust'), # SPS start
      (b'\xAA\xB4\x06\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF\x06\xAB','SDS011',9600,'dust'), # SDS
      ]

names = []; found = []; serial = None
debug = False
for i in range(len(TTL)):
  ttl = TTL[i]
  if ttl['baud'][0] == None: continue
  if ttl['pins'][2]: # power TTL support
    pin = Pin(ttl['pins'][2], mode=Pin.OUT)
    if pin.value():
       pin.value(0) # toggle to reset
    if not pin.value():
       if debug: print("Powerup TTL (Tx yellow ->dev Rx,Rx white -> dev Tx,Pwr red)=%s" % str(ttl['pins']))
       pin.value(1)
       sleep(2)
  else: print("No TTL power support")
  fnd = None; serial = None
  if not debug:
    print("%s: pins %s connected to " % (ttl['name'],str(ttl['pins'])),end='')
  for baudrate in ttl['baud']:
    if serial:
      if serial.any(): serial.readall()
      serial.deinit(); serial = None; sleep(1)
    if fnd: break
    serial = UART(i,baudrate=baudrate, pins=ttl['pins'][:2], timeout_chars=20)
    if serial.any(): serial.readall()
    if debug: print("Open serial on %s, baudrate %d" %(str(ttl['pins'][:2]),baudrate))
    while True:
      if fnd: break
      for activate in activations + activations[1:]:
        if activate[0]:
          if activate[2] != baudrate: continue
          if activate[1] in names: continue
          if activate[3] in found: continue
          if debug: print("Try to wakeup at baudrate %d %s(%s)" % (activate[2],activate[3],activate[1]))
          serial.write(activate[0])
        if debug: int("Wait", end='')
        for i in range(10):
          sleep(1)
          if serial.any(): break
          if debug: print(".",end='')
          sleep(5)
        if debug: print("")
        if serial.any():
          firmware = ''
          if debug: print("Got %d bytes" % serial.any())
          fnd = ''
          line = serial.readall()
          if debug: print("TTL %s got: %s" % (ttl['name'],str(line)))
          if line.count(b'\x42\x4D') and (not 'PMSx003' in names):
            fnd = ('PMSx003','dust')
            idx = line.find(b'BM')
            if (idx >= 0) and (idx+28 < len(line)):
              firmware = ' ID=%d' % int(line[idx+28])
          elif line.count(b'\xAA') and line.count(b'\xC0') and (not 'SDS011' in names): fnd = ('SDS011','dust')
          elif (line.count(b'~\x00\x00') or line.count(b'\x00\xFF~')) and (not 'SPS30' in names): fnd = ('SPS30','dust')
          elif line.count(b'~\x00\xD0\x00') and (not 'SPS30' in names):
            fnd = ('SPS30','dust'); print("SPS info name") # may show more detail
          elif line.count(b'u-blox') and (not 'gps' in found): fnd = ('NEO-6','gps')
          elif line.count(b'$GPG') and (not 'gps' in found): fnd = ('GPS','gps')
          if fnd:
            names.append(fnd[0]); found.append(fnd[1])
            if debug:
              print("%s: pins %s connected to %s(%s)%s" % (ttl['name'],str(ttl['pins']),fnd[1],fnd[0],firmware))
            else:
              print("%s(%s)%s at baudrate %d" % (fnd[1],fnd[0],firmware,baudrate))
          break
        elif debug: print("Try to activate")

sys.exit()
