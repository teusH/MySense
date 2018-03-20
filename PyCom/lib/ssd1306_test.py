from machine import SPI   # ssd1306 display via GPIO
import SSD1306
from machine import unique_id
from machine import Pin
import binascii
from led import LED
import pycom

# stop processing press user button
button = Pin('P10',mode=Pin.IN, pull=Pin.PULL_UP)
#led = Pin('P9',mode=Pin.OUT)

def pressed(what):
  #global LED
  print("Pressed %s" % what)
  # LED.blink(5,0.1,0xff0000,False)

#  global led
#  led.toggle()

button.callback(Pin.IRQ_FALLING|Pin.IRQ_HIGH_LEVEL,handler=pressed,arg='STOP')

# red P24 3v3 and black P25 Gnd
# SPI pins
S_CLK  = 'P19'  # brown D0
S_MOSI = 'P23'  # white D1
S_MISO = 'P18'  # NC
# SSD pins
S_DC   = 'P20'  # purple DC
S_RES  = 'P21'  # gray   RES
S_CS   = 'P22'  # blew   CS

oled = None
def display(txt,x,y,clear, prt=True):
  ''' Display Text on OLED '''
  global oled
  if oled != None:
    if clear:
      oled.fill(0)
    oled.text(txt,x,y)
    oled.show()
  if prt:
    print(txt)

def rectangle(x,y,w,h,col=1):
  global oled
  ex = int(x+w); ey = int(y+h)
  for xi in range(int(x),ex):
    for yi in range(int(y),ey):
      oled.pixel(xi,yi,col)

def ProgressBar(x,y,width,height,secs,blink=0,slp=1):
  global oled, LED
  rectangle(x,y,width,height)
  if (height > 4) and (width > 4):
    rectangle(x+1,y+1,width-2,height-2,0)
    x += 2; width -= 4;
    y += 2; height -= 4
  elif width > 4:
    rectangle(x+1,y,width-2,height,0)
    x += 2; width -= 4;
  else:
    rectangle(x,y,width,height,0)
  step = width/(secs/slp); xe = x+width; myslp = slp
  if blink: myslp -= (0.1+0.1)
  for sec in range(int(secs/slp+0.5)):
    if blink:
      LED.blink(1,0.1,blink,False)
    sleep(myslp)
    if x > xe: continue
    rectangle(x,y,step,height)
    oled.show()
    x += step
  return True

try:
    # Turn off hearbeat LED
    pycom.heartbeat(False)

    # spi = SPI(0,SPI.MASTER, baudrate=100000, parity=0, phase=0, pins=('P10', 'P11', 'P14'))
    spi = SPI(0,SPI.MASTER, baudrate=100000,pins=(S_CLK, S_MOSI, S_MISO))
    # oled display: defaults dc = P5, res = P6, cs = P7
    oled = SSD1306.SSD1306_SPI(128,64,spi,S_DC, S_RES, S_CS)
    if not ProgressBar(0,44,128,8,30,0xebcf5b,10):
        LED.blink(5,0.3,0xff0000,True)
    display("MySense PyCom",0,0,True)
    myID = binascii.hexlify(unique_id()).decode('utf-8')
    display("s/n " + myID, 0, 16, False)
except:
    print("Failed to initiate oled display")
