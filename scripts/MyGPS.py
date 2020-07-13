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

# $Id: MyGPS.py,v 1.1 2020/05/31 13:40:18 teus Exp teus $

modulename='$RCSfile: MyGPS.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.1 $"[11:-2]

help = """
   Command: python %s [arg] ...
   --help    | -h       This message
   --verbose | -v       Be more verbose (std err channel)
   --correct | -c       Correct address in Sensors table
   --date S  | -d S     Correct address only from date S (seconds from POSIX timestamp) 
   
   Correct address (street, municipality, province, postcode) using reverse lookup
   of GPS coordinates from table Sensors of MySQL database luchtmetingen.
   DB credentials are taken from environment.
   Examples (wildcard in names is '%%'):
   arg: 'SAN' correct address from coordinates of measurement kits for project SAN
   arg: 'SAN_%%123' correct address for kits project SAN with serial ending like %%123
   arg: '%%N'  correct address from coordinates of measurement kits for project names ending 'N'
""" % modulename

# importing the requests library 
import sys
import requests 
from requests.exceptions import HTTPError
import datetime

verbose = False    # be more versatile
correct = False    # make correction / update MySQL table Sensor with address items
date    = ''       # select measurement kit emta with datum from up to now, dflt all

def convert2geohash(coordinates):
    global verbose
    import geohash              # used to get geohash encoder
    if type(coordinates) is unicode: coordinates = str(coordinates)
    if type(coordinates) is str:
        oord = value[1:-1].split(',')
    else: oord = coordinates
    if not (2 <= len(oord) <= 3) or not type(oord) is list:
        raise ValueError("location coordinates error with %s" % str(ordinates))
    for i in range(2): oord[i] = float(oord[i])
    lat = max(oord[0],oord[1]); lon = min(oord[0],oord[1]) # correct expected values
    return '%s' % str(pygeohash(lat, lon, precision=12))

# zoom 18 gives moost details as eg street
# addressdetailks=1 gives 'address'
# example of json return value
# {
#   u'category': u'place',
#   u'addresstype': u'place',
#   u'type': u'house',
#   u'display_name': u'13, My Street, MyVillage, MyMunicipalitry, MyState, MyCountry, 1234AB, MyCountry',
#   u'name': None,
#   u'importance': 0,
#   u'place_id': 32574585,
#   u'lat': u'51.123456',
#   u'lon': u'6.12345',
#   u'boundingbox': [u'51.123456', u'51.123456', u'6.123456', u'6.123456'],
#   u'address': {
#      u'road': u'My Street',
#      u'house_number': u'13',
#      u'city': u'MyMunicipality',
#      u'suburb': u'MyVillage',
#      u'postcode': u'1234AB',
#      u'state': u'MyState',
#      u'country': u'MyCountry',
#      u'country_code': u'xy'
#   },
#   u'osm_id': 7297310746,
#   u'osm_type': u'node',
#   u'place_rank': 30,
#   u'licence': u'Data \xa9 OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright'
# }

LAT = 0
LON = 1
ALT = 2
def GPS2Adress(coordinates):
    global verbose
    # 51.419563,6.14741,20  LAT,LON,ALT style
    Rslt = {}
    if type(coordinates) is unicode: coordinates = str(coordinates)
    if not type(coordinates) is str: return Rslt
    oord = coordinates.split(',')
    if not (2 <= len(oord) <= 3): return Rslt
    if not oord[0] or not float(oord[0]): return Rslt
    # using GPS reverse from Nominatim OpenSteetmap.org
    if float(oord[LAT]) < float(oord[LON]): # correct to Europe coordinates
        tmp = oord[LON]; oord[LON] = oord[LAT]; oord[LAT] = tmp
    if len(oord[LAT]) < 7 or len(oord[LON]) < 6: return Rslt  # precision not high enough
    get = 'reverse?format=jsonv2&addressdetails=1&zoom=18&lat=%s&lon=%s' % (oord[LAT],oord[LON])
    url = 'https://nominatim.openstreetmap.org/'

    try:
        response = requests.get(url+get,timeout=3.0)
        # If the response was successful, no Exception will be raised
        response.raise_for_status()
    except HTTPError as http_err:
        sys.stderr.write('HTTP error occurred: %s\n' % http_err)
        return Rlst
    except Exception as err:
        sys.stderr.write('Other error occurred: %s' % err)
        return Rlst
    response = response.json()
    for item in [(u'postcode','pcode'),(u'road','street'),(u'suburb','village'),(u'city','municipality'),(u'state','province')]:
        try:
            Rslt[item[1]] = str(response[u'address'][item[0]])
        except: pass
    # house number is lossy
    try: Rslt['street'] += ' ' + str(response[u'address'][u'house_number'])
    except: pass
    # correct some fields eg Noord-Brabant -> Brabant
    try: Rslt['province'] = Rslt['province'][Rslt['province'].index('-Brabant')+1:]
    except: pass
        
    return Rslt

def AddressCorrect(project, serial='%', correct=True):
    global verbose, date
    address = ['street','village','municipality','province','pcode']
    kits = DB.db_query("SELECT UNIX_TIMESTAMP(id), coordinates, project, serial, %s FROM Sensors WHERE %s active AND project like '%s' AND serial like '%s'" % (','.join(address),date,project,serial), True)
    if not len(kits):
        sys.stderr.write("Kits for project %s are not defined.\n" % project)
        return False
    for kit in kits:
        kit = list(kit) # convert tuple to list
        if len(kit[4:]) != len(address):
            sys.stderr.write("Unable to extract enough column values in project %s for %s." % (kit[2],', '.join(address)))
            continue
        result = GPS2Adress(kit[1])
        if not result:
            if verbose:
              sys.stderr.write("Precision coordinates %s to low for project %s serial %s\n" % (kit[1],kit[2],kit[3]))
            continue
        if verbose:
            sys.stderr.write("project %s, serial %s, GPS: %s\n" % (kit[2],kit[3],kit[1]))
        qry = []
        for item in result.keys():
            try:
              if verbose:
                 sys.stderr.write("\t%s Database: %s" % (item,str(kit[4+address.index(item)])) )
                 sys.stderr.write("\tOpenStreetMap: %s\n" % str(result[item]))
              if item == 'pcode': # sometimes it is as '1234 AB' or as '1234AB'
                kit[4+address.index(item)] = str(kit[4+address.index(item)]).replace(' ','')
              # street house number from reverse GPS is lossy
              length = len(str(result[item]))
              if item == 'street':
                  try:
                    length = len(str(result[item])[:str(result[item]).rindex(' ')])
                  except: pass
              if str(kit[4+address.index(item)])[:length].lower() != str(result[item])[:length].lower():
                  qry.append("%s = '%s'" % (item,str(result[item])) )
            except: pass
        if not qry: continue
        if verbose:
            sys.stderr.write("Correcting entry ID %s, project %s, SN %s with: %s\n" % (datetime.datetime.fromtimestamp(kit[0]).strftime("%Y-%m-%d %H:%M"),kit[2],kit[3],', '.join(qry)))
        if not correct: continue
        try:
            DB.db_query("UPDATE Sensors SET %s WHERE UNIX_TIMESTAMP(id) = %d" % (','.join(qry),kit[0]),False)
        except Exception as e:
            sys.stderr.write("Error while updating Sensors id = %s, values: %s, exception: %s\n" % (kit[0],','.join(qry),str(e)))
    return True

if __name__ == '__main__':
    argv = []
    for i in range(1,len(sys.argv)):
        if sys.argv[i] in ['--help', '-h']:      # help, how to use CLI
            print(help); exit(0)
        elif sys.argv[i] in ['--verbose', '-v']: # be more verbose
            verbose = True
        elif sys.argv[i] in ['--correct', '-c']: # correct address in Sensors table
            correct = True
        elif sys.argv[i] in ['--date', '-d']:    # correct address in Sensors table
            date = int(sys.argv[i+1]); i += 1
            if not date:
                print(help); exit(1)
            date = 'datum >= FROM_UNIXTIME(%d) AND ' % date
        else: argv.append(sys.argv[i])
    if not verbose:
        import logging
        logging.getLogger("requests").setLevel(logging.WARNING)

    import MyDB as DB
    DB.Conf['output'] = True
    DB.Conf['hostname'] = 'localhost'         # host InFlux server
    DB.Conf['database'] = 'luchtmetingen'     # the MySql db for test usage, must exists
    DB.Conf['user'] = 'IoS'                   # user with insert permission of InFlux DB
    DB.Conf['password'] = 'acacadabra'        # DB credential secret to use InFlux DB
    if not verbose: DB.Conf['level'] = 'WARNING' # log level less verbose

    for project in argv:
        if project.find('_') < 0:
            AddressCorrect(project, correct=correct)
        else:
            AddressCorrect(project[:project.index('_')],serial=project[project.index('_')+1:],correct=correct)
