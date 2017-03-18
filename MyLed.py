#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
#
# Copyright (C) 2017, Behoud de Parel, Teus Hagen, the Netherlands
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from __future__ import print_function

# $Id: MyLed.py,v 1.1 2017/03/18 16:11:15 teus Exp teus $

# Turn Grove led on, off or blink for an amount of time

""" Turn Grove led on, off or blink for an amount of time
    MyLed [--on|--off|--blink N,M,O|--led Dn|--button Dm]
    default: led off
    blink: N (dflt 1) secs on (dflt 1), M secs off, O period in minutes (dlft 30m)
    led: Grove socket nr (dflt D6)
    button: Grove socket nr (dflt: None) time button is pressed
"""
progname='$RCSfile: MyLed.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.1 $"[11:-2]
__license__ = 'GPLV4'
grovepi = None
import sys
try:
    import atexit
    import argparse
    grovepi = __import__('grovepi')
except ImportError:
    print("ERROR: One of the modules missing")
    exit(1)

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    exit(1)

SOCKET = 'D6'
LED = 'OFF'
BLINK=[]
BUTTON = 'D0'

def get_arguments():
    global LED, SOCKET, BLINK, BUTTON
    parser = argparse.ArgumentParser(prog=progname, description='System led ON/OFF switch, and time button is pressed - Behoud de Parel', epilog="Copyright (c) Behoud de Parel\nAnyone may use it freely under the 'GNU GPL V4' license.")
    parser.add_argument("--light", help="Switch system led ON or OFF (dlft).", default=LED, choices=['ON','on','OFF','off'])
    parser.add_argument("--blink", help="Switch system led on/off for a period of time (e.g. 1,1,30 : 1 sec ON, optional 1 sec (dflt) OFF, optional max period 30 (dflt) minutes).",default='0,0,30')
    parser.add_argument("--led", help="Led socket number, e.g. D6 (dflt)", default=SOCKET,choices=['D3','D4','D5','D6','D7'])
    parser.add_argument("--button", help="Button socket number, e.g. D5 (dflt=None)", default=BUTTON,choices=['D3','D4','D5','D6','D7'])
    args = parser.parse_args()
    SOCKET = int(args.led[1])
    LED = 0
    if args.light.upper() == 'ON':
        LED = 1
    BLINK = args.blink.split(',')
    if len(BLINK) == 0:
        BLINK[0] = 0
    else:
        BLINK[0] = int(BLINK[0])
    if len(BLINK) <= 1:
        BLINK[1] = 0
    else:
        BLINK[1] = int(BLINK[1])
    if len(BLINK) != 3:
        BLINK[2] = 30
    else:
        BLINK[2] = int(BLINK[2])
    if BLINK[0] != 0:
        LED = 1
    BUTTON = int(args.button[1])

def Led_Off():
    global grovepi
    grovepi.digitalWrite(SOCKET,0)
    exit(0)

from time import time
started = time()

PRESSED = 0
def pressed():
    global PRESSED, started, LED, BLINK, grovepi, SOCKET
    if not BUTTON: return
    while True:
        try:
            NEW = grovepi.digitalRead(BUTTON)
        except IOError:
            eprint("Button IOError")
        if PRESSED and (not NEW):
            print("%d" % int(time()-started))
            grovepi.digitalWrite(SOCKET,0)
            exit(0)
        if (not PRESSED) and (not NEW):
            # wait for button press and try again
            sleep(5)
            continue
        if (not PRESSED) and NEW:
            PRESSED = NEW
            started = time()
            BLINK = [1,1,30]
            LED = 1
        elif (int(time()-started)/6) >= 1:
            BLINK = [(int(time()-started)/6),1,30]
            LED = 1
        return
   
get_arguments()

grovepi.pinMode(SOCKET,'OUTPUT')
import signal
if BUTTON:
    grovepi.pinMode(BUTTON,'INPUT')
    signal.signal(signal.SIGHUP,Led_Off)
    signal.signal(signal.SIGKILL,Led_Off)
    # atexit.register(Led_Off)

from time import sleep
sleep(0.5)

while True:
    try:
        pressed()
        if time() - started >= BLINK[2]*60:
            grovepi.digitalWrite(SOCKET,0)
            break
        grovepi.digitalWrite(SOCKET,LED)
        if not BLINK[0]:
            break
        sleep(BLINK[LED])
        LED = not LED
    except IOError:
        eprint("IO ERROR")
    except KeyboardInterrupt:
        grovepi.digitalWrite(SOCKET,0)
        exit(0)
    except:
        grovepi.digitalWrite(SOCKET,0)
        
