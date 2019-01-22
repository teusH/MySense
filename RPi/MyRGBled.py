#!/usr/bin/env python
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

# $Id: MyRGBled.py,v 1.2 2019/01/22 12:04:26 teus Exp teus $

# exercise RGB ed of Pi different colloprs for a period of time
# <led color=red secs=0.2> ....
# if secs option is undefined or 0 period is unlimited till next command
# use: Conf dict as configuration
# inSync=False do use multi threading
# pinR:11 pinY:13 pinB:15 pin of Pi used for color led, if one isdnot defined no led
# if not GPIO import (run is not on a Pi) no RGBled is used
# debug = False provide extra debug info

import time
import re
import threading
import atexit

class RGBthread:
    ''' manage the RGB leds of the Pi '''
    def __init__(self, conf, debug=False, inSync=False):
        self.debug = debug
        if 'debug' in conf.keys(): self.debug = conf['debug']
        self.conf = conf
        self.threads = []; self.name = 'RGBthread'
        self.gpio = {}
        self.pins = False; self.RGBopen()
        self.STOP = False
        self.inSync = inSync # use threading or not
        if 'RGBlock' in conf.keys(): self.lock = conf['RGBlock']
        else:
            self.lock = threading.Lock()
            self.condition = threading.Condition(self.lock)
        self.commands = []
        if not self.inSync: self.start_thread()
        return

    # activated by thread start()
    # note subthreads will not catch Keyboard Interrupt <cntrl>c
    # kill it by <cntrl>z and kill %1
    class ThisThread(threading.Thread):   # the real run part of the thread
        def __init__(self,threading,loop,threadID, name):
            threading.Thread.__init__(self)
            self.threadID = threadID
            self.name = name
            self.loop = loop
        def run(self):
            # print("Thread started with self.loop call")
            self.loop()
            # print("Thread %s stopped." % self.name)
            return

    # stop the thread
    def stop_thread(self):
        self.STOP = True        # ask self threads to stop
        if not self.inSync:
            self.lock.acquire()
            self.condition.notify()
            self.lock.release()
            for thrd in threading.enumerate():
                try:
                    threading.join()
                except:
                    pass
            if self.debug: print("Stopped threads.")
        self.RGBstop()
        return

    # initialize
    def start_thread(self):
        if self.STOP: return True
        ID = threading.activeCount()+1
        for Trd in self.threads:
            if Trd.getName() == self.name:
                if Trd.isAlive():
                    return True
                else:
                    # maybe we should join first to delete the thread?
                    self.threads.remove(Trd)
        self.threads.append(self.ThisThread(threading, self.run, ID, self.name))
        try:
            atexit.register(self.stop_thread)
            self.threads[len(self.threads)-1].start()
            # time.sleep(2)      # allow some data to come in
        except:
            return False
        return True

    # ready RGB hardware
    def RGBopen(self):
        self.pins = True
        try:
            for pin in ['pinR','pinG','pinB']:
                if not pin in self.conf.keys(): raise ValueError("Missing pin %s def" % pin)
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BOARD)       # Numbers GPIOs by physical location
            for pin in ['pinR','pinG','pinB']:
                GPIO.setup(self.conf[pin], GPIO.OUT)   # Set conf' mode is output
                GPIO.output(self.conf[pin], GPIO.HIGH) # Set conf to high(+3.3V) to off led
            self.gpio = {}
            for pin in ['pinR','pinG','pinB']:
                self.gpio[pin] = GPIO.PWM(self.conf[pin], 2000)  # set Frequence to 2KHz
                self.gpio[pin].start(0)      # Initial duty Cycle = 0(leds off)
        except Excerption as err:
            self.pins = False
            print("RGB hw init failed")
	    return False
        return True
    
    # RGB hardware reset
    def RGBstop(self):
        try:
            if (not self.pins) or (not len(self.gpio)): return
            for pin in ['pinR','pinG','pinB']:
                self.gpio[pin].stop()
                GPIO.output(self.conf[pin], GPIO.HIGH)    # Turn off all leds
            GPIO.cleanup()
            self.gpio = {}
        except: pass
    
    def RGBhasOne(self):
        if len(self.commands): return True
        else: return False

    def RGBgetOne(self):
        # print("RGBgetOne called")
        if not self.inSync:
            # if self.debug: print("RGBgetOne gets lock")
            self.lock.acquire()
            # if self.debug: print("RGBgetOne has lock")
        if not len(self.commands): cmd = {}
        else: cmd = self.commands.pop(0)
        if not self.inSync: self.lock.release()
        if self.debug: print("RGB got command: ", cmd)
        return cmd

    def run(self):
        if not self.inSync:
            if self.debug: print("RGB run() thread start")
        while True:
            try:
                if self.STOP:
                    # print("RGB thread stopped")
                    break
                cmd = {}
                if not self.inSync:
                    while True:
                        self.lock.acquire()
                        if self.RGBhasOne():
                            self.lock.release(); break
                        # if self.debug: print("Thread wait on condition RGB cmd ready")
                        self.condition.wait()
                        # if self.debug: print("Thread leaves waits for RGB command")
                        self.lock.release()
                cmd = self.RGBgetOne()
                if (cmd == None) or (not 'color' in cmd.keys()):
                    if not self.inSync: continue
                    else: break
                self.setColor(int(cmd['color']))
                if ('secs' in cmd.keys()) and (cmd['secs'] <= 0.001): continue
                if self.debug:
                    print("RGBthread light for %f seconds" % cmd['secs'])
                time.sleep(cmd['secs'])
                self.setColor(0xFFFFFF)  # color black
                if self.inSync: return
            except Exception as err:
                print("Thread exception as %s" % err)
                break

    def Map(self, x, in_min, in_max, out_min, out_max):
        return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    
    colors = {
        'WHITE': 0XFFFFFF,
        'SILVER': 0XC0C0C0,
        'GRAY': 0X808080,
        'GREY': 0X808080,
        'BLACK': 0X000000,
        'RED': 0XFF0000,
        'MAROON': 0X800000,
        'YELLOW': 0XFFFF00,
        'OLIVE': 0X808000,
        'LIME': 0X00FF00,
        'GREEN': 0X008000,
        'AQUA': 0X00FFFF,
        'TEAL': 0X008080,
        'BLUE': 0X0000FF,
        'NAVY': 0X000080,
        'FUCHSIA': 0XFF00FF,
        'PURPLE': 0X800080,
        'CYAN': 0X00FFFF,
        'DARKBLUE': 0X0000A0,
        'LIGHTBLUE': 0XADD8E6,
        'ORANGE': 0XFFA500,
        'PURPLE': 0X800080,
        'BROWN': 0XA52A2A,
        'MAGENTA': 0XFF00FF,
    }

    def setColor(self,col):   # For example : col = 0x112233
        freq = {
            'pinR': 100 - self.Map((col & 0xFF0000) >> 16, 0, 255, 0, 100),
            'pinG': 100 - self.Map((col & 0x00FF00) >> 8, 0, 255, 0, 100),
            'pinB': 100 - self.Map((col & 0x0000FF) >> 0, 0, 255, 0, 100)
        }
        if self.debug: print("Set led to color: 0x%.6X" % col)
        for f in freq.keys():
            if self.debug or (not self.pins):
                print("Set led color %s: %d%%" % ( f, freq[f]))
            if self.pins:
                self.gpio[f].ChangeDutyCycle(freq[f])  # Change duty cycle

        # R_val = map((col & 0xFF0000) >> 16, 0, 255, 0, 100)
        # G_val = map((col & 0x00FF00) >> 8, 0, 255, 0, 100)
        # B_val = map((col & 0x0000FF) >> 0, 0, 255, 0, 100)
    
        # self.gpio['pinR'].ChangeDutyCycle(100-R_val)     # Change duty cycle
        # self.gpio['pinG'].ChangeDutyCycle(100-G_val)
        # self.gpio['pinB'].ChangeDutyCycle(100-B_val)

    def RGBcommand(self, strg):
        strt = 0; myStrg = strg.upper()
        while True:
            strt = myStrg.find('<LED ',strt)
            if strt < 0: return
            end = myStrg.find('>', strt+5)
            if end < 0: return
            end += 1
            self.AddRGBcommand(myStrg[strt:end])
            strt = end

    def AddRGBcommand(self, light):
        light = light[4:].upper()
        try: light = light[:light.index('>')]
        except: pass
        light = light.strip()
        cmd = {'secs': 0}
        light = re.sub(' +',' ',light)
        for word in light.split():
            try:
                if word[:3] == 'COL':
                    color = word[word.index('=')+1:]
                    if color.upper() in self.colors.keys():
                        cmd['color'] = self.colors[color.upper()]
                    else:
                        cmd['color'] = int(word[word.index('=0')+1:],0)
                elif word[:3] == 'SEC': cmd['secs'] = float(word[word.index('=')+1:])
                else: print("Unknow RGB word %s" % word)
            except: pass
        if cmd['secs'] > 60*5.0: cmd['secs'] = 0 # 5 minutes is forever
        if not 'color' in cmd.keys(): return False
        # if self.debug: print("Require lock for add a command")
        if not self.inSync: self.lock.acquire()
        # if self.debug: print("Add RGB command:", cmd)
        self.commands.append(cmd)
        if not self.inSync:
            # print("And notify waiter")
            self.condition.notify()
            self.lock.release()
        return True
    
if __name__ == '__main__':
    Conf = {'pinR':11, 'pinG':13, 'pinB':15,}  # Conf is a dict
    Conf['debug'] = True
    RGB = RGBthread(Conf, debug=True, inSync=False)
    try:
        colCmds = [
            '<led color=0xFF0000 sec=0.5>\n',
            '<led color=0x00FF00 sec=1.5>\n',
            '<led color=0x0000FF>\n',
            '<led color=0xFF0F00 sec=0>',
            '<led color=red sec=2>\n',
            '<led color=green sec=2>\n',
            '<led color=blue sec=2>\n',
            '<led color=white sec=2>\n',
            '<led color=black sec=2>\n',
            ]:
        if len(sys.argv) > 1: colCmds = argv[1:]
        for col in colCmds:
            RGB.AddRGBcommand(col)
            if RGB.inSync: RGB.run()
            time.sleep(0.5)
        time.sleep(10)
    except Exception as err:
        print("Exception %s" % err)
    finally:
        RGB.stop_thread()

