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

# $Id: Calibrate.py,v 1.2 2017/04/10 19:20:40 teus Exp teus $

""" Create and show best fit for two columns of values from database
"""
progname='$RCSfile: Calibrate.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.2 $"[11:-2]

try:
    import sys
    import mysql
    import mysql.connector
    import datetime
    import math
    from time import time
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError as e:
    print ("One of the import modules not found: %s" % e)
    exit(1)

def db_connect(net):
    for M in ('user','password','hostname','database'):
        if (not M in net.keys()):
            print("Please provide credential %s" % M)
            exit(1)
    try:
        DB = mysql.connector.connect(
                charset='utf8',
                user=net['user'],
                password=net['password'],
                host=net['hostname'],
                port=net['port'],
                database=net['database'])
    except:
        print("Unable to connect to database %s on host %s" %(net['database'],net['hostname']))
        exit(1)
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
        print("Database query \"%s\" failed with:\ntype: \"%s\"\nvalue: \"%s\"" %(query,sys.exc_info()[0],sys.exc_info()[1]))
        exit(1)
    return True

def getColumn(db,table,period):
    qry = "SELECT UNIX_TIMESTAMP(datum),(if(isnull(%s),'nan',%s)) FROM %s WHERE UNIX_TIMESTAMP(datum) >= %d AND UNIX_TIMESTAMP(datum) <= %d order by datum" % \
        (table['column'],table['column'],table['name'],timing['start'],timing['end'])
    values = db_query(db,qry, True)
    for i in range(len(values),0):
        while (not type(values[i][1]) is int) and (not type(values[i][1]) is float):
            values.pop(i)
    return values

X = []
Y = []
maxX = None
maxY = None
scale = None
def getArrays(net,table1,table2,timing,interval=600):
    global X, Y, maxX, maxY
    DB = db_connect(net)
    DX = getColumn(DB,table1,timing)
    DY = getColumn(DB,table2,timing)
    DB.close()
    X = []; Y = []
    ty = -1
    for tx in range(0,len(DX)):
        ty += 1
        if ty > len(DY)-1: break
        if DX[tx][0] < DY[ty][0]-interval: continue
        while DX[tx][0] > DY[ty][0]+interval:
            ty += 1
            if ty > len(DY)-1: break
        if ty > len(DY)-1: break
        fltX = float(DX[tx][1])
        fltY = float(DY[ty][1])
        if maxX == None:
            maxX = fltX
            maxY = fltY
        if maxX < fltX: maxX = fltX
        if maxY < fltY: maxY = fltY
        X.append(fltX)
        Y.append(fltY)
    return

net = {
        'hostname': 'lunar',
        'user': 'teus',
        'password': 'acacadabra',
        'database': 'luchtmetingen',
        'port': 3306
    }
table1 = { 'name': 'BdP_8d5ba45f', 'column': 'pm_10' }
table2 = { 'name': 'BdP_3f18c330', 'column': 'pm10' }
timing = { 'start': time() - 24*60*60, 'end': time() }
interval = 600
order = 1       # polynomium order: default linear regression best fit line
show = False    # show the graph and regression polynomium

def get_arguments():
    """ Command line argument roll in """
    import argparse
    global progname
    global net, table1, table2, timing, interval, order, show
    parser = argparse.ArgumentParser(prog=progname, description='Get from two tables a table for a period of time and calculate the regression', epilog="Copyright (c) Behoud de Parel\nAnyone may use it freely under the 'GNU GPL V4' license.")
    parser.add_argument("-H", "--hostname", help="Database host name, default: %s" % net['hostname'], default="%s" % net['hostname'])
    parser.add_argument("-U", "--user", help="Database user name, default: %s" % net['user'], default="%s" % net['user'])
    parser.add_argument("-P", "--password", help="Database password, default: %s" % net['password'], default="%s" % net['password'])
    parser.add_argument("-D", "--database", help="Database name, default: %s" % net['database'], default="%s" % net['database'])
    parser.add_argument("-1", "--table1", help="Database table one/column name, default: %s/%s" % (table1['name'],table1['column']), default="%s/%s" % (table1['name'],table1['column']))
    parser.add_argument("-2", "--table2", help="Database table two/column name, default: %s/%s" % (table2['name'],table2['column']), default="%s/%s" % (table2['name'],table2['column']))
    parser.add_argument("-i", "--interval", help="Interval sample timing (two values in same sample time) in seconds, default: %d" % 600, default="%d" % interval)
    parser.add_argument("-t", "--timing", help="Database period of time UNIX start-end seconds, default: %d-%d" % (timing['start'],timing['end']), default="%d-%d" % (timing['start'],timing['end']))
    parser.add_argument("-o", "--order", help="best fit polynomium order, default: linear regression best fit line (order 2)", default=order)
    parser.add_argument("-s", "--show", help="show graph, default: graph is not shown", default=False, choices=['False','True'])
    # overwrite argument settings into configuration
    args = parser.parse_args()
    net['hostname'] = args.hostname
    net['user'] = args.user
    net['password'] = args.password
    net['database'] = args.database
    table1['name'] = args.table1.split('/')[0]
    table1['column'] = args.table1.split('/')[1]
    table2['name'] = args.table2.split('/')[0]
    table2['column'] = args.table2.split('/')[1]
    timing['start'] = int(args.timing.split('-')[0])
    timing['end'] = int(args.timing.split('-')[1])
    interval = int(args.interval)
    order = int(args.order)
    show = bool(args.show)

# get command line arguments to identify database, tables, columns and period
get_arguments()

getArrays(net,table1,table2,timing,interval)
Xnp = np.array(X, dtype=float)
Ynp = np.array(Y, dtype=float)
Z = np.polyfit(Xnp,Ynp,order,full=True)

if order == 1: scale = (maxY/maxX)
print("Best fit polynomial regression curve: ",Z[0][::-1])
print("Rcond: %e" % Z[4] )

def regression(z,x):
    global scale
    y = []
    for i in range(0,len(x)):
        y.append(0.0)
        for j in range(0,len(z)):
            y[i] += z[j]*(pow(x[i],j))
    return y

if show:
    sortedX = []
    for i in X: sortedX.append(i)
    sortedX.sort()
    plt.plot(X, Y, 'o', sortedX, regression(Z[0][::-1],sortedX), 'r', markersize=3, label='')
    plt.xlabel('table %s column %s' %(table1['name'],table1['column']))
    plt.ylabel('table %s column %s' %(table2['name'],table2['column']))
    plt.title('Plot %s/%s - %s/%s' %(table1['name'],table1['column'],table1['name'],table1['column']))
    plt.legend()
    plt.show()
