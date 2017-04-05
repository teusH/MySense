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

# $Id: MyCONSOLE.py,v 2.5 2017/04/05 09:10:05 teus Exp teus $

# TO DO: write to file or cache

""" Publish measurements to console STDOUT
    Relies on Conf setting biy main program
"""
modulename='$RCSfile: MyCONSOLE.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.5 $"[11:-2]

try:
    import MyLogger
    import sys
    from time import time
    import datetime
except ImportError as e:
    MyLogger.log("FATAL","One of the import modules not found: %s" % e)

# configurable options
__options__ = ['output','file']

Conf = {
     'output': False,    # console output dflt enabled if no output channels defined
#    'fd': None,         # input handler
     'file': '/dev/stdout',   # Debugging: write to file
}

def registrate(ident):
    global Conf
    if 'registrated' in Conf.keys():
        return Conf['registrated']
    print datetime.datetime.fromtimestamp(time()).strftime('%b %d %Y %H:%M:%S')
    print "Registration of project %s, S/N %s, location %s:" % (ident['project'], ident['serial'],ident['geolocation'])
    for Id in ("label","description","street","village","province","municipality",'fields','units','calibrations','types','apikey','intern_ip','extern_ip','version'):
        if (Id in ident.keys() and (ident[Id] != None)):
            print "%15s: " % Id, ident[Id]
    print ''
    Conf['registrated'] = True

# =============================================
# print telegram with measurement values on console
# =============================================
# import datetime
def publish(**args):
    global Conf
    
    if not Conf['output']:
        return
    for key in ['data','ident']:
        if not key in args.keys():
            MyLogger.log('FATAL',"Broker publish call missing argument %s." % key)
    registrate(args['ident'])
    print "    %-14s: %s (%s)" % ('time',args['data']['time'],datetime.datetime.fromtimestamp(args['data']['time']).strftime("%Y-%m-%d %H:%M:%S"))
    for item in sorted(args['data'].iterkeys()):
        if item != 'time':
            print "\t%-10s: %s" % (item,args['data'][item])

