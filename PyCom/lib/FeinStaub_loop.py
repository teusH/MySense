'''
Created on 23 Apr 2017

@author: rxf
'''
import time
import machine

# from umqtt import MQTTClient
from network import WLAN
import sds011
# from machine import I2C
from machine import SPI, Pin
import pycom
import socket
from network import LoRa
import binascii
from network import WLAN



# Globale KONSTANTEN
MQTT_HOST='rexfue.de'
MQTT_TOPIC='/Feinstaub/raspi_Z/'

########################
# Put in Your Keys here
########################
import appkeys

########################
# define used sensor (SD011 is always selected)
use_ssd1306 = True
use_bme280 = True

# import the necessary drivers
if use_ssd1306:
    import ssd1306
    
if use_bme280:
    import bme280        
    
# define timings fpr SDS011    
SDS_REPEAT_TIME = 150           # alle 150 sec messen
SDS_WARMUP = 10                 # 10 Sekunden War,up für den SDS
SDS_MEASURE = 15                # dann 5sec (== 5mal) messen


# Globale Variable
aktTimer = 0;
# SDSisRunning = False
SDS_sumP10 = 0
SDS_sumP25 = 0
SDS_P10 = 0
SDS_P25 = 0
SDS_cnt = 0
temp = 0
humi = 0
press = 0

    
def doSDS(tick):
    ''' SDS: read data, calculate average over 5 values '''
    global SDS_P10, SDS_P25, SDS_sumP10, SDS_sumP25, SDS_cnt
    
    if tick < SDS_WARMUP:
        sds011.readSDSvalues()
        return False                                  # 10sec only wait
    if tick < SDS_MEASURE:
        P10,P25 = sds011.readSDSvalues()
        if P10 > 0 and P25 > 0:
            SDS_sumP10 = SDS_sumP10 + P10
            SDS_sumP25 = SDS_sumP25 + P25
            SDS_cnt = SDS_cnt+1
        return False
    
    if SDS_cnt != 0:
        SDS_P10 = SDS_sumP10 / (SDS_cnt * 10)
        SDS_P25 = SDS_sumP25 / (SDS_cnt * 10)
    SDS_sumP10 = 0
    SDS_sumP25 = 0
    SDS_cnt = 0
    sds011.startstopSDS(False)
    return True
# END  def doSDS(tick):           
            
       
def showData():
    ''' print data to console and to display '''
    global SDS_P10, SDS_P25, temp, humi, press, client, s

    print('SDS P10:',SDS_P10)
    print('SDS_P25:',SDS_P25)     
    print('Temperatur: ',temp)
    print('Feuchte: ',humi)
    print('Druck (local): ', press)
    if use_ssd1306:
        display("P10  "+str(SDS_P10),0,0,True)
        display("P25  "+str(SDS_P25),0,12,False)
        display("T    "+str(temp),0,28,False)
        display("F    "+str(humi),0,40,False)
        display("P    "+str(press),0,52,False)
    
def display(txt,x,y,clear):
    ''' Display Text on OLED '''
    if use_ssd1306:
        if clear:
            oled.fill(0)
        oled.text(txt,x,y)
        oled.show()
    
if use_bme280:
    i2c = I2C(0,)
    bme = bme280.BME280(i2c=i2c)

if use_ssd1306:
    #oled = ssd1306.SSD1306_I2C(128,64,i2c)
    oled = ssd1306.SSD1306_PSI(128,64,spi,Pin('P20'),Pin('P21'),Pin('P22'))

waitTime = 0
SDStickCnt = 0
print("Starting...")


# Colors
off = 0x000000
red = 0xff0000
green = 0x00ff00
blue = 0x0000ff

# Turn off hearbeat LED
pycom.heartbeat(False)

# Initialize LoRaWAN radio
lora = LoRa(mode=LoRa.LORAWAN)

# Set network keys
app_eui = binascii.unhexlify(appkeys.APP_EUI) 
app_key = binascii.unhexlify(appkeys.APP_KEY)

# Switch OFF WLAN
#print("Disable WLAN");
#wlan = WLAN()
#wlan.deinit()

# Join the network
print("Try to Join Network ....")
lora.join(activation=LoRa.OTAA, auth=(app_eui, app_key), timeout=0)
pycom.rgbled(red)
display("Joining LoRa ...",0,0,True)

# Loop until joined
while not lora.has_joined():
    print('Not joined yet...')
    pycom.rgbled(off)
    time.sleep(0.1)
    pycom.rgbled(red)
    time.sleep(2)

print('Joined')
display("Joined !", 0,20,False)

display("Wait 1 min ..",0,40,False)

pycom.rgbled(blue)

s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)
s.setblocking(True)


startTimer = int(round(time.time()))

while True:
    aktTimer = int(round(time.time()))
    timeover = aktTimer - startTimer

    # Do every second:
    if timeover >= 1:                       # 1 sec over
        # restart startTimer 
        startTimer = aktTimer;              # Timer reinit
        # Timers zählen
        waitTime = waitTime + 1;            # inc Waittime and SDStickCnt
        SDStickCnt = SDStickCnt + 1
        #work on SDS011
        if sds011.SDSisRunning:             # if SDS011 is running
            ready = doSDS(SDStickCnt)       # handle it
            if ready:
                showData()
                tosend = '{"P1":'+str(SDS_P10)+',"P2":'+str(SDS_P25)+'}'
                count = s.send(tosend)
                print('Sent %s  count:%s' % (tosend,count))
                tosend = '{"T":"'+temp+'","H":"'+humi+'","P":"'+press+'"}'
                count = s.send(tosend)
                print('Sent %s count:%s ' % (tosend,count))
                pycom.rgbled(green)
                time.sleep(0.1)
                pycom.rgbled(0x000010)
        # after one minute     
        if waitTime >= SDS_REPEAT_TIME:     # 1 min over
            print('1min um')
            waitTime = 0                    # restart Timer
            sds011.startstopSDS(True)       # start SDS      
            SDStickCnt = 0            
            if use_bme280:
                temp = bme.temperature
                press = bme.pressure
                humi = bme.humidity


print("All over")                           # will be never reached

