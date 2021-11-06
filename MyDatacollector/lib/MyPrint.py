#
# Copyright: Teus Hagen, 2017, RPL-1.5
# Open Source Initiative  https://opensource.org/licenses/RPL-1.5
#
#   Unless explicitly acquired and licensed from Licensor under another
#   license, the contents of this file are subject to the Reciprocal Public
#   License ("RPL") Version 1.5, or subsequent versions as allowed by the RPL,
#   and You may not copy or use this file in either source code or executable
#   form, except in compliance with the terms and conditions of the RPL.
#
#   All software distributed under the RPL is provided strictly on an "AS
#   IS" basis, WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESS OR IMPLIED, AND
#   LICENSOR HEREBY DISCLAIMS ALL SUCH WARRANTIES, INCLUDING WITHOUT
#   LIMITATION, ANY WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
#   PURPOSE, QUIET ENJOYMENT, OR NON-INFRINGEMENT. See the RPL for specific
#   language governing rights and limitations under the RPL.
__license__ = 'RPL-1.5'

# $Id: MyPrint.py,v 1.13 2021/11/06 14:55:05 teus Exp teus $

# print lines to /dev/stdout, stderr or FiFo file
""" Threading to allow prints to fifo file or otherwise
"""
__version__ = "0." + "$Revision: 1.13 $"[11:-2]

import threading

import logging
logging.basicConfig(level=logging.DEBUG,
                    format='(%(threadName)-9s) %(message)s',)
from time import time, sleep
import sys
from os import path
if sys.version[0] == '2':
    import Queue
else:
    import queue as Queue

# some usefull colors:
# DFLT   0 grayish
# RED    1
# GREEN  2
# YELLOW 3
# PURPLE 5
# GRAY   8 dark
# BLACK  16
# BLEW   21
# BROWN  52

class MyPrint:
    # initialize variables for this thread instance
    def __init__(self, output=sys.stderr, color=False, fifo=False, **args):
        self.fifo = fifo
        self.color = color          # use colorize on terminal output
        self.colorize = None
        self.fd = None
        if type(output) is str:
          if not fifo: # output to stderr/stdout or file
            try:
              self.output = open(output,'w')
            except Exception as e:
              sys.stderr.write('Unable to write to %s.\n' % output)
              exit(1)
          else:
            self.fifo = output
            self.output = None
            if not path.exists(self.fifo):
              try:
                from os import mkfifo
                mkfifo(self.fifo) # will block if no reader
              except Exception as e:
                print("MK fifo error: %s." % str(e))
                exit(1)
        else:
            self.output = output    # file handler
        if self.output.isatty(): self.color = color
        if self.color:
            try:
              from xtermcolor import colorize
              self.colorize = colorize
            except: self.color = False
            if output == sys.stderr: self.fd = 2
            else: self.fd = 1
        self.inits = {}
        self.queue = Queue.Queue(maxsize=100)  # FiFo queue
        self.timeout = 0.1                     # timeout to retry queue
        self.inits['DEBUG'] = False
        self.inits['date'] = False  # prepend datetime string to each output line
        self.inits['strftime'] = "%Y-%m-%d %-H:%M:%S" # default date format
        for key in args.keys(): self.inits[key] = args[key]
        self.STOP = False           # stop thread
        self.RUNNING = False        # print thread is running, may wait on pipe listener

    # output channel thread, reads from Queue
    def printer(self):
        if self.inits['DEBUG']: logging.debug('output channel thread thread started ...')
        if self.inits['date']: import datetime
        self.RUNNING = True
        if self.fifo: # named pipe output
          if self.inits['DEBUG']: logging.debug('Wait for named pipe listener.')
          try: # may initially block here waiting on listener
            self.output = open(self.fifo,'w')
          except: 
            print('Error cannot create fifo %s file.' % self.fifo)
            exit(1)
          if self.inits['DEBUG']: logging.debug('Named pipe listener is active.')
        try:
          while not self.STOP:   # stop thread
            try:
              timing, line, color = self.queue.get(timeout=self.timeout)
            except: continue
            if line == None: self.STOP = True
            if line:
              if self.inits['date']:
                timing = datetime.datetime.fromtimestamp(timing).strftime(self.inits['strftime']) + '\t'
              else: timing = ''
              if (color != None) and self.color:
                try: line = self.colorize(line, ansi=color, fd=self.fd)
                except: pass
              self.output.write(timing + line + "\n")
              self.output.flush()
              self.queue.task_done()
            if self.inits['DEBUG']: logging.debug('Printed one line')
        except Exception as e:
          sys.stderr.write('Exception error MyPrint: %s\n' % str(e))
          # logging.debug('Failed to print on output channel')
          if self.fifo:
            sleep(0.1); self.output = None; os.remove(self.fifo)
          if self.inits['DEBUG']: logging.debug('printout thread FINISHED')
        self.queue.task_done()
    
    def MyPrint(self,line,color=None):
        if self.inits['DEBUG']: logging.debug('Producer thread started ...')
        if not self.RUNNING:
            threading.Thread(name='printer', target=self.printer, args=()).start()
            sleep(0.1)
        try:
          self.queue.put((time(),line,color), timeout=(self.timeout+1))
          #sleep(self.timeout)  # give thread time to do something
        except self.queue.FULL: return False # skip message
        return True

    def stop(self):
        cnt = 0
        while not self.queue.empty() and cnt < 10: # empty Queue
           sleep(self.timeout)
           cnt += 1
        self.STOP = True
        self.MyPrint(None) # force stop
        self.queue.join()
        sleep(self.timeout)
        
if __name__ == '__main__':
    import sys
    from random import randrange
    if len(sys.argv) > 1:
        if sys.argv[1].find('fifo=') >= 0:
            Print = MyPrint(output=sys.argv[1][5:], fifo=True, date=True)
        else: Print = MyPrint(output=sys.argv[1])
    else:
        Print = MyPrint(output='/dev/stderr', color=True, DEBUG=False, date=True)
    for i in range(100):
        Print.MyPrint('Color nr %d of 100' % i, color=i)
        if (i%3) == 0: sleep(randrange(20)/10.0)
    Print.stop()
