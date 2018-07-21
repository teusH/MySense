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

# $Id: grubbs.py,v 2.4 2018/07/21 19:49:13 teus Exp teus $


# To Do: support CSV file by converting the data to MySense DB format
#       table: columns: datum, names (temp, rv, pm10, pm25, no2, o3 etc.)

""" Remove from a set of values the outliers.
    Set will come from MySQL database with air quality values.
    Will try a sliding window of sets in a period of time.
    Will support to validate a new value.
    Script uses Python statistics lib and numpy.
    Input from database, spreadsheet (XLSX) and CVS file formats.
    Database table/column (sensor name) over a period of time.
    Database credentials can be provided from command environment.
"""
progname='$RCSfile: grubbs.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.4 $"[11:-2]

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
reset = True    # revalidate cells on every start
RESET = False   # revalidate all cells in the command line period
lossy = True    # do not re-valid cells in first quarter of window
showOutliers = False # show also outliers in chart
sigma = 2.0     # graph variance band sigma/propability

# global variables can be overwritten from command line
# database access credentials
net = {
        'hostname': 'localhost',
        'user': os.environ['USER'],
        'password': 'acacadabra',
        'database': 'luchtmetingen',
        'port': 3306,
        'fd': None
    }

# start in secs, stop in sec, sliding window in secs (dflt end - stop)
# sliding window will stop-window, step back with 1/2 window size, upto start
# if window has less as 15 values the outlier removal is skipped
# start/stop date-time will be converted to secs via Unix date command
period = ['30 days ago','now',None] # last 30 days, window is full period
pollutants = [
    # {
    #     'table': None,
    #     'pollutant': None,
    #     'range':[float('nan'),float('nan')]
    # },
    ]

show = False    # show a graph with outliers in different color
colors = [
        ['orange','orangered','red'],
        ['lightgreen','green','darkgreen'],
        ['azure','blue','darkblue'],
        ['lavender','purple','magenta'],
        ['lime','yellow','olive'],
        ['silver','grey','black'],
    ]
MaxPerGraph = 4 # max graphs per subplot
pngfile = None  # show the scatter graph and regression polynomial best fit graph

# raw (outliers) limits for some pollutants, manually set, avoid rough spikes
tresholds = [False,
    ['^[a-su-z]?temp$',-50,50,None], # temp type
    ['^[a-qs-z]?rv$',0,100,None],    # humidity type
    ['^[a-oq-z]?pm_?[12][05]?$',0,200,None],# dust type
    ['^[a-np-z]?[Oo]3',0,250,None],  # ozon type
    ['^[a-mo-z]?[Nn][Oo]2?',0,100,None],    # ozon type
    ]

# Grubbs Z-score tresholds
test = 'max'    # either min, max or both (two-tailed)  outliers test
alpha = 0.05    # Grubb significant level
ddof  = 1       # Delta Degree of Freedom (stddev)
# return default [min,max] for a particular sensor type
# nan is not configured, no boundary set
def getTresholds(name):
        import re
        if not tresholds[0]:
            for i in range(1,len(tresholds)):
                tresholds[i][0] = re.compile(tresholds[i][0])
        for i in range(1,len(tresholds)):
            if tresholds[i][0].match(name):
               return tresholds[i][1:3]
        return [float('nan'),float('nan')]

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
    global debug, verbose
    if not table in checked.keys():
        if not (table,) in db_query("SHOW TABLES", True,db=db):
            print("Table with name \"%s\" does not exists in DB." % table)
            return None
        else:
            checked['table'] = []
    if not len(checked['table']):
        for col in db_query("DESCRIBE %s" % table,True,db=db):
            fnd = False
            for item in ['_valid','id','datum']:
                if col[0].find(item) >= 0:
                    fnd = True; break
            if fnd: continue
            checked['table'].append(col[0])
    if not pollutant in checked['table']:
        print("Pollutant (column) \"%s\" in table %s does not exists." % (pollutant,table))
        return None
    if not period: return True
    valued = 'NOT ISNULL(%s)' % pollutant
    if valid: valued += ' AND %s_valid' % pollutant
    qry = "SELECT COUNT(%s) FROM %s WHERE UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d AND %s" % \
        (pollutant, table, period[0], period[1], valued)
    cnt = db_query(qry, True, db=db)
    if not cnt[0][0] and debug:
        print("Table %s / column %s No values in the (window) period." % (table, pollutant))
    return cnt[0][0]

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
            print("Table %s, column %s, period %s up to %s: condition: %s, invalidated in raw way %d cells from total of %d values" % \
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
    global debug, verbose
    if not Check(table,pollutant,period=period, db=db):
        return None
    qry = 'SELECT %s FROM %s WHERE UNIX_TIMESTAMP(datum)>= %d AND UNIX_TIMESTAMP(datum) <= %d AND %s_valid' % \
        (pollutant, table, period[0], period[1], pollutant)
    data = db_query(qry, True,db=db)
    if len(data) < 15 and verbose:
        print("Table %s, column %s, period %s upto %s, only %d values. Skipped this subperiod." % \
            (table, pollutant, \
            datetime.datetime.fromtimestamp(period[0]).strftime('%d %b %Y %H:%M'), \
            datetime.datetime.fromtimestamp(period[1]).strftime('%d %b %Y %H:%M'), \
            len(data)))
        return None
    data = np.array([float(data[i][0]) for i in range(0,len(data))])
    result = grubbs(np.array(data),test=test, alpha=alpha, ddof=ddof)
    if result['liers']:
        update = '%s < %f OR %s > %f' % \
            (pollutant, result['min'], pollutant, result ['max'])
    else: return False
    if debug:
        print("Table %s, colums %s, period %s up to %s: Grubbs Z-score invalidate %d cells from %d cells:\n\tmean %.2f stddev %.2f, min %.2f max %.2f." % \
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
    except:
        sys.exit("Unable to find date/time from string \"%s\"." % string)
    for i in number.split('\n'):
        if i:
            secs = timing_re.match(i)
            if secs: return int(i)
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
    for col in db_query("DESCRIBE %s" % tbl,True,db=db):
        fnd = True
        for sub in ['_valid','_ppb','_color','id','datum','rssi','longi','latit','altit']:
            if col[0].find(sub) >= 0:
                fnd = False; break
        if fnd:
            pols.append(col[0])
    print("\t%s" % ', '.join(pols))

# show table in thye database with sensors
def showTables(db=net):
    print("Database %s has following sensor kit  tables (<project>_<serial>):" % db['database'])
    for tbl in db_query("SHOW TABLES",True,db=db):
        # omit governmental stations
        if not tbl[0].find('_') >= 0: continue
        fnd = True
        # omit tables which are extentions and intermediate
        # To Do: use Sensors or stations table to filter
        for t in ['datum','day','aqi','Max','Day','lki']:
            if tbl[0].find('_'+t) > 0:
                fnd = False; break
        if fnd:
            showPols(tbl[0],db=db)

# collect script configuration from command line
def get_arguments():
    global pollutants
    """ Command line argument roll in """
    import argparse
    global progname, debug, verbose, net, period
    global show, pngfile, showOutliers, alpha, ddof, test, lossy
    global reset, RESET, sigma
    parser = argparse.ArgumentParser(prog=progname, description='''
Get from a database with "pollutant" values the measured (raw) values
over a period of time.
Invalidate the measurements when not in a provided minimum-maximum range.
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
    parser.add_argument("--alpha",help="Grubb's significant level, default: %f." % alpha, default=alpha, type=float)
    parser.add_argument("--ddof",help="use delta degree of Freedom (N*stddev), default: %f." % ddof, default=ddof, type=float)
    parser.add_argument("--test",help="Grubb's test for min(minimal), max(imal) or two-tailed (both) outliers test, default: %s." % test, default=test, choices=['min','max','two-tailed'])

    parser.add_argument("-r", "--reset", help="do not re-valid all cells in sliding window first. See also the lossy option. Default: re-validate cells.", default=reset, action='store_false')
    parser.add_argument("-R", "--RESET", help="re-valid all cells in the full period first, default: do not re-validate the measurements.", default=RESET, action='store_true')
    parser.add_argument("-l", "--lossy", help="Turn lossy off. Re-valid all the cells in the sliding window period before starting the scan. Default: only re-validate all cells from second quarter of time in the sliding window.", default=lossy, action='store_false')
    parser.add_argument("-S", "--show", help="show graph, default: graph is not shown", default=show, action='store_true')
    parser.add_argument("--sigma", help="show graph with variance sigma. Sigma=0 no variance band is plotted. Default: sigma=%.1f" % sigma, default=sigma, type=float)
    parser.add_argument("-L", "--outliers", help="Do show in graph the outliers, default: outliers are shown", default=showOutliers, action='store_true')
    parser.add_argument("-f", "--file", help="generate png graph file, default: no png", default=pngfile)
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
    if pngfile != None: show = True
    if args.window:
        mult = 60*60
        args.window = args.window.lower()
        for char in ['h','d','w','m']:
            idx = args.window.find(char)
            if idx < 0: continue
            if not idx: args.window = '1' + args.window
            if char == 'h': mult = 3600
            elif char == 'd': mult = 3600*24
            elif char == 'w': mult = 3600*24*7
            else: mult = 3600*24*30
        period[2] = int(args.window[:idx])*mult
    else:
        period[2] = period[1] - period[0]
    if not len(args.args):
        showTables()
        exit(0)
    elif len(args.args[0].split('/')) == 1:
        showPols(arg.args[0])
        exit(0)
    
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
        for serial in serials:
            for pol in polArray:
                pols = '%s%s/%s' % (project,serial,pol)
                pols = pols.split('/')
                if (not len(pols)) or (not pols[0]) or (not pols[1]):
                    break
                pollutants.append({ 'table': None, 'pollutant': None, 'range':[float('nan'),float('nan')]})
                pollutants[-1]['table'] = pols[0]
                pollutants[-1]['pollutant'] = pols[1]
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
                if verbose:
                    print("Find spikes and outliers in table %s for column %s,\n\toutliers value range [%f - %f]" % (pollutants[-1]['table'],pollutants[-1]['pollutant'],pollutants[-1]['range'][0],pollutants[-1]['range'][1]))

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
 
    Z = zscore(X, ddof=ddof)  # Z-score
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
        Z = zscore(X, ddof=ddof)
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
    if lossy: start = period[0]+int(period[1]-period[0]/4)
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
        raise ValueError("Database table %s has no measurements for pollutant %s in the provided period of time." % \
            (pollutant['table'],pollutant['pollutant']))
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
        print("Statistical period overview %s\n    for %s from table %s:\n\tnr invalid cells %d, nr valid cells %d, average %.2f, std dev %.2f,\n\tminimum %.2f, maximum %.2f." % \
            (string, pol.upper(), table, rslt['invalids'],
            rslt['count'], rslt['avg'], rslt['stddev'],
            rslt['min'], rslt['max']))
    if string: return None
    return rslt

# remove outliers in a table for a pollutant within a period
def FindOutliers(pollutant,db=net):
    global verbose, debug, period, lossy, RESET
    if (not pollutant['table']) or (not pollutant['pollutant']): return
    doStatistics(pollutant['table'],pollutant['pollutant'],period=period,db=db,string='(before outliers removal)')
    freq = int(period[1]-period[0])/(int(period[2]/2))
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
        if not rawInvalid(pollutant['table'],pollutant['pollutant'],periods[i],minimal=pollutant['range'][0],maximal=pollutant['range'][1],db=db):
            if debug:
                print("Skip table %s column %s for this period." % \
                    (pollutant['table'],pollutant['pollutant']))
            continue
        Zscore(pollutant['table'],pollutant['pollutant'],periods[i],db=db)
    doStatistics(pollutant['table'],pollutant['pollutant'],period=period,db=db,string='(after outliers removal)')

def PlotConvert(data):
    dates = [data[i][0] for i in range(0,len(data))]
    dateconv = np.vectorize(datetime.datetime.fromtimestamp)
    dates = dateconv(dates)
    values = np.array([float(data[i][1]) for i in range(0,len(data))])
    return (dates,values)

def getPlotdata(period, pollutant, db=net):
    global debug, verbose
    table = pollutant['table']
    pol = pollutant['pollutant'] 
    if not Check(table, pol, db=db):
        return None
    # validated values
    qry = "SELECT UNIX_TIMESTAMP(datum), %s FROM %s WHERE %s_valid AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d" % \
        (pol, table, pol, period[0], period[1])
    values = db_query(qry, True, db=db)
    update = 'ISNULL(%s)' % pol; supdate = 'NOT ISNULL(%s)' % pol
    if pollutant['range'][0] != float('nan'):
        update += 'OR (%s < %f)' % (pol,pollutant['range'][0])
        supdate += ' AND (%s >= %f)' % (pol,pollutant['range'][0])
    if pollutant['range'][1] != float('nan'):
        update += ' OR (%s > %f)' % (pol, pollutant['range'][1])
        supdate += ' AND (%s <= %f)' % (pol, pollutant['range'][1])
    # values really out of defined range
    qry = "SELECT UNIX_TIMESTAMP(datum), %s FROM %s WHERE (%s) AND NOT %s_valid AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d" % \
        (pol, table, update, pol, period[0], period[1])
    outliers = db_query(qry, True, db=db)
    # outliers in Z-score
    qry = "SELECT UNIX_TIMESTAMP(datum), %s FROM %s WHERE %s AND NOT %s_valid AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d" % \
        (pol, table, supdate, pol, period[0], period[1])
    spikes = db_query(qry, True, db=db)
    return [values,spikes,outliers]
    
        
# best line fit for array of dates and values
# from: https://stackoverflow.com/questions/22239691/code-for-line-of-best-fit-of-a-scatter-plot-in-python
def BestFit(data,order=1, grit=1):
    dates = [data[i][0] for i in range(0,len(data))]
    values = np.array([float(data[i][1]) for i in range(0,len(data))])
    # determine best fit line
    par = np.polyfit(dates, values, 1, full=True)

    slope=par[0][0]
    intercept=par[0][1]
    xl = [dates[0], dates[-1]]
    # loop in the grit
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

def Trendline(data, order=1, grit=1):
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
    for x in range(minxd,maxxd+1,int((maxxd-minxd)/(grit+1))):
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

def makeSpline(dates,x,values,floor,ceil):
    from scipy.interpolate import UnivariateSpline
    try:
        spl = UnivariateSpline(dates, values)
    except:
        return np.array(values) # ???
    spl.set_smoothing_factor(0.5)
    d = spl(x); p = []
    for i in d: # slice to chart height
        if i < floor: i = floor
        if i > ceil: i = ceil
        p.append(i)
    return  np.array(p)

def propability(sigma):
    import scipy.stats
    return round(100*scipy.stats.norm(0,1).cdf(sigma),1)

# plot a spline and variation band
# select ROUND((CEILING(UNIX_TIMESTAMP(datum) / 3600) * 3600)) AS timeslice, avg(pol) from table group by timeslice order by datum desc
def plotAverage(pollutant,period,floor,ceil,plt,color='b',interval=3600,db=net, grit=1000, sigma=0):
    dateconv = np.vectorize(datetime.datetime.fromtimestamp)
    if sigma > 4: sigma = 4
    if sigma < 0: sigma = 0
    
    table = pollutant['table'] ; pol = pollutant['pollutant']
    qry = 'SELECT ROUND((CEILING(UNIX_TIMESTAMP(datum) / %d) * %d)) AS timeslice, AVG(%s), STDDEV(%s) FROM %s WHERE NOT ISNULL(%s) AND %s_valid AND UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d GROUP BY timeslice ORDER BY datum' % \
        (interval,interval,pol, pol, table, pol, pol, period[0], period[1])
    data = db_query(qry, True, db=db)
    if len(data) < 15: return False
    spg = (data[-1][0]-data[0][0]+int(grit/2))/grit     # secs per grit 
    data.append((None,None,None))
    x = []; m = []; su = []; sl = []
    label = '%s %d hr average and variance sigma=+/-%.1f (%.1f%%)' % (pol,interval/3600,sigma,propability(sigma))
    for idx in range(0,len(data)):
        if data[idx][1] != None:
            x.append(data[idx][0])
            m.append(float(data[idx][1]))
            if sigma:
                Y  = float(data[idx][1])-sigma*float(data[idx][2])
                if Y < floor: Y = floor
                sl.append(Y)
                Y = float(data[idx][1])+sigma*float(data[idx][2])
                if Y > ceil: Y = ceil
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

# plot a spline and variation band
# select ROUND((CEILING(UNIX_TIMESTAMP(datum) / 3600) * 3600)) AS timeslice, avg(pol) from table group by timeslice order by datum desc
def plotSpline(data,plt,color='b',grit=3600):
    from scipy.interpolate import UnivariateSpline
    dates = [data[i][0] for i in range(0,len(data))]
    if len(dates) <= 5: return None
    values = np.array([float(data[i][1]) for i in range(0,len(data))])
    dateconv = np.vectorize(datetime.datetime.fromtimestamp)
    for idx in range(0,len(dates)):
        x = []; y = []; i = idx
        while (i+1 < len(dates)) and (dates[i+1]-dates[i] < grit):
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

def CreateGraphs(period, pollutants, db=net):
    global debug, verbose, file, colors, sigma
    import matplotlib.pyplot as plt
    from matplotlib import gridspec
    import matplotlib.dates as mdates
    from matplotlib.dates import MO, TU, WE, TH, FR, SA, SU

    periodStrt = datetime.datetime.fromtimestamp(period[0]).strftime('%d %b %Y %H:%M')
    periodEnd = datetime.datetime.fromtimestamp(period[1]).strftime('%d %b %Y %H:%M')
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    #Width = 7.5; Height = 5
    # fig = plt.figure(tight_layout=True, figsize=(Width,Height))
    fig, ax = plt.subplots()
    months = mdates.MonthLocator()
    days = mdates.DayLocator()  # every day
    hours = mdates.HourLocator(interval=4)  # every hour
    weeks = mdates.WeekdayLocator(byweekday=SU)  # every week
    Fmt = mdates.DateFormatter('%-d %b')

    # fig = plt.figure()
    # left=0.1, bottom=0.1, right=0.97, top=0.93, wspace=0.25, hspace=0.25
    # fig.subplots_adjust(top=0.93, bottom=0.5, left=0.2, right=0.2)
    # create some bling bling
    #fig.suptitle('Data from %s, best fit polynomial for type(s): %s' % (net['database'],', '.join(set([elmt['type'] for elmt in sensors]))),
    #    fontsize=9, fontweight='bold')
    plt.suptitle("Chart with pollutants scatter graphs with spikes (Z-score) and outiers (min-max limit)", y=1.05, fontsize=8)
    minDate = time(); maxDate = 0; fnd = False
    projects = {};
    for idx in range(0,len(pollutants)):
        if not pollutants[idx]['table'] in projects.keys():
            projects[pollutants[idx]['table']] = []
        if not pollutants[idx]['pollutant'] in projects[pollutants[idx]['table']]:
            projects[pollutants[idx]['table']].append(pollutants[idx]['pollutant'])
        (values,spikes,outliers) = getPlotdata(period, pollutants[idx], db=net)
        label = '%s' % pollutants[idx]['pollutant']
        if len(values) > 0:
            try: max = values[len(values)-1][0]
            except: max = values[0][0]
            if maxDate < max: maxDate = max
            if minDate > values[0][0]: minDate = values[0][0]
            (dates,Yvalues) = PlotConvert(values)
            ax.scatter(dates, Yvalues,marker='.', color=colors[idx][0], label=label)
            plotAverage(pollutants[idx],period,np.min(Yvalues),np.max(Yvalues),plt,color=colors[idx][2],interval=3600, db=db, sigma=sigma)
            label=''; fnd = True
        if len(spikes) > 0:
            try: max = spikes[len(spikes)-1][0]
            except: max = spikes[0][0]
            if maxDate < max: maxDate = max
            if minDate > spikes[0][0]: minDate = spikes[0][0]
            (dates,Yvalues) = PlotConvert(spikes)
            ax.scatter(dates, Yvalues,marker='o', color=colors[idx][1], label=label)
            label=''; fnd = True
            ax.scatter(dates, Yvalues,marker='.', color=colors[idx][0], label=label)
        if showOutliers and (len(outliers) > 0):
            try: max = outliers[len(outliers)-1][0]
            except: max = outliers[0][0]
            if maxDate < max: maxDate = max
            if minDate > outliers[0][0]: minDate = outliers[0][0]
            (dates,Yvalues) = PlotConvert(outliers)
            ax.scatter(dates, Yvalues,marker='s', color=colors[idx][2], label=label)
            label=''; fnd = True
            ax.scatter(dates, Yvalues,marker='.', color=colors[idx][0], label=label)
    if not fnd:
        print("Found no data to plot.")
        return False
    # format the ticks
    if (maxDate-minDate)/(24*60*60) < 4: # month modus
        freq = 1
        ax.xaxis.set_major_locator(days)
        ax.xaxis.set_major_formatter(Fmt)
        ax.xaxis.set_minor_locator(mdates.HourLocator(interval=1))
        # ax.tick_params(direction='out', length=6, width=2, colors='r')
        ax.xaxis.set_minor_locator(mdates.HourLocator(interval=6))
    elif (maxDate-minDate)/(24*60*60) < 10: # month modus
        freq = 1
        ax.xaxis.set_major_locator(days)
        ax.xaxis.set_major_formatter(Fmt)
        ax.xaxis.set_minor_locator(mdates.HourLocator(interval=3))
        # ax.tick_params(direction='out', length=6, width=2, colors='r')
        ax.xaxis.set_minor_locator(mdates.HourLocator(interval=6))
    elif (maxDate-minDate)/(24*60*60) < 15: # month modus
        freq = 2
        ax.xaxis.set_major_locator(days)
        ax.xaxis.set_major_formatter(Fmt)
        ax.xaxis.set_minor_locator(hours)
    elif (maxDate-minDate)/(24*60*60) < 40: # week modus
        freq = 1
        ax.xaxis.set_major_locator(weeks)
        ax.xaxis.set_major_formatter(Fmt)
        ax.xaxis.set_minor_locator(days)
    elif (maxDate-minDate)/(24*60*60) < 61: # week modus
        freq = 1
        ax.xaxis.set_major_locator(months)
        ax.xaxis.set_major_formatter(Fmt)
        ax.xaxis.set_minor_locator(weeks)
    else:
        freq = 2
        ax.xaxis.set_major_locator(months)
        ax.xaxis.set_major_formatter(Fmt)
        ax.xaxis.set_minor_locator(weeks)
    (dates, Yvalues) = PlotConvert([(minDate-30*60,0),(maxDate+30*60,0)])
    ax.set_xlim(dates[0],dates[1])
    if showOutliers:
        plt.title("Measurements: values, spikes, outliers for %s: %s\nin the period %s up to %s" % \
            (pollutants[idx]['table'], ', '.join(projects[pollutants[idx]['table']]), periodStrt, periodEnd), fontsize=10)
    else:
        plt.title("Measurements: values, and spikes (no outliers) for %s: %s\nin the period %s up to %s" % \
            (pollutants[idx]['table'], ', '.join(projects[pollutants[idx]['table']]), periodStrt, periodEnd), fontsize=10)
    (dates, Yvalues) = PlotConvert([(minDate-10*60,0),(maxDate+10*60,0)])
    ax.set_xlim(dates[0],dates[1])
    [label.set_fontsize('x-small') for (i,label) in enumerate(ax.xaxis.get_ticklabels())]
    [label.set_fontsize('x-small') for (i,label) in enumerate(ax.yaxis.get_ticklabels())]
    [label.set_rotation(45) for (i,label) in enumerate(ax.xaxis.get_ticklabels())]
    if len(ax.xaxis.get_ticklabels()) > 7:
        [l.set_visible(False) for (i,l) in enumerate(ax.xaxis.get_ticklabels()) if i % freq != 0]
    plt.grid(True)#, color='g', linestyle='-', linewidth=5)
    fig.text(0.98, 0.015, 'generated %s by pyplot/numpy for MySense' % datetime.datetime.fromtimestamp(time()).strftime('%d %b %Y %H:%M'),
        verticalalignment='bottom', horizontalalignment='right',
        color='gray', fontsize=8)
    ax.legend(loc=2,fontsize=7, shadow=True, framealpha=0.5, fancybox=True)
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
    for item in pollutants:
        FindOutliers(item,db=net)
    if show:
        CreateGraphs(period, pollutants)
    exit(0)

