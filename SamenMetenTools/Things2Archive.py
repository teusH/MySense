# Open Source Initiative  https://opensource.org/licenses/RPL-1.5
#
#   Unless explicitly acquired and licensed from Licensor under another
#   license, the contents of this file are subject to the RECIPROCAL PUBLIC
#   LICENSE ("RPL") Version 1.5, or subsequent versions as allowed by the RPL,
#   and You may not copy or use this file in either source code or executable
#   form, except in compliance with the terms and conditions of the RPL.
#
#   All software distributed under the RPL is provided strictly on an "AS
#   IS" basis, WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESS OR IMPLIED, AND
#   LICENSOR HEREBY DISCLAIMS ALL SUCH WARRANTIES, INCLUDING WITHOUT
#   LIMITATION, ANY WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
#   PURPOSE, QUIET ENJOYMENT, OR NON-INFRINGEMENT. See the RPL for specific
#   language governing rights and limitations under the RPL.
#
# Copyright (C) 2024, Teus Hagen, the Netherlands
#
"""
Python3.8+ script to generate Samen Meten Things stations info of a period
into different formats: XLSX, CSV (sep ';', header columns dict keys),
JSON.
Archived data may be compressed in format defined in file extenstion.
Archived data is an overview air quality observation low-cost stations
in various municipalities or neighbouring stations or GPS ordinate
in a certain period of time from RIVM database.
Data origine is obtained via SamenMetenThings tools module from RIVM Samen Meten API.
Script command line: 'python3 script [Period=one year ago,now] name ...
Period name in human readable format is language dependant (command environment 'LANG').
Name may be a municipality name, low-cost station name or GPS ordinate.
If the name a file name with extension .csv, json with optionaly .gz compression
the file is used as data origin. If so the file name is used as region name.
Archived is station ID, GPS, optional address, owner, project, sensors (first seen,
last seen, count observations, sensor type and manufacturer, if defined), ...

Output name extension defines the format of the archive.

Command: scriptname [options] region (municipality, neighbours of station name or GPS) 
Command examples:
                 python3 scriptname Land\ van\ Cuijk Land\ van\ Cuijk.html
                 python3 scriptname Land\ van\ Cuijk.json.gz Land\ van\ Cuijk.html
or               python3 scriptname DEBUG ArchiveTest.json
or               python3 scriptname help

Command line options:
    Help                                        # get help information
    DEBUG=False                                 # use buildin test region
    Period=,now                                 # from YYYY-MM-DD hh:mm to end time
                                                # or period in human format, eg now
    Sensors='(pm25|pm10|temp|rh|pres|nh3|no2)'  # only these sensors
    Select='reg expression'                     # default all, filter on these station names
    Verbosity=0                                 # >3 include thread info progress
    Expand='location,address,owner,project'     # extra info
    User=$USER                                  # user name XSLX property
    Company=''                                  # company name XSLX property
    Bookstate=draft                             # state of archive file XSLX property
    Output='Regional_Stations'                  # default archive file name
    Hide=GPS,address,first,last,count,type      # default XLSX hidden columns XLSX
    Ext='json'                                  # default output format
"""
import re
import sys,os
from collections import OrderedDict
import datetime
import dateparser                      # check time period with Python dateparser
from dateutil import tz                # get timezone
from typing import Union,List          # if Python 3.8

import SamenMetenThings as RIVM

__version__ = os.path.basename(__file__) + " V" + "$Revision: 1.2 $"[-5:-2]
__license__ = 'Open Source Initiative RPL-1.5'
__author__  = 'Teus Hagen'

# globals which can be overwritten via command line: <name>='value', ....
DEBUG     = False                       # debug modus, do not use SamenMetenThings class

# defaults
Regions = dict()                        # regions in archive
Period = None                           # period of interest, comma separated
# To Do: may need to filter out unsupported sensors
Sensors   = '(pm25|pm10|temp|rh|pres|nh3|no2)' # sensor types of interest, reg exp
# calibrated example: pm25_kal, pm10_kal
Select    = None                        # filter station names (dflt None) else Reg Exp.
Verbosity = 0                           # level of verbosity for Things
Expand    = 'location,address,owner,project' # extra info of stations from Things
# By = 'owner,project'
Properties = dict()                     # archived properties
import pwd
Output = 'Regional_Stations'            # default archive file name
Hide='GPS,address,first,last,count,type' # default XLSX hidden XLSX columns
Company = ''                            # company name user XLSX property
Bookstate = 'draft'                     # book state archive XLSX property
Ext = 'json'                            # default output format

# progress metering, with teatime music: every station takes ca 30 seconds delay
def progress(Name,func,*args,**kwargs):
    from threading import Thread
    thread = Thread(target=func, args=args, kwargs=kwargs)
    #thread.setDeamon(True)              # P 3.10+: thread.deamon(True)
    thread.start()
    teaTime = time()
    while thread.is_alive():
        secs = time()-teaTime; mins = int(secs/60); secs = secs-(mins*60)
        mins = f"{mins}s" if mins else ''
        sys.stderr.write(f'Busy downloading for {Name}: {mins}{secs:.1f}s\r')
        sleep(0.1)
    thread.join()
    sys.stderr.write(f'Download {Name} done in {mins.replace("m"," minutes ")}{int(secs)} seconds' + ' '*40 + '\n')

# Pandas dataframe columns with indexes per row station (index Things ID):
#   [ { 'Things ID':str,
#       'GPS': [float,float],  #    'longitude':float, 'latitude':float,
#       'address':str, 'owner':str, 'project':str,
#       '<sensor-i> first':YYYY-MM-DDTHH:mm:ssZ, '<sensor-i> last:YYYY-MM-DDTHH:mm:ssZ,
#       '<sensor-i> count':int, '<sensor-i> product':str, ... },
#     { ... }, ... ]
#   stations:dict: required keys:
#         'Things ID', 'location':list[ordinates:list|tuple,address:str],
#   other dict keys are optional:
#           <sensor-i> name sensor with
#               optional dict[str] keys: 'first', 'last', 'count', '@iot.id', 'product'

# simplify Samen Meten Things stations info dict to
#     row of 1-dim dict[key:str,value:any] per station
# make it ready to convert to e.g. CSV or Pandas dataframe
def simplifySamenMetenStationsDict(Stations:dict) -> tuple:
    import re
    import pandas as pd
    import datetime
    # local time should be done with reg expression
    def datetime_str_to_datetime(yyyy_mm_dd_hh_mm: str, end=False) -> str:
        """datetime_str_to_datetime"""
        if not type(yyyy_mm_dd_hh_mm) is str: return yyyy_mm_dd_hh_mm
        if re.match(r'[0-9]{4}-[01][0-9]*-[0-3][0-9]$', yyyy_mm_dd_hh_mm):
            date = datetime_str_to_datetime(yyyy_mm_dd_hh_mm +('23:59:59' if end else '00:00:00'))
        elif re.match(r'[0-9]{4}-[01][0-9]*-[0-3][0-9]\s[0-2][0-9]:[0-5][0-9]$', yyyy_mm_dd_hh_mm):
            date = datetime_str_to_datetime(yyyy_mm_dd_hh_mm + (":59" if end else ":00"))
        else:
            date = yyyy_mm_dd_hh_mm
        return date

    def local_to_panda(local: str, end=False, tz=None) -> datetime:
        """local_to_panda"""
        date = pd.to_datetime(datetime_str_to_datetime(local, end=end)).tz_localize(tz='Europe/Amsterdam')
        if not tz:
            return  date
        else:
            return date.tz_convert(tz=tz)

    stations = list()
    for station, value in Stations.items():
        if not station or not value or not type(value) is dict: continue
        row = dict()
        for idx, idxVal in value.items():
            if not idx or not idxVal: continue
            if re.match(r'(sensors)$',idx,re.I):
                for idxS, idxSVal in idxVal.items():
                    if not type(idxSVal) is dict:
                        row[f'{idxS}'] = idxSVal
                        continue
                    for idxST, idxSTV in idxSVal.items():
                        if type(idxSTV) is str and re.match(r'20\d\d-\d\d-\d\d',idxSTV):
                            # convert to type pd._libs.tslibs.timestamps.Timestamp UTC
                            if re.match(r'20\d\d-\d\d-\d\d[T\s][\d:\.]*Z',idxSTV):
                                row[f'{idxS} {idxST}'] = pd.to_datetime(idxSTV)
                            else:
                                row[f'{idxS} {idxST}'] = local_to_panda(idxSTV, tz=datetime.timezone.utc)
                            #row[f'{idxS} {idxST}'] = datetime.datetime.strptime(first,"%Y-%m-%dT%H:%M:%S.%f%z")
                        else: row[f'{idxS} {idxST}'] = idxSTV
            elif re.match(r'(location)$',idx,re.I):
                if not idxVal or not type(idxVal) is list: continue
                try:              # GPS to grid of max 5 decimals (ca 1 meter)
                    row['GPS'] = [round(float(idxVal[0][0]),3),round(float(idxVal[0][1],3))]
                    #row['longitude'] = round(float(idxVal[0][0]),3)
                    #row['latitude'] = round(float(idxVal[0][1],3))
                except: continue
                if idxVal[1]: row['address'] = idxVal[1]
            else: row[idx] = str(idxVal)
        if row:
            row['Things ID'] = station
            stations.append(row)
    return stations

# ======================================= get regional stations info in CSV archive file
# https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html
# DataFrame.to_csv(path_or_buf=None, *, sep=',', na_rep='',
#    float_format=None, columns=None, header=True, index=True,
#    index_label=None, mode='w', encoding=None, compression='infer',
#    quoting=None, quotechar='"', lineterminator=None, chunksize=None,
#    date_format=None, doublequote=True, escapechar=None, decimal='.',
#    errors='strict', storage_options=None)

# generate Samen Meten Things stations info dict to CSV file
# timestamps in csv file are in local time
# to do: add extra header info as e.g. period, version, generation date
# mode append is not yet implemeted. Needs a keycheck and key ordering
def SamenMetenStations2CSV(Regions:Union[List[str],dict],Output:str='SamenMetenStationsInfo.csv.gz', Mode:str='w',dropIoTids:bool=True) -> None:
    stations = None
    if type(Regions) is dict: stations = Regions.copy()
    elif type(Regions) is list:
        stations = dict()
        for _ in Regions:
            if (_ := Get_Stations( _, Things=None, Period=Period)) and type(_) is dict:
                stations.update(_)
    # elif type(Regions) is str:   # get stations in dict format from archived file
    #     stations = GetFromArchive(Regions)
    else: return False
    if not stations: return False
    # simplify Stations info list to one dimensional list of dicts
    stations = simplifySamenMetenStationsDict(stations)
    import pandas as pd
    import datetime
    import re
    try:
        from tzlocal import get_localzone
        localTZ = str(get_localzone())
    except: localTZ = 'Europe/Amsterdam'
    stations = pd.DataFrame.from_dict(stations)
    stations.set_index('Things ID', drop=True, inplace=True) # indexed by station name
    stations.sort_index(ascending=False, inplace=True)
    # convert timestamp columns to local datetime strings
    iotColumns = list()
    for column in stations.keys():
        if dropIoTids and re.match(r'.*@iot.id$',column,re.I):
            iotColumns.append(column)
        elif re.match(r'.*\s(last|first)',column,re.I):  # pandas timestamp column
            #stations[column] = stations[column].tz_localize(tz=localTZ)
            stations[column] = stations[column].apply(lambda x: x.tz_convert(tz=localTZ))
            #for _ in range(0,len(stations[column])):
            #    stations[column][_] = stations[column][_].tz_convert(tz=localTZ)
    if iotColumns:      # remove columns stations and sensor with @iot.id Things ID:
        stations.drop(columns=iotColumns, inplace=True)
    stations.to_csv(Output, sep=';', date_format='%Y-%m-%d %H:%M', mode=Mode)
# SamenMetenStations2CSV(stations, Output='SamenMetenStationsInfo.csv.gz'))
# ================================= end routine stations to CSV archive

#                                        ===================== main
def help() -> None:
    sys.stderr.write(
        f"""
Generate overview of low cost stations in regions 
or comman separated list of low-cost stations (xlsx sheet per argument name).
Spreadsheet workbook (XLSX), CSV file (sep ';'), JSON file, or HTML Open Street Map file
with measurements info:
    location (GPS, address),
    station properties (owner,project, municipality code, ref codes), and
    sensors installed (sensor type, first-last record timestamp, record count) in a period.

Command: {os.path.basename(__file__)} [options] help or name, ...
Name is either municipality name or comma separated list of low-cost station names.

Output as formatted file (default: CSV sep ';'). Use File='Yours.xlsx' to change this.
        GPS is a list [longitude,latitude].
        Addresses are postal addresses (resolution is 100 meters)..
        Observations timestamps are in local time format.

Options station info settings:
        Period to obtain operational stations from Things.
        Period={Period}                       E.g. 'one year ago,now' Defines last year.
        Sensors='{Sensors}'                   Defines sensor types of interest (regular expression).
        Select='{Select if Select else 'None'}' Filter on station names. Default: do not filter.
        Expand='{Expand}'                     List of station properties of interest.
        `
        File='{Output}'                         Default 'Regional_Stations'. File extention:
        Ext='{Ext}'                             One of: xlsx,csv[.gz,tgz,gzip],json,html.
        Verbosity={Verbosity}                 Verbosity level. Level 5 gives timings info.
        DEBUG                                 In debug modus: Buildin data will be used.

Options for archive property settings:
        Company=YourCompanyName               Default empty.
        Status={Bookstate}                    Status archived data.
        User={os.environ['USER']}            Created by user name. Default: login name.
        XLSX Workbook sheets are per region (municipality, neighbourhood station or GPS).
        XLSX Hide={Hide}                      Hide these XLSX columns.
Command options:
        """)

for arg in sys.argv[1:]:
    if re.match(r'^(--)?help$',arg,re.I):
        help()
        exit(0)
    # collect command line options
    if m := re.match(r'^(--)?([^\s]*)\s*(=)\s*([^\s]+.*)$', arg):
      if m.groups()[2] == '=':
        if m.groups()[1]   == 'Period':    # only measurements in this period
            Period = ','.join([x.strip() for x in m.groups()[3].strip().split(',')])
        elif m.groups()[1] == 'Company':   # company of XLSX book creation
            Company = m.groups()[3].strip()
        elif m.groups()[1] == 'User':      # user of XLSX book creation
            User = m.groups()[3].strip()
        elif m.groups()[1] == 'Status':    # status of XLSX spreadsheet book
            Bookstate = m.groups()[3].strip()
        elif m.groups()[1] == 'File':      # file name of XLSX spreadsheet book
            Output = m.groups()[3].strip()
        elif m.groups()[1] == 'Sensors':   # sensor types of interest (reg exp)
            Sensors = m.groups()[3].strip()
        elif m.groups()[1] == 'Select':    # filter reg exp for stations names
            Select = m.groups()[3].strip()
        elif m.groups()[1] == 'Hide':      # hide these XLSX columns
            Hide = m.groups()[3].strip()
        elif m.groups()[1] == 'Verbosity': # verbosity level
            Verbosity = int(m.groups()[3].strip())
        elif m.groups()[1] == 'Expand':    # show station property info as well
            Expand = m.groups()[3].strip()
        elif m.groups()[1] == 'Ext':       # use Ext as archive format
            Ext = re.sub('^.','',m.groups()[3].strip().lower())
            if not re.match(r'(xlsx|(csv(.gz|.tgz|.gzip)|json)?)$',Ext):
                sys.stderr,write(f"Output file extention '{m.groups()[0]}' is not supported\n")
                exit(1)
        continue
    if re.match(r'^(--)?debug$',arg,re.I): # DEBUG use buildin station dict
        DEBUG = True; Verbosity = 1
        Output = 'RegionName-TEST'
        continue
    # collect region names
    Regions.append(arg)

if not len(Regions):
    sys.stderr.write("No regions defined. Exiting\n")
    exit(1)
if Output == 'Regional_Stations' and len(regions) < 2: # get region name as file name
    Output = regions[0]
Success = None
Properties = {                             # archived file properties
            "title": "Air Quality measurements information from RIVM/Things",
            "subject": "Low-Cost stations in regions: " + ', '.join(regions),
            "author": User,
            "manager": "",
            "company": Company,
            "category": "Air Quality measurements",
            "keywords": "Air Quality, sensors, Particular Matter, NOx, NH3",
            "comments": f"{__license__}.\nCreated by {os.path.basename(__file__)} with Python on {datetime.datetime.now().strftime('%-d %b %Y')}.",
            "status": Bookstate,
          }
if re.Match(r'xlsx$', Ext):                # generate XLSX spreadsheet workbook
    Success = GenerateXLSX(Regions, Output=Output+'.'+Ext, Properties=Properties)
elif re.Match(r'csv', Ext, re.I):          # generate CSV archive of regional stations
    Success =  SamenMetenStations2CSV(Regions, Output+'.'+Ext, Mode='w',dropIoTids=True)

if not Verbosity: exit(0 if Success else 1)
if not Success:
    if Success is None:
        sys.stderr.write("No regional low-cost stations found.\n")
    else: sys.stderr.write("Failed\n")
    exit(1)
if Verbosity:
    sys.stderr.write(f"Generated archive file: '{Output+'.'+Ext}'\n")
    for key, value in Properties.items():
        sys.stderr.write(f"{key}\t{value}\n")

    
