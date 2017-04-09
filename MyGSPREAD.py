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

# $Id: MyGSPREAD.py,v 2.8 2017/04/09 18:15:35 teus Exp teus $

# TO DO:  OPERATIONAL TESTS

""" Publish measurments to Google shared spreadsheet (gspread) service
    Get Google apikey credentials.
    Spreadsheet name is <project name>_<serial nr>
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyGSPREAD.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.8 $"[11:-2]

# configurable options
__options__ = ['output','sheet','credentials','user','ttl','hostname','apikey']

Conf = {
    'output': False,      # local spreadsheet file
    'user': None,         # Google sharing user
    'hostname': None,     # mark this modiule requires internet and user@host def
    'credentials': None,  # json file with Google credentials
    'apikey': None,       # api key to share spreadsheet with the world
    'ttl': '%Y-%b',       # time dependent name of sheet (strftime)
    'sheet': 'IoS_',      # sheet name prepend: <name><ttl>
}

# CSV spreadsheets dispatcher
CSV = {}                  # keys are serials with dict to GSPREAD CSV file handling
try:
    import MyLogger
    import gspread        # install via eg github https://github.com/burnash/gspread
    from oauth2client.service_account import ServiceAccountCredentials
    import datetime
    import os
    from datetime import date
    from time import time
except ImportError:
    MyLogger.log('FATAL',"GSPREAD module missing for spreadsheet output.")
    Conf['output'] = False

# ========================================================
# write data  or sensor values to  share spreadsheet file at Google
# ========================================================
# create spreadsheet file and push the header
# create a new sheet if the ttl (dflt one day) is changed
# extend the file name with a month string

# an easy hack to get credentials
#class Credentials (object):
#  global Conf
#  def __init__ (self, access_token=None):
#    self.access_token = Conf['apikey']
#
#  def refresh (self, http):
#    # get new access_token
#    # this only gets called if access_token is None

# use the credentials received as json file from Google development website
def authenticate_google_docs():
    global Conf
    #if ('apikey' in Conf.keys()) and (Conf['apikey'] != None):
    #    return gspread.open_by_key(Conf['apikey'])
    if (Conf['credentials'] == None) or (not os.access(Conf['credentials'],os.R_OK)):
        MyLogger.log('ERROR','Gspread unable to read Google credentials file %s.' % Conf['credentials'])
        return False
    scope = ['https://spreadsheets.google.com/feeds']
    gc = None
    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_name(Conf['credentials'], scope)
        gc =  gspread.authorize(credentials)
    except Exception as ex:
        MyLogger.log('ERROR','Gspread unable to get Google gspread access. Error: %s' % ex)
    return gc

# update project sheet with identification details, subjected to PII rulings
def show_ident(ident):
    global Conf, CSV
    IDtxt = None
    new = True
    ID = CSV[ident['serial']]
    row1 = ['date','project','serial']
    row2 = [datetime.datetime.fromtimestamp(time()).strftime('%b %d %Y %H:%M:%S')+"\n", ident['project'], ident['serial']]
    for key in ("label","description","geolocation","street","village","province","municipality",'fields','units','types','extern_ip','version'):
        if (key in ident.keys() and (ident[key] != None)):
            values = ident[key]
            if key == 'geolocation':
                if ident[key] == '0,0,0': continue
                else: values += '(lat,lon,alt)'
            if type(ident[key]) is list:
                values = ', '.join(ident[key])
            row1.append(key)
            row2.append("%15s: %s\n" % (key,values))
    try:
        IDtxt = ID['fd'].add_worksheet(title='info', rows="20", cols="%d" % len(Row2))
        if new:
            # would be nice to give this row a color
            IDtxt.append_rows(row1)
        IDtxt.append_rows(row2)
    except:
        MyLogger.log('WARNING","Gspread unable to created/update info sheet')
        return False
    MyLogger('DEBUG','Gspread added identification to %s_%s.info sheet.' % (ident['project'],ident['serial']))
    return True

# create a new CSV file and/or open it
# every serial should be unique (not checked) and get own file handling
def registrate(args):
    global Conf, CSV, gspread
    for key in ['ident']:
        if not key in args.keys():
            MyLogger.log('FATAL',"GSPREAD %s argument missing." % key)
    if (Conf['fd'] != None) and (not Conf['fd']):
        if ('waiting' in Conf.keys()) and ((Conf['waiting']+Conf['last']) >= time()):
            CSV = {}
            raise IOError
            return False
    ID = args['ident']['serial']
    if not ID in CSV.keys():
        if len(CSV) >= 20:
            for id in CSV.keys():       # garbage collection
                if not 'sheet' in CSV[id].keys():
                    del CSV[id]
                elif ('last' in CSV[id]) and (int(time())-CSV[id]['last'] > 2*60*60):
                    del CSV[id]
            if len(CSV) >= 20:
                MyLogger('WARNING',"to much GSPREAD id's in progress. Skipping %s" & ID)
                return False
        CSV[ID] = { 'worksheet': Conf['sheet'], 'renew': 0 }
    ID = CSV[ID]
    # authenticate
    if (not 'auth' in ID.keys()):
        try:
            ID['auth'] = authenticate_google_docs()
        except:
            Conf['auth'] = False
    if ID['auth'] == False:
        MyLogger.log('ERROR','Gspread unable to get access to Google gspread. Disabled.')
        Conf['output'] = False
        return False
    # get the spreadsheet
    if (not ID['worksheet']):
        ID['worksheet'] = args['ident']['project'] + '_' + args['ident']['serial']
        ID['sheet'] = Conf['sheet']
        ID['fd'] = None
    try:
        if ID['worksheet'] in ID['auth'].worksheets():
            ID['fd'] = ID['auth'].open(ID['worksheet'])
            new = False
        else:
            ID['fd'] = ID['auth'].create(ID['worksheet'])
            if (Conf['user'] == None) and (Conf['hostname'] == None):
                ID['fd'].share(None, perm_type='anyone', role='reader')
            else:
                ID['fd'].share('%s@%s' % (Conf['user'],Conf['hostname']), perm_type='user', role='reader')
    except:
        Conf['output'] = False
        MyLogger.log('ERROR','Gspread: unable to authorize or access spreadsheet.')
        return False
    try:
        show_ident(args['ident'],ID['fd'])
    except:
        pass

    # get the sheet sorted by ttl (dflt per month)
    newNme = Conf['sheet'] + datetime.datetime.now().strftime(Conf['ttl'])
    new = False
    if (ID['sheet'] != newNme) or ('not cur_sheet' in ID.keys()):
        new = True
        ID['sheet'] = newNme
        ID['cur_sheet'] = None
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
        try:
            ID['cur_sheet'] = ID['fd'].add_worksheet(title=newName, rows="%d" % 32*24*60, cols="%d" % len(Row))
            # would be nice to give them a color
            ID['cur_sheet'].append_rows(Row)
        except:
            MyLogger.log('ERROR','GSPREAD Unable to create new %s sheet in %s.' % (newNme, ID['worksheet'])) 
            Conf['last'] = time() ; Conf['fd'] = 0 ; Conf['waitCnt'] += 1
            if not (Conf['waitCnt'] % 5): Conf['waiting'] *= 2
            raise IOError
            return False
        MyLogger.log('INFO',"Created and can add gspread records to file:" + ID['sheet'])
        Conf['waiting'] = 5 * 30 ; Conf['last'] = 0 ; Conf['waitCnt'] = 0
    return True
    
# add record to the CSV file
def publish(**args):
    global Conf, writer, CSV
    if (not 'output'  in Conf.keys()) or not Conf['output']:
        return False
    for key in ['data','ident']:
        if not key in args.keys():
            MyLogger.log('FATAL',"GSPREAD method: missing argument %s." % key)
    if not 'fd' in Conf.keys(): Conf['fd'] = None
    if not 'last' in Conf.keys():
        Conf['waiting'] = 5 * 30 ; Conf['last'] = 0 ; Conf['waitCnt'] = 0
    if not registrate(args):
        CSV = {}
        if Conf['waitCnt'] <= 5:
            raise IOError
        Conf['output'] = False  # give up
        MyLogger.log('ERROR',"GSPREAD method spreadsheet creation/opening.")
        return False
    ID = CSV[args['ident']['serial']]
    if (not 'cur_sheet' in ID.keys()) or (not ID['cur_sheet']):
        MyLogger.log('ERROR',"GSPREAD method spreadsheet creation/opening.")
        return False
    try:
        Row = []
        for Fld in args['ident']['fields']:
            if type(args['data'][Fld]) is list:
                for i in args['data'][Fld]:
                    Row.append(i)
            elif Fld == 'time':     # convert UNIX birth time to local time string
                Row.append(datetime.datetime.fromtimestamp(args['data'][Fld]).strftime("%Y-%m-%d %H:%M:%S"))
            else:
                Row.append(args['data'][Fld])
        ID['cur_sheet'].append_rows(Row)
        ID['last'] = int(time())
    except IOError:
        CSV['ID']['auth'].close(CSV['ID']['worksheet'])
        CSV = {}
        raise IOError
        return False
    except:
        MyLogger.log('ERROR',"CSVrecord error in %s, timestamp: %s" % (ID['cur_name'], args['data']['time']) )
        return False
    MyLogger.log('DEBUG',"CSVrecord in %s, timestamp: %s" % (ID['cur_name'], args['data']['time']) )
    Conf['waiting'] = 5 * 30 ; Conf['last'] = 0 ; Conf['waitCnt'] = 0
    return True
    
