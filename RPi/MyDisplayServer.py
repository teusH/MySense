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

# $Id: MyDisplayServer.py,v 2.3 2019/01/28 11:22:08 teus Exp teus $

# script will run standalone, collects text lines from sockets streams and
# displays the scrolled lines on an Adafruit display

# display is an OLED SSD1306 little B/W screen
# use of RGBled
# needs MySSD1306_display.py module, which is based on Adafruit library software

import socket 
import threading
try:
    from SocketServer import ThreadingMixIn 
except:
    from socketserver import ThreadingMixIn 
import time
import sys
import os
import re
import atexit
 
# main thread starts display thread and maintains 5 socket readers on localhost/2017
# shared variables between the threads
Conf = {
    'stop': False,                # stop threads
    'lines': [],                  # lines to show on display
    'display': (None,'128x64',True),  # Adafruit display: SPI or I2C 32 or 64 pixels height, oled Y/B?
    'addLine': None,              # ref to addLine display routine
    'threads': [],                # threads alive deprecated
    'lock': threading.Lock(),     # lock between threads
    'rgb': False,                 # use RGBled, dflt no RGB led
    # 'pinR': 11, 'pinG': 13, 'pinB': 15, # default RGB Pi pins should be GPIO pins
    # use GPIO pin numbering!
    'pinR': 17, 'pinG': 27, 'pinB': 22, # default RGB Pi pins should be GPIO pins
    'debug': False,               # debug modus, no multi threading for sockets
    }
TCP_IP = 'localhost'
TCP_PORT = 2017 
FOREGRND = False
progname = "MyDisplayServer"
PID_FILE = '/var/tmp/' + progname + '.pid'

# Multithreaded Python server : TCP Server Socket Thread Pool

class DisplayThread(object):
    ''' manage the display in a thread '''
    def __init__(self,conf):
        self.logger = conf['logging']
        threading.__init__("display")
        self.conf = conf
        if 'lock' in conf.keys(): self.lock = conf['lock']
        else: self.lock = threading.Lock()
        self.type = conf['display'][0]
        self.size = conf['display'][1]
        self.yb = conf['display'][2]
        self.logger.debug("[+]Adafruit display started")
        try:
            self.SSD1306 = __import__("MySSD1306_display")
            if not self.SSD1306.InitDisplay(conf['display'][0],conf['display'][1],yb=conf['display'][2]):
                self.logger.debug("No SSD1306 desplay hardware found")
            self.conf['addLine'] = self.SSD1306.addLine
        except:
            self.logger.fatal("Display error for SSD1306 type %s size %s." %(conf['display'][0],conf['display'][1]))
            raise ValueError("Unknown SSD1306 type/size")

    def start(self):
        threading.Thread(target = self.SSD1306.Show,args = (self.lock,self.conf)).start()

class ClientThread(object):
    ''' socket listening threads '''
    def __init__(self, host, port, conf):
        self.logger = conf['logging']
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.conf = conf
        self.debug = False
        if 'debug' in self.conf.keys(): self.debug = self.conf['debug']
        if 'lock' in conf.keys(): self.lock = conf['lock']
        else: self.lock = threading.Lock()
        self.logger.debug("[+] New server socket thread started for " + host + ":" + str(port) )

    # no multi threaded listening in debug modus
    def listen(self):
        self.sock.listen(5)
        while True:
            client, address = self.sock.accept()
            if len(sys.argv) <= 1: # no client thread
                self.listenToClient(client,address)
            else:
                threading.Thread(target = self.listenToClient,args = (client,address)).start()

    def getAttr(self,string,search):
        ''' handle text attributes '''
        start = string.find(search)
        if start < 0: return ''
        start += len(search)
        end = string.find('"', start)
        if end < 0: return ''
        return string[start:end]

    def getFont(self,font):
        ''' find ttf file in the system '''
        import subprocess
        if not font: return ''
        try:
            df = subprocess.check_output(["/usr/bin/find","/usr/share/fonts/truetype/","-name",font + ".ttf"])
            for i in df.split('\n'):
                if i:
                    if i.find(font+".ttf") > 0:
                        return i
        except:
            pass
        return ''

    # TO DO: add text color and <img>
    def getArgs(self,string):
        ''' strip style xml attribute from string and return dict with style attributes '''
        attrs = {}
        if string[0] != '<': return {}
        if string[1:6] == 'clear': return { 'clear': True }
        elif string[1:5] == 'text':
            # <text> has attrubutes: fill, font, size
            fill = self.getAttr(string,'fill="')
            if fill and fill.isdigit():
                fill = int(fill)
                if fill > 255: fill = 255
                attrs['fill'] = fill
            font = self.getFont(self.getAttr(string,'font="'))
            if not font: return attrs
            size = self.getAttr(string,'size="')
            if (not size) or (not size.isdigit()): size = 8
            attrs.update({ 'font': font, 'size': int(size) })
            return attrs
            
    def listenToClient(self, client, address):
        ''' manage one connection to a socket '''
        if self.debug:
            self.conf['addLine']("New client accepted")
        client.settimeout(60)
        while not self.conf['stop']:
            try:
                data = self.linesplit(client) # generator object
                if data:
                    for txt in data:
                        txt = txt[:-1]     # delete end of line delimeter
                        self.logger.debug("Received a line: %s" % txt)
                        if txt[:4].lower() == '<led':
                            if self.conf['rgb']:
                              if not 'RGB' in self.conf.keys():
                                self.conf['RGB'] = RGBthread(self.conf, debug=self.conf['debug'], inSync=False)
                              txt = self.conf['RGB'].RGBcommand(txt)
                            else: txt = txt[txt.find('>')+1:]
                            if not len(txt): continue
                        if self.conf['addLine'] == None:
                            raise NameError("Unable to use addLine routine of Display")
                        args = {}
                        while True:
                            if (not len(txt)) or txt[0] != '<': break
                            newArgs = self.getArgs(txt)
                            if not len(newArgs): break
                            txt = txt[txt.find('>')+1:]
                            args.update(newArgs)
                        self.conf['addLine'](txt, **args)
                    client.close()
                    return True
                else:
                    self.logger.debug("Display server close this connection.")
                    
            except:
                client.close()
                return False
 
    def linesplit(self,client):                    # linesplit is a line generator
        ''' generator: list of lines '''
        size = 1024
        buffer = client.recv(size)
        buffering = True
        while buffering:
            if "\n" in buffer:
                (line, buffer) = buffer.split("\n", 1)
                yield line + "\n"
            else:
                more = client.recv(size)
                if not more:
                    buffering = False
                else:
                    buffer += more
        if buffer:
            yield buffer

# ===========================================================
# RGB led (multi threaded class
# ===========================================================

# MyRGBled.py 1.2 2019/01/22 12:04:26

# exercise RGB ed of Pi different colloprs for a period of time
# <led color=red secs=0.2 repeat=5> ....
# if secs option is undefined or 0 period is unlimited till next command
# if repeat is undefined the cmd is one time (wait between next seq is secs seconds.
# use: Conf dict as configuration
# inSync=False do use multi threading
# pinR:11 pinG:13 pinB:15 pin of Pi used for color led, if one isdnot defined no led
# if not GPIO import (run is not on a Pi) no RGBled is used
# debug = False provide extra debug info

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
            # need to use GPIO pin numbers iso board pin due to Adafruit display lib
            GPIO.setmode(GPIO.BCM)       # Numbers GPIOs by physical location
            for pin in ['pinR','pinG','pinB']:
                GPIO.setup(self.conf[pin], GPIO.OUT)   # Set conf' mode is output
                GPIO.output(self.conf[pin], GPIO.HIGH) # Set conf to high(+3.3V) to off led
            self.gpio = {}
            for pin in ['pinR','pinG','pinB']:
                self.gpio[pin] = GPIO.PWM(self.conf[pin], 2000)  # set Frequence to 2KHz
                self.gpio[pin].start(0)      # Initial duty Cycle = 0(leds off)
        except Exception as err:
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
                for cnt in range(0,cmd['repeat']):
                  if cnt: time.sleep(cmd['secs'])
                  self.setColor(int(cmd['color']))
                  if ('secs' in cmd.keys()) and (cmd['secs'] <= 0.001): continue
                  if self.debug:
                    print("RGBthread light for %f seconds" % cmd['secs'])
                  time.sleep(cmd['secs'])
                  self.setColor(0x000000)  # color black
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
            'pinR': self.Map((col & 0xFF0000) >> 16, 0, 255, 0, 100),
            'pinG': self.Map((col & 0x00FF00) >> 8, 0, 255, 0, 100),
            'pinB': self.Map((col & 0x0000FF) >> 0, 0, 255, 0, 100)
        }
        if self.debug: print("Set led to color: 0x%.6X" % col)
        for f in freq.keys():
            if self.debug or (not self.pins):
                print("Set led color %s: %d%%" % ( f, freq[f]))
            if self.pins:
                self.gpio[f].ChangeDutyCycle(freq[f])  # Change duty cycle

    def RGBcommand(self, strg):
        strt = 0; myStrg = strg.upper()
        fnd = myStrg.find('<LED ',strt)
        if fnd < 0: return strg[strt:]
        end = myStrg.find('>', strt+5)
        if end < 0: return ''
        end += 1
        self.AddRGBcommand(myStrg[strt:end])
        return strg[end:]

    def AddRGBcommand(self, light):
        light = light[4:].upper()
        try: light = light[:light.index('>')]
        except: pass
        light = light.strip()
        cmd = {'secs': 0, 'repeat': 1}
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
                elif word[:3] == 'REP': cmd['repeat'] = int(word[word.index('=')+1:])
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
    
    # Conf = {'pinR':11, 'pinG':13, 'pinB':15,}  # Conf is a dict
    # Conf['debug'] = True
    # RGB = RGBthread(Conf, debug=True, inSync=True)
    # colCmds = [ '<led color=0xFF0000 sec=0.5>\n', ...]
    # RGB.command(colCmds[0])
    # if RGB.inSync: RGB.run()
    # RGB.stop_thread()


# ===========================================================
# Routines needed to run as UNIX deamon
# ===========================================================

def delpid():
    ''' clean up pid file '''
    global PID_FILE
    os.remove(PID_FILE)

def pid_kill(pidfile):
    ''' stop this main process '''
    pid = int(os.read(fd, 4096))
    os.lseek(fd, 0, os.SEEK_SET)

    try:
        os.kill(pid, SIGTERM)
        sleep(0.1)
    except OSError as err:
        err = str(err)
        if err.find("No such process") > 0:
            if os.path.exists(pidfile):
                os.remove(pidfile)
        else:
            sys.exit(str(err))

    if pid_is_running():
        sys.exit("Failed to kill %d" % pid)

def pid_is_running(pidfile):
    ''' status of this main process '''
    try:
        fd = os.open(pidfile, os.O_RDONLY)
    except:
        return False
    contents = os.read(fd, 4096)
    os.lseek(fd, 0, os.SEEK_SET)
    if not contents:
        return False
    os.close(fd)

    p = subprocess.Popen(["ps", "-o", "comm", "-p", str(int(contents))],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if stdout == "COMM\n":
        return False
    if 'python' in stdout[stdout.find(b'\n')+1:].decode('utf-8'):
        return int(contents)

def deamon_daemonize(pidfile):
    ''' disconnect from terminal IO and deamonize '''
    global progname
    try:
        pid = os.fork()
        if pid > 0:
            # exit first child
            sys.exit(0)
    except OSError as err:
        sys.stderr.write('fork #1 failed: {0}\n'.format(err))
        sys.exit(1)
    # decouple from parent environment
    os.setsid()
    os.umask(0)
    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent
            sys.exit(0)
    except OSError as err:
        sys.stderr.write('fork #2 failed: {0}\n'.format(err))
        sys.exit(1)
    # write pidfile
    atexit.register(delpid)
    pid = str(os.getpid())
    try:
        fd = os.open(pidfile, os.O_CREAT | os.O_RDWR)
    except IOError as e:
        sys.exit("Process already running? Failed to open pidfile %s: %s" % (progname, str(e)))
    assert not fcntl.flock(fd, fcntl.LOCK_EX)
    os.ftruncate(fd, 0)
    os.write(fd, "%d\n" % int(pid))
    os.fsync(fd)
    # redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    si = open(os.devnull, 'r')
    so = open(os.devnull, 'a+')
    se = open(os.devnull, 'a+')
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

def deamon_detach(pidfile):
    ''' start as deamon '''
    if pidfile == None:
        sys.exit("Cannot start deamon: no pid file defined.")
    # Check for a pidfile to see if the daemon already runs
    if pid_is_running(pidfile):
        sys.exit("Daemon already running.")
    # Start the daemon
    deamon_daemonize(pidfile)

def deamon_stop(pidfile):
    ''' stop the deamon '''
    if pidfile == None:
        sys.exit("Cannot stop deamon: no pid file defined.")
    # Get the pid from the pidfile
    pid = pid_is_running(pidfile)
    if not pid:
        sys.stderr.write("Daemon not running.\n")
        exit(0)

    # Try killing the daemon process
    error = os.kill(pid,SIGTERM)
    if error:
        sys.exit(error)

def deamon_status(pidfile):
    ''' get status of this deamon '''
    global progname
    if pid_is_running(pidfile):
        sys.stderr.write("%s is running.\n" % progname)
    else:
        sys.stderr.write("%s is NOT running.\n" % progname)

############## main process
if __name__ == "__main__":
    import logging
    SIZE = '128x64'
    BUS = 'I2C'
    YB = True  # YellowBlue oled (default not)
    for i in range(len(sys.argv)-1,-1,-1):   # parse the command line arguments
        if sys.argv[i][0] != '-': continue
        if sys.argv[i][0:2] == '-d':         # debug modus
            Conf['debug'] = True
            sys.argv.pop(i)
        elif sys.argv[i][0:2] == '-h':       # help/usage
            print("Adafruit display server arguments: -debug, -help, -port, -size (dflt 128x64 or 128x32), -bus (dflt SPI or I2C), [start|stop|status]")
            print("    RGB led Pi pins -led (dflt false, if pin defined True), -R (red dfld %d), -Y (yellow dfld %d), -B (blue dfld %d). Use GPIO pin numbering scheme." %(Conf['pinR'],Conf['pinG'],Conf['pinB']))
            print("No argument: process is run in foreground and not deamonized.")
            exit(0)
        elif sys.argv[i][0:2] == '-p':       # port to listen to on localhost address
            TCP_PORT = int(sys.argv[i+1])
            sys.argv.pop(i+1); sys.argv.pop(i)
        elif sys.argv[i][0:2] == '-s':       # size of the display 128x32 or 128x64
            SIZE = sys.argv[i+1]
            sys.argv.pop(i+1); sys.argv.pop(i)
        elif sys.argv[i][0:2] == '-b':       # bus type I2C or SPI
            BUS = sys.argv[i+1]
            sys.argv.pop(i+1); sys.argv.pop(i)
        elif sys.argv[i][0:2].lower() == '-y': # YellowBlue oled display
            YB = True
            sys.argv.pop(i)
        elif sys.argv[i][0:4].lower() == '-rgb': # enable RGBled, dflt OFF
            # RGB led handling, donw in a separate thread, only started on first use
            Conf['rgb'] = True
            sys.argv.pop(i)
        elif sys.argv[i][0:2] == '-R': # Red Pi pin nr RGB led
            # if any pin is not defined the led will NOT glow
            Conf['rgb'] = True
            Conf['pinR'] = int(sys.argv[i+1])
            sys.argv.pop(i+1); sys.argv.pop(i)
        elif sys.argv[i][0:2] == '-G': # Green Pi pin nr RGB led
            Conf['rgb'] = True
            Conf['pinG'] = int(sys.argv[i+1])
            sys.argv.pop(i+1); sys.argv.pop(i)
        elif sys.argv[i][0:2] == '-B': # Blue Pi pin nr RGB led
            Conf['rgb'] = True
            Conf['pinB'] = int(sys.argv[i+1])
            sys.argv.pop(i+1); sys.argv.pop(i)

    if Conf['debug']:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    Conf['logging'] = logging

    if len(sys.argv) > 1:                   ###### non interactive modus
        import atexit
        import subprocess
        from os import geteuid, getegid
        from signal import SIGTERM
        import fcntl
        if sys.argv[1] == 'stop':
            deamon_stop(PID_FILE)
            logging.info("Display Server stop")
            exit(0)
        elif sys.argv[1] == 'status':
            deamon_status(PID_FILE)
            exit(0)
        elif sys.argv[1] != 'start':
            sys.exit("Argument %s: unknown process request." % sys.argv[1])
        else:
            deamon_detach(PID_FILE)
        logging.info("Display Server starts up")
    # else:
    #    Conf['debug'] = True

    if (SIZE != '128x32') and (SIZE != '128x64'):
        sys.exit("Display size %s is not supported!" % SIZE)
    if BUS == None:
        print("If oled display is used: Display HW bus needs to be defined: I2C or SPI!")
    elif (BUS != 'SPI') and (BUS != 'I2C'):
        sys.exit("Display bus %s is not supported!" % BUS)
    Conf['display'] = (BUS,SIZE,YB)
    Active = False
    try:
        if not Active:
            DisplayThread(Conf).start()
            Active = True
            time.sleep(1)
            Conf['addLine']("Welcome to MySense", clear=True)
        ClientThread(TCP_IP,TCP_PORT,Conf).listen()
    except:
        Conf['stop'] = True
        logging.exception("Display Server: Unexpected exception")
    finally:
        logging.info("Display/RGBled Server: Shutting down")
        conf['stop'] = True
    logging.info("Display server: All done")
