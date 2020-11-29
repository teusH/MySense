#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
#
# Copyright (C) 2020, Behoud de Parel, Teus Hagen, the Netherlands
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

# $Id: mqtt_test.py,v 1.3 2020/11/27 14:05:54 teus Exp teus $

# Broker between TTN and some  data collectors: luftdaten.info map and MySQL DB
# if nodes info is loaded and DB module enabled export nodes info to DB
# the latter will enable to maintain in DB status of kits and kit location/activity/exports

# module mqtt: git clone https://github.com/eclipse/paho.mqtt.python.git
# cd paho.mqtt.python ; python setup.py install
# broker server: Debian: apt-get install mqtt

"""Simple test script for TTN MQTT broker access
    Module can be used as library as well CLI
    command line (CLI) arguments:
        verbose=true|false or -v or --verbose. Default False
        user=TTNuser user account name for TTN
        password=TTNpassword eg ttn-account-v2.abscdefghijl123456789ABCD
        node will be seen at TTN as topic ID. Multiple (no wild card) is possible
        node='comma separated nodes' ... to subscribe to. Dflt node='+' (all wild card).
        show=pattern regular expression of device IDs to display the full data record.
            Dflt: None
"""

import paho.mqtt.client as mqttClient
import threading
import time, datetime
import re
import sys
import json

# routines to collect messages from TTN MQTT broker (yet only subscription)
# collect records in RecordQueue[] using QueueLock
# broker with TTN connection details: host, user credentials, list of topics
# broker = {
#        "address": "eu.thethings.network",  # Broker address default
#        "port":  1883,                      # Broker port default
#        "user":  "20201126grub",            # Connection username
#                                            # Connection password
#        "password": ttn-account-v2.GW36kBmsaNZaXYCs0jx4cbPiSfaK6r0q9Zj0jx4Bmsts"
#        "topic": "+" , # topic or list of topics to subscribe to
#    }
class TTN_broker:
    def __init__(self, broker, verbose=False, keepalive=60):
        self.Connected = None  # None=ont yet, False from disconnected, True connected
        self.message_nr = 0    # number of messages received
        self.RecordQueue = []  # list of received data records
        self.QueueLock = threading.RLock() # Threadlock fopr queue handling
        self.TTNclient = None  # TTN connection handle
        self.verbose = verbose # verbosity
        self.broker = broker   # TTN access details
        self.KeepAlive = keepalive # connect keepalive in seconds, default 60
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            if self.verbose: print("Connected to broker")
            self.Connected = True                # Signal connection 
        else:
            print("ERROR: Connection failed")
            raise IOError("TTN MQTT connection failed")
    
    def on_disconnect(self, client, userdata, rc):
        if self.verbose: print("TTN disconnect rc=%d." % rc)
        if not rc:
            print("Disconnect from client site.")
        else:
            print("ERROR: disconnect from broker: %s" % str(client) )
        if self.Connected != None:
            self.TTNclient.disconnect()
            self.TTNclient.loop_stop()
            time.sleep(0.1)
            print("Will try to restart TTN MQTT connection")
        self.Connected = False
     
    def on_message(self, client, userdata, message):
        self.message_nr += 1
        try:
            record = json.loads(message.payload)
            # print("%s: Message %d received: " % (datetime.datetime.now().strftime("%m-%d %Hh%Mm"),self.message_nr) + record['dev_id'] + ', port=%d' % record['port'] + ', raw payload="%s"' % record['payload_raw'])
            if len(record) > 25:
                print("WARNING: TTN MQTT records overload. Skipping.")
            else:
                with self.QueueLock: self.RecordQueue.append(record)
            return True
        except Exception as e:
            # raise ValueError("Payload record is not in json format. Skipped.")
            print("ERROR: it is not json payload, error: %s" % str(e))
            print("\t%s skipped message %d received: " % (datetime.datetime.now().strftime("%m-%d %Hh%Mm"),self.message_nr) + 'topic: %s' % message.topic + ', payload: %s' % message.payload)
            return False

    @property
    def TTNConnected(self):
        return self.Connected
     
    def TTNinit(self):
        if self.TTNclient == None:
            if self.verbose: print("Initialize TTN MQTT client", end='', flush=True)
            self.TTNclient = mqttClient.Client("PythonTestTTN")        # create new instance
            self.TTNclient.username_pw_set(broker["user"], password=broker["password"])    # set username and password
            self.TTNclient.on_connect = self.on_connect        # attach function to callback
            self.TTNclient.on_message = self.on_message        # attach function to callback
            self.TTNclient.on_disconnect = self.on_disconnect  # attach function to callback
            for cnt in range(3):
                try:
                    self.TTNclient.connect(broker["address"], port=broker["port"], keepalive=self.KeepAlive) # connect to broker
                    break
                except Exception as e:
                    print("\n%s ERROR Try to connect failed to %s with error: %s" % (datetime.datetime.now().strftime("%m-%d %Hh%Mm:"),broker["address"], str(e)))
                    if cnt >= 2:
                        print("FATAL Giving up.")
                        exit(1)
        else:
            self.TTNclient.reinitialise()
            if self.verbose: print("Reinitialize TTN MQTT client", end='', flush=True)
            # self.TTNclient.on_connect = on_connect        # attach function to callback
            # self.TTNclient.on_message = on_message        # attach function to callback
            # self.TTNclient.on_disconnect = on_disconnect  # attach function to callback
        if self.verbose: print(".")
        return True
    
    def TTNstart(self):
        self.Connected = False
        if not self.TTNclient:
            self.TTNinit()
        cnt = 0
        if self.verbose: print("Starting up TTN MQTT client.")
        self.TTNclient.loop_start()
        time.sleep(0.1)
        while self.Connected != True:    # Wait for connection
            if cnt > 250:
                if self.verbose: print("FAILURE: waited for connection too long.")
                return False
            if self.verbose:
                if not cnt:
                    print("Wait for connection")
                elif (cnt%10) == 0:
                    sys.stdout.write("\033[F") #back to previous line 
                    sys.stdout.write("\033[K") #clear line 
                    print("Wait for connection % 3.ds"% (cnt/10))
            cnt += 1
            time.sleep(0.1)
        if self.verbose: print("TTN MQTT client connected.")
        self.TTNclient.subscribe(broker['topic'])
        return True
    
    def TTNstop(self):
        if not self.TTNclient: return
        if self.verbose: print("EXITING")
        self.TTNclient.disconnect()
        self.TTNclient.loop_stop()

if __name__ == '__main__':
    # show full received TTN MQTT record foir this pattern
    show = None
    node = '+'          # TTN MQTT pattern for subscription device topic part
    user = "2020"          # Connection username
    verbose = False
    # Connection password
    password = "ttn-account-v2.GW36kBmsaACACADBRA4msa0q9iSB2Ixts"
    keepalive = 60      # to play with keepalive connection settings
    
    for arg in sys.argv[1:]:
        if arg  in ['-v','--verbode']:
            verbose = True; continue
        Match = re.match(r'(?P<key>verbose|show|node|user|password|keepalive)=(?P<value>.*)', arg, re.IGNORECASE)
        if Match:
            Match = Match.groupdict()
            if Match['key'].lower() == 'verbose':
                if Match['value'].lower() == 'false': verbose = False
                elif Match['value'].lower() == 'true': verbose = True
            elif Match['key'].lower() == 'show': show = re.compile(Match['value'], re.I)
            elif Match['key'].lower() == 'node':
                if node == '+': node = Match['value']
                else: node += ',' + Match['value']
            elif Match['key'].lower() == 'user': user = Match['value']
            elif Match['key'].lower() == 'password': password = Match['value']
            elif Match['key'].lower() == 'keepalive':
                if Match['value'].isdigit(): keepalive = int(Match['value'])
    
    # TTN MQTT broker access details
    topics = []
    for topic in node.split(','):
        topics.append(("+/devices/" + topic + "/up",0))
    broker = {
        "address": "eu.thethings.network",  # Broker address
        "port":  1883,                      # Broker port
        "user":  user,                      # Connection username
                                            # Connection password
        "password": password,
        "topic": (topics[0][0] if len(topics) == 1 else topics), # topic to subscribe to
    }
    TTN = TTN_broker(broker, verbose=verbose, keepalive=keepalive)
    
    if not TTN or not TTN.TTNstart():
        print("Unable to initialize TTN MQTT connection.")
        exit(1)
    polling = 1  # number of secs to delay check for data
    waiting = 0  # number of seconds to wait for data record
    startTime = time.time() # last time started
    restarts = 1 # number of restarts with restart timeing of 60 seconds
    try:
        while True:
            if TTN.TTNConnected:
                if len(TTN.RecordQueue):
                    with TTN.QueueLock: record = TTN.RecordQueue.pop(0)
                    if waiting:
                        sys.stdout.write("\033[F") #back to previous line
                        sys.stdout.write("\033[K") #clear line
                    print("%s: received data record: %s" % (datetime.datetime.now().strftime("%m-%d %Hh%Mm%Ss"),str(record['dev_id'])))
                    if show and show.match(record['dev_id']):
                        print("%s" % str(record))
                    waiting = 0
                    time.sleep(polling)
                elif waiting > 45*60:  # giving up
                    sys.stderr.write("FATAL: waiting for data record took to long. Dead MQTT server?\n")
                    break
                else:
                    if verbose:
                      if not waiting:
                        print("Wait for record to arrive")
                      else:
                        sys.stdout.write("\033[F") #back to previous line 
                        sys.stdout.write("\033[K") #clear line 
                        print("Wait for record to arrive % 3.ds"%waiting)
                    waiting += polling
                    time.sleep(polling)
                continue
            if restarts <= 10:
                sys.stderr.write("ERROR: %s: Connection died. Try again.\n" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                time.sleep(restarts*60)
                if TTN.TTNstart(): # do a reconnect
                    restarts = 1
                    startTime = time.time()
                    continue
                else: restarts += 1  # try again and delay on failure
            else:
                sys.stderr.write("ERROR: %s: Connection died. Try again.\n" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                sys.stderr.write("FATAL: Unable to reconnect. Dead network?\n")
                break
    except Exception as e:
        sys.stderr.write("EXITING on exception: %s\n" % str(e))
if TTN: TTN.TTNstop()
exit(0)
