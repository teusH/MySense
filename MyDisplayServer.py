#!/usr/bin/env python3
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

# $Id: MyDisplayServer.py,v 1.1 2017/06/16 19:58:16 teus Exp teus $

# script will run standalone, collects text lines from sockets streams and
# displays the scrolled lines on an Adafruit display

# display is an OLED SSD1306 little B/W screen
# needs MySSD1306_display.py module, which is based on Adafruit library software

import socket 
import threading
from SocketServer import ThreadingMixIn 
import time
import sys
import os
 
# main thread starts display thread and maintains 5 socket readers on localhost/2017
# shared variables between the threads
Conf = {
    'stop': False,                # stop threads
    'lines': [],                  # lines to show on display
    'display': ('SPI','128x64'),  # Adafruit display: SPI or I2C 32 or 64 pixels height
    'addLine': None,              # ref to addLine display routine
    'threads': [],                 # threads alive deprecated
    'lock': threading.Lock(),     # lock between threads
    'debug': False,               # debug modus, no multi threading for sockets
    }
TCP_IP = 'localhost'
TCP_PORT = 2017 
FOREGRND = False
progname = "MyDisplayServer"
PID_FILE = '/var/tmp/' + progname + '.pid'

# Multithreaded Python server : TCP Server Socket Thread Pool

class DisplayThread(object):
    def __init__(self,conf):
        self.SSD1306 = __import__("MySSD1306_display")
        self.logger = conf['logging']
        threading.__init__("display")
        self.conf = conf
        if 'lock' in conf.keys(): self.lock = conf['lock']
        else: self.lock = threading.Lock()
        self.type = conf['display'][0]
        self.size = conf['display'][1]
        self.logger.debug("[+]Adafruit display started")
        try:
            self.SSD1306.InitDisplay(conf['display'][0],conf['display'][1])
            self.conf['addLine'] = self.SSD1306.addLine
        except:
            self.logger.fatal("Display error for SSD1306 type %s size %s." %(conf['display'][0],conf['display'][1]))
            raise ValueError("Unknow SSD1306 type/size")

    def start(self):
        threading.Thread(target = self.SSD1306.Show,args = (self.lock,self.conf)).start()

class ClientThread(object):
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

    def listen(self):
        self.sock.listen(5)
        while True:
            client, address = self.sock.accept()
            if self.debug:
                self.listenToClient(client,address)
            else:
                threading.Thread(target = self.listenToClient,args = (client,address)).start()

    def listenToClient(self, client, address):
        if self.debug:
            self.conf['addLine']("New client accepted")
        client.settimeout(60)
        while not self.conf['stop']:
            try:
                data = self.linesplit(client) # generator object
                if data:
                    for txt in data:
                        txt = txt[:-1]
                        self.logger.debug("Received a line: %s" % txt)
                        if self.conf['addLine'] != None:
                            self.conf['addLine'](txt)
                        else:
                            raise NameError("Unable to use addLine routine of Display")
                    client.close()
                    return True
                else:
                    self.logger.debug("Display server close this connection.")
                    
            except:
                client.close()
                return False
 
    def linesplit(self,client):                    # linesplit is a line generator
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
# Routines needed to run as UNIX deamon
# ===========================================================

def delpid():
    global PID_FILE
    os.remove(PID_FILE)

def pid_kill(pidfile):
    pid = int(os.read(fd, 4096))
    os.lseek(fd, 0, os.SEEK_SET)

    try:
        os.kill(pid, signal.SIGTERM)
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
    if 'python' in stdout[stdout.find("\n")+1:]:
        return int(contents)

def deamon_daemonize(pidfile):
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
    if pidfile == None:
        sys.exit("Cannot start deamon: no pid file defined.")
    # Check for a pidfile to see if the daemon already runs
    if pid_is_running(pidfile):
        sys.exit("Daemon already running.")
    # Start the daemon
    deamon_daemonize(pidfile)

def deamon_stop(pidfile):
    if pidfile == None:
        sys.exit("Cannot stop deamon: no pid file defined.")
    # Get the pid from the pidfile
    pid = pid_is_running(pidfile)
    if not pid:
        sys.stderr.write("Daemon not running.\n")
        exit(0)

    # Try killing the daemon process
    error = os.kill(pid,signal.SIGTERM)
    if error:
        sys.exit(error)

def deamon_status(pidfile):
    global progname
    if pid_is_running(pidfile):
        sys.stderr.write("%s is running.\n" % progname)
    else:
        sys.stderr.write("%s is NOT running.\n" % progname)

if __name__ == "__main__":
    import logging
    for i in range(len(sys.argv)-1,-1,-1):
        if sys.argv[i][0] != '-': continue
        if sys.argv[i][0:1] == '-d':
            Conf['debug'] = True
            pop(i)
        elif sys.argv[i][0:1] == '-h':
            print("Adafruit display server arguments: -debug, -help, -port, [start|stop|status]")
            print("No argument: process is run in foreground and not deamonized.")
            exit(0)
        elif sys.argv[i][0:1] == '-p':
            TCP_PORT = int(sys.argv[i+1])
            pop(i+1); pop(i)
    # Conf['debug'] = True
    if Conf['debug']:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    logging.info("Display Server starts up")
    Conf['logging'] = logging
    if len(sys.argv) > 1:
        import atexit
        import subprocess
        from os import geteuid, getegid
        from signal import SIGTERM
        import fcntl
        if sys.argv[1] == 'stop':
            deamon_stop(PID_FILE)
            exit(0)
        elif sys.argv[1] == 'status':
            deamon_status(PID_FILE)
            exit(0)
        elif sys.argv[1] != 'start':
            print("Argument %s: unknown process request.")
            exit(1)
        else:
            deamon_detach(PID_FILE)
    Active = False
    try:
        if not Active:
            DisplayThread(Conf).start()
            Active = True
            time.sleep(1)
            Conf['addLine']("Welcome to MySense")
        ClientThread(TCP_IP,TCP_PORT,Conf).listen()
    except:
        Conf['stop'] = True
        logging.exception("Display Server: Unexpected exception")
    finally:
        logging.info("Display Server: Shutting down")
        conf['stop'] = True
    logging.info("Display server: All done")
