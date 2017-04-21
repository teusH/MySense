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

# $Id: MyRegression.py,v 1.13 2017/04/19 15:28:01 teus Exp teus $

""" Create and show best fit for two columns of values from database.
    Use guessed sample time (interval dflt: auto detect) for the sample.
    Print best fit polynomial graph up to order (default linear) and R-squared
    Show the scatter graph and best fit graph (default: off).
    Database table/column over a period of time.
    Database credentials can be provided from command environment.
    Script uses: numpy package and matplotlib from pyplot.
"""
progname='$RCSfile: MyRegression.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.13 $"[11:-2]

try:
    import sys
    import os
    import mysql
    import mysql.connector
    import datetime
    import math
    import re
    import subprocess
    from time import time
    import numpy as np
except ImportError as e:
    sys.exit("One of the import modules not found: %s" % e)

# global variables can be overwritten from command line
# database access credentials
net = {
        'hostname': 'lunar',
        'user': 'teus',
        'password': 'acacadabra',
        'database': 'luchtmetingen',
        'port': 3306
    }
# database identifiers
# first range/array of regression values (second wil be calibrated against this one)
table1 = { 'name': 'BdP_8d5ba45f', 'column': 'pm_25', 'type': 'Dylos DC1100' }
# second (Y) range/array of regression values
table2 = { 'name': 'BdP_3f18c330', 'column': 'pm25', 'type': 'Shinyei PPD42NS' }
# period of time for the regression values
timing = { 'start': time() - 24*60*60, 'end': time() }

interval = None # auto detect interval from database time values
order = 1       # best fit polynomial, order: default 1: linear regression graph
show = False    # show the scatter graph and regression polynomial best fit graph
normMinMax = False    # transform regression polynomial best fit graph to [0,1] space
normAvgStd = False    # transform regression polynomial best fit graph to [-1,1] space

def db_connect(net):
    for M in ('user','password','hostname','database'):
        if (not M in net.keys()):
            sys.exit("Please provide credential %s" % M)
    try:
        DB = mysql.connector.connect(
                charset='utf8',
                user=net['user'],
                password=net['password'],
                host=net['hostname'],
                port=net['port'],
                database=net['database'])
    except:
        sys.exit("Unable to connect to database %s on host %s" %(net['database'],net['hostname']))
    return DB

def db_query(db,query,answer):
    """ database query """
    try:
        c = db.cursor()
        c.execute (query)
        if answer:
            return c.fetchall()
        else:
            db.commit()
    except:
        sys.exit("Database query \"%s\" failed with:\ntype: \"%s\"\nvalue: \"%s\"" %(query,sys.exc_info()[0],sys.exc_info()[1]))
    return True

# get the most frequent interval timing
# outliers are those with more as one hour or less as one minute
def getInterval(arr, amin = 60, amax = 60*60):
    ivals = []
    for iv in range(0,len(arr)-1):
        diff = abs(arr[iv+1][0]-arr[iv][0])
        if (diff > amax) or (diff < amin): continue
        ivals.append(diff)
    n = len(ivals)
    ivals_bar = sum(ivals)/n
    ivals_std = math.sqrt(sum([(iv-ivals_bar)**2 for iv in ivals])/(n-1))
    # print("average sample interval: %3.1f, std dev: %3.1f" % (ivals_bar, ivals_std))
    return int(ivals_bar+ 2* ivals_std)
    

# we could first get average/std dev and omit the outliers
def getColumn(db,table,period, amin = 60, amax = 60*60):
    global interval
    qry = "SELECT UNIX_TIMESTAMP(datum),(if(isnull(%s),'nan',%s)) FROM %s WHERE UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d and %s_valid  order by datum" % \
        (table['column'],table['column'],table['name'],timing['start'],timing['end'],table['column'])
    values = db_query(db,qry, True)
    if len(values) < 5:
        sys.exit("Only %d records in DB %s/%s. Need more values for proper regression." % (len(values),table['name'],table['column']))
    imin = None; imax = None; nr_records = len(values)
    i = len(values)-1
    while ( i >= 0 ):
        try:
            values[i] = (values[i][0],float(values[i][1]))
        except:
            pass
        if math.isnan(values[i][1]):
            values.pop(i)
            i -= 1
            continue
        if i == 0: break
        diff = abs(values[i][0]-values[i-1][0])
        i -= 1
        if imin == None:
            imin = imax = diff
        if (diff >= amin) and (diff <= amax):
            if diff < imin: imin = diff
            if diff > imax: imax = diff
    ival = int(imin+abs(imax-imin)/2)           # half between min and max
    aval = getInterval(values,amin,amax)        # cover 95% of samples
    if (interval == None) or (ival > interval) or (aval > interval):
        interval = aval ; strg = 'avg+2*stddev'
        if ival < aval:
            interval = aval; strg = 'minimal- 50% -maximal'
        print("Auto interval samples is (re)set to %d (%s)" % (interval,strg))
    print("Database table %s column %s: %d db records, deleted %d NaN records." % (table['name'],table['column'],len(values), nr_records-len(values)))
    return values

X = []
Y = []
Xmax = None
Xmax = None
Xmin = None
Xmin = None

def pickValue(arr, time, sample):
    value = 0; cnt = 0
    index = 0
    while (index < len(arr)) and (arr[index][0] < time-sample): 
        index += 1
    if index >= len(arr): return None
    while (index < len(arr)) and (arr[index][0] < time+sample):
        cnt += 1; value += arr[index][1]
        index += 1
    if not cnt: return None
    return value*1.0/cnt

def getArrays(net,table1,table2,timing):
    global X, Y, interval
    DB = db_connect(net)
    DX = getColumn(DB,table1,timing,60,60*60)
    DY = getColumn(DB,table2,timing,60,60*60)
    DB.close()
    X = []; Y = []
    skipped = 0
    for tx in range(0,len(DX)):
        yval = pickValue(DY,DX[tx][0],interval/2)
        if yval == None:
            skipped += 1
            continue
        xval = DX[tx][1]
        X.append(xval)
        Y.append(yval)
    print("Collected %d values in sample time frame (%dm/%ds) for the graph." % (len(X),interval/60,interval%60))
    if skipped:
        print("Skipped %d db records not find Y value in same sample timing." % skipped)
    return

def date2secs(string):
    timing_re = re.compile("^([0-9]+)$")
    if timing_re.match(string): return int(string)
    try:
        number = subprocess.check_output(["/bin/date","--date=%s" % string,"+%s"])
    except:
        sys.exit("unable to find date/time from string %s." % string)
    for i in number.split('\n'):
        if i:
            secs = timing_re.match(i)
            if secs: return int(i)
    sys.exit("unable to find date/time from string %s." % string)
            
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

def get_arguments():
    """ Command line argument roll in """
    import argparse
    global progname
    global net, table1, table2, timing, interval, order, show, normMinMax, normAvgStd
    parser = argparse.ArgumentParser(prog=progname, description='Get from two tables a table for a period of time and calculate the regression', epilog="Environment DB credentials as DBHOST=hostname, DBPASS=acacadabra, DBUSER=username are supported.\nCopyright (c) Behoud de Parel\nAnyone may use it freely under the 'GNU GPL V4' license.")
    parser.add_argument("-H", "--hostname", help="Database host name, default: %s" % net['hostname'], default="%s" % net['hostname'])
    parser.add_argument("--port", help="Database port number, default: %d" % net['port'], default="%d" % net['port'])
    parser.add_argument("-U", "--user", help="Database user name, default: %s" % net['user'], default="%s" % net['user'])
    parser.add_argument("-P", "--password", help="Database password, default: %s" % net['password'], default="%s" % net['password'])
    parser.add_argument("-D", "--database", help="Database name, default: %s" % net['database'], default="%s" % net['database'])
    parser.add_argument("-1", "--table1", help="Database table one/column name, default: %s/%s/%s" % (table1['name'],table1['column'],table1['type']), default="%s/%s/%s" % (table1['name'],table1['column'],table1['type']))
    parser.add_argument("-2", "--table2", help="Database table one/column name, default: %s/%s/%s" % (table2['name'],table2['column'],table2['type']), default="%s/%s/%s" % (table2['name'],table2['column'],table2['type']))
    parser.add_argument("-i", "--interval", help="Interval sample timing (two values in same sample time) in seconds, default: auto detect", default=None)
    parser.add_argument("-t", "--timing", help="Database period of time UNIX start-end seconds or use date as understood by UNIX date command: 'date --date=SOME_DATE_string', default: %d/%d or \"1 day ago/%s\"" % (timing['start'],timing['end'],datetime.datetime.fromtimestamp(timing['start']).strftime('%Y-%m-%d %H:%M')), default="%d/%d" % (timing['start'],timing['end']))
    parser.add_argument("-o", "--order", help="best fit polynomium order, default: linear regression best fit line (order 2)", default=order)
    parser.add_argument("-n", "--norm", help="best fit polynomium min-max normalized to [0,1] space, default: no normalisation", choices=['False','True'], default=normMinMax)
    parser.add_argument("-N", "--NORM", help="best fit polynomium [avg-std,avg+std] normalized to [-1,1] space (overwrites norm option), default: no normalisation", choices=['False','True'], default=normMinMax)
    parser.add_argument("-s", "--show", help="show graph, default: graph is not shown", default=show, choices=['False','True'])
    # overwrite argument settings into configuration
    args = parser.parse_args()
    net['hostname'] = args.hostname
    net['port'] = int(args.port)
    net['user'] = args.user
    net['password'] = args.password
    net['database'] = args.database
    tbl = args.table1.split('/')
    if len(tbl) < 2: sys.exit("table definition should define at least table/column")
    if len(tbl[0]):
        table1['name'] = tbl[0]
    if len(tbl[1]):
        table1['column'] = tbl[1]
    if len(tbl) > 2:
        if len(tbl[2]): table1['type'] = tbl[2]
        else: table1['type'] = 'unknown'
    tbl = args.table2.split('/')
    if len(tbl) < 2: sys.exit("table definition should define at least table/column")
    if len(tbl[0]):
        table2['name'] = tbl[0]
    if len(tbl[1]):
        table2['column'] = tbl[1]
    if len(tbl) > 2:
        if len(tbl[2]): table2['type'] = tbl[2]
        else: table2['type'] = 'unknown'
    timing['start'] = date2secs(args.timing.split('/')[0])
    timing['end'] = date2secs(args.timing.split('/')[1])
    if args.interval != None: interval = int(args.interval)
    order = int(args.order)
    show = bool(args.show)
    normMinMax = bool(args.norm)
    normAvgStd = bool(args.NORM)
    if normAvgStd: normMinMax = False

def regression(z,x):
    y = []
    for i in range(0,len(x)):
        y.append(0.0)
        for j in range(0,len(z)):
            y[i] += z[j]*(pow(x[i],j))
    return y

# ref: https://stackoverflow.com/questions/893657/how-do-i-calculate-r-squared-using-python-and-numpy
# TO DO add higher order polynomial
def get_r2_numpy(x,y,poly):
    xnp = np.array(x, dtype=float)
    ynp = np.array(y, dtype=float)
    xpoly = regression(poly[::-1],x)
    xpoly = np.array(xpoly, dtype=float)
    
    r_squared = 1 - (sum((y-xpoly)**2) / ((len(y)-1) * np.var(y, ddof=1)))
    return r_squared

# only ok for linear
def get_r2_corrcoeff(x,y):
    return np.corrcoef(x,y)[0,1]**2    

# only ok for linear
def get_r2_python(x_list,y_list):
    n = len(x_list)
    x_bar = sum(x_list)/n
    y_bar = sum(y_list)/n
    x_std = math.sqrt(sum([(xi-x_bar)**2 for xi in x_list])/(n-1))
    y_std = math.sqrt(sum([(yi-y_bar)**2 for yi in y_list])/(n-1))
    zx = [(xi-x_bar)/x_std for xi in x_list]
    zy = [(yi-y_bar)/y_std for yi in y_list]
    r = sum(zxi*zyi for zxi, zyi in zip(zx, zy))/(n-1)
    return r**2

# to identify database, tables, columns and period
from_env('DB')          # get DB credentials from command environment
get_arguments()         # get command line arguments

# roll in arrays for regression calculation
getArrays(net,table1,table2,timing)
Xnp = np.array(X, dtype=float)
Xmin = np.nanmin(Xnp); Xmax = np.nanmax(Xnp)
Xavg = np.nanmean(Xnp); Xstd = np.nanstd(Xnp)
Ynp = np.array(Y, dtype=float)
Ymin = np.nanmin(Ynp); Ymax = np.nanmax(Ynp)
Yavg = np.nanmean(Ynp); Ystd = np.nanstd(Ynp)

print('Regression best fit calculation details for: %s versus %s' % (table2['type'],table1['type']))
print('Graph for %s %s/%s <- %s/%s' % (net['database'],table1['name'],table1['column'],table2['name'],table2['column']))
print('Samples period: %s up to %s, interval timing %dm:%ds.' % (datetime.datetime.fromtimestamp(timing['start']).strftime('%b %d %H:%M'),datetime.datetime.fromtimestamp(timing['end']).strftime('%b %d %Y %H:%M'),interval/60,interval%60))
print("%20s/%8s:\tavg=%5.2f, std dev=%5.2f, min-max=(%5.2f, %5.2f)" % (table1['name'],table1['column'],Xavg,Xstd,Xmin,Xmax))
print("%20s/%8s:\tavg=%5.2f, std dev=%5.2f, min-max=(%5.2f, %5.2f)" % (table2['name'],table2['column'],Yavg,Ystd,Ymin,Ymax))


if normMinMax:
    print('Normalisation (min,max):')
    print('\t%s/%s [%6.2f,%6.2f] ->[0,1]' % (table1['name'],table1['column'],Xmin,Xmax))
    print('\t%s/%s [%6.2f,%6.2f] ->[0,1]' % (table2['name'],table2['column'],Ymin,Ymax))
    X = X - Xmin; X /= (Xmax-Xmin)
    Xnp = np.array(X, dtype=float)
    Y = Y - Ymin; Y /= (Ymax-Ymin)
    Ynp = np.array(Y, dtype=float)
if normAvgStd:
    print('Normalisation (avg-stddev,avg+stddev):')
    print('\t%s/%s [%6.2f,%6.2f] ->[-1,+1]' % (table1['name'],table1['column'],Xavg-Xstd,Xavg+Xstd))
    print('\t%s/%s [%6.2f,%6.2f] ->[-1,+1]' % (table2['name'],table2['column'],Yavg-Ystd,Yavg-Ystd))
    X = X - Xavg
    if Xstd > 1.0: X /= Xstd
    Xnp = np.array(X, dtype=float)
    Y = Y - Yavg
    if Ystd > 1.0: Y /= Ystd
    Ynp = np.array(Y, dtype=float)
    # X = X - (Xavg-Xstd); X /= ((Xavg+Xstd)-(Xavg-Xstd))
    # Y = Y - (Yavg-Ystd); Y /= ((Yavg+Ystd)-(Yavg-Ystd))

# calculate the polynomial best fit graph
Z  = np.polyfit(Xnp,Ynp,order,full=True)
Zrev  = np.polyfit(Ynp,Xnp,order,full=True)

# if order == 1:
#     R2 = get_r2_corrcoeff(X,Y)
#     R2 = get_r2_python( list(X),list(Y))
# else:
R2 = get_r2_numpy(X,Y,Z[0])
#R2rev = get_r2_numpy(Y,X,Zrev[0])
# print("Rcond: %1.3e" % Z[4] )
print("Number of samples %s/%s: %d and %s/%s: %d, R²: %6.4f" % (table1['name'],table1['column'],len(X),table2['name'],table2['column'],len(Y),R2))

print("Best fit polynomial regression curve (a0 + a1*X + a2*X**2 + ...): ")
string = ', '.join(["%4.3e" % i for i in Z[0][::-1]])
Xstring = "  %s/%6s (%10s)-> best fit [ %s ]" % (table1['name'],table1['column'],table1['type'],string)
print(Xstring)
stringrev = ', '.join(["%4.3e" % i for i in Zrev[0][::-1]])
Ystring = "  %s/%6s (%10s)-> best fit [ %s ]" % (table2['name'],table2['column'],table2['type'],stringrev)
print(Ystring)

def makeXgrid(mn,mx,nr):
    grid = (mx-mn)/(nr*1.0)
    # return np.linspace(mn, mx, 100)
    return [mn + i*grid for i in range(0,nr+1)]
    
if show:
    import matplotlib.pyplot as plt
    if normMinMax:
        sortedX = makeXgrid(0,1,100)
    elif normAvgStd:
        dev = Xstd
        if Xstd < 1.0: dev = 1.0
        sortedX = makeXgrid((Xmin-Xavg)/dev,(Xmax-Xavg)/dev,100)
    else:
        sortedX = makeXgrid(Xmin,Xmax,100)
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    fig = plt.figure()
    # create some bling bling
    fig.suptitle('Best fit polynomial for %s with %s' % (table2['type'],table1['type']),
        fontsize=9, fontweight='bold')
    ax = fig.add_subplot(111)
    ax.set_title('Regression graph for %s' % net['database'],
        fontsize=9, fontweight='bold')
    title_strg = "%20s %6s: %5.2f(avg), %5.2f(std dev), %5.2f(min), %5.2f(max)" % (table1['name'],table1['column'],
        Xavg,Xstd,Xmin,Xmax)
    title_strg += "\n%20s %6s: %5.2f(avg), %5.2f(std dev), %5.2f(min), %5.2f(max)" %(table2['name'],table2['column'],
        Yavg,Ystd,Ymin,Ymax)
    title_strg += "\nR$^2$=%6.4f, order=%d" % (R2, order)
    if normMinMax: title_strg += ', (min,max)->(0,1) normalized'
    if normAvgStd: title_strg += ', (avg, std dev) -> (0,1) normalized'
    title_strg += "\nCalibration polynomial constants (low order first): "
    title_strg += "\n%s" % Xstring
    title_strg += "\n%s" % Ystring
    fig.text(0.98, 0.015, 'generated %s by pyplot/numpy' % datetime.datetime.fromtimestamp(time()).strftime('%d %b %Y %H:%M'),
        verticalalignment='bottom', horizontalalignment='right',
        transform=ax.transAxes, color='gray', fontsize=8)
    # the graph
    ax.set_title("for period: %s up to %s" % (datetime.datetime.fromtimestamp(timing['start']).strftime('%b %d %H:%M'),datetime.datetime.fromtimestamp(timing['end']).strftime('%b %d %Y %H:%M')),fontsize=8)
    ax.text(0.03, 0.96, title_strg, transform=ax.transAxes, fontsize=8,
        verticalalignment='top', bbox=props)
    ax.set_xlabel('table %s column %s (%s)' %(table1['name'],
        table1['column'],table1['type']), fontsize=8, fontweight='bold')
    ax.set_ylabel('table %s column %s (%s)' %(table2['name'],table2['column'],
        table2['type']), fontsize=8 , fontweight='bold')
    #ax.plot(X, Y, 'o', sortedX, regression(Z[0][::-1],sortedX), 'r',
    #    markersize=3, label='')
    ax.plot(X, Y, 'o', sortedX, np.poly1d(Z[0])(sortedX), 'r',
        markersize=3, label='')
    # plt.legend()
    plt.show()
