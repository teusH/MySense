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

# $Id: MyLogger.py,v 4.1 2021/02/07 14:37:26 teus Exp teus $

# TO DO:

""" Push logging to the external world.
"""
modulename='$RCSfile: MyLogger.py,v $'[10:-4]
__version__ = "0." + "$Revision: 4.1 $"[11:-2]

import sys

# configurable options
__options__ = ['level','file','output','date']

Conf = {
    'level': 'INFO',
    'istty': False, # should go away
    'file' : sys.stderr,
    'fd': None,
    'output': True,
    'date': True, # prepend with date
    'print': True, # color printing
    'stop': None
}
# ===========================================================================
# logging
# ===========================================================================

# logging levels
FATAL    = 70
#CRITICAL = 60
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
    if not Conf['output']: return
    def IsTTY():
        global Conf
        if Conf['istty']: return True
        try:
            # log messages go to tty
            if Conf['file'] == None or ['/dev/stdout','/dev/stderr','/dev/tty'].index(Conf['file']) >= 0:
                Conf['istty'] = True
        except:
            Conf['istty'] = False
        return Conf['istty']
                
    def printc(text, color=0): # default color ansi black
        global Conf
        try:
          if Conf['print']:
            Conf['print'].MyPrint(text, color=color)
            return
        except: pass
        try: sys.stderr.write(text+'\n')
        except: pass

    if type(level) is str:
        level = log_levels.index(level.upper())*10
    try:
        if int(level /10) < log_levels.index(Conf['level'].upper()):
            return
    except:
        pass
    name = name.replace('.py','')
    if name != 'MySense': name = 'MySense ' + name.replace('My','')
    if Conf['fd'] == None and Conf['print'] == None:
        # this part needs some work
        try:
            import logging, logging.handlers
            Conf['fd'] = logging.getLogger("IoS-sensor_log")
        except:
            sys.exit("FATAL error while initiating logging. IoS program Aborted.")
        try:
            Conf['fd'].setLevel(10 * log_levels.index(Conf['level']))
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
    elif Conf['print'] != None and (type(Conf['print']) is bool):
      if (not 'file' in Conf.keys()) or not Conf['file']:
        Conf['file'] = sys.stderr
      try:
        import MyPrint
        fifo = False
        if (type(Conf['file']) is str) and Conf['file'].find('fifo=') == 0:
            fifo = True; Conf['file'] = Conf['file'][5:]
        Conf['print'] = MyPrint.MyPrint(output=Conf['file'], color=Conf['print'], fifo=fifo, date=Conf['date'])
        Conf['stop'] = Conf['print'].stop
      except Exception as e:
        sys.stderr.write("Exception with loading module print color: %s\n" % str(e))
        Conf['print'] = None

    if Conf['fd']:
        try:
            Conf['fd'].log(level,name + ': ' + message)
        except:
            sys.exit("Unable to log to %s. Program aborted." % Conf["log"]['file'])
        if level == FATAL:
            Conf['fd'].log(CRITICAL,"Program aborted.")
            sys.exit("FATAL error. Program Aborted.")
    else:
        printc("%s %s: %s" % (name,log_levels[int(level/10)%len(log_levels)], message),log_colors[int(level/10)%len(log_levels)])
    
def show_error():               # print sys error
    log('ERROR',"Failure type: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
    return

