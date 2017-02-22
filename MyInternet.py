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

# $Id: MyInternet.py,v 2.3 2017/02/01 12:47:13 teus Exp teus $

# TO DO:

""" Maintain internet connection and info about the ip and rssi values
"""
modulename='$RCSfile: MyInternet.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.3 $"[11:-2]

# configurable options
__options__ = []

Conf = {
    # 'connected': defined?,  # if key defined and is there internet?
    # 'last':     None,   # last time checked to throddle connection info
}

try:
    import MyLogger
    import re
    import subprocess
    from time import time
    from random import shuffle
    import socket
    try:
        import urllib2 as urlreq
        from urllib2 import URLError
    except ImportError:
        import urllib.request as urlreq
        from urllib.error import URLError
except ImportError as e:
    MyLogger.log('FATAL',"Unable to load module %s" % e)

# see if there is an internet connection.
# on wifi provide rssi strength
# return None on no internet, rssi strength 0 on no wifi otherwise rssi strength
def internet(ident):
    global Conf
    def get_internal_ip(ident):
        global Conf
        if 'connected' in Conf.keys():
            if Conf['connected'] != None:
                return Conf['connected']
        Conf = { 'connected': False, 'intern_ip': [], 'extern_ip': None }
        try:
            p=subprocess.Popen('/sbin/ifconfig',shell=True,stdout=subprocess.PIPE)
            stdout, stderr = p.communicate()
            ips = re.findall('addr:\s*([0-9a-f]+([\.:][0-9a-f]+)+)', stdout)
            for item in ips:
                # TO DO: may need to exclude wifi AP ip addresses
                if (item[0][0:4] != '127.') and (item[0][0:5] != 'fe80:'):
                    Conf['intern_ip'].append(item[0])
            if len(Conf['intern_ip']):
                ident['intern_ip'] = Conf['intern_ip']
                Conf['connected'] = True
        except:
            Conf['connected'] = False
        return Conf['connected']

    def get_external_ip(ident):
        # if this fails there might be still an internet connection
        global Conf
        if not get_internal_ip(ident):
            return False
        if (Conf['extern_ip'] != None):
            if len(Conf['extern_ip']):
                ident['extern_ip'] = Conf['extern_ip']
                return True
            else:
                return False
        Us = ["checkip.dyndns.org","www.privateinternetaccess.com/pages/whats-my-ip/","cmyip.com","ipinfo.com"]
        #Us = ["http://checkip.dyndns.org"]
        shuffle(Us)
        site = '' ; grap = []
        for U in Us:
            try:
                # allow max wait as 30 seconds
                MyLogger.log('DEBUG',"External IP address, try http://%s" % U)
                site = urlreq.urlopen('http://'+U, timeout=30).read()
                grap = re.findall('([1-9][0-9]{0,2}(\.[1-9][0-9]{0,2}){3}|[0-9a-fA-F]{1,4}(:[0-9a-fA-F]{1,4}){3,6})', site)
                if len(grap):
                    break
            except URLError as e:
                MyLogger.log('ERROR',"No external due to " + e.reason)
                return False
            except:
                pass
        if len(grap):
            Conf['extern_ip'] = []
            for item in grap:
                if not item[0] in Conf['extern_ip']:
                    Conf['extern_ip'].append(item[0])
            ident['extern_ip'] = Conf['extern_ip']
            return True
        return False

    socket.setdefaulttimeout(30)

    if not get_internal_ip(ident):
        return False
    try:
        get_external_ip(ident)
    except:
        return False
    return True

