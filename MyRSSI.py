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

# $Id: MyRSSI.py,v 1.2 2017/02/01 12:47:13 teus Exp teus $

# TO DO:

""" wifi rssi values
"""
modulename='$RCSfile: MyRSSI.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.2 $"[11:-2]

# configurable options
__options__ = ['input']

Conf = {
    'input': False,
    # 'rssi':     None,   # if wifi provide signal strength
    # 'last':     None,   # last time checked to throddle connection info
    'fields': ['rssi'],   # strength or signal level
    'units' : ['dBm'],    # per field the measurement unit
}

try:
    import MyLogger
    import re
    # import subprocess, threading
    import subprocess
    from threading import Timer
    from time import time
except ImportError as e:
    MyLogger.log('FATAL',"Unable to load module %s" % e)

class Command(object):
    def __init__(self, cmd):
        self.cmd = cmd
        self.process = None

    def run(self, timeout):
        stdout = ''
        def target():
            global stdout
            print 'Thread started'
            self.process = subprocess.Popen(self.cmd, shell=True, stdout=subprocess.PIPE)
            stdout, stderr = self.process.communicate()
            print 'Thread finished'
            
        thread = threading.Thread(target=target)
        thread.start()

        thread.join(timeout)
        if thread.is_alive():
            print 'Terminating process'
            self.process.terminate()
            thread.join()
        print self.process.returncode
        return stdout

#command = Command("echo 'Process started'; sleep 2; echo 'Process finished'")
#command.run(timeout=3)
#command.run(timeout=1)

# obtain some wifi info so we can track the wifi availability
def getdata():
    global Conf
    if ('rssi' in Conf.keys()) and (not Conf['rssi']):
        return {}
    if not 'rssi' in Conf.keys():
        Conf.update({'rssi': 0, 'last': 0})
    # only once per 15 minutes
    if time()-Conf['last'] > 15*60:
        Conf['last'] = int(time())
        try:
            # p=subprocess.Popen('/sbin/iwconfig',shell=True,stdout=subprocess.PIPE)
            # stdout, stderr = p.communicate()
            # command = Command('/sbin/iwconfig')
            # stdout = command.run(timeout=4)
            kill = lambda process: process.kill()
            cmd = ['/sbin/iwconfig']
            iw = subprocess.Popen( cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            my_timer = Timer(5, kill, [iw])
            try:
                my_timer.start()
                stdout, stderr = iw.communicate()
            finally:
                try:
                    my_timer.cancel()
                except:
                    pass
            ips = re.findall('[Ss]ignal\s+level=\s*(-[0-9]+)\s+dBm', stdout)
            for item in ips:
                # TO DO: may need to exclude wifi AP ip interfaces
                Conf['rssi'] = item[0]
                break
        except:
            return {}
    return {'time': int(time()),'rssi': Conf['rssi']}
