# -*- coding: utf-8 -*-
import time

# after examples from Adafruit SSD1306
import Adafruit_GPIO.SPI as SPI
import Adafruit_SSD1306
import sys
import logging

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

# display variables
disp = None
width = None
height = None
image = None
draw = None
# Load default font.
font = None
fntSize = 8
# Alternatively load a TTF font.  Make sure the .ttf font file is in the same directory as this python script!
# Some nice fonts to try: http://www.dafont.com/bitmap.php
# font = ImageFont.truetype('Minecraftia.ttf', 8)
Lines = None
stop = False
YB   = False # display is yellow blue type

# initialize the display, return ref to the display
def InitDisplay(type,size,yb = False):
    global disp, width, height, image, draw, YB

    # Raspberry Pi pin configuration:
    RST = 24
    # Note the following are only used with SPI:
    DC = 23
    SPI_PORT = 0
    SPI_DEVICE = 0
    # Note the following is only used with I2C:
    I2C = 1     # i2c bus number
    
    if type == 'I2C' and size == '128x32':
        # 128x32 display with hardware I2C:
        disp = Adafruit_SSD1306.SSD1306_128_32(rst=RST,i2c_bus=I2C)
    elif type == 'I2C' and size == '128x64':
        # 128x64 display with hardware I2C:
        disp = Adafruit_SSD1306.SSD1306_128_64(rst=RST,i2c_bus=I2C)
    elif type == 'SPI' and size == '128x32':
        # 128x32 display with hardware SPI:
        disp = Adafruit_SSD1306.SSD1306_128_32(rst=RST, dc=DC, spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz=8000000))
    elif type == 'SPI' and size == '128x64':
        # 128x64 display with hardware SPI:
        disp = Adafruit_SSD1306.SSD1306_128_64(rst=RST, dc=DC, spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz=8000000))
    else: raise ValueError("Unknown Adafruit Display.")

    # Initialize library.
    disp.begin()
    # Get display width and height.
    width = disp.width
    height = disp.height
    YB = yb
    
    # Clear display.
    disp.clear()
    disp.display()

    ClearDisplay()

    return True

def ClearDisplay():
    global image, draw

    # image with mode '1' for 1-bit color
    image = Image.new('1', (width, height))
    
    # Create drawing object
    draw = ImageDraw.Draw(image)
    # draw.rectangle((0,0,width-1,height-1), outline=1, fill=0)

    return True
    

# add a line to the pool
# TO DO: font and font size is per line now
def addLine(text,**args):
    global Lines, font, fntSize, draw
    if ('font' in args.keys()) and (type(args['font']) is str):
        if 'size' in args.keys(): fntSize = int(args['size'])
        if fntSize < 4: fintSize = 8
        try:
            font = ImageFont.truetype(args['font'],fntSize)
        except:
            font = None
    if font == None:
        font = ImageFont.load_default(); fntSize = 8
    clear = (False if (not 'clear' in args.keys()) else args['clear'])
        
    unused, MaxH = draw.textsize(text, font=font)
    if Lines == None: Lines = []
    while True:
        if len(Lines) > 100: sleep(5)   # wait till more lines are displayed
        else: break
    Lines.append( {
        'x':1,'MaxH': MaxH,
        'txt':text,
        'fnt': font,
        'fill': 255 if not 'fill' in args.keys() else args['fill'],
        'clear': clear,    # clear display and push this line on top display
        'timing': int(time.time()),
        })
    return True

# allow to scroll if text width exceeds display width
def scroll(linenr,yPos):
    global Lines, width, height, draw
    # baseY = yPos+Lines[linenr]['MaxH']
    if yPos > height: return False
    if not 'strt' in Lines[linenr].keys(): Lines[linenr]['strt'] = -6
    txt = Lines[linenr]['txt']
    if Lines[linenr]['strt'] > 0:
        txt = Lines[linenr]['txt'][Lines[linenr]['strt']:]
    delay = False
    if txt[0] == '|': delay = True
    twidth, unused = draw.textsize(txt, font=Lines[linenr]['fnt'])
    trimmed = False
    while twidth > width:
        trimmed = True
        txt = txt[:-1]
        twidth, unused = draw.textsize(txt, font=Lines[linenr]['fnt'])
    if (Lines[linenr]['fill'] > 0) and (time.time()-Lines[linenr]['timing'] > 65*60):
        Lines[linenr]['fill'] -= 1
    draw.text((1, yPos), txt, font=Lines[linenr]['fnt'], fill=Lines[linenr]['fill'])
    if trimmed:
        Lines[linenr]['strt'] += 1
    else:
        Lines[linenr]['strt'] = -6
    return delay

# display as much lines as possible
DisplayError = 0
def Display(lock):
    global Lines, draw, image, disp, DisplayError, YB, height
    if Lines == None or not len(Lines): return (False,False)
    # ClearDisplay()
    # Clear image buffer by drawing a black filled box.
    linenr = 0; Ypos = 1 ; delay = False
    while True:
        if lock != None:
            with lock: nrLines = len(Lines)
        else:
            nrLines = len(Lines)
        if not linenr:    # clear display
            if Ypos:
                draw.rectangle((0,0,width,height), outline=0, fill=0)
            Ypos = 0; trimmedY = False
        if linenr >= nrLines: break
        if YB and (linenr >= 5):
           trimmedY = True
           break
        if Ypos > height:
           trimmedY = True
           break
        if Lines[linenr]['clear']:
            Lines[linenr]['clear'] = False
            for i in range(0,linenr):
                Lines.pop(0)
            linenr = 0
            continue
        if not linenr:      # clear display
            draw.rectangle((0,0,width,height), outline=0, fill=0)
        if scroll(linenr,Ypos): delay = True
        Ypos += Lines[linenr]['MaxH']
        if YB and not linenr: Ypos += 3  # first yellow line takes 3 leds extra
        linenr += 1
    # Draw the image buffer.
    disp.image(image)
    try:
        disp.display()
        DisplayError = 0
    except:
        # print("Failure in displaying image")
        if DisplayError > 10:
            logging.exception("Display Server: too may SSD1306 display errors.")
            sys.exit("Too many I2C ERRORs while displaying on SSD1306.")
        disp.image(image)
        try:
            disp.display()
        except:
            DisplayError += 1
        logging.exception("WARNING Display Server: SSD1306 display error.")
    return trimmedY,delay

# run forever this function
def Show(lock, conf):
    global Lines
    count = 0
    if 'lines' in conf.keys() and (type(conf['lines']) is list):
        Lines = conf['lines']
    if Lines == None: Lines = []
    # TO DO: slow down if there are no changes
    #        scroll line by tab stop with longer show delay
    if not 'stop' in conf.keys(): conf['stop'] = False
    while not conf['stop']:
        if not len(Lines):
              time.sleep(5)   # first line has a delay of 5 seconds
              count = 0
              continue
        trimmedy,delay = Display(lock)
        if trimmedy:          # scroll vertical, allow 10 seconds for top line to read
            if int(time.time()) - Lines[0]['timing'] > 10:
                if lock != None:
                    with lock: Lines.pop(0)
                else:
                    if len(Lines): Lines.pop(0)
        if delay: time.sleep(10)
        else: time.sleep(0.3)
        

if __name__ == "__main__":
    BUS = 'I2C'
    SIZE = '128x64'
    YB = True
    InitDisplay(BUS,SIZE,yb=YB)
    addLine('First short line',  font=font, fill=255)
    addLine('Second short line')
    addLine('Third line')
    addLine('|Forth a longer line,  | more a the previous line.')
    addLine('Fifth short line.')
    addLine('|This might be the last| line to be displayed.')
    addLine('Seventh line will scroll the display')
    addLine('Eight line will scroll the display', clear=True)
    addLine('Nine  line will scroll the display')

    Show(None,{})
