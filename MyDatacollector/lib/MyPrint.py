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

# $Id: MyPrint.py,v 1.7 2021/10/24 15:30:46 teus Exp teus $

# print lines to /dev/stdout, stderr or FiFo file
# thread buffer (max MAX).
""" Threading to allow prints to fifo file or otherwise
"""
__version__ = "0." + "$Revision: 1.7 $"[11:-2]

import threading
#import atexit
import logging
logging.basicConfig(level=logging.DEBUG,
                    format='(%(threadName)-9s) %(message)s',)
from time import time, sleep
import sys
from os import path

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
        self.color = False          # use colorize on terminal output
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
        self.inits['MAX'] = 100      # max length buffer of output lines
        self.inits['DEBUG'] = False
        self.inits['date'] = False  # prepend datetime string to each output line
        self.inits['strftime'] = "%Y-%m-%d %-H:%-M:%-S" # default date format
        for key in args.keys(): self.inits[key] = args[key]
        self.condition = threading.Condition()
        self.bufferLock = threading.Lock()
        self.STOP = False           # stop thread
        self.RUNNING = False        # print thread is running, may wait on pipe listener
        self.buffer = []            # fifo buffer limited size
        # atexit.register(self.stop)  # stop clients

    # output channel thread, reads from buffer
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
          while not self.STOP:
            with self.condition:
              if self.inits['DEBUG']: logging.debug('Printer waiting ...')
              self.condition.wait(20)
              while len(self.buffer):
                line = ''
                with self.bufferLock:
                  timing, line, color = self.buffer.pop(0)
                try:
                  if line:
                    if self.inits['date']:
                        timing = datetime.datetime.fromtimestamp(timing).strftime(self.inits['strftime']) + '\t'
                    else: timing = ''
                    if (color != None) and self.color:
                        try: line = self.colorize(line, ansi=color, fd=self.fd)
                        except: pass
                    # print >>self.output, timing + line
                    self.output.write(timing + line + "\n")
                    self.output.flush()
                except Exception as e:
                    sys.stderr.write('Error: %s\n' % str(e))
                    # logging.debug('Failed to print on output channel')
                if self.inits['DEBUG']: logging.debug('Printed one line')
          if self.inits['DEBUG']: logging.debug('Consumer FINISHED')
        except: pass
        try:
          if self.fifo:
            sleep(0.1); self.output = None; os.remove(self.fifo)
        except: pass
    
    def MyPrint(self,line,color=None):
        if self.inits['DEBUG']: logging.debug('Producer thread started ...')
        if not self.RUNNING:
            threading.Thread(name='printer', target=self.printer, args=()).start()
            sleep(1)
        with self.condition:
            if self.inits['DEBUG']: logging.debug('Making resource available')
            with self.bufferLock:
                if len(self.buffer) == self.inits['MAX']: self.buffer.pop(0)
                self.buffer.append((time(),line,color))
            if self.inits['DEBUG']: logging.debug('Notifying to all consumers')
            self.condition.notifyAll()
        sleep(0.05)

    def stop(self):
        self.STOP = True
        with self.condition:
          self.condition.notifyAll()
        sleep(2)
        
if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1].find('fifo=') >= 0:
            Print = MyPrint(output=sys.argv[1][5:], fifo=True, date=True)
        else: Print = MyPrint(output=sys.argv[1])
    else:
        Print = MyPrint(output='/dev/stderr', color=True, DEBUG=False, date=True)
    for i in range(100):
        Print.MyPrint('Line %d' % i, color=i)
        if (i%3) == 0: sleep(2)
    Print.stop()
