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

# $Id: MyCONSOLE.py,v 2.8 2017/12/23 13:11:59 teus Exp teus $

# TO DO: write to file or cache

""" Publish measurements to console STDOUT
    Relies on Conf setting biy main program
"""
modulename='$RCSfile: MyCONSOLE.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.8 $"[11:-2]

try:
    import MyLogger
    import sys
    from time import time
    import datetime
except ImportError as e:
    MyLogger.log(modulename,"FATAL","One of the import modules not found: %s" % e)

# configurable options
__options__ = ['output','file']

Conf = {
     'output': False,    # console output dflt enabled if no output channels defined
#    'fd': None,         # input handler
     'file': '/dev/stdout',   # Debugging: write to file
     'match': [           # translation table for db abd unit names
        ('C','oC'),
        ('F','oF'),
        ('pcs/qf','pcs/0.01qf'),
           ],

}

IdentSeen = {}
def registrate(ident):
    global Conf
    fnd = False
    for Id in ("serial","label","geolocation","street",'apikey','intern_ip'):
        if not ident[Id]:
            continue
        if ident[Id] in IdentSeen.keys():
            return
        IdentSeen[ident[Id]] = True
        fnd = True
        break
    if not fnd:
        fnd = hash(ident)
        if fnd in IdentSeen.keys(): return
        IdentSeen[fnd] = True
    print datetime.datetime.fromtimestamp(time()).strftime('%b %d %Y %H:%M:%S')
    fnd = True
    for Id in ("project","serial","geolocation"):
        if not Id in ident.keys():
            print "Info: in ident record %s field is missing." % Id
            fnd = False
    if fnd:
        print "Registration of project %s, S/N %s, location %s:" % (ident['project'], ident['serial'],ident['geolocation'])
    for Id in ("label","serial","description","street","village","province","municipality",'fields','units','calibrations','types','apikey','intern_ip','extern_ip','version'):
        if (Id in ident.keys() and (ident[Id] != None)):
            print "%15s: " % Id, ident[Id]
    print ''
    return

def findInfo(ident,field):
    UT = ['','']   # (unit,sensor type)
    try:
        indx = ident['fields'].index(field)
        UT[0] = ('' if ident['units'][indx] == '%' else ' ') + ident['units'][indx] 
        UT[1] = ' ' + ident['types'][indx]
    except:
        pass
    finally:
        return (UT[0],UT[1])
    
# =============================================
# print telegram with measurement values on console
# =============================================
# import datetime
def publish(**args):
    global Conf
    def trans(name):
        global Conf
        if (not 'match' in Conf.keys()) or (not type(Conf['match']) is list):
            return name
        for item in Conf['match']:
             if not type(item) is tuple: continue
             if name.find(item[0]) < 0: continue
             name = name.replace(item[0],item[1])
        return name
    
    if not Conf['output']:
        return
    for key in ['data','ident']:
        if not key in args.keys():
            MyLogger.log(modulename,'FATAL',"publish call missing argument %s." % key)
    registrate(args['ident'])
    print "    %-14s: %s (%s)" % ('time',args['data']['time'],datetime.datetime.fromtimestamp(args['data']['time']).strftime("%Y-%m-%d %H:%M:%S"))
    for item in sorted(args['data'].iterkeys()):
        if item != 'time':
            Unit,Type = findInfo(args['ident'],item)
            print "\t%-10s: %s%s%s" % (item,args['data'][item],trans(Unit),Type)

# test main loop
if __name__ == '__main__':
    Conf['output'] = True
    from time import sleep
    try:
        import Output_test_data
    except:
        print("Please provide input test data: ident and data.")
        exit(1)

    for cnt in range(0,len(Output_test_data.data)):
        timings = time()
        try:
            publish(
                ident=Output_test_data.ident,
                data = Output_test_data.data[cnt],
            )
        except Exception as e:
            print("output channel error was raised as %s" % e)
            break
        timings = 10 - (time()-timings)
        if timings > 0:
            print("Sleep for %d seconds" % timings)
            sleep(timings)

