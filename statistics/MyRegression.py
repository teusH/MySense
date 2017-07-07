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

# $Id: MyRegression.py,v 3.9 2017/07/07 15:16:34 teus Exp teus $

""" Create and show best fit for at least two columns of values from database.
    Use guessed sample time (interval dflt: auto detect) for the sample.
    Print best fit polynomial graph up to order (default linear) and R-squared
    Multi linear regression modus.
    Show the scatter graph and best fit graph (default: off).
    Input from database, spreadsheet (XLSX) and CVS file formats.
    Database table/column (sensor name) over a period of time.
    Database credentials can be provided from command environment.
    Script uses: numpy package, SciPy and statPY and matplotlib from pyplot.
"""
progname='$RCSfile: MyRegression.py,v $'[10:-4]
__version__ = "0." + "$Revision: 3.9 $"[11:-2]

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
        'port': 8086
    }
# database identifiers
# first range/array of regression values (second wil be calibrated against this one)
sensors = [
    { 'db': 'luchtmetingen', 'table': 'BdP_8d5ba45f', 'column': 'pm_25', 'type': 'Dylos' },
    # second (Y) range/array of regression values
    { 'db': 'luchtmetingen', 'table': 'BdP_3f18c330', 'column': 'pm25', 'type': 'PPD42NS' },
]

# xlsx and csv input file
# TO DO: extent to use a row of files, add csv file input
Pandas = {
    'input' : None,     # input file name to parse with pandas
    'module' : None,    # panda module to load
}
# type of input and file handler
resource = { 'type': None, 'fd': None }

# period of time for the regression values
timing = { 'start': time() - 24*60*60, 'end': time() }

interval = None # auto detect interval from database time values
order = 1       # best fit polynomial, order: default 1: linear regression graph
show = True     # show the scatter graph and regression polynomial best fit graph
SHOW = True     # show the value and scatter graphs
colors = ['y','b','g','darkblue','sienna','teal','purple','m','r']
MaxPerGraph = 4 # max graphs per subplot
pngfile = None  # show the scatter graph and regression polynomial best fit graph
normMinMax = False    # transform regression polynomial best fit graph to [0,1] space
normAvgStd = False    # transform regression polynomial best fit graph to [-1,1] space
ml_mode = False # multi linear regression mode (default False: regression polynomial)
HTML = False    # output in HTML format (default text)
PrevP = False   # current in paragraph output style?

def MyPrint(strg, P=False, B=False, I=False):
    global HTML, PrevP
    if not len(strg):
        if HTML:
            if PrevP: print("</p>")
        PrevP = False
        return
    if HTML:
        if B:
            print("<br />")
        if P:
            if PrevP: print ("</p>")
            print("<p>")
            PrevP = True
        if I:
            print('<div style="font-size: 10pt; text-indent: +1.5em">')
    print(strg)
    if HTML and I:
        print('</div>')

def db_connect(net):
    global resource
    for M in ('user','password','hostname','database'):
        if (not M in net.keys()):
            if M == 'database' and resource['type'] != 'mysql': continue
            sys.exit("Please provide access credential %s" % M)
    try:
        if resource['type'] == 'mysql':
            DB = mysql.connector.connect(
                charset='utf8',
                user=net['user'],
                password=net['password'],
                host=net['hostname'],
                port=net['port'],
                database=net['database'])
        elif resource['type'] == 'influx':
            from influxdb import InfluxDBClient
            DB = InfluxDBClient(
                net['hostname'], net['port'],
                net['user'], net['password'],
                timeout=2*60)
    except:
        sys.exit("Unable to connect to database %s on host %s" %(net['database'],net['hostname']))
    return DB

def influxDBs(DB):
    ''' get a list of databases on the InFlux server. Might fail on no admin credentials. '''
    rts = []
    try:
        response = DB.get_list_database()
        for item in response:
            if not 'name' in item.keys(): continue
            if item['name'][0] == '_': continue   # internal table
            if len(item['name']): rts.append(item['name'])
    except: # no admin access or connectivity
        sys.stderr.write('Influx server: No database list access permission (admin rights)\n')
        return rts
    return rts

def influxMmnt(DB,db):
    ''' get list of measurements on InFlux server. May return empty on no credentials. '''
    rts = []
    try:
        response = DB.get_list_series(db)
    except:
        sys.stderr.write('No list available at InFlux server.\n')
        return rts
    for item in response:
        for measurement in item['tags']:
            if not 'key' in measurement.keys(): continue
            measurement = measurement['key'].split(',')[0]
            if len(measurement) and (not measurement in rts): rts.append(measurement)
    return rts

def influxQry(DB,db,query,col):
    '''Do a query to the Influx server. Returns a matrix, first row has column names'''
    # expect response as list of dictionaries, e.g.
    # [{u'mean': 469.8, u'time': 1498134000}, ...]
    try:
        response = list(DB.query(query,database=db,params={'epoch':'s'},expected_response_code=200).get_points())
    except:
        sys.stderr.write('Error in query nr %s, value: %s\n' % (sys.exc_info()[0],sys.exc_info()[1]))
        return []
    rts = []
    if not type(col) is list: col = [col]
    if len(response):
        for rec in response:
            row = []
            for nm in ['time']+col:
                val = rec.get(nm,None)
                if (nm == 'time') and (type(val) is str):
                    if (len(val) > 16) and (val[4] == '-'):
                        # RFC3339 date format
                        val = int(mktime(strptime(rec[nm].replace('Z','UTC'),'%Y-%m-%dT%H:%M:%S%Z')))
                    else:
                        val = None
                row.append(val)
            rts.append(row)
    return rts

def influxFlds(DB,db,serie):
    ''' get a list of fields for a serie '''
    # expect something like:
    #  [ { "results": [
    #    { "statement_id": 0,
    #      "series": [
    #            { "name": "raw",
    #              "columns": [ "fieldKey", "fieldType" ],
    #              "values": [ [ "pm10_pcsqf", "float" ], ... ]
    #            } ]
    #    } ]
    #    }]
    query = "SHOW FIELD KEYS FROM %s..%s" % (db,serie)
    try:
        response = list(DB.query(query,database=db,expected_response_code=200).get_points())
    except:
        sys.stderr.write('Error in query nr %s, value: %s\n' % (sys.exc_info()[0],sys.exc_info()[1]))
        return []
    rts = []
    for rec in response:
        if ('fieldType' in rec.keys()) and (not rec['fieldType'] in ('float','int')):
            continue
        if ('fieldKey' in rec.keys()) and len(rec['fieldKey']):
            rts.append(rec['fieldKey'])
    return rts

def influxTags(DB,db,serie, Type='type'):
    ''' get list of tags for a measurement on InFlux server. May return empty on no credentials. '''
    rts = []
    query = "SHOW series ON %s" % db
    try:
        response = list(DB.query(query,database=db,expected_response_code=200).get_points())
    except:
        sys.stderr.write('No measurements available at InFlux server.\n')
        return rts
    for item in response:
        if not 'key' in item.keys(): continue
        tags = item['key'].split(',')
        if len(tags) < 2: continue
        if tags[0] != serie: continue
        for i in range(1,len(tags)):
            if tags[i][0:len(Type)] != Type: continue
            tag = tags[i][len(Type)+1:].replace('"','')
            if not tag  in rts: rts.append(tag)
    return rts
    
def influxCnt(DB,sensor,period):
    query = "SELECT count(*) FROM %s..%s WHERE type = '\"%s\"\' and time >= %ds and time <= %ds" % (sensor['table'],sensor['measurement'],sensor['type'].lower(),period['start'],period['end'])
    try:
        responses = list(DB.query(query,database=sensor['table'],expected_response_code=200).get_points())
    except:
        sys.exit('No access on database %s for \"%s\" on InFlux server.\n' % (sensor['table'],sensor['column']))
    count = 0
    for resp in responses:
        count = resp.get('count_'+sensor['column'],0)
        if count: break
    return count

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
    # MyPrint("Average sample interval: %3.1f, std dev: %3.1f" % (ivals_bar, ivals_std), B=True)
    return int(ivals_bar+ 2* ivals_std)
    
def fromMySQL(fd,sensor,period):
    # check table and sensor (column) name for existance
    if not (sensor['table'],) in db_query(fd,"SHOW TABLES", True):
        sys.exit("Table with name \"%s\" does not exists in DB." % sensor['table'])
    names = db_query(fd,"DESCRIBE %s" % sensor['table'],True)
    fnd = False
    for name in names:
        if name[0] == sensor['column']:
            fnd = True ; break
    if not fnd:
        sys.exit("Sensor (column) \"%s\" in table %s does not exists." % (sensor['column'],sensor['table']))
    # get the tuples (UNIX time stamp, valid value) for this period of time
    qry = "SELECT UNIX_TIMESTAMP(%s),(if(isnull(%s),'nan',%s)) FROM %s WHERE UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d and %s_valid  order by datum" % \
        (sensor['date'],sensor['column'],sensor['column'],sensor['table'],period['start'],period['end'],sensor['column'])
    return db_query(fd,qry, True)

def fromInFlux(fd,sensor,period):
    global interval
    # check measurement and sensor name for existance
    series = influxMmnt(fd,sensor['table'])
    if not len(series):
        sys.exit("InFlux database with name \"%s\" does not exists." % sensor['table'])
    if not sensor['measurement'] in series:
        sys.exit("InFlux measurement \"%s\" does not exists in database %s." % (sensor['measurement'],sensor['table']))
    names = influxFlds(fd,sensor['table'],sensor['measurement'])
    if not sensor['column'] in names:
        sys.exit("Sensor (column) \"%s\" in database %s does not exists." % (sensor['column'],sensor['table']))
    # default interval 10m with average (we might shave outliers out a bit)
    response = []
    if influxCnt(fd,sensor,period):
        # use average for the interval (dflt 10 minutes)
        # debate: avoid null readings and hide outliers
        query = "SELECT mean(%s) FROM %s WHERE type = '\"%s\"' and time >= %ds and time <= %ds group by time(%s) order by time" % (sensor['column'],sensor['measurement'],sensor['type'].lower(),period['start'],period['end'],('10m' if interval == None else '%ds' % interval))
        # one column mean is identified as 'mean', more as 'mean_'+col_name
        response = influxQry(fd,sensor['table'],query,'mean')
        for i in range(len(response)-1,-1,-1):  # check the matrix for values
            if (len(response[i]) != 2) or (response[i][1] == None):
                response.pop(i)
            elif not((type(response[i][1]) is int) or (type(response[i][1]) is float)):
                response.pop(i)
    if not len(response):
        sys.exit("InFlux measurement \"%s\" in database %s has no values." % (sensor['measurement'],sensor['table']))
    # response.insert(0,['time',sensor['column']])
    return response

# we could first get average/std dev and omit the outliers
def getColumn(sensor,period, amin = 60, amax = 60*60):
    global interval, resource
    if (not 'type' in resource.keys()) or (not 'fd' in resource.keys()):
        sys.exit("Data resource error: no access to database/spreadsheet.")
    if resource['type'] == 'mysql':
        values = fromMySQL(resource['fd'],sensor,period)
    elif resource['type'] == 'influx':
        values = fromInFlux(resource['fd'],sensor,period)
    elif (resource['type'] == 'elsx') or (resource['type'] == 'csv'):
        if not 'read' in Pandas.keys():
            Pandas['read'] = GetXLSX()
        if not Pandas['read']:
            return np.array([])
        values = FromXLSX(sensor)
    else:
        sys.exit("Data resource error: unknown data type")
    if len(values) < 5:
        sys.exit("Only %d records in database/spreadsheet %s/%s. Need more values for proper regression." % (len(values),sensor['table'],sensor['column']))
    imin = None; imax = None; nr_records = len(values)
    i = len(values)-1
    while ( i >= 0 ):
        try:
            values[i] = [int(values[i][0]),float(values[i][1])]
        except:
            pass
        if math.isnan(values[i][1]):
            values.pop(i)
            i -= 1
            continue
        if i == 0: break
        diff = abs(values[i][0]-values[i-1][0]) # try to guess the sample interval time
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
        MyPrint("Auto interval samples is (re)set to %d (%s)" % (interval,strg),B=True)
    MyPrint("Database table %s sensor (column) %s: %d db records, deleted %d NaN records." % (sensor['table'],sensor['column'],len(values), nr_records-len(values)),B=True)
    return np.array(values)

X = []
Y = []
Xmax = None
Xmax = None
Xmin = None
Xmin = None

LastIndex = 0
def pickValue(arr, time, sample):
    global LastIndex
    value = 0.0; cnt = 0
    index = LastIndex
    while (index < len(arr)) and (arr[index][0] < time-sample): 
        index += 1
    if index >= len(arr): return None
    while (index < len(arr)) and (arr[index][0] < time+sample):
        cnt += 1; value += arr[index][1]
        index += 1
    LastIndex = index - 2
    if (LastIndex < 0) or (index >= len(arr)): LastIndex = 0
    if not cnt: return None
    return value/cnt

def getData(net,sensors,timing):
    global resource
    Data = []
    for I in range(0,len(sensors)):
        Data.append(getColumn(sensors[I],timing,60,60*60))
    if (resource['type'] == 'mysql') and (resource['fd'] != None):
        resource['fd'].close()
    else: Pandas['fd'] = None
    return Data

def getArrays(net,sensors,timing):
    """ Build a matrix with times and column values """
    global interval

    try:
        Data = getData(net,sensors,timing)
    except StandardError as err:
        sys.exit("Cannot obtain the records from the database/spreadsheet. Error: %s." % err)

    X = []
    skipped = 0
    # build a matrix every row: [time, colVal0, colVal1, ...]
    for tx in range(0,len(Data[0][:,0])):
        row = [] ; row.append(Data[0][tx][0]); row.append(Data[0][tx][1])
        try:
            for I in range(1,len(sensors)):
                yval = pickValue(Data[I],row[0],interval/2)
                if yval == None:
                    skipped += 1
                    raise ValueError
                row.append(yval)
        except ValueError:
            continue
        X.append(row)
    MyPrint("Collected %d values in sample time frame (%dm/%ds) for the graph." % (len(X),interval/60,interval%60),B=True)
    if skipped:
        MyPrint("Skipped %d db records, could not find any value(s) in same sample interval." % skipped)
    return np.array(X)

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

def get_arguments():
    """ Command line argument roll in """
    import argparse
    global progname
    global net, sensors, timing, interval, order, show, normMinMax, HTML
    global normAvgStd, pngfile, SHOW, MaxPerGraph, Pandas, resource, ml_mode
    parser = argparse.ArgumentParser(prog=progname, description='Get from at least two sensors for a period of time and calculate the regression best fit polynomial.\nEach argument defines the [[table]/]sensor(column)/[date]/[type][/measurement] DB table use definition.\nFor non DB use the table is sheet1 and should be omitted.\nDefault definitions: the previous names or column numbers for table, sensor, date, type will be used.', epilog="Environment DB credentials as DBHOST=hostname, DBPASS=acacadabra, DBUSER=username are supported.\nThey are used for MySQL and for InFlux credentials.\n\nCommand use with no arguments will, if possible, provide a list of MySQL table names (sensorkit names), InFlux database names (sensor kit names), or in case of spreadsheet inmfo about column names.\nWith one argument (sensor kit name) script will list all sensor names, sensor types for that sensor kit.\n\nUsage example for two or more command arguments (the measurements selection):\nMySQL: \"BdP_12345abcd/pm_25/datum/SDS011\"\nXLSX/CSV (here column nr iso id in first row): \"/3/0/Dylos\"\nInFlux: \"BdP_654321daef/pm25/time/PPD42NS/raw\"\n\nCopyright (c) Behoud de Parel, 2017\nAnyone may use it freely under the 'GNU GPL V4' license. Any script change remains free.")
    parser.add_argument("-I", "--input", help="XLSX or CSV input file (path/filename.{xlsx,csv}, default: None\nOptions as <option>=<value> as command arguments.\nOptions: sheetname=0 (xlsx), header=0 (row with header or None), skiprows=0 (nr of rows to skip at start, delimiter=',' (None: auto detect).", default=Pandas['input'])
    parser.add_argument("-H", "--hostname", help="Database host name, default: %s" % net['hostname'], default="%s" % net['hostname'])
    parser.add_argument("--port", help="Database port number, default: DB dfl port", default="3306")
    parser.add_argument("-U", "--user", help="Database user name, default: %s" % net['user'], default="%s" % net['user'])
    parser.add_argument("-P", "--password", help="Database password, default: %s" % net['password'], default="%s" % net['password'])
    parser.add_argument("-D", "--database", help="Database name, default: %s" % net['database'], default="%s" % net['database'])
    parser.add_argument("-T", "--Type", help="Database type, default: MySQL", default="mysql", choices=['mysql','influx'])
    parser.add_argument("-i", "--interval", help="Interval sample timing (two values in same sample time) in seconds, default: auto detect", default=None)
    parser.add_argument("--first", help="Start of date/time period. Format as with -t option. Default: use of -t option", default=None)
    parser.add_argument("--last", help="End of date/time period. Format as with -t option. Default: use of -t option", default=None)
    parser.add_argument("-t", "--timing", help="Period of time UNIX start-end seconds or use date as understood by UNIX date command: 'date --date=SOME_DATE_string', default: %d/%d or \"1 day ago/%s\"" % (timing['start'],timing['end'],datetime.datetime.fromtimestamp(timing['start']).strftime('%Y-%m-%d %H:%M')), default="%d/%d" % (timing['start'],timing['end']))
    parser.add_argument("-o", "--order", help="best fit polynomium order, default: linear regression best fit line (order 2)", default=order)
    parser.add_argument("-n", "--norm", help="best fit polynomium min-max normalized to [0,1] space, default: no normalisation", type=bool, choices=[False,True], default=normMinMax)
    parser.add_argument("-N", "--NORM", help="best fit polynomium [avg-std,avg+std] normalized to [-1,1] space (overwrites norm option), default: no normalisation", type=bool, choices=[False,True], default=normMinMax)
    parser.add_argument("-s", "--show", help="show graph, default: graph is not shown", default=show, type=bool, choices=[False,True])
    parser.add_argument("-S", "--SHOW", help="show value and scatter graphs, default: graph is not shown", default=SHOW, type=bool, choices=[False,True])
    parser.add_argument("-m", "--multi", help="multi linear regression mode: second argument has more dependences defined by 3rd, etc argument, default: %s polynomial regression calculation" % ml_mode, default=ml_mode, type=bool, choices=[False,True])
    parser.add_argument("-f", "--file", help="generate png graph file, default: no png", default=pngfile)
    parser.add_argument("--HTML", help="generate output in HTML format, default: no html", default=False, dest='HTML', action='store_true')
    parser.add_argument("-g", "--graphs", help="plot N graps in one scatter plot, default: %d" % MaxPerGraph, default=MaxPerGraph, type=int, choices=range(1,6))
    parser.add_argument('args', nargs=argparse.REMAINDER, help="Database table one/sensor or column name, default: %s/%s/%s %s/%s/%s. Spreadsheet (sheet1) columns: name/value_colnr/[date_colnr][/type] (default date: col 0, name: pollutant nr, colum nr: 1, 2, type: ?)" % (sensors[0]['table'],sensors[0]['column'],sensors[0]['type'],sensors[1]['table'],sensors[1]['column'],sensors[1]['type']))
    # overwrite argument settings into configuration
    args = parser.parse_args()
    Pandas['input'] = args.input
    net['hostname'] = args.hostname
    net['user'] = args.user
    net['password'] = args.password
    net['database'] = args.database
    HTML = args.HTML
    resource = {"type": 'mysql', "fd": None}
    if args.Type != resource['type']: resource['type'] = args.Type
    net['port'] = int(args.port)
    if (resource['type'] == 'influx') and (net['port'] == 3306):
        net['port'] = 8086      # default influx port
        net['database'] = 'influxdb'
    cnt = 0
    if Pandas['input']:
        options = { 'header': 0, 'sheetname': 0, 'skiprows': 0, 'delimiter': ',' }
        if len(args.args):
            for I in range(len(args.args)-1,-1,-1):
                if args.args[I].find('=') < 0: continue
                use = args.args[I].split('=')
                if use[0] in options.keys():
                    if use[1].isdigit(): option[use[0]] = int(use[1])
                    elif use[1] == 'None': option[use[0]] = None
                    else: option[use[0]] = use[1]
                    args.args.pop(I)
        try:
            Pandas['module'] = __import__('pandas')
        except:
            sys.exit("Unable to load Pandas module")
        OK = True
        if not os.path.isfile(Pandas['input']): OK = False
        if Pandas['input'][-4:].upper() == 'XLSX':
            resource['type'] = 'xlsx'
        elif Pandas['input'][-3:].upper() == 'CSV':
            resource['type'] = 'csv'
        else: OK = False
        if not OK:
            sys.exit("File %s does not exists or is not an xlsx/csv file." % Pandas['input'])
        try:
            if resource['type'] == 'xlsx':
                Pandas['fd'] = Pandas['module'].read_excel(Pandas['input'],
                    header=options['header'], sheetname=options['sheetname'],
                    skiprows=options['skiprows'])
            elif resource['type'] == 'csv':
                Pandas['fd'] = Pandas['module'].read_csv(Pandas['input'],
                    header=options['header'], delimiter=options['delimiter'],
                    skiprows=options['skiprows'])
            else: raise TypeError
            resource["fd"] = Pandas['fd']
        except Exception as err:
            sys.exit("File %s not an xlsx/csv file, error: %s." % (Pandas['input'],err))
            
        # TO DO: add to use sheet nr's / names iso numbers
        sensors = [ {'date': 0 }]
        if len(args.args) <= 1: showXLSX(args.args)
        last_col = 0
        for tbl in args.args:
            atbl = tbl.split('/')
            if cnt > len(sensors)-1:
                sensors.append({'date': sensors[cnt-1]['date']})
            sensors[cnt]['table'] = 'pollutant %d' % cnt
            last_col += 1
            sensors[cnt]['column'] = last_col
            sensors[cnt]['type'] = 'unknown %d' % cnt
            if len(atbl[0]): sensors[cnt]['table'] = atbl[0]
            if len(atbl[1]):
                sensors[cnt]['column'] = int(atbl[1])
                last_col = int(atbl[1])
            if (len(atbl) > 2) and (cnt < 1):
                if len(atbl[2]): sensors[cnt]['date'] = int(atbl[2])
            if len(atbl) > 3:
                if len(atbl[3]): sensors[cnt]['type'] = atbl[3]
                elif cnt: sensors[cnt]['type'] = sensors[cnt-1]['type']
            cnt += 1
    else:
        resource['fd'] = db_connect(net)
        sensors = [ {'date': 'datum', 'measurement': 'raw' }]
        if len(args.args) <= 1:
            if resource['type'] == 'influx':
                showIF(net,args.args)
            else:
                showDB(net,args.args)
            exit(0)
        for tbl in args.args:
            atbl = tbl.split('/')
            if cnt > len(sensors)-1:
                sensors.append({'date': sensors[cnt-1]['date'] })
            if len(atbl[0]): sensors[cnt]['table'] = atbl[0]
            if len(atbl[1]): sensors[cnt]['column'] = atbl[1]
            if len(atbl) > 2:
                if len(atbl[2]): sensors[cnt]['date'] = atbl[2]
            if len(atbl) > 3:
                if len(atbl[3]): sensors[cnt]['type'] = atbl[3]
                else: sensors[cnt]['type'] = sensors[cnt-1]['type']
            if (len(atbl) > 4) and len(atbl[4]):
                if atbl[4] in ('raw','data'):
                    sensors[cnt]['measurement'] = atbl[4]
                else: sensors[cnt]['measurement'] = sensors[cnt-1]['measurement']
            cnt += 1
    DateTime = args.timing.split('/')[0]
    if args.first != None: DateTime = args.first
    timing['start'] = date2secs(DateTime)
    DateTime = args.timing.split('/')[1]
    if args.last != None: DateTime = args.last
    timing['end'] = date2secs(DateTime)
    if timing['start'] > timing['end']:
        (timing['start'],timing['end']) = (timing['end'],timing['start'])
    if args.interval != None: interval = int(args.interval)
    order = int(args.order)
    show = bool(args.show)
    SHOW = bool(args.SHOW)
    if SHOW: show=True
    ml_mode = bool(args.multi)
    pngfile = args.file
    if pngfile != None: show = True
    MaxPerGraph = int(args.graphs)
    normMinMax = bool(args.norm)
    normAvgStd = bool(args.NORM)
    if normAvgStd: normMinMax = False

# print overview of columns in database
def showDB(net,args):
    sys.stderr.write("Define arguments (at least 2) for tabel_name/column_name/[date_name]/[type]")
    tbls = []
    if len(args): tbls = args[0].split('/')
    else:
        for (tbl,) in db_query(resource['fd'],"SHOW TABLES",True):
            omit = False
            for sub in ['_valid','_datums','_aqi','_dayly','_Max8HRS','_DayAVG','_norm','Sensors','stations']:
                if tbl.find(sub) >= 0: omit = True      # omit some names
            if not omit: tbls.append(tbl)
        sys.stderr.write("Will only print all table names in the database.")
            
    MyPrint("Database %s tables:" % net['database'],P=True)
    cnt = 1
    for tbl in tbls:
        if len(args):
            MyPrint("Table %s has the following sensors:" % tbl,B=True)
            cnt = 1
            for col in db_query(resource['fd'],"DESCRIBE %s" % tbl,True):
                if col[0] == 'id': continue
                omit = False
                for sub in ['_valid']:
                    if col[0].find(sub) >= 0: omit = True      # omit some names
                if omit: continue
                if not (cnt%4): MyPrint("",B=True)
                print"  %14s" % col[0].ljust(14),
                cnt = cnt + 1
            MyPrint("",P=True)
        else:
            if not (cnt%4): MyPrint("")
            print "  %14s" % tbl.ljust(14),
            cnt = cnt + 1
    MyPrint("",B=True)
    if len(args):
        sys.exit("Please provide at least two sensor (column) definition arguments.")
    else:
        sys.exit("How to get an overview of sensors (columns) per table?: use only one argument e.g. \"DB_table_1/DB_table_2/...\"")
    
        
# print overview what databases and series are available from InFlux server
def showIF(net,args):
    global resource
    DB = resource['fd']
    if DB == None:
        sys.exit("FATAL No Influx module loaded.")
    sys.stderr.write("Define arguments (at least 2) for database_name/column_name/[date_name]/[type]/[serie_name]")
    sys.stderr.write("E.g. BdP_33040d54/pm25//PPD42NS/raw")
    tbls = []
    if len(args):
        tbls = args[0].split('/')
        try:
            tblNme = tbls[0]
            if not len(tblNme): raise ValueError
            measurements = influxMmnt(DB, tblNme)
            if len(measurements):
                MyPrint("For database %s found series: %s" % (tblNme,', '.join(measurements)),P=True)
            for mnt in measurements:
                flds = influxFlds(DB,tblNme,mnt)
                if not len(flds): continue
                MyPrint("Database %s measurement \"%s\" has fields: %s" % (tblNme,mnt,', '.join(flds)),B=True)
                types = influxTags(DB,tblNme,mnt,Type='type')
                if len(types):
                    MyPrint("Database %s measurement \"%s\" types: %s" % (tblNme,mnt,', '.join(types)),B=True)
        except:
            sys.exit("ERROR either to connect to InFlux server of query failure.")
    else:
        try:
            MyPrint("InFlux server has following databases: %s\n" % ', '.join(influxDBs(DB)),P=True)
        except:
            sys.exit("InFlux server: you need admin rights to get a database last.")

# print overview of columns in the spreadsheet
def showXLSX(args):
    sys.stderr.write("Define arguments (at least 2) for short_name/column_nr/[date_column_nr]/[type]")
    MyPrint("XLSX spreadsheet header info:",P=True)
    MyPrint("Column\tName",B=True)
    nr = 0
    wanted = []
    if len(args):
        strg = args[0].replace('\/','@')
        strg = strg.replace('/','|')
        strg = strg.replace('@','/')
        wanted = strg.split('|') 
    for I in list(Pandas['fd']):
        if len(args) and (not I in wanted): continue
        length = len(Pandas['fd'][I])
        dstr = ''
        if type(Pandas['fd'][I][0]) is Pandas['module'].tslib.Timestamp:
            dstr = 'period: %s' % datetime.datetime.strftime(datetime.datetime.fromtimestamp(Pandas['fd'][I][0].value // 10**9),'%Y-%m-%d %H:%M:%S')       
            dstr =  dstr + ' to %s' % datetime.datetime.strftime(datetime.datetime.fromtimestamp(Pandas['fd'][I][length-1].value // 10**9),'%Y-%m-%d %H:%M:%S')       
        MyPrint("%d\t\"%s\"\tcount=%d\t%s" % (nr,I,length,dstr),B=True)
        nr += 1
    sys.exit("Please provide at least two column definition arguments.")

# get the interesting part of the spreadsheet into the data area
def GetXLSX():
    header = list(Pandas['fd'])
    needs = {}
    try:
        for I in range(0,len(sensors)):
            sensors[I]['date'] = int(sensors[I]['date'])
            needs[sensors[I]['date']] = 1
            sensors[I]['column'] = int(sensors[I]['column'])
            needs[sensors[I]['column']] = 1
        for I in range(0,len(header)):
            if not I in needs.keys():
                del Pandas['fd'][header[I]]
        for I in range(0,len(sensors)):
            for key in ['date','column']:
                sensors[I][sensors[I][key]] = header[sensors[I][key]]
        start = datetime.datetime.strftime(datetime.datetime.fromtimestamp(timing['start']),'%Y-%m-%d %H:%M:%S')
        end = datetime.datetime.strftime(datetime.datetime.fromtimestamp(timing['end']),'%Y-%m-%d %H:%M:%S')
        Array = Pandas['fd'][Pandas['fd'][header[sensors[0]['date']]] >= start]
        Pandas['fd'] = Array
        Array = Pandas['fd'][Pandas['fd'][header[sensors[0]['date']]] <= end]
    except:
        sys.exit("xlsx/csv spreadsheet file: parse error or empty set.")
        return False
    Pandas['fd'] = Array
    return True

def FromXLSX(sensor):
    values = []
    length = len(Pandas['fd'][sensor[sensor['column']]])
    for I in range(0,len(Pandas['fd'][sensor[sensor['date']]])):
        if I >= length: break
        values.append([Pandas['fd'][sensor[sensor['date']]][I].value // 10**9,
        Pandas['fd'][sensor[sensor['column']]][I]])
    return values

        
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

################################ main part: configure what to do
# to identify database, tables, sensors and period
# TO DO: use DB per sensor entity
# TO DO: for sensor info use e.g.
#        table=BdP_XYZ,sensor=pm25,type=PPD42NS,date=time,db=mysql(user:ape,pass:aca,host:server,db:luchtmetingen)
#        table=BdP_XYZ,sensor=pm25,type=PPD42NS,date=time,serie=raw,db=influx(user:ape,pass:aca,host:server)
from_env('DB')          # get DB credentials from command environment
get_arguments()         # get command line arguments

MyPrint('Regression best fit calculation details for sensor type(s): %s' % ', '.join(set([elm['type'] for elm in sensors])),P=True)
if Pandas['input'] == None:
    MyPrint('Graphs based on data %s from %s on server %s as user %s:' % (resource['type'].upper(),net['database'],net['hostname'],net['user']),B=True)
else:
    MyPrint('Graphs based on spreadsheet xlsx/csv data from file %s' % Pandas['input'],B=True)
    

################################ get core of data
# we have to take slices from the matrix: row = [time in secs, values 1, values 2, ...]
Matrix = getArrays(net,sensors,timing)

MyPrint('Samples period: %s up to %s, interval timing %dm:%ds.' % (datetime.datetime.fromtimestamp(timing['start']).strftime('%b %d %H:%M'),datetime.datetime.fromtimestamp(timing['end']).strftime('%b %d %Y %H:%M'),interval/60,interval%60),P=True)
Stat = { 'min': [], 'max': [], 'avg': [], 'std': [] }

# some simple statistics
for I in range(0,len(sensors)):
    # roll in arrays for regression calculation
    Stat['min'].append(np.nanmin(Matrix[:,I+1]))
    Stat['max'].append(np.nanmax(Matrix[:,I+1]))
    Stat['avg'].append(np.nanmean(Matrix[:,I+1]))
    Stat['std'].append(np.nanstd(Matrix[:,I+1]))
    if normMinMax:
        MyPrint('Normalisation (min,max):',B=True)
        MyPrint('\t%s/%s [%6.2f,%6.2f] ->[0,1]' % (sensors[I]['table'],sensors[I]['column'],Stat['min'][I],Stat['max'][I]))
        Matrix[:,I+1] = Matrix[:,I+1] - Stat['min'][I]
        Matrix[:,I+1] /= (Stat['max'][I]-Stat['min'][I])
    if normAvgStd:
        MyPrint('Normalisation (avg-stddev,avg+stddev):',B=True)
        MyPrint('\t%s/%s [%6.2f,%6.2f] ->[-1,+1]' % (sensors[I]['table'],sensors[I]['column'],Stat['avg'][I]-Stat['std'][I],Stat['avg'][I]+Stat['std'][I]))
        Matrix[:,I+1] = Matrix[:,I+1] - Stat['avg'][I]
        if Stat['std'][I] > 1.0: Matrix[:,I+1] /= Stat['std'][I]

def getFit(fitMatrix):
    global sensors
    for sensor in range(0,len(sensors)): sensors[sensor]['Z0'] = None
    if (fitMatrix == None) or (len(sensors) != len(fitMatrix[0])):
        return
    for sensor in range(0,len(sensors)):
        # sensors[sensor]['Z0'] = list(reversed(list(fitMatrix[:,sensor])))
        sensors[sensor]['Z0'] = fitMatrix[:,sensor]

import statsmodels.api as sm
def getLMFit(sensor):
    global Matrix, sensors
    try:
        StatX = Matrix[:,sensor+1:]; StatX = sm.add_constant(StatX)
        reslts = sm.OLS(Matrix[:,1],StatX).fit()
    except ValueError as err:
        sys.stderr.write("ERROR: %s" % err)
        raise ValueError("Error in Linear Regression best fit calculation")
    if not 'R2' in sensors[sensor].keys():
        sensors[sensor]['R2'] = reslts.rsquared
    if not 'fit' in sensors[sensor].keys():
        sensors[sensor]['fit'] = reslts.params
    return reslts

########################### regression/fit part
Z  = np.polyfit(Matrix[:,1],Matrix[:,1:],order,full=True)
if not ml_mode:
    # calculate the polynomial best fit graph
    getFit(Z[0])
    
    # print("Rcond: %1.3e" % Z[4] )


yname = '%s/%s' % (sensors[0]['table'],sensors[0]['column'])
if not ml_mode:
    sensors[0]['fit'] = [0.0,1.0]; sensors[0]['R2'] = 0.0
    for I in range(1,len(sensors)):
        MyPrint("Data from table/sheet %s, sensor (column) %s:" % (sensors[I]['table'],sensors[I]['column']),B=True,P=True)
        if (I == 1) and (pngfile != None) and HTML:
            print("<a href=\"%s\"><img src=\"%s\" align=right width=300 alt=\"scatter image and graphs for sensor\"/></a>" % (os.path.basename(pngfile),os.path.basename(pngfile)))
        MyPrint("\tnumber %d, min=%5.2f, max=%5.2f" % (len(Matrix[:,I+1]),Stat['min'][I],Stat['max'][I]),B=True,I=True)
        MyPrint("\tavg=%5.2f, std dev=%5.2f" % (Stat['avg'][I],Stat['std'][I]),B=True,I=True)
        if I == 0: continue
        # if order == 1:
        #     R2 = get_r2_corrcoeff(Matrix[:,1],Matrix[:,2])
        #     R2 = get_r2_python( list(Matrix[:,1]),list(Matrix[:,2]))
        # else:
        sensors[I]['R2'] = get_r2_numpy(Matrix[:,1],Matrix[:,I+1],Z[0][:,I])
        results = getLMFit(I)
        xname = [ '%s/%s' % (sensors[I]['table'],sensors[I]['column'])]
    
        # print("\tBest fit polynomial regression curve (a0*X^0 + a1*X^1 + a2*X^2 + ...): ")
        # string = ', '.join(["%4.3e" % i for i in Z[0][:,I]])  # correct ???
        if HTML:
            MyPrint("\tR-squared (R²) with %s: %6.4f" % (xname[0],sensors[I]['R2']),B=True,I=True)
            MyPrint("Best fit linear single polynomial regression curve (A<sub>0</sub>*X<sup>0</sup> + A<sub>1</sub>*X<sup>1</sup>): ",B=True,I=True)
        else:
            MyPrint("\tR-squared (R<sup>2</sup>) with %s: %6.4f" % (xname[0],sensors[I]['R2']),B=True,I=True)
            MyPrint("Best fit linear single polynomial regression curve (A₀*X⁰ + A₁*X¹): ",B=True,I=True)
        MyPrint("\t%s (%s)-> best fit coefficients:" % (yname,sensors[I]['type']),B=True,I=True)
        MyPrint("\t%s" % ', '.join(["%4.3e" % i for i in sensors[I]['fit']]),B=True,I=True)

        MyPrint("Statistical summary linear regression for %s with %s:" % (yname,xname),P=True)
        summary = results.summary(xname=xname,yname=yname)
        if HTML:
            if PrevP: print("</p>");
            for i in range(0,len(summary.tables)):
                print("<p>")
                print(summary.tables[i].as_html())
                print("</p>")
            if PrevP: print("<p>")
        else: print(summary)
        # results.{params,tvalues,pvalues,fvalues,nobs,rsquared,rsquared_adj,scale,llf}
else:
    MyPrint('',P=True)
    MyPrint("Statistical multi linear regression for %s/%s with:" % (sensors[0]['table'],sensors[0]['column']))
    xname = []
    for I in range(1,len(sensors)):
        if (I == 1) and (pngfile != None) and HTML:
            print("<p><img src=\"%s\" align=right width=300 alt=\"scatter image and graphs for sensor\"/>" % pngfile)
        xname.append("%s/%s" % (sensors[I]['table'],sensors[I]['column']))
    MyPrint("%s" % ', '.join(xname))
    StatX = Matrix[:,2:]; StatX = sm.add_constant(StatX)
    for sensor in range(0,len(sensors)):
        sensors[sensor]['Z0'] = Z[0][:,I]
    try:
        results = sm.OLS(Matrix[:,1],StatX).fit()
        # TO DO: next needs some more thought: calibration polynomial or average poly?
        # results.{params,tvalues,pvalues,fvalues,nobs,rsquared,rsquared_adj,scale,llf}
        sensors[0]['fit'] = [0.0,1.0]     # is this correct to get polynomial coeffs???
        sensors[1]['fit'] = []
        for elm in results.params: sensors[1]['fit'].append(float(elm))
        sensors[0]['R2'] = sensors[1]['R2'] = results.rsquared
    except ValueError as err:
        sys.stderr.write("ERROR: %s" % err)
    if HTML:
        MyPrint("\tR-squared (R²) with %s: %6.4f" % (xname[0],sensors[I]['R2']),B=True,I=True)
        MyPrint("Best fit linear single polynomial regression curve (A<sub>0</sub>*X<sup>0</sup> + A<sub>1</sub>*X<sup>1</sup>): ",B=True,I=True)
    else:
        MyPrint("\tR-squared (R<sup>2</sup>) with %s: %6.4f" % (xname[0],sensors[I]['R2']),B=True,I=True)
        MyPrint("Best fit linear single polynomial regression curve (A₀*X⁰ + A₁*X¹): ",B=True,I=True)
    MyPrint("\t%s (%s)-> best fit coefficients:" % (yname,sensors[I]['type']),B=True,I=True)
    string = '%4.3e' % sensors[1]['fit'][0]
    for I in range(1,len(sensors[1]['fit'])):
        if len(string): string += ' + '
        string += "%e (%s)" % (sensors[1]['fit'][I],xname[I-1])
    MyPrint("%s" % string,I=True)

    MyPrint('',P=True)
    summary = results.summary(xname=xname,yname=yname)
    if HTML:
        if PrevP: print("</p>");
        for i in range(0,len(summary.tables)):
            print("<p>")
            print(summary.tables[i].as_html())
            print("</p>")
        if PrevP: print("<p>")
    else: print(summary)
            
##############################   plotting part ####################
def makeXgrid(mn,mx,nr):
    grid = (mx-mn)/(nr*1.0)
    # return np.linspace(mn, mx, 100)
    return [mn + i*grid for i in range(0,nr+1)]

# maybe numpy can do this simpler
# create a new matrix with values calculated using best fit polynomial
def getFitMatrix():
    global Matrix, sensors, Stat
    from numpy.polynomial.polynomial import polyval
    new = []
    for I in range(0,len(Matrix)):      # best fit value for these measurements
        row = []
        for J in range(1,len(Matrix[I])):
            row.append(polyval(Matrix[I][J],sensors[J-1]['fit']))
        new.append(row)
    new = np.array(new)
    fitStat = {'min':[], 'max':[], 'avg':[], 'std':[] }
    for I in range(0,len(sensors)):
        fitStat['min'].append(np.min(new[:,I]))
        fitStat['max'].append(np.max(new[:,I]))
        fitStat['avg'].append(np.average(new[:,I]))
        fitStat['std'].append(np.std(new[:,I]))
    return (new,fitStat)

# calculate y values for calibration graph
# TO DO: the following is probably only right for single linear regression ???
def mlArray():
    global Matrix, sensors
    new = []
    for I in range(0,len(Matrix)):
        val = sensors[1]['fit'][0]
        for J in range(1,len(sensors[1]['fit'])): val += Matrix[I][J+1] * float(sensors[1]['fit'][J])
        new.append(val)
    return np.array(new)

# plot a spline of dates/measurements for each sensor
def SplinePlot(figure,gs,base):
    global Stat, fitStat, sensors, Matrix, colors, results
    from matplotlib import dates
    ax = figure.add_subplot(gs[base,0])
    string = "Graphs of measurements for period: %s up to %s" % (datetime.datetime.fromtimestamp(timing['start']).strftime('%b %d %H:%M'),datetime.datetime.fromtimestamp(timing['end']).strftime('%b %d %Y %H:%M'))

    ax.set_title(string, fontsize=8)
    times = [int(elmt) for elmt in Matrix[:,0]]
    fds = dates.date2num(map(datetime.datetime.fromtimestamp, times))
    for tick in ax.get_xticklabels(which='minor'):
        tick.set_fontsize(8) 
    for tick in ax.get_xticklabels(which='major'):
        tick.set_rotation(-45)
    if (timing['end']-timing['start'])/(24*60*60) < 7:
        ax.xaxis.set_major_locator(dates.DayLocator(interval=1))
        ax.xaxis.set_major_formatter(dates.DateFormatter('%m/%d'))
        ax.xaxis.set_minor_locator(dates.HourLocator(byhour=[6,12,18]) )
        ax.xaxis.set_minor_formatter(dates.DateFormatter('%0Hh'))
    elif (timing['end']-timing['start'])/(24*60*60) < 21:
        ax.xaxis.set_major_locator(dates.DayLocator(interval=2))
        ax.xaxis.set_major_formatter(dates.DateFormatter('%m/%d'))
        ax.xaxis.set_minor_locator(dates.HourLocator(byhour=[6,12,18]) )
    else:
        ax.xaxis.set_major_locator(dates.DayLocator(interval=7))
        ax.xaxis.set_major_formatter(dates.DateFormatter('%m/%d'))
        ax.xaxis.set_minor_locator(dates.HourLocator(byhour=12) )
        # ax.xaxis.set_minor_formatter(dates.DateFormatter(''))
    plt.subplots_adjust(bottom=.3)
    ax.set_ylabel('scaled to avg %s/%s (%s)' %(sensors[0]['table'],sensors[0]['column'],
                sensors[0]['type']), fontsize=8 , fontweight='bold')

    (fitMatrix,fitStat) = getFitMatrix()
    for I in range(1,len(Matrix[0,:])): # leave gaps blank
        if ml_mode and (I > 2): break
        strt = -1; lbl = None
        nr = len(Matrix[:,0])
        # TO DO: why do we need scaling?
        # scaled =  Stat['avg'][0]/Stat['avg'][I-1] #  ???? TO CORRECT
        scaled = 1.0
        fitscaled = fitStat['avg'][0]/fitStat['avg'][I-1]
        if (scaled > 95.0) and (scaled < 105.0): scalemsg = ''
        else: scalemsg = ' %3.1f%% scaled' % (scaled*100.0)
        while strt < nr-2:
            strt += 1
            if abs(Matrix[strt,0]-Matrix[strt+1,0]) > interval*2: continue
            end = strt
            while True:
                end += 1
                if end >= nr: break
                if abs(Matrix[end,0]-Matrix[end-1,0]) > interval*2: break
            if lbl == None:
                lbl = '%s/%s %s(%s)' % (sensors[I-1]['table'],sensors[I-1]['column'],scalemsg,sensors[I-1]['type'])
            ax.plot(fds[strt:end],Matrix[strt:end,I]*scaled, '-', c=colors[I%len(colors)], label=lbl)
            # TO DO: what is the fit polynomial?
            if I > 1:       # add best fit correction graph
                if len(lbl): lbl += ' correction fit'
                ax.plot(fds[strt:end],fitMatrix[strt:end,I-1] * fitscaled, ':', c=colors[I%len(colors)], linewidth=2, label=lbl)
            strt = end-1
            lbl = ''

    # Set the fontsize
    legend = ax.legend(loc='upper left', labelspacing=-0.1, shadow=True)
    for label in legend.get_texts():
        label.set_fontsize(7)
    for label in legend.get_lines():
        label.set_linewidth(1.5)  # the legend line width
    legend.get_frame().set_facecolor('0.95')
    legend.get_frame().set_linewidth(0.01)

# plot a scattered plot range of max MaxPerGraphs scatter plots in one subplot
def ScatterPlot(figure,gs,base):
    global Stat, sensors, Matrix, MaxPerGraph, colors, props, results, Z
    ax = None; strg1 = strg2 = ''
    for I in range(1,len(sensors)):
        # the graphs
        nr_graphs = 0
        ax = figure.add_subplot(gs[base+(I/MaxPerGraph),0])

        # title of the plot
        if not (I-1)%MaxPerGraph:
            ax.set_title("for period: %s up to %s" % (datetime.datetime.fromtimestamp(timing['start']).strftime('%b %d %H:%M'),datetime.datetime.fromtimestamp(timing['end']).strftime('%b %d %Y %H:%M')),fontsize=8)

        # box with text for each graph
        if (I%MaxPerGraph) == 1:
            strg1 = "R$^2$=%6.4f, order=%d" % (sensors[I]['R2'], order)
            strg1 += "\n%s/%s: %5.2f(avg), %5.2f(std dev), %5.2f(min), %5.2f(max)" % (sensors[0]['table'],sensors[0]['column'],
                Stat['avg'][0],Stat['std'][0],Stat['min'][0],Stat['max'][0])
            strg2 = '\n\nBest fit ml polynomials (low order first):'
            strg2 += "\n%s/%s: [%s]" % (sensors[0]['table'],sensors[0]['column'],'0, 1')
        for J in range(I,I+MaxPerGraph):
            if ml_mode and (I > 2): break
            if J == len(sensors): break
            nr_graphs += 1
            strg1 += "\n%s/%s: %5.2f(avg), %5.2f(std dev), %5.2f(min), %5.2f(max)" %(sensors[J]['table'],sensors[J]['column'],
                Stat['avg'][J],Stat['std'][J],Stat['min'][J],Stat['max'][J])
        if normMinMax: strg1 += ', (min,max)->(0,1) normalized'
        if normAvgStd: strg1 += ', (avg, std dev) -> (0,1) normalized'
        for J in range(I,I+MaxPerGraph):
            if ml_mode and (I > 2): break
            if J == len(sensors): break
            strg2 += "\n%s/%s: [%s]" % (sensors[J]['table'],sensors[J]['column'],', '.join(["%4.3e" % i for i in sensors[J]['fit']]))
        if (I == (len(sensors)-1)) or ((MaxPerGraph-1) == (I%MaxPerGraph)):
            ax.text(0.03, 0.96, strg1+strg2, transform=ax.transAxes, fontsize=8,
                verticalalignment='top', bbox=props)
            strg1 = strg2 = ''

        # legend text(s)
        if not (I-1)%MaxPerGraph:
            ax.set_xlabel('table %s sensor (column) %s (%s)' %(sensors[0]['table'],
                sensors[0]['column'],sensors[0]['type']), fontsize=8, fontweight='bold')
        label = ''
        if nr_graphs == 1:
            ax.set_ylabel('table %s sensors (column) %s (%s)' %(sensors[I]['table'],sensors[I]['column'],
                sensors[I]['type']), fontsize=8 , fontweight='bold')
        else:
            label = '%s/%s (%s)' % (sensors[I]['table'],sensors[I]['column'],sensors[I]['type'])
        
        # the scatter and best fit graph(s)
        for J in range(I,I+MaxPerGraph):
            if J >= len(sensors): break
            ax.plot(Matrix[:,1], Matrix[:,J+1], 'o', c=colors[J%MaxPerGraph],markersize=3, label='%s' % label)
            if ml_mode and (J != 1): continue # next in ml_mode does not make sense
            if not ml_mode:
                color = colors[J%MaxPerGraph]
            else: color = 'r'
            # ax.plot(sortedX, np.poly1d(list(reversed(sensors[J]['fit'])))(sortedX), '-', c=color, label='%s versus %s' % (sensors[0]['type'],sensors[J]['type']))
            ax.plot(sortedX, np.poly1d(sensors[J]['Z0'])(sortedX), '-', c=color, label='%s versus %s' % (sensors[0]['type'],sensors[J]['type']))
            xtxt = (np.max(sortedX)+np.min(sortedX))/2
            ax.annotate("best fit\n%s/%s ~ %s/%s" % (sensors[0]['table'],sensors[0]['column'],sensors[I]['table'],sensors[I]['column']),
                xy=(xtxt,np.poly1d(sensors[J]['Z0'])(xtxt)),
                ha='center', va='top', fontsize=7.5, color='black',
                bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.3),
                xytext=(xtxt*1.02,np.poly1d(sensors[J]['Z0'])(xtxt) * 0.92),
                arrowprops=dict(color='gray', arrowstyle='->', connectionstyle='arc3,rad=0.5'))
        I = J-1    

        if len(label):
            # Set the fontsize
            legend = ax.legend(loc='lower right', labelspacing=-0.1, shadow=True)
            for label in legend.get_texts():
                label.set_fontsize(7)
            for label in legend.get_lines():
                label.set_linewidth(1.5)  # the legend line width
            legend.get_frame().set_facecolor('0.95')
            legend.get_frame().set_linewidth(0.01)
    
if show:
    import matplotlib.pyplot as plt
    from matplotlib import gridspec
    base = 0    # base for scatter graphs
    if SHOW: base = 1
    if normMinMax:
        sortedX = makeXgrid(0,1,100)
    elif normAvgStd:
        dev = Stat['std'][0]
        if Stat['std'][0] < 1.0: dev = 1.0
        sortedX = makeXgrid((Stat['min'][0]-Stat['avg'][0])/dev,(Stat['max'][0]-Stat['avg'][0])/dev,100)
    else:
        sortedX = makeXgrid(Stat['min'][0],Stat['max'][0],100)

    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    # fig = plt.figure(tight_layout=True, figsize=(7.5,(base+(len(sensors)/MaxPerGraph)+1) *5.0))
    Width = 7.5
    Height = 5
    if SHOW: Height *= 2
    fig = plt.figure(tight_layout=True, figsize=(Width,Height))
    # fig = plt.figure()
    # left=0.1, bottom=0.1, right=0.97, top=0.93, wspace=0.25, hspace=0.25
    # fig.subplots_adjust(top=0.93, bottom=0.5, left=0.2, right=0.2)
    # create some bling bling
    #fig.suptitle('Data from %s, best fit polynomial for type(s): %s' % (net['database'],', '.join(set([elmt['type'] for elmt in sensors]))),
    #    fontsize=9, fontweight='bold')
    gs = gridspec.GridSpec(base + (len(sensors)-1)/MaxPerGraph+1,1)
    # bottom declaration
    fig.text(0.98, 0.015, 'generated %s by pyplot/numpy' % datetime.datetime.fromtimestamp(time()).strftime('%d %b %Y %H:%M'),
        verticalalignment='bottom', horizontalalignment='right',
        color='gray', fontsize=8)

    if SHOW: SplinePlot(fig,gs,0)
    ScatterPlot(fig,gs,base)

    if pngfile != None:
        plt.savefig(pngfile, bbox_inches='tight')
    else:
        plt.show()
