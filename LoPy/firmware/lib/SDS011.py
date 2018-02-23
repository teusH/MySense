'''
Created on 24 Apr 2017

@author: rxf
'''
from machine import  UART

# read from UART1 V5,Gnd, SDS011/Rx - GPIO P3/Tx, SDS011/Tx - GPIO P4/Rx
ser = UART(1,baudrate=9600)
SDSisRunning = None

def readSDSvalues():
    ''' read PM values '''
    global ser
    
    while True:
        n = ser.any()
        if n == 0:
            continue
        if n > 10:
            ser.read(n)
            continue
        rcv = ser.read(10)
        if len(rcv) != 10:
            continue
        if rcv[0] != 170 and rcv[1] != 192:
            print("try to sychronize")
            continue
        i = 0
        chksm = 0
        while i < 10:
            if i >= 2 and i <= 7:
                chksm = (chksm + rcv[i]) & 255
            i = i+1
        if chksm != rcv[8]:
            print("*** Checksum-Error")
            return -1,-1
        pm25 = (rcv[3]*256+rcv[2])
        pm10 = (rcv[5]*256+rcv[4])
        return pm10/10.0,pm25/10.0
        
# SDS anhalten bzw starten
def startstopSDS(was):
    """ den SDS011 anhalten bzw. starten:
    was = TRUE  --> fan start, wait 15 secs
    was = FALSE --> fan stop
    """
    global SDSisRunning, ser
    
    start_SDS_cmd = bytearray(b'\xAA\xB4\x06\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF\x06\xAB')
    stop_SDS_cmd =  bytearray(b'\xAA\xB4\x06\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF\x05\xAB')
    if was == True:
        ser.write(start_SDS_cmd)
        print("SDS fan/laser start.")
    else:
        ser.write(stop_SDS_cmd)
        print("SDS fan/laser off")
    SDSisRunning = was
# END def startstopSDS(was):
    
        
