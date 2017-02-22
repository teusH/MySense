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

# $Id: MyMQTTPUB.py,v 1.3 2017/02/01 12:47:13 teus Exp teus $

# module mqtt: git clone https://github.com/eclipse/paho.mqtt.python.git
# cd paho.mqtt.python ; python setup.py install
# broker server: Debian: apt-get install mqtt

# TO DO: write to file or cache

""" Publish measurements as client to a Mosquitto broker
    Subscribe to measurements from a Mosquitto Broker server
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyMQTTPUB.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.3 $"[11:-2]

try:
    import MyLogger
    import sys
    import json
    import socket
    from time import time, sleep
    socket.setdefaulttimeout(30)
    import paho.mqtt.client as mqtt
except ImportError as e:
    MyLogger.log("FATAL","One of the import modules not found: %s" % e)

# configurable options
__options__ = ['output','hostname','user','password','apikey','prefix','topic','cert','ttl']

Conf = {
    'output': False,     # output to MQTT broker is required
    'host': 'localhost', # server host number for mqtt broker
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
            MyLogger.log('DEBUG',"Connected to MQTT publishing broker")
            pass
    
    def on_publish(client, obj, MiD):
        global waiting, mid
        waiting = False
        mid = MiD
        MyLogger.log('DEBUG',"MQTT publish mid: " + str(mid))
    
    def on_log(client, obj, level, string):
        MyLogger.log('DEBUG',"MQTT publishing Broker: %s" % string)

    def on_disconnect(client, obj, MiD):
        global waiting, mid
        waiting = False
        mid = MiD
        MyLogger.log('DEBUG',"MQTT publishing On disconnect mid: " + str(mid) )

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

        mqttc.connect(Conf['host'], Conf['port'])
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
        MyLogger.log('ERROR',"IoS MQTT publishing Failure type: %s; value: %s. MQTT broker aborted." % (sys.exc_info()[0],sys.exc_info()[1]) )
        Conf['output'] = False
        raise IOError("MQTT communication failure, message id: %s" % str(mid))
        return False
    if waiting:
        MyLogger.log('ATTENT',"Sending telegram to MQTT broker")
        raise IOError("MQTT publishing timeout, message id: %s" % str(mid))
        return False
    MyLogger.log('DEBUG',"Sent telegram to MQTT broker, waiting = %s, message id: %s" % (str(waiting),str(mid)) )
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
            MyLogger.log('FATAL',"Broker publish call missing argument %s." % key)
    if (not args['internet']['module'].internet(args['ident'])):
        Conf['output'] = False
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
    data = json.dumps({ 'id': request, 'data': data })
    topic = '%s/%s/%s' % (Conf['topic'],request['project'],request['serial'])
    try:
        PubOrSub(topic, data)
    except IOError as e:
        MyLogger.log('ERROR',"Sending registration to MQTT broker %s: error: %s" % (Conf['host'],e))
        return False
    return True

ErrorCnt = 0
def publish(**args):
    global Conf, ErrorCnt
    if (not Conf['output']) or (ErrorCnt > 20):
        return False
    for key in ['ident','data','internet']:
        if not key in args.keys():
            MyLogger.log('FATAL',"Broker publish call missing argument %s." % key)
    if not args['internet']['module'].internet(args['ident']):
        Conf['output'] = False # to do: add recovery time out
        MyLogger.log('ERROR',"No internet access. Abort MQTT broker output.")
        return False
    for key in ['apikey']:      # force to ident
        if (key in Conf.keys()) and (Conf[key] != None) and len(Conf[key]):
            args['data'][key] = Conf[key]

    # obtain session registration via broker (to do: needs some work)
    if not registrate(args):
        ErrorCnt += 1
        return False
    ErrorCnt = 0
    return True
