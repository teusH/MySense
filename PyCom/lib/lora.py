""" LoRaWan module interface
"""

# script from https://github.com/TelenorStartIoT/lorawan-weather-station
# $Id: lora.py,v 1.3 2018/10/25 18:57:19 teus Exp teus $

import socket
from binascii import unhexlify
from network import LoRa
from led import LED

class LORA(object):
  'Wrapper class for LoRa'

  # LoRa and socket instances
  lora = None
  s = None

  #def connect(self, dev_eui, app_eui, app_key, ports=1, callback=None):
  def connect(self, method, ports=1, callback=None):
    """
    Connect device to LoRa.
    Set the socket and lora instances.
    """

    self.callback = callback # call back routine on LoRa reply callback(port,response)
    # Disable blue blinking and turn LED off
    LED.heartbeat(False)
    LED.off()

    # Initialize LoRa in LORAWAN mode
    self.lora = LoRa(mode = LoRa.LORAWAN)

    if (not 'OTAA' in method.keys()) or (not 'ABP' in method.keys()):
        print("No activation method defined.")
        return False
    count = 0
    if 'OTAA' in method.keys():
        # Join a network using OTAA (Over the Air Activation)
        dev_eui = unhexlify(method['OTAA'][0])
        app_eui = unhexlify(method['OTAA'][1])
        app_key = unhexlify(method['OTAA'][2])
        self.lora.join(activation = LoRa.OTAA, auth = (dev_eui, app_eui, app_key), timeout = 0)
        # Wait until the module has joined the network
        while not self.lora.has_joined():
          LED.blink(1, 2.5, 0xff0000)
          if count > 5:
            count = 0
            break
          print("Wait for OTAA join: " ,  count)
          sleep(12) # auto retry is 15 secs
          count += 1
        if self.lora.has_joined():
          count += 1
          print("LoRa OTAA joined.")

    if not count:
        if not 'ABP' in method.keys(): return False
        import struct
        dev_addr = struct.unpack('>l', unhexlify(method['ABP'][0]))[0]
        nwk_swkey = unhexlify(method['ABP'][1])
        app_swkey = unhexlify(method['ABP'][2])
        self.lora.join(activation = LoRa.ABP, auth = (dev_addr, nwk_swkey, app_swkey))
        print("LoRa method ABP.")

    # Create a LoRa socket
    LED.blink(2, 0.1, 0x009900)
    self.s = []
    self.s.append(socket.socket(socket.AF_LORA, socket.SOCK_RAW))

    # Set the LoRaWAN data rate
    self.s[0].setsockopt(socket.SOL_LORA, socket.SO_DR, 5)

    # Make the socket non-blocking
    self.s[0].setblocking(False)

    # print("Create LoRaWAN socket")

    # Create a raw LoRa socket
    # default port 2
    self.s.append(None)
    for nr in range(ports):
      print("Setting up port %d" % (nr+2))
      self.s.append(socket.socket(socket.AF_LORA, socket.SOCK_RAW))
      self.s[nr+2].setblocking(False)
      if nr: self.s[nr+2].bind(nr+2)
    LED.off()
    return True

  def send(self, data, port=2):
    """
    Send data over the network.
    """
    if (port < 2) or (port > len(self.s)): raise ValueError('Unknown LoRa port')
    if not self.s[port]: raise OSError('No socket')

    rts = True
    try:
      self.s[port].send(data)
      LED.blink(2, 0.1, 0x0000ff)
      # print("Sending data")
      # print(data)
    except OSError as e:
      if e.errno == 11:
        print("Caught exception while sending")
        print("errno: ", e.errno)
      rts = False

    LED.off()
    data = self.s[port].recv(64)
    # print("Received data:", data)
    if self.callback and data:
       self.callback(port,data)
    return rts
