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

# $Id: MyCSV.py,v 2.6 2017/06/04 09:40:55 teus Exp teus $

# TO DO: write to file or cache

""" Publish measurments to Comma Separated V (CSV) file
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyCSV.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.6 $"[11:-2]

# configurable options
__options__ = ['output','file','ttl']

Conf = {
    'output': False,     # local spreadsheet file
    'file': None,    # name is extended: id,day-month-year,.csv
    'ttl': 24*60*60,     # time to live for new worksheet
#   'renew': None,       # max time to renew registration
}

# CSV file dispatcher
CSV = {}                 # keys are serials with dict to CSV file handling
try:
    import MyLogger
    import csv
    import datetime
    import os
    from datetime import date
    from time import time
except ImportError:
    MyLogger.log(modulename,'FATAL',"module missing.")
    Conf['output'] = False

# ========================================================
# write data  or sensor values to local CSV file per day one file
# ========================================================
# create CSV file and push the header
# create a new file if the ttl (dflt one day) is changed
# extend the file name with a day string
def show_ident(ident,path):
    global Conf
    IDtxt = None
    if os.path.exists(path):
        try:
            os.remove(path)
        except:
            pass
    try:
        try:
            IDtxt=open(path, 'wt', newline='', encoding="utf-8")
        except TypeError:
            IDtxt=open(path, 'wt')
    except:
        MyLogger.log(modulename,'ERROR',"Unable to info file %s. Abort." % path)
        return False
    IDtxt.write(datetime.datetime.fromtimestamp(time()).strftime('%b %d %Y %H:%M:%S')+"\n")
    IDtxt.write("Identification info of sensor: project %s, S/N %s\n" % (ident['project'], ident['serial']))
    for Id in ("label","description","geolocation","street","village","province","municipality",'fields','units','types','apikey','intern_ip','extern_ip','version'):
        if (Id in ident.keys() and (ident[Id] != None)):
            values = ident[Id]
            if Id == 'geolocation':
                if ident[Id] == '0,0,0': continue
                else: values += '(lat,lon,alt)'
            if type(ident[Id]) is list:
                values = ', '.join(ident[Id])
            IDtxt.write("%15s: %s\n" % (Id,values))
    IDtxt.close()
    return True

# create a new CSV file and/or open it
# every serial should be unique (not checked) and get own file handling
def registrate(args):
    global Conf, CSV
    for key in ['ident']:
        if not key in args.keys():
            MyLogger.log(modulename,'FATAL',"%s argument missing." % key)
    ID = args['ident']['serial']
    if not ID in CSV.keys():
        if len(CSV) >= 20:
            for id in CSV.keys():       # garbage collection
                if not 'fd' in CSV[id].keys():
                    del CSV[id]
                elif ('last' in CSV[id]) and (int(time())-CSV[id]['last'] > 2*60*60):
                    CSV[id]['fd'].close() ; del CSV[id]
            if len(CSV) >= 20:
                MyLogger('WARNING',"to much CSV id's in progress. Skipping %s" & ID)
                return False
        CSV[ID] = { 'file': Conf['file'], 'renew': 0 }
    ID = CSV[ID]
    if ('fd' in ID.keys()) and ID['fd']:
        if (time() > ID['renew']) and ('fd' in ID.keys()):
            ID['renew'] = int((time()-1)/(24*60*60))*24*60*60+Conf['ttl']
            ID['fd'].close(); del ID['fd']
    if 'fd' in ID.keys():
        return True
    if (not ID['file']):
        try:
            ID['file'] = args['ident']['project'] + '/'
            os.mkdir(args['ident']['project'],0770)
        except OSError:
            pass
        except:
            ID['file'] = './'
        ID['file'] += args['ident']['serial']
    ID['cur_name'] = ID['file']+'_'+datetime.datetime.now().strftime("%Y-%m-%d")+'.csv'

    try:
        show_ident(args['ident'],ID['file']+'.txt')
    except:
        pass
    new = True
    if os.path.exists(ID['cur_name']):
        if not os.access(ID['cur_name'],os.W_OK):
            MyLogger.log(modulename,'FATAL',"Cannot write to %s. Abort." % ID['cur_name'])
        try:
            try:
                ID['fd']=open(ID['cur_name'], 'at', newline='', encoding="utf-8")
            except TypeError:
                ID['fd']=open(ID['cur_name'], 'at')
        except:
            MyLogger.log(modulename,'FATAL',"Cannot write to %s. Abort." % ID['cur_name'])
        new = False
    else:
        #Otherwise: create it
        try:
            try:
                ID['fd']=open(ID['cur_name'], 'wt', newline='', encoding="utf-8")
            except TypeError:
                ID['fd']=open(ID['cur_name'], 'wt')
        except:
            MyLogger.log(modulename,'ERROR',"Unable to create file %s. Abort CSV." % ID['cur_name'])
            Conf['output'] = False
            raise IOError
            return False
    #Write csv-header
    try:
        ID['writer'] = csv.writer(ID['fd'], dialect='excel', delimiter=';', quoting=csv.QUOTE_NONNUMERIC)
        if new:
            Row = []
            cells = args['ident']
            for i in range(0,len(cells['fields'])):
                # this needs some more thought
                if type(args['data'][cells['fields'][i]]) is list:
                    for j in range(1,len(args['data'][cells['fields'][i]])):
                        Row.append("%s_%d(%s)" % (cells['fields'][i],j,cells['units'][i]))
                else:
                    Row.append("%s(%s)" % (cells['fields'][i],cells['units'][i]))
            ID['writer'].writerow(Row)
    except:
        MyLogger.log(modulename,'ERROR',"Failed to open file %s for writing." % ID['cur_name'])
        raise IOError
        return False
    MyLogger.log(modulename,'INFO',"Created and will add records to file:" + os.getcwd() + '/' + ID['cur_name'])
    return True
    
# add record to the CSV file
def publish(**args):
    global Conf, writer, CSV
    if (not 'output'  in Conf.keys()) or not Conf['output']:
        return False
    for key in ['data','ident']:
        if not key in args.keys():
            MyLogger.log(modulename,'FATAL',"Method: missing argument %s." % key)
    if not registrate(args):
        MyLogger.log(modulename,'ERROR',"Failed file creation/opening.")
        return False
    Row = []
    for Fld in args['ident']['fields']:
        if type(args['data'][Fld]) is list:
            for i in args['data'][Fld]:
                Row.append(i)
        elif Fld == 'time':     # convert UNIX brith time to local time string
            Row.append(datetime.datetime.fromtimestamp(args['data'][Fld]).strftime("%Y-%m-%d %H:%M:%S"))
        else:
            Row.append(args['data'][Fld])
    ID = CSV[args['ident']['serial']]
    ID['writer'].writerow(Row)
    ID['fd'].flush()
    ID['last'] = int(time())
    #ID = args['ident']['serial']
    #CCSV[]SV[ID]['writer'].writerow(Row)
    #CSV[ID]['fd'].flush()
    #CSV[ID]['last'] = int(time())
    MyLogger.log(modulename,'DEBUG',"Record in %s, timestamp: %s" % (ID['cur_name'], args['data']['time']) )
    return True
    
