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

# $Id: MyMQTTSUB.py,v 2.8 2018/05/27 19:53:57 teus Exp teus $

# module mqtt: git clone https://github.com/eclipse/paho.mqtt.python.git
# cd paho.mqtt.python ; python setup.py install
# broker server: Debian: apt-get install mqtt

# TO DO: write to file or cache

""" Publish measurements as client to a Mosquitto broker
    Subscribe to measurements from a Mosquitto Broker server
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyMQTTSUB.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.8 $"[11:-2]

try:
    import MyLogger
    import sys, os
    import json
    import socket
    import re
    from time import time, sleep
    socket.setdefaulttimeout(60)
    import paho.mqtt.client as mqtt
except ImportError as e:
    MyLogger.log(modulename,"FATAL","One of the import modules not found: %s" % e)

# configurable options
__options__ = ['input','hostname','user','password','prefix','cert','ttl','projects','serials','apikey','topic']

Conf = {
    'input': False,      # output to MQTT broker is required
    'hostname': 'localhost', # server host number for mqtt broker
    'port': 1883,        # default MQTT port
    'user': None,        # user/password
    'password': None,    # credentials to access broker
    'qos' : 0,           # dflt 0 (max 1 telegram), 1 (1 telegram), or 2 (more)
    'cert' : None,       # X.509 encryption
    'topic': 'IoS',      # main topic
    'prefix': 'IoS_',    # Internet of Sense base of topic
    'apikey': 'MQTT' + str(os.getpid()), # get unique client id
    'projects': '.*',    # regular expression to accpet projects to subscribe to
    'serials': '.*',     # regular expression to accept serial numbers
    'timeout' : 2*60*60, # timeout for this broker
    'omit': None,        # regular expression omit to receive these items
#    'fd': None,         # have a mqtt connection
#    'file': None,       # Debugging: write to file
}

waiting = False          # waiting for telegram
mid = None               # for logging: message ID
telegrams = []           # telegram buffer, max length is 100     
ErrorCnt = 0             # connectivit error count, slows down, >20 reconnect, >40 abort
PingTimeout = 0          # last time ping request was sent
# =======================================================
# post json data to a MQTT broker for nodes somewhere internet land
# =======================================================
# use telegram style

# Define event callbacks
def PubOrSub(topic,option):
    global Conf, waiting, mid, telegrams, PingTimeout, ErrorCnt
    waiting = False
    mid = None
    telegram = None
    def on_connect(client, obj, rc):
        global waiting
        if rc != 0:
            MyLogger.log(modulename,'ERROR',"Connection error nr: %s" % str(rc))
            Conf['input'] = False
            waiting = False
            if 'fd' in Conf.keys():
                Conf['fd'] = None
            raise IOError("MQTTsub connect failure.")
        else:
            MyLogger.log(modulename,'DEBUG',"Connected.")
            pass
    
    def on_message(client, obj, msg):
        global waiting, telegrams
        waiting = False
        #MyLogger.log(modulename,'DEBUG','MQTTsub msg: topic: ' + msg.topic + ", qos: " + str(msg.qos) + ", msg: " + str(msg.payload))
        try:
            if len(telegrams) > 100:    # 100 * 250 bytes
                MyLogger.log(modulename,'ERROR',"Input buffer is full.")
                return
            telegrams.append( {
                'topic': msg.topic,
                'payload': str(msg.payload),
                })
        except:
            MyLogger.log(modulename,'DEBUG','In message.')
    
    def on_subscribe(client, obj, MiD, granted_qos):
        global waiting, mid
        mid = MiD
        MyLogger.log(modulename,'DEBUG',"mid: " + str(mid) + ",qos:" + str(granted_qos))
    
    def on_log(client, obj, level, string):
        global PingTimeout, Conf, ErrorCnt
        # MyLogger.log(modulename,'DEBUG',"log: %s" % string)
        if string.find('PINGREQ') >= 0:
            if not PingTimeout:
                PingTimeout = int(time())
                #MyLogger.log(modulename,'DEBUG',"log: ping")
            elif int(time())-PingTimeout > 10*60: # should receive pong in 10 minutes
                MyLogger.log(modulename,'ATTENT',"Ping/pong timeout exceeded.")
                if ('fd' in Conf.keys()) and (Conf['fd'] != None):
                    Conf['fd'].disconnect()
                    waiting = False
                    Conf['registrated'] = False
                    del Conf['fd']
                    ErrorCnt += 1
                    PingTimeout = 0
        elif string.find('PINGRESP') >= 0:
            if int(time())-PingTimeout != 0:
                MyLogger.log(modulename,'DEBUG',"Log: ping/pong time: %d secs" % (int(time())-PingTimeout))
            PingTimeout = 0
        else:
            MyLogger.log(modulename,'DEBUG',"Log: %s..." % string[:17])

    def on_disconnect(client, obj, MiD):
        global waiting, mid, Conf
        waiting = False
        if 'fd' in Conf.keys():
            Conf['fd'] = None
        mid = MiD
        MyLogger.log(modulename,'DEBUG',"Disconnect mid: " + str(mid) )
        raise IOError("MQTTsub: disconnected")

    try:
        if (not 'fd' in Conf.keys()) or (Conf['fd'] == None):
            Conf['fd']  = mqtt.Client(Conf['prefix']+Conf['apikey'])
            Conf['fd'].on_connect = on_connect
            Conf['fd'].on_disconnect = on_disconnect
            try:
                ['NOTSET','DEBUG'].index(MyLogger.Conf['level'])
                Conf['fd'].on_log = on_log
            except: pass
            if ('user' in Conf.keys()) and Conf['user'] and ('password' in Conf.keys()) and Conf['password']:
                Conf['fd'].username_pw_set(username=Conf['user'],password=Conf['password'])
            #Conf['fd'].connect(Conf['hostname'], port=Conf['port'], keepalive=60)
            Conf['fd'].connect(Conf['hostname'], Conf['port'])
            Conf['fd'].on_subscribe = on_subscribe
            Conf['fd'].on_message = on_message
            Conf['fd'].loop_start()
            Conf['fd'].subscribe(topic, qos=Conf['qos'])

        timeout = time() + Conf['timeout']
        waiting = True
        while waiting:
            if time() > timeout:
                break
            if len(telegrams):
                waiting = False
                break
            sleep(1)       # maybe it should depend on timeout
        # Conf['fd'].disconnect()
        #Conf['fd'].loop_stop()
    except:
        MyLogger.log(modulename,'ERROR',"Failure type: %s; value: %s. MQTT broker aborted." % (sys.exc_info()[0],sys.exc_info()[1]) )
        Conf['output'] = False
        del Conf['fd']
        raise IOError("%s" % str(mid))
        return telegram
    if waiting:
        MyLogger.log(modulename,'ATTENT',"Sending telegram to broker")
        raise IOError("%s" % str(mid))
        return telegram
    MyLogger.log(modulename,'DEBUG',"Received telegram from broker, waiting = %s, message id: %s" % (str(waiting),str(mid)) )
    if len(telegrams):
        return telegrams.pop(0)
    return telegram

# mqttc = mosquitto.Mosquitto()
# # Assign event callbacks
# mqttc.on_message = on_message
# mqttc.on_connect = on_connect
# mqttc.on_publish = on_publish
# mqttc.on_subscribe = on_subscribe
# 
# Uncomment to enable debug messages
#mqttc.on_log = on_log

def getdata():
    global Conf, ErrorCnt
    if (not Conf['input']):
        sleep(10)
        return {}
    if ErrorCnt:
        if ErrorCnt > 20:
            Conf['registrated'] = None
            if ('fd' in Conf.keys()) and (Conf['fd'] != None):
                try:
                    Conf['fd'].disconnect()
                    Conf['fd'] = None
                except:
                    pass
            sleep((ErrorCnt-20)*60)
        else:
            sleep(ErrorCnt)
    
    if (not 'registrated' in Conf.keys()) or (Conf['registrated'] == None):
        if 'registrated' in Conf.keys():
            MyLogger.log(modulename,'ATTENT',"Try to reconnect to broker.")
        if (not 'projects' in Conf.keys()) or (not len(Conf['projects'])):
            Conf['projects'] = ['ALL']
        if (not 'topic' in Conf.keys()) or (Conf['topic'] == None):
            Conf['topic'] = 'IoS'
        for key in ['user','password','hostname']:
            if (not key in Conf.keys()) or (Conf[key] == None):
                Conf['input'] = False
                MyLogger.log(modulename,'FATAL',"Missing login %s credentials." % key)
        try:
            Conf['projects'] = re.compile(Conf['projects'], re.I)
            Conf['serials'] = re.compile(Conf['serials'], re.I)
        except:
            MyLogger.log(modulename,'FATAL','Regular expression for project or serial.')
        Conf['registrated'] = True

    try:
        msg = PubOrSub(Conf['topic']+"/#", None)
        if msg == None:
            ErrorCnt += 1
            return {}
        ErrorCnt = 0
        msg['topic'] = msg['topic'].split('/')
        msg['payload'] = json.loads(msg['payload'])
    except IOError as e:
        if ErrorCnt > 40:
            MyLogger.log(modulename,'FATAL',"Subscription failed Mid: %s. Aborted." % e)
        ErrorCnt += 1
        MyLogger.log(modulename,'WARNING',"Subscription is failing Mid: %s. Slowing down." % e)
    if (len(msg['topic']) < 3) or (msg['topic'][0] != Conf['topic']) or (not type(msg['payload']) is dict) or (not 'id' in msg['payload'].keys()):
        sleep(0.1)
        return getdata()
    msg['project'] = msg['topic'][1]
    msg['serial'] = msg['topic'][2]
    # check the pay load
    if not type(msg['payload']) is dict:
        sleep(0.1)
        return getdata()
    if not 'id' in msg['payload'].keys():
        msg['id'] = { 'project': msg['project'], 'serial': msg['serial']}
    else:
        msg['id'] = msg['payload']['id']
    if not 'data' in msg['payload'].keys():
        msg['payload']['data'] = None
    # validate identification
    # TO DO: check serial to api key (mqtt broker checks user with project/serial)
    for key in ['project','serial']:
        if (not Conf[key+'s'].match(msg[key])) or (not key in msg['payload']['id'].keys()) or (msg[key] != msg['payload']['id'][key]):
            MyLogger.log(modulename,'WARNING',"Not a proper telegram. Skipped.")
            sleep(0.1)
            return getdata()
    return { 'register': msg['id'], 'data': msg['payload']['data'] }

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['input'] = True
    Conf['hostname'] = 'lunar'
    Conf['user'] = 'ios'
    Conf['password'] = 'acacadabra'
    # Conf['cert'] = None       # X.509 encryption
    Conf['topic'] = 'IoS'      # main topic
    Conf['prefix'] = 'IoS_'    # Internet of Sense base of topic
    Conf['apikey'] = 'MQTT' + str(os.getpid()) # get unique client id
    Conf['projects'] = '.*'    # regular expr to accept projects to subscribe to
    Conf['serials'] = '.*'     # regular expression to accept serial numbers

    Conf['debug'] = True
    for cnt in range(0,25):
        timing = time()
        try:
            data = getdata()
        except Exception as e:
            print("input sensor error was raised as %s" % e)
            break
        print("Getdata returned:")
        print(data)
        timing = 2 - (time()-timing)
        if timing > 0:
            sleep(timing)
