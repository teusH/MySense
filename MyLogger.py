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

# $Id: MyLogger.py,v 3.4 2017/06/04 15:01:58 teus Exp teus $

# TO DO:

""" Push logging to the external world.
"""
modulename='$RCSfile: MyLogger.py,v $'[10:-4]
__version__ = "0." + "$Revision: 3.4 $"[11:-2]

# configurable options
__options__ = ['level','file']

Conf = {
    'level': 0,
    'istty': False,
    'file' : None,
    'fd': None,
}
# ===========================================================================
# logging
# ===========================================================================

try:
    import sys
except:
    print("FATAL error: no sys to import")
    exit(1)

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
# TO DO: install remote logging
def log(name,level,message): # logging to console or log file
    global Conf
    # seems python3 logging module does not allow logging on stdout or stderr
    def IsTTY():
        global Conf
        try:
            # log messages go to tty
            if Conf['file'] == None or ['/dev/stdout','/dev/stderr','/dev/tty'].index(Conf['file']) >= 0:
                Conf['istty'] = True
        except:
            Conf['istty'] = False
        return Conf['istty']

    if type(level) is str:
        level = log_levels.index(level.upper())*10
    try:
        if int(level /10) < log_levels.index(Conf['level'].upper()):
            return
    except:
        pass
    name = name.replace('.py','')
    if name != 'MySense': name = 'MySense ' + name.replace('My','')
    if Conf['fd'] == None and not IsTTY():
        try:
            import logging, logging.handlers
            Conf['fd'] = logging.getLogger("IoS-sensor_log")
        except:
            sys.exit("FATAL error while initiating logging. IoS program Aborted.")
        try:
            Conf['fd'].setLevel(10 * log_levels.index(Conf['level']))
        except:
            Conf['fd'].setLevel(1)  # log all
        if Conf['file'].lower() == 'syslog':
            log_handle = logging.handlers.SysLogHandler(address = '/dev/log')
        else:
            log_handle = logging.FileHandler(Conf['file'])
        log_frmt = logging.Formatter("%(asctime)s IoS %(levelname)s: %(message)s", datefmt='%Y/%m/%d %H:%M:%S')
        log_handle.setFormatter(log_frmt)
        Conf['fd'].addHandler(log_handle)
    if not Conf['istty']:
        try:
            Conf['fd'].MyLogger.log(level,name + ': ' + message)
        except:
            sys.exit("Unable to log to %s. Program aborted." % Conf["log"]['file'])
        if level == FATAL:
            Conf['fd'].MyLogger.log(CRITICAL,"Program aborted.")
            sys.exit("FATAL error. Program Aborted.")
    else:
        sys.stderr.write("%s %s: %s" % (name,log_levels[int(level / 10)], message + "\n"))
        if level == FATAL:
            sys.exit("FATAL error. IoS Program Aborted.")
    
def show_error():               # print sys error
    log('ERROR',"Failure type: %s; value: %s" % (sys.exc_info()[0],sys.exc_info()[1]) )
    return

