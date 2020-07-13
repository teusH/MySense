#!/usr/bin/env python
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

# $Id: MyDisplayClient.py,v 1.3 2017/08/15 13:50:28 teus Exp teus $

# script to send text to SSD1306 display server

import socket
import sys
from time import sleep

def displayMsg(msg):
    host = 'localhost'
    port = 2017
    degree = u'\N{DEGREE SIGN}'
    micro = u'\N{MICRO SIGN}'

    if not len(msg): return True
    if not type(msg) is list: msg = msg.split("\n")
    for i in range(len(msg)-1,-1,-1):
        if not len(msg[i]):
            msg.pop(i)
            continue
        msg[i] = format(msg[i])
        if msg[i][-1] == "\n": msg[i] = msg[i][:-1]
        msg[i] = msg[i].replace('oC',degree + 'C')
        #msg[i] = msg[i].replace('ug/m3',micro + 'g/m³')
        msg[i] = msg[i].replace('ug/m3',micro + 'g/m3')
    msg = "\n".join(msg) + "\n"
    if not len(msg): return True
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host,port))
        sock.send(msg)
        sock.close()
        return True
    except:
        raise IOError("Unable to talk to display service")
        return False

if __name__ == '__main__':
    for msg in sys.argv[1:]:
        if not displayMsg(msg):
            print("Failed to display message: %s",msg)
