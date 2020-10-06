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

# $Id: FilterShow.py,v 2.2 2020/10/06 15:29:37 teus Exp teus $


# To Do: support CSV file by converting the data to MySense DB format
#       table: columns: datum, names (temp, rv, pm10, pm25, no2, o3 etc.)

""" Remove from a set of values the outliers.
    Set will come from MySQL database with air quality values.
    Will try a sliding window of sets in a period of time.
    Will support to validate a new value.
    Script uses Python statistics lib and numpy.
    Input from MySQL database
    Use a simple CSV to MYSQL converter script to be able to
    use this script for values collected in spreadsheet (XLSX)
    or  CVS file formats:
    Columns: datum, <pollutant name>, <name>_valid,...
    Table name format <project>_<serial>.
    Database table/column (sensor name) over a period of time.
    Database credentials can be provided from command environment.
"""
progname='$RCSfile: FilterShow.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.2 $"[11:-2]

try:
    import sys
    import os
    import mysql
    import mysql.connector
    import subprocess
    import datetime
    import math
    import re
    from time import time
    import numpy as np
    from scipy.stats import t, zscore
except ImportError as e:
    sys.exit("One of the import modules not found: %s" % e)
 
debug = False   # debug messages
verbose = True  # be more versatile
reset = True    # revalidate values on every start
RESET = False   # revalidate all values in the command line period
lossy = True    # do not re-valid values in first quarter of window
onlyShow = False # only show chart, do not filter spikes and outliers
showOutliers = False # show also outliers in chart
sigma = 2.0     # graph variance band sigma/propability
threshold = 15  # minimal amound of measurement to act on
cleanup = 2     # cleanup raw values: invalidate NULL and # succeeding static values
cleanup_only = False # do only a cleanup

# global variables can be overwritten from command line
# database access credentials
net = {
        'hostname': 'localhost',
        'user': None,
        'password': 'acacadabra',
        'database': 'luchtmetingen',
        'port': 3306,
        'fd': None
    }
try: net['user'] = os.environ['USER']
except: pass
# start in secs, stop in sec, sliding window in secs (dflt end - stop)
# sliding window will stop-window, step back with 1/2 window size, upto start
# if window has less as "threshold" values the outlier removal is skipped
# start/stop date-time will be converted to secs via Unix date command
period = ['30 days ago','now',None] # last 30 days, window is full period
startPM = None # start time PM NULL correction to overwrite period start
pollutants = [
    # {
    #     'table': None,
    #     'pollutant': None,
    #     'range':[float('nan'),float('nan')]
    # },
    ]

show = False    # show a graph with outliers in different color
colors = [
        ['orange','orangered','red','black'],
        ['lightgreen','green','darkgreen','black'],
        ['blue','azure','darkblue','black'],
        ['purple','lavender','magenta','black'],
        ['lime','yellow','olive','black'],
        ['silver','grey','black','black'],
    ]
MaxPerGraph = 4 # max graphs per subplot
pngfile = None  # show the scatter graph and regression polynomial best fit graph

# Joost RH correction for dust count measurements
JoostFactor = [4.65,-0.65]
JoostCache = None       # speed check up
def Joost(data,args=None):
    global JoostFactor, JoostCache
    if (args == None) or (len(args) < 2): return None
    if (JootsCache == None) or (JoostCache != args):
      if (getUnits(args[0])[0][:2] != 'PM') or (getUnits(args[1])[0][:2] != 'RH'):
        raise ValueError
      JostCache = [args[0],args[1]]
    if (len(data) < 2) or (data[0] == None) or (data[1] == None):
        return None
    if data[1] > 100: data[1] = 100
    if data[1] < 0: data[1] = 0
    return data[0]*(JoosFactor[0]*(100-data[1])**JoostFactor[1])

# raw (outliers) limits for some pollutants, manually set, avoid rough spikes
# 1st: search pattern for DB column names for polAttrs
# 2nd: minimum and maximum for outliers detection
# 3th: unit + class per pollutant for charts
# 4th: database column names translated to something humans understand
# 5th: EU norm daily average and WHO (to be completed)
Norms = ['EU norm','WHO norm'] # norm type
# 6th: array with correction routine and routine arg or None
# To Do: complete with more values
polAttrs = [False,
    ['^[a-su-z]?temp$',                      # temp class
        [-50,50,None],['$^oC$','meteo'],
        'temperature',None,None],
    ['^[a-qs-z]?rv$',                        # humidity class
        [0,100,None],['RH %','meteo'],
        'rel. humidity',None,None],
    ['^[a-km-z]?(luchtdruk|pres(sure)?)$',   # air pressure class
        [800,1200,None],['Hpa','meteo'],
        'air pressure',None,None],
    ['^[a-oq-z]?pm_?10$',                    # dust class PM10
        [0,200,None],['PM $\mu g/m^3$','dust'],
        'PM$_1$$_0$',[32,20],[Joost,['pm','rv']]],
    ['^[a-oq-z]?pm_?25$',                    # dust class PM2.5
        [0,200,None],['PM $\mu g/m^3$','dust'],
        'PM$_2$.$_5$',[25,10],[Joost,['pm','rv']]],
    ['^[a-oq-z]?pm_?1$',                     # dust class PM1
        [0,200,None],['PM $\mu g/m^3$','dust'],
        'PM$_1$.$_0$',[Joost,['pm','rv']]],
    ['^[a-np-z]?[Oo]3',                      # gas classes O3
        [0,250,None],['ozon','gas'],
        'O$_3$',None,None],
    ['^[a-mo-z]?[Nn][Oo]2?',                 # gas classes NOx
        [0,100,None],['stikstofoxides','gas'],
        'NO$_x$',None,None],
    ['^[a-mo-z]?[Nn][Hh]3',                  # gas classes NH3
        [0,100,None],['NH$_3$','gas'],
        'NH$_3$',None,None],
    # next must be general class, catch all
    ['.*',
       None,None,
       'undefined',None,None],
    ]

def eCompile():
    global polAttrs
    if polAttrs[0]: return
    for i in range(1,len(polAttrs)):
        # if len(polAttrs[i]) < 7:
        #     print("WARNING pollutant description incorrect in script \"%s\"" % polAttrs[i][0])
        # while len(polAttrs[i]) < 7:
        #     polAttrs[i].append(None)
        polAttrs[i][0] = re.compile(polAttrs[i][0])
    polAttrs[0] = True

# Grubbs Z-score thresholds
test = 'max'    # either min, max or both (two-tailed)  outliers test
alpha = 0.05    # Grubb significant level
ddof  = 1       # Delta Degree of Freedom (stddev)
# return default [min,max] for a particular sensor type
# nan is not configured, no boundary set
def getTresholds(name):
    global polAttrs
    rts = [float('nan'),float('nan'),None]
    eCompile()
    for i in range(1,len(polAttrs)):
        if polAttrs[i][0].match(name):
           if len(polAttrs[i]) < 2: return rts
           if polAttrs[i][1] == None:
              return rts
           return polAttrs[i][1]
    return rts  # should not happen

# next needed in the show charts
# To Do: units may differ: ug/m3, mV, KOhm, pcs/liter, pcs/m3, pcs/ft2, etc.
# used in chart labels
subcharts = [] # collect nr of subcharts
# get on pol name array with units and class name
def getUnits(name):
    global polAttrs, subcharts
    rts = None # default
    eCompile()
    for i in range(1,len(polAttrs)):
        if polAttrs[i][0].match(name):
            if len(polAttrs[i]) < 3: return rts
            if polAttrs[i][2] != None:
                rts = polAttrs[i][2]
            if not rts in subcharts:
                subcharts.append(rts)
            break
    return rts # may not happen

# get on pol name a human understandable full name
def getName(name):
    global polAttrs
    rts = name # the default
    eCompile()
    for i in range(1,len(polAttrs)-1):
        if polAttrs[i][0].match(name):
            if len(polAttrs[i]) < 4: return rts
            if polAttrs[i][3]:
                rts = polAttrs[i][3]
            break
    return rts

# get on pol name an array with EU, WHO pollutant norm
def getNorm(name):
    global polAttrs
    rts = [None,None]
    eCompile()
    for i in range(1,len(polAttrs)-1):
        if polAttrs[i][0].match(name):
            if len(polAttrs[i]) < 5: return rts
            if polAttrs[i][4]:
                rts = polAttrs[i][4]
            break
    return rts

# NULL correction routine
# use: getCor(name)[0](value,args=getCor(name)[1])
def Null(value, args=None):
    return value

# get on pol name an array: correction routine and routine arguments
# in script use: getCor(name)[0](value,args=getCor(name)[1])
def getCor(name):
    global polAttrs
    rts = [None,[]]
    eCompile()
    for i in range(1,len(polAttrs)-1):
        if polAttrs[i][0].match(name):
            if len(polAttrs[i]) < 6: return rts
            if polAttrs[i][5]:
                rts = polAttrs[i][5]
            break
    return rts

# try to combine charts with same type (meteo, dust, ...)
# and use left and right y-axis (max 2 in one chart)
def chartCombine():
    global subcharts
    from operator import itemgetter # , attrgetter
    subcharts = sorted(subcharts,key=itemgetter(1,0))
    newCharts = []
    for item in subcharts:
        fndi = False
        for i in range(0,len(newCharts)):
            if item[1] != newCharts[i][0][1]: continue
            for j in range(0,2):
                if item == newCharts[i]:
                    fndi = True; break
                if len(newCharts[i]) < 2:
                    newCharts[i].append(item)
                    fndi = True; break
        if not fndi: newCharts.append([item])
    return newCharts
    
def db_connect(db=net):
    if db['fd']: return
    for M in ('user','password','hostname','database'):
        if (not M in net.keys()):
            if M == 'database' and resource['type'] != 'mysql': continue
            sys.exit("Please provide access credential %s" % M)
    try:
        db['fd'] = mysql.connector.connect(
            charset='utf8',
            user=db['user'],
            password=db['password'],
            host=db['hostname'],
            port=db['port'],
            database=db['database'])
    except:
        db['fd'] = None
        raise IOError("Unable to connect to database %s on host %s" %(db['database'],db['hostname']))
    return True

def db_query(query,answer,db=net):
    if not db['fd']: db_connect(db)
    """ database query """
    try:
        c = db['fd'].cursor()
        c.execute (query)
        if answer:
            return c.fetchall()
        else:
            db['fd'].commit()
    except:
        raise ValueError("Database query \"%s\" failed with:\ntype: \"%s\"\nvalue: \"%s\"" %(query,sys.exc_info()[0],sys.exc_info()[1]))
    return True

checked = {} # cache search requests
# do some check if table and columns exists in DB, and count valids or all
def Check(table,pollutant,period=None, valid=True,db=net):
    global debug, verbose, threshold
    if not table in checked.keys():
        if not table in [str(r[0]) for r in db_query("SHOW TABLES", True,db=db)]:
            print("Table with name \"%s\" does not exists in DB." % table)
            return None
        else:
            checked['table'] = []
    if not len(checked['table']):
        for col in db_query("DESCRIBE %s" % table,True,db=db):
            fnd = False
            for item in ['_valid','id','datum']:
                if str(col[0]).find(item) >= 0:
                    fnd = True; break
            if fnd: continue
            checked['table'].append(str(col[0]))
    if not pollutant in checked['table']:
        print("Pollutant (column) \"%s\" in table %s does not exists." % (pollutant,table))
        return None
    if not period: return True
    valued = 'NOT ISNULL(%s)' % pollutant
    if valid: valued += ' AND %s_valid' % pollutant
    qry = "SELECT COUNT(%s) FROM %s WHERE UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d AND %s" % \
        (pollutant, table, period[0], period[1], valued)
    cnt = db_query(qry, True, db=db)
    if (cnt[0][0] < threshold):
        if debug:
          print("Table %s / column %s not minimal %d values in the (window) period." % (table, pollutant,cnt[0][0]), threshold)
        return 0
    return cnt[0][0]

# search for ranges of static values in array (highest date first) of Posix dates and values
# returns an array of start/end/static values
def FindStatics(records, length=5):
    Rslt = []; cnt = 0; value = None; last = None; first = None; value2 = None
    for i in range(0,len(records)):
        if records[i][1] == None or str(records[i][1]).lower() == 'null': continue
        try:
          if value != None:
            changed = value != records[i][1] or i == (len(records)-1)
            if len(records[i]) > 2:
              if value2 != records[i][2]: changed = True
            if changed:
              if cnt >= length:
                Rslt.append((records[i-1][0],last,value,cnt))
                cnt = 0; last = None
              value = None; value2 = None
          if value == None:
              value = records[i][1]; cnt = 0
          if value2 == None and len(records[i]) > 2:
              value2 = records[i][2]
          if records[i][1] == value: cnt += 1
          if cnt == 1: last = records[i][0]
        except: pass
    return Rslt

# an awffull hack to avoid PM values marked as not valid if mass conversion fails
def AdjustPM( table, pollutant, periodStrt, periodEnd, db=net):
    global verbose, startPM, adjustPM

    if not adjustPM: return False # adjust only when enabled by argument
    if not pollutant.lower() in ['pm1','pm25','pm10']: return False
    rts = db_query("SHOW COLUMNS FROM %s like '%s'" % (table,pollutant + '_cnt'),True, db=db)
    if not rts or not rts[0]: return False
    rts = db_query("SELECT count(datum) FROM %s WHERE UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %s AND ISNULL(%s) AND NOT ISNULL(%s_cnt)" % (table,startPM if startPM else periodStrt,periodEnd,pollutant,pollutant), True, db=db)
    if not rts or not rts[0][0]: return False
    if verbose:
        print("%d %s Null measurements set to 0.013 and valid in this period started from %s." % (rts[0][0],pollutant,datetime.datetime.fromtimestamp(startPM if startPM else periodStrt).strftime('%d %b %Y %H:%M')))
    db_query("UPDATE %s SET %s = 0.013, %s_valid = 1 WHERE UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %s AND ISNULL(%s) AND NOT ISNULL(%s_cnt)" % (table,pollutant,pollutant,startPM if startPM else periodStrt,periodEnd,pollutant,pollutant), False, db=db)
    return True

# invalidate cel value if values are NULL or are static (failing)
# 
def rawCleanUp(table, pollutants,period,cleanup=3,db=net):
    global debug, verbose
    if (period[1]-period[0]) > (cleanup+2)*7*24*3600:
        subperiod = [0,0]
        try:
          subperiod[0] = period[0]; subperiod[1] = period[0]+cleanup*7*24*3600
          rawCleanUp(table, pollutants,subperiod,cleanup=cleanup,db=net)
          subperiod[0] = period[0]+cleanup*7*24*3600-2*24*3600; subperiod[1] = period[1]
          return rawCleanUp(table, pollutants,subperiod,cleanup=cleanup,db=net)
        except: return False
    for pollutant in pollutants:
      if pollutant.lower() in ['pm1','pm25','pm10']: # hack
        AdjustPM(table,pollutant,period[0],period[1],db=db)
      qry = 'SELECT count(*) FROM %s WHERE UNIX_TIMESTAMP(datum)>= %d AND UNIX_TIMESTAMP(datum) <= %d AND isnull(%s) AND %s_valid' % \
        (table, period[0], period[1], pollutant, pollutant)
      totalNulls = db_query(qry,True, db=db)[0][0]
      if debug:
        print("Table %s, column %s, period %s up to %s has %d NULL values" % \
            (table, pollutant, \
            datetime.datetime.fromtimestamp(period[0]).strftime('%d %b %Y %H:%M'), \
            datetime.datetime.fromtimestamp(period[1]).strftime('%d %b %Y %H:%M'), \
            totalNulls))
      if totalNulls:
        qry = 'UPDATE %s SET %s_valid = 0 WHERE isnull(%s) AND UNIX_TIMESTAMP(datum)>= %d AND UNIX_TIMESTAMP(datum) <= %d AND %s_valid' % \
            (table, pollutant, pollutant, period[0], period[1], pollutant)
        if not db_query(qry,False,db=net): return False
      # search for static values in this period
      qry = 'SELECT count(%s), min(UNIX_TIMESTAMP(datum)), max(UNIX_TIMESTAMP(datum)) FROM %s WHERE NOT isnull(%s) AND UNIX_TIMESTAMP(datum)>= %d AND UNIX_TIMESTAMP(datum) <= %d' % \
        (pollutant, table, pollutant, period[0], period[1])
      total = db_query(qry, True, db=db)
      if not len(total) or not len(total[0]) or int(total[0][0]) < 15:
        return True # not enough values
      # search candidate for static value
      cnt = 0; new = 0; total = total[0]

      # here we add another value of the same sensor to improve the static test
      secondS = ''
      if pollutant ==  'temp': secondS = ', rv'
      elif pollutant ==  'rv': secondS = ', temp'
      elif pollutant ==  'pm10': secondS = ', pm25'
      elif pollutant ==  'pm25': secondS = ', pm10'
      qry = 'SELECT UNIX_TIMESTAMP(datum), %s%s FROM %s WHERE NOT isnull(%s) AND UNIX_TIMESTAMP(datum)>= %d AND UNIX_TIMESTAMP(datum) <= %d ORDER BY datum DESC' % \
        (pollutant, secondS, table, pollutant, total[1], total[2])
      records = db_query(qry, True, db=db)
      if debug:
        print("Static values search in period: %s up to %s with %d not null values." % (datetime.datetime.fromtimestamp(total[1]).strftime('%d %b %Y %H:%M'),datetime.datetime.fromtimestamp(total[2]).strftime('%d %b %Y %H:%M'), total[0]) )
      # length is arbitrary: static in 10*interval time (ca 2 hours) or when 2 sensors 5*interval
      StatVals = FindStatics(records,length=(5 if len(records[0])>2 else 10))
      # returns [(first,last,value,cnt), ... ]
      for CntDt in StatVals:
        if CntDt[3] < 5: continue # probably no static value in this range
        #if debug:
        #  print("Period with last date %s: %d static values with value %s" % (datetime.datetime.fromtimestamp(CntDt[1]).strftime('%d %b %Y %H:%M'),CntDt[3], str(CntDt[2])))
        qry = 'SELECT count(%s) FROM %s WHERE NOT isnull(%s) AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d AND %s = %s AND %s_valid' % \
            (pollutant, table, pollutant, CntDt[0], CntDt[1], pollutant, str(CntDt[2]), pollutant)
        Ncnt = 0
        try: Ncnt =  db_query(qry, True, db=db)[0][0]
        except: pass
        #if debug:
        #  print("Found in total %d (%d marked as valid) static values (%s), next period at date %s" % (CntDt[3],Ncnt,str(CntDt[2]),datetime.datetime.fromtimestamp(CntDt[0]).strftime('%d %b %Y %H:%M')))
        new += Ncnt; cnt += CntDt[3]
        if Ncnt:
          qry = 'UPDATE %s SET %s_valid = 0 WHERE NOT isnull(%s) AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d AND %s = %s AND %s_valid' % \
                (table, pollutant, pollutant, CntDt[0], CntDt[1], pollutant, str(CntDt[2]), pollutant)
          db_query(qry, False, db=db)
        else: Ncnt = 0
      if verbose:
        if cnt:
          print("Table %s, column %s, period %s up to %s has %d measurements with %d (%d new) invalidated static values, %d NULL values." % \
            (table, pollutant, \
             datetime.datetime.fromtimestamp(period[0]).strftime('%d %b %Y %H:%M'), \
             datetime.datetime.fromtimestamp(period[1]).strftime('%d %b %Y %H:%M'), \
             total[0],cnt,new,totalNulls))
        else:
          print("Table %s, column %s, period %s up to %s has no static values in the measurements, %d NULL values." % \
            (table, pollutant, \
             datetime.datetime.fromtimestamp(period[0]).strftime('%d %b %Y %H:%M'), \
             datetime.datetime.fromtimestamp(period[1]).strftime('%d %b %Y %H:%M'),totalNulls) )

# invalidate cel value if value not in raw range
def rawInvalid(table,pollutant,period,minimal=float('nan'),maximal=float('nan'),db=net):
    global debug, verbose
    if not Check(table,pollutant,period=period, db=db):
        return False
    update = ''
    if minimal != float('nan'):
        update = '(%s < %f)' % (pollutant,minimal)
    if maximal != float('nan'):
        if update: update += ' OR '
        update += '(%s > %f)' % (pollutant, maximal)
    qry = 'SELECT count(*) FROM %s WHERE UNIX_TIMESTAMP(datum)>= %d AND UNIX_TIMESTAMP(datum) <= %d AND %s_valid' % \
        (table, period[0], period[1], pollutant)
    total = db_query(qry,True, db=db); total = total[0][0]
    if debug:
        print("Table %s, column %s, period %s up to %s has %d values" % \
            (table, pollutant, \
            datetime.datetime.fromtimestamp(period[0]).strftime('%d %b %Y %H:%M'), \
            datetime.datetime.fromtimestamp(period[1]).strftime('%d %b %Y %H:%M'), \
            total))
    if not total: return False
    if update:
        if debug:
            qry = 'SELECT count(*) FROM %s WHERE (%s OR ISNULL(%s)) AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d AND %s_valid' % \
                (table, update, pollutant, period[0], period[1], pollutant)
            cnt = db_query(qry, True, db=db)
            print("Table %s, column %s, period %s up to %s: condition: %s, invalidated in raw way %d values from total of %d values" % \
                (table, pollutant, \
                datetime.datetime.fromtimestamp(period[0]).strftime('%d %b %Y %H:%M'), \
                datetime.datetime.fromtimestamp(period[1]).strftime('%d %b %Y %H:%M'), \
                update, cnt[0][0], total))
        qry = 'UPDATE %s SET %s_valid = 0 WHERE (%s OR ISNULL(%s)) AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d AND %s_valid' % \
            (table, pollutant, update, pollutant, period[0], period[1], pollutant)
        return db_query(qry,False,db=net)
    return False

# collect an array with id's (dates-time) and values from DB
def Zscore(table,pollutant,period,db=net):
    global debug, verbose, threshold
    if not Check(table,pollutant,period=period, db=db):
        return None
    qry = 'SELECT %s FROM %s WHERE UNIX_TIMESTAMP(datum)>= %d AND UNIX_TIMESTAMP(datum) <= %d AND %s_valid' % \
        (pollutant, table, period[0], period[1], pollutant)
    data = db_query(qry, True,db=db)
    if len(data) < threshold and verbose:
        print("Table %s, column %s, period %s upto %s, only %d values. Skipped this subperiod." % \
            (table, pollutant, \
            datetime.datetime.fromtimestamp(period[0]).strftime('%d %b %Y %H:%M'), \
            datetime.datetime.fromtimestamp(period[1]).strftime('%d %b %Y %H:%M'), \
            len(data)))
        return None
    data = np.array([float(data[i][0]) for i in range(0,len(data))])
    result = grubbs(np.array(data),test=test, alpha=alpha, ddof=ddof)
    if result:
        if result['liers']:
            update = '%s < %f OR %s > %f' % \
                (pollutant, result['min'], pollutant, result ['max'])
        elif result['stddev'] == 0.0 and result['valid'] > 3:  # static over the period
            update = '%s  < %f OR %s > %f' % \
                (pollutant, result['min']-0.01, pollutant, result ['max']+0.1)
        else: return False
    else: return False
    if debug:
        print("Table %s, colums %s, period %s up to %s: Grubbs Z-score invalidate %d values from %d values:\n\tmean %.2f stddev %.2f, min %.2f max %.2f." % \
            (table, pollutant, \
            datetime.datetime.fromtimestamp(period[0]).strftime('%d %b %Y %H:%M'), \
            datetime.datetime.fromtimestamp(period[1]).strftime('%d %b %Y %H:%M'), \
            result['liers'], len(data),
            result['mean'], result['stddev'],
            result['min'], result['max']
            ))
    qry = 'UPDATE %s SET %s_valid = 0 WHERE (%s) AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d AND %s_valid' % \
        (table, pollutant, update, period[0], period[1], pollutant)
    return db_query(qry, False, db=db)

# convert date-time to secs
def date2secs(string):
    timing_re = re.compile("^([0-9]+)$")
    string = string.replace('-','/')
    if timing_re.match(string): return int(string)
    try:
        number = subprocess.check_output(["/bin/date","--date=%s" % string,"+%s"])
        number = number.decode('utf-8').strip()
    except:
        sys.exit("Unable to find date/time from string \"%s\"." % string)
    if number:
        secs = timing_re.match(number)
        if secs: return int(number)
    sys.exit("Unable to find date/time from string \"%s\"." % string)

# roll in the definition from environment eg passwords
def from_env(name):
    """ hostname, user credentials can (should) be defined from environment as
        <section name><host|user|pass> e.g. DBHOST, DBUSER, DBPASS
    """
    global net
    for credit in ['hostname','user','password','port']:
        if not credit in net.keys():
            net[credit] = None
        try:
            net[credit] = os.getenv(name.upper()+credit[0:4].upper(),net[credit])
        except:
            pass
    return True

# show sensor types in the DB for the table
def showPols(tbl,db=net):
    print("Table %s has the following sensor colums:" % tbl)
    pols = []
    for col in [str(r[0]) for r in db_query("DESCRIBE %s" % tbl,True,db=db)]:
        fnd = True
        for sub in ['_valid','_ppb','_color','id','datum','rssi','longi','latit','altit']:
            if col.find(sub) >= 0:
                fnd = False; break
        if fnd:
            pols.append(col)
    print("\t%s" % ', '.join(pols))
    try:
      col = db_query("SELECT DATE_FORMAT(min(datum),'%%Y-%%m-%%d %%H:%%i'), DATE_FORMAT(max(datum),'%%Y-%%m-%%d %%H:%%i'), DATEDIFF(max(datum),min(datum)) FROM %s" % tbl, True, db=db)
      print("  Data from %s up to %s (%d days)." % (col[0][0],col[0][1],col[0][2]))
    except: pass

# show table in the database with sensors
def showTables(db=net):
    print("Database %s has following sensor kit  tables (<project>_<serial>):" % db['database'])
    for tbl in [str(r[0]) for r in db_query("SHOW TABLES",True,db=db)]:
        # omit governmental stations
        if not tbl.find('_') >= 0: continue
        fnd = True
        # omit tables which are extentions and intermediate
        # To Do: use Sensors or stations table to filter
        for t in ['datum','day','aqi','Max','Day','lki']:
            if tbl.find('_'+t) > 0:
                fnd = False; break
        if fnd:
            showPols(tbl,db=db)

# check if there are measurements for a pollutant in the period
def checkPollutant(pollutant,period, db=net):
    global threshold
    qry = 'SELECT COUNT(%s) FROM %s WHERE NOT ISNULL(%s) AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d' % \
        (pollutant['pollutant'], pollutant['table'], pollutant['pollutant'], period[0], period[1])
    try:
        cnt = db_query(qry, True, db=db)
        return cnt[0][0] >= threshold
    except: return False

# collect script configuration from command line
def get_arguments():
    global pollutants
    """ Command line argument roll in """
    import argparse
    global progname, debug, verbose, net, period
    global show, pngfile, showOutliers, alpha, ddof, test, lossy
    global reset, RESET, sigma, onlyShow, threshold
    global cleanup, cleanup_only, startPM, adjustPM

    parser = argparse.ArgumentParser(prog=progname, description='''
Get from a database with "pollutant" values the measured (raw) values
over a period of time.
Invalidate the measurements when not in a provided minimum-maximum range.
Invalidate the measurements when NULL or static during the interval of N (dflt 3) weeks.
One may do only a cleanup (invalidate NULL and static values) and avoid other operations.
And next invalidate outliers according to their Z-score (Grubbs).
Each argument defines the table[/pollutant[/minimum:maximum]].

Shorthand for filter argument definitions, e.g.:
ThisProject_Serial1,Serial2/pm10,pm25/2:150,rv/:nan
will filter on table ThisProject_Serial1 and ThisProject_Serial2
for pollutants pm10 dflt outlier range,
pm25 with outlier range 2 - 150, and
rv with outlier range minimum dflt and no maximum.

Command with no arguments will, if possible, provide a list of
MySQL table names (sensorkit names).
With one argument (sensor kit table name) and no pollutant name
the script will list all sensor/pollutant names, sensor types
for that sensor kit.
If minimum or maximum in the argument is provided as "nan",
this particular range is not taken into account.
If no limit range is defined the script will use default values.

The sliding window will be moved by half the window size on
every scan with a next start time. Default on every scan in
the window the measurements after the first quarter will be
re-validated first.
Use the lossy option to indicate that first quarter of the window
the measurements also need to be re-validated on start of the scan.
Note: sliding window is experimental. And can be turned off by
the reset option.

Usage example:
"BdP_12345abcd/pm25/0:250" or "LoPy_1234567a/temp/-40:40"

Copyright (c) Behoud de Parel, 2018
Anyone may use it freely under the GNU GPL V4 license.
Any script change remains free. Feel free to indicate improvements.''')
    parser.add_argument("-H", "--hostname", help="Database host name, default: %s" % net['hostname'], default="%s" % net['hostname'])
    parser.add_argument("--port", help="Database port number, default: DB dfl port", default="3306")
    parser.add_argument("-U", "--user", help="Database user name, default: %s" % net['user'], default="%s" % net['user'])
    parser.add_argument("-P", "--password", help="Database password, default: %s" % net['password'], default="%s" % net['password'])
    parser.add_argument("-D", "--database", help="Database name, default: %s" % net['database'], default="%s" % net['database'])
    parser.add_argument("-s","--start",help="Start of the period to search for outliers, default: 30 days ago. Use date command strings as format.", default="%s" % period[0])
    parser.add_argument("-e","--end",help="End of the period to search for outliers, default: now. Use date command strings as format.", default="%s" % period[1])
    parser.add_argument("-w","--window",help="Sliding window in period. Sliding will be overlapped by half of the window length. Default full period (window = 0). Default format is in hours. Other formats: nPERIOD, where n is count (may be empty for 1), and PERIOD is H[ours], D[ays], W[eeks], M[onths].")
    parser.add_argument("--threshold",help="Minimum amount of measurements to do the statistics on, default: %d." % threshold, default=threshold, type=int)
    parser.add_argument("--alpha",help="Grubb's significant level, default: %f." % alpha, default=alpha, type=float)
    parser.add_argument("--ddof",help="use delta degree of Freedom (N*stddev), default: %f." % ddof, default=ddof, type=float)
    parser.add_argument("--test",help="Grubb's test for min(minimal), max(imal) or two-tailed (both) outliers test, default: %s." % test, default=test, choices=['min','max','two-tailed'])

    parser.add_argument("-c", "--cleanup", help="invalidate all values with NULL values or static values in this period of time. Default: more as %d succeeding static values. Cleanup == 0 will disable invalidation process." % cleanup, default=cleanup, type=int, choices=range(0,11))
    parser.add_argument("-C", "--cleanup_only", help="Only do an invalidate all values with NULL values or static values during interval of %d weeks (> 0). Default: invalidate spikes etc. as well." % cleanup, default=cleanup_only, action='store_true')
    parser.add_argument("-r", "--reset", help="do not re-valid all values in sliding window first. See also the lossy option. Default: re-validate values.", default=reset, action='store_false')
    parser.add_argument("-R", "--RESET", help="re-valid all values in the full period first, default: do not re-validate the measurements.", default=RESET, action='store_true')
    parser.add_argument("-l", "--lossy", help="Turn lossy off. Re-valid all the values in the sliding window period before starting the scan. Default: only re-validate all values from second quarter of time in the sliding window.", default=lossy, action='store_false')
    parser.add_argument("-S", "--show", help="show graph, default: graph is not shown", default=show, action='store_true')
    parser.add_argument("--onlyshow", help="show graph, do not filter spikes nor outliers, default: filter spikes and outliers in database", default=onlyShow, action='store_true')
    parser.add_argument("--sigma", help="show graph with variance sigma. Sigma=0 no variance band is plotted. Default: sigma=%.1f" % sigma, default=sigma, type=float)
    parser.add_argument("-L", "--outliers", help="Do show in graph the outliers, default: outliers are shown", default=showOutliers, action='store_true')
    parser.add_argument("-f", "--file", help="generate png graph file, default: no png", default=pngfile)
    parser.add_argument("--adjustPM", help="Adjust PM mass values NULL to 0.013 in database, default: no adjustment.", default=False, action='store_true')
    parser.add_argument("--startPM", help="Overwrite period start time for PM NULL correction phase to database, default: period start.", default=None)
    parser.add_argument('args', nargs=argparse.REMAINDER, help="<Database table name>/[<pollutant or column name>[/<minimal:maximal>]] ... An empty name: the name of the previous argument will be used. No argument will give overview of available sensor kit table names. <table_name> as argument will print avaialable sensor type names for a table.")
    parser.add_argument("-d","--debug",help="Debugging on. Dflt %d" % debug, default=debug, action='store_true')
    parser.add_argument("-q","--quiet",help="Be silent. Dflt %d" % verbose, default=verbose, action='store_false')
    # overwrite argument settings into configuration
    args = parser.parse_args()
    net['hostname'] = args.hostname
    net['user'] = args.user
    net['password'] = args.password
    net['database'] = args.database
    debug = args.debug
    verbose = args.quiet
    if debug: verbose = True
    period[0] = date2secs(args.start)
    period[1] = date2secs(args.end)
    onlyShow = args.onlyshow
    threshold = args.threshold
    show = args.show
    showOutliers = args.outliers
    alpha = float(args.alpha)
    ddof = float(args.ddof)
    test = args.test
    reset = args.reset
    RESET = args.RESET
    lossy = args.lossy
    sigma = args.sigma
    pngfile = args.file
    cleanup = args.cleanup
    cleanup_only = args.cleanup_only
    if args.startPM:
        startPM = date2secs(args.startPM)
        adjustPM = True
    if args.adjustPM: adjustPM = True
    if pngfile != None: show = True
    if args.window:
        mult = 60*60  # default hours
        args.window = args.window.lower()
        if not args.window[0].isdigit(): args.window = '1' + args.window
        for char in ['h','d','w','m']:
            idx = args.window.find(char)
            if idx < 0: idx = len(args.window); continue
            if char == 'h': mult = 3600; break
            elif char == 'd': mult = 3600*24; break
            elif char == 'w': mult = 3600*24*7; break
            else: mult = 3600*24*30 # 4 weeks
        period[2] = int(args.window[:idx])*mult
    else:
        period[2] = period[1] - period[0]
    if not len(args.args):
        showTables()
        exit(0)
    elif len(args.args[0].split('/')) == 1:
        showPols(args.args[0])
        exit(0)
    
    if verbose and not onlyShow:
        print("Find spikes and outliers. Period: %s upto %s:" % \
            (datetime.datetime.fromtimestamp(period[0]).strftime('%d %b %Y %H:%M'), \
            datetime.datetime.fromtimestamp(period[1]).strftime('%d %b %Y %H:%M')))
    # parse arguments dbtable[/dbcolumn[/[[min]:[max]]]]
    # min/max may have default value 'nan'
    # if empty use definition of previous argument
    for arg in range(0,len(args.args)):
        if not args.args[arg]: continue
        if arg and args.args[arg][0] == '/':
            args.args[arg] = args.args[arg-1][0:args.args[arg-1].find('/')] + args.args[arg]
        # build pollutant: <project>_<serial>[,<serial>...]/<poll>[/min:max][,<poll>[/min:max] ...]
        
        project = '';
        serials = args.args[arg][0:args.args[arg].find('/')]
        polArray = args.args[arg][args.args[arg].find('/')+1:]
        if args.args[arg].find('_') >= 0:
            project = args.args[arg][0:args.args[arg].find('_')+1]
            serials = args.args[arg][args.args[arg].find('_')+1:]
        try:
            serials = serials[:serials.index('/')]
        except:
            pass
        serials = serials.split(',')
        polArray = polArray.split(',')
        # collect work to do in pollutants array
        for serial in serials:
            for pol in polArray:
                pols = '%s%s/%s' % (project,serial,pol)
                pols = pols.split('/')
                if (not len(pols)) or (not pols[0]) or (not pols[1]):
                    break
                pollutants.append({ 'table': None, 'pollutant': None, 'range':[float('nan'),float('nan')], 'unit': None})
                pollutants[-1]['table'] = pols[0]
                pollutants[-1]['pollutant'] = pols[1]
                pollutants[-1]['units'] = getUnits(pols[1])
                if len(pols) < 3: pols.append(':')
                if not pols[2]: pols[2] = ':'
                if pols[2].find(':') < 0: pols[2] += ':'
                minmax = pols[2].split(':')
                for i in range(0,2):
                    if not minmax[i]:
                       minmax[i] = getTresholds(pollutants[-1]['pollutant'])[i]
                    try: minmax[i] = float(minmax[i])
                    except: minmax[i] = float('nan')
                pollutants[-1]['range'] = minmax[:2]
                if checkPollutant(pollutants[-1],period):
                  if verbose and not onlyShow:
                    print("\ttable %s pollutant '%s'\toutliers range [%f - %f]" % (pollutants[-1]['table'],pollutants[-1]['pollutant'],pollutants[-1]['range'][0],pollutants[-1]['range'][1]))
                else:  # for some reason no data for this pollutant
                  if verbose:
                    print("\tpollutant '%s': no measurements for this period. Skipped." % pols[1])
                    pollutants.pop() 
        # next argument
    return

# https://stackoverflow.com/questions/11686720/is-there-a-numpy-builtin-to-reject-outliers-from-a-list
# detect outliers with a modified Z-score
def reject_outliers(X, m=2.0):
    '''
    performs the original modified Z-score test
    X : ndarray
    returns the outliers
    
    the simple algorithm uses mean-m*s < Xi < mean + m*s
    '''
    dist = np.abs(X-np.median(X))
    mdev = np.median(dist)
    S = dist/mdev if mdev else 0.0
    return X[S >= m]

# detect outliers in a numpy array
# from: http://codegist.net/snippet/python/grubbspy_leggitta_python
def grubbs(X, test='two-tailed', alpha=0.05, ddof=1):
 
    '''
    Performs Grubbs' test for outliers recursively until the null hypothesis is
    true.
 
    Parameters
    ----------
    X : ndarray
        A numpy array to be tested for outliers.
    test : str
        Describes the types of outliers to look for. Can be
        'min' (look for small outliers),
        'max' (look for large outliers), or
        'two-tailed' (look for both).
    alpha : float
        The significance level.
 
    Returns
    -------
    (X : ndarray The original array with outliers removed.)
    outliers : ndarray array of outliers.
    floor: (minimal,maximal) value of array with outliers removed
    '''
 
    if np.min(X) == np.min(X):
        return { # static values give stddev == 0 and so division error
                'valid': len(X),
                'liers': 0,
                'min': np.min(X),
                'max': np.max(X),
                'mean': np.mean(X),
                'stddev': 0.0,
                }
    try:
        Z = zscore(X, ddof=ddof)  # Z-score
    except: return { # static values give stddev == 0 and so division error
                'valid': len(X),
                'liers': 0,
                'min': np.min(X),
                'max': np.max(X),
                'mean': np.mean(X),
                'stddev': 0.0,
                }
    N = len(X)  # number of samples
 
    # calculate extreme index and the critical t value based on the test
    if test == 'two-tailed':
        extreme_ix = lambda Z: np.abs(Z).argmax()
        t_crit = lambda N: t.isf(alpha / (2.*N), N-2)
    elif test == 'max':
        extreme_ix = lambda Z: Z.argmax()
        t_crit = lambda N: t.isf(alpha / N, N-2)
    elif test == 'min':
        extreme_ix = lambda Z: Z.argmin()
        t_crit = lambda N: t.isf(alpha / N, N-2)
    else:
        raise ValueError("Test must be 'min', 'max', or 'two-tailed'")
 
    # compute the threshold
    thresh = lambda N: (N - 1.) / np.sqrt(N) * \
        np.sqrt(t_crit(N)**2 / (N - 2 + t_crit(N)**2))
 
    # create array to store outliers
    outliers = np.array([])
 
    # next may need a cheaper way to get a result
    # loop throught the array and remove any outliers
    while abs(Z[extreme_ix(Z)]) > thresh(N):
 
        # update the outliers
        outliers = np.r_[outliers, X[extreme_ix(Z)]]
        # remove outlier from array
        X = np.delete(X, extreme_ix(Z))
        # repeat Z score
        try:
            Z = zscore(X, ddof=ddof)
        except:
            print("ERROR in grubbs/zscore call (stddev == 0)\n")
            break
        N = len(X)
 
    return {
        'valid': len(X),
        'liers': len(outliers),
        'min': np.min(X),
        'max': np.max(X),
        'mean': np.mean(X),
        'stddev': np.std(X,ddof=1),
        }

# set for this pollutant in this period all values valid
def resetValid(table,pollutant,period,db=net, lossy=True):
    global debug, verbose, reset
    if not Check(table,pollutant, db=db):
        return None
    update = ''
    if not reset: return True
    start = period[0]
    if lossy: start = period[0]+int((period[1]-period[0])/4)
    if debug:
        qry = 'SELECT COUNT(*) FROM %s WHERE NOT %s_valid AND NOT ISNULL(%s) AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d' % \
        (table, pollutant, pollutant, start, period[1])
        cnt = db_query(qry, True, db=db)
        print("Table %s, column %s, in previous period %s up to %s: revalidated %d cell(s)" % \
            (table, pollutant, \
            datetime.datetime.fromtimestamp(start).strftime('%d %b %Y %H:%M'), \
            datetime.datetime.fromtimestamp(period[1]).strftime('%d %b %Y %H:%M'), \
            cnt[0][0]))
    qry = 'UPDATE %s SET %s_valid = 1 WHERE NOT ISNULL(%s) AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d' % \
        (table, pollutant, pollutant, start, period[1])
    return db_query(qry, False, db=db)

def doStatistics(table,pollutant,period,db=net,string=''):
    global verbose, debug
    if not verbose: return
    if not Check(table,pollutant,period=period,db=db):
        print("Database table %s has no measurements for pollutant %s in the provided period of time." % \
            (table,pollutant))
        return
    qry = "SELECT count(%s) FROM %s WHERE not %s_valid AND NOT ISNULL(%s) AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d" % \
        (pollutant, table, pollutant, pollutant, period[0],period[1])
    invalids = db_query(qry, True, db=db)
    qry = "SELECT count(%s), AVG(%s), STDDEV(%s), MIN(%s), MAX(%s) FROM %s WHERE %s_valid AND NOT ISNULL(%s) AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d" % \
        (pollutant,pollutant,pollutant,pollutant,pollutant, \
        table, pollutant, pollutant, period[0],period[1])
    rslt = db_query(qry, True, db=db)
    rslt = {
        'invalids': invalids[0][0],
        'count': rslt[0][0],
        'avg': rslt[0][1], 'stddev': rslt[0][2],
        'min': rslt[0][3], 'max': rslt[0][4],
        }
    if verbose and rslt['count']:
        pol = pollutant
        if pol == 'pm25': pol = 'pm2.5'
        if pol == 'rv': pol = 'rh'
        if verbose and (not debug) and rslt['invalids']:
          print("Statistical period overview %s\n    for '%s' from table %s:\n\tnr invalid values %d, nr valid values %d, average %.2f, std dev %.2f,\n\tminimum %.2f, maximum %.2f." % \
            (string, pol, table, rslt['invalids'],
            rslt['count'], rslt['avg'], rslt['stddev'],
            rslt['min'], rslt['max']))
        elif debug:
          print("Statistical period overview %s\n    for %s from table %s:\n\tnr invalid values %d, nr valid values %d, average %.2f, std dev %.2f,\n\tminimum %.2f, maximum %.2f." % \
            (string, pol.upper(), table, rslt['invalids'],
            rslt['count'], rslt['avg'], rslt['stddev'],
            rslt['min'], rslt['max']))
    if string: return None
    return rslt

# remove outliers in a table for a pollutant within a period
def FindOutliers(pollutant,db=net):
    global verbose, debug, period, lossy, RESET, cleanup, cleanup_only
    if (not pollutant['table']) or (not pollutant['pollutant']): return
    doStatistics(pollutant['table'],pollutant['pollutant'],period=period,db=db,string='(before outliers removal)')
    freq = int(int(period[1]-period[0])/(int(period[2]/2)))
    period[0] += int(period[1]-period[0])%freq
    strt = period[0]; periods = []
    for i in range(0,freq-1):
        if strt + 10*60*60 > period[1]: break
        periods.append([strt,strt+period[2]])
        strt += int(period[2]/2)
        if period[1]-10*60*60 < strt < period[1]:
            strt = period[1] - int((period[2]+1)/2)
    # avoid too much shaving of values
    # set all values as valid in the main period
    if RESET:
        resetValid(pollutant['table'], pollutant['pollutant'], period, db=db, lossy=False)
    elif lossy:
        resetValid(pollutant['table'], pollutant['pollutant'], period, db=db, lossy=lossy)
    for i in range(0,len(periods)):
        if i:
            # set pollutant_valid = 1 in this start+half period, end period
            resetValid(pollutant['table'], pollutant['pollutant'], [periods[i][0],periods[i-1][1]], db=db, lossy=lossy)
        if cleanup:
          rawCleanUp(pollutant['table'], [pollutant['pollutant']],periods[i],cleanup=cleanup,db=db)
          if cleanup_only: continue
        if not rawInvalid(pollutant['table'],pollutant['pollutant'],periods[i],minimal=pollutant['range'][0],maximal=pollutant['range'][1],db=db):
            if debug:
                print("Skip table %s column %s for this period." % \
                    (pollutant['table'],pollutant['pollutant']))
            continue
        Zscore(pollutant['table'],pollutant['pollutant'],periods[i],db=db)
    doStatistics(pollutant['table'],pollutant['pollutant'],period=period,db=db,string='(after outliers removal)')

def PlotConvert(data):
    dates = [data[i][0] for i in range(0,len(data))]
    values = [float(data[i][1]) for i in range(0,len(data))]
    for i in range(len(data)-1,-1,-1):  # filter out None values
        if data[i][1] == None:
            dates.pop(i); values.pop(i)
    dateconv = np.vectorize(datetime.datetime.fromtimestamp)
    return (dateconv(dates),np.array(values))

def getPlotdata(period, pollutant, db=net):
    global debug, verbose
    table = pollutant['table']
    pol = pollutant['pollutant'] 
    if not Check(table, pol, db=db):
        return None
    # validated values
    qry = "SELECT UNIX_TIMESTAMP(datum), %s FROM %s WHERE %s_valid AND NOT ISNULL(%s) AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d" % \
        (pol, table, pol, pol, period[0], period[1])
    values = db_query(qry, True, db=db)
    update = 'ISNULL(%s)' % pol; supdate = 'NOT ISNULL(%s)' % pol
    if pollutant['range'][0] != float('nan'):
        update += 'OR (%s < %f)' % (pol,pollutant['range'][0])
        supdate += ' AND (%s >= %f)' % (pol,pollutant['range'][0])
    if pollutant['range'][1] != float('nan'):
        update += ' OR (%s > %f)' % (pol, pollutant['range'][1])
        supdate += ' AND (%s <= %f)' % (pol, pollutant['range'][1])
    # values really out of defined range: outliers
    qry = "SELECT UNIX_TIMESTAMP(datum), %s FROM %s WHERE (%s) AND NOT %s_valid AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d" % \
        (pol, table, update, pol, period[0], period[1])
    outliers = db_query(qry, True, db=db)
    # outliers in Z-score: spikes
    qry = "SELECT UNIX_TIMESTAMP(datum), %s FROM %s WHERE %s AND NOT %s_valid AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d" % \
        (pol, table, supdate, pol, period[0], period[1])
    spikes = db_query(qry, True, db=db)
    return [values,spikes,outliers]
    
        
# next routine is not used any longer
# best line fit for array of dates and values
# from: https://stackoverflow.com/questions/22239691/code-for-line-of-best-fit-of-a-scatter-plot-in-python
def BestFit(data,order=1, grid=1):
    dates = [data[i][0] for i in range(0,len(data))]
    values = np.array([float(data[i][1]) for i in range(0,len(data))])
    # determine best fit line
    par = np.polyfit(dates, values, 1, full=True)

    slope=par[0][0]
    intercept=par[0][1]
    xl = [dates[0], dates[-1]]
    # loop in the grid
    yl = [slope*xx + intercept  for xx in xl]
    
    # coefficient of determination
    variance = np.var(values)
    residuals = np.var([(slope*xx + intercept - yy)  for xx,yy in zip(dates,values)])
    Rsqr = np.round(1-residuals/variance, decimals=2)
    # plt.text(.9*max(dates)+.1*min(dates),.9*max(dates)+.1*min(dates),'$R^2 = %0.2f$'% Rsqr, fontsize=30)
 
    # error bounds
    yerr = [abs(slope*xx + intercept - yy)  for xx,yy in zip(dates,values)]
    par = np.polyfit(dates, yerr, 2, full=True)
     
    yerrUpper = [(xx*slope+intercept)+(par[0][0]*xx**2 \
        + par[0][1]*xx + par[0][2]) for xx,yy in zip(dates,values)]
    yerrLower = [(xx*slope+intercept)-(par[0][0]*xx**2 \
        + par[0][1]*xx + par[0][2]) for xx,yy in zip(dates,values)]
    
    # dateconv = np.vectorize(datetime.datetime.fromtimestamp)
    # dates = dateconv(xl)
    # plt.plot(dates, yl, '-'+c)
    # plt.fill_between(dates, yerrLower, yerrUpper, facecolor=c, alpha=alpha)
    ## plt.plot(dates, yerrLower, '--'+c)
    ## plt.plot(dates, yerrUpper, '--'+c)
    return { 
        'Rsqr': Rsqr,
        'x': xl, 'y': yl,
        'eUp': yerrUpper, 'eLo': yerrLower, 
    }

# next routine is not used
# calculate linear regression line
def Trendline(data, order=1, grid=1):
    """Make a line of best fit"""

    dates = [data[i][0] for i in range(0,len(data))]
    if len(dates) <= 1: return None
    minxd = np.min(dates)
    maxxd = np.max(dates)
    if maxxd <= minxd: return None
    values = np.array([float(data[i][1]) for i in range(0,len(data))])

    #Calculate trendline
    coeffs = np.polyfit(dates, values, order)

    # intercept = coeffs[-1]
    # slope = coeffs[-2]
    # power = coeffs[0] if order == 2 else 0

    xl = []; yl = []
    for x in range(minxd,maxxd+1,int((maxxd-minxd)/(grid+1))):
        xl.append(x); yl.append(np.polyval(coeffs,x))
    #yl = power * xl ** 2 + slope * xl + intercept

    #Calculate R Squared
    p = np.poly1d(coeffs)
    ybar = np.sum(values) / len(values)
    ssreg = np.sum((p(dates) - ybar) ** 2)
    sstot = np.sum((values - ybar) ** 2)
    Rsqr = ssreg / sstot

    return { 
        'Rsqr': Rsqr,
        'x': np.array(xl), 'y': np.array(yl),
        'eUp': None, 'eLo': None, 
    }

# create a spline through a set of values
# date original dates, x new dates on regular intervals,
# values, max and minimum values, returns splined values on x
def makeSpline(dates,x,values,floor,ceil):
    from scipy.interpolate import UnivariateSpline
    try:
        spl = UnivariateSpline(dates, values)
    except:
        return np.array(values) # ???
    spl.set_smoothing_factor(0.5)
    d = spl(x); p = []
    for i in d: # slice to chart height
        # if i < floor: i = floor
        # if i > ceil: i = ceil
        p.append(i)
    return  np.array(p)

def propability(sigma):
    import scipy.stats
    return round(100*scipy.stats.norm(0,1).cdf(sigma),1)

# plot a spline and variation (sigma) band
# select ROUND((CEILING(UNIX_TIMESTAMP(datum) / 3600) * 3600)) AS timeslice, avg(pol) from table group by timeslice order by datum desc
def plotAverage(pollutant,period,floor,ceil,plt,color='b',interval=3600,db=net, grid=1000, sigma=0, label=''):
    dateconv = np.vectorize(datetime.datetime.fromtimestamp)
    if sigma > 4: sigma = 4
    if sigma < 0: sigma = 0
    
    table = pollutant['table'] ; pol = pollutant['pollutant']
    qry = 'SELECT ROUND((CEILING(UNIX_TIMESTAMP(datum) / %d) * %d)) AS timeslice, AVG(%s), STDDEV(%s) FROM %s WHERE NOT ISNULL(%s) AND %s_valid AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d GROUP BY timeslice ORDER BY datum' % \
        (interval,interval,pol, pol, table, pol, pol, period[0], period[1])
    data = db_query(qry, True, db=db)
    if len(data) < threshold: return False
    spg = (data[-1][0]-data[0][0]+int(grid/2))/grid     # secs per grid 
    data.append((None,None,None))
    x = []; m = []; su = []; sl = []
    for idx in range(0,len(data)):
        if data[idx][1] != None:
            x.append(data[idx][0])
            m.append(float(data[idx][1]))
            if sigma:
                Y  = float(data[idx][1])-sigma*float(data[idx][2])
                # if Y < floor: Y = floor
                sl.append(Y)
                Y = float(data[idx][1])+sigma*float(data[idx][2])
                # if Y > ceil: Y = ceil
                su.append(Y)
            continue
        elif not len(x): continue
        dc = dateconv(x)
        dx = [d for d in range(x[0],x[-1],spg)] 
        if sigma:
            sl = makeSpline(x,dx,sl,floor,ceil)
            su = makeSpline(x,dx,su,floor,ceil)
            plt.fill_between(dateconv(dx), sl, su, where=su >= sl, color='w', facecolor=color, alpha=0.2, interpolate=True, label='')
        m = makeSpline(x,dx,m,floor,ceil)
        plt.plot(dateconv(dx), m, '-', c=color, lw=1, label=label)
        # plot var band
        x = []; m = []; su = []; sl = []; label = ''
    return

# plot a spline and variation band
# select ROUND((CEILING(UNIX_TIMESTAMP(datum) / 3600) * 3600)) AS timeslice, avg(pol) from table group by timeslice order by datum desc
def plotSpline(data,plt,color='b',grid=3600):
    from scipy.interpolate import UnivariateSpline
    dates = [data[i][0] for i in range(0,len(data))]
    if len(dates) <= 5: return False
    values = np.array([float(data[i][1]) for i in range(0,len(data))])
    dateconv = np.vectorize(datetime.datetime.fromtimestamp)
    for idx in range(0,len(dates)):
        x = []; y = []; i = idx
        while (i+1 < len(dates)) and (dates[i+1]-dates[i] < grid):
            x.append(dates[i]); y.append(values[i]); i += 1
        idx = i
        if len(x) < 10: continue
        try:
            spl = UnivariateSpline(x, y)
        except:
            continue
        spl.set_smoothing_factor(0.5)
        xs = np.linspace(x[0], x[-1], int(float(x[-1]-x[0])/(dates[-1]-dates[1])*1000.0))
        plt.plot(dateconv(xs), spl(xs), c=color, lw=1)
    return True


# plot a spline of corrected pollutant
# correction = [name,routine] e.g. [['rv'],Cpow]
def showCorrected(plt, data, pollutant, correction, color='b', grid=3600):
    values = correction[1](pollutant['table'],data,correction[0])
    if (values != None) and len(values):
        return plotSpline(values,plt,color==color, grid=grid)
    return False

# show a chart with subcharts with graphs of all pollutants in
# a period of time
def CreateGraphs(period, pollutants, db=net):
    global debug, verbose, file, colors, sigma
    import matplotlib.pyplot as plt
    from matplotlib import gridspec
    import matplotlib.dates as mdates
    from matplotlib.dates import MO, TU, WE, TH, FR, SA, SU
    global subcharts, colors, Norms
    interval = 60*60 # average calculation interval in secs

    periodStrt = datetime.datetime.fromtimestamp(period[0]).strftime('%d %b %Y %H:%M')
    periodEnd = datetime.datetime.fromtimestamp(period[1]).strftime('%d %b %Y %H:%M')
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    #Width = 7.5; Height = 5
    # fig = plt.figure(tight_layout=True, figsize=(Width,Height))
    fig = plt.figure(tight_layout=True)
    # fig, ax = plt.subplots()
    # left=0.1, bottom=0.1, right=0.97, top=0.93, wspace=0.25, hspace=0.25
    # fig.subplots_adjust(top=0.93, bottom=0.5, left=0.2, right=0.2)
    # create some bling bling
    #fig.suptitle('Data from %s, best fit polynomial for type(s): %s' % (net['database'],', '.join(set([elmt['type'] for elmt in sensors]))),
    #    fontsize=9, fontweight='bold')

    months = mdates.MonthLocator()
    days = mdates.DayLocator()  # every day
    hours = mdates.HourLocator(interval=4)  # every hour
    weeks = mdates.WeekdayLocator(byweekday=SU)  # every week
    Fmt = mdates.DateFormatter('%-d %b')

    plt.suptitle("Chart with pollutants scatter graphs with spikes (Z-score) and outiers (min-max limit)", y=1.05, fontsize=8)
    minDate = time(); maxDate = 0
    projects = {};
    # combine gaphs per type of pollutants in one subchart
    # To Do: e.g. if defined RH,
    #        apply on dust measurement the Joost correction factor
    ax = []
    # newcharts from subcharts
    subcharts = chartCombine() # create subchart [[l1,r1],[l2,r2],...]
    colId = len(colors)-1; fndGraph = False
    for subchrt in range(0,len(subcharts)):
      ax.append([None,None]); fnd = False
      handles = []; labels = [] # collect legend for this subchart
      for Y in range(0,len(subcharts[subchrt])):
        if (not Y) and (not subchrt):
          ax[subchrt][Y] = plt.subplot2grid((len(subcharts),1), (subchrt,0), rowspan=1, colspan=1)
        elif not Y:
          ax[subchrt][Y] = plt.subplot2grid((len(subcharts),1), (subchrt,0), rowspan=1, colspan=1, sharex=ax[0][0])
        else: ax[subchrt][Y] = ax[subchrt][0].twinx()
        ax[subchrt][Y].set_ylabel(subcharts[subchrt][Y][1]+' '+subcharts[subchrt][Y][0])
        ax[subchrt][Y].grid(False)
        #hands = []; labs = []
        for idx in range(0,len(pollutants)):
          if pollutants[idx]['units'] != subcharts[subchrt][Y]: continue
          if not pollutants[idx]['table'] in projects.keys():
            projects[pollutants[idx]['table']] = []
          if not getName(pollutants[idx]['pollutant']) in projects[pollutants[idx]['table']]:
            projects[pollutants[idx]['table']].append(getName(pollutants[idx]['pollutant']))
          (values,spikes,outliers) = getPlotdata(period, pollutants[idx], db=net)
          colId += 1; colId %= len(colors)
          label = '%s' % getName(pollutants[idx]['pollutant'])
          label2 = '%s %d hr%s average and +/-%.1f sigma (%.1f%%)' % (getName(pollutants[idx]['pollutant']),interval/3600,'' if ((interval%3600)/60) == 0 else '%d min' % ((interval%3600)/60), sigma,propability(sigma))
          lab = None; hand = None
          if len(values) > 0:
            try: max = values[-1][0]
            except: max = values[0][0]
            if maxDate < max: maxDate = max
            if minDate > values[0][0]: minDate = values[0][0]
            (dates,Yvalues) = PlotConvert(values)
            ax[subchrt][Y].scatter(dates, Yvalues,marker='.', color=colors[colId][0], label=label)
            #hand, lab = ax[subchrt][Y].get_legend_handles_labels()
            #if label:
            #    labs += label; hands += hand
            plotAverage(pollutants[idx],period,np.min(Yvalues),np.max(Yvalues),ax[subchrt][Y],color=colors[colId][2],interval=interval, db=db, sigma=sigma, label=label2)
            fnd = True
            norm = getNorm(pollutants[idx]['pollutant'])
            for n in range(0,len(norm)):
              try:
                if norm[n] != None:
                    ax[subchrt][Y].axhline(norm[n],c=colors[colId][n],lw=(n+1),ls='dotted',label=(getName(pollutants[idx]['pollutant'])+' '+Norms[n]))
                    # ax[subchrt][Y].text(x, norm[n], horizontalalignment='center')
              except: pass
          if len(spikes) > 0:
            try: max = spikes[-1][0]
            except: max = spikes[0][0]
            if maxDate < max: maxDate = max
            if minDate > spikes[0][0]: minDate = spikes[0][0]
            (dates,Yvalues) = PlotConvert(spikes)
            ax[subchrt][Y].scatter(dates, Yvalues,marker='o', color=colors[colId][1], label='')
            fnd = True
            ax[subchrt][Y].scatter(dates, Yvalues,marker='.', color=colors[colId][0], label='')
          if showOutliers and (len(outliers) > 0):
            if fnd: label = ''
            try: max = outliers[len(outliers)-1][0]
            except: max = outliers[0][0]
            if maxDate < max: maxDate = max
            if minDate > outliers[0][0]: minDate = outliers[0][0]
            (dates,Yvalues) = PlotConvert(outliers)
            ax[subchrt][Y].scatter(dates, Yvalues,marker='s', color=colors[colId][2], label=label)
            fnd = True
            ax[subchrt][Y].scatter(dates, Yvalues,marker='.', color=colors[colId][0], label='')
        hands, labs = ax[subchrt][Y].get_legend_handles_labels()
        if len(hands):
            handles += hands; labels += labs
        elif verbose and (len(subcharts[subchrt]) < 2): # only once
            print("Found no data to plot for a subchart %s." % subcharts[subchrt][0][1])
      # finish this subchart
      if len(handles):
        ax[subchrt][0].legend(handles,labels,loc=2,fontsize=6, shadow=True, framealpha=0.9, labelspacing=0.3, fancybox=True)
        fndGraph = True
    if not fndGraph:
        print("Could not find measurements in this period. No show.")

        return False
    # format the ticks
    for subchrt in range(0,len(subcharts)):
      if (maxDate-minDate)/(24*60*60) < 4: # month modus
        freq = 1
        ax[subchrt][0].xaxis.set_major_locator(days)
        ax[subchrt][0].xaxis.set_major_formatter(Fmt)
        ax[subchrt][0].xaxis.set_minor_locator(mdates.HourLocator(interval=1))
        # ax.tick_params(direction='out', length=6, width=2, colors='r')
        ax[subchrt][0].xaxis.set_minor_locator(mdates.HourLocator(interval=6))
      elif (maxDate-minDate)/(24*60*60) < 10: # month modus
        freq = 1
        ax[subchrt][0].xaxis.set_major_locator(days)
        ax[subchrt][0].xaxis.set_major_formatter(Fmt)
        ax[subchrt][0].xaxis.set_minor_locator(mdates.HourLocator(interval=3))
        # ax[0].tick_params(direction='out', length=6, width=2, colors='r')
        ax[subchrt][0].xaxis.set_minor_locator(mdates.HourLocator(interval=6))
      elif (maxDate-minDate)/(24*60*60) < 15: # month modus
        freq = 2
        ax[subchrt][0].xaxis.set_major_locator(days)
        ax[subchrt][0].xaxis.set_major_formatter(Fmt)
        ax[subchrt][0].xaxis.set_minor_locator(hours)
      elif (maxDate-minDate)/(24*60*60) < 40: # week modus
        freq = 1
        ax[subchrt][0].xaxis.set_major_locator(weeks)
        ax[subchrt][0].xaxis.set_major_formatter(Fmt)
        ax[subchrt][0].xaxis.set_minor_locator(days)
      elif (maxDate-minDate)/(24*60*60) < 61: # week modus
        freq = 1
        ax[subchrt][0].xaxis.set_major_locator(months)
        ax[subchrt][0].xaxis.set_major_formatter(Fmt)
        ax[subchrt][0].xaxis.set_minor_locator(weeks)
      else:
        freq = 2
        ax[subchrt][0].xaxis.set_major_locator(months)
        ax[subchrt][0].xaxis.set_major_formatter(Fmt)
        ax[subchrt][0].xaxis.set_minor_locator(weeks)
      [label.set_fontsize('x-small') for (i,label) in enumerate(ax[subchrt][0].xaxis.get_ticklabels())]
      [label.set_fontsize('x-small') for (i,label) in enumerate(ax[subchrt][0].yaxis.get_ticklabels())]
      [label.set_rotation(45) for (i,label) in enumerate(ax[subchrt][0].xaxis.get_ticklabels())]
      if len(ax[subchrt][0].xaxis.get_ticklabels()) > 7:
        [l.set_visible(False) for (i,l) in enumerate(ax[subchrt][0].xaxis.get_ticklabels()) if i % freq != 0]
      dateconv = np.vectorize(datetime.datetime.fromtimestamp)
      dates = dateconv([minDate-30*60,maxDate+30*60])
      ax[subchrt][0].set_xlim(dates[0],dates[1])
    if showOutliers:
        plt.title("Measurements: values, spikes, outliers for %s: %s\nin the period %s up to %s" % \
            (pollutants[idx]['table'], ', '.join(projects[pollutants[idx]['table']]), periodStrt, periodEnd), fontsize=8)
    else:
        plt.title("Measurements: values, and spikes (no outliers) for %s: %s\nin the period %s up to %s" % \
            (pollutants[idx]['table'], ', '.join(projects[pollutants[idx]['table']]), periodStrt, periodEnd), fontsize=8)
    plt.grid(True)#, color='g', linestyle='-', linewidth=5)
    fig.text(0.98, 0.015, 'generated %s by pyplot/numpy for MySense' % datetime.datetime.fromtimestamp(time()).strftime('%d %b %Y %H:%M'),
        verticalalignment='bottom', horizontalalignment='right',
        color='gray', fontsize=6)
    plt.xlabel('date/time', fontsize=7)
    # rotates and right aligns the x labels, and moves the bottom of the
    # axes up to make room for them
    fig.autofmt_xdate()
    try:
        if pngfile != None:
            plt.savefig(pngfile, bbox_inches='tight')
        else:
            plt.show()
    except:
        print("Unable to show or store chart.")
        return False
    return True

##################################################
# the main part
if __name__ == "__main__":

    from_env('DB')          # get DB credentials from command environment
    get_arguments()         # get command line arguments
    if not onlyShow:
        for item in pollutants:
            FindOutliers(item,db=net)
    if show or onlyShow: 
        CreateGraphs(period, pollutants, db=net)
    exit(0)

