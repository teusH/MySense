# Copyright 2019, Teus Hagen, GPLV3
# search 2 TTL busses for devices
'''Simple test script for searching on TTL/UART channels for UART devices
'''

__version__ = "0." + "$Revision: 1.2 $"[11:-2]
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
      # (b'\x7E\x00\xD0\x01\x01\x2D\x7E','SPS30',115200,'dust'),     # SPS info, name
      # (b'\x7E\x00\xD0\x01\x02\x2C\x7E','SPS30',115200,'dust'),     # SPS info, code
      (b'\x7E\x00\xD0\x01\x03\x2B\x7E','SPS30',115200,'dust'),     # SPS info, S/N
      (b'\x7E\x00\x00\x02\x01\x03\xF9\x7E','SPS30',115200,'dust'), # SPS start
      (b'\xAA\xB4\x06\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF\x06\xAB','SDS011',9600,'dust'), # SDS
      ]

names = []; found = []; serial = None
verbose = False
for i in range(len(TTL)):
  ttl = TTL[i]
  if ttl['baud'][0] == None: continue
  if ttl['pins'][2]: # power TTL support
    pin = Pin(ttl['pins'][2], mode=Pin.OUT)
    if pin.value():
       pin.value(0) # toggle to reset
    if not pin.value():
       if verbose: print("Powerup TTL (Tx yellow ->dev Rx,Rx white -> dev Tx,Pwr red)=%s" % str(ttl['pins']))
       pin.value(1)
       sleep(2)
  else: print("No TTL power support")
  fnd = None; serial = None
  if not verbose:
    print("%s: pins %s connected to " % (ttl['name'],str(ttl['pins'])),end='')
  for baudrate in ttl['baud']+ttl['baud']:
    if serial:
      if serial.any(): serial.readall()
      serial.deinit(); del serial; serial = None; sleep(1)
    if fnd: break
    if verbose: print("Open serial %d on %s, baudrate %d" % (i,str(ttl['pins'][:2]),baudrate))
    serial = UART(i,baudrate=baudrate, pins=ttl['pins'][:2], timeout_chars=20)
    if serial.any(): serial.readall()
    if fnd: break
    for activate in activations:
      if activate[0]:
        if activate[2] != baudrate: continue
        if activate[1] in names: continue
        if activate[3] in found: continue
        if verbose: print("Try at baudrate %d, activate %s(%s)" % (activate[2],activate[3],activate[1]))
        serial.write(activate[0])
      elif baudrate == 115200: continue
      if verbose: print("Wait", end='')
      for j in range(5):
        sleep(1)
        if serial.any(): break
        if verbose: print(".",end='')
        sleep(5)
      if verbose: print("")
      if serial.any():
        firmware = ''
        if verbose: print("Got %d bytes" % serial.any())
        fnd = ''
        line = serial.readall()
        if verbose: print("TTL %s got: %s" % (ttl['name'],str(line)))
        if line.count(b'\x42\x4D') and (not 'PMSx003' in names):
          fnd = ('PMSx003','dust')
          idx = line.find(b'BM')
          if (idx >= 0) and (idx+28 < len(line)):
            firmware = ' ID=%d' % int(line[idx+28])
        elif line.count(b'\xAA') and line.count(b'\xC0') and (not 'SDS011' in names): fnd = ('SDS011','dust')
        elif (line.count(b'~\x00\x00') or line.count(b'\x00\xFF~')) and (not 'SPS30' in names): fnd = ('SPS30','dust')
        elif line.count(b'~\x00\xD0\x00') and (not 'SPS30' in names):
          idx = line.find(b'~\x00\xD0\x00')
          value = ''
          if idx >= 0:
            if line[idx+5]: value = line[idx+5:-3].decode()
          if activate[0][4] == 0x01:
            fnd = ('SPS30','dust')
            info = 'name' 
          elif activate[0][4] == 0x02:
            fnd = ('SPS30','dust')
            info = 'code'
          elif activate[0][4] == 0x03:
            fnd = ('SPS30','dust')
            info = 'S/N'
          else: info = 'info'
          print("SPS info %s: '%s'" % (info,value)) # may show more detail
        elif line.count(b'u-blox') and (not 'gps' in found): fnd = ('NEO-6','gps')
        elif line.count(b'$GPG') and (not 'gps' in found): fnd = ('GPS','gps')
        if fnd:
          names.append(fnd[0]); found.append(fnd[1])
          if verbose:
            print("%s: pins %s connected to %s(%s)%s" % (ttl['name'],str(ttl['pins']),fnd[1],fnd[0],firmware))
          else:
            print("%s(%s)%s at baudrate %d" % (fnd[1],fnd[0],firmware,baudrate))
        break

sys.exit()
