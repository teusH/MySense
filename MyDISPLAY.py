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

# $Id: MyDISPLAY.py,v 1.1 2017/06/17 14:10:34 teus Exp teus $

""" Publish measurements to display service
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyDISPLAY.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.1 $"[11:-2]

try:
    import MyLogger
    import sys
    import datetime
    import socket
    from time import time
except ImportError as e:
    MyLogger.log(modulename,"FATAL","One of the import modules not found: %s" % e)

# configurable options
__options__ = ['output','port',]

Conf = {
    'output': False,
    'hostname': 'localhost', # host InFlux server
    'port': 2017,        # default display port number
    'fd': None,          # have sent to db: current fd descriptor, 0 on IO error
    'omit' : ['time','geolocation',],  # fields not archived
}

# ========================================================
# write data directly to a database
# ========================================================
# create table <ProjectID_Serial>, record columns,
#       registration Sensors table on the fly
def attributes(**t):
    global Conf
    Conf.update(t)

def displayMsg(msg):
    global Conf
    degree = u'\N{DEGREE SIGN}'
    micro = u'\N{MICRO SIGN}'
        
    if not len(msg): return True
    if not type(msg) is list: msg = msg.split("\n")
    for i in range(len(msg)-1,-1,-1): 
        if not len(msg[i]):
            msg.pop(i)
            continue
        msg[i] = format(msg[i])
        if msg[i][-1] == "\n": msg[i] = msg[i][:-1]
        msg[i] = msg[i].replace('oC',degree + 'C')
        #msg[i] = msg[i].replace('ug/m3',micro + 'g/m³')
        msg[i] = msg[i].replace('ug/m3',micro + 'g/m3')
    msg = "\n".join(msg) + "\n"
    if not len(msg): return True
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((Conf['host'],Conf['port']))
        sock.send(msg)
        sock.close()
        return True
    except:
        raise IOError("Unable to talk to display service")
        return False

# connect to db and keep connection as long as possible
def db_connect(geo,name):
    """ Connect to InFlux database and save filehandler """
    global Conf
    if not 'fd' in Conf.keys(): Conf['fd'] = False
    if not Conf['fd']:
        Conf['port'] = int(Conf['port'])
        if (Conf['hostname'] != 'localhost') and (not Conf['port']):
            MyLogger.log(modulename,'ERROR',"Access display service %s / %d."  % (Conf['hostname'], Conf['port']))      
            Conf['output'] = False
            return False
        if (Conf['fd'] != None) and (not Conf['fd']): # should not happen, internal error
            MyLogger.log(modulename,'ERROR','Unable to use display service')
            Conf['output'] = False
            return False
        try:
            displayMsg(datetime.datetime.fromtimestamp(time()).strftime('%Hh %Mm%Ss ') + ' MySense activated')
            if len(name): displayMsg(name)
            if geo:
                geo = geo.split(',')
                if len(geo) == 3:
                    displayMsg('long: %8.5f, lat: %8.5f, alt: %dm' % (float(geo[0]),float(geo[1]),int(geo[2])))
                elif len(geo) == 2:
                    displayMsg('long: %8.5f, lat: %8.5f' % (float(geo[0]),float(geo[1])))
            Conf['fd'] = True
        except IOError:
            MyLogger.log(modulename,'ERROR',"Access database %s / %s."  % (Conf['hostname'], Conf[database]))      
            Conf['output'] = False
    return Conf['fd']

# registrate the sensor to the Sensors table and update location/activity
def db_registrate(ident):
    """ create or update identification inf to Sensors table in database """
    global Conf
    if ("registrated" in Conf.keys()) and (Conf['registrated'] != None):
        return Conf['registrated']
    if len(ident['fields']) == 0:
        return False
    geo = ''
    if 'geolocation' in ident.keys(): geo = ident['geolocation']
    name = ''
    for item in ['project','serial','label']:
        if (item in ident.keys()) and len(ident[item]):
            if len(name): name += ', '
            name += item + ': ' + ident[item]
    if not db_connect(geo,name):
        return False

    # next fails on non admin priv users
    Conf['tags'] = {}
    # the fields: information about the sensor
    if (not 'fields' in ident.keys()) or (not 'units' in ident.keys()) or (len(Conf['fields']) != len(Conf['units'])):
        MyLogger.log(modulename,'Error','fields and/or units key mising or incorrect.')
        return False
    for i in range(0,len(Conf['fields'])):
        if Conf['fields'][i] in Conf['omit']: continue
        Conf['tags'][Conf['fields'][i]] = ( (u'\N{DEGREE SIGN}'+'C') if Conf['units'][i] == 'C' else Conf['units'][i])
    Conf["registrated"] = True
    return True

def publish(**args):
    """ add records to the database,
        on the first update table Sensors with ident info """
    global Conf, ErrorCnt
    if (not 'output' in Conf.keys()) or (not Conf['output']):
        return
    for key in ['data','ident']:
        if not key in args.keys():
            MyLogger.log(modulename,'FATAL',"Publish call missing argument %s." % key)

    # TO DO: get the transaltion table from the MySense.conf file
    def db_name(my_name):
        DBnames = {
        }
        if my_name in DBnames.keys(): return DBnames[my_name]
        return my_name

    if Conf['fd'] == None: Conf['registrated'] = None
    if not db_registrate(args['ident']):
        MyLogger.log(modulename,'WARNING',"Unable to registrate the sensor.")
        return False
    if Conf['fd'] == None:
        return False
   
    lines = ['','','']   # db_name, unit, value
    for item in args['data'].keys():
        if item in Conf['omit']: continue
        if not args['data'][item]: continue
        Nm = db_name(item)
        if type(args['data'][item]) is list:
            MyLogger.log(modulename,'WARNING',"Found list for sensor %s." % item)
            continue
        else:
            if not args['data'][item]: continue
            fields[Nm] = args['data'][item]
            lines[0] += rjust('%5s' % Nm, 5)
            lines[1] += rjust('%5s' % Conf['tags'][item])
            lines[2] += rjust('%5.0f' % float(args['data'][item]))
        lines.insert(0,datetime.datetime.fromtimestamp(time()).strftime('%d %b %H:%M:%S'))
        if 'time' in args['data'].keys():
            try:
                lines[0] = datetime.datetime.fromtimestamp(args['data']['time']).strftime('%d %b %H:%M:%S')
            except:
                pass
        try:
            sendMsg(lines)
        except:
            MyLogger.log(modulename,'ERROR','Unable to send text to display service.')
            return False
    return True

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['output'] = True
    Conf['port'] = 2017
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
        timings = 30 - (time()-timings)
        if timings > 0:
            print("Sleep for %d seconds" % timings)
            sleep(timings)

