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

# $Id: MyCONSOLE.py,v 3.4 2020/04/23 13:53:30 teus Exp teus $

# TO DO: write to file or cache

""" Publish measurements to console STDOUT
    Relies on Conf setting biy main program
"""
modulename='$RCSfile: MyCONSOLE.py,v $'[10:-4]
__version__ = "0." + "$Revision: 3.4 $"[11:-2]

try:
    import sys
    from time import time
    import datetime
    import MyPrint
except ImportError as e:
    sys.exit("FATAL: One of the import modules not found: %s" % e)

# configurable options
__options__ = ['output','file','print']

Conf = {
     'output': False,    # console output dflt enabled if no output channels defined
#    'fd': None,         # input handler
     'file': '/dev/stdout',   # Debugging: write to file
     'match': [           # translation table for db abd unit names
        ('C','oC'),
        ('F','oF'),
        ('pcs/qf','pcs/0.01qf'),
          ],
     'print': True,      # if not None try to print color, or False: fifo
     'log': None,        # log print routine (name,level,message)
     'stop': None

}

# ansi colors: 1:red, 2:green, 3:yellow, 4:blew, 5:purple, 8: gray, 16: black, 21: blew
def printc(text, color=0): # default color ansi black
    global Conf
    try:
      if Conf['print']:
        Conf['print'](text, color=color)
        return
    except: pass
    try: sys.stdout.write(text+'\n')
    except: pass

IdentSeen = {}
def registrate(ident):
    global Conf
    fnd = None ; new = False
    if not Conf['log']:
        import MyLogger
        Conf['log'] = MyLogger.log
    # should be unique
    for Id in ("serial","geolocation","street","label",'apikey','intern_ip'):
        if not Id in ident.keys():
            continue
        else: fnd = ident[Id]
        if (Id == "serial") and ('project' in ident.keys()):
            fnd = '%s_%s' % (ident['project'],fnd)
        if not fnd in IdentSeen.keys():
            IdentSeen[fnd] = new = True
        break
    if not fnd:
        fnd = hash(ident)
        if not fnd in IdentSeen.keys():
            IdentSeen[fnd] = new = True
    try:
        if ident['count'] == 1:
            new = True
        count = str(ident['count'])
    except: count = '?'
    if ('print' in Conf.keys()) and (type(Conf['print']) is bool):
      try:
        import MyPrint
        fifo = False
        if (type(Conf['file']) is str) and (Conf['file'].find('fifo=') == 0):
            fifo = True; Conf['file'] = Conf['file'][5:]
        Conf['print'] = MyPrint.MyPrint(output=Conf['file'], color=Conf['print'], fifo=fifo, date=False)
        Conf['stop'] = Conf['print'].stop
        Conf['print'] = Conf['print'].MyPrint
      except: Conf['print'] = None
        
    printc('ID: %s (#%s) at %s' % (str(fnd),count,datetime.datetime.fromtimestamp(time()).strftime('%b %d %Y %H:%M:%S')),18)
    if not new: return  # ident is similar as previous
    try:
        printc("    Identity info of project %s S/N %s at geo location %s:" % (ident['project'], ident['serial'],ident['geolocation']),4)
    except: pass
    for Id in ("label","project","serial","description","comment","geolocation","coordinates","street","pcode","village","province","municipality",'fields','units','calibrations','types','apikey','intern_ip','extern_ip','version'):
        if Id == 'geolocation': printc('    location details:',4)
        elif Id == 'fields': printc('    sensor details:',4)
        if (Id in ident.keys() and (ident[Id] != None)):
            if type(ident[Id]) is list:
                printc("%15s: %s" % (Id,str(ident[Id]).replace(' ','').replace('u\'','').replace('\'','')))
            else:
                printc("%15s: %s" % (Id,str(ident[Id])))
    printc('')
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
        UT[0] = ('' if ident['units'][indx] == '%' else '') + ident['units'][indx] 
        UT[1] = '' + ident['types'][indx]
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
        return False
    for key in ['data','ident']:
        if not key in args.keys():
            Conf['log'](modulename,'FATAL',"publish call missing argument %s." % key)
    registrate(args['ident'])
    # printc('    sensor data:',4)
    printc("    %-14s: %s (%s)" % ('time',args['data']['time'],datetime.datetime.fromtimestamp(args['data']['time']).strftime("%Y-%m-%d %H:%M:%S")),4)
    for item in sorted(args['data'].iterkeys()):
        if item != 'time':
            Unit,Type = findInfo(args['ident'],item)
            printc("\t%-10s: %-10.10s%-8.8s%s" % (item,args['data'][item],trans(Unit),Type))
    return True

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

