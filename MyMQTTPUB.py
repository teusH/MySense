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

# $Id: MyMQTTPUB.py,v 1.9 2018/05/28 11:49:02 teus Exp teus $

# module mqtt: git clone https://github.com/eclipse/paho.mqtt.python.git
# cd paho.mqtt.python ; python setup.py install
# broker server: Debian: apt-get install mqtt

# TO DO: write to file or cache

""" Publish measurements as client to a Mosquitto broker
    Subscribe to measurements from a Mosquitto Broker server
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyMQTTPUB.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.9 $"[11:-2]

try:
    import MyLogger
    import sys
    import json
    import socket
    from time import time, sleep
    socket.setdefaulttimeout(30)
    import paho.mqtt.client as mqtt
except ImportError as e:
    MyLogger.log(modulename,"FATAL","One of the import modules not found: %s" % e)

# configurable options
__options__ = ['output','hostname','user','password','apikey','prefix','topic','cert','ttl']

Conf = {
    'output': False,     # output to MQTT broker is required
    'hostname': 'localhost', # server host number for mqtt broker
    'port': 1883,        # default MQTT port
    'user': None,        # user/password
    'password': None,    # credentials to access broker
    'cert' : None,       # X.509 encryption
    'topic': 'IoS',      # Internet of Sense base of topic
                         # to do: use hash(apikey,int(time)) as session key
                         # sent at register time and checked by broker with data
    'prefix': 'IoS_',     # client id prefix key
    'apikey': None,      # no shared secret, so everybody can see it
    'timeout' : 2,       # timeout for this broker
    'omit': ['intern_ip'],  # omit to send these items, obey PII ruling
    'fd': None,          # 1 once connected, 0 if connectivity broke
#    'file': None,       # Debugging: write to file
}

waiting = False
mid = None
# =======================================================
# post json data to a MQTT broker for nodes somewhere internet land
# =======================================================
# use telegram style

def PubOrSub(topic,telegram):
    """ Send or Receive a telegram to/from MQTT broker server """
    global Conf, waiting, mid
    waiting = False
    mid = None

    # Define event callbacks
    def on_connect(client, obj, rc):
        global waiting
        if rc != 0:
            if rc == 5:
                rc = "Not Authorized"
            else:
                rc = str(rc)
            Conf['output'] = False
            waiting = False
            raise IOError("MQTT broker publish connect failure: %s." % rc)
        else:
            MyLogger.log(modulename,'DEBUG',"Connected to publishing broker")
            pass
    
    def on_publish(client, obj, MiD):
        global waiting, mid
        waiting = False
        mid = MiD
        MyLogger.log(modulename,'DEBUG',"Publish mid: " + str(mid))
    
    def on_log(client, obj, level, string):
        MyLogger.log(modulename,'DEBUG',"Broker: %s" % string)

    def on_disconnect(client, obj, MiD):
        global waiting, mid
        waiting = False
        mid = MiD
        MyLogger.log(modulename,'DEBUG',"On disconnect mid: " + str(mid) )

    Conf['fd'] = 1
    try:
        mqttc = mqtt.Client(Conf['prefix']+Conf['apikey'])     # unique client ID
        mqttc.on_connect = on_connect
        mqttc.on_disconnect = on_disconnect
        try:
            ['NOTSET','DEBUG'].index(MyLogger.Conf['level'])
            mqttc.on_log = on_log
        except: pass
        if telegram != None:
            mqttc.on_publish = on_publish
        else:
            mqttc.on_subscribe = on_subscribe
        if ('user' in Conf.keys()) and Conf['user'] and ('password' in Conf.keys()) and Conf['password']:
            mqttc.username_pw_set(username=Conf['user'],password=Conf['password'])

        mqttc.connect(Conf['hostname'], Conf['port'])
        Conf['fd'] = 1
        timeout = time() + Conf['timeout']
        waiting = True
        mqttc.loop_start()
        mqttc.publish(topic,telegram)
        while waiting:
            if time() > timeout:
                break
            sleep(1)       # maybe it should depend on timeout
        # mqttc.disconnect()
        mqttc.loop_stop()
    except:
        MyLogger.log(modulename,'ERROR',"Failure type: %s; value: %s. MQTT broker aborted." % (sys.exc_info()[0],sys.exc_info()[1]) )
        raise IOError
        return False
    if waiting:
        MyLogger.log(modulename,'ATTENT',"Sending telegram: wait")
        raise IOError
        return False
    MyLogger.log(modulename,'DEBUG',"Sent telegram, waiting = %s, message id: %s" % (str(waiting),str(mid)) )
    return True

# mqttc = mosquitto.Mosquitto()
# # Assign event callbacks
# mqttc.on_message = on_message
# mqttc.on_connect = on_connect
# mqttc.on_publish = on_publish
# mqttc.on_subscribe = on_subscribe
# 
# Uncomment to enable debug messages
#mqttc.on_log = on_log

# =======================================================
# once per session registrate and receive session cookie
# =======================================================
# TO DO: cert: this needs to have more security in it
# unique id: <project>_<serial> (apikey) credentials: user/password
# topic: IoS/register/<project>/<serial>
# pay load items: version,ident fields
def registrate(args):
    global Conf, mqtt
    for key in ['ident','internet','data']:
        if not key in args.keys():
            MyLogger.log(modulename,'FATAL',"Register call missing argument %s." % key)
    if (not type(args['internet']['module']) is bool) and (not args['internet']['module'].internet(args['ident'])):
        Conf['output'] = False
        return False

    if (Conf['fd'] != None) and (not Conf['fd']):
        if ('waiting' in Conf.keys()) and ((Conf['waiting']+Conf['last']) >= time()):
            raise IOError
            return False

    if (not 'apikey' in Conf.keys()) or (Conf['apikey'] == None):
        Conf['apikey'] = "%s_%s" % (args['ident']['project'],args['ident']['serial'])
    request = { 'apikey': Conf['apikey'] }
    for fld in args['ident'].keys():
        if fld in Conf['omit']: # use PII rules for this
            continue
        if ('fld' == 'extern_ip') and ('extern_ip' in args['internet'].keys()):
            request[fld].extend(args['internet'][fld])  # mqtt route taken
        if (args['ident'][fld] != None) and len(args['ident'][fld]):
            if key == 'fields':
                request['items'] = []
                if ('fields' in args['ident'].keys()) and (args['ident']['fields'] != None) and len(args['ident']['fields']):
                    for i in range(0,len(args['ident']['fields'])):
                        request['items'].append(args['ident']['fields'][i] + ':' + args['ident']['units'][i])
            else:
                request[fld] = args['ident'][fld]
    data = {}
    if 'fields' in args['ident'].keys():
        for key in args['ident']['fields']:  # only values defined in fields array
            data[key] = None
            if key in args['data'].keys():
                data[key] = args['data'][key]
    data = json.dumps({ 'metadata': request, 'data': data })
    topic = '%s/%s/%s' % (Conf['topic'],request['project'],request['serial'])
    try:
        PubOrSub(topic, data)
        Conf['waiting'] = 5 * 30 ; Conf['last'] = 0 ; Conf['waitCnt'] = 0
    except IOError as e:
        Conf['last'] = time() ; Conf['fd'] = 0 ; Conf['waitCnt'] += 1
        if not (Conf['waitCnt'] % 5): Conf['waiting'] *= 2
        MyLogger.log(modulename,'ERROR',"Sending registration to %s, error: %s" % (Conf['hostname'],e))
        raise IOError
        return False
    return True

ErrorCnt = 0
def publish(**args):
    global Conf, ErrorCnt
    if (not Conf['output']) or (ErrorCnt > 20):
        return False
    for key in ['ident','data','internet']:
        if not key in args.keys():
            MyLogger.log(modulename,'FATAL',"Publish call missing argument %s." % key)
    if (not type(args['internet']['module']) is bool) and (not args['internet']['module'].internet(args['ident'])):
        Conf['output'] = False # to do: add recovery time out
        MyLogger.log(modulename,'ERROR',"No internet access. Abort broker output.")
        return False
    for key in ['apikey']:      # force to ident
        if (key in Conf.keys()) and (Conf[key] != None) and len(Conf[key]):
            args['data'][key] = Conf[key]
    if not 'fd' in Conf.keys(): Conf['fd'] = None
    if not 'last' in Conf.keys():
        Conf['waiting'] = 5 * 30 ; Conf['last'] = 0 ; Conf['waitCnt'] = 0

    # obtain session registration via broker (to do: needs some work)
    if not registrate(args):
        ErrorCnt += 1
        return False
    ErrorCnt = 0
    return True

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['output'] = True
    Conf['hostname'] = 'lunar'         # host InFlux server
    Conf['user'] = 'ios'               # user with insert permission of InFlux DB
    Conf['password'] = 'acacadabra'    # DB credential secret to use InFlux DB

    # try to see the telegrams sent via
    # topic: Conf['topic']/ident 'project'/ident 'serial'
    # telegram: { 'data': {}, 'metadata': {} }
    # mosquitto_sub -u ios -P acacadabra -h lunar -t IoS/BdP/+

    net = { 'module': True, 'connected': True }
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
                internet = net
            )
        except Exception as e:
            print("output channel error was raised as %s" % e)
            break
        timings = 30 - (time()-timings)
        if timings > 0:
            print("Sleep for %d seconds" % timings)
            sleep(timings)
