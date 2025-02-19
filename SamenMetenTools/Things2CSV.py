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
Python3.8+ script to generate overview in CSV format of meta station info
in various regions in a certain period of time.
Info data (Samen Meten dict) e.g. obtained via SamenMetenThings tools module RIVM API.
"""
import re
import sys,os
from collections import OrderedDict
import datetime
from dateutil import tz                # get timezone
from typing import Union,List,Dict,Union,Any # if Python 3.8
import pandas as pd
import SamenMetenThings as RIVM

__version__ = os.path.basename(__file__) + " V" + "$Revision: 2.2 $"[-5:-2]
__license__ = 'Open Source Initiative RPL-1.5'
__author__  = 'Teus Hagen'

# convert yyyy-mm-dd [hh:mm] to local timestamp:datetime
def datetime_str_to_datetime(yyyy_mm_dd_hh_mm: str, end=False) -> str:
    """datetime_str_to_datetime convert string to zone aware datetime."""
    if not type(yyyy_mm_dd_hh_mm) is str: return yyyy_mm_dd_hh_mm
    if re.match(r'[0-9]{4}-[01][0-9]*-[0-3][0-9]$', yyyy_mm_dd_hh_mm):
        date = datetime_str_to_datetime(yyyy_mm_dd_hh_mm +('23:59:59' if end else '00:00:00'))
    elif re.match(r'[0-9]{4}-[01][0-9]*-[0-3][0-9]\s[0-2][0-9]:[0-5][0-9]$', yyyy_mm_dd_hh_mm):
        date = datetime_str_to_datetime(yyyy_mm_dd_hh_mm + (":59" if end else ":00"))
    else:
        date = yyyy_mm_dd_hh_mm
    return date

# convert local timestamp:str to Pandas datetime
def local_to_panda(local: str, end=False, tz=None) -> datetime:
    """local_to_panda: convert local time to Panda zone aware datetime."""
    try:
        from tzlocal import get_localzone
        localTZ = str(get_localzone())
    except: localTZ = 'Europe/Amsterdam'
    date = pd.to_datetime(datetime_str_to_datetime(local, end=end)).tz_localize(tz=localTZ)
    if not tz:
        return  date
    else:
        return date.tz_convert(tz=tz)
    
# parse period local datetime str to period datetime list
# returns list(start:datetime or None,datetime or None): None use sensor timestamps
def ParsePeriod(Period:str) -> Union[datetime.datetime,List[datetime.datetime]]:
    if Period is None: return ParsePeriod(",")
    if not Period: return pd.NaT
    if Period.find(',') < 0:
        if not type(dt := dateparser.parse(Period)) is datetime.datetime:
            raise ValueError(f"Unix date {Period} failure. Check LANG env. variable setting.")
        return dt
    period = list()
    for dt in Period.strip().split(',')[:2]:
        if not dt: period.append(pd.NaT)
        else: period.append(local_to_panda(ParsePeriod(dt.strip()).strftime("%Y-%m-%d %H:%M:%S"),tz='UTC'))
    return period

# input example: [{'Things ID': str, 'GPS': [], 'pm10 count': int, ...} { ... }}
# Rename=[(r'str exp',str)] used for humanised column names
# To Do filter Pandas series:
# DropCols: drop columns with names not matching reg.exp e.g. allow only reg. exp sensor names
# DropRow: drop certain rows e.g. allow only reg.exp station names
def ListDictToSeries(Data: dict, Indexed:str='Things ID', Rename:List[tuple]=None, Sort:bool=True) -> pd.core.frame.DataFrame:
    """ListDictSeries() Convert a list of one dim dict's to Pandas series dataframe.
    Drop columns not matching Select reg.exp.
    Rename column names e.g. 'sensor pm10 last' to 'pm10 last' (normalised names).
    Sort the dataframe."""

    if not Data: return None
    df = pd.DataFrame.from_dict(Data)                # convert to Panda series
    df.dropna(inplace=True,how='all')                # drop row with all NaN
    if df.empty: return None                     # no stations found
    df.dropna(inplace=True,how='all',axis='columns') # drop columns with all NaN
    if df.empty: return None                     # no stations found
    if Rename:          # change column names via reg.exp
        columns = dict()
        for i in range(0, len(Rename)): # do not rename if new name is not defined
            if not type(Rename[i]) is tuple and len(Rename[i]) < 2: continue
            if Rename[i][1] is None or Rename[i][0] is None: continue
            for col in df.columns:
                flags = 0 if len(Rename[i]) < 3 else Rename[i][2]
                if re.match(Rename[i][0],col,flags):
                    columns[col] = re.sub(Rename[i][0],Rename[i][1],col,flags)
                    if not columns[col]:
                        del columns[col]
                        # sys.stderr.write(f"Warning: column '{col}' not renamed!\n")
            if columns:
                try:    # noqa
                    df.rename(columns=columns, inplace=True)
                except: pass
    # To Do: to save memory drop sensor not needed sensor, expand columns and station rows 
    if Indexed:         # define index (station names)
        df.set_index(Indexed, drop=True, inplace=True) # indexed by timestamp
    if Sort:
        df.sort_index(ascending=True, inplace=True)    # sort on station names
    return df

# concatenate two pandas dataframes
# unique will overwrite the left dataframe series on doubles (dflt)
def ConcatSeries(Left:pd.core.frame.DataFrame,Right:pd.core.frame.DataFrame,Unique:bool=True, Sort:bool=True) -> pd.core.frame.DataFrame:
    """ConcatSeries() Combine two Pandas series dateframe into one (sorted) dataframe.
    Not unique index name (station name) handling: optionaly overwrite with second frame."""

    left = Left.copy()
    doubles = []
    if Unique:
        for item in Right.index:
            if item in Left.index: doubles.append(item)
    if doubles: left.drop(index=doubles,inplace=True)
    left = pd.concat([left,Right],sort=False)
    if Sort: left.sort_index(ascending=True, inplace=True) # sort on station names
    return left

# class to convert Things station info dict to XLSX spreadsheet workbook
class Things2CSV:
    """Things2XLSX generates CSV archive file rows of low-cost station meta information.
    Information data originates from Smane Meten Things API webqueries (class).
    Input via a Things dict with per station name (column 0) sensor informtion
    Filtering:
        Period=',' (dflt: full period): station should have observations in this period.
        Period are local timestamps, and may defined in human format (language dependent) like 'yesterday'.
        Sensors='pm25,pm10,temp,rh,no2,o3,nh3'  Comma separated list or reg exp of wanted sensors.
        Expand='location,address,owner,project' Comma separated list of info names allowed.
        Select='.*'                             Reg Exp of station names allowed.
    Warning: Station information does not not be complete.
    Output in CSV:
    CSV file properties as e.g. author, title, subject, comment, version, date generated, etc.
    Timestamps in CSV are converted to local time zone.
    Rows with Things '@iot.id' (limited life time) are probably missing.

    Meta info rows start with '#' char Property type delimiter info string
    Property items: title, subject, author, category, state, keywords, comments, generated, version.

    Input: Samen Meten Things dict with station: {station info}, list with one dim dicts,
          region name as e.g. 'Land van Cuijk', file name with file type extension
          as e.g. 'Land van Cuijk.json.gz' or 'Land van Cuijk.json', etc.
          Yet supported input files: (compressed) json, csv.
       Dict input example: {
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
        List input example:
          {'owner': 'niks', 'project': 'Palmes', 'rh': None, 'no2 @iot.id': 42860,
          'no2 first': Timestamp('2023-10-05 08:00:00+0000', tz='UTC'), 'no2 count': 10,
          'no2 last': Timestamp('2024-07-30 08:00:00+0000', tz='UTC'),
          'no2 product': 'Palmes', 'pm25 @iot.id': 42859,
          'Things ID': 'OHN_gm-2216', 'GPS': (6.123,54.123), 'region': 'TEST-region'}
    """

    def __init__(self,CSVfile:str, **kwargs:Dict[str,str]):
        # class defaults:
        self.Verbosity = 0              # level of verbosity for Things
        # hide xlsx column: GPS,owner,project,address,first,last,count,type
        #self.Hide      = 'GPS,owner,first,count'  # default CSV columns to Hide

        # humanise or dehumanise sensor names function
        # names are converted to utf8 in output (default True)
        self.UTF8 = kwargs.get('utf8',True) # humanise (dflt) sensor names in output
        self.UTF8 = kwargs.get('utf-8',self.UTF8)
        self.Humanisation = RIVM.HumaniseClass(utf8=self.UTF8)
        # calibrated example: pm25_kal, pm10_kal
        # Sensors filter: CSV sensor columns with these names
        self.Sensors   = '(pm25|pm10|temp|rh|pres|nh3|no2)' # dflt sensor filter
        self.Delim     = ' '            # str to separate sensor from sensor type..
        # Expand filter: filter on list of station properties, dflt: usual column names
        self.Expand    = 'location,address,owner,project' # extra info of stations from Things
        self.Select    = None           # select stations with name reg.exp (dflt: all)
        self.ZipFile = False            # zip file for files > 4GB
        # no Period, period is taken from min - max sensor timestamps per regional sheet
        self.Period = None              # period date/time, e.g. YYYY-MM-DD,YYYY-MM-DD
        # By = 'owner,project'
        self.User = None                # user, author property
        self.Properties = {             # XLSX book properties
                "title": "Air Quality measurements information from RIVM/Things",
                # "subject":str         # names of regions
                # "author":str,         # user
                "category": "Air Quality measurements",
                # 'state':str,
                "keywords": "Air Quality, sensors, Particular Matter, NOx, NH3",
                "comments": f"{__license__}.;Created by {os.path.basename(__file__)} with Python and CSV (Pandas)",
                "generated": {datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S%Z')},
                "version": __version__,
              }

        # import class options (too many)
        for key,value in kwargs.items():
            if re.match('Verbosity',key,re.I):       # be more versatyle
                self.Verbosity = value
            elif re.match('Period',key,re.I): # defines local period Start/End
                if not type(value) is str or value.find(',') < 0:
                    raise ValueError(f"Period '{value}' has no comman to separate start,end")
                self.Period = value
            elif re.match('Sensors',key,re.I):       # only these sensors
                self.Sensors = self.Humanisation.DehumaniseSensor(value)
                if value.find(',') > 0:              # convert list to reg exp
                    self.Sensors = '(' + value.replace(',','|').replace(' ','') + ')'
            # separator to be used in multi dim convert to one dim dict
            elif re.match('Delim',key,re.I):         # separator sensor<Delim>Type
                    self.Delim = value
            elif re.match('Expand',key,re.I):        # expand with eg address, GPS
                self.Expand = value
            elif re.match('Select',key,re.I):        # selects only those station names (reg exp)
                self.Select = value
            elif re.match('Zip.*',key,re.I):         # zip file for spreadsheet >4GB
                self.ZipFile = True if re.match('true',value,re.I) else False
            elif re.match('UTF-?8',key,re.I):        # humanise with utf-8 chars
                # To Do: may need to support humaize without using utf-8 chars
                self.UTF8 = True if re.match('true',value,re.I) else False
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

        self.CSVfile = CSVfile if CSVfile else 'Things-Stations-Info'  # default file name
        if re.match(r'.*\.gz$',self.CSVfile,re.I): self.ZipFile = True # gzip output file
        self.CSVfile = re.sub(r'.csv(\.gz)?','', self.CSVfile,re.I)    # file name extention
        # collected Pandas dataframe series for output
        self.Stations = pd.DataFrame()               # pd.core.frame.DataFrame result
        # region names with list of collected station names
        self.Regions = dict()                        # {'regionI':[station1,..],..}
        if self.Verbosity:
            sys.stderr.write(f"Creating CSV {'(gzipped) ' if self.ZipFile else ''}file: '{self.CSVfile}.csv'\n")

    # to support 'with clause' Things2XLSX(): Generate Workbook c.q. Add Stations clause
    def __enter__(self):
       return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
       # convert self.Stations into CSV file
       if exc_type:
           raise exc_type(exc_value)
       elif not self.CloseWorkbook():
           raise IOError("ERROR failed to generate Samen Things CSV file {self.CSVfile}.")
       self.CSVfile = None
       self.Stations = pd.DataFrame()               # pd.core.frame.DataFrame free memory

    # add from list of tuples with region name and dict with info stations to xlsx sheet
    # period sheet is taken from min - max timestamps sensors
    def GenerateOutputFile(self, Regions:Union[list,dict]) -> bool:
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
           if self.Add_Stations(stations, RegionName=regionName, Period=None): # timestamps period
               regions.append(regionName)
           else:
               sys.stderr.write(f"Region '{regionName}': no stations found.'\n") 
       return(CloseWorkbook())

    # delete columns not matching names: Things ID, GPS, Select, Expand
    def FilterColumns(self, Dataframe:pd.DataFrame) -> None:
        # generate regular expression for matching column header names
        # Sensor filter
        if Dataframe.empty: return
        compiled = self.Sensors if self.Sensors else '(pm25|pm10|temp|rh|pres|nh3|no2)'
        if compiled.find(','): compiled = compiled.replace(',','|')
        if compiled:
            if not compiled[0] == '(': compiled = '('+compiled+')'
            compiled = [compiled+'.*']
        else: compiled = list()
        # Expand filter: filter on list of station properties, dflt: usual column names
        # default: extra info of stations from Things
        if self.Expand is None: self.Expand = 'location,address,owner,project'
        if self.Expand and self.Expand.find(',') > 0:
            self.Expand = self.Expand.replace(',','|')
        if self.Expand: compiled.append(self.Expand)
        compiled.append('Things ID|GPS')
        compiled = '^('+'|'.join(compiled)+')$'
        compiled = re.compile(compiled,re.I) # column names should match, drop others
        # TO DO: add sensorI<delim>[first,last,count,symbol,type] match
        dropping = [_ for _ in Dataframe.columns if compiled.match(_,re.I)]
        if dropping:
            if self.Verbosity > 2:
                sys.stderr.write(f"Dropping columns: {', '.join(dropping)}\n")
            Dataframe.drop(columns=dropping, inplace=True)

    # localise timestamps
    def Date2Local(self, Dataframe:pd.DataFrame) -> None:
        timestampColMatch = re.compile(r'.*(first|last)$')
        columns = list()
        for col in Dataframe.columns:
            if timestampColMatch.match(col):
                Dataframe[col] = self.Stations[col].apply(lambda x: x.strftime('%Y-%m-%d %H:%M') if type(x) is pd.Timestamp else None)
                columns.append(col)
        if self.Verbosity and columns:
            sys.stderr.write(f"Localized timestamps columns (Things header names): {', '.join(columns)}\n")

    # convert Pandas dateframe columns names into humanised names
    def HumaniseColHeaders(self, Dataframe:pd.DataFrame) -> None:
        humanised = dict()
        if Dataframe.empty: return
        for name in Dataframe.columns:
           if (humName := self.Humanisation.HumaniseSensor(name,Humanise=None)) != name:
               humanised.update({name: humName})
        if humanised:
            Dataframe.rename(columns=humanised,inplace=True)
            if self.Verbosity > 2:
                sys.stderr.write(f"Column headers renamed:\n")
                for _ in [f"'{x}' -> '{y}'" for x,y in humanised.items()]:
                    sys.stderr.write(f"\t{_}\n")

    # delete rows from series with index name not matching reg. exp self.Select
    def FilterRows(self, Dataframe:pd.DataFrame) -> None:
        # allow  only stations with names (reg.exp): default None
        if not self.Select or Dataframe.empty:
            return
        dropping = [_ for _ in Dataframe.index if not re.match(self.Select,_,re.I)]
        if dropping:
            if self.Verbosity > 2:
                sys.stderr.write(f"Skipping stations: {', '.join(dropping)}\n")
            Dataframe.drop(index=dropping, inplace=True)

    # timestamps in csv file are in local time
    # df['time'] = df['datetime'].apply(lambda x: x.strftime('%H%M%S'))
    # to do: add extra header info as e.g. period, version, generation date
    # mode append is not yet implemeted. Needs a keycheck and key ordering
    
    # CSV book creation: properties as comments, stations as (gzipped) CSV 
    # outpout example:
    #     # title: Air Quality measurements information from RIVM/Things
    #     # ...
    #     Things ID;@iot.id;owner;project;GPS;address;temperatuur @iot.id;temperatuur symbol;temperatuur first;temperatuur count;temperatuur last;temperatuur product;PM₂.₅ (gekalibreerd) @iot.id;PM₂.₅ (gekalibreerd) symbol;PM₂.₅ (gekalibreerd) first;PM₂.₅ (gekalibreerd) count;PM₂.₅ (gekalibreerd) last;PM₂.₅ (gekalibreerd) product;PM₂.₅ @iot.id;PM₂.₅ symbol;PM₂.₅ first;PM₂.₅ count;PM₂.₅ last;PM₂.₅ product;region;PM₁₀ @iot.id
    #     OHN_gm-2126;1234.0;Ohnics;GM;(5.938, 51.503);;;;NaT;;NaT;;;;NaT;;NaT;;42859.0;;NaT;;NaT;;TEST-region;42860.0
    #     OHN_gm-2136;8236.0;Ohnics;GM;(5.933, 51.474);Eijk 5, Veen, gem. Ven, prov. Lirg;42885.0;C;2023-10-05 08:00;9167.0;2024-10-28 12:00;DS18B20;42884.0;ug/m3;2023-10-05 08:00;9106.0;2024-10-28 11:00;Sensirion SPS030;42883.0;ug/m3;2023-10-05 08:00;9167.0;2024-10-28 12:00;Sensirion SPS030;TEST-region;
    #     ...
    def CloseWorkbook(self) -> bool:
        if not self.CSVfile: return False
        self.Properties.update({
                "subject": "Low-Cost stations in regions: " + ', '.join([_ for _ in self.Regions.keys()])})
        # clean up unwanted columns
        #self.FilterColumns(self.Stations)
        # allow only stations matching reg.exp names
        #self.FilterRows(self.Stations)
        self.Date2Local(self.Stations)
        # humanise column names with utf-8 names
        if self.UTF8: self.HumaniseColHeaders(self.Stations)
        # convert UTF Pandas timestamps to local timestamps strings YYYY-MM-DD HH:MM
        if self.Verbosity > 1:         # log index headers as collected and renamed
            sys.stderr.write(f"CSV headers: {', '.join(self.Stations.columns)}\n")
        # may need to convert timestamps
        self.CSVfile += '.csv'
        self.UTF8 = None if not self.UTF8 else 'utf-8'
        try:
            # add as comments the properties in header of the file
            with open(self.CSVfile, 'w', encoding=self.UTF8) as f_out:
                for key, value in self.Properties.items():
                    f_out.write(f"# {key}: {str(value)}\n")
            # https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html
            # DataFrame.to_csv(path_or_buf=None, sep=',', na_rep='', float_format=None,
            #           columns=None, header=True, index=True, index_label=None,
            #           mode='w', encoding=None, compression='infer', quoting=None,
            #           quotechar='"', line_terminator=None, chunksize=None,
            #           date_format=None, doublequote=True, escapechar=None,
            #           decimal='.', errors='strict', storage_options=None)
            self.Stations.to_csv(self.CSVfile, sep=';', header=True, index=True, mode='a', encoding=self.UTF8, date_format='%s')
            import os
            if self.ZipFile:
                import gzip
                import shutil
                with open(self.CSVfile, 'rb') as f_in:
                    with gzip.open(self.CSVfile+'.gz', 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                if os.path.exists(self.CSVfile):
                    os.remove(self.CSVfile); self.CSVfile += '.gz'
                else:
                    raise IOError(f"ERROR failed to write gzipped CSV file {self.CSVfile+'.gz'}")
            if self.Verbosity:
                sys.stderr.write(f"Created CSV file: {self.CSVfile}\n\tCSV properties:\n")
                if self.Verbosity > 1 and self.Properties:
                    sys.stderr.write('\TArchive properties:\n')
                    for p,v in self.Properties.items():
                        if v: sys.stderr.write(f"\t\t{p}:\t{v}\n")
                if self.Verbosity > 1 and self.Regions:
                    sys.stderr.write(f"\tRegions {', '.join([_ for _ in self.Regions.keys()])}\n")
                else:
                    for p,v in self.Regions.items():
                        sys.stderr.write(f"\tregion {p} with stations: {v}\n")

            return True
        except:
            sys.stderr.write(f"ERROR: failed to write generated CSV file '{self.CSVfile}'.\n")
            return False
    
    # convert Samen Meten Things dict with stations info (multi dimensional)
    #     stations dict { startion: station info dict, ... }
    #     to list of one dimension dict with station name, info attributes.
    # Make it ready to convert to e.g. CSV or Pandas dataframe
    # output:
    #     Pandas dataframe list with one dimensional dict's
    #       [ { 'Things ID':str,
    #       'GPS': [float,float],  #    'longitude':float, 'latitude':float,
    #       'address':str, 'owner':str, 'project':str,
    #       '<sensor-i> first':YYYY-MM-DDTHH:mm:ssZ, '<sensor-i> last:YYYY-MM-DDTHH:mm:ssZ,
    #       '<sensor-i> count':int, '<sensor-i> product':str, ... },
    #         { ... }, ... ]
    #   stations:dict: required keys:
    #         'Things ID', 'location':list[ordinates:list|tuple,address:str],
    #         other dict keys are optional:
    #           <sensor-i> name sensor with
    #               optional dict[str] keys: 'first', 'last', 'count', '@iot.id', 'product'
    def NormaliseDict(self, Stations:dict, RegionName:str=None) -> tuple:
        """ NormaliseDict: convert Samen Meten Things dict with stations info
            (multi dimensional) stations dict { station: station info dict, ... }
            to list of one dimension dict with station name, info attributes."""

        # recursive on the dict, to do: allow not hashable keys
        # output { key(str): non dict value, ...}, example:
        #     [ {'Things ID': 'OHN_gm-2136', '@iot.id': 8236,
        #       'project': 'GM', 'owner': 'Ohnics',
        #       'GPS': (5.933, 51.474), 'address': 'Eijk 5, Veen, gem. Ven, prov. Lirg'],
        #       'temp @iot.id': 42885, 'temp symbol': 'C', 'temp product': 'DS18B20',
        #       'temp first': '2023-10-05T08:00:00.000Z', 'temp count': 9167, 'temp last': '2024-10-28T12:00:00.000Z',
        #       'pm25_kal @iot.id': 42884, 'pm25_kal symbol': 'ug/m3',
        #       'pm25_kal first': '2023-10-05T08:00:00.000Z', 'pm25_kal count': 9106,
        #       'pm25_kal last': '2024-10-28T11:00:00.000Z',
        #       'pm25_kal product': 'Sensirion SPS030', 'pm25 @iot.id': 42883,
        #       'pm25 symbol': 'ug/m3', 'pm25 product': 'Sensirion SPS030',
        #       'pm25 first': '2023-10-05T08:00:00.000Z', 'pm25 count': 9167, 'pm25 last': '2024-10-28T12:00:00.000Z',},
        #     ...]
        def OneDimDict(newDict:dict, oldDict:dict, keyName:str=None) -> None:
            # datetime strings and location info is handled as special case.
            # TO DO: check if datetimes per sensor are in period: if not skip station
            for idx, value in oldDict.items():
                if not type(value) is dict:
                    if type(value) is str:
                        # convert to type pd._libs.tslibs.timestamps.Timestamp UTC
                        # in CSV one would check on datetime type and convert to local
                        if re.match(r'20\d\d-\d\d-\d\d[T\s][\d:\.]*Z',value):
                            value = pd.to_datetime(value)
                        elif re.match(r'20\d\d-\d\d-\d\d',value):
                            value = local_to_panda(idxSTV, tz=datetime.timezone.utc)
                    # location key is split into GPS and address
                    if type(value) is list and value and re.match(r'(location)$',idx,re.I):
                        # value = [(long:float,lat:float),address:street nr,town,municipal,state]
                        if value[0]:        # GPS to grid of max 5 decimals (ca 1 meter)
                            newDict['GPS'] = (round(float(value[0][0]),3),round(float(value[0][1]),3))
                            #newDict['longitude'] = round(float(value[0][0]),3)
                            #newDict['latitude'] = round(float(value[0][1],3))
                        # address may have region name e.g. zip code, urban name, etc.
                        try:
                            if value[1]: newDict['address'] = value[1]
                        except: pass
                        continue
                    newDict[str(idx) if not keyName else keyName+self.Delim+str(idx)] = value
                    continue
                OneDimDict(newDict, value, keyName=('' if not idx or re.match(r'^(sensors?)',str(idx),re.I) else str(idx)))

        stations = list()
        # 'normalise' a multi dimensional dict, format: <prev key>space<key>:value
        for station, info in Stations.items():
            if not station or not info: continue
            flattened = dict()
            OneDimDict(flattened,info)
            if flattened:   # add station name to dict
                flattened['Things ID'] = station
                if RegionName: flattened['region'] = RegionName
                stations.append(flattened) # add one dim dict to list of stations
        return stations
    
    # Add_Stations({'stationNameN': {station info), ...}, ...}, regionName, period)
    #             OR list of normalized (simplified) dict's
    #            ([{'Station ID':str,infoType:value,...     ], regionName, period)
    # convert (normalised) Things dict to Pandas dataframe series
    # TO DO: add region name of stations to the series?
    # Add_Stations() add station to self.Stations Pandas dataframe series
    # Filtering: only stations with observation timestamps in Period.
    def Add_Stations(self,Stations:dict,RegionName:str=None,Period:str=None) -> bool:
        """Add_Stations from Samen Meten Tools dict or list of discts
        with station info
        add to Pandas dataframe series collection
        for an archive CSV file with low-cost station information"""

        stations = list()
        if type(Stations) is dict:
            stations = self.NormaliseDict(Stations,RegionName)
        elif type(Stations) is list:
            stations = Stations
        # we have one dimensional list of dicts with station info
        # [ {'Station ID':str,'GPS':value,'address':str,...,'SensorI first':value,...} ]
        if not type(stations) is list:
            raise ValueError("Error: data is not a Things dictionary")
        if not len(stations):
            sys.stderr.write(f"Unable to find stations in the region {RegionName if RegionName else 'no region name defined'}. Skipped.")
            return False
        if self.Verbosity > 0:
            sys.stderr.write(f"Found {len(stations)} stations in region {RegionName if RegionName else 'no region provided'}\n")

        # skip station if station dict is not conformant or not in period active
        period = ParsePeriod(Period)
        if not type(period) is list: period = [pd.NaT,pd.NaT]
        for row, station in enumerate(stations):
            # check if records are conformant and complete
            if not type(station) is dict or not station:
                stations[row] = {}; continue
            if not station.get('Things ID'):
                sys.stderr.write(f"Station dict '{str(station)}' is not conformant. Skipped.\n")
                stations[row] = {}; continue
            if not station.get('GPS'):
                sys.stderr.write(f"Warning: GPS location unknown for station '{str(station)}'. Skipped.\n")
                stations[row] = {}; continue
            first = pd.NaT; last = pd.NaT
            # dehumanise all sensor names in this station dict
            for key, value in station.items():
                if re.match(r'.*'+self.Delim+'(first|last)$',key): # timestamp
                    if type(value) is str: # convert to datetime stamp
                        try: value = local_to_panda(value)
                        except: value = pd.NaT
                        station[key] = value
                    if value is pd.NaT: continue
                    if re.match(r'.*'+self.Delim+'first$',key):
                        if first is pd.NaT: first = value
                        else: first = min(first,value)
                    if re.match(r'.*'+self.Delim+'last$',key):
                        if last is pd.NaT: last = value
                        else: last = max(last,value)
            # skip stations not active in period
            if not first is pd.NaT and not type(period[1]) is type(pd.NaT) and first > period[1]:
                if self.Verbosity: save = stations[row].copy() # remember for next warning
                stations[row] = {}
            elif not last is pd.NaT and not type(period[0]) is type(pd.NaT) and last < period[0]:
                if self.Verbosity: save = stations[row].copy() # remember for next warning
                stations[row] = {}
            if self.Verbosity and not stations[row]:
                sys.stderr.write(f"Warning skip station '{save}': not in period\n")
                del save

        # remove from series not relevant stations
        stations = ListDictToSeries(stations, Indexed='Things ID', Rename=None, Sort=True)
        if stations.empty or stations is None:
            if self.Verbosity:
                sys.stderr.write(f"Region {RegionName} has no stations with info data.\n")
            return
        # filter columns names and row index. Clean up unwanted columns and rows
        self.FilterColumns(stations)
        # allow only stations matching reg.exp names
        self.FilterRows(stations)

        # maintain list of regions.
        self.Regions.update({(f"region {len(self.Regions)+1}" if not RegionName else RegionName): ','.join(stations.index)})
        self.Stations = ConcatSeries(self.Stations,stations,Unique=True, Sort=False)

    # ========================= end routine stations to generate CSV archive
    
# ==========================================================================
# ===================== main

########### command line tests of (class) subroutines or command line checks
# CLI options: help, debug, verbosity=N,
#              properties: title=Name, company=X, user=X, company=X, status=X
#              period to select stations from Things
#              period=YYYY-MM-DD HH:MM,YYYY-MM-DD HH:MM or auto detect
#              sensors and expand use names as defined by Samen Meten API
#              sensors=comma separeted list of Things sensor names pm25,no2,..)
#                     sensor names may be humanised names,
#                     e.g. PM₂.₅,NO₂, see SamenMetenThings
#              expand=comma separated list of extra info
#                     e.g. address, owner, project, (sensor) product, symbol
# yet implemented here: Things API info (dict), json, normalised dict towards csv. 
if __name__ == '__main__':
    OutputFile = ''                      # CSV archive file name
    DEBUG = False                        # use internal test regional dict
    Verbosity = 0                        # verbosity level
    Period = None                        # only stations active in period start,end
    Kwargs = dict()                      # class options
    Output = None                        # default output test file name
    Regions = list()                     # list of region names collected from args

    def help() -> None:                  # print some help information
        sys.stderr.write(f"""
            NOT ALL GENERATION FUNCTIONS ARE IMPLEMENTED YET.
Command examples:
    Do a test:
        {os.path.basename(__file__)} DEBUG (test data or use help.)
    Create map with stations info for stations in munipality from source RIVM Things:
        {os.path.basename(__file__)} Land\ van\ Cuijk File=Land\ van\ Cuijk.html
    Create archive file from CSV file and JSON archive into one CSV archive:
        {os.path.basename(__file__)} Venray 'Land van Cuijk.json.gz'  Sensors='pm10,pm25'

General command options:
    --help|-h                    Print this help.
    Verbosity={Verbosity}        Verbosity level. Level 5 gives timings info.
    DEBUG                        Internal debug data.
    --version|-v                 Print version: {__version__}

Output is XLSX|CSV|JSON formatted file. Use File='Your achive file name' to change this.
Filename extension '.csv' or '.csv.gz' is automatically added to the file name.

The class module generates an overview of low cost stations in regions 
in CSV format: ';' (dflt) separated list of low-cost stations. With '#' properties lines.
Per csv record station info with fields (if available) as:
    location (GPS, address),
    station properties (owner,project, municipality code, ref codes), and
    sensors installed (sensor type, first-last record timestamp, record count, unit, product type) in a period.

Options for the output generation:
    ZipFile=False compress the output file. Zip the CSV file.
    File|Output=OutputfileName. Default '<RegionName>.csv' or 'Things-Stations-Info.csv'.

Options for property settings of the archive file (record line starts with '#'):
    Title=YourTitle               Default: some string.
    Company=YourCompanyName       Default empty.
    BookStatus=status             Default 'draft'.
    User|Author=MyName            Owner of the info. Dflt: login name.

Options to filter data information domains:
    Sensors='(pm25|pm10|temp|rh|pres|nh3|no2)' Only these sensor names.
    Expand='location,address,owner,project'    Only these extra information.
    Expand may have: symbol, product           (not tested)
    Select='.*'                                Reg exp. only these stations. Dflt: all
    Delim=' '                                  Delimeter used in normalize multi dim dict.
    Period=datetime start,datetime end string default: empty (use sensor timestamps)
    Period=None                                Only stations active in period.
    For period timestamp the Python time parser is applied to understand human expressions,
    this is language dependant (e.g. 'yesterday,now' or 'gisteren,vandaag').
""")
        exit(0)

    for arg in sys.argv[1:]:
        if re.match(r'^--*h(elp)*$',arg,re.I): help()

        # class options definitions
        if m := re.match(r'^(--)?([^\s]*)\s*(=)\s*([^\s]+.*)$', arg):
          if m.groups()[2] == '=':
            if re.match('Verbos',m.groups()[1],re.I):       # verbosity level
                Verbosity = int(m.groups()[3].strip())
            elif re.match('(Output|File)$',m.groups()[1],re.I): # output XLSX file name
                OutputFile = re.sub(r'\.xlsx','',m.groups()[3].strip(),re.I)
            elif re.match('Hide',m.groups()[1],re.I): pass  # only for XLSX output
            # options type properties
            elif re.match('Title$',m.groups()[1],re.I):     # base name of archive
                Kwargs.update({'Title': m.groups()[3].strip()})
            elif re.match('Company$',m.groups()[1],re.I):   # company 
                Kwargs.update({'Company': m.groups()[3].strip()})
            elif re.match(r'(User|Author)',m.groups()[1]):  # user of created file
                Kwargs.update({'Author': m.groups()[3].strip()})
            elif re.match('Bookstate',m.groups()[1],re.I):  # status of archive
                Kwargs.update({'Bookstate': m.groups()[3].strip()})
            # options type info fields filtering
            # date/time period and station info selections
            elif re.match('Sensors$',m.groups()[1],re.I):   # sensor types of interest (reg exp)
                Kwargs.update({'Sensors': m.groups()[3].strip()})
            elif re.match('Delim$',m.groups()[1],re.I):     # delimiter used in normalize dict
                Kwargs.update({'Delim': m.groups()[3].strip()})
            elif re.match('Expand$',m.groups()[1],re.I):    # show station property info as well
                Kwargs.update({'Expand': m.groups()[3].strip()})
            # to collect station info from Samen Meten Tools get regional stations
            elif re.match('Select$',m.groups()[1],re.I):    # filter reg exp for stations names
                Kwargs.update({'Select': m.groups()[3].strip()})
            continue
        # options type script handling
        elif re.match(r'^((--)?debug|-d)$',arg,re.I):       # DEBUG use buildin station dict
            DEBUG = True; Verbosity = 3
            continue
        elif re.match(r'^(--*v(ersion)*)$',arg):            # print version and exit
            sys.stderr.write(f"{__version__}\n")
            exit(0)
        Regions.append(arg)
    if Verbosity:
        Kwargs.update({'Verbosity': Verbosity})
    
    # function to detect delays
    # progress metering,
    # it is teatime music: every station can take about 15-90 seconds download time
    def progress(Name,func,*args,**kwargs):
        from threading import Thread
        thread = Thread(target=func, args=args, kwargs=kwargs)
        #thread.setDeamon(True)                              # P 3.10+: thread.deamon(True)
        thread.start()
        teaTime = time()
        while thread.is_alive():
            secs = time()-teaTime; mins = int(secs/60); secs = secs-(mins*60)
            mins = f"{mins}s" if mins else ''
            sys.stderr.write(f'Busy downloading for {Name} from Things API: {mins}{secs:.1f}s\r')
            sleep(0.1)
        thread.join()
        sys.stderr.write(f'Download {Name} from Samen Meten Things done in {mins.replace("m"," minutes ")}{int(secs)} seconds' + ' '*40 + '\n')
    
    # check if file is json file with Samen Meten Things dict
    # To Do: needs some more work of data acceptance
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
                        for _ in _.keys(): # this needs to be extended: unit, product
                            if re.match(r'(sensors|owner|project|location)',_):
                                _ = None; break # rely there is not a None key
                        if _: data = None
                    else: data = None
                else: # (gzipped) CSV file, to do
                    sys.stderr.write(f"CSV file '{filename}' not yet supported. Skipped.\n")
                    return None
            except: pass
            if type(data) is dict: return data
            if type(data) is list:
                for _ in data:
                    if not type(_) is dict: return None
                return data
            return None
        return filename  # it is not an archive file

    # obtain low-cost stations info for a region (municipality, stations neighbouring
    # a station or GPS location oor list of stations via
    # Samen Meten Things API database website qry.
    # result: Pandas dataframe dict(station name:station info). See DEBUG as example.
    import dateparser                      # check time period with Python dateparser
    def GetStationInfo(RegionName:str, **kwargs) -> tuple:
        """GetStationsInfo(str: municipality, or list of (GPS or station ID's),
        options Period (Start,End) may use Unix date command to get dateformat,
        Things class (sensors,product type, human readable sensor types, sensors status (first/last, count in period)
        """
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

    if DEBUG:                # just some test data
        # dict with stations is either:
        #     multi dimensional dict as : {'stationNameI': {info key: value, ...}, ...}
        #     or (e.g. 'Sensor': { sensID: {'first': dt, ...}, ...} is mapped into
        # One dimensional items: 'SensID<DELIM>first': dt, 'SensID<DELIM>@iot.id': value, ...
        #     one dimensional dict, a normalized dict: {'Things ID':str, ...}
        Regions = [('DEBUG-test-stations',{
         'OHN_gm-2136':
             {   '@iot.id': 8236, 'owner': 'Ohnics', 'project': 'GM',
                 'location': [(5.933, 51.474), 'Eijk 5, Veen, gem. Ven, prov. Lirg'],
                 'sensors': {
                    'temp': {'@iot.id': 42885, 'symbol': 'C', 'first': '2023-10-05T08:00:00.000Z', 'count': 9167, 'last': '2024-10-28T12:00:00.000Z', 'product': 'DS18B20'},
                    'pm25_kal': {'@iot.id': 42884, 'symbol': 'ug/m3', 'first': '2023-10-05T08:00:00.000Z', 'count': 9106, 'last': '2024-10-28T11:00:00.000Z', 'product': 'Sensirion SPS030'},
                    'pm25': {'@iot.id': 42883, 'symbol': 'ug/m3', 'first': '2023-10-05T08:00:00.000Z', 'count': 9167, 'last': '2024-10-28T12:00:00.000Z', 'product': 'Sensirion SPS030'}}},
         'OHN_gm-2138':
             {  '@iot.id': 8238, 'owner': 'Ohnics', 'project': 'GM',
                'location': [(6.087, 51.511), 'Hoofd 4, Meer, gem. Horst, prov. Limburg'],
                'sensors': {
                    'temp': {'@iot.id': 42891, 'symbol': 'C', 'first': '2023-10-05T08:00:00.000Z', 'count': 9160, 'last': '2024-10-28T11:00:00.000Z', 'product': 'DS18B20'},
                    'pm25_kal': {'@iot.id': 42890, 'symbol': 'ug/m3', 'first': '2023-10-05T08:00:00.000Z', 'count': 9096, 'last': '2024-10-28T11:00:00.000Z', 'product': 'Sensirion SPS030'},
                    'pm25': {'@iot.id': 42889, 'symbol': 'ug/m3', 'first': '2023-10-05T08:00:00.000Z', 'count': 9160, 'last': '2024-10-28T11:00:00.000Z', 'product': 'Sensirion SPS030'}}},
        'OHN_gm-2126':
           {   '@iot.id': 1234, 'owner': 'Ohnics', 'project': 'GM',
               'location': [(5.938, 51.503)],
               'sensors': {
                   'temp': None, 'pm10': {'@iot.id': 42860}, 'pm25': {'@iot.id': 42859}}},
        'OHN_gm-2216':
           {    'owner': 'niks', 'project': 'Palmes',
                'sensors': {
                    'rh': None, 'pm25': {'@iot.id': 42859},
                    'no2': {'@iot.id': 42860, 'first': '2023-10-05T08:00:00.000Z', 'count': 10, 'last': '2024-07-30T08:00:00.000Z','product':'Palmes'}}}
          },None)]  # full period 
        OutputFile = 'DEBUG-test-stations'

    if not Regions: help()
    if not OutputFile:
        if len(Regions) == 1 and re.match(r'[\s\w\./-]+$',Regions[0]):
            # only one name: use the region name as output file name
            OutputFile = re.sub(r'\.[jsoncvxl]{3,4}(\.gz)?','',Regions[0],re.I)
        else: OutputFile = 'Things-Stations-Info'  # default file name

    # generate CSV file (';' separated records,    # comment line with file properties)
    # with stations information per region.
    with Things2CSV(OutputFile, **Kwargs) as Convert2CSV:
        # collect regions with stations from archive or Samen Meten Things website
        for region in Regions:
            if not DEBUG:
              # if input is from file, get the data
              if type(data := FileIsThingsArchive(region)) is dict or type(data) is list and data:
                region = (re.sub(r'\.(json|csv)(\.gz)?$','',region, re.I),data,None)
              elif not data:  # error opening archive file
                sys.stderr.write(f"Things archive file '{region}' reading or format error. Skipped.\n")
              else:   # region name: get stations of that region from Samen Meten API
                try:
                    # next can take a while. To Do: use progress metering if Verbosity?
                    # if Verbosity: progress(Name,GetStationInfo,region,Kwargs)
                    item =  GetStationInfo(region,**Kwargs)
                    if not type(item[1]) is dict:
                        sys.stderr.write(f"Failed to get stations info from Samen Meten API for region '{region}'. Skipped.\n")
                        continue
                    else:
                        region = (item[0],item[1],item[2])
                    # args: region name:str, stations:dict, period list[datetime,datetime]
                except:
                    sys.stderr.write(f"Error to get stations in region '{region[0]}'. Skipped.\n")
                    continue
            # region[1] is (normalized?) dict, region[1] name region
            # only with timestamps in this period: region[2] is period
            # add stations from dict to Pandas dataframe series
            Convert2CSV.Add_Stations(region[1],RegionName=region[0],Period=region[2])
