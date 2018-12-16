#!/usr/bin/python
# -*- coding: utf-8 -*-

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

# $Id: GatewayLogDisplay.py,v 1.15 2018/12/16 16:30:01 teus Exp teus $

# script to rerad gw-forward LoRa logging on stdin
# use oled display to visualize some statistics

# using MyDisplayServer to read display records, reading from port 2017 localhost

import sys
import time
import re               # input parsing via regular expressions
import threading        # display messages via separate thread
import atexit
import socket           # needed for oled display server

# command flags can change this
debug = False
verbose = False         # be more verbose
transparent = False     # output the input lines
log = True              # log to stdout statistics

threads = []
ERRORS = 0

def GetInput(stream):
    global transparent
    line = stream.readline()
    if transparent and line:
        print(line[:-1])
        sys.stdout.flush()
    return line

# send text to SSD1306 display server
def displayMsg(msg):
    global verbose
    host = 'localhost'
    port = 2017
    degree = u'\N{DEGREE SIGN}'
    micro = u'\N{MICRO SIGN}'

    if verbose: print("Display message:", msg)
    if not len(msg): return True
    if not type(msg) is list: msg = msg.split("\n")
    for i in range(len(msg)-1,-1,-1):
        if not len(msg[i]):
            msg.pop(i)
            continue
        msg[i] = format(msg[i])
        if msg[i][-1] == "\n": msg[i] = msg[i][:-1]
        msg[i] = msg[i].replace('oC',degree + 'C')
        #msg[i] = msg[i].replace('ug/m3',micro + 'g/m³')
        msg[i] = msg[i].replace('ug/m3',micro + 'g/m3')
    msg = "\n".join(msg) + "\n"
    if not len(msg): return True
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host,port))
        sock.send(msg)
        sock.close()
        return True
    except:
        #raise IOError("Unable to talk to display service")
        print( msg )
        sys.stdout.flush()
        return False

PolYFwdVersion = ''
ContactSrvr = ''
coordinates = {}
CurDate = 0
Stat = {
    'UpstreamPackages': 0,
    'UpstreamBytes': 0,
    'UpstreamOK': 0,
    'DownstreamPackages': 0,
    'DownstreamBytes': 0,
    'TxErrors': 0,
}
Alive = False
NewRecord = False
# messages array: [ up array, down array ]
# up array: [packages, bytes]
# down array: [packages, bytes, Tx errors]
# compressed to start + 60 minutes max 24 hours, start + 24 hours, prev hour, prev day
# start time
thisHour = [[0,0],[0,0,0]]
prevHour =  [[0,0],[0,0,0]]
thisDay = [[0,0],[0,0,0]]
prevDay = [[0,0],[0,0,0]]
curHour = -1
curDay = -1

DisplayLock = threading.Condition()  # semaphore for display message log
#DisplayLock = threading.Lock()  # semaphore for display message log
NextHour = 0
# combine logging per time hour and per calendar day
def Cleanup(atime):
    global curHour, curDay
    global thisHour, prevHour, thisDay, prevDay
    if datetime.fromtimestamp(atime).hour == curHour: return False
    prevHour = thisHour; thisHour = [[0,0],[0,0,0]]
    if curDay != datetime.fromtimestamp(atime).day: # day has elapsed
        prevDay = thisDay; thisDay = [[0,0],[0,0,0]]
        curDay = datetime.fromtimestamp(atime).day
    curHour = datetime.fromtimestamp(atime).hour
    return True

Srvr = '---'
def Update():
    global debug
    global CurDate, RecCount
    global DisplayLock, NewRecord
    global Stat, Alive, Srvr
    global thisHour, thisDay
    global RecCount, LastTime
    if not CurDate:
        # print("No date record seen")
        return False
    fnd = False
    for item in 'UpstreamPackages', 'UpstreamBytes', 'DownstreamPackages', 'DownstreamBytes', 'TxErrors':
        if (item in Stat.keys()) and Stat[item]: fnd = True
        else: Stat[item] = 0
    if not fnd:
        # print("No updates found")
        return False
    DisplayLock.acquire()
    Cleanup(CurDate)
    thisHour[0][0] += Stat['UpstreamPackages']; thisDay[0][0] += Stat['UpstreamPackages']
    thisHour[0][1] += Stat['UpstreamBytes']; thisDay[0][1] += Stat['UpstreamBytes']
    thisHour[1][0] += Stat['DownstreamPackages']; thisDay[1][0] += Stat['DownstreamPackages']
    thisHour[1][1] += Stat['DownstreamBytes']; thisDay[1][1] += Stat['DownstreamBytes']
    thisHour[1][2] += Stat['TxErrors']; thisDay[1][1] += Stat['TxErrors']
    NewRecord = True
    # print("Update happened")
    try:
      DisplayLock.notify()
    except RuntimeError: pass
    DisplayLock.release()
    RecCount = 0
        
    RecCount += 1
    if debug: Log()
    Stat = {}
    CurDate = 0
    return True

class myThread (threading.Thread):
   def __init__(self, threadID, name, callback):
      threading.Thread.__init__(self)
      self.threadID = threadID
      self.name = name
      self.callback = callback
   def run(self):
      if debug: print "Starting " + self.name
      self.callback()
      # print("%s died" % self.name)

ID = 0
STOP = False
sleepCond = threading.Condition()
# stop the thread
# TO DO: add conditional wake up to client thread
def stop_thread():
    global STOP, DisplayLock
    STOP = True        # ask self threads to stop
    try:
      with DisplayLock: DisplayLock.notify()
      for thrd in threading.enumerate():
        try:
            threading.join()
        except:
            pass
    except: return
    if debug:
        print("Stopped threads.")
    return

# initialize
def start_thread(callback,name='display'):
    global ID, threads, TINTERV
    if STOP:
        return True
    ID = threading.activeCount()+1
    for Trd in threads:
        if Trd.getName() == name:
            if Trd.isAlive():
                return True
            else:
                # maybe we should join first to delete the thread?
                threads.remove(Trd)
    threads.append(myThread(ID, name, callback))
    try:
        atexit.register(stop_thread)
        threads[len(threads)-1].start()
    except:
        return False
    return True

# this runs in a thread
def Log():
    global DisplayLock, NewRecord, STOP
    global thisHour, thisDay, prevHour, prevDay, Srvr, log, Alive
    try:
      while True:
        try:    # catch if caslling thread died
            if STOP: return True
        except: return False
        msg = []
        DisplayLock.acquire()
        with DisplayLock:
            # print("Thread Log wait")
            DisplayLock.wait(30)
        try:
          if not NewRecord:
            DisplayLock.release()
            if debug: return False
            # print("sleep 10 secs")
            time.sleep(20)
            continue
        except: return False
        # print("new record")
        timing = "<clear>%s" % time.strftime("%d %b %H:%M",time.localtime())
        timing.replace(' 0','0')
        timing += '+' if Alive else ' '
        timing += '%s' % Srvr
        msg.append("Up   Hour %d prev %d" % (thisHour[0][0],prevHour[0][0]))
        msg.append("Up   Day  %d prev %d" % (thisDay[0][0],prevDay[0][0]))
        msg.append("Down Hour %d prev %d" % (thisHour[1][0],prevHour[1][0]))
        if thisHour[1][2] or prevHour[1][2]:
            msg[-1] += "|Tx Errors %d prev %d" % (thisHour[1][2],prevHour[1][2])
        msg.append("Down Day  %d prev %d" % (thisDay[1][0],prevDay[1][0]))
        if thisDay[1][2] or prevDay[1][2]:
            msg[-1] += "|Tx Errors %d prev %d" % (thisDay[1][2],prevDay[1][2])
        NewRecord = False
        DisplayLock.release()
        displayMsg(timing + "\n" + "\n".join(msg))
        if log:
            print('; '.join(msg))
            sys.stdout.flush()
        if debug: return True
    except:
      print("Thread Log() error")
      sys.exit(1)

def Info(aline):
    global ContactSrvr, Alive, Srvr, NewRecord, DisplayLock
    if (not ContactSrvr) and (aline.find('Successfully contacted server') >= 0):
        ContactSrvr = aline[aline.find('server')+7:].replace('router.eu.thethings.','TTN ')
        displayMsg("Router %s" % ContactSrvr)
        if ContactSrvr.find('TTN') >= 0: Srvr = 'TTN'
        else: Srvr = ContactSrvr[:3]
    if aline.find('PUSH_ACK received') > 0:
        Alive = True
    if aline.find('tarting the concentr') >= 0:
        DisplayLock.acquire()
	NewRecord = True
        DisplayLock.notify()
        DisplayLock.release()
    return

UpstreamPattern = re.compile('.*RF\s+pack.*forwarded:\s+(?P<nr>[0-9]+)\s+.(?P<bytes>[0-9]+).*')
UpstreamOK = re.compile('.*PUSH.*acknowledged:\'s+(?P<ok>[0-9\.]+).*')
def CollectUpstream(stream):
    global Stat
    aline = ''
    while True:
        aline = GetInput(stream)
        if not aline: break
        if not aline[0] == '#': break
        if aline[0:3] == '###': break
        record = None
        if aline.find('forwarded:') > 0: record = UpstreamPattern.match(aline)
        try:
          if record:
            record = record.groupdict()
            Stat['UpstreamPackages'] = int(record.pop('nr'))
            Stat['UpstreamBytes'] = int(record.pop('bytes'))
            record = None
          elif aline.find('acknowledged') > 0: record = UpstreamOK.match(aline)
          if record:
            record = record.groupdict()
            Stat['UpstreamOK'] = int(record.pop('ok'))
        except: pass
    return aline

DownstreamPattern = re.compile('.*RF\s.*sent to concentrator:\s+(?P<nr>[0-9]+)\s+.(?P<bytes>[0-9]+).*')
def CollectDownstream(stream):
    global Stat
    while True:
        aline = GetInput(stream)
        if not aline: break
        if not aline[0] == '#': break
        if aline[0:3] == '###': break
        try:
          if aline.find('RF records:') >= 0:
            Stat['TxErrors'] = int(aline[aline.find(': ')+2:-1])
            continue
          record = None
          if aline.find('RF packets') > 0: record = DownstreamPattern.match(aline)
          if record:
            record = record.groupdict()
            Stat['DownstreamPackages'] = int(record.pop('nr'))
            Stat['DownstreamBytes'] = int(record.pop('bytes'))
        except: pass
    return aline

GPSpattern = re.compile('.*latitude (?P<latitude>[0-9\.]+), longitude (?P<longitude>[0-9\.]+), altitude (?P<altitude>[0-9\.]+).*')
def CollectGPS(stream):
    global GPSpattern
    global coordinates

    aline = ''
    while True:
        aline = GetInput(stream)
        if not aline: break
        if not aline[0] == '#': break
        if aline[0:3] == '###': break
        coords = GPSpattern.match(aline)
        if coords:
            coords = coords.groupdict()
            coordinates = {}
            for item in ['latitude','longitude','altitude']:
                try:
                    coordinates[item] = coords.pop(item)
                except: pass
            aline = GetInput(stream)
            break
    return aline
    
from datetime import datetime
from dateutil.parser import parse
def SetDate(aline):
    global CurDate
    try:
        CurDate = datetime.strptime(aline, '##### %Y-%m-%d %H:%M:%S %Z #####\n')
        CurDate = int(time.mktime(CurDate.timetuple()))
    except: pass

def help():
    print("""
Filter ttn-forwarder output and show the exstracted statistics
on an oled display via the MySense display service.
Arguments:
  -v be more verbose
  -d debug messages
  -t be also tranparent: input lines are transferred to output as well
  -q do not log hourly and dayly package statistics to std out (dflt log)
  -h this help message
""")
    sys.exit(0)

input = sys.stdin
for i in range(len(sys.argv)-1,0,-1):
    if sys.argv[i][0] != '-':
        input = open(sys.argv[i],'r')
    if sys.argv[i][1] == 'v': verbose = True
    if sys.argv[i][1] == 'd': debug = True
    if sys.argv[i][1] == 't': transparent = True
    if sys.argv[i][1] == 'q': log = False
    if sys.argv[i][1] == 'h': help()
    del sys.argv[i]
if debug or verbose: log = True

line = ''
if not debug: start_thread(Log)

LastTime = time.time()
while True:
    # give display also a chance to proceed, throddle a bit
    line = GetInput(input)
    if not line: break
    line.strip()
    if line.find('INFO: ') >= 0:
        # INFO record
        Info(line)
        continue
    if line.find('ERROR: ') >= 0:
        if line.find('failed to start') >= 0:
            displayMsg("FATAL FORWARDER\nconcentrator start failed")
            sys.exit(1)
        else:
            msg = line
        if not ERRORS: msg = '<clear>' + msg
        ERRORS += 1
        displayMsg(msg)
    elif line.find('*** Poly Packet') >=0:
        line =GetInput(input)
        if line and (not PolYFwdVersion) and (line.find('Version: ') >= 0):
            PolYFwdVersion = line[line.find('Version: ')+9:-1]
            displayMsg("<clear>LoRa Fwd V%s" % PolYFwdVersion)
        continue
    if line.find('### [UPSTREAM') >= 0:
        line = CollectUpstream(input)
        if not line: break
    if line.find('### [DOWNSTREAM') >= 0:
        line = CollectDownstream(input)
        if not line: break
    if line.find('### [GPS') >= 0:
        line = CollectGPS(input)
        if not line: break
    if line.find('##### 20') >= 0:
        SetDate(line)
        if (time.time() - LastTime) < 0.4:
            time.sleep(0.4)
        LastTime = time.time()
        continue
    if line.find('## END ##') >= 0:
        Update()
        Alive = False
        continue
    # if len(line) == 1: Alive = False
    # skip this line

stop_thread()           
