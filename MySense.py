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

# $Id: MySense.py,v 2.19 2017/03/13 19:38:49 teus Exp teus $

# TO DO: encrypt communication if not secured by TLS
#       and received a session token for this data session e.g. via a broker
#       Change the sensor read architecture to a row of functions per sensor type
#       and import them if needed
#       Backup data on temporaly gap in connection
#       Gspread: one Sensors sheet with rows of sensors, per sensor worksheet
#       Add a data aggregation interval window with for every output stream a subwindow.

# Reminder: adhere CIO P 2180.1 GSA rules of handling PII

# start this process where also the modules/plugins reside

# code is based on code from (https://github.com):
# MIT Clairity CEE Senior Capstone Project report V1 dd 15-05-14
# Waag Society Amsterdam Smart Citizens Lab Urban AirQ
# Citi-Sense
# opensensors.io
# Smart-Citizen-Kit
# smartemssion
# polluxnzcity
# AirCastingAndroidClient
# smart-city-air-challenge (USA GOV)
""" Log data from sensors,
    e.g. Dylos, Alphasense Data, rel. huminity and temperature
    to local file in CSV format, and
    remotely: database and/or Google gspread spreadsheet format.
        On start register sensor with info to remote site.
        Broker: 2 json data files: register info data and json measurents
    Sensor info: type sensor, pollutant id, measurement unit
    Configuration: Conf global dict. Optionally: .conf file
    To do: On internet disconnect DB data will be saved localy till
        connection is established again.
"""
progname='$RCSfile: MySense.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.19 $"[11:-2]
__license__ = 'GPLV4'
# try to import only those modules which are needed for a configuration
try:
    import sys
    import os
    # sys.path.append("/home/pi/quick2wire-python-api/")
    #import quick2wire.i2c as i2c
    import re
    from time import time, sleep
    import subprocess
    import datetime
    from threading import Thread
    from datetime import date
    import argparse
    import MyLogger
    try:
        import ConfigParser
    except ImportError as e:
        try:
            import configparser as ConfigParser
        except ImportError:
            sys.exit("ERROR: ConfigParser module not found.")
except ImportError:
    print("One of the import modules is missing.")
    print("Install eg. Debian: apt-get install python[3]-module_name first!")
    exit(1)

reload(sys)  
sys.setdefaultencoding('utf8')

# global data
Conf = {}       # data dict for configuration variables, values and static values

# ==========================================================================
# configuration
# ==========================================================================
# allowed output/output channels can be switched on or off
# from configuration file or command argument options
# INPUT/OUTPUT)_I IO needs internet connectivity
# all are plugins declared via the init/config file
OUTPUTS_I  = []         # output using internet
OUTPUTS    = []         # local output channels
INPUTS_I   = []         # inputs from internet (disables other input channels)
INPUTS     = []         # local input channels
INTERVAL   = 60*60      # dflt main loop interval in seconds

# parse the program configuration (ini) file progname.conf
#       or uppercase progname as defined by environment variable
# Parse configuration
def read_configuration():
    global Conf, OUTPUTS, OUTPUTS_I, INPUTS, INPUTS_I, progname
    config = ConfigParser.RawConfigParser()
    initFile = os.getenv(progname.replace('.py','').upper())
    if not initFile:
        initFile = progname.replace('.py','') + '.conf'
    if os.path.isfile(initFile):
        try:
            config.read(initFile)
        except:
            sys.exit("Config/init file %shas configuration errors." % initFile)
    else:
        config = None
        MyLogger.log('WARNING',"No configuration file %s.conf found." % (progname.replace('.py','')))

    if config:
        for key in config.sections():
            if not key in Conf.keys():
                Conf[key] = {}
            options = []
            if os.path.isfile('My'+key.upper()+'.pyc') or os.path.isfile('My'+key.upper()+'.py'):
                Conf[key]['import'] = 'My'+key.upper()
                Conf[key]['module'] = False
                try:
                    Conf[key]['module'] = __import__(Conf[key]['import'])
                    if not CheckVersion(Conf[key]['module'].__version__):
                        MyLogger.log('FATAL',"Module %s version is not compatible." % key)
                except NameError:
                    MyLogger.log('FATAL',"Module %s has no version defined." % key)
                    Conf[key]['module'] = False
                except ImportError:
                    MyLogger.log('WARNING',"Unable to install plugin My%s. Try running the plugin for the failure message." % key.upper())
                    Conf[key]['module'] = False
                if not Conf[key]['module']:
                    del Conf[key]
                else:
                    options = Conf[key]['module'].__options__
                    for InOut in ['input','output']:
                        if InOut in options:
                            #MyLogger.log('DEBUG',"Importing %s plugin: %s" % (InOut,Conf[key]['import']))
                            Conf[key][InOut] = False
                            if (InOut == 'input') and (not InOut in INPUTS+INPUTS_I):
                                if 'hostname' in options:
                                    INPUTS_I.append(key)
                                else:
                                    INPUTS.append(key)
                            if (InOut == 'output') and (not InOut in OUTPUTS+OUTPUTS_I):
                                if 'hostname' in options:
                                    OUTPUTS_I.append(key)
                                else:
                                    OUTPUTS.append(key)
                    # end for InOut
            else:
                if key == 'id':
                    options = ['project','serial','geolocation']
                elif key == 'process':
                    options = ['home','pid','user','group','start_dir']
                elif key == 'logging':
                    options = ['level','file']
            #MyLogger.log('DEBUG','Configuring module %s: options %s.' % (key,', '.join(config.options(key))) )
            for opt in config.options(key):
                if not opt in options: continue
                try:
                    Conf[key][opt.lower()] = config.get(key,opt)
                    if opt in ['input','output']:
                        Conf[key][opt.lower()] = config.getboolean(key,opt)
                    elif opt.lower() == 'port':
                        if re.compile("^[0-9]+$").match(Conf[key][opt.lower()]):
                            Conf[key][opt.lower()] = int(Conf[key][opt.lower()])
                    elif (opt.lower() == 'level'):
                        Conf[key][opt.lower()] = Conf[key][opt.lower()].upper()
                except:
                    pass
            # end if
                
    if config == None:
        return

    for io in ['input','output']:
        if io == 'input': array = INPUTS+INPUTS_I
        else: array = OUTPUTS+OUTPUTS_I
        Conf[io + 's'] = []          # ######    different output possibilities
        for Nme in array:
            if Conf[Nme][io]:
                Conf[io+'s'].append(Nme)

    # if root change effective user/group
    try:
        if (os.geteuid() == 0) and ('user' in Conf['process'].keys()):
            import pwd
            Conf['process']['uid'] = pwd.getpwname(Conf['process']['user'])[2]
    except:
        MyLogger.show_error()
    try:
        if (os.getegid() == 0) and ('group' in Conf['process'].keys()):
            import grp
            Conf['process']['gid'] = grp.getgrnam(Conf['process']['group'])[2]
    except:
        MyLogger.show_error()
    return True

def get_serial():
    try:        # try serial cpu number
        p=subprocess.Popen('cat /proc/cpuinfo',shell=True,stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()
        ips = re.findall('Serial\s+:\s*([A-Za-z0-9]+)', stdout)
        for item in ips:
            return item.lstrip('0')
    except:
        pass
    try:
        p=subprocess.Popen('/sbin/ifconfig',shell=True,stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()
        ips = re.findall('HWaddr\s+([0-9a-f]{2}(:[0-9a-f]{2}){5})', stdout)
        for item in ips:
            return item[0].replace(':','')
    except:
        pass
    return 'undefined'

# ==================================================================
# configuration defaults definitions and values: init Conf and update from conf file
# ==================================================================
# TO DO: push all input/output routines in a class and load dynamically
def get_config():
    global Conf, __version__
    Conf = {}
    Conf['process'] = {
        'home': '/var/tmp/',   # deamon process home directory, default: current
        'pid': '/var/tmp/',    # deamon pid file directory
        'user': None,          # deamon user ID
        'group': None,         # deamon grgoup ID, pref: dailout
        'start_dir': os.getcwd() + '/' # remember where we started this process
    }
    Conf['id'] = {
        'project': 'undefined',    # project identification
        'serial': get_serial(),    # serial number of this sensor 
        'geolocation': None, # lat,long, and altitude in meters
        'version': __version__,  # data version
    }
    Conf['logging'] = {
        #'level': 'NOTSET',   # verbosity
        'level': 'ATTENT',   # verbosity
        'file': '/dev/stderr', # /var/log/IoS/IoS.log Unix log file
    }
    # communication mechanism to internet land
    Conf['internet'] = {
        'import': 'MyInternet', # the plugin for internet connectivity
        'module': None,         # last time connected to internet
        'connected': None       # connected to internet?
    }
    # default loaded modules
    Conf['console'] = {
        'output': False,
        'import': 'MyConsole',
        'module' : None,
        'file': '/dev/stdout',
    }
    # defaults for output modes: only console output is enabled
    if not 'console' in OUTPUTS:
        OUTPUTS.append('console')
    # Configuration or init file handling
    if not read_configuration():
       MyLogger.log('WARNING',"Init/configuration skipped.")

# ===================================================================
# Commandline arguments parsing
# ===================================================================
def get_arguments():
    global Conf, progname, INTERVAL
    parser = argparse.ArgumentParser(prog=progname, description='Sensor datalogger - Behoud de Parel\nCommand arguments overwrite optional config file.', epilog="Copyright (c) Behoud de Parel\nAnyone may use it freely under the 'GNU GPL V4' license.")
    parser.add_argument("-d", "--debug", help="List of input sensors and show the raw sensor values.", default="")
    parser.add_argument("-i", "--input", help="Input sensor(s), comma separated list of %s" % ','.join(INPUTS+INPUTS_I), default="%s" % ','.join(Conf['inputs']))
    parser.add_argument("-o", "--output", help="Output mode(s), comma separated list of %s" % ','.join(OUTPUTS+OUTPUTS_I), default="%s" % ','.join(Conf['outputs']))
    parser.add_argument("-l", "--level", help="Be less verbose, default='%s'" % Conf['logging']['level'], default=Conf['logging']['level'], type=str.upper, choices=MyLogger.log_levels)
    parser.add_argument("-P", "--project", help="Project XYZ, default='%s'" % Conf['id']['project'], default=Conf['id']['project'], choices=['BdP','VW'])
    parser.add_argument("-S", "--node", help="Sensor node serial number, default='%s'" % Conf['id']['serial'], default=Conf['id']['serial'])
    parser.add_argument("-G", "--geolocation", help="Sensor node geolocation (latitude,longitude), default='%s'" % Conf['id']['geolocation'], default=Conf['id']['geolocation'])
    parser.add_argument("-I", "--interval", help="Sensor read cycle interval in minutes, default='%d'" % (INTERVAL/60), default=(INTERVAL/60))
    parser.add_argument("-D", "--DYLOS", help="Read pm sensor input from an input file instead. Debugging simulation.")
    parser.add_argument("process", help="Process start/stop/status. Default: interactive", default='interactive', choices=['interactive','start','stop','status'], nargs='?')
    # overwrite argument settings into configuration
    return parser.parse_args()

# roll in the definition from environment eg passwords
def from_env(name):
    global Conf
    for credit in ['hostname','user','password']:
        if not credit in Conf[name].keys():
            Conf[name][credit] = None
        try:
            Conf[name][credit] = os.getenv(name.upper()+credit[0:4].upper(),Conf[name][credit])
        except:
            pass
    return True

# =================================================================
# Overwrite configuration values with argument values
# =================================================================
def integrate_options():
    global Conf, OUTPUTS, OUTPUTS_I, INPUTS, INPUTS_I, INTERVAL
    
    cmd_args = get_arguments()

    Conf['id']['project'] = cmd_args.project
    Conf['id']['serial'] = cmd_args.node
    Conf['id']['geolocation'] = cmd_args.geolocation
    INTERVAL = cmd_args.interval * 60

    Conf['outputs'] = []
    # TO DO: enable MQTT to be used on output as well on input
    for Nme in OUTPUTS+OUTPUTS_I:
        # different output modes
        try:
            Conf[Nme]['output'] = cmd_args.output.rindex(Nme) >= 0
        except:
            Conf[Nme]['output'] = False
        if Conf[Nme]['output']:
            if not Nme in Conf['outputs']:
                Conf['outputs'].append(Nme)
            # database credits and configurations
            if Nme in OUTPUTS_I:
                from_env(Nme)

    if 'db' in Conf['outputs']:
        try:
            Conf['db']['database']= os.getenv('DB', Conf['db']['database'])
        except:
            pass
                
    if not len(Conf['outputs']):
        if not 'console' in Conf.keys():
            Conf['console'] = { 'import': 'MyCONSOLE', 'type': None}
        Conf['console']['output'] = True
        if not Nme in Conf['outputs']:
            Conf['outputs'].append('console')
        MyLogger.log('WARNING',"No output channels defined. Enabled output to console.")

    # TO DO: enable MQTT to be used on output as well on input
    Conf['inputs'] = []
    for Nme in INPUTS+INPUTS_I:
        # different input sensors
        try:
            Conf[Nme]['input'] = cmd_args.input.rindex(Nme) >= 0
        except:
            Conf[Nme]['input'] = False
        if Conf[Nme]['input']:
            if not Nme in Conf['inputs']:
                Conf['inputs'].append(Nme)
            if Nme in INPUTS_I:
                from_env(Nme)
        try:    # allow to display raw sensor values from a sensor thread
            Conf[Nme]['debug'] = cmd_args.debug.rindex(Nme) >= 0
        except:
            Conf[Nme]['debug'] = False

    if 'dylos' in Conf['inputs']:
        if ('usbPID' in Conf['dylos'].keys()):
            if re.compile("^[0-9a-zA-Z_,]{7,}").match(Conf['dylos']['usbPID']) == None:
                sys.exit(Conf['dylos']['usbPID'] + " is not a USB producer name.")
        if cmd_args.DYLOS:
            Conf['dylos'].update({ 'input': True, 'file': cmd_args.debug })

    if not len(Conf['inputs']):
        MyLogger.log('FATAL',"No sensor input is defined.")

    Conf['logging']['level']    = cmd_args.level.upper()     # how much we log
    return cmd_args.process

# show the intension of this process
def show_startup():
    global Conf, progname, __version__
    MyLogger.log('ATTENT',"%s Started Sensor processing: %s Version:%s" % (datetime.datetime.strftime(datetime.datetime.today(), "%Y-%m-%d %H:%M:%S " ), progname, __version__))
    MyLogger.log('DEBUG',"Control-C to abort")
    MyLogger.log('DEBUG',"Engine: Python Version %s.%s.%s\n" % sys.version_info[:3])
    MyLogger.log('DEBUG',"Startup parameters:")
    for item in ('project','serial','geolocation'):
        if (item in Conf['id'].keys()) and (Conf['id'][item] != None):
            MyLogger.log('ATTENT',"\t %s:\t%s" % (item,Conf['id'][item]))

    MyLogger.log('INFO',"Available INPUT SENSORS: %s" % ', '.join(INPUTS+INPUTS_I))
    for Sensor in INPUTS+INPUTS_I:
        if (not Sensor in Conf.keys()) or (not 'input' in Conf[Sensor].keys()):
            MyLogger.log('INFO',"Sensor %s not installed." % Sensor)
            continue
        if Conf[Sensor]['input']:
            MyLogger.log('ATTENT',"Sensor %s (plugin %s) is switched ON." % (Sensor,Conf[Sensor]['import']))
            for Opt in Conf[Sensor].keys():
                if Opt == 'input' or Opt == 'module': continue
                MyLogger.log('INFO',"\t%s:\t%s" % (Opt,Conf[Sensor][Opt]))
        else:
            MyLogger.log('INFO',"Sensor %s (plugin %s) is switched OFF." % (Sensor,Conf[Sensor]['import']))
                # continue
            for Opt in Conf[Sensor].keys():
                if Opt == 'input' or Opt == 'module': continue
                MyLogger.log('DEBUG',"\t%s:\t%s" % (Opt,Conf[Sensor][Opt]))

    MyLogger.log('INFO',"Available OUTPUT CHANNELS: %s" % ', '.join(OUTPUTS+OUTPUTS_I))
    for Mode in OUTPUTS+OUTPUTS_I:
        if Conf[Mode]['output']:
            MyLogger.log('ATTENT',"Ouput channel %s (plugin %s) is ENABLED." % (Mode,Conf[Mode]['import']))
            for Attr in Conf[Mode].keys():
                if (Attr != 'output') and (Attr != 'password') and (Attr != 'module'):
                    MyLogger.log('INFO',"\t%s:\t%s" % (Attr,Conf[Mode][Attr]))
        else:
           MyLogger.log('DEBUG',"Ouput channel %s (plugin %s) is DISABLED, attributes:" % (Mode,Conf[Mode]['import']))
           # continue
           for Attr in Conf[Mode].keys():
               if (Attr != 'output') and (Attr != 'password') and (Attr != 'module'):
                   MyLogger.log('DEBUG',"\t%s:\t%s" % (Attr,Conf[Mode][Attr]))
    
# ===========================================================
# Routines needed to run as UNIX deamon
# ===========================================================

def delpid():
    global pidfile
    os.remove(pidfile)

def pid_kill(pidfile):
    pid = int(os.read(fd, 4096))
    os.lseek(fd, 0, os.SEEK_SET)

    try:
        os.kill(pid, SIGTERM)
        sleep(0.1)
    except OSError as err:
        err = str(err)
        if err.find("No such process") > 0:
            if os.path.exists(pidfile):
                os.remove(pidfile)
        else:
            sys.exit(str(err))

    if pid_is_running():
        sys.exit("Failed to kill %d" % pid)

def pid_is_running(pidfile):
    try:
        fd = os.open(pidfile, os.O_RDONLY)
    except:
        return False
    contents = os.read(fd, 4096)
    os.lseek(fd, 0, os.SEEK_SET)
    if not contents:
        return False
    os.close(fd)

    p = subprocess.Popen(["ps", "-o", "comm", "-p", str(int(contents))],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if stdout == "COMM\n":
        return False
    if 'python' in stdout[stdout.find("\n")+1:]:
        return int(contents)

    return False

def deamon_daemonize(pidfile):
    global progname
    try:
        pid = os.fork()
        if pid > 0:
            # exit first child
            sys.exit(0)
    except OSError as err:
        sys.stderr.write('fork #1 failed: {0}\n'.format(err))
        sys.exit(1)
    # decouple from parent environment
    os.setsid()
    os.umask(0)
    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent
            sys.exit(0)
    except OSError as err:
        sys.stderr.write('fork #2 failed: {0}\n'.format(err))
        sys.exit(1)
    # write pidfile
    atexit.register(delpid)
    pid = str(os.getpid())
    try:
        fd = os.open(pidfile, os.O_CREAT | os.O_RDWR)
    except IOError as e:
        sys.exit("Process already running? Failed to open pidfile %s: %s" % (progname, str(e)))
    assert not fcntl.flock(fd, fcntl.LOCK_EX)
    os.ftruncate(fd, 0)
    os.write(fd, "%d\n" % int(pid))
    os.fsync(fd)
    # redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    si = open(os.devnull, 'r')
    so = open(os.devnull, 'a+')
    se = open(os.devnull, 'a+')
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

def deamon_detach(pidfile):
    if pidfile == None:
        sys.exit("Cannot start deamon: no pid file defined.")
    # Check for a pidfile to see if the daemon already runs
    if pid_is_running(pidfile):
        sys.exit("Daemon already running.")

    # Start the daemon
    deamon_daemonize(pidfile)

def deamon_stop(pidfile):
    if pidfile == None:
        sys.exit("Cannot stop deamon: no pid file defined.")
    # Get the pid from the pidfile
    pid = pid_is_running(pidfile)
    if not pid:
        sys.stderr.write("Daemon not running.\n")
        exit(0)

    # Try killing the daemon process
    error = os.kill(pid,SIGTERM)
    if error:
        sys.exit(error)

def deamon_status(pidfile):
    global progname
    if pid_is_running(pidfile):
        sys.stderr.write("%s is running.\n" % progname)
    else:
        sys.stderr.write("%s is NOT running.\n" % progname)

# Define Global Variables

# ================ List of Global Variables to be stored in DB
# next has keys as: time, dylos[4], temp, humidity, asense[8]
# ================ End of Variable List

# =================================================================
# read forever sensor data and publicise the results
# =================================================================
# compile the sensors values telegram and output the telegram to the world
# TO DO: multiple input channels can block each other: select/multi threading
def sensorread():
    #Continuously loop collecting all data
    global Conf, INTERVAL
    if not 'fields' in Conf['id'].keys():
        Conf['id']['fields'] = ['time']
        Conf['id']['units'] = ['s']
    Conf['id']['types'] = []
    data = { 'time': 0 }
    first = True
    local = True
    # for now if input vai internet is defined, local sensor input is disabled
    # TO DO: have 2 threads: one for input and one (main thread) for output
    # TO DO: handle multiple input channels with select and threads
    while True:
        if not len(Conf['outputs']):
            MyLogger.log('FATAL',"No output available any more. Abort.")
        data = {'time': data['time']}
        ident = Conf['id']
        local = True
        gotData = False
        t_cnt = 0 ; t_time = 0
        for Sensor in Conf['inputs']:
            if not Conf[Sensor]['input']:
                continue
            try:
                sensed = Conf[Sensor]['module'].getdata()
                if (not type(sensed) is dict) or (not len(sensed)):
                    continue
                if 'hostname' in Conf[Sensor].keys():
                    # if len(Conf['inputs'])-1:
                    ident = {}
                    if 'register' in sensed.keys():
                        ident = sensed['register']
                    if 'data' in sensed.keys():
                        data.update(sensed['data'])
                        gotData = True
                    local = False
                    break
                if ('time' in sensed.keys()) and sensed['time']:
                    t_cnt += 1
                    t_time += sensed['time']                       
                for key in sensed.keys():
                    if key == 'time': continue
                    if key in data.keys():
                        # some sensor key are the same, except only 2 of them
                        # examples are meteo values eg temp, humidity
                        MyLogger.log('DEBUG',"There is more then one %s in data stream: collected: %5.1f, new %5.1f" % (key,data[key],sensed[key]))
                        if (type(data[key]) is int) and (type(sensed[key]) is int):
                            sensed[key] = int((sensed[key]+data[key]+0.5)/2)
                        else:
                            sensed[key] = (sensed[key]+data[key])/2
                data.update(sensed)
                gotData = True
            except KeyboardInterrupt:
                exit(0)
            except (Exception) as error:
                MyLogger.log('ERROR',"%s Error : %s. Disabled." % (Sensor,error))
                Conf['inputs'].remove(Sensor)
                if not len(Conf['inputs']):
                    MyLogger.log('FATAL',"No input sensors active any more. Exiting.")
                continue
            if first and local:
                for i in range(0,len(Conf[Sensor]['module'].Conf['fields'])):
                    if not Conf[Sensor]['module'].Conf['fields'][i] in Conf['id']['fields']:
                        Conf['id']['fields'].append(Conf[Sensor]['module'].Conf['fields'][i])
                        Conf['id']['units'].append(Conf[Sensor]['module'].Conf['units'][i])
                if ('type' in Conf[Sensor]['module'].Conf.keys()) and (Conf[Sensor]['module'].Conf['type'] != None):
                    if not Conf[Sensor]['module'].Conf['type'] in Conf['id']['types']:
                        Conf['id']['types'].append(Conf[Sensor]['module'].Conf['type'])
                if Sensor == 'gps':
                    if ((not 'geolocation' in Conf['id'].keys())) or \
                        (Conf['id']['geolocation'] == None):
                        Conf['id']['geolocation'] = data["geolocation"]
                if (Sensor == 'rssi') and ('rssi' in data.keys()) and data['rssi']:
                    if ('description' in Conf['id'].keys()) and Conf['id']['description']:
                        Conf['id']['description'] += " wifi signal level: %d" % data['rssi']
                    else:
                        Conf['id']['description'] = " wifi signal level: %d" % data['rssi']
        first = False

        if local:
            data['time'] = int(time())   # datetime.datetime.now()
            if t_cnt and t_time:
                data['time'] = int(t_time/t_cnt)
            # ident = Conf['id']
        elif not len(ident):
            continue
        elif (not 'project' in ident.keys()) or (not 'serial' in ident.keys()):
            continue
        # TO DO: push inputs into an array with idents and data and publish them
        # next have threads to fill and empty the buffer supervised with a semaphore
        
        if gotData:      # data collected?
            for Out in Conf['outputs']:
                if not Conf[Out]['output']: continue
                if not 'module' in Conf[Out].keys(): continue
                # TO DO: do this async
                try:
                    Conf[Out]['module'].publish(
                        ident = ident,
                        data = data,
                        internet = Conf['internet']
                    )
                except IOError:
                    Conf['outputs'].remove(Out)
                    MyLogger.log('ERROR',"Publish via %s failed. Buffering it for now?" % Out)
                    # TO DO: add buffer for non published data
                    # Add2Buffer(Out,data)
                except:
                    Conf['outputs'].remove(Out)
                    Conf[Out]['module'].Conf['output'] = False
                    MyLogger.log('ERROR',"Publish via %s failed. Skipping it." % Out)
        if local:
            if local and (time() - data['time'] < INTERVAL):    # limit to once per minute
                sleep(INTERVAL-(time()-data['time'])) 
        local = True
    return False

def CheckVersion(version):
    global __version__
    if version == None:
        return False
    mod = re.split('\.',version, maxsplit = 3)
    mine = re.split('\.',__version__, maxsplit = 3)
    if len(mod) < 2:
        return False
    if (int(mod[0]) != int(mine[0])):
        return False
    if (int(mod[1]) > int(mine[1])):
        return False
    return True

# try to save some memory by freeing memory of unused plugins
def FreeConfMem(*IO):
    global Conf
    for io in IO:
        for key in Conf.keys():
            if not type(Conf[key]) is dict:
                continue
            if (io in Conf[key].keys()) and (not Conf[key][io]):
                # the unload in python does not really free much mem
                if 'module' in Conf[key].keys():
                    try:
                        del Conf[key]['module']
                        sys.modules.pop(Conf[key]['import'])
                    except:
                        pass
                del Conf[key]
                MyLogger.log('DEBUG',"Deleted plugin My%s (unused)." % key.upper())
    return True

# load optional configured input/output module plugins
# clean up the configuration
def LoadWrapup(io):
    global Conf, INPUTS_I, OUTPUTS_I
    def Review(io,internet):     # allow only local plugings or remote plugins
        global Conf
        net = []
        notNet = []
        for i in range(0,len(Conf[io])):
            if ('hostname' in Conf[Conf[io][i]].keys()) and Conf[Conf[io][i]]['hostname']:
                net.append(Conf[io][i])
            else:
                notNet.append(Conf[io][i])
        if internet:
            return net
        else:
            return notNet
            
    if io == 'inputs':
        inet = Review(io,True)
        if len(inet): # found input channel from internet
            for Nme in Review(io,False):
                Conf[Nme]['input'] = False  # turn local sensors off
            Conf['inputs'] = inet
    for Nme in Conf[io]:
        if (not Conf[Nme][io.replace('s','')]) or (not 'import' in Conf[Nme].keys()):
            continue
        if Nme in INPUTS_I + OUTPUTS_I: # need internet connectivity?
            try:
                if not Conf['internet']['module']:      # only once
                    MyLogger.log('DEBUG',"Importing module: %s" % Conf['internet']['import'])
                    Conf['internet']['module'] = __import__(Conf['internet']['import'])
                    Conf['internet']['connected']=Conf['internet']['module'].internet(Conf['id'])
            except:
                MyLogger.log('FATAL',"Unable to install internet access.")
        if ('import' in Conf[Nme].keys()) and (not 'module' in Conf[Nme].keys()):
            MyLogger.log('DEBUG',"Importing %s plugin: %s" % (io,Conf[Nme]['import']))
            try:
                Conf[Nme]['module'] = __import__(Conf[Nme]['import'])
                if not CheckVersion(Conf[Nme]['module'].__version__):
                    MyLogger.log('FATAL',"Module %s version is not compatible." % Nme)
            except NameError:
                MyLogger.log('FATAL',"Module %s has no version defined." % Nme)
            except ImportError:
                MyLogger.log('FATAL',"Unable to import input/output module %s" % Conf[Nme]['import'])
        # handle options for the module
        if ('module' in Conf[Nme].keys()):
            Conf[Nme]['module'].Conf.update(Conf[Nme])  # set module attributes

# ===============================================================
# Main program
# ===============================================================
# initialise

get_config()
process = integrate_options()
MyLogger.Conf.update(Conf['logging'])
LoadWrapup('inputs')
LoadWrapup('outputs')

################# ================================================ ##############
#                     start running                                ##############
################# ================================================ ##############
if ('start_dir' in Conf['process'].keys()) and Conf['process']['start_dir']:
    try:
        os.chdir(Conf['process']['start_dir'])
    except:
        MyLogger.log('FATAL',"Could not change directory to %s." % Conf['process']['start_dir'])

if process == 'interactive':  ## interactive mode ===========
    print("Stop this process NOT via <cntrl>c, but via <cntrl>z and kill %1")
    show_startup()
    FreeConfMem('input','output')
    del INPUTS; del INPUTS_I ; del OUTPUTS; del OUTPUTS_I
    sensorread()                   # ============================= RUN
else:                              ## service mode     ===========
    import atexit
    from os import geteuid, getegid
    from signal import SIGTERM
    import fcntl
    try:
        if ('uid' in Conf['process'].keys()) and (Conf['process']['uid']):
            setuid(Conf['process']['uid'])
        if ('gid' in Conf['process'].keys()) and (Conf['process']['gid']):
            setgid(Conf['process']['gid'])
    except:
        MyLogger.log('ERROR',"Cannot set process uid (%d) or gid (%d)." % (setuid(Conf['process']['uid'],etgid(Conf['process']['gid']))))
    if geteuid() == 0:
        MyLogger.log('ERROR',"Process deamon is running under root permissions!")
    pidfile = Conf['process']['pid'] + progname + '.pid'
    os.chdir(Conf['process']['home'])    # current directory now is here
    if process == 'start':
        show_startup()
        FreeConfMem('input','output')
        del INPUTS; del INPUTS_I ; del OUTPUTS; del OUTPUTS_I
        ser = open_input_stream()
        Conf['console']['output'] = False
        deamon_detach(pidfile)
        WaitTime = 60   # wait time to restart sensorread

        for RunCnt in range(1,30):
            LastTime = time()
            try:
                sensorread()            # ======================== RUN
            except IOError, e:
                for name in Conf.keys():
                    if Conf[name].has_key('fd') and Conf[name,'id']:
                        try:
                            close(Conf[name,'fd'])
                        except:
                            pass
                        Conf[name,'fd'] = None
                MyLogger.log('ERROR',"IO error %s, try to restart" % e)
            if (time() - LastTime) > 60:
                WaitTime = 60
            else:
                WaitTime *= 2
            if WaitTime > 60*60:
                WaitTime = 60*60
            sleep(WaitTime)
                    
    elif process == 'stop':
        deamon_stop(pidfile)
    elif process == 'status':
        deamon_status(pidfile)
    else:
        sys.exit("Unknown process request.")
exit(0)
