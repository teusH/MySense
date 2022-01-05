#!/usr/bin/env python3
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
#
# Copyright (C) 2017, Behoud de Parel, Teus Hagen, the Netherlands
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

# $Id: MyGPS.py,v 1.11 2022/01/05 11:28:06 teus Exp teus $

__modulename__='$RCSfile: MyGPS.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.11 $"[11:-2]
import inspect
def WHERE(fie=False):
   global __modulename__, __version__
   if fie:
     try:
       return "%s V%s/%s" % (__modulename__ ,__version__,inspect.stack()[1][3])
     except: pass
   return "%s V%s" % (__modulename__ ,__version__)

import sys
if sys.version_info[0] >= 3: unicode = str
try: import pygeohash as geohash
except: import geohash              # used to get geohash encoder

# uses python geohash lib, try to correct lat/long swap
def convert2geohash(coordinates,precision=12, verbose=False):
    oord = coordinates
    if type(oord) is unicode: oord = str(oord)
    try:
      if type(oord) is str:
        oord = oord.split(',')[:2]
      oord = [ float(x) for x in oord[:2]]
      # geohash uses (lat, long). Correction action max/min only works in Nld
      return '%s' % geohash.encode(max(float(oord[0]),float(oord[1])), min(float(oord[0]),float(oord[1])), precision)
    except:
      raise ValueError("location coordinates error with %s" % str(coordinates))

# returns (latitude,longitude) tuple from geohash string
def fromGeohash(geostr):
    return geohash.decode(geostr)

# from: https://pydoc.net/pygeohash/1.2.0/pygeohash.distances/
# Thanks to Will McGinnis
def GPS2Aproximate(geohash_1, geohash_2):
    """
    Returns the approximate great-circle distance between two geohashes in meters.
    :param geohash_1:
    :param geohash_2:
    """
    def checkBase32(item):
        if type(item) is unicode: item = str(item)
        if not type(item) is str:
            item = convert2geohash(item,precision=10)
        if not item.isalnum():
          raise ValueError("Geohash %s is not a valid geohash" % item)
        return item.lower()
 
    # find how many leading characters are matching
    matching = 0
    for g1, g2 in zip(checkBase32(geohash_1), checkBase32(geohash_2)):
        if g1 == g2: matching += 1
        else: break
    # we only have precision metrics up to 10 characters
    # the distance between geohashes based on matching characters, in meters.
    return [20000000,5003530,625441,123264,19545,3803,610,118,19,3.71,0.6][min(10,matching)]
 
 
# returns distance in meters between two GPS coodinates
# hypothetical sphere radius 6372795 meter
# courtesy of TinyGPS and Maarten Lamers, using Haversine
# should return 208 meter 5 decimals is diff of 11 meter
# args (latitude,longitude) or geohash string
# GPSdistance((51.419563,6.14741{,21}),(51.420473,6.144795{,23.8}))
# GPSdistance('5a1cabcdf','lkabcdf')
def GPSdistance(geo_1, geo_2, aprox=False):
    """
    converts the geohashes to lat/lon
    and then calculates the haversine great circle distance in meters.
    """
    def checkBase32(item):
        if not type(item) is str: return ''
        if not item.isalnum():
          raise ValueError("Geohash %s is not a valid geohash" % item)
        return item.lower()

    if checkBase32(geo_1):
        if aprox: return GPS2Aproximate(geo_1, geo_2)
        lat_1, lon_1 = geohash.decode(geo_1)
    else:
        lat_1 = float(geo_1[0]); lon_1 = float(geo_1[1])
    if checkBase32(geo_2):
        if aprox: return GPS2Aproximate(geo_1, geo_2)
        lat_2, lon_2 = geohash.decode(geo_2)
    else:
        lat_2 = float(geo_2[0]); lon_2 = float(geo_2[1])

    R = 6371000
    import math
    phi_1 = math.radians(lat_1)
    phi_2 = math.radians(lat_2)
    delta_phi = math.radians(lat_2-lat_1)
    delta_lambda = math.radians(lon_2-lon_1)
    a = math.sin(delta_phi/2.0) * math.sin(delta_phi/2.0) + math.cos(phi_1) * math.cos(phi_2) * math.sin(delta_lambda/2) * math.sin(delta_lambda/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# zoom 18 gives moost details as eg street
# addressdetailks=1 gives 'address'
# example of json return value
# {
#   u'category': u'place',
#   u'addresstype': u'place',
#   u'type': u'house',
#   u'display_name': u'13, My Street, MyVillage, MyMunicipalitry, MyState, MyCountry, 1234AB, MyCountry',
#   u'display_name': u'MyVillage, MyMunicipality, MyState, MyCountry, 1234AB, MyCountry',
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
#      u'village': u'MyVillage',
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

# obtain aproximate address info from a GPS coordinate or geohash
# returns dict with human location info
def GPS2Address(place, city=None, verbose=False):
    # 51.419563,6.14741,20  LAT,LON,ALT style
    Rslt = {}
    if not city:
      if type(place) is unicode: place = str(place)
      if type(place) is str and place.find(',') > 0:
        oord = place.replace(' ','').split(',')[:2]
      elif type(place) is str:
        oord = geohash.decode(place.lower())
      else:
        oord = [place[0],place[1]]
      oord = [float(oord[0]),float(oord[1])]
      # correct ordinates swap
      oord = [max(oord),min(oord)] # only ok for Nld
      Rslt = {'longitude': str(oord[1]), 'latitude': str(oord[0]), 'altitude': float(0),
            'geohash': geohash.encode(oord[0],oord[1],10),
            # 'coordinates': "%.7f,%.7f,0.0" % (oord[1],oord[0]) # coodinates is deprecated
           }
      if not len(oord) == 2: return {}
      if not oord[0]: return {}
      # using GPS reverse from Nominatim OpenSteetmap.org
      get = 'reverse?format=jsonv2&addressdetails=1&zoom=18&lat=%.7f&lon=%.7f' % (oord[0],oord[1])
    else:
      # ref: https://nominatim.org/release-docs/develop/api/Search/
      # street=<street name>+<housenr> Nld style
      # city=<city>
      # country=<country>
      # postalcode=<postal code>
      # countrycode=<country code>
      # limit=<integer>
      # example:
      # 'https://nominatim.openstreetmap.org/search?
      #         q=deBide+2&city=gorst&format=json&addressdetails=1&limit=1&countrycode=N'
      # result:
      # [{"place_id":301644,
      #  "licence":"Data OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright",
      #  "osm_type":"node",
      #  "osm_id":2793717064,
      #  "boundingbox":["51.4206003","51.4203","6.1331","6.1331"],
      #  "lat":"51.4206503","lon":"6.135481",
      #  "display_name":"28, De Bisweide, Lovendaal, Grrst, Hoaas, Lirg, Nand, 59AZ, Nederland",
      #  "class":"place","type":"house","importance":0.411,
      #  "address":{"house_number":"8","road":"De Bie",
      #  "hamlet":"Lovendaal","village":"Grubbenvorst",
      #  "municipality":"Horst aan de Maas",
      #  "state":"Limburg","country":"Nederland",
      #   "postcode":"5971AZ","country_code":"nl"}}]
      get = 'search?q=%s,+%s&format=jsonv2&addressdetails=1&countrycode=NL&limit=1' % (place.replace(' ','+'),city.replace(' ','+'))
    url = 'https://nominatim.openstreetmap.org/'

    try:
        import requests
        if not verbose:
          import logging
          #logging.getLogger("requests").setLevel(logging.WARNING)
          logging.getLogger("urllib3").setLevel(logging.WARNING)
        response = requests.get(url+get,timeout=3.0)
        # If the response was successful, no Exception will be raised
        response.raise_for_status()
    except HTTPError as http_err:
        sys.stderr.write('HTTP error occurred: %s\n' % http_err)
        return {}
    except Exception as err:
        sys.stderr.write('Other error occurred: %s' % err)
        return {}
    try: response = response.json()
    except: return {}
    if not response: return {}
    if type(response) is list:
      response = response[0]
    for item in [(u'postcode','pcode'),(u'road','street'),(u'house_number','housenr'),(u'suburb','village'),(u'village','village'),(u'city','municipality'),(u'state','province'),(u'municipality','municipality')]:
        try:
            Rslt[item[1]] = str(response[u'address'][item[0]])
        except: pass
    if 'boundingbox' in response.keys():
      try:
        Rslt['latitude'] = "%.7f" % float(response['lat'])
        Rslt['longitude'] = "%.7f" % float(response['lon'])
        Rslt['geohash'] = convert2geohash([float(response['lat']),float(response['lon'])])
      except: pass
    # house number is lossy
    #try: Rslt['street'] += ' ' + str(response[u'address'][u'house_number'])
    #except: pass
    # correct some fields eg Noord-Brabant -> Brabant
    try: Rslt['province'] = Rslt['province'][Rslt['province'].index('-Brabant')+1:]
    except: pass

    return Rslt

def GeoQuery(address, verbose=False):
    addr = []
    # detect type of search string: ordinate string, geohash, pcode-NN or human
    try:
      if type(address) is list:
        addr = address[:4] # [nr, street, village {, municipality|province|country} ]
      elif type(address) is dict:
        addr = []
        for item in ['nr','street','village','municipality']:
          try:
            if strip(address[item]): addr.append(strip(address[item]))
            # if item is 'street': add[len(addr)-1] += ' ' + address['nr']
          except: pass
      if addr:
        addr = ','.join(addr) + ', Netherlands' # only NL
      else: addr = address
    except: return {}
    if addr.find(',') < 0: # ordinates or geohash?
      if not (len(addr) == 6 and addr[:4].isdigit() and addr[4:6].isalpha()):
        # not <pcode>-<nr> eg 1234AB-28 Nld postcode type
        return GPS2Address(address, verbose=verbose)
    if ''.join([x.strip().replace('.','') for x in addr.split(',')]).isdigit():
      # ordinates
      return GPS2Address(addr, verbose=verbose)

    Rslt = {}
    try:
      from geopy.geocoders import Nominatim # fair use OpenStreetMap licensing: ODbl 1.0 osm.org
      from geopy.exc import GeocoderTimedOut
      geolocator = Nominatim(user_agent="MySense")
      location = None
      for timeout in [7,14,21]:
         try:
            location = geolocator.geocode(addr,timeout=timeout).raw
            if location: break
         except GeocoderTimedOut: pass
         except: break
      if not location: return None  # Nominatim connect failure
      # e.g. location = {
      #        u'osm_type': u'node', u'type': u'house', u'class': u'place'
      #    ->  u'display_name': u'3, Vletweg, Blanhoek, Opo, Sint Pieter, Nord-Babant, Nepland, 5845AS, Nederland',
      #    ->  u'lon': u'5.0208753', u'lat': u'51.44077',
      #        u'boundingbox': [u'51.4696007', u'51.4760907', u'5.0187553', u'5.0287553'],
      #        u'importance': 0.331, u'place_id': 34941378,
      #        u'licence': u'Data \xa9 OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright', u'osm_id': 2861701124,
      #       }
      if verbose:
        sys.stderr.write("Request Nominatum address: '%s'\n" % str(addr))
        try:
          sys.stderr.write("Got address: '%s (lon%s,lat %s)'\n" % (str(location['display_name']),str(location['lon']),str(location['lat'])))
        except: pass
      addr = location[u'display_name'].replace(', ',',').split(',')
      if len(addr) == 6: addr = [None,None,None] + addr  # no NR and street
      # [u'nr', u'street', u'District', u'village', u'municipality', u'province', u'country', u'pcode', u'country']
      for item in [(0,'housenr'),(1,'street'),(3,'village'),(4,'municipality'),(5,'province'),(7,'pcode')]:
        try:
          if not addr[item[0]]: continue
          Rslt[item[1]] = addr[item[0]]
          # if item[0] == 1: Rslt[item[1]] += ' %s' % addr[0] # add house nr to street field
        except: pass
      Rslt['longitude'] = "%.7f" % float(location[u'lon'])
      Rslt['latitude'] = "%.7f" % float(location[u'lat'])
      Rslt['altitude'] = "%.1f" % float(0)
      Rslt['geohash'] = geohash.encode(float(location[u'lat']),float(location[u'lon']),9)
      # coordinates is deprecated
      #Rslt['coordinates'] = "%.7f,%.7f,0" % (float(str(location[u'lon'])),float(str(location[u'lat'])))
      # correct some fields eg Noord-Brabant -> Brabant
      Rslt['province'] = Rslt['province'][Rslt['province'].index('-Brabant')+1:]
    except: pass
    return Rslt

# test examples
# {'province': u'Nederland', 'municipality': u'Limburg', 'longitude': u'6.135481', 'street': u'Lovendaal', 'village': u'Horst aan de Maas', 'latitude': u'51.4206503'

# list measurement kits with their distance in area (in meters) around project/serial 
# args: list of kit identifiers, first arg may be a coordinate
def FindNeighbours(kits, area=5000, db=None, verbose=False, correct=False):
    def takeSecond(item):
        return item[2]
    def fix(item):
        try:
          coord = item.split(',')
          if float(coord[0]) < float(coord[1]):
            return True, ','.join([coord[1],coord[0]]) if len(coord) == 2 else ','.join([coord[1],coord[0], coord[2]])
        except: pass
        return False, item
    if not db: raise ValueError("Database object not defined.")

    neighbours = [] # list of list with tuple (project,serial,active) and coord 
    for kit in kits:
        if kit.find('_') > 0:
          project = kit[:kit.find('_')]; serial = kit[kit.find('_')+1:] 
          adding =  db.db_query("SELECT UNIX_TIMESTAMP(id), coordinates, project, serial, active FROM Sensors WHERE active AND project like '%s' AND serial like '%s' order by project, serial, active DESC" % (project,serial), True)
        elif kit[:2] in ['NL','DW']: # only active stations (last=NULL)
            adding =  db.db_query("SELECT UNIX_TIMESTAMP(first), REPLACE(REPLACE(geolocation,'N ',','),'E',''), organisation, id, if( ISNULL(last), 1, 0) FROM stations WHERE id like '%s' AND NOT ISNULL(geolocation) AND ISNULL(last)" % kit, True)
        elif not len(neighbours) and (kit.find(',') or kit.isalnum()):
            neighbours.append([('unknown','none',None),kit])
            continue
        else:
            sys.stderr.write("Skip %s, could be a national station" % kit)
            continue
        if verbose: sys.stderr.write("Found %d measurement kits to add.\n" % len(adding))
        for item in adding:
            if not len(item): continue
            item = list(item)
            cor, item[1] = fix(str(item[1]))
            neighbours.append([(item[2],item[3],item[4]),item[1]])
            if correct and cor:
                if verbose: sys.stderr.write("Corrected geo coordinate for %s\n" % kit)
                db.db_query("UPDATE Sensors set coordinates = '%s' WHERE UNIX_TIMESTAMP(id) = %s AND serial = '%s' AND project = '%s'" % (item[1], item[0], serial, project), False)
    if len(neighbours) < 1:
        sys.stderr.write("No kits found.\n")
        return False
    neighbours[0].append(0) # center of area
    for nr in range(len(neighbours)-1,0,-1):
       if neighbours[nr][0][0] == neighbours[nr-1][0][0] and neighbours[nr-1][0][1] == neighbours[nr][0][1]:
           del neighbours[nr]; continue
       dist = GPSdistance(neighbours[0][1].split(','),neighbours[nr][1].split(','), aprox=aproximate)
       if dist > area and verbose:
         sys.stdout.write("Kit project %s, serial %s distance to project %s, serial %s: %.2 meters. Skipped.\n" % (neighbours[0][0][0],neighbours[0][0][1],neighbours[0][nr][0],neighbours[0][nr][1],dist))
         del neighbours[nr]; continue
       neighbours[nr].append(dist)
    neighbours.sort(key=takeSecond)
    return neighbours
       
# correct meta location/address info in database against geo info from Nominatim
# Nominatim: try first with street house nr, village if not try with ordinate/geohash
# correct argument 0: no correction, 1: correct, 2: correct only via interaction request
# to do: interact with possibility to enter better info
import re
def AddressCorrect(project, serial='%', correct=1, date='', db=None, verbose=False):
    if not db: raise ValueError("Database object not defined.")
    def abbreviate(strg): # make usual changes in names similar
        strg = str(strg).lower()
        # make the comparison lossy
        for one in [(r'str(aat|\.)','str'),(r'a(an |/)de* ','ad '),(r'van de','vd'),(r'-[0-9a-z]{0,4}$',''),(r's(in)*t ','st. '),(r'burg[emdtr]* ','burg. '),(r'past[or]* ','past. ')]:
            strg = re.sub(one[0],one[1],strg)
        return strg
    # interact
    def GetAnswer(question): # interact for a change
        try: line = raw_input("Changes to be made in DB ([y]/n) update to \033[32m%s\033[0m? " % question)
        except: line = input("Changes to be made in DB ([y]/n) update to \033[32m%s\033[0m? " % question)
        line = line.strip()
        if not line or (line.lower()[0] == 'y'): return True
        return False

    address = ['NULL','NULL','NULL','street','housenr','village','municipality','province','pcode']
    for loc in db.db_query("DESCRIBE Sensors", True): # if available
        if loc[0] == 'geohash': address[0] = 'geohash'
        elif loc[0] == 'coordinates':
            address[1] = "SUBSTRING_INDEX(coordinates,',',1)"   # longitude
            address[2] = "SUBSTRING_INDEX(SUBSTRING_INDEX(coordinates,',',2),',',-1)"  # latitude
    if address[0] == 'NULL' and address[1] != 'NULL':
        address[0] = "ST_GeoHash(SUBSTRING_INDEX(coordinates,',',1),SUBSTRING_INDEX(SUBSTRING_INDEX(coordinates,',',2),',',-1),12)"
    kits = db.db_query("SELECT UNIX_TIMESTAMP(id), project, serial, %s FROM Sensors WHERE %s active AND project like '%s' AND serial like '%s'" % (','.join(address),date,project,serial), True)
    address[:3] = ['geohash','longitude','latitude']
    if not len(kits):
        sys.stderr.write("Kit home location for project %s are not defined.\n" % project)
        return False
    for kit in kits:
        result = False
        kit = list(kit) # convert tuple to list
        if len(kit[3:]) != len(address):
            sys.stderr.write("Unable to extract enough column values in project %s for %s." % (kit[2],', '.join(address)))
            continue
        if kit[6] and kit[8]: # 6: street, 7: house nr, 8: village
          # street,house nr,village takes precedence for ordinates and address search
          result =  GPS2Address(kit[6]+' '+kit[7],city=kit[8],verbose=verbose)
        if not result:  # try to get address info via ordinates, a reverse search
          # 3: geohash, 4: latitude, 5: longitude
          if kit[2]: result = GPS2Address([float(kit[4]),float(kit[5])], verbose=verbose) # coordinates column takes precedence
          elif kit[1]: result = GPS2Address(kit[1], verbose=verbose) # geohash
        if verbose or correct > 1:
            sys.stderr.write("Project %s, serial %s: \n" % (kit[1],kit[2]))
            if not result:
              sys.stderr.write("   No geo info found.\n")
            else: sys.stderr.write("  %-13.12s: %20.19s | %-20.19s\n" % ('item','database','openstreet map'))
        if not result: continue
        qry = []
        for item in sorted(result.keys(),reverse=True):
            if not item in address: continue
            try:
              if verbose or correct > 1:
                sys.stderr.write("  %-13.12s: %20.19s " % (item,str(kit[3+address.index(item)])) )
                sys.stderr.write("| %-20.19s" % str(result[item]))
              if item in ['latitude','longitude']:
                if verbose or correct > 1: sys.stderr.write("\n")
                continue
              if item == 'pcode': # sometimes it is as '1234 AB' or as '1234AB'
                kit[3+address.index(item)] = str(kit[3+address.index(item)]).replace(' ','')
              # street house number from reverse GPS is lossy
              differ = False
              if item == 'geohash':
                if GPS2Aproximate(kit[3],result['geohash']) > 118: # > 118 meters
                  differ = True
              elif abbreviate(kit[3+address.index(item)]) != abbreviate(result[item]):
                differ = True
              if verbose or correct > 1:
                if differ: sys.stderr.write(" \033[31mDIFFER\033[0m\n")
                else: sys.stderr.write(" \033[1mSAME\033[0m\n")
              if differ:
                if correct:
                  if correct < 2:
                    qry.append("%s = '%s'" % (item,str(result[item])) )
                  elif GetAnswer(str(result[item])):
                    qry.append("%s = '%s'" % (item,str(result[item])) )
            except: pass
        if not qry: continue
        if verbose:
            sys.stderr.write("Correcting entry ID %s, project %s, SN %s" % (datetime.datetime.fromtimestamp(kit[0]).strftime("%Y-%m-%d %H:%M"),kit[2],kit[3]))
        if not qry:
            if verbose: sys.stderr.write(": No correction\n")
            continue
        if verbose:
            sys.stderr.write(" with: %s\n" % ', '.join(qry))
        try:
            db.db_query("UPDATE Sensors SET %s WHERE UNIX_TIMESTAMP(id) = %d" % (','.join(qry),kit[0]),False)
        except Exception as e:
            sys.stderr.write("Error while updating Sensors id = %s, values: %s, exception: %s\n" % (kit[0],','.join(qry),str(e)))
    return True

if __name__ == '__main__':
    help = """
   Command: python %s [arg] ...
   --help    | -h       This message
   --verbose | -v       Be more verbose (std err channel)
   --correct | -c       Correct address in Sensors table
   --date S  | -d S     Correct address only from date S (seconds from POSIX timestamp) 
   --distance           Calculates and list distances from arg1 to arg2
   --neighbour          Calculates distance to neighbours from arg1 to arg2, ... argN
   --aproximate | -a    Use in distance calculation geohash aproximates
   --area=2000          Max circel area for distance calculations, dflt 2000 meter
   --lookup  | -l       Lookup location information for a home location
                        Location may be 'street nr, village', ordinates, geohash
   
   Correct address (street, municipality, province, postcode) using reverse lookup
   of GPS coordinates from table Sensors of MySQL database luchtmetingen.
   DB credentials are taken from environment.
   Examples (wildcard in names is '%%'):
   arg: 'SAN' correct address from coordinates of measurement kits for project SAN
   arg: 'SAN_%%123' correct address for kits project SAN with serial ending like %%123
   arg: '%%N'  correct address from coordinates of measurement kits for project names ending 'N'
   On distance calculation first arg is center. First ar may be a coordinate or geohash.
""" % __modulename__
    # importing the requests library 
    import requests 
    from requests.exceptions import HTTPError
    import datetime
    
    verbose = False    # be more versatile
    lookup = False     # search home location details
    correct = 0        # make correction / update MySQL table Sensor with address items
    date    = ''       # select measurement kit emta with datum from up to now, dflt all
    distance = False   # calculate distances between list of measurement kits
    neighbour = False  # calculate distance between 2 GPS locations
    aproximate = False # use geohash aproximates in distance calculations
    area = 5000        # area is 5 km
 
    argv = []
    for i in range(1,len(sys.argv)):
        if sys.argv[i] in ['--help', '-h']:      # help, how to use CLI
            print(help); exit(0)
        elif sys.argv[i] in ['--verbose', '-v']: # be more verbose
            verbose = True
        elif sys.argv[i] in ['--correct', '-c']: # correct address in Sensors table
            correct = 1
        elif sys.argv[i] in ['--interact', '-i']: # correct address interactively
            correct = 2
        elif sys.argv[i] in ['--lookup', '-l']:  # search home location info
            lookup = True
        elif sys.argv[i] in ['--date', '-d']:    # correct address in Sensors table
            date = int(sys.argv[i+1]); i += 1
            if not date:
                print(help); exit(1)
            date = 'datum >= FROM_UNIXTIME(%d) AND ' % date
        elif sys.argv[i] in ['--neighbour']:      # calculate distances
            neighbour = True
        elif sys.argv[i] in ['--distance']:      # calculate distances
            distance = True
        elif sys.argv[i] in ['--aproximate','-a']: # use geohash aproximation
            aproximate = True; neighbour = True
        elif sys.argv[i][:7] in ['--area=']:  # limit to area in meters
            neighbour = True
            if sys.argv[i][8:].isdigit():
              area = int(sys.argv[i][8:])
        else: argv.append(sys.argv[i])
    if not verbose:
        import logging
        #logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    if lookup:
      if not argv: # just a small geo query test run
        print("Lookup test:")
        argv = [
          'de Bisweide 14, Grubbenvorst',
          '6.134581, 51.4026503, 21.3',
          'u1hek8gdz']
      for one in argv:
        print("Geo query home location for '%s'" % one)
        for item in sorted(GeoQuery(one).items()):
          print("\t%12.12s:\t%s" % item)
      exit(0)

    import MyDB as DB
    DB.Conf['output'] = True
    DB.Conf['hostname'] = 'localhost'         # host InFlux server
    DB.Conf['database'] = 'luchtmetingen'     # the MySql db for test usage, must exists
    DB.Conf['user'] = 'IoS'                   # user with insert permission of InFlux DB
    DB.Conf['password'] = None                # DB credential secret to use InFlux DB
    if not verbose: DB.Conf['level'] = 'WARNING' # log level less verbose
    import os
    for credit in ['hostname','user','password','database']:
      try:
        DB.Conf[credit] = os.getenv('DB'+(credit[0:4].upper() if credit != 'database' else ''),DB.Conf[credit])
      except:
        pass

  
    if not neighbour and not distance:
      # get addresses for some kits
      for project in argv:
        if not DB.Conf['password']:
          print('Database credentials eg password missing. Exiting.')
          exit(1)
        if project.find('_') < 0:
            AddressCorrect(project, db=DB, correct=correct, date=date, verbose=verbose)
        else:
            AddressCorrect(project[:project.index('_')],serial=project[project.index('_')+1:],correct=correct, db=DB, date=date, verbose=verbose)

    elif distance:
       dist = GPSdistance(argv[0],argv[1])
       sys.stderr.write("Distance from %s to %s: %.2f\n" % (argv[0],argv[1],dist))
    elif neighbour: # neighbour  distances calculations for a list of kits.
       # First (may be a coordinate, or geohash) is center
       for kit in FindNeighbours(argv, area=area, db=DB, verbose=verbose, correct=correct):
          sys.stderr.write("Kit project %s, serial %s (%s) is on distance %.1f\n" % (kit[0][0],kit[0][1], str(kit[1]), kit[2]))
    DB.Conf['STOP']()
    # just a hack to exit also with blocked threads
    import os
    import signal
    import platform
    # get the current PID for safe terminate server if needed:
    PID = os.getpid()
    if platform.system() != 'Windows':
        os.killpg(os.getpgid(PID), signal.SIGKILL)
    else:
        os.kill(PID, signal.SIGTERM)
    # for one in __threads__: stop(one) and join(one)
    exit(status)

