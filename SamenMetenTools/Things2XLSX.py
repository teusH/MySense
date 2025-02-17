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
in various regions (one region per XLSX sheet) in a certain period of time.
Data (Samen Meten dataframe) e.g. obtained via SamenMetenThings tools module RIVM API.
"""
import re
import sys,os
from collections import OrderedDict
import datetime
import dateparser                      # check time period with Python dateparser
from dateutil import tz                # get timezone
from typing import Union,List,Dict,Union,Any # if Python 3.8

import xlsxwriter

__version__ = os.path.basename(__file__) + " V" + "$Revision: 2.3 $"[-5:-2]
__license__ = 'Open Source Initiative RPL-1.5'
__author__  = 'Teus Hagen'

# class to convert Things station info dict to XLSX spreadsheet workbook
class Things2XLSX:
    """Things2XLSX generates XLSX spreadsheet workbook with per sheet (regional name)
    rows of low-cost station sensor information.
    Information data originates from Smane Meten Things (class).
    Input via a Things dict with per station name (row index) sensor informtion (columns)
    Station information might not be complete, e.g. Things '@iot.id' is probably missing.
    E.g.: {
       'OHN_gm-2136': {'owner': 'Ohnics', 'project': 'GM',
           'location': [(5.933, 51.474), 'Eijk 5, Veen, gem. Ven, prov. Lirg'],
           'sensors': {
               'temp': {'symbol': 'C', 'first': '2023-10-05T08:00:00.000Z',
                   'count': 9167, 'last': '2024-10-28T12:00:00.000Z',
                   'product': 'DS18B20'},
               'pm25_kal': {'@iot.id': 42884, 'symbol': 'ug/m3',
                   'first': '2023-10-05T08:00:00.000Z', 'count': 9106,
                   'last': '2024-10-28T11:00:00.000Z', 'product': 'Sensirion SPS030'},
               'pm25': {'@iot.id': 42883, 'symbol': 'ug/m3',
                    'first': '2023-10-05T08:00:00.000Z', 'count': 9167,
                    'last': '2024-10-28T12:00:00.000Z', 'product': 'Sensirion SPS030'},
            ... }}, ...  }
    """

    def __init__(self,XLSXfile:str, **kwargs:Dict[str,str]):
    # class defaults:
        self.Verbosity = 0              # level of verbosity for Things
        # hide xlsx column: GPS,owner,project,address,first,last,count,type
        self.Hide      = 'GPS,owner,first,count'  # default XLSX columns to Hide

        # calibrated example: pm25_kal, pm10_kal
        # Sensors filter: xlsx sensor columns with these names
        self.Sensors   = '(pm25|pm10|temp|rh|pres|nh3|no2)' # dflt sensor filter
        # Expand filter: filter on list of station properties, dflt: usual column names
        self.Expand    = 'location,address,owner,project' # extra info of stations from Things
        self.ZipFile = False            # zip file for files > 4GB
        self.Workbook = None            # workbook handle
        # no Period, period is taken from min - max sensor timestamps per regional sheet
        self.Period = None              # period date/time, e.g. YYYY-MM-DD,YYYY-MM-DD
        # By = 'owner,project'
        self.User = None                # user, author property
        self.Properties = {             # XLSX book properties
                "title": "Air Quality measurements information from RIVM/Things",
                # "subject":str         # names of regions
                "manager": "",
                # "author":str,         # user
                "category": "Air Quality measurements",
                # 'state':str,
                # 'company':str,
                "keywords": "Air Quality, sensors, Particular Matter, NOx, NH3",
                "comments": f"{__license__}.\nCreated by {os.path.basename(__file__)} with Python and XlsxWriter on {datetime.datetime.now().strftime('%-d %b %Y')}.",
              }

        # import class options
        for key,value in kwargs.items():
            if re.match('Verbosity',key,re.I):       # be more versatyle
                self.Verbosity = value
            elif re.match('Period',key,re.I): # defines local period Start/End
                if not type(value) is str or value.find(',') < 0:
                    raise ValueError(f"Period '{value}' has no comman to separate start,end")
                self.Period = value
            elif re.match('Sensors',key,re.I):       # only these sensors
                self.Sensors = value
                if value.find(',') > 0:              # convert list to reg exp
                    self.Sensors = '(' + value.replace(',','|').replace(' ','') + ')'
            elif re.match('Expand',key,re.I):        # expand with eg address, GPS
                self.Expand = value
            elif re.match('Hide',key,re.I):          # names columns to hide
                self.Hide = value
            elif re.match('Zip.*',key,re.I):         # zip file for spreadsheet >4GB
                self.ZipFile = True if re.match('true',re.I) else False
            elif re.match('User',key,re.I):          # property author
                self.User = value
            elif re.match('(Author|Title|Company|Status|Category|Keywords|Comments|Subject|Manager)',key,re.I):
                self.Properties.update({key.lower(): value})
        if not self.Properties.get('author'):        # default set author
            if not self.User:
                try:
                    import pwd
                    self.User = re.sub(r'\s*,.*$','',pwd.getpwnam(os.environ["USER"]).pw_gecos)
                    self.User = f"{self.User} ({os.environ['USER']})"
                except: self.User = ''
            if self.User:
                self.Properties.update({'author': self.User})

        self.XLSXfile = XLSXfile if XLSXfile else 'Things-Stations-Info' # defualt file name
        self.XLSXfile = re.sub(r'.xslx','', self.XLSXfile,re.I) # file name extention
        self.RegionsStations = []                    # list of (region name, #stations)
        if self.Verbosity:
            sys.stderr.write(f"Creating XLSX spreadsheet {'zipped ' if self.ZipFile else ''}file: '{XLSXfile}.xlsx'\n")

    # to support 'with clause' Things2XLSX(): Generate Workbook c.q. Add Stations clause
    def __enter__(self):
       if not self.Workbook:
           self.Workbook = xlsxwriter.Workbook(self.XLSXfile+'.xlsx', {'remove_timezone': True})
       return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
       self.CloseWorkbook()
       if exc_type:
           raise exc_type(exc_value)

    # add from list of tuples with region name and dict with info stations to xlsx sheet
    # period sheet is taken from min - max timestamps sensors
    def GenerateWorkbook(self, Regions:Union[list,dict]) -> bool:
       # next can take quite some time. To Do: add progress meter?
       # convert to list of tuples with region name and Pandas dataframe dict
       if type(Regions) is dict:      # just stations info, Pandas dataformat dict
           regions = [(None,Regions)]
       else:
           regions = []
           for _ in Regions:
               if type(_) is tuple or type(_) is list: regions.append(_[:2])
               else: regions.append((None,_))
       for regionName,stations in Regions:
           if type(regionName) is dict:
               _ = regionName ; regionName = stations; stations = _
           if self.Add_Stations(stations, RgionName=regionName, Period=None): # timestamps period
               regions.append(regionName)
           else:
               sys.stderr.write(f"Region '{regionName}': no stations found.'\n") 
       return(CloseWorkbook())

    def CloseWorkbook(self) -> bool:
        if self.Workbook:                                # XLSX book creation
            self.Properties.update({
                "subject": "Low-Cost stations in regions: " + ', '.join([_[0] for _ in self.RegionsStations])})
            self.Workbook.set_properties(self.Properties)
            if self.Verbosity:
                sys.stderr.write(f"Created XLSX file: {self.XLSXfile}\n\tXLSX properties:\n")
                if self.Verbosity < 1:
                    for p,v in properties.items():
                        if v: sys.stderr.write(f"\t\t{p}:\t{v}\n")
                    for p,v in self.RegionsStations:
                        sys.stderr.write(f"\tregion {p} with {v} stations\n")

    # XLSX matrix columns, sheet has name municipality
            #calculationProperties = Workbook.CalculationProperties;
            #        calculationProperties.ForceFullCalculation = true;
            #        calculationProperties.FullCalculationOnLoad = true;
            # set to manual to speedup, use key F9 to recalculate cells
            self.Workbook.set_calc_mode('auto')
            self.Workbook.close()
            self.Workbook = None
            return True
        return False
    
    # name     GPS ...   properties ...                 sensors (name, first, last, count)
    # station, location, [address,] [owner,] [project,] [sensor-i, first, last, count] ,...
    # Add_Stations will use Sensors and Expand to filter out these columns
    # Preriod is None: take min - max from sensor timestamps, else 'start,end'
    def Add_Stations(self, Stations:dict, RegionName:str=None, Period:str=None) -> bool:
        """Add_Stations from Samen Meten Tools dict with station info and
        create a spreadsheet sheet with low-cost station information."""

        # parse period local datetime str to period datetime list
        # returns list(start:datetime or None,datetime or None): None use sensor timestamps
        def ParsePeriod(Period:str) -> Union[datetime.datetime,List[datetime.datetime]]:
            if Period is None: return ParsePeriod(",")
            if not Period: return None
            if Period.find(',') < 0:
                if not type(dt := dateparser.parse(Period)) is datetime.datetime:
                    raise ValueError(f"Unix date {Period} failure. Check LANG env. variable setting.")
                return dt
            period = list()
            for dt in Period.strip().split(',')[:2]:
                period.append(ParsePeriod(dt.strip()))
            return period
                
        if not self.Workbook:
            self.Workbook = xlsxwriter.Workbook(self.XLSXfile+'xlsx', {'remove_timezone': True})
            if self.ZipFile: self.Workbook.use_zip64()
        self.RegionsStations.append((RegionName,len(Stations)))
        # handle period with a start date but no end date
        if type(Period) is str and Period.find(',') < 0: Period += ','
        period = ParsePeriod(Period)    # define period start-end, dflt None,None

        # take care: XLSX starts with row 1, not zero
        def n2a(n:int) -> str:   # convert column number to xlsx column name
            d, m = divmod(n,26)  # 26 is the number of ASCII letters
            return '' if n < 0 else n2a(d-1)+chr(m+65) # chr(65) = 'A'
        def cell2xlsx(row:int,col:int) -> str:
            return f"{n2a(col)}{row+1}"

        if not type(Stations) is dict or not len(Stations):
            sys.stderr.write(f"Unable to find stations in the region {RegionName if RegionName else 'no region name defined'} or data is not a Things dictionary. Skipped.")
            return False
        if self.Verbosity > 0:
            sys.stderr.write(f"Found {len(Stations)} stations in region {RegionName if RegionName else 'no region provided'}\n")
    
        sensors = re.sub(r'[\(\)\s]','',self.Sensors).split('|') # ordered list of sensor names 
        expand = set(self.Expand.split(',')) - set(['location','address'])
        location = []
        for _ in ['location','address']:
            if self.Expand.find(_) >= 0: location.append(_)
    
        # ================================= convert to XLSX spreadsheet
        # spreadsheet cell fg colors
        RED    = '#d92121'
        GREEN  = '#019b3f'
        YELLOW = '#c3b306'
        BLEW   = '#b7ebff'
        GRAY   = '#e8e8e8'
        MGRAY  = '#d8d8d8'
        DGRAY  = '#c8c8c8'
        ACTIVE = 7                          # dflt 7 days before End is active
        nACTIVE = 21                        # dflt 21 days before End is not active
        # spreadsheet cell formats          ============= cell formats
        title_format      = self.Workbook.add_format(
            { 'bold': True, 'align': 'center', 'valign': 'vcenter',
              'border_color': DGRAY, 'fg_color': DGRAY,})
        italic            = self.Workbook.add_format({ 'italic': True, 'bold': False,})
        hrd_bold          = self.Workbook.add_format(
            { 'bold': True, 'align': 'center',
              'left': True, 'right': True, 'left_color': 'white', 'right_color': 'white',
              'valign': 'vcenter','fg_color': DGRAY,})
        hrd_italic        = self.Workbook.add_format(
            { 'italic': True, 'align': 'center', 'valign': 'vcenter',
              'left': True, 'right': True, 'left_color': 'white', 'right_color': 'white',
              'fg_color': MGRAY,})
        ghrd_bold         = self.Workbook.add_format(
            { 'bold': True, 'align': 'center',
              'left': True, 'right': True, 'left_color': 'white', 'right_color': 'white',
              'valign': 'vcenter','fg_color': '#b8b8b8',})
        ghrd_italic       = self.Workbook.add_format(
            { 'italic': True, 'align': 'center', 'valign': 'vcenter',
              'left': True, 'right': True, 'left_color': 'white', 'right_color': 'white',
              'fg_color': DGRAY,})
        gray_format       = self.Workbook.add_format({'fg_color': GRAY})
        gray_date_format  = self.Workbook.add_format({'num_format': 'yyyy-mm-dd', 'fg_color': GRAY})
        mgray_format      = self.Workbook.add_format({'fg_color': MGRAY})
        mgray_date_format = self.Workbook.add_format({'num_format': 'yyyy-mm-dd', 'fg_color': MGRAY})
        dgray_format      = self.Workbook.add_format({'fg_color': DGRAY})
        dgray_date_format = self.Workbook.add_format({'num_format': 'yyyy-mm-dd', 'fg_color': DGRAY})
        date_format       = self.Workbook.add_format({'num_format': 'yyyy-mm-dd'})
        human_date_format = self.Workbook.add_format({'num_format': 'd mmm yyyy'})
        red_date_format   = self.Workbook.add_format({'num_format': 'yyyy-mm-dd', 'fg_color': RED})
        red_format        = self.Workbook.add_format({'font_color': RED, 'bold':True})
        yellow_date_format= self.Workbook.add_format({'num_format': 'yyyy-mm-dd', 'fg_color': YELLOW})
        yellow_format     = self.Workbook.add_format({'font_color': YELLOW, 'bold': True})
        green_format      = self.Workbook.add_format({'font_color': GREEN, 'bold': True})
        bold_format       = self.Workbook.add_format({'bold': True})
        invisible         = self.Workbook.add_format({'font_color': 'white'})
        right             = self.Workbook.add_format({"align": "right"})
    
        # conditional cell Arow format station with activity from Brow
        # to do: gas Palmes sensors are once a month ...
        def bgCondition(row:int, col:int, ref:int) -> None:
            # period is defined in the cell periodCell [start,end] dlft: timestamps sensor
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
    
        column = dict(); width = list()
        Row = -1; col = -1; inactives = 0; deads = []; sheetPeriod = [None,None]
        worksheet = self.Workbook.add_worksheet(name=RegionName)
    
        # Row with title (header) spreadsheet sheet 6 cells wide
        Row += 2
        title_location = f"{cell2xlsx(Row-1,1)}:{cell2xlsx(Row,7)}"
        worksheet.merge_range(title_location,"")  # just location
    
        #                                    =============== define cells with reference values
        # Row with globals period first (C), period last (D), active (E), inactive (F) allowance
        Row += 1
                                             # sheet period of measurements
        # period is defined in the cell periodCell [start,end] dlft: timestamps sensor
        periodCell = [cell2xlsx(Row,2),cell2xlsx(Row,3)] # Row (3), col C and D
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
        import SamenMetenThings as RIVM
        humanise = RIVM.HumaniseClass(utf8=True)
        lastColumn = []; lastRow = Row+1
    
        dark = True
        for name in sensors:                 # sensors name: first/last timestamp, record count, type
            col += 1
            worksheet.merge_range(Row,col,Row,col+3,humanise.HumaniseSensor(name),ghrd_bold if dark else hrd_bold)
            worksheet.write_string(Row+1,col,'first',ghrd_italic if dark else hrd_italic); width.append(0)
            worksheet.write_string(Row+1,col+1,'last',ghrd_italic if dark else hrd_italic); width.append(0)
            lastColumn.append(col+1)         # columns with last timestamp sensor record
            worksheet.write_string(Row+1,col+2,'count',ghrd_italic if dark else hrd_italic); width.append(0)
            worksheet.write_string(Row+1,col+3,'type',ghrd_italic if dark else hrd_italic); width.append(0)
            # set timestamp and record count columns format
            worksheet.set_column(f"{cell2xlsx(Row+2,col)}:{cell2xlsx(Row+2+len(Stations),col+1)}",15,gray_date_format if dark else date_format)
            if dark:
                worksheet.set_column(f"{cell2xlsx(Row+1+2,col+2)}:{cell2xlsx(Row+1+2+len(Stations),col+3)}",7,gray_format)
            column[name] = col; col += 3; dark = not dark
        Row += 2
    
        #                                   ============= formula cells
        RowsStart = Row                     # stations table data starts here
    
        # set datetime.datetime formats and last date in station sensor cells
        def maxFormula(row:int,columns:list) -> None:
            if not columns: return
            #worksheet.write_comment(f"{cell2xlsx(0,0)}",f"Spreadsheet may need to be recalculated.\nThis differs per version.\nForce recalutation by pressing F9 or change days value in cell {nACTIVEcell}.",{'visible': True})
            worksheet.set_column(f"{cell2xlsx(row,column['period'])}:{cell2xlsx(len(Stations)+row,column['period'])}",None,date_format)
            for r in range(row,len(Stations)+row):
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
                worksheet.set_column(f"{cell2xlsx(row,c-1)}:{cell2xlsx(len(Stations)+row,c)}",None,gray_date_format if grayish else date_format)
                if grayish:
                    worksheet.set_column(f"{cell2xlsx(row,c+1)}:{cell2xlsx(len(Stations)+row,c+2)}",None,gray_format)
                grayish = not grayish
    
        maxFormula(RowsStart,lastColumn)       # set formula for activity checks
        sensorsFomatting(RowsStart,lastColumn) # set formats of sensor columns: dark, normal (swap)
    
        #  spreadsheet station table         =============== station info Rows
        active = 0                           # stations active or dead in period
        for station,info in Stations.items():
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
                            if sheetPeriod[0]:
                                sheetPeriod[0] = min(sheetPeriod[0],first)
                            else: sheetPeriod[0] = first
                        else: worksheet.write(Row,col,"")
                        if (last := info['sensors'][s].get('last',None)):
                            last = datetime.datetime.strptime(last,"%Y-%m-%dT%H:%M:%S.%f%z")
                            bgCondition(Row,col+1, col+1)   # bg color condition on activity
                            worksheet.write_datetime(Row,col+1,last)
                            if sheetPeriod[1]:
                                sheetPeriod[1] = max(sheetPeriod[1],last)
                            else: sheetPeriod[1] = last
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
            if self.Verbosity:
                sys.stderr.write(f"Station {station} ({RegionName}) was {'never' if not sensing else (str(len(actives))+' active')} sensor(s) operational.\n")
            Row += 1
    
        if not sheetPeriod[0]:
            sheetPeriod[0] = datetime.datetime(1970, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
        if not sheetPeriod[1]:
            sheetPeriod[1] = datetime.datetime(2070, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
        # guess sheet period, either from argument, or from sensors timestamps
        if period[0] is None: period[0] = sheetPeriod[0]
        if not period[0] is None:
            worksheet.write_datetime(periodCell[0],period[0],human_date_format)
        worksheet.write_comment(periodCell[0],"First date of period shown in spreadsheet sheet.")
        if period[1] is None: period[1] = sheetPeriod[1]
        if not period[1] is None:
            worksheet.write_datetime(periodCell[1],period[1],human_date_format)
        worksheet.write_comment(periodCell[1],"Last date of period shown in spreadsheet sheet.")
        # sheet stations statistics info     ================== wrap up
        if self.Verbosity:
            sys.stderr.write(f"Stations in municipality {RegionName}: nr of station(s): {len(Stations)}, station(s) active: {active}, {len(deads)} silent station(s).\n")
        subtitle = f"\n{len(Stations)} stations, {len(Stations)-inactives} active, {len(deads)} unused."
        if period[0] or period[1]:
            subtitle += f" in period{period[0].strftime(' %-d %b %Y') if period[0] else ''}{period[1].strftime(' upto %-d %b %Y') if period[1] else ''} "
        generated = f"              (generated at {datetime.datetime.now().strftime('%-d %b %Y')})"
        #                                    ================= title with overall info
        worksheet.write_rich_string(re.sub(r':.*','',title_location),f"station statistics of municipality {RegionName}",italic,subtitle,right,generated,title_format)
    
        #                                    ================== cleanup sheet
        for i,w in enumerate(width):         # adjust column width's
            if w: worksheet.set_column(f"{n2a(i)}:{n2a(i)}",w)
            else: worksheet.set_column(f"{n2a(i)}:{n2a(i)}", None, None, {'hidden': 1})
        for i in deads:
            worksheet.set_row(i, None, None, {'hidden':1}) # hide rows dead stations
        # hide sensor columns: first, lastColumn[], count, type
        # column = {'station': 0, 'period': 1, 'GPS': 2, 'address': 3, 'owner': 4, 'project': 5, 'pm25': 6, 'pm10': 10, ...}
        for col in (set(column.keys())-set(self.Sensors)).intersection(set(self.Hide.split(','))):
            if (col := column.get(col)): # restrict hide to non sensors
                worksheet.set_column(f"{n2a(col)}:{n2a(col)}", None, None, {'hidden': 1})
        # sensor type
        hide = { 'first': 0, 'last': 1, 'count': 2, 'type': 3, } # relative index
        hide = [hide.get(_) for _ in  set(hide.keys()).intersection(set(self.Hide.split(',')))]
        for rh in hide:
            for col in self.Sensors:
              if not (col := column.get(col)) is None:
                  worksheet.set_column(f"{n2a(rh+col)}:{n2a(rh+col)}", None, None, {'hidden': 1})
        return True
    
#                                        ===================== main
XLSXfile = 'Regional_Stations.xlsx'   # default XLSX spreadsheet file

# ================================================================================
################## command line tests of (class) subroutines or command line checks
# command line options:  help, debug, verbosity=N,
#                        title=Name
#                        period to select stations from Things
#                        period=YYYY-MM-DD HH:MM,YYYY-MM-DD HH:MM or auto detect
#                        sensors=comma separeted list of sensors to get info
#                        expand=comma separated lst of extra info e.g. address, sensor branche
#                        hide=column names to hide in xlsx
#                        company=X, user=X, company=X, status=X XLSX properties definitions
if __name__ == '__main__':
    DEBUG = False; Verbosity = 0; Period = None
    def help() -> None:
        sys.stderr.write(
            f"""
Command: {os.path.basename(__file__)} DEBUG (test data) or help
Command options:
        --help|-h                            Print help
        Verbosity={Verbosity}                Verbosity level. Level 5 gives timings info.
        DEBUG                                In debug modus: Things queries will not be done.
        --version|-v                         Print version: {__version__}
Commandline is just for debugging or XLSX function tests.
Output is XLSX formatted file (default: {XLSXfile}). Use File='Your name' to change this.
Filename extension '.xlsx' is added to the file name.

Class module generate overview of low cost stations in regions 
or comman separated list of low-cost stations (xlsx sheet per argument name).
One spreadsheet sheet with low-cost station (Things) measurements info per sheet:
    location (GPS, address),
    station properties (owner,project, municipality code, ref codes), and
    sensors installed (sensor type, first-last record timestamp, record count) in a period.

Options for the xlsx write module:
        Defines sensor types of interest (regular expression)
            Sensors='(pm25|pm10|temp|rh|pres|nh3|no2)' calibrated examples: pm25_kal, pm10_kal.
            Expand='location,address,owner,project' to expand.
            Period=datetime start,datetime end string default: empty (use sensor timestamps)
            Timestamp will use time parser to understand human expressions (language dependant).
        Hide these XLSX columns. Default Hide='GPS,address,first,last,count,type'
        ZipFile=False zip the xlsx file for files > 4GB
Options XLSX spreadsheet book property settings:
        File=Outputfile.xlsx                  Default 'Things-Stations-Info'.
        Title=YourTitle
        Company=YourCompanyName               Default empty.
        BookStatus=status                     Default 'draft'.
        User=MyName                           Created by user name. Default: login name.

        """)

    Kwargs = dict()                          # class options
    Output = 'Things-regional-stations-Test' # default output test file name
    Regions = list()                         # list of region names collected from args
    for arg in sys.argv[1:]:
        if re.match(r'^--*h(elp)*$',arg,re.I):
            help(); exit(0)
        # class options definitions
        if m := re.match(r'^(--)?([^\s]*)\s*(=)\s*([^\s]+.*)$', arg):
          if m.groups()[2] == '=':
            if m.groups()[1] == 'Verbosity':   # verbosity level
                Verbosity = int(m.groups()[3].strip())
            elif m.groups()[1] == 'Output':    # output XLSX file name
                output = re.sub(r'\.xlsx','',m.groups()[3].strip(),re.I)
            elif m.groups()[1] == 'Title':     # file base name of XLSX spreadsheet book
                output = m.groups()[3].strip()
            elif m.groups()[1] == 'Hide':      # hide these Xlsx columns
                Kwargs.update({'Hide': m.groups()[3].strip()})
            elif m.groups()[1] == 'Company':   # company of XLSX book creation
                Kwargs.update({'Company': m.groups()[3].strip()})
            elif m.groups()[1] == 'User':      # user of XLSX book creation
                Kwargs.update({'User': m.groups()[3].strip()})
            elif m.groups()[1] == 'Bookstate': # status of XLSX spreadsheet book
                Kwargs.update({'Bookstate': m.groups()[3].strip()})
            # date/time period and station info selections
            elif m.groups()[1] == 'Sensors':   # sensor types of interest (reg exp)
                Kwargs.update({'Sensors': m.groups()[3].strip()})
            elif m.groups()[1] == 'Expand':    # show station property info as well
                Kwargs.update({'Expand': m.groups()[3].strip()})
            # to collect station info from Samen Meten Tools get regional stations
            elif m.groups()[1] == 'Select':    # filter reg exp for stations names
                Kwargs.update({'Select': m.groups()[3].strip()})
            continue
        elif re.match(r'^((--)?debug|-d)$',arg,re.I):   # DEBUG use buildin station dict
            DEBUG = True; Verbosity = 3
            output = 'TEST-region'
            continue
        elif re.match(r'^(--*v(ersion)*)$',arg): # print version and exit
            sys.stderr.write(f"{__version__}\n")
            exit(0)
        Regions.append(arg)
    if Verbosity:
        Kwargs.update({'Verbosity': Verbosity})
    
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
    
    # check if file is json file with Samen Meten Things dict
    def FileIsThingsArchive(filename:str) -> Union[dict,str]:
        if re.match(r'.*\.(json|csv)(\.gz)?$',filename):
            method = open
            if re.match(r'.*\.gz$',filename):
                import gzip
                method = gzip.open
            try:
                data = None
                if re.match('.*\.json(\.gz)?$',filename):
                    import json
                    with method(filename, 'r') as fin:
                        data = json.loads(fin.read())
                    # do a simple check for Things dict
                    if type(data) is dict and (_ := data.get(next(iter(data)))):
                        for _ in _.keys():
                            if re.match(r'(sensors|owner|project|location)',_):
                                _ = None; break # rely there is not a None key
                        if _: data = None
                    else: data = None
                else: # (gzipped) CSV file, to do
                    sys.stderr.write(f"CSV file '{filename}' not yet supported. Skipped.\n")
                    return None
            except: pass
            if type(data) is dict: return data
            return None
        return filename  # it is not an archive file

    # obtain low-cost stations info for a region (municipality, stations neighbouring
    # a station or GPS location oor list of stations via
    # Samen Meten Things API database website qry.
    # result: Pandas dataframe dict(station name:station info). See DEBUG as example.
    def GetStationInfo(RegionName:str, **kwargs) -> tuple:
        """GetStationsInfo(str: municipality, or list of (GPS or station ID's),
        options Period (Start,End) may use Unix date command to get dateformat,
        Things class (sensors,product type, human readable sensor types, sensors status (first/last, count in period)
        """
        import SamenMetenThings as RIVM
        if Verbosity > 0:
            sys.stderr.write(f'Collect stations with region {RegionName} for period {str(Period)}\n')
        if Things is None:
            # human readable info, UTF8, add sensor status, sensor type info, use threading
            Things = RIVM.SamenMetenThings(Sensors=sensors,Product=True,Humanise=True,Utf8=True,Status=True,Verbosity=0,Threading=True)
            if Verbosity > 1: Things.Verbose = Verbosity
        Period = kwargs.get('Period',None)
        Select = kwargs.get('Select',None)
        Sensors = kwargs.get('Sensors',None)
        Expand = kwargs.get('Expand',None)
        if Period and not type(Period) is list:
            period = []
            for _ in Period.strip().split(','):
                _ = _.strip(); dt = None
                if len(_):  # command date just to get proper timestamp format
                    dt = dateparser.parse(_)
                    if not type(dt) is datetime.datetime:
                        raise(f"Unix date {_} failure. Check LANG env. variable setting.")
                    dt = dt.astimezone(tz.UTC)  # convert local time to utc
                    dt = datetime.datetime.strftime(dt,"%Y-%m-%dT%H:%M:%SZ")
                    if not re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',dt):
                        raise(f"Unix date {_} failure. Check LANG env. variable setting.\n")
                period.append(dt)
            if len(period) < 2: period.append(None)
            elif type(Period) is list: period = Period[:2]
        else: period = [None,None]
        # get period of timestamps of observations available Start - End
        if period[1] is None:
            period[1] = datetime.datetime.now(datetime.timezone.utc)
        else:
            period[1] = datetime.datetime.strptime(RIVM.ISOtimestamp(End),'%Y-%m-%dT%H:%M:%S%z')
        if period[0] is None:
            period[0] = datetime.datetime.strptime('1970-01-01T00:00:00Z','%Y-%m-%dT%H:%M:%S%z')
        else:
            period[0] = datetime.datetime.strptime(RIVM.ISOtimestamp(Start),'%Y-%m-%dT%H:%M:%S%z')
    
        sheetName = list(); region = None
        # filter low-cost station name, station @iot.id, or station GPS
        if (m := re.findall(r'([\(\[]\s*\d+\.\d+\s*,\s*\d+\.\d+\s*[\)\]]|[a-z]+_[a-z0-9_-]+[a-z0-9]|\d+)',RegionName,re.I)):
            # list of low-cost stations
            for _ in m:
                    sheetName.append(_.strip())
            # a single low_cost station name will be used to identify municipality!
            if len(sheetName) == 1 and sheetName[0].find('_'):
                # use station name to identify municipality
                sheetName = sheetName[0]
        else: sheetName = RegionName
        if type(sheetName) is list: region = 0  # no region, list of single station names
    
        # may expand properties: e.g. gemcode (984), knmicode (knmi_06391), pm25regiocode (NL10131), etc.
        stations = Things.get_InfoNeighbours(RegionName, Region=region,
                Select=Select, By=Expand,
                Start=(None if not period[0] else periond[0].strftime("%Y-%m-%dT%H:%M:%SZ")),
                End=(None if not period[1] else periond[1].strftime("%Y-%m-%dT%H:%M:%SZ")))
        return (RegionName,stations,period)

    RegionalStations = list()
    if DEBUG:
        RegionalStations = [('TEST-region', {
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
            },Period)]

    # collect regions with stations from archive or Samen Meten Things website
    for region in Regions:
        if type(data := FileIsThingsArchive(region)) is dict:
            RegionalStations.append((re.sub(r'\.(json|csv)(\.gz)?$','',region, re.I),data,None))
        elif type(data) is None:  # error opening archive file
            sys.stderr.write(f"Things archive file '{region}' reading or format error. Skipped.\n")
        else:   # region name: get staions of that region
            try:
                # next can take a while. use progress metering?
                item =  GetStationInfo(region,**Kwargs)
                if type(item[1]) is dict:
                    RegionalStations.append((item[0],item[1],item[2]))
                # args: region name:str, stations:dict, period list[datetime,datetime]
            except:
                sys.stderr.write(f"Error to get stations in region '{region}'. Skipped.\n")

    # push regions with stations info in an XLSX spreadsheet workbook
    # RegionName, StationsDict = GetStationInfo(RegionName, Period=',now')
    if len(RegionalStations):
        with Things2XLSX(Output, **Kwargs) as Convert2XLSX:
            for region in RegionalStations:
                Convert2XLSX.Add_Stations(region[1],RegionName=region[0],Period=region[2])
            # or use: ThingsXLSX.GenerateWorkbook(Regions:lRegionName:None,Stations dict])
    else: help()
        

