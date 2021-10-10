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

# $Id: MyThreading.py,v 1.1 2021/08/26 15:48:06 teus Exp teus $

# the values provided are rounded (3 decimals) of values in the
# thread buffer (max BUFSIZE). INTERVAL and the thread interval (TINTERV)
# are defining the window in the buffer.
""" Threading to allow sensor readings independent from MySense main
    routine
    Has internal read interval and MySense input read interval.
"""

__modulename__='$RCSfile: MyThreading.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.1 $"[11:-2]
import inspect
def WHERE(fie=False):
   global __modulename__, __version__
   if fie:
     try:
       return "%s V%s/%s" % (__modulename__ ,__version__,inspect.stack()[1][3])
     except: pass
   return "%s V%s" % (__modulename__ ,__version__)

import threading
import atexit

class MyThreading:
    __version__ = "0." + "$Revision: 1.1 $"[11:-2]
    __license__ = 'GPLV4'

    STOP = False    # stop all threads
    threadLock = threading.Lock() # lock to be used for average of values in buffer
    threads = []    # list of threads

    
    # initialize variables for this thread instance
    def __init__(self, **args):
        if not 'callback' in args.keys():
            raise RuntimeError("Need a callback routine identifier")
        inits = {}                 # defaults
        inits['name'] = 'MyTTNprint' # sensor name for this thread
        inits['DEBUG'] = False     # be more versatile
        for key in args.keys():
            inits[key] = args[key]
        self.name = inits['name']         # sensor name for this thread
        self.DEBUG = inits['DEBUG']       # debug modus

        self.Buffer = []      # time ordered list of measurements of sensor
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
        def run(self):
            self.bufCollect(self.callback,self.conf)
            #print("Thread %s stopped." % self.name)
            return
        
    def bufCollect(self,callback,conf):
        self.STOP = False
        if self.DEBUG:
            print("Starting sensor %s collect." % self.name)
        while not self.STOP:
            lastT = self.time()
            #self.bufAdd(callback(conf))
                with self.sleepCond: self.sleepCond.wait(lastT)
            if self.SYNC:
                cnt -= 1
                if cnt <= 0: self.STOP = True
        return

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

