#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
# 
# Copyright (C) 2017, Behoud de Parel, Teus Hagen, the Netherlands
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

# $Id: MyLogger.py,v 3.10 2021/11/03 16:38:29 teus Exp teus $

# TO DO:

""" Push logging to the external world.
"""
modulename='$RCSfile: MyLogger.py,v $'[10:-4]
__version__ = "0." + "$Revision: 3.10 $"[11:-2]

import sys
from time import sleep

# configurable options
__options__ = ['level','file','output','date','print']

def stop():
    global Conf
    try:
      for stop in Conf['shutdown']:
        try: stop()
        except: pass
    except: pass

Conf = {
    'level': 'INFO',
    'istty': None, # should go away
    'file' : sys.stderr,
    'fd': None,
    'output': True,
    'date': True, # prepend with date
    'print': True, # color printing
    'shutdown': [],
    'STOP': stop
}
# ===========================================================================
# logging
# ===========================================================================

# logging levels
FATAL    = 70
CRITICAL = 60
#ERROR    = 50
#WARNING  = 40
#ATTENT   = 30
#INFO     = 20
#DEBUG    = 10
#NOTSET   = 0

log_levels = ['NOTSET','DEBUG','INFO','ATTENT','WARNING','ERROR','CRITICAL','FATAL']
log_colors = [16,6,21,4,3,5,9,1]
# TO DO: install remote logging
def log(name,level,message): # logging to console or log file
    global Conf
    # seems python3 logging module does not allow logging on stdout or stderr
    if not Conf['output']: return False
    def IsTTY():
        global Conf
        if Conf['istty'] != None: return Conf['istty']
        try:
            # log messages go to tty
            Conf['istty'] = False
            if Conf['file'] == None: Conf['istty'] = True
            for _ in ['stdout','stderr','tty']:
              if str(Conf['file']).find(_) > 0: Conf['istty'] = True
        except:
            Conf['istty'] = False
        return Conf['istty']
                
    def printc(text, color=0): # default color ansi black
        global Conf
        if type(Conf['print']) is bool and Conf['print']:
          try: from lib.MyPrint import MyPrint as MyPrint
          except: from MyPrint import MyPrint
          Conf['print'] = MyPrint(color=IsTTY())
          try: Conf['shutdown'].append(Conf['print'].stop)
          except: pass
        try:
          if Conf['print']:
            Conf['print'].MyPrint(text, color=color)
            return True
        except: pass
        try: sys.stderr.write(text+'\n')
        except: pass

    if type(level) is str:
        level = log_levels.index(level.upper())*10
    try:
        if int(level /10) < log_levels.index(Conf['level'].upper()):
            return False
    except:
        pass
    name = name.replace('.py','')
    if name != 'MySense': name = 'MySense ' + name.replace('My','')
    if Conf['fd'] == None and Conf['print'] == None:
        # this part needs some work
        try:
            import logging, logging.handlers
            Conf['fd'] = logging.getLogger("IoS-sensor_log")
            try:
              if Conf['stop'] == None: Conf['stop'] = [logging.shutdown]
              else: Conf['stop'].append(logging.shutdown)
            except: pass
        except:
            sys.exit("FATAL error while initiating logging. IoS program Aborted.")
        try:
            # map logger levels: NOTSET,DEBUG,INFO,ATTENT,WARNING,ERROR,CRITICAL,FATAL
            # to syslog levels:  NOTSET,DEBUG,INFO,       WARNING,ERROR,CRITICAL
            level = log_levels.index(Conf['level'])*10
            if level == 30: level -= 5
            elif level > 30: level -= 10
            Conf['fd'].setLevel(level)
        except:
            Conf['fd'].setLevel(logging.WARNING)
        if Conf['date']:
            log_frmt = logging.Formatter("%(asctime)s IoS %(levelname)s: %(message)s", datefmt='%Y/%m/%d %H:%M:%S')
        else:
            log_frmt = logging.Formatter("IoS log %(levelname)s: %(message)s")
        if type(Conf['file']) is str:
          if Conf['file'].lower() == 'syslog':
            log_handle = logging.handlers.SysLogHandler(address = '/dev/log')
            log_handle.setFormatter(log_frmt)
          else:
            log_handle = logging.FileHandler(Conf['file'])
            log_handle.setFormatter(log_frmt)
        elif Conf['file']:
            log_handle = Conf['file']
            # log_handle = logging.StreamHandler(Conf['file'])
            # log_handle.setFormatter(log_frmt)
        Conf['fd'].addHandler(log_handle)
    elif type(Conf['print']) is bool:
      if (not 'file' in Conf.keys()) or not Conf['file']:
        Conf['file'] = sys.stderr
      try:
        try: from lib.MyPrint import MyPrint
        except: from MyPrint import MyPrint
        fifo = False
        if (type(Conf['file']) is str) and Conf['file'].find('fifo=') == 0:
            fifo = True; Conf['file'] = Conf['file'][5:]
        Conf['print'] = MyPrint(output=Conf['file'], color=IsTTY(), fifo=fifo, date=Conf['date'])
        Conf['shutdown'].append(Conf['print'].stop)
      except Exception as e:
        sys.stderr.write("Exception with loading module print color: %s\n" % str(e))
        Conf['print'] = None

    rts = False
    if Conf['fd']:
        try:
            rts = Conf['fd'].log(level,name + ': ' + message)
        except:
            sys.exit("Unable to log to %s. Program aborted." % Conf["log"]['file'])
        if level == FATAL:
            rts = Conf['fd'].log(CRITICAL,"Program is aborted.")
            # to do: handle stop multithreadings
            stop()  # stop on lower levels
            sys.exit("FATAL error. Program Aborted.")
    else:
        printc("%s %s: %s" % (name,log_levels[int(level/10)%len(log_levels)], message),log_colors[int(level/10)%len(log_levels)])
        rts = True
    sleep(0.2)  # give room to print thread
    return rts
    
def show_error():               # print sys error
    return log('ERROR',"Failure type: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )

if __name__ == '__main__':
    Conf['level'] = 'INFO'                 # default log level
    Conf['file'] = sys.stderr              # default
    Conf['print'] = True                   # default colored print on stderr

    if len(sys.argv) > 1:
      for i in range(1,len(sys.argv)):
        if sys.argv[i].find('stderr') >= 0:
          Conf['file'] = sys.stderr.write
          Conf['print'] = True
          print("Using log service via standard error, colored output.")
        elif sys.argv[i].find('syslog') >= 0:
          Conf['file'] = 'syslog'
          Conf['print'] = None  # required for system logging
          print("Using log service via system logging service syslog.")
        elif sys.argv[i].upper() in log_levels:
          Conf['level'] = sys.argv[i].upper()
          print("Using minimal log level '%s'." % Conf['level'])
        else:
          Conf['file'] = sys.argv[i]
          Conf['print'] = False
          print("Using log service via log (use of named pipe?: fifo='file_name') file '%s'." % sys.argv[i])
    else:
      Conf['level'] = 'DEBUG'                # show everything
      Conf['file'] = sys.stderr              # default
      Conf['print'] = True                   # colored print on stderr
      print("Using log service via standard error")
    for one in log_levels[1:]:  # skip UNSET level
      print("Try to log messager on level %s (minimal level %s)" % (one,Conf['level']))
      try:
        rts = log(sys.argv[0],one,"This is level %s as logger test" % one)
        if rts: print("Logged")
        elif rts == None: print("Logging undefined (syslog?)")
        else: print("Not logged")
      except Exception as e: print("Level %s log failed with '%s'" % (one, str(e)))
    stop()
