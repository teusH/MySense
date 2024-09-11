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
# Copyright (C) 2024, Behoud de Parel, Teus Hagen, the Netherlands
#
"""
Python3.8+ script to generate overview in XLSX of measurements taken by low-cost stations
in various municipalitiea (one municipality per XLSX sheet) in a certain period of time.
Data is obtained via SamenMetenThings tools module from RIVM Samen Meten API.
Script command line: python3 script [Period=one year ago,now] municipality_name ...
"""
import re
import sys,os
from collections import OrderedDict
import datetime

import SamenMetenThings as RIVM

__version__ = os.path.basename(__file__) + " V" + "$Revision: 1.2 $"[-5:-2]
__license__ = 'Open Source Initiative RPL-1.5'
__author__  = 'Teus Hagen'

# class defaults
Period = ',now'                              # period of interest, comma separated
# calibrated example: pm25_kal, pm10_kal
Sensors = '(pm25|pm10|temp|rh|pres|nh3|no2)' # sensor types (ordered) of interest, reg exp
Select  = None                               # don't filter station names (dflt None) else Reg Exp.
Verbosity = 0                                # level of verbosity for Things
Expand  = 'location,address,owner,project'   # extra info of stations from Things
# By = 'owner,project'
DEBUG   = False                              # debug modus, do not use SamenMetenThings class

# progress metering, teatime music
def progress(Name,func,*args,**kwargs):
    from threading import Thread
    thread = Thread(target=func, args=args, kwargs=kwargs)
    #thread.setDeamon(True)   # P 3.10+: thread.deamon(True)
    thread.start()
    teaTime = time()
    while thread.is_alive():
        secs = time()-teaTime; mins = int(secs/60); secs = secs-(mins*60)
        mins = f"{mins}s" if mins else ''
        sys.stderr.write(f'Busy downloading for {Name}: {mins}{secs:.1f}s\r')
        sleep(0.1)
    thread.join()
    sys.stderr.write(f'Download {Name} done in {mins.replace("m"," minutes ")}{int(secs)} seconds' + ' '*40 + '\n')

import xlsxwriter
Workbook = None                              # XLSX workbook handle
def n2a(n:int) -> str:                       # convert column number to xlsx column name
    d, m = divmod(n,26) # 26 is the number of ASCII letters
    return '' if n < 0 else n2a(d-1)+chr(m+65) # chr(65) = 'A'

# XLSX matrix columns, sheet has name municipality
# name     GPS ...   properties ...                 sensors (name, first, last, count)
# station, location, [address,] [owner,] [project,] [sensor-i, first, last, count] ,...
def Add_Stations( Municipality:str, Things=None, Period=Period) -> bool:
    global Sensors, Select, Expand, Workbook, Verbosity
    if Things is None:
        Things = RIVM.SamenMetenThings(Sensors=Sensors,Verbosity=0,Threading=True)
        if Verbosity > 2: Things.Verbose = Verbosity
    if Period:
        period = [x.strip() for x in Period.strip().split(',')]
        Start = period[0]
        if len(period) > 1: End = period[1]
        else: End = None
    else: Start = End = None
    # may expand properties: e.g. gemcode (984), knmicode (knmi_06391), pm25regiocode (NL10131), etc.
    if DEBUG:
        stations = {
    'OHN_gm-2136': {'owner': 'Ohnics', 'project': 'Grenzeloos Meten', 'location': [(5.933, 51.474),'Veer 1, Blit, gem. Ven, prov. Lbg'], 'sensors': {'temp': None, 'pm25_kal': {'@iot.id': 42884}, 'pm25': {'@iot.id': 42883, 'first': '2023-10-05T08:00:00.000Z', 'count': 7968, 'last': '2024-09-08T14:00:00.000Z'}}},
    'OHN_gm-2116': {'owner': 'Ohnics', 'project': 'Grenzeloos Meten', 'location': [(5.938, 51.503)], 'sensors': {'temp': None, 'pm10': {'@iot.id': 42860}, 'pm25': {'@iot.id': 42859}}}
    }
    else:
        stations = Things.get_MunicipalityStations(Municipality, Select=Select, By=Expand, Status=True, Start=Start, End=End)
    if End is None:
        End = datetime.datetime.now(datetime.timezone.utc)
    else:
        End = datetime.datetime.strptime(RIVM.ISOtimestamp(End),'%Y-%m-%dT%H:%M%z')
    if not type(stations) is dict and not len(stations):
        sys.stderr.write(f"Unable to find stations in municipality {Municipality}\n")
        return False
    if Verbosity > 0:
        sys.stderr.write(f"Found {len(stations)} in municipality {Municipality}\n")
    # Address=True, Start=None, End=None, Select=Sensors, By='address,id'
    #{ 'OHN_gm-2161: {   'location': [(6.126, 51.524), 'Veer 1, Blit, gem. Ven, prov. Lbg'],
    #                    '@iot.id': 12345, 'owner': 'XYS', 'project': 'XYZ',
    #                    'sensors': { 'temp': None,
    #                                 'pm25_kal': {   '@iot.id': 42932,
    #                                                 'first': '2023-10-05T08:00:00.000Z',
    #                                                 'count': 7968,
    #                                                 'last': '2024-09-08T14:00:00.000Z'},
    #                                 ...  }}, ... } 

    Sensors = re.sub(r'[\(\)\s]','',Sensors).split('|') # ordered list of sensor names 
    expand = set(Expand.split(',')) - set(['location','address'])
    location = []
    for _ in ['location','address']:
        if Expand.find(_) >= 0: location.append(_)

    # spreadsheet
    hrd_bold = Workbook.add_format(
        { 'bold': True, 'align': 'center',
          'left': True, 'right': True, 'left_color': 'white', 'right_color': 'white',
          'valign': 'vcenter','fg_color': '#d4d2d2',})
    hrd_italic = Workbook.add_format(
        { 'italic': True, 'align': 'center', 'valign': 'vcenter',
          'left': True, 'right': True, 'left_color': 'white', 'right_color': 'white',
          'fg_color': '#d4d2d2',})
    gray_format = Workbook.add_format({'fg_color': '#d9d8d8'})
    date_format = Workbook.add_format({'num_format': 'yyyy-mm-dd'})
    orange_date_format =  Workbook.add_format({'num_format': 'yyyy-mm-dd', 'fg_color': '#ffcf90'})
    orange_format = Workbook.add_format({'fg_color': '#ffcf90'})
    gray_date_format = Workbook.add_format({'num_format': 'yyyy-mm-dd', 'fg_color': '#d9d8d8'})

    column = dict(); width = list(); row = -1; nr = -1; inactives = 0
    worksheet = Workbook.add_worksheet(name=Municipality)
    # leave first 2 row blank for content info as nr of (in)active station in last part of period
    row += 2

    # header row, row+1
    row += 1; nr += 1
    worksheet.write_string(row,nr,'station',hrd_bold)
    worksheet.write_string(row+1,nr,'Things ID',hrd_italic); width.append(12)
    if len(location) > 1:
        nr += 1
        worksheet.merge_range(row,nr,row,nr+1,'location',hrd_bold)
        worksheet.write_string(row+1,nr,"GPS",hrd_italic)
        width.append(0); column['location'] = 1
        nr += 1
        worksheet.write_string(row+1,nr,"address",hrd_italic)
        width.append(0); column['address'] = 2
    elif len(location):
        nr += 1
        worksheet.write_string(row,nr,location[0],hrd_bold)
        worksheet.write_string(row+1,nr,'',hrd_bold)
        width.append(0); column[location[0]] = 1
    for name in list(expand):
        nr += 1
        worksheet.write_string(row,nr,name,hrd_bold)
        worksheet.write_string(row+1,nr,'property',hrd_italic)
        column[name] = nr; width.append(0)
    humanise = RIVM.HumaniseClass(utf8=True)
    for name in Sensors:
        nr += 1
        worksheet.merge_range(row,nr,row,nr+2,humanise.HumaniseSensor(name),hrd_bold)
        worksheet.write_string(row+1,nr,'first',hrd_italic); width.append(0)
        worksheet.write_string(row+1,nr+1,'last',hrd_italic); width.append(0)
        worksheet.write_string(row+1,nr+2,'count',hrd_italic); width.append(0)
        column[name] = nr; nr += 2
    row += 2

                                        # station info rows
    active = []
    for station,info in stations.items():
        row += 1
        operational = False

        if column.get('address') or column.get('location'):
          if info.get('location') and len(info['location']):
            if col := column.get('address'):
               if len(info['location']) > 1 :
                 address = re.sub(r',\s*(gem|prov)\.\s.*','',info['location'][1])
               else: address = ''
               worksheet.write_string(row,col,address, gray_format)
               width[col] = max(len(address)+2,width[col])
            if col := column.get('location'):
               location = str(info['location'][0])
               worksheet.write_string(row,col,location,gray_format)
               width[col] = max(len(location)+2,width[col])

        for n in expand:                # owner, project, knmicode, etc.
            if n == 'location' or n == 'address': continue
            if not (item := info.get(n)): continue
            if not (col := column.get(n)): continue
            worksheet.write_string(row,col,str(item))
            width[col] = max(len(str(item))+2,width[col])

        if info.get('sensors'):
            gray = False
            for s,v in info.get('sensors').items():
                if type(info['sensors'][s]) is dict and info['sensors'][s].get('@iot.id'):
                  if (col := column.get(s)):
                    gray = not gray
                    if (first := info['sensors'][s].get('first',None)):
                        first = datetime.datetime.strptime(first,"%Y-%m-%dT%H:%M:%S.%f%z")
                        worksheet.write_datetime(row,col,first,gray_date_format if gray else date_format)
                        width[col] = max(12,width[col])
                    if (last := info['sensors'][s].get('last',None)):
                        last = datetime.datetime.strptime(last,"%Y-%m-%dT%H:%M:%S.%f%z")
                        if (End - last).days >= 1:   # at least till one day before end period
                            operational = True
                            worksheet.write_datetime(row,col+1,last,gray_date_format if gray else date_format)
                        else:
                            worksheet.write_datetime(row,col+1,last,orange_date_format)
                        width[col+1] = max(12,width[col+1])
                    if (count := info['sensors'][s].get('count',None)):
                        if gray: worksheet.write_number(row,col+2,count, gray_format)
                        else: worksheet.write_number(row,col+2,count)
                        width[col+2] = max(7,width[col+2])

        if not operational:
            worksheet.write_string(row,0,station,orange_format)
            # worksheet.set_row(row, None, None, {'hidden':1})
            if Verbosity:
                sys.stderr.write(f"Station {station} ({Municipality}) was not operational in the period {Period}\n")
            inactives +=1
        else: worksheet.write_string(row,0,station)
        width[0] = max(len(station)+2,width[0])

    # sheet stations statistics info
    if Verbosity:
        sys.stderr.write(f"Stations in municipality {Municipality}: nr of stations: {len(stations)}, stations not active: {inactives}\n")
    worksheet.merge_range(0,0,0,10,f'municipality {Municipality} statistics: nr of stations: {len(stations)}, stations not active: {inactives}',hrd_bold)
    for i,w in enumerate(width):
        if w: worksheet.set_column(f"{n2a(i)}:{n2a(i)}",w)
        else: worksheet.set_column(f"{n2a(i)}:{n2a(i)}", None, None, {'hidden': 1})
    if row > 1: return True
    else: return False

#                                =================================== main
XLSXfile = 'MunicipalityStations.xlsx'
def help() -> None:
    sys.stderr.write(
        f"""
Generate overview of low cost stations in municipalities (xlsx sheet per municipality)
with measurements info:
    location (GPS, address),
    station properties (owner,project, municipality code, ref codes), and
    sensors installed (sensor type, first-last record timestamp, record count) in a period.

Command: {os.path.basename(__file__)} [options] help or municipality, ...

Output as XLSX formatted file (default: {XLSXfile}). Use File='Yours.xlsx' to change this.

Options station info settings:
        Period='2021-01-31,2021-02-31 23:59'  Defines period of observations. Default: all.
        Period='one year ago,now'             Defines last year.
        Sensors='{Sensors}'                   Defines sensor types of interest (regular expression).
        Select='{Select if Select else 'None'}' Filter on station names. Default: do not filter.
        Expand='{Expand}'                     List of station properties of interest.
Options XLSX book property settings:
        File=Outputfile.xlsx                  Default '{XLSXfile}'.
        Company=YourCompanyName               Default empty.
        Status=BookStatus                     Default 'draft'.
Command options:
        Verbosity={Verbosity}                 Verbosity level. Level 5 gives timings info.
        DEBUG={'True' if DEBUG else 'False'}  In debig modus: Things queries will not be done.
        """)

municipalities = []; company = ''; status = 'draft'
for Municipality in sys.argv[1:]:
    if re.match(r'^(--)?help$',Municipality,re.I):
        help(); Workbook = None
        break
    if m := re.match(r'^(--)?([^\s]*)\s*(=)\s*([^\s]+.*)$', Municipality):
      if m.groups()[2] == '=':
        if m.groups()[1] == 'Period':           # only measurements in this period
            Period = ','.join([x.strip() for x in m.groups()[3].strip().split(',')])
        elif m.groups()[1] == 'Company':        # company of XLSX book creation
            company = m.groups()[3].strip()
        elif m.groups()[1] == 'Status':         # status of XLSX book
            status = m.groups()[3].strip()
        elif m.groups()[1] == 'File':           # file name of XLSX book
            XLSXfile = m.groups()[3].strip()
        elif m.groups()[1] == 'Sensors':        # sensor types of interest (reg exp)
            Sensors = m.groups()[3].strip()
        elif m.groups()[1] == 'Select':         # filter reg exp for stations names
            Select = m.groups()[3].strip()
        elif m.groups()[1] == 'Verbosity':      # verbosity level
            Verbosity = int(m.groups()[3].strip())
        elif m.groups()[1] == 'Expand':         # show station property info as well
            Expand = m.groups()[3].strip()
        elif m.groups()[1] == 'DEBUG':          # DEBUG use buildin station dict
            DEBUG = True if m.groups()[3].strip() == 'True' else False
        continue
    if Workbook is None:
        Workbook = xlsxwriter.Workbook(XLSXfile, {'remove_timezone': True})
        if Verbosity:
            sys.stderr.write(f"Creating XLSX book: '{XLSXfile}'\n")
            sys.stderr.write(f"""Add stations for municipality: '{Municipality}'
            Filter on sensor types: '{Sensors}'
            Filter station names: '{'all' if not Select else Select}'
            Show also these station properties: '{Expand}'\n""")
    # next can take quite some time. To Do: add progress meter?
    if Add_Stations( Municipality, Period=Period):
        municipalities.append(Municipality)
    else:
        sys.stderr.write(f"Municipality '{Municipality}': no stations in period '{Period}'\n") 

if Workbook:                                    # XLSX book creation
    import pwd
    user = re.sub(r'\s*,.*$','',pwd.getpwnam(os.environ["USER"]).pw_gecos)
    if user: user = f"{user} ({os.environ['USER']})"
    else: user = ''
    properties = {                              # XLSX book properties
        "title": "Air Quality measurements information from RIVM/Things",
        "subject": "Low-Cost stations in municipalities: " + ', '.join(municipalities),
        "author": user,
        "manager": "",
        "company": company,
        "category": "Air Quality measurements",
        "keywords": "Air Quality, sensors, Particular Matter, NOx, NH3",
        "comments": f"{__license__}.\nCreated by {os.path.basename(__file__)} with Python and XlsxWriter on {datetime.datetime.now().strftime('%-d %b %Y')}.",
        "status": status,
      }
    Workbook.set_properties(properties)
    Workbook.close()

    if Verbosity >= 0:
        sys.stderr.write(f"Created XLSX book: '{XLSXfile} with {len(municipalities)} municipalities (sheet(s))'\n")
    if Verbosity:
        sys.stderr.write(f"\tXLSX properties:\n")
        for p,v in properties.items():
            if v: sys.stderr.write(f"\t\t{p}:\t{v}\n")
