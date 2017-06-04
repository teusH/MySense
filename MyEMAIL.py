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

# $Id: MyEMAIL.py,v 2.6 2017/06/04 09:40:55 teus Exp teus $

# TO DO: write to file or cache

""" Publish via email identification of this measurement node
    Email either via smtp 587 port (requires email credentials)
    or using conventual email service: sendmail
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyEMAIL.py,v $'[10:-4]
__version__ = "0." + "$Revision: 2.6 $"[11:-2]

# send email once on startup when broker is used

# configurable options
__options__ = ['output','hostname','user','pass','to','ttl','from']

Conf = {
    'output': False,
    'to': None,          # send sensor location details via email to
    # on a dump node we need an email forwarder and user credits
    'user': None,        # 587 port smtp proxy service credentials
    'password': None,    # 587 port smtp proxy service credentials
    'hostname': 'localhost',    # 587 port smtp proxy service server
    'port': 587,         # smtp port
    'from': None,        # the from address of the email
    'registrated': None, # have registrated
    'ttl': None,         # time in secs to live for forced new registrationo
    'version': None,     # data version
    'fd': None,          # 1 once connected, 0 if connectivity broke
}

try:
    import MyLogger
    from email.mime.text import MIMEText
    import datetime
    import smtplib
except ImportError:
    MyLogger.log(modulename,'FATAL',"Unable to import needed module.")

def get_from():
    """ get from address for sending emails. """
    global Conf
    if ('from' in Conf.keys()) and (Conf['from'] != None):
        return Conf['from']
    try:
        import getpass
        import socket
        Conf['from'] = getpass.getuser() + '@' + socket.getfqdn()
    except:
        MyLogger.log(modulename,'ERROR',"For sending email missing getpass or socket module.")
        return None
    return Conf['from']

def registrate(ident,net):
    """ send email once a while (defined by ttl) with identification details.
        PII rules should be applied. """
    global Conf
    def WhereAmI(key,flds):
        global Conf
        query = []
        for fld in flds:
            if ((key,fld) in Conf.keys()) and (key[fld] != None):
                query.append("%s:\t%s" % (fld,key[fld]))
        if not len(query): return ''
        return "\n\t".join(query)

    if (Conf['fd'] != None) and (not Conf['fd']):
        if ('waiting' in Conf.keys()) and ((Conf['waiting']+Conf['last']) >= time()):
            # raise IOError
            return False

    if Conf['registrated'] != None:
        if not Conf['ttl']:
            return Conf['registrated']
        if not 'renew' in Conf.keys():
            Conf['renew'] = int(time())+Conf['ttl']
        if time() < Conf['renew']:
            return Conf['registrated']
    if not net['module'].internet(ident):
        Conf['registrated'] = False
        return False
    Conf['registrated'] = True

    # Code to Send (geo)location info eg IP address(es)
    body = "Sensor %s_%s is switched on." % (ident['project'],ident['serial'])
    body += WhereAmI(ident,["label","description","geolocation","street","village","province","municipality"])
    if 'types' in ident.keys():
        body += "\nInstalled sensors from: %s" % ', '.join(ident['types'])
    if 'fields' in ident.keys():
        body += "\nMysensors installed:"
        for i in range(0,len(ident['fields'])):
            body += "\n\t%s, %s" % (ident['fields'][i],ident['units'][i])
    body += WhereAmI(ident,['intern_ip','extern_ip','version'])
    msg = MIMEText(body)
    msg['Subject'] = 'IP For Node %s_%s on %s' % (ident['project'],ident['serial'],datetime.date.today().strftime('%b %d %Y'))
    if (not 'from' in Conf.keys()) or (not Conf['from']):
        Conf['from'] = get_from()
    for frm in ['from','to']:
        if (frm in Conf.keys()) and (Conf[frm] != None):
            try:
                Conf[frm].find('@')
            except:
                Conf[frm] = None
    if (not 'to' in Conf.keys()) or (Conf['to'] == None):
        MyLogger.log(modulename,'ERROR',"Email To address is defined. Email aborted.")
        Conf['output'] = False
        return False
    msg['To'] = Conf['to']
    msg['From'] = Conf['from']
    # send the message via proxy or direct
    smtp = True
    for cred in ['hostname','user','password']:
        if (not cred in Conf.keys()) or not Conf[cred]:
            smtp = False
            break
    try:
        if smtp:
            msg['From'] = Conf['user']
            smtpserver = smtplib.SMTP(Conf['hostname'], Conf['port'])
            smtpserver.ehlo()
            smtpserver.starttls()
            smtpserver.ehlo
            smtpserver.login(Conf['user'], Conf['password'])
        else:
            if msg['From'] == None:
                MyLogger.log(modulename,'ERROR',"From address is not defined. Email aborted.")
                Conf['output'] = False
                return False
            smtpserver = smtplib.SMTP('localhost')
        smtpserver.sendmail(msg['From'], [msg['To']], msg.as_string())
        smtpserver.quit()
    except:
        MyLogger.log(modulename,WARNING,"SMTP error, unable to send session email")
        Conf['registrated'] = False
        Conf['last'] = time() ; Conf['fd'] = 0 ; Conf['waitCnt'] += 1
        if not (Conf['waitCnt'] % 5):
            Conf['waiting'] *= 2
            return False        # we tried hard, no more tries from now
        raise IOError
        return False
    Conf['waiting'] = 5 * 30 ; Conf['last'] = 0 ; Conf['waitCnt'] = 0 ; Conf['fd'] = 1
    return True

def publish(**args):
    global Conf

    if not 'fd' in Conf.keys(): Conf['fd'] = None
    if not 'last' in Conf.keys():
        Conf['waiting'] = 5 * 30 ; Conf['last'] = 0 ; Conf['waitCnt'] = 0

    if Conf['registrated'] != None:
        if (not Conf['ttl']) or (not 'renew' in Conf.keys()):
            return Conf['registrated']
        if time() < Conf['renew']:
            return Conf['registrated']
    # time to send registration email
    for key in ['data','internet','ident']:
        if not key in args.keys():
            MyLogger.log(modulename,'FATAL',"Publish call missing argument %s." % key)
    return registrate(args['ident'],args['internet'])

