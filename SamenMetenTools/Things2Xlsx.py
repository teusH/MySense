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
import subprocess                      # check time period with UNIX subprocess date
from typing import Union,List          # if Python 3.8

import SamenMetenThings as RIVM

__version__ = os.path.basename(__file__) + " V" + "$Revision: 1.8 $"[-5:-2]
__license__ = 'Open Source Initiative RPL-1.5'
__author__  = 'Teus Hagen'

# class defaults
Period = ',now'                         # period of interest, comma separated
# calibrated example: pm25_kal, pm10_kal
# To Do: may need to filter out unsupported sensors
Sensors = '(pm25|pm10|temp|rh|pres|nh3|no2)' # sensor types (ordered) of interest, reg exp
Select  = None                          # don't filter station names (dflt None) else Reg Exp.
Verbosity = 0                           # level of verbosity for Things
Expand  = 'location,address,owner,project' # extra info of stations from Things
# By = 'owner,project'
DEBUG   = False                         # debug modus, do not use SamenMetenThings class

# progress metering, teatime music: every station can take about 15-90 seconds download time
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

import xlsxwriter
# spreadsheet cell fg colors
RED    = '#d92121'
GREEN  = '#019b3f'
YELLOW = '#c3b306'
BLEW   = '#b7ebff'
GRAY   = '#e8e8e8'
MGRAY  = '#d8d8d8'
DGRAY  = '#c8c8c8'
ACTIVE = 7                               # 7 days before End is active
nACTIVE = 21                             # 21 days before End is not active
Workbook = None                          # XLSX workbook handle
# take care: XLSX starts with row 1, not zero
def n2a(n:int) -> str:                   # convert column number to xlsx column name
    d, m = divmod(n,26)                  # 26 is the number of ASCII letters
    return '' if n < 0 else n2a(d-1)+chr(m+65) # chr(65) = 'A'
def cell2xlsx(row:int,col:int) -> str:
    return f"{n2a(col)}{row+1}"

# XLSX matrix columns, sheet has name municipality
# name     GPS ...   properties ...                 sensors (name, first, last, count)
# station, location, [address,] [owner,] [project,] [sensor-i, first, last, count] ,...
def Add_Stations( Municipality:str, Things=None, Period:Union[str,List[str]]=Period) -> bool:
    """Add_Stations(str: municipality, or list of (GPS or station ID's),
    options Period (Start,End) may use Unix date command to get dateformat,
    Things class (sensors,product type, human readable sensor types, sensors status (first/last, count in period)
    create a spreadsheet sheet with station information."""
    global Sensors, Select, Expand, Workbook, Verbosity
    if Things is None:
        # human readable info, UTF8, add sensor status, sensor type info, use threading
        Things = RIVM.SamenMetenThings(Sensors=Sensors,Product=True,Humanise=True,Utf8=True,Status=True,Verbosity=0,Threading=True)
        if Verbosity > 2: Things.Verbose = Verbosity
    if DEBUG:
        Period = '2023/01/01,2024/08/22'
    if Period and not type(Period) is list:
        period = []
        for _ in Period.strip().split(','):
            _ = _.strip()
            try:
              if len(_):  # command date just to get proper timestamp format
                  try:
                    _ = subprocess.check_output(["/bin/date","--date=%s" % _,"+%F"]).decode('utf-8').strip()
                  except:
                    sys.stderr.write("Unix date command failure\n")
                    return None
              else: _ = None
              period.append(_)
            except: raise(f"Unable to convert '{_}' to reasonable date time")
        if len(period) < 2: period.append(None)
        elif type(Period) is list: period = Period[:2]
    else: period = [None,None]
    municipality = list(); region = None
    # filter low-cost station name, station @iot.id, or station GPS
    if (m := re.findall(r'([\(\[]\s*\d+\.\d+\s*,\s*\d+\.\d+\s*[\)\]]|[a-z]+_[a-z0-9_-]+[a-z0-9]|\d+)',Municipality,re.I)):
        # list of low-cost stations
        for _ in m:
                municipality.append(_.strip())
        # a single low_cost station name will be used to identify municipality!
        if len(municipality) == 1 and municipality[0].find('_'):
            # use station name to identify municipality
            municipality = municipality[0]
    else: municipality = Municipality
    if type(municipality) is list: region = 0  # no region, list of single station names
    Start = period[0]; End = period[1]
    # may expand properties: e.g. gemcode (984), knmicode (knmi_06391), pm25regiocode (NL10131), etc.
    if DEBUG:                       # avoid wait on teatime 
        stations = {
           'OHN_gm-2136': {'@iot.id': 8236, 'owner': 'Ohnics', 'project': 'GM', 'location': [(5.933, 51.474), 'Eijk 5, Veen, gem. Ven, prov. Lirg'],
               'sensors': {
                   'temp': {'@iot.id': 42885, 'symbol': 'C', 'first': '2023-10-05T08:00:00.000Z', 'count': 9167, 'last': '2024-10-28T12:00:00.000Z', 'product': 'DS18B20'},
                   'pm25_kal': {'@iot.id': 42884, 'symbol': 'ug/m3', 'first': '2023-10-05T08:00:00.000Z', 'count': 9106, 'last': '2024-10-28T11:00:00.000Z', 'product': 'Sensirion SPS030'},
                   'pm25': {'@iot.id': 42883, 'symbol': 'ug/m3', 'first': '2023-10-05T08:00:00.000Z', 'count': 9167, 'last': '2024-10-28T12:00:00.000Z', 'product': 'Sensirion SPS030'}}},
           'OHN_gm-2138': {'@iot.id': 8238, 'owner': 'Ohnics', 'project': 'GM', 'location': [(6.087, 51.511), 'Hoofd 4, Meer, gem. Horst, prov. Limburg'],
               'sensors': {
                   'temp': {'@iot.id': 42891, 'symbol': 'C', 'first': '2023-10-05T08:00:00.000Z', 'count': 9160, 'last': '2024-10-28T11:00:00.000Z', 'product': 'DS18B20'},
                   'pm25_kal': {'@iot.id': 42890, 'symbol': 'ug/m3', 'first': '2023-10-05T08:00:00.000Z', 'count': 9096, 'last': '2024-10-28T11:00:00.000Z', 'product': 'Sensirion SPS030'},
                   'pm25': {'@iot.id': 42889, 'symbol': 'ug/m3', 'first': '2023-10-05T08:00:00.000Z', 'count': 9160, 'last': '2024-10-28T11:00:00.000Z', 'product': 'Sensirion SPS030'}}},
    'OHN_gm-2126': {'@iot.id': 1234, 'owner': 'Ohnics', 'project': 'GM', 'location': [(5.938, 51.503)],
            'sensors': {
                  'temp': None, 'pm10': {'@iot.id': 42860}, 'pm25': {'@iot.id': 42859}}},
    'OHN_gm-2216': {'owner': 'niks', 'project': 'Palmes',
            'sensors': {
                'rh': None,
                'no2': {'@iot.id': 42860, 'first': '2023-10-05T08:00:00.000Z', 'count': 10, 'last': '2024-07-30T08:00:00.000Z','product':'Palmes'}, 'pm25': {'@iot.id': 42859}}}
        }
    else:
        stations = Things.get_InfoNeighbours(Municipality, Region=region, Select=Select, By=Expand, Start=Start, End=End)
    if not type(stations) is dict: return False
    if not len(stations):
        sys.stderr.write(f"Unable to get stations for municipality {Municipality}.\n")
        return False
    if not type(stations) is dict and not len(stations):
        sys.stderr.write(f"Unable to find stations in municipality {Municipality}\n")
        return False
    if Verbosity > 0:
        sys.stderr.write(f"Found {len(stations)} stations in municipality {Municipality}\n")

    if End is None:
        End = datetime.datetime.now(datetime.timezone.utc)
    else:
        End = datetime.datetime.strptime(RIVM.ISOtimestamp(End),'%Y-%m-%dT%H:%M:%S%z')
    if Start is None:
        Start = datetime.datetime.strptime('1970-01-01T00:00:00Z','%Y-%m-%dT%H:%M:%S%z')
    else:
        Start = datetime.datetime.strptime(RIVM.ISOtimestamp(Start),'%Y-%m-%dT%H:%M:%S%z')

    Sensors = re.sub(r'[\(\)\s]','',Sensors).split('|') # ordered list of sensor names 
    expand = set(Expand.split(',')) - set(['location','address'])
    location = []
    for _ in ['location','address']:
        if Expand.find(_) >= 0: location.append(_)

    # spreadsheet cell formats          ============= cell formats
    title_format      = Workbook.add_format(
        { 'bold': True, 'align': 'center', 'valign': 'vcenter',
          'border_color': DGRAY, 'fg_color': DGRAY,})
    italic            = Workbook.add_format({ 'italic': True, 'bold': False,})
    hrd_bold          = Workbook.add_format(
        { 'bold': True, 'align': 'center',
          'left': True, 'right': True, 'left_color': 'white', 'right_color': 'white',
          'valign': 'vcenter','fg_color': DGRAY,})
    hrd_italic        = Workbook.add_format(
        { 'italic': True, 'align': 'center', 'valign': 'vcenter',
          'left': True, 'right': True, 'left_color': 'white', 'right_color': 'white',
          'fg_color': MGRAY,})
    ghrd_bold         = Workbook.add_format(
        { 'bold': True, 'align': 'center',
          'left': True, 'right': True, 'left_color': 'white', 'right_color': 'white',
          'valign': 'vcenter','fg_color': '#b8b8b8',})
    ghrd_italic       = Workbook.add_format(
        { 'italic': True, 'align': 'center', 'valign': 'vcenter',
          'left': True, 'right': True, 'left_color': 'white', 'right_color': 'white',
          'fg_color': DGRAY,})
    gray_format       = Workbook.add_format({'fg_color': GRAY})
    gray_date_format  = Workbook.add_format({'num_format': 'yyyy-mm-dd', 'fg_color': GRAY})
    mgray_format      = Workbook.add_format({'fg_color': MGRAY})
    mgray_date_format = Workbook.add_format({'num_format': 'yyyy-mm-dd', 'fg_color': MGRAY})
    dgray_format      = Workbook.add_format({'fg_color': DGRAY})
    dgray_date_format = Workbook.add_format({'num_format': 'yyyy-mm-dd', 'fg_color': DGRAY})
    date_format       = Workbook.add_format({'num_format': 'yyyy-mm-dd'})
    human_date_format = Workbook.add_format({'num_format': 'd mmm yyyy'})
    red_date_format   = Workbook.add_format({'num_format': 'yyyy-mm-dd', 'fg_color': RED})
    red_format        = Workbook.add_format({'font_color': RED, 'bold':True})
    yellow_date_format= Workbook.add_format({'num_format': 'yyyy-mm-dd', 'fg_color': YELLOW})
    yellow_format     = Workbook.add_format({'font_color': YELLOW, 'bold': True})
    green_format      = Workbook.add_format({'font_color': GREEN, 'bold': True})
    bold_format       = Workbook.add_format({'bold': True})
    invisible         = Workbook.add_format({'font_color': 'white'})
    right             = Workbook.add_format({"align": "right"})

    # conditional cell Arow format station with activity from Brow
    # to do: gas Palmes sensors are once a month ...
    def bgCondition(row:int, col:int, ref:int) -> None:
        # Period is defined in the cell periodCell [start,end] dlft: 1970/1/1, now()
        # active = end period - datetime.timedelta(days=ACTIVE)    # GREEN BOLD
        # sleeping = end period - datetime.timedelta(days=nACTIVE) # YELLOW BOLD
        # inactive = start period - datetime.timedelta(days=1)     # RED BOLD
        # else: not seen in period: normal
        if ref is None: ref = col
        formatCell = f"{cell2xlsx(row,col)}"
        refCell = f"{cell2xlsx(row,ref)}"
        worksheet.conditional_format(
                formatCell,
                {'type':     'formula',
                 'criteria': f"{refCell} >= {periodCell[1]} - {ACTIVEcell}",
                 'format':   bold_format })
        worksheet.conditional_format(
                formatCell,
                {'type':     'formula',
                 'criteria': f"{refCell} >= {periodCell[1]} - {nACTIVEcell}",
                 'format':   yellow_format })
        worksheet.conditional_format(
                formatCell,
                {'type':     'formula',
                 'criteria': f"{refCell} > {periodCell[0]}",
                 'format':   red_format })

    column = dict(); width = list(); Row = -1; col = -1; inactives = 0; deads = []
    worksheet = Workbook.add_worksheet(name=Municipality)

    # Row with title (header) spreadsheet sheet 6 cells wide
    Row += 2
    title_location = f"{cell2xlsx(Row-1,1)}:{cell2xlsx(Row,7)}"
    worksheet.merge_range(title_location,"")  # just location

    #                                    =============== define cells with reference values
    # Row with globals period first (C), period last (D), active (E), inactive (F) allowance
    Row += 1
                                         # sheet period of measurements
    periodCell = [cell2xlsx(Row,2),cell2xlsx(Row,3)] # Row (3), col C and D
    worksheet.write_datetime(periodCell[0],Start,human_date_format)
    worksheet.write_comment(periodCell[0],"First date of period shown in spreadsheet sheet.")
    worksheet.write_datetime(periodCell[1],End,human_date_format)
    worksheet.write_comment(periodCell[1],"Last date of period shown in spreadsheet sheet.")
    ACTIVEcell = cell2xlsx(Row,4)        # ACTIVE days minimum active up to End, col E
    worksheet.write_number(ACTIVEcell,ACTIVE)   # End -days -> active
    worksheet.write_comment(ACTIVEcell,"labeled active (green) if last timestamp is seen within  nr days before end period.")
    nACTIVEcell = cell2xlsx(Row,5)       # nACTIVE days minimum of inactive, col F
    worksheet.write_number(nACTIVEcell,nACTIVE) # End - days -> inactive
    worksheet.write_comment(nACTIVEcell,"labeled inactive (yellow) if last timestamp is seen before active (green) period and after first date of period.")

    # header Row, Row+1                  =============== set header stations table
    Row += 1; col += 1                   # column station
    column['station'] = col; width.append(12);
    worksheet.write_string(Row,column['station'],'station',ghrd_bold)
    worksheet.write_string(Row+1,column['station'],'Things ID',hrd_italic)

    col += 1; column['period'] = col     # column period
    worksheet.write_string(Row,column['period'],'last seen',hrd_bold)
    worksheet.write_string(Row+1,column['period'],'in period',hrd_italic)
    width.append(0)                      # hide period (Start/End) column 1 (B)

    if len(location) > 1:                # columns location (GPS, address)
        col += 1
        worksheet.merge_range(Row,col,Row,col+1,'location',hrd_bold)
        worksheet.write_string(Row+1,col,"GPS",hrd_italic)
        width.append(0); column['GPS'] = col
        col += 1
        worksheet.write_string(Row+1,col,"address",hrd_italic)
        width.append(0); column['address'] = col
    elif len(location) == 1:             # column GPS
        col += 1
        worksheet.write_string(Row,col,'location',hrd_bold)
        worksheet.write_string(Row+1,col,'GPS',hrd_italic)
        width.append(0); column['GPS'] = col

    for prop in list(expand):            # columns station properties
        col += 1
        worksheet.write_string(Row,col,prop,ghrd_bold)
        worksheet.write_string(Row+1,col,prop,ghrd_italic)
        column[prop] = col; width.append(0)
    humanise = RIVM.HumaniseClass(utf8=True)
    lastColumn = []; lastRow = Row+1

    dark = True
    for name in Sensors:                 # sensors name: first/last timestamp, record count
        col += 1
        worksheet.merge_range(Row,col,Row,col+3,humanise.HumaniseSensor(name),ghrd_bold if dark else hrd_bold)
        worksheet.write_string(Row+1,col,'first',ghrd_italic if dark else hrd_italic); width.append(0)
        worksheet.write_string(Row+1,col+1,'last',ghrd_italic if dark else hrd_italic); width.append(0)
        lastColumn.append(col+1)         # columns with last timestamp sensor record
        worksheet.write_string(Row+1,col+2,'count',ghrd_italic if dark else hrd_italic); width.append(0)
        worksheet.write_string(Row+1,col+3,'type',ghrd_italic if dark else hrd_italic); width.append(0)
        # set timestamp and record count columns format
        worksheet.set_column(f"{cell2xlsx(Row+2,col)}:{cell2xlsx(Row+2+len(stations),col+1)}",15,gray_date_format if dark else date_format)
        if dark:
            worksheet.set_column(f"{cell2xlsx(Row+1+2,col+2)}:{cell2xlsx(Row+1+2+len(stations),col+3)}",7,gray_format)
        column[name] = col; col += 3; dark = not dark
    Row += 2

    #                                   ============= formula cells
    RowsStart = Row                     # stations table data starts here

    # set datetime formats and last date in station sensor cells
    def maxFormula(row:int,columns:list) -> None:
        if not columns: return
        worksheet.write_comment(f"{cell2xlsx(RowsStart-2,column['station'])}","Spreadsheet may need to be recalculated.\nThis differs per version.\nForce cell recalutation by pressing F9 or change days value in cell {nACTIVEcell}.")
        worksheet.write_comment(f"{cell2xlsx(row,column['period'])}","Spreadsheet may need to be recalculated.\nThis differs per version.\nForce recalutation by pressing F9 or change days value in cell {nACTIVEcell}.")
        worksheet.set_column(f"{cell2xlsx(row,column['period'])}:{cell2xlsx(len(stations)+row,column['period'])}",None,date_format)
        for r in range(row,len(stations)+row):
            formula = ''
            for c in columns:
                formula += f",IF(ISBLANK({cell2xlsx(r,c)}),0,{cell2xlsx(r,c)})"
            # ACTIVEcell IF() is just to cause recalculation. To Do: push button "recalculate"
            formula = f"=IF({nACTIVEcell} > {ACTIVEcell},MAX({formula[1:]}),0)"
            worksheet.write_formula(cell2xlsx(r,column['period']),formula)
            bgCondition(r,column['station'], column['period']) # station background color condition

    # set datetime and dark formats in sensors columns (first,last,count), every other gray
    def sensorsFomatting(row:int,columns:list) -> None:
        grayish = True
        for c in columns:
            worksheet.set_column(f"{cell2xlsx(row,c-1)}:{cell2xlsx(len(stations)+row,c)}",None,gray_date_format if grayish else date_format)
            if grayish:
                worksheet.set_column(f"{cell2xlsx(row,c+1)}:{cell2xlsx(len(stations)+row,c+2)}",None,gray_format)
            grayish = not grayish

    maxFormula(RowsStart,lastColumn)       # set formula for activity checks
    sensorsFomatting(RowsStart,lastColumn) # set formats of sensor columns: dark, normal (swap)

    #  spreadsheet station table         =============== station info Rows
    active = 0                           # stations active or dead in period
    for station,info in stations.items():
        operational = False

                                         # location info: GPS, optional address
        if column.get('address') or column.get('GPS'):
          if info.get('location') and len(info['location']):
            if column.get('address'):
               if len(info['location']) > 1 :
                   address = re.sub(r',\s*(gem|prov)\.\s.*','',info['location'][1])
               else: address = ''
               worksheet.write_string(Row,column['address'],address)
               width[column['address']] = max(len(address)+2,width[column['address']])
            if column.get('GPS') and len(info['location']) and len(info['location'][0]):
               location = str(info['location'][0])
               worksheet.write_string(Row,column['GPS'],location)
               width[column['GPS']] = max(len(location)+2,width[column['GPS']])

        for n in expand:                 # owner, project, knmicode, etc.
            if n == 'location' or n == 'address':    continue
            if not info.get(n) or not column.get(n): continue
            worksheet.write_string(Row,column[n],str(info.get(n)))
            width[column[n]] = max(len(str(info.get(n)))+2,width[column[n]])

        if info.get('sensors'):          # sensors of the station
            actives = []; sensing = 0
            for s,v in info.get('sensors').items():
                if not (col := column.get(s)): continue # col -> first record
                if type(info['sensors'][s]) is dict and info['sensors'][s].get('@iot.id'):
                    if (first := info['sensors'][s].get('first',None)):
                        first = datetime.datetime.strptime(first,"%Y-%m-%dT%H:%M:%S.%f%z")
                        worksheet.write_datetime(Row,col,first)
                        width[col] = max(12,width[col])
                    else: worksheet.write(Row,col,"")
                    if (last := info['sensors'][s].get('last',None)):
                        last = datetime.datetime.strptime(last,"%Y-%m-%dT%H:%M:%S.%f%z")
                        bgCondition(Row,col+1, col+1)   # bg color condition on activity
                        worksheet.write_datetime(Row,col+1,last)
                        width[col+1] = max(12,width[col+1]); actives.append(s)
                    else: worksheet.write(Row,col+1,"")
                    if (count := info['sensors'][s].get('count',None)):
                        worksheet.write_number(Row,col+2,count)
                        width[col+2] = max(7,width[col+2]); sensing += 1
                    else: worksheet.write(Row,col+2,"")
                    if(product := info['sensors'][s].get('product',None)):
                        product = product.split(' ')[0]
                        worksheet.write(Row,col+3,product)
                        width[col+3] = max(len(product)+1,width[col+3])
                    else: worksheet.write(Row,col+3,"")

        worksheet.write(Row,column['station'],station,gray_format)
        width[column['station']] = max(7,len(station)+2)
        if len(actives): active += 1
        if not sensing: deads.append(Row)
        if Verbosity:
            sys.stderr.write(f"Station {station} ({Municipality}) was {'never' if not sensing else (str(len(actives))+' active')} sensor(s) operational.\n")
        Row += 1

    # sheet stations statistics info     ================== wrap up
    if Verbosity:
        sys.stderr.write(f"Stations in municipality {Municipality}: nr of station(s): {len(stations)}, station(s) active: {active}, {len(deads)} silent station(s).\n")
    subtitle = f"\n{len(stations)} stations, {len(stations)-inactives} active, {len(deads)} unused."
    #if len(period):
    #    subtitle += f" in period{Start.strftime(' %-d %b %Y') if period[0] else ''}{End.strftime(' upto %-d %b %Y') if End else ''} "
    generated = f"              (generated at {datetime.datetime.now().strftime('%-d %b %Y')})"
    #                                    ================= title with overall info
    worksheet.write_rich_string(re.sub(r':.*','',title_location),f"station statistics of municipality {Municipality}",italic,subtitle,right,generated,title_format)
    #worksheet.write_rich_string(0,1,f"station statistics of municipality {Municipality}\n",italic,f"nr of stations: {len(stations)} ({inactives} inactive, {len(deads)} unused){period}",title_format)

    #                                    ================== cleanup sheet
    for i,w in enumerate(width):         # adjust column width's
        if w: worksheet.set_column(f"{n2a(i)}:{n2a(i)}",w)
        else: worksheet.set_column(f"{n2a(i)}:{n2a(i)}", None, None, {'hidden': 1})
    for i in deads:
        worksheet.set_row(i, None, None, {'hidden':1}) # hide rows dead stations
    return True

#                                        ===================== main
XLSXfile = 'MunicipalityStations.xlsx'   # default XLSX spreadsheet file
def help() -> None:
    sys.stderr.write(
        f"""
Generate overview of low cost stations in municipalities 
or comman separated list of low-cost stations (xlsx sheet per argument name).
Spreadsheet sheet with measurements info:
    location (GPS, address),
    station properties (owner,project, municipality code, ref codes), and
    sensors installed (sensor type, first-last record timestamp, record count) in a period.

Command: {os.path.basename(__file__)} [options] help or name, ...
Name is either municipality name or comma separated list of low-cost station names.

Output as XLSX formatted file (default: {XLSXfile}). Use File='Yours.xlsx' to change this.

Options station info settings:
        Period='2021-01-31,2021-02-31 23:59'  Defines period of observations. Default: all.
        Period='one year ago,now'             Defines last year.
        Sensors='{Sensors}'                   Defines sensor types of interest (regular expression).
        Select='{Select if Select else 'None'}' Filter on station names. Default: do not filter.
        Expand='{Expand}'                     List of station properties of interest.
Options XLSX spreadsheet book property settings:
        File=Outputfile.xlsx                  Default '{XLSXfile}'.
        Company=YourCompanyName               Default empty.
        Status=BookStatus                     Default 'draft'.
Command options:
        Verbosity={Verbosity}                 Verbosity level. Level 5 gives timings info.
        DEBUG                                 In debig modus: Things queries will not be done.
        """)

municipalities = []; company = ''; status = 'draft'; idx = 0
for Municipality in sys.argv[1:]:
    if re.match(r'^(--)?help$',Municipality,re.I):
        help(); Workbook = None
        break
    idx += 1
    if m := re.match(r'^(--)?([^\s]*)\s*(=)\s*([^\s]+.*)$', Municipality):
      if m.groups()[2] == '=':
        if m.groups()[1] == 'Period':    # only measurements in this period
            Period = ','.join([x.strip() for x in m.groups()[3].strip().split(',')])
        elif m.groups()[1] == 'Company': # company of XLSX book creation
            company = m.groups()[3].strip()
        elif m.groups()[1] == 'Status':  # status of XLSX book
            status = m.groups()[3].strip()
        elif m.groups()[1] == 'File':    # file name of XLSX book
            XLSXfile = m.groups()[3].strip()
        elif m.groups()[1] == 'Sensors': # sensor types of interest (reg exp)
            Sensors = m.groups()[3].strip()
        elif m.groups()[1] == 'Select':  # filter reg exp for stations names
            Select = m.groups()[3].strip()
        elif m.groups()[1] == 'Verbosity': # verbosity level
            Verbosity = int(m.groups()[3].strip())
        elif m.groups()[1] == 'Expand':  # show station property info as well
            Expand = m.groups()[3].strip()
        continue
    if re.match(r'^(--)?debug$',Municipality,re.I):   # DEBUG use buildin station dict
        DEBUG = True; Verbosity = 1
        XLSXfile = 'MunicipalityStations-TEST.xlsx'
    if Workbook is None:
        Workbook = xlsxwriter.Workbook(XLSXfile, {'remove_timezone': True})
        if Verbosity:
            sys.stderr.write(f"""Creating XLSX spreadsheet file: '{XLSXfile}'
            for stations in municipalities: '{','.join(sys.argv[idx:])}'
            Filter on sensor types: '{Sensors.replace('|',', ')[1:-1]}'
            Filter station names: '{'turned off' if not Select else Select}'
            Also showing station properties: '{Expand}'\n""")
    # next can take quite some time. To Do: add progress meter?
    if DEBUG:
        Add_Stations('fake region', Period=Period)
        break
    elif Add_Stations( Municipality, Period=Period):
        municipalities.append(Municipality)
    else:
        sys.stderr.write(f"Municipality '{Municipality}': no stations in period '{Period}'\n") 

if Workbook:                              # XLSX book creation
    import pwd
    user = re.sub(r'\s*,.*$','',pwd.getpwnam(os.environ["USER"]).pw_gecos)
    if user: user = f"{user} ({os.environ['USER']})"
    else: user = ''
    properties = {                        # XLSX book properties
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
    # set to manual to speedup, use key F9 to recalculate cells
    Workbook.set_calc_mode('auto')
    Workbook.close()

    if Verbosity >= 0:
        if DEBUG: municipalities = [None]
        sys.stderr.write(f"Created XLSX book: '{XLSXfile}' with {len(municipalities)} municipalities sheet(s)'\n")
    if Verbosity:
        sys.stderr.write(f"\tXLSX properties:\n")
        for p,v in properties.items():
            if v: sys.stderr.write(f"\t\t{p}:\t{v}\n")
