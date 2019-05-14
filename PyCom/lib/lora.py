""" LoRaWan module interface
"""

# script from https://github.com/TelenorStartIoT/lorawan-weather-station
# $Id: lora.py,v 5.7 2019/05/14 15:23:35 teus Exp teus $

import socket
from ubinascii import unhexlify
from network import LoRa
from time import sleep_ms

class LORA(object):
  'Wrapper class for LoRa'
  def __init__(self):
    # LoRa and socket instances
    # Initialize LoRa in LORAWAN mode
    self.lora = LoRa(mode = LoRa.LORAWAN, region=LoRa.EU868)
    self.callback = None
    self.sockets = []
    self.LED = None
    self.debug = False

  def connect(self, method, ports=1, callback=None, myLED=None, debug=False):
    """
    Connect device to LoRa.
    Set the socket and lora instances.
    myLED is led object, on resume use lora nvram
    """
    self.callback = callback # call back routine on LoRa reply callback(port,response)
    self.debug = debug
    self.LED = myLED
    if myLED : myLED.heartbeat(False)
    self.restore; sleep_ms(500)
    if self.lora.has_joined():
      self.getPorts(ports)
      return True
    if self.debug: print("No previous LoRa join. Try to join.")
    if (not type(method) is dict): raise ValueError("No activation method defined.")
    if not method:
      try:
        from Config import dev_eui, app_eui, app_key
        method['OTAA'] = (dev_eui, app_eui, app_key)
      except:
        try:
          from Config import dev_addr, nwk_swkey, app_swkey
          method['ABP'] = (nwk_swkey, nwk_swkey, app_swkey)
        except: raise VCalueError("No LoRa keys defined")
      if self.debug: print("LoRa keys load from Config")
    count = 0
    if self.debug: print("Try to join LoRa/%s" % str(method.keys()))
    if 'OTAA' in method.keys():
      # Join a network using OTAA (Over the Air Activation) next code looks strange
      dev_eui = method['OTAA'][0]; dev_eui = unhexlify(dev_eui)
      app_eui = method['OTAA'][1]; app_eui = unhexlify(app_eui)
      app_key = method['OTAA'][2]; app_key = unhexlify(app_key)
      self.lora.join(activation = LoRa.OTAA, auth = (dev_eui, app_eui, app_key), timeout = 0)
      # Wait until the module has joined the network
      while not self.lora.has_joined():
        if myLED: myLED.blink(1, 2.5, 0xff0000)
        if count > 20: break  # stop this?
        print("Wait for OTAA join: " ,  count)
        count += 1
      if self.lora.has_joined():
        count = 1
        print("LoRa OTAA join.")
      else: count = 0

    if not count:
      if not 'ABP' in method.keys():
        print("No ABP TTN keys defined.")
        return False
      import struct
      # next code is strange. ABP method is not yet operational
      dev_addr = method['ABP'][0]; dev_addr = unhexlify(dev_addr)
      dev_addr = struct.unpack('>l', dev_addr)[0]
      nwk_swkey = method['ABP'][1]; nwk_swkey = unhexlify(nwk_swkey)
      app_swkey = method['ABP'][2]; app_swkey = unhexlify(app_swkey)
      print("LoRa ABP join.")
      self.lora.join(activation = LoRa.ABP, auth = (dev_addr, nwk_swkey, app_swkey))

    self.getPorts(ports)
    if myLED: myLED.blink(2, 0.1, 0x009900)
    self.dump
    return True


  def getPorts(self,ports):
    # Create a LoRa sockets
    self.sockets = []
    self.sockets.append(socket.socket(socket.AF_LORA, socket.SOCK_RAW))

    # Set the LoRaWAN data rate
    self.sockets[0].setsockopt(socket.SOL_LORA, socket.SO_DR, 2)

    # Make the socket non-blocking
    self.sockets[0].setblocking(False)

    # Create a raw LoRa socket
    # default port 2
    self.sockets.append(None)
    for nr in range(ports):
      self.sockets.append(socket.socket(socket.AF_LORA, socket.SOCK_RAW))
      self.sockets[nr+2].setblocking(False)
      if nr: self.sockets[nr+2].bind(nr+2)
      if self.debug: print("Installed LoRa port %d" % (nr+2))
    return True

  def send(self, data, port=2):
    """
    Send data over the network.
    """
    if (port < 2) or (port > len(self.sockets)): raise ValueError('Unknown LoRa port %d' % port)
    if not self.sockets[port]: raise OSError('No socket')

    rts = True
    try:
      self.sockets[port].send(data)
      if self.LED: self.LED.blink(2, 0.1, 0x0000ff)
      if self.debug: print("Sending data")
      # print(data)
    except OSError as e:
      if e.errno == 11:
        print("Caught exception while sending")
        print("errno: ", e.errno)
      else: print("Lora ERROR: %s" % e)
      rts = False

    if self.LED: self.LED.off
    data = self.sockets[port].recv(64)
    if self.debug: print("Received data:", data)
    if self.callback and data:
       self.callback(port,data)

    sleep_ms(1000); self.dump # save status
    return rts

  @property
  def dump(self):
    from time import sleep_ms
    sleep_ms(2000)
    if self.debug: print("Save LoRa keys")
    return self.lora.nvram_save()

  @property
  def restore(self):
    self.lora.nvram_restore()
    if self.debug: print("Restore LoRa keys")
    return self.lora.stats().tx_counter

  @property
  def status(self):
    return self.lora.stats().tx_counter

  @property
  def clear(self):
    if self.debug: print("Clear LoRa keys")
    self.lora.nvram_erase()
