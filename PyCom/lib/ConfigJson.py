# Copyright 2019, Teus Hagen, RPL-1.5
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

# search for I2C devices and get supporting libraries loaded
__version__ = "0." + "$Revision: 7.1 $"[11:-2]
__license__ = 'RPL-1.5'

import ujson

class MyConfig:
  def __init__(self, file='MySenseConfig.json', archive=True, debug=False):
    # dict self.config = { 'ttl': { 'dust': {}, 'gps': {} }, 'var': value, ... }
    self.file = '/flash/' + file
    self.dirty = None
    self.version = __version__[:3]
    self.config = {}
    self.items = ['name','address','pins','use','baud'] # keys to collect
    self.debug = debug
    self.stored = 0 # count as safeguard
    self.doArchive = archive
    self.check = None
    return None

  # checksum of string
  def checksum(self,msg):
    v = 21
    for c in msg: v ^= ord(c)
    return v

  # import json config file
  def getConfig(self,atype=None, abus=None):
    if self.dirty == None: # try to roll in
      self.config = { 'Version': self.version }
      self.dirty = False
      try:
        with open(self.file, 'r') as config_file:
          self.config = ujson.loads(config_file.read())
        if self.debug: print("config read: ", self.config)
        if self.config['Version'] != self.version:
          raise ValueError("version %s" % self.config['Version'])
      except OSError:
        if self.debug: print("No archived config: %s" % self.file)
        return {}
      except Exception as e:
        print("Json config error: %s." % e)
        #with open(self.file, 'r') as config_file:
        #  print("File content error: ", config_file.read())
        if not self.debug:
          self.remove
          print("File %s deleted." % self.file)
        else: print("Json file: %s." % self.file)
        return {}
      if self.debug: print("Found config file: %s" % self.file, self.config)
    if (abus == None) and (atype == None): return self.config
    try:
      if abus != None:
        if atype != None: value = self.config[abus][atype]
        else: value = self.config[abus]
      else: value = self.config[atype]
      #if type(value) is dict: return value.copy()
      # tuples are imported as list!
      #elif (type(value) is list) or (type(value) is tuple): return value[:]
      return value
    except: return None

  # copy value to config collection
  def dump(self, atype, avalue, abus=None):
    if self.debug: print("dump %s: %s" % (atype,str(avalue)))
    if self.dirty == None: self.getConfig()
    # make a copy
    if type(avalue) is dict:
       value = avalue.copy()
       if 'updated' in value.keys():
         if value['updated']: self.dirty = True
         del value['updated']
       #for item in value.keys(): # need better check
       #  if not item in self.items: del value[item]
    elif (type(avalue) is list) or (type(avalue) is tuple):
       value = avalue[:]
    else: value = avalue
    if abus != None:
      if self.debug:
        print("dump(%s,%s,%s): type: " % (str(atype),str(avalue),str(abus)), type(self.config),"\ncontent:\n",self.config)
      if not abus in self.config.keys(): self.config[abus] = {'updated': True}
      self.config[abus][atype] = value # is probably dict
      if ('updated' in self.config[abus].keys()):
          if self.config[abus]['updated']: self.dirty = True
          del self.config[abus]['updated']
    else:
      try:
        if atype != None:
          if value != None: self.config[atype] = value       # is probably not dict
          else: del self.config[atype]
        else: self.config = {'Version': self.version}
      except: pass
      self.dirty = True # maybe still not changed
    return self.dirty

  def DiffDict(self, a, b):
    eq = (a == b)
    if not self.debug: return eq
    if eq: return eq
    if (not type(a) is dict) or (not type(b) is dict):
      return eq
    for item in list(set(a).intersection(set(b))):
        if self.debug and a[item] != b[item]:
          print("item %s value a(%s) != b(%s)", (item,str(a[item]),str(b[item])) )
          print("keys a-b: ",set(a).difference(set(b))," keys b-a: ", set(b).difference(set(a)))
    return eq

  # delete clean json content
  def JsonCleanup(self, adict):
    for item,val in adict.items():
        if type(val) is dict:
            self.JsonCleanup(val)
            continue
        elif type(val) is list or \
            type(val) is tuple or \
            type(val) is bool or \
            type(val) is str or \
            type(val) is float or \
            type(val) is int or \
            val is None:
              continue
        del adict[item]

  # dump to json config file in flash mem
  def export(self,force=False):
    for bus in ['i2c','ttl']:
       if not bus in self.config: continue
       if 'update' in self.config[bus]:
         if self.config[bus]['update']: self.dirty = True
         del self.config[bus]['update']
    if not 'Version' in self.config.keys():
      self.config['Version'] = self.version
    if not force  and not self.dirty: return False
    # add explicit flg if present in dust
    if not 'explicit' in self.config.keys():
      try: self.config['explicit'] = self.config['ttl']['dust']['explicit']
      except: pass
    self.dirty = False
    if not self.check and self.DiffDict(self.config,self.check):
      if self.debug: print("MyConfig is not dirty")
      return False
    if self.stored > 5: # safeguard
      print("Too many writes on %s" % self.file)
      return False
    self.stored += 1
    self.check = self.config.copy()
    self.JsonCleanup(self.check)
    try:
      with open(self.file,'w') as config_file:
        c = config_file.write(ujson.dumps(self.check))
      if self.debug: print("Updated %s with config:\n\t" % self.file,self.check)
      else: print("Flashed %d bytes to config file %s." % (c,self.file))
    except Exception as e:
      print("Json flash file dump failed: %s" % e)
      return False
    return True

  @property
  def store(self):
    if self.doArchive: return self.export(force=False)

  @property
  def archive(self): return self.export(force=True)

  @property
  def updated(self): return self.dirty

  @property
  def remove(self):
    import os
    try: return os.remove(self.file)
    except: return False

  @property
  def clear(self):
    self.remove; self.dirty = None; self.config = {}

  @property
  def MyConfig(self):
    return self.getConfig()
