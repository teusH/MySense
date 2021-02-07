#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
#
# Copyright (C) 2020, Behoud de Parel, Teus Hagen, the Netherlands
# Open Source Initiative  https://opensource.org/licenses/RPL-1.5
#
#   Unless explicitly acquired and licensed from Licensor under another
#   license, the contents of this file are subject to the Reciprocal Public
#   License ("RPL") Version 1.5, or subsequent versions as allowed by the RPL,
#   and You may not copy or use this file in either source code or executable
#   form, except in compliance with the terms and conditions of the RPL.
#
#   All software distributed under the RPL is provided strictly on an "AS
#   IS" basis, WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESS OR IMPLIED, AND
#   LICENSOR HEREBY DISCLAIMS ALL SUCH WARRANTIES, INCLUDING WITHOUT
#   LIMITATION, ANY WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
#   PURPOSE, QUIET ENJOYMENT, OR NON-INFRINGEMENT. See the RPL for specific
#   language governing rights and limitations under the RPL.
__license__ = 'RPL-1.5'

# $Id: MyTTNclient.py,v 4.1 2021/02/07 14:37:26 teus Exp teus $

# Broker between TTN and some  data collectors: luftdaten.info map and MySQL DB
# if nodes info is loaded and DB module enabled export nodes info to DB
# the latter will enable to maintain in DB status of kits and kit location/activity/exports

# module mqtt: git clone https://github.com/eclipse/paho.mqtt.python.git
# cd paho.mqtt.python ; python setup.py install
# broker server: Debian: apt-get install mqtt

"""Simple test script for TTN MQTT broker access
    Broker access is designed for multiple brokers data record MQTT downloads.
    MQTT topics may be a list of topics.
    Main routine is GetData() to start and handle data records downloads.
    GetData() returns with the TTN MQTT data record in json/dict format, or
    empty dict for no recort, or None for End of Records/Data.
    Module can be used as library as well CLI

    command line (CLI) arguments:
        verbose=true|false or -v or --verbose. Default False.
        user=TTNuser user account name for TTN.
        password=TTNpassword eg ttn-account-v2.abscdefghijl123456789ABCD.
        keepalive=N Keep A Live in seconds for connection, defaults to 180 secs.
            Dflt: None.
        node will be seen at TTN as topic ID. Multiple (no wild card) is possible.
        node='comma separated nodes' ... to subscribe to. Dflt node='+' (all wild card).
        show=pattern regular expression of device IDs to display the full data record.
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
    def __init__(self, broker, fifo, lock, verbose=False, keepalive=180, logger=None):
        self.TTNconnected = None  # None=ont yet, False from disconnected, True connected
        self.message_nr = 0       # number of messages received
        self.RecordQueue = fifo   # list of received data records
        self.QueueLock = lock     # Threadlock fopr queue handling
        self.TTNclient = None     # TTN connection handle
        self.verbose = verbose    # verbosity
        self.broker = broker      # TTN access details
        if not 'lock' in broker.keys(): # make sure timestamp sema is there
            self.broker['lock'] = threading.RLock()
        self.KeepAlive = keepalive # connect keepalive in seconds, default 60
        self.logger = logger      # routine to print errors
    
    def _logger(self, pri, message):
        try: self.logger('MyTTNclient',pri,message)
        except: sys.stdout.write("MyTTNclient %s: %s.\n" % (pri, message)) 

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            if self.verbose: self._logger("INFO","Connected to broker")
            self.TTNconnected = True                # Signal connection 
            with self.broker['lock']: self.broker['timestamp'] = time.time()
        else:
            self._logger("ERROR","Connect to MQTT broker failed: %s." % [ "successful", "internet connection broke up", "invalid client identifier", "server unavailable", "bad username or password", "not authorised"][rc])
            raise IOError("TTN MQTT connection failed")
    
    def _on_disconnect(self, client, userdata, rc):
        if self.verbose:
            self._logger("ERROR","Disconnect rc=%d from broker %s" % (rc, self.broker))
        self._logger("ERROR","Broker disconnect: rc=%d." % rc)
        time.sleep(0.1)
        self.TTNconnected = False
     
    def _on_message(self, client, userdata, message):
        self.message_nr += 1
        try:
            record = json.loads(message.payload)
            # self._logger("INFO","%s: Message %d received: " % (datetime.datetime.now().strftime("%m-%d %Hh%Mm"),self.message_nr) + record['dev_id'] + ', port=%d' % record['port'] + ', raw payload="%s"' % record['payload_raw'])
            if len(record) > 25: # primitive way to identify incorrect records
              self._logger("WARNING","TTN MQTT records overload. Skipping.")
            elif len(self.RecordQueue) > 100:
              self._logger("WARNING","exhausting record queue. Skip record: %s." % record['dev_id'])
            else:
              with self.QueueLock:
                self.RecordQueue.append(record)
                # in principle next should be guarded by a semaphore
                with self.broker['lock']: self.broker['timestamp']  = time.time()
            return True
        except Exception as e:
            # raise ValueError("Payload record is not in json format. Skipped.")
            self._logger("ERROR","it is not json payload, error: %s" % str(e))
            self._logger("INFO","\t%s skipped message %d received: " % (datetime.datetime.now().strftime("%m-%d %Hh%Mm"),self.message_nr) + 'topic: %s' % message.topic + ', payload: %s' % message.payload)
            return False

    @property
    def TTNConnected(self):
        return self.TTNconnected
     
    def TTNinit(self):
        if self.TTNclient == None:
            # may need this on reinitialise()
            self.TTNclientID = "ThisTTNtestID" if not 'clientID' in self.broker.keys() else self.broker['clientID']
            if self.verbose:
                self._logger("INFO","Initialize TTN MQTT client ID %s" % self.TTNclientID)
            # create new instance, clean session save client init info?
            self.TTNclient = mqttClient.Client(self.TTNclientID, clean_session=True)
            self.TTNclient.username_pw_set(self.broker["user"], password=self.broker["password"])    # set username and password
            self.TTNclient.on_connect = self._on_connect        # attach function to callback
            self.TTNclient.on_message = self._on_message        # attach function to callback
            self.TTNclient.on_disconnect = self._on_disconnect  # attach function to callback
            for cnt in range(3):
                try:
                    # TODO: set_tls setting not yet supported
                    # if 'cert' in self.broker.keys() do set ssl
                    self.TTNclient.connect(self.broker["address"], port=self.broker["port"], keepalive=self.KeepAlive) # connect to broker
                    break
                except Exception as e:
                    self._logger("INFO","%s connection failure." % datetime.datetime.now().strftime("%m-%d %Hh%Mm:"))
                    self._logger("ERROR","Try to (re)connect failed to %s:%s with error: %s" % (self.broker["address"],str(self.broker["topic"]), str(e)))
                    time.sleep(60)
                    if cnt >= 2:
                        self._logger("FATAL","Giving up.")
                        exit(1)
        else:
            try:
                self.broker['count'] += 1
                time.sleep(self.broker['count']*60) # slow down a bit
            except: self.broker['count'] = 1
            self.TTNclient.reinitialise()
            if self.verbose:
                self._logger("INFO","Reinitialize TTN MQTT client")
        return True
    
    def TTNstart(self):
        if self.TTNconnected: return True
        self.TTNconnected = False
        if not self.TTNclient:
            self.TTNinit()
        else: self.TTNclient.reinitialise(client_id=self.TTNclientID)
        cnt = 0
        if self.verbose:
            self._logger("INFO","Starting up TTN MQTT client.")
        self.TTNclient.loop_start()
        time.sleep(0.1)
        while self.TTNconnected != True:    # Wait for connection
            if cnt > 250:
                if self.verbose:
                    self._logger("FAILURE","waited for connection too long.")
                self.TTNstop()
                return False
            if self.verbose:
                if not cnt:
                    self._logger("INFO","Wait for connection")
                elif (cnt%10) == 0:
                    if self.logger == sys.stdout.write:
                        sys.stdout.write("\033[F") #back to previous line 
                        sys.stdout.write("\033[K") #clear line 
                    self._logger("INFO","Wait for connection % 3.ds"% (cnt/10))
            cnt += 1
            time.sleep(0.1)
        qos = 0 # MQTT dflt 0 (max 1 telegram), 1 (1 telegram), or 2 (more)
        try: qos = self.broker['qos']
        except: pass
        self.TTNclient.subscribe(self.broker['topic'], qos=qos)
        if self.verbose:
            self._logger("INFO","TTN MQTT client started")
        return True
    
    def TTNstop(self):
        if not self.TTNclient: return
        if self.verbose: self._logger("ERROR","STOP TTN connection")
        try:
            self.TTNclient.loop_stop()
            self.TTNclient.disconnect()
        except: pass
        self.TTNconnected = False
        self.TTNclient = None  # renew MQTT object class
        time.sleep(60)

def _logger(self, pri, message, logger=None):
    try: logger('MyTTNclient',pri,message)
    except: sys.stdout.write("MyTTNclient %s: %s.\n" % (pri, message)) 

MQTTindx = None
MQTTFiFo = []    # first in, first out data records queue
MQTTLock = threading.RLock() # lock for queue access
# find brokers who need to be (re)started up
def MQTTstartup(MQTTbrokers,verbose=False,keepalive=180,logger=None):
    global MQTTindx, MQTTFiFo, MQTTLock
    brokers = MQTTbrokers
    if not type(brokers) is list: brokers = [brokers] # single broker
    for indx in range(len(brokers)-1,-1,-1):
      broker = brokers[indx]
      if not broker or not type(broker) is dict:
        del brokers[indx]
        continue
      if not 'fd' in broker or broker['fd'] == None: # initialize
        broker['fd'] = None      # class object handle
        broker['restarts'] = 0   # nr of restarts with timing of 60 seconds
        broker['startTime'] = 0  # last time started
        broker['count'] = 0      # number of secs to delay check for data
        broker['timestamp'] = 0  # last time record
        broker['lock'] = threading.RLock() # sema for timestamp
      if not broker['fd']:
        broker['fd'] = TTN_broker(broker, MQTTFiFo, MQTTLock, verbose=verbose, keepalive=keepalive, logger=logger)
      if not broker['fd']:
        _logger("ERROR","Unable to initialize TTN MQTT class for %s" % str(broker),logger=logger)
        del MQTTbrokers[indx]
        continue
      if not broker['fd'] or not broker['fd'].TTNstart():
        _logger("FATAL","Unable to initialize TTN MQTT connection: %s." % str(broker),logger=logger)
        del MQTTbrokers[indx]
      elif not broker['startTime']:
        with broker['lock']:
          broker['timestamp'] = broker['startTime'] = time.time()
      MQTTindx = -1
    if not len(brokers): return False
    return True

# stop a broker or a list of brokers
def MQTTstop(MQTTbrokers):
    brokers = MQTTbrokers
    if not type(brokers) is list: brokers = [brokers]
    for broker in brokers:
      try:
        broker['fd'].TTNstop(); broker['fd'] = None
      except: pass

# default logging routine
def logging(string):
    sys.stdout.write(string + '\n')

# get a record from an MQTT broker eg TTN
#     verbose: verbosity, keepalive: keep connect,
#     logger: fie to lo, sec2pol: wait on record
def GetData(MQTTbrokers, verbose=False,keepalive=180,logger=None, sec2pol=10):
    global MQTTindx, MQTTFiFo, MQTTLock
    timing = time.time()
    while True:
      # find brokers who are disconnected
      if not type(MQTTbrokers) is list: MQTTbrokers = [MQTTbrokers]
      for broker in MQTTbrokers:
        if not broker or len(broker) < 2: continue
        try:
          if not broker['fd'].TTNConnected:
            broker['fd'].MQTTStop()
            broker['fd'] = None
        except:
          if not type(broker) is dict:
            raise ValueError("Undefined broker %s" % str(broker))
          broker['fd'] = None
      if not len(MQTTbrokers) or not MQTTstartup(MQTTbrokers,verbose=verbose,keepalive=keepalive,logger=logger):
        _logger("INFO","no MQTT broker available",logger=logger)
        return None
      if MQTTindx == None: MQTTindx = -1
      now = time.time()

      # try to find a (next) queue with a data record
      if len(MQTTFiFo):
          with MQTTLock: record = MQTTFiFo.pop(0)
          return record

      # no record found, reset dying connections, delete dead connections
      ToBeRestarted = (0,None,-1) # (minimal wait time, broker)
      for nr in range(len(MQTTbrokers)):
        MQTTindx = (MQTTindx+1)%len(MQTTbrokers)
        broker = MQTTbrokers[MQTTindx]

        # CONNECTED broker
        if broker['fd'].TTNConnected:
          # there was no record in the record queue
          if (now - broker['timestamp'] > 20*60) and (now - broker['startTime'] > 45*60):
            _logger("ERROR","Waiting (waiting for %d secs, running %d seconds) too long for data from broker %s. Stop connection." % (now - broker['timestamp'], now - broker['startTime'], str(broker)),logger=logger)
            broker['fd'].TTNstop()
            del MQTTbrokers[MQTTindx]
            # break  # break to while True loop
          if not broker['timestamp']: 
            with broker['lock']: broker['timestamp'] = now

        # DISCONNECTED broker
        elif broker['restarts'] <= 3: # try simple restart
            _logger("ERROR"," %s: Connection died. Try again." % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),logger=logger)
            broker['fd'].TTNstop()
            if now-broker['startTime'] > 15*60: # had run for minimal 5 minutes
              broker['restarts'] = 0
              broker['fd'] = None
              with broker['lock']: broker['timestamp'] = now
              # break # break to while True loop
            else:
              broker['restarts'] += 1  # try again and delay on failure
              with broker['lock']: broker['timestamp'] = now
        else:
            _logger("ERROR"," %s: Too many restries on broker %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S",str(broker))),logger=logger)
            broker['fd'].TTNstop()
            broker['fd'] = None
            broker = {}

        if not ToBeRestarted[1]:
          ToBeRestarted = (broker['timestamp'],broker,MQTTindx)
        elif broker['timestamp'] < ToBeRestarted[0]:
          ToBeRestarted = (broker['timestamp'],broker,MQTTindx)
      
      if ToBeRestarted[1]:
        #if verbose:
        #  LF = ''
        #  if int(time.time()-timing) and logger == sys.stdout.write:
        #    LF = "\033[F\033[K" #back to previous line and clear line 
        #  _logger("INFO","%sWaiting %3d+%3d secs." % (LF,time.time()-timing,max(ToBeRestarted[1]['timestamp'] - now,sec2pol)), logger=logger)
        time.sleep(max(ToBeRestarted[1]['timestamp'] - now,sec2pol))
        MQTTindx = ToBeRestarted[2]-1
      else:
        #if verbose:
        #  LF = ''
        #  if int(time.time()-timing) and logger == sys.stdout.write:
        #    LF = "\033[F\033[K" #back to previous line and clear line 
        #  _logger("INFO","%sAwaiting %3d+%3d secs." % (LF,time.time()-timing,sec2pol),logger=logger)
        time.sleep(sec2pol)
      # and try again in the while True loop
    return None

if __name__ == '__main__':
    # show full received TTN MQTT record foir this pattern
    show = None         # show details of data record for nodeID pattern
    node = '+'          # TTN MQTT devID pattern for subscription device topic part
    # user = "1234567890abc"       # connection user name
    user = "201802215971az"        # Connection username
    verbose = False
    logger = None       # routine to print messages to console
    # Connection password
    # password = "ttn-account-v2.ACACADABRAacacadabraACACADABRAacacadabra"
    password = "ttn-account-v2.GW3msa6kBNZs0jx4aXYCcbPaK6r0q9iSfZjIOB2Ixts"
    keepalive = 180     # play with keepalive connection settings, dflt 180 secs
    
    for arg in sys.argv[1:]: # change defualt settings arg: <type>=<value>
        if arg  in ['-v','--verbode']:
            verbose = True; continue
        Match = re.match(r'(?P<key>verbose|show|node|user|password|keepalive)=(?P<value>.*)', arg, re.IGNORECASE)
        if Match:
            Match = Match.groupdict()
            if Match['key'].lower() == 'verbose':
                if Match['value'].lower() == 'false': verbose = False
                elif Match['value'].lower() == 'true': verbose = True
            elif Match['key'].lower() == 'show': # pattern show details record
                show = re.compile(Match['value'], re.I)
            elif Match['key'].lower() == 'node': # comma separated list of devID's
                if node == '+': node = Match['value']
                else: node += ',' + Match['value']
            elif Match['key'].lower() == 'user':
                user = Match['value']
            elif Match['key'].lower() == 'password':
                password = Match['value']
            elif Match['key'].lower() == 'keepalive':
                if Match['value'].isdigit(): keepalive = int(Match['value'])
    
    # TTN MQTT broker access details
    topics = []
    for topic in node.split(','): # list of appID/devices/devID
        topics.append(("+/devices/" + topic + "/up",0))
    TTNbroker = {
        "address": "eu.thethings.network",  # Broker address
        "port":  1883,                      # Broker port
        "user":  user,                      # Connection username
                                            # Connection password
        "password": password,
        "topic": (topics[0][0] if len(topics) == 1 else topics), # topic to subscribe to
    }
    MQTTbrokers = [ TTNbroker, ] # may be a list of TTN/user brokers

    while True:
      try:
        timing = time.time()
        DataRecord = GetData(MQTTbrokers,verbose=verbose,keepalive=keepalive,logger=None) 
        if DataRecord:
          print("%s:%s received data record: %s" % (datetime.datetime.now().strftime("%m-%d %Hh%Mm%Ss"), " delay %3d secs," % (time.time()-timing if verbose else ''),str(DataRecord['dev_id'])))
          if show and show.match(DataRecord['dev_id']):
            print("%s" % str(DataRecord))
        elif record == None: break
        else:
          print("No data record received. Try again.")
      except Exception as e:
        print("End of get data record with exception: %s" % str(e))
        break

    MQTTstop(MQTTbrokers)
    exit(0)
