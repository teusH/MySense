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

# $Id: MyThreading.py,v 2.5 2017/03/27 19:30:29 teus Exp teus $

# the values provided are rounded (3 decimals) of values in the
# thread buffer (max BUFSIZE). INTERVAL and the thread interval (TINTERV)
# are defining the window in the buffer.
""" Threading to allow sensor readings independent from MySense main
    routine
    Has internal read interval and MySense input read interval.
"""
    
import threading
import atexit

class MyThreading:
    from time import time,sleep

    __version__ = "0." + "$Revision: 2.5 $"[11:-2]
    __license__ = 'GPLV4'

    STOP = False    # stop all threads
    threadLock = threading.Lock() # lock to be used for average of values in buffer
    threads = []    # list of threads

    
    # initialize variables for this thread instance
    def __init__(self, **args):
        if not 'callback' in args.keys():
            raise RuntimeError("Need a callback routine identifier")
        inits = {}                 # defaults
        inits['bufsize'] = 80/5    # internal buffer (window) of values
        inits['interval'] = 5      # internal max secs interval for new values
        inits['name'] = 'MySensor' # sensor name for this thread
        inits['sync'] = False      # in debug mode no threading
        inits['DEBUG'] = False     # be more versatile
        inits['conf'] = None       # dict with Conf keys e.g. pin/port for Add method
        for key in args.keys():
            inits[key] = args[key]
        self.BUFSIZE = inits['bufsize']   # internal buffer (window) of values
        self.TINTERV = inits['interval']  # internal max interval for new values
        self.name = inits['name']         # sensor name for this thread
        self.SYNC = inits['sync']         # in debug mode no threading
        self.DEBUG = inits['DEBUG']       # debug modus
        self.callback = args['callback']  # routine to add sensor value
	self.conf = inits['conf']         # arg valuees for callback

        self.BufAvg = {}      # record avg of values in buffer (dynamic window)
        self.Buffer = []      # time ordered list of measurements of sensor
        self.INTERVAL = self.TINTERV * self.BUFSIZE # max window buffer size
        # conditional wait (avoid sleep() in client thread)
        self.sleepCond = threading.Condition()

    # activated by thread start()
    # note subthreads will not catch Keyboard Interrupt <cntrl>c
    # kill it by <cntrl>z and kill %1   
    class ThisThread(threading.Thread):   # the real run part of the thread
        def __init__(self,threading,bufCollect,threadID, name, callback,conf):
            threading.Thread.__init__(self)
            self.threadID = threadID
            self.name = name
            self.callback = callback
            self.bufCollect = bufCollect
            self.conf = conf
        def run(self):
            self.bufCollect(self.callback,self.conf)
            #print("Thread %s stopped." % self.name)
            return
        
    # maintain Buffer of measurements
    def bufCleanup(self):
        if len(self.Buffer) >= self.BUFSIZE:
            self.Buffer.pop(0)
        if not len(self.Buffer):
            return
        dels = [];      # collect indexes of buffered items to be deleted
        last = self.time() - self.INTERVAL - self.TINTERV
        if len(self.BufAvg):
            last = self.BufAvg['time'] -self.TINTERV
        for i in range(0,len(self.Buffer)):
            if self.Buffer[i]["time"] <= last:
                dels.append(i)
        if len(dels):
            dels.reverse()
            for i in dels:
                self.Buffer.pop(i)
        if len(self.Buffer)-1 >= self.BUFSIZE:
            self,Buffer.pop(0)
        if (not len(self.Buffer)) and len(self.BufAvg):
            avg = {}
            for key in self.BufAvg.keys():
                if key == 'time': avg[key] = int(self.time())
                else: avg[key] = None
            with self.threadLock: self.BufAvg = avg
            
    def bufCollect(self,callback,conf):
        self.STOP = False
        if self.SYNC:
            #import random ; cnt = random.randint(1,5)
            cnt = 3
        if self.DEBUG:
            print("Starting sensor %s collect." % self.name)
        while not self.STOP:
            lastT = self.time()
            #self.bufAdd(callback(conf))
            rec = callback(conf)
            if not len(rec): continue
            if self.DEBUG:
                print("Sensor %s got input: " % self.name, rec)
            self.bufCleanup()
            self.Buffer.append(rec)

            avg = {}
            for key in self.Buffer[0]:
                if key == 'time': continue
                cnt = 0 ; total = 0
                for i in range(0,len(self.Buffer)):
                    if self.Buffer[i][key] == None: continue
                    if not len(avg):
                        avg = { 'time': self.Buffer[i]['time'] }
                    total += self.Buffer[i][key] ; cnt += 1
                    last = self.Buffer[i]['time']
                if cnt:
                    avg[key] = round(total/cnt,3)
            if len(avg):
                avg['time'] = (avg['time']+last)/2        # timestamp in the middle
            with self.threadLock: self.BufAvg = avg
            lastT = self.TINTERV - (self.time()-lastT)
            if lastT > 0:
                # TO DO: change this to conditional wait
                # self.sleep(lastT)
                with self.sleepCond: self.sleepCond.wait(lastT)
            if self.SYNC:
                cnt -= 1
                if cnt <= 0: self.STOP = True
        return

    # get the collected record (average in window of bufer size
    # or wait max 3 X interval for a none empty record
    def getRecord(self):
       for cnt in range(0,3):
           mean = {}
           if self.SYNC: self.bufCollect(self.callback,self.conf) # sync waiting for value
           # else it is done by the sensor thread with interval timings
           with self.threadLock:
               if len(self.BufAvg):
                   mean = self.BufAvg
           if len(mean):
               return mean
           self.sleep(self.TINTERV) # if empty wait and try again
       raise IOError("No input success while waiting 3 X %d seconds" % self.TINTERV)
       return {}
    
    # stop the thread
    # TO DO: add conditional wake up to client thread
    def stop_thread(self):
        self.STOP = True        # ask self threads to stop
        #self.sleepCond.acquire()
        with self.sleepCond: self.sleepCond.notify()
        #self.sleepCond.release()
        for thrd in threading.enumerate():
            try:
                threading.join()
            except:
                pass
        if self.DEBUG:
            print("Stopped threads.")
        return

    # initialize
    def start_thread(self):
        if self.STOP:
            return True
        ID = threading.activeCount()+1
        for Trd in self.threads:
            if Trd.getName() == self.name:
                if Trd.isAlive():
                    return True
                else:
                    # maybe we should join first to delete the thread?
                    self.threads.remove(Trd)
        self.threads.append(self.ThisThread(threading,self.bufCollect,ID, self.name, self.callback,self.conf))
        if not self.SYNC:
            try:
                atexit.register(self.stop_thread)
                self.threads[len(self.threads)-1].start()
                self.sleep(self.TINTERV*2)      # allow some data to come in
            except:
                return False
        return True
        
    def bufAdd(self,rec):
        if self.DEBUG:
            print("Sensor %s got input: " % self.name, rec)
        self.Buffer.append(rec)

