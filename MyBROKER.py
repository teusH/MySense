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

# $Id: MyBROKER.py,v 2.6 2017/06/04 09:40:55 teus Exp teus $

# TO DO: write to file or cache

""" Publish measurements to a simple broker
    Relies on Conf setting biy main program
"""
modulename='$RCSfile: MyBROKER.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.6 $"[11:-2]

try:
    import MyLogger
    import sys
    import json
    import socket
    socket.setdefaulttimeout(30)
    import requests
except ImportError as e:
    MyLogger.log(modulename,"FATAL","One of the import modules not found: %s" % e)

# configurable options
__options__ = ['output','hostname','port','url','apikey']

Conf = {
    'output': False,     # Broker
#    'fd': None,          # input handler
    'hostname': 'localhost',  # host to access
    'port': '8081',      # port may also be port 80
    'url': 'node',   # server port number for brokers
    'apikey': None,      # no shared secret, so everybody can see it
    'registrated': None, # has send identification to broker on boot
    'ttl': None,         # time in secs to live for forced new registration
    'omit': [],          # omit to send these items
    'fd': None,          # 1 internet connect success, 0 connectivity broke down
#   'renew': None,       # time to renew registration
#    'file': None,       # Debugging: write to file
}

# =======================================================
# post json data to a broker for nodes somewhere internet land
# =======================================================
# use MQTT telegram style

# =======================================================
# once per session registrate and receive session cookie
# =======================================================
# TO DO: this needs to have more security in it e.g. add apikey signature
def registrate(ident,net):
    global Conf
    if Conf['registrated'] != None:
        if (not 'ttl' in Conf.keys()) or (not Conf['ttl']):
            return Conf['registrated']
        if not 'renew' in Conf.keys():
            Conf['renew'] = int(time())+Conf['ttl']
        if time() < Conf['renew']:
            return Conf['registrated']
    if (not net['module'].internet(ident)) or (not 'apikey' in Conf.keys()) and len(Conf['apikey']):
        Conf['registrated'] = False
        return False
    request = {}
    request['project'] = ident['project']
    request['serial'] = ident['serial']
    if len(ident['extern_ip']):
        request['extern_ip'] = ident['extern_ip']
    if 'geolocation' in ident.keys():
        request['geolocation'] = ident['geolocation']
    if 'apikey' in ident.keys():
        request['apikey'] = ident['apikey']
    else:
        request['apikey'] = 'unknown'
    if 'fields' in Conf['omit']:
        request['items'] = []
        if ('fields' in ident.keys()):
            for i in range(0,len(ident['fields'])):
                request['items'].append(ident['fields'][i] + ':' + ident['units'][i])
    headers = {'content-type': 'application/json', 'X-Sensors-APIkey': 'registrate'}
    Conf['fd'] = 0
    try:
        r = requests.post('https://'+Conf['hostname']+':'+Conf['port']+'/'+Conf['url'], data=json.dumps(request), headers=headers)
        # should receive a session key cookie Conf['session']['cookie'] = cookie
        # and check cookie for new regsitration
        Conf['registrated'] = True
        Conf['fd'] = 1
        MyLogger.log(modulename,'DEBUG',"Registration request sent to broker")
    except IOError:
        MyLogger.log(modulename,'ERROR','Internet connection is failing')
        raise IOError('Broker connectivity error')
        return False
    except:
        MyLogger.log(modulename,'ERROR',"Sending registration to url %s" % Conf['url'])
        Conf['registrated'] = False
    return Conf['registrated']

def publish(**args):
    global Conf
    if (not Conf['output']) or (not Conf['apikey']):
        return
    for key in ['data','internet','ident']:
        if not key in args.keys():
            MyLogger.log(modulename,'FATAL',"Broker publish call missing argument %s." % key)
    if not args['internet']['module'].internet(ident,args['internet']):
        Conf['output'] = False # to do: add recovery time out
        MyLogger.log(modulename,'ERROR',"No internet access. Abort broker output.")
        return False
    if not 'fd' in Conf.keys(): Conf['fd'] = None
    if not 'last' in Conf.keys():
        Conf['waiting'] = 5 * 30 ; Conf['last'] = 0 ; Conf['waitCnt'] = 0
    # obtain session registration via broker (to do: needs some work)
    if (not Conf['fd']) and (time() < (Conf['last']+Conf['waiting'])):
        raise IOError('Broker has to wait')
        return False
    try:
        if (not 'registrated' in Conf.keys()) or (not Conf['registrated']):
            registrate(args['ident'])

        headers = {'content-type': 'application/json', 'X-Sensors-APIKEY': Conf['broker']['apikey']}
        if ('cookie' in Conf.keys()) and len(Conf['cookie']):
            request['cookie'] = Conf['cookie']
        r = requests.post('https://'+Conf['hostname']+':'+Conf['port']+'/'+Conf['url'], data=json.dumps(request), headers=headers)
        MyLogger.log(modulename,'DEBUG',"Data send to broker")
    except IOError:
        MyLogger.log(modulename,'WARNING','Broker internet connectivity error.')
        Conf['last'] = time() ; Conf['fd'] = 0 ; Conf['waitCnt'] += 1
        Conf['registrated'] = None      # force registrate
        if not (Conf['waitCnt'] % 5): Conf['waiting'] *= 2
        raise IOError("Broker repeated access try failed")
        return False
    except:
        MyLogger.log(modulename,'ERROR',"Sending data to url %s" % Conf['url'])
        Conf['output'] = False
        return False
    Conf['last'] = time(); Conf['waitCnt'] = 0
    return True

