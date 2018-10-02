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

# $Id: MyCONSOLE.py,v 2.11 2018/10/02 13:47:58 teus Exp teus $

# TO DO: write to file or cache

""" Publish measurements to console STDOUT
    Relies on Conf setting biy main program
"""
modulename='$RCSfile: MyCONSOLE.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.11 $"[11:-2]

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
    fnd = None ; new = False
    for Id in ("serial","label","geolocation","street",'apikey','intern_ip'):
        if not ident[Id]:
            continue
        if ident[Id] in IdentSeen.keys():
            fnd = ident[Id]
            break
        fnd = ident[Id]; new = True
        break
    if not fnd:
        fnd = hash(ident)
        if not fnd in IdentSeen.keys(): new = True
    print 'ID: %s at %s' % (str(fnd),datetime.datetime.fromtimestamp(time()).strftime('%b %d %Y %H:%M:%S'))
    if (not new) and (cmp(IdentSeen[fnd],ident) == 0): return  # ident is simular as previous
    else: IdentSeen[fnd] = ident.copy()
    fnd = True
    for Id in ("project","serial","geolocation"):
        if not Id in ident.keys():
            print "Info: in ident record %s field is missing." % Id
            fnd = False
    if fnd:
        print "%s registration of project %s, S/N %s, location %s:" % ('New' if new else 'Updated',ident['project'], ident['serial'],ident['geolocation'])
    for Id in ("label","serial","description","street","village","province","municipality",'fields','units','calibrations','types','apikey','intern_ip','extern_ip','version'):
        if (Id in ident.keys() and (ident[Id] != None)):
            print "%15s: " % Id, ident[Id]
    print ''
    return

translateTBL = {
        "pm03": ["pm0.3","PM0.3"],
        "pm1":  ["roet","soot"],
        "pm25": ["pm2.5","PM2.5"],
        "pm5":  ["pm5.0","PM5.0"],
        "pm10": ["pm","PM"],
        "O3":   ["ozon"],
        "NH3":  ["ammoniak","ammonium"],
        "NO2":  ["stikstof","stikstofdioxide","nitrogendioxide"],
        "NO":   ["stikstof","stikstofoxide","nitrogenoxide"],
        "CO2":  ["koolstofdioxide","carbondioxide"],
        "CO":   ["koolstofmonoxide","carbonoxide"],
        "temp": ["temperature"],
        "luchtdruk": ["pressure","pres","pha","pHa"],
        "rv":   ["humidity","hum","vochtigheid","vocht"],
        "ws":   ["windspeed","windsnelheid"],
        "wr":   ["windrichting","winddirection","direction"],
        "altitude":  ["alt","hoogte","height"],
        "longitude":  ["long","lon","lengte graad"],
        "latitude":  ["lat","breedte graad"],
        "geolocation": ["gps","GPS","coordinates","geo"],
        "gas":  ["air"],
        "aqi":  ["air quality","luchtkwaliteit","lki"],
        "version": ["versie","release"],
        "meteo": ["weer"],
        "dust": ["fijnstof"],
        "time": ["utime","timestamp"]
    }
# rename names into known field names
def translate( sense ):
    sense.replace('PM','pm')
    for strg in ('O3','NH','NO','CO'):
        sense.replace(strg.lower(),strg)
    for strg in translateTBL.keys():
        if sense.lower() == strg.lower(): return strg
        for item in translateTBL[strg]:
            if item == sense: return strg
    return sense

def findInfo(ident,field):
    UT = ['','']   # (unit,sensor type)
    try:
        indx = ident['fields'].index(translate(field))
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

