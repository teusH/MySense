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
Python3.8+ library script to download Things (Samen Meten API) station information and observations.
Returns station info (location, sensors, types, status, station neighbours, etc.) in a dictionary,
and sensor observations as Pandas dataframe.
As well stations near a location point or station name, or stations within a municipality.
As external website queries (Things, Open Soft Data, Open Street Map, TOOI) consume a lot of time,
multi threading can be used for a speedup factor of 2-5.
The module can be called stand alone. Try 'python3 ModuleName help'.

Hint: keep your development area clean by: export PYTHONDONTWRITEBYTECODE=1

Some example of routines:
StreetMap(GPS:Union[str,tuple]) -> str # obtain address via Open Street Map
Municipality_NameCode(item:Union[str,int]) -> str # municipality info via standaarden overheid (TOOI)
MunicipalityName(item:Union[str,int], region="gemeente") -> str # municpality info via Open Data Soft
Class SamenMetenThings:                # Things API query routines
                                       # station names in a municipality
def get_SensorStatus(self, Stations:dict, Start=None, End=None) -> None:
    def get_StationsInfo(self,Region:Union[int,str],Data:List[dict],Sensors:Union[str,re.Pattern]=None,Select:Union[str,re.Pattern]=None, PropSelect:List[str]=[]) -> dict:
    def InfoFromNeighboursList(self,Names:List[Union[str,int]], Region:int=None, By:str="id,name", Select:Union[str,re.Pattern]=None, Sensors:Union[str,re.Pattern]=None, Start=None, End=None) -> dict
    def get_InfoNeighbours(self,Name:Union[str,int,List[Union[str,int]]], Region:int=None, By:str="id,name", Select:Union[str,re.Pattern]=None, Sensors:Union[str,re.Pattern]=None, Start=None, End=None) -> dict
    def get_ThingsObservations(self, Iotid:int, Start:Any=None, End:Any=None, Timestamp:str="phenomenonTime", Result:list=["result"],Data:Any=None,Key:Any=None) -> Union[pd.core.frame.DataFrame,None]
    def get_Neighbours(self,Point:Union[str,List[float]],Range:int=None,Max:int=50,Select:str=None, Address:bool=None) -> Dict[str,tuple]
    def get_StationInfo(self, Name:str, Address:bool=None, Neighbours:Union[int,bool]=None, Sensors:str=None, Start:Any=None, End:Any=None) -> Dict
    def get_StationData(self, Name:str, Address:bool=None, Humanise:bool=None, Start:Any=None, End:Any=None, Sensors:str=None, Neighbours:bool=None) -> Dict[str,Any]

    To Do: add properties info (meta info about output generated) as tiltle, subject, owner, version,etc.
"""

#
# Obtains Samen Meten Things station observations with meta info and data (Pandas dataframe),
# station neighbours station names with optionally location and address, stations in municipality.
# Makes use of Samen Meten Things V1.0 RIVM query webservice,
# Open Street Map and Open Data Soft.
# Various webservices will differ on speed and amount of detail requests.
# Observation data requests can run in parallel (multithreading).
# Verbosity amount is leveled. Verbosity will switch on download progress meter.
#
# Tested with Python3.8+ Use of Python Typing 3.8+
# Zuinige Rijder and GOMmers (Geërgerde Ouwe Mannen): thanks for your ideas and input.
#
# Uses public web API query services:
#     https://api-samenmeten.rivm.nl/v1.0   Internet of Things
#     https://nominatim.openstreetmap.org/  Maps and locations
#     https://public.opendatasoft.com/      Open Data access
#     https://opendata.cbs.nl/              Open governmental statistical database access
#
# Use of webservices can be anonimised (http proxying).
# Reminders:
# PM source detection:
# https://www.awgl.nl/images/projecten/2020/GCN/Handreiking_GCN_project_2020.pdf
# For meteo observations see:
# https://developer.dataplatform.knmi.nl/edr-api KNMI Developer Portal
# API access requires an API key. The API architecture is similar as RIVM Things API.
# Docs geoPandas: https://geopandas.org/en/stable/getting_started.html

import os,sys
__version__ = os.path.basename(__file__) + " V" + "$Revision: 4.6 $"[-5:-2]
__license__ = 'Open Source Initiative RPL-1.5'
__author__  = 'Teus Hagen'

# library modules dependencies
# TO DO: add more and better typing and decorate (less transperant) support:
#        https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html
from typing import Any,Union,Dict,List,Callable  # if Python 3.8
import re                               # handling regular expressions
import datetime                         # used for timestamping
import pandas as pd                     # used for observation dataframes
from threading import Semaphore, Thread # used when threading mode is turned ON
from time import time, sleep            # used with threading, and time debugging
import logging                          # use logging facility, warn if needed.

# ================                      = time conversion routines
# No need for?: import aiohttp $ pip install aiohttp[speedups] and use it with http requests
from functools import lru_cache         # caching function results
#

# ====================               = timestamp conversion routines
# there is a war of Python programming, time, and time conversion styles
# convert humanised date-time to ISO8601 UTC e.g. "month ago" 
# uses 'date' command for conversion humanised date strings to digital timestamps
# TO DO: extend with needed date/time format
def date2ISOutc(string:str) -> str:     # just for the fun
    """local time stamp convert to ISO utc timestamp.
       External CLI date is used to convert humanised stamp (e.g. 'yesterday') to utc stamp."""
    timing_re = re.compile(r'^[0-9]{4}-[01][0-9]*-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]Z$')
    if timing_re.match(string): return int(string)
    import dateparser                   # convert human readable time to datetime format
    from dateutil import tz             # convert local datetime to UTC datetime
    try:
        string =  dateparser.parse(string)
        if not type(string) is datetime.datetime:
            raise(f"Unix date {string} failure. Check LANG env. variable setting.")
        string = datetime.datetime.strftime(string.astimezone(tz.UTC),"%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        sys.exit(f"Date parse failure on {string}")
    if string:
        if timing_re.match(string): return string
    raise ValueError(f"Date conversion error on {string}")
#
# test: date2ISOutc('now') or date2ISOutc('1 Feb 2023')

#from time, datetime, ISO conversion coroutiness
def datetime_iso8601(date:datetime) -> str:
    """datetime_iso8601: convert utc datetime to ISO8601 string"""
    return datetime.datetime.strftime(date, "%Y-%m-%dT%H:%M:%SZ")

# local time string, add hh_mm and handle end inclusion time on end period
def YYYYMMDD(yyyymmdd:str) -> str:
    """convert YYYY-MM-DD formated stamp to YYYY-MM-DD HH:MM:SS"""
    if not type(yyyymmdd) is str: return yyyymmdd
    if re.match(r'[0-9]{4}-[01][0-9]*-[0-3][0-9]$', yyyymmdd):
        date = YYYYMMDD(yyyymmdd +' 00:00:00')
    elif re.match(r'[0-9]{4}-[01][0-9]*-[0-3][0-9]\s[0-2][0-9]:[0-5][0-9]$', yyyymmdd):
        date = YYYYMMDD(yyyymmdd + ":00")
    else:
        date = yyyymmdd
    return date

# convert local time to Pandas utc time ISO8601
def local_to_pandas(local:str, tz:str='UTC') -> pd._libs.tslibs.timestamps.Timestamp:
    """local_to_pandas: ISO UTC convert local date string to Pandas timestamp"""
    date = pd.to_datetime(YYYYMMDD(local)).tz_localize(tz='Europe/Amsterdam')
    if not tz: return date
    else: return date.tz_convert(tz=tz)

# convert to simple local humanised timestamp
def pandas_to_local(utc:datetime) -> str:
    """pandas UTC timestamp to local timestamp string"""
    date = utc.tz_convert(tz='Europe/Amsterdam')
    return datetime.datetime.strftime(date, "%Y-%m-%d %H:%M")

# TO DO: ISOstamp_to_PandaStamp

# returns with the help of a decorated function YYYY-MM-DDTHH:MMZ UTC timestamp
def local2ISOstamp(func) -> str:
    def timestamp(*args, **kwargs):
       # check if already ISOtimestamp
       if re.match(r'[0-9]{4}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]Z$',args[0]):
           return args[0].replace('Z',':00Z')
       elif re.match(r'[0-9]{4}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z$',args[0]):
           return args[0]
       if not re.match(r'[0-9]{4}-[01][0-9]*-[0-3][0-9](\s[0-2][0-9]:[0-5][0-9])?$',args[0]):
           return date2ISOutc(args[0])
       UTCstamp = local_to_pandas(func(*args, **kwargs))
       return datetime.datetime.strftime(UTCstamp, "%Y-%m-%dT%H:%M:%SZ")
    return timestamp

# converts any string representing some date/time
# returns: ISO8601 UTC in YYYY-MM-DDTHH:MM:SSZ timestamp format
@local2ISOstamp   # the world of ease and transparant programming
def ISOtimestamp(string:str) -> str:
    return YYYYMMDD(string)
#
# test: ISOtimestamp("2024-06-01") or ISOtimestamp("tomorrow")

# ================                      = make it human readable: humanise routines
# convert header names to Things header names, visa versa to humanised names
class HumaniseClass:
    """HumaniseClass: (de)humanise sensor strings"""
    def __init__(self, utf8:bool=False) -> None:
        self.utf8 = utf8  # use of utf-8 symbols can be turned off
        self.chr2utf8 = {
            '0': u'\u2080', '1': u'\u2081', '2': u'\u2082', '3': u'\u2083',
            '4': u'\u2084', '5': u'\u2085', '6': u'\u2086', '7': u'\u2087',
            '8': u'\u2088', '9': u'\u2089', 'X': u'\u2093',
            'C': u"\u2103", 'ug/m3': u"\u03bcg/m\u00b3", 'hPa': u"\u3371",
        }
        self.utf82chr = {}
        self.sense = r'((o|no|nh|co|pm)([0-9x])([\\.,])?([0-9])?)' # Things sensor naming style
        return None

    # convert to humanised sensor type. Some spreadsheets may not handle utf-8!
    def HumaniseSensor(self, name:str, Humanise:bool=False) -> str:
        """HumaniseSensor: convert a bare sensor string into human readable thing"""
        if Humanise is None: Humanise = self.utf8
        name = name.replace('_kal', ' (gekalibreerd)' if Humanise else ' kal')
        name = re.sub('pres','luchtdruk',name,re.I)     # pres?
        name = re.sub('temp','temperatuur',name,re.I)   # temp?
        name = re.sub('r[hv]%?','RH',name,re.I)         # percentage is deprecated
        name = re.sub('pm25','pm2.5',name,re.I)         # 2,5?
        name = re.sub('hpa','hPa',name,re.I)            # pres symbol

        # uppercase sensor names
        def UPPER(match:re.Match) -> str:
            _ = match.group(0).upper()
            return _

        name = re.sub(r'\b'+self.sense+r'\b',UPPER,name,re.I)
        if not self.utf8: return name # use  utf-8 coding?
        # convert subscripts PM₁₀, PM₂.₅, etc. and unit symbols ℃  μg/m³  ㍱
        match = re.findall(r'\b'+self.sense[:-1]+r'|(ug/m3|C|hPa))\b',name,re.I)
        if not match: return name
        for item in match: # list of tuples e.g. ('PM2.5', 'PM', '2', '.', '5', ''), ...
            try:
                if not item[0]: continue # assert tuple is not None or empty
            except Exception: continue
            if item[0] == 'PM2.5': item = ('PM2.5', 'PM', '2', '.', '5') # patch
            utf8 = ''
            for _ in item[1:]:
                if _: utf8 += self.chr2utf8.get(_,_) # convert
            name = name.replace(item[0],utf8)
        return name

    # convert names to Things IoT sensor namings e.g. pm25_kal ug/m3 (SPS30)
    # strict=True will convert to bare Things sensor and/or symbol names
    def DehumaniseSensor(self, name:str, strict:bool=True) -> str:
        """DehumaniseSensor: convert a humanised sensor string into a bare string"""
        if not self.utf82chr: # poor man's utf-8 decoding
            for item,utf8 in self.chr2utf8.items():
                if len(utf8) == 1: self.utf82chr[utf8] = item
            self.utf82chr.update({u'\u03bc': 'u', u'\u00b3': '3'})
        for chr in set(re.findall(r'['+''.join(self.utf82chr.keys())+r']', name)):
            if chr: name = name.replace(chr,self.utf82chr.get(chr,chr))
        name = name.replace('luchtdruk','pres',re.I)
        name = name.replace('temperatuur','temp',re.I)
        name = re.compile(r'\s*\(?\s(ge)?[kc]al(ibreerd)?\)?').sub('_kal',name)
        name = re.compile(r'%?rh%?',re.I).sub('rh',name)       # perc deprecated
        name = re.compile(r'pm2[,\.]5',re.I).sub('pm25',name)  # comma deprecated
        m = re.match(r'\b(((o|no|nh|co|pm)[0-9x][0-9]?|pres|rh)(_kal)?)\b',name,re.I)
        if not m: return name
        if strict: return m.group(0).lower()
        else: return name.replace(m.group(0),m.group(0).lower())
#
# tests: HumaniseClass = HumaniseClass(utf8=True)
#        for name in ["pm25","pm25_kal","rh","pres","temp","ug/m3","C","%","hpa",
#                     "pm25_kal ug/m3 (SPS30)", "nox ppm", "pres hPa"]
#           name1 = HumaniseClass(utf8=True).HumaniseSensor(name)
#           name2 = HumaniseClass.DehumaniseSensor(name1,strict=True)
#           print(f"{name} -> {name1} -> {name2}")

# ================                = from MyWorekers.py wrapper ThreadWorkersPool Class
#from time import time
#from typing import Callable,Any,Union,Dict,List
#import numpy as np
#import logging
# class of workers with threads to download website query results
from threading import Semaphore
# disclaimer: python  decorators and threadgroups: my penny has not yet dropped.
# for tests see MyWorkersTest.py
from concurrent import futures

class MyWorkers:
    __version__ = "MyWorkers " + "Revision: 2.2 $"[-5:-2]
    __license__ = 'Open Source Initiative RPL-1.5'

    """A wrapper for threadpool class for ease result and exception handling.
       alternative Thread Group implementation.
       Using function aim (buffering): no collection of results is needed.
       Makes use names and results in buffers (lists or dict).
       Submit will start thread, Wait4Workers will close Thread Group.
       If MaxWorkers < 2 no threading will take place.
       Timing will turn thread time metering on."""

    # trick to get names per submitted Thread in the pool
    # the worker result problem: bind identity with worker and thread
    def __init__(self, WorkerNames:str='SamenMetenThread', MaxWorkers:int=4, Timing:bool=False):
        self.WorkerNames = WorkerNames
        if MaxWorkers > 1:
            self.Executor = futures.ThreadPoolExecutor(max_workers=MaxWorkers,thread_name_prefix=WorkerNames,)
        else: self.Executor = None    # else (debugging modus) no threading
        self.Futures = {}             # dict with futures as key, submit id
        self.Results = {}             # dict with results of the thread when done
        self.Number:int = -1          # count of submitted thread routines
        self.Stamp = Timing           # timing threads
        self.Metering:float = None    # start timestamp of first worker
        self.SemaBaskit = Semaphore() # semaphore for Baskit handling

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_val, trace):
        self.Shutdown()
        if not exception_type is None:
            logging.warning(f"{self.WorkerNames}: a thread raised exception {exception_type}, reason '{str(exception_val)}'.")

    # This may cause race conditions: wait the use till executor has finished!
    # Parameters: thread identification, thread worker info: result, exception, bvaskit, timing, nr
    # Results: complete self.Results[Ident] with thread result info, 
    #          if Baskit not None: forward results to Baskit and only info in self.Results[Ident].
    #          callback arg { 'ident', 'result', or 'except'}.
    def _WorkResult(self, Ident:str, Result:Any=None, Baskit:Union[dict,list,Callable]=None, Except:Any=None, teaTime:float=None, Nr:int=None) -> None:
        """add worker result and info to self.Results and result to baskit (object or call back).
           Make sure before using results till executor has finished!"""

        self.Results.update( {Ident:{}})
        if not Nr is None: self.Results[Ident]['nr'] = Nr # subject to be decripated
        if self.Stamp and not teaTime is None:
            self.Results[Ident]['timing'] = teaTime # not exact time metering thread
            teaTime =f"\n\tmetering: ca {round(teaTime,1)} seconds"
        else: teaTime = ''
        # thread result handling: if Baskit is defined Result is forwarded in Baskit
        if Except is None and not Result is None:  # thread result (if Result is None?)
          # next can be more fine graded towards semaphore per Baskit (Python how?)
          with self.SemaBaskit:                 # only one thread uses Baskit
            if type(Baskit) is dict:            # if  dict update else overwrite
              if type(Result) is dict: Baskit.update(Result)
              elif type(Result) is OrderedDict: Baskit.update(Result)
              else: Baskit = Result             # will destroy what is in basket
            elif type(Baskit) is OrderedDict:     # if ordered dict update else overwrite
              if type(Result) is OrderedDict: Baskit.update(Result)
              elif type(Result) is dict: Baskit.update(Result)
              else: Baskit = Result             # will destroy what is in basket
            elif type(Baskit) is list:          # baskit is list append result
              if len(Baskit): Baskit.append(Result)
              else: Baskit = Result
            elif isinstance(Baskit,Callable):   # make a call back
              arg = {'ident': Ident }
              if not Result is None: arg['result'] = Result
              if not Except is None: arg['except'] = Except
              Baskit(arg)                       # call back with label with thread info
            else: self.Results[Ident]['result'] = Result # collect via Results dict
            logging.debug(f"Thread '{Ident}' completed work:\n\tresult '{str(Result) if Result is None else str(Except)}'{teaTime}.")
        else:
          self.Results[Ident]['except'] = Except # worker raised an exception
          if isinstance(Baskit,Callable):       # make a call back with event
            arg = self.Results[Ident].copy()
            arg.update({'ident': Ident})
            Baskit(arg)                          # inform the event via callback
          if not Except is None:
            logging.warning(f"Thread '{Ident}' generated an exception:\n\ttype: '{str(type(Except))}'\n\treason '{str(Except)}'{teaTime}.")
          else:
            logging.debug(f"Thread '{Ident}' completed work:\n\tresult 'None'{teaTime}.")

    # called when worker has done and was added as callback worker done function
    # add info from future to worker label when worker thread is done
    # creates an info label with thread results and if needed forward thread result.
    def _WorkDone(self, future) -> bool:
        """Label the info work done and ref to result or exception. Add label to self.Results dict.
           If needed give call back with label with ref result via _WorkResult.
           _WorkResult might push into baskit (dict list or call back function)."""

        ident = self.Futures[future].get('ident',None)
        if ident is None:
            logging.warning(f"Unexpected future worker in concurrent.Futures: '{str(future)}'.")
            return False
        baskit = self.Futures[future].get('baskit',None)
        if self.Stamp and self.Futures[future].get('start',None): # thread metering
            teaTime = round(time()-self.Futures[future]['start'],2)
        else: teaTime = ''
        nr = self.Futures[future].get('nr',None)
        try:                                     # add result to label or baskit
            result = future.result()
            self._WorkResult(ident,Nr=nr,Result=result,Baskit=baskit,teaTime=teaTime)
        except BaseException as exc:
            self._WorkResult(ident,Nr=nr,Except=exc,Baskit=baskit,teaTime=teaTime)
        return True

    # wait till all workers are completed. This may disrupt thread timing.
    # result: {nameWorker: result, ...} with result as { thread result, exception, time metering}
    # workers are mainly downloading data from internet. They may hang.
    def Wait4Workers(self, timeout:int=None) -> dict:
        """Wait till all workers have been done. Workers.
           Results dict with worker ident: { result and work info}."""

        if not self.Executor is None:
            if timeout is None: timeout = 6*60         # all workers time metering
            for future in futures.as_completed(self.Futures, timeout=timeout):
                if not self._WorkDone(future):
                    logging.debug(f"Worker {self.Futures[future]} timeout reached.")
                    continue # should not happen
            if self.Metering: self.Metering = time()-self.Metering
        elif self.Metering: self.Metering = time()-self.Metering
        return self.Results                            # make all worker info available

    def Shutdown(self) -> None:
        if not self.Executor is None:
            self.Executor.shutdown()                   # wait till done and release
        self.Executor = None

    @property
    def Timing(self) -> Union[None,float]:
        """Timing when all Workers are done."""

        if not self.Stamp or self.Metering is None: return None
        else: return self.Metering

    @property
    def Count(self) -> int:
        """Current total of submitted Workers for this Executor"""
        return self.Number+1

    # submit worker. The complicated way to shorten teaTime.
    def Submit(self, *args:Any, **kwargs:Dict[str,Any]) -> None:
        """Submit task for a Worker. Returns result in a buffer (dict or list.
           If buffer has a length the buffer is appended/updated with the result.
           PARAMETERS: dict(optional 'ident' (name: str), optional 'baskit' Union[list,dict,function])
                       or optional ident: str, optional Baskit:Union[list,dict,Callable],
                       Worker thread function (Callable), args, kwargs.
                       Optional ident (worker name):str (default: 'name_function nr_worker'),
                       Optional baskit None (dflt) or result baskit: appended/updated or call back function.
           RESULT: Info (optional timing, nr worker) and if baskit is not defined the worker
                       result/exception event is added to self.Results[thread indent] dict.
                       
           If baskit is a function the function will be used as call back with work info results
           immediately when worker thread has finshed.
           The wait routine waits till all work is done and deletes Executor instance."""
        try:
            if isinstance(args[0],dict) and len(args[0]):
                                          # has optional keys: ident, baskit, when_done
                label, *args = args
                Ident = label.get('ident',None)
                Baskit = label.get('baskit',None)
            else:
                if isinstance(args[0],str): Ident, *args = args
                else: Ident = None        # will be func __name__ + worker count
                if isinstance(args[0],(list,dict)):  Baskit, *args = args
                elif isinstance(args[0],Callable) and isinstance(args[1],Callable):
                    Baskit, *args = args  # callback with argument Results[Ident]
                else: Baskit = None       # results will be in workers wait dict
            Func, *args = args            # collect worker method and attributes
        except: raise ValueError("Submit workers argument error.")

                                          # start global teaTime metering
        with self.SemaBaskit:
            if self.Metering is None : self.Metering = round(time(),2)
            self.Number += 1              # current count workers. May be depricated.
        if not isinstance(Func,Callable):
            raise ValueError(f"Submit function '{str(Func)}' is not callable.")
        if Ident is None: Ident = f"{Func.__name__} {self.Number}"

        if not self.Executor is None:     # submit work to workers thread pool
            future = self.Executor.submit(Func,*args,**kwargs)
            self.Futures[future] = {
                                          # binds future worker with real world
                    'ident': Ident, 'baskit': Baskit,
                    'nr': self.Number,
                    'start': round(time(),2) if self.Stamp else None,
                }
            if isinstance(Baskit,Callable): # immediate result when work done
                future.add_done_callback(self._WorkDone)
            #logging.debug(f"Submitted worker ident '{Ident}' as future {self.Futures[future]}")
        else:                             # case of worker thread pool is not activated.
            try:
                if self.Stamp:           # function time metering
                    teaTime = round(time(),2)
                else: teaTime = None
                #logging.debug(f"Running ident '{Ident}' function '{str(Func)}'")
                result = Func(*args,**kwargs)
                if not teaTime is None: teaTime=round(time()-teaTime,1)
                self._WorkResult(Ident,Nr=self.Number,Result=result,Baskit=Baskit,teaTime=teaTime)
            except BaseException as exc:
                if not teaTime is None: teaTime=round(time()-teaTime,1)
                self._WorkResult(Ident,Nr=self.Number, Baskit=Baskit,Except=exc,teaTime=teaTime)
                #logging.debug(f"Running ident '{Ident}' function '{str(Func)}' raised event '{str(exp)}'")
#

# ================                = humanise geo names and codes
#
# from https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&zoom=18&lat=51.4470000&lon=6.0990000&email=noreply@host.domain
# {
#    "lat": "51.4474101","lon": "6.0996691",
#    "display_name": "10, Hoogheide, Lottum, Horst aan de Maas, Limburg, Nederland, 5973 RK, Nederland",
#    "address": {
#        "house_number": "10", "road": "Hoogheide", "postcode": "5973 RK",
#        "village": "Lottum",  "municipality": "Horst aan de Maas",
#        "state": "Limburg", "country": "Nederland", "country_code": "nl",
#        "ISO3166-2-lvl4": "NL-LI"},
#    "place_id": 96169730, "boundingbox": ["51.4473601","51.4474601","6.0996191","6.0997191"]}
#    "osm_type": "node", "osm_id": 2793660675, "importance": 9.99999999995449e-06,
#    "category": "place", "type": "house","place_rank": 30,
#    "addresstype": "place","name": "",
#    "licence": "Data © OpenStreetMap contributors, ODbL 1.0. http://osm.org/copyright",
#    See Usage Policy: https://operations.osmfoundation.org/policies/nominatim/
#
# Get humanised address information from Open Streets Map service (resolution is about 100 meters)
# parameter: ordinates (tuple or str): autocorrected to Europe lat,lon ordinates.
# returns:   "street housenr, village, gem. municipality, state(provincie)" if defined
# Concider to limit the amount of StreetMap() calls e.g. via the cache?
# declarator is disabled with multithreading
#@lru_cache(maxsize=16)   # cache is thread save? (GPS:str is a trick to make it hashable)
def StreetMap(GPS:Union[str,tuple]) -> str:   # GPS: string: [lat,lon] or (lat, lon) or lat,lon
    """StreetMap: returns an Open Street Map address for a GPS ordinates"""
    if type(GPS) is str:
        m = re.match(r'^\s*[\(\[]?\s*([0-9][0-9\.]+[0-9]+)\s*,\s*([0-9][0-9\.]+[0-9]+)\s*[\]\)]?\s*$',GPS)
        if m:
            GPS = (float(m.groups()[0]),float(m.groups()[1]))
        else: return ''
    lat = max(GPS[:2]); lon = min(GPS[:2])   # assert MET gps zone
    try:
        # if used frequently add parameter email address: &email=noreply@MYhost.MYdomain
        url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&zoom=18&lat={lat:.6f}&lon={lon:.6f}"
        content = execute_request(url)
        content = content.get("address",None)
        if not content: return ''
        address = []
        for _,item in enumerate(["road","house_number","village","municipality","state"]):
            if not content.get(item,False): continue
            if _ == 3:
                if content.get("village",False):
                    if content.get(item) != content.get("village",''):
                        address.append('gem. ' + content[item])
                else: address.append(content[item])
            elif _ == 1: address[0] += ' ' + content[item]
            elif _ == 4 and content.get(item,False):
                address.append('prov. '+content[item])
            else: address.append(content[item])
        return ', '.join(address)
    except Exception: pass
    #logging.warning(f"No Open Street address info for {lat:.6f} (lat), {lon:.6f} (long)")
    return ''
#
# test: StreetMap("51.4474101,6.0996691") ->  "Hoogheide 10, Lottum, gem. Horst aan de Maas"

# ================                      = GPS routines
# from pygeohash import geohash,distances
# Hypothetical sphere radius 6.372.795 meter.
# Courtesy of TinyGPS and Maarten Lamers, using Haversine
# Parameters (latitude,longitude). Coordinate is corrected to MET ordinates for swap
# Returns    distance in meters between two GPS coodinates (tuple)
@lru_cache(maxsize=8)   # cache is thread save?
def GPSdistance(geo_1:tuple, geo_2:tuple) -> int:
    """GPSdistance: distance in meters between 2 Points"""
    lat_1 = float(max(geo_1[:2])); lon_1 = float(min(geo_1[:2]))
    lat_2 = float(max(geo_2[:2])); lon_2 = float(min(geo_2[:2]))
    R = 6371000
    import math
    phi_1 = math.radians(lat_1)
    phi_2 = math.radians(lat_2)
    delta_phi = math.radians(lat_2 - lat_1)
    delta_lambda = math.radians(lon_2 - lon_1)
    a = math.sin(delta_phi / 2.0) * math.sin(delta_phi / 2.0) + math.cos(phi_1) * math.cos(phi_2) * math.sin(delta_lambda / 2) * math.sin(delta_lambda / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return int(R * c)  # distance in meters

# uses python geohash lib, try to correct lat/long swap
@lru_cache(maxsize=8)   # cache is thread save?
def Geohash(coordinates,precision:int=12):
    import pygeohash as GeoHash
    oord = coordinates
    try:
      if type(oord) is str and oord.find(',') > 1:
        oord = oord.split(',')[:2]
      # geohash uses (lat, long). Correction action max/min only works in Nld
      return '%s' % GeoHash.encode(max(float(oord[0]),float(oord[1])), min(float(oord[0]),float(oord[1])), precision)
    except:
      raise ValueError("location coordinates error with %s" % str(coordinates))
#
# test:  GPSdistance((51.419563,6.14741),(51.420473,6.144795))

# ================                      = Internet routines
# use command environment to require the use of proxy
@lru_cache(maxsize=1)
def ProxySupport() -> Union[None,dict]:
    """ProxySupport: get use of proxy support"""
    proxy_support = {}                          # http requests via a proxy?
    # export http_proxy=http://user:password@host:port
    # export https_proxy=https://user:password@host:port
    for proxy in ['https_proxy', 'http_proxy']: # static proxy
        if proxy in os.environ.keys():
           proxy_support[proxy[:-6]] = os.environ[proxy]
    # use of rendering proxy e.g. proxy service account via https://www.scrapingbee.com/
    # http/https_proxy  give self.proxy_support = {
    #    "http": "http://YOUR_SCRAPINGBEE_API_KEY:render_js=False&premium_proxy=True@proxy.scrapingbee.com:8886",
    #    "https": "https://YOUR_SCRAPINGBEE_API_KEY:render_js=False&premium_proxy=True@proxy.scrapingbee.com:8887" }
    if proxy_support: return proxy_support
    else: return None

# for access to website query services. Subject to be used via Thread Workers Pool
# internet library modules dependences
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen,build_opener,install_opener,_opener,ProxyHandler,quote
from requests.utils import requote_uri
import json

# Tuned for Open Street Map (dict[str,Any]), Open Data Soft (results: Union[list,dict[str,Any]]) and
#           Samen Meten (value, Union[dict[str,Any],list]) query responses
# It is time for standardisation of queries via an URL
# this can be decorated?
def execute_request(Url:str, callBack:Callable=None) -> Union[dict,list]:
    """execute_request: get info from the outside world"""
    def GetData(Url):
        ttl = 240 if callBack else 120                # Thinks service is slow
        try:
            with urlopen(Request(requote_uri(Url)), timeout=ttl) as response:
                return response.read()
        except:
            raise IOError(f"Time out on data request or UIRL error with URL '{Url}'. Exiting.")

    if _opener is None:
        opener = build_opener()
        install_opener(opener)
    else:
        opener = _opener
    _ = ProxySupport()
    if _:
        opener = build_opener(ProxyHandler(_))
        install_opener(opener)
    opener.addheaders = [('User-Agent','application/json')]
    for retries in range(3):                           # try to get some data
        try:
            # TO DO: for metering per request
            # if metering:
            #     name = None                          # get domain name as thread name
            #     m = re.search(r'^https?://([a-z][a-z0-9\.]+[a-z])/',Url)
            #     if m: name = m.group(1)
            #     body = DownloadMetering(name,GetData,Url)
            # else:
            body = GetData(Url)                        # if not metering
            body = json.loads(body.decode("utf-8"))
            if type(body) is dict:
                if 'value' in body.keys():         # should be done with callBack
                    iot = {}
                    iot.update({k: v for k, v in body.items() if k in ['@iot.nextLink', '@iot.count']})
                    if len(iot): body['value'].append(iot) # this is tricky
                    return body['value']
                elif 'results' in body.keys():     # Samen Meten Things
                    if type( body['results']) is list: # limit is 1, should be list[dict, ...]
                        if len( body['results']): return body['results'][0]  # should be a dict
                        else: return {}
                    elif not type(body['results']) is dict: return {}
                    else: return body['results']   # should be a dict
                else: return body                  # Open Street Map
            elif type(body) is list: return body   # TOOI standaarden.overheid.nl
            else:
                raise ValueError(f"URL {Url} unexpected result: {response.read()}")
        except HTTPError as error:  # 400-510
            if callBack is None:
                raise IOError(f"{error.status}: {str(error.reason)}")
            else: # maybe caller has some clue
                body = None
                # expect an error in json format
                try: body = json.loads(error.read().decode("utf-8"))
                except: pass
                if callBack(error.status,str(error.reason),body): # not temporary problem
                    raise IOError(f"{error.status}: {str(error.reason)}")
        except URLError as error: raise IOError(str(error.reason))
        except TimeoutError: pass
        except Exception as ex: raise IOError(str(ex))
        sleep(60+retries*30)
    raise IOError(f"{Url}: tried, however no results")

# ================================          = Open Data Soft query service
# convert municipality name to code or visa versa
# https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/
#      georef-netherlands-gemeente/records?
#      select=gem_name,gem_code&where=gem_name = "Venray"&limit=2
#      returns:
# {"total_count": 1, "results": [{"gem_name": ["Venray"], "gem_code": ["0984"]}]}
# on falure: {"total_count": 0, "results": []}
# Not all municipality codes are known by Open Data Soft nor Things. E.g. Land van Cuijk.
# TO DO: This api can be used to get the bounding box of the municipality.
# TO DO: add support for 'buurt' (suburb) and village, and bounding box municipality.
# TO DO: use CBS query service for this. Some municipality codes are not up to date.
@lru_cache(maxsize=16)   # module sources this is thread save?
def MunicipalityName(item:Union[str,int], region:str="gemeente") -> str:
    """MunicipalityName translate municipality name or code"""
    if type(item) is int: item = str(item)
    select = ("gem_name","gem_code")
    url =  "https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
    url += f"georef-netherlands-{region}/records?"
    if item.isdigit():                                               # max 9.999 codes!
        url += f'select={select[0]}&where={select[1]} = "{("000"+str(item))[-4:]}"&limit=1'
        select = select[0]
    else:
        url += f'select={select[1]}&where={select[0]} = "{item}"&limit=1'
        select = select[1]
    # Things gemeentecode has no leading zero's
    try: result = re.sub(r'^0+','',execute_request(url)[select][0])  # if len(select) > 0 ???
    except Exception:
        logging.warning(f"Coding region {region}: unable to find name or code for {item}")
        return ''
        # raise ValueError(f"Unable to get municipality info from {item}")
    return result
#
# test: MunicipalityName('Venray') -> municipality code

# ================================          = TOOI repository service
# Wet Openbaarheid Bestuur: TOOI (Thesauri en Ontologieën voor Overheidsinformatie)
# See: https://standaarden.overheid.nl/tooi
#https://repository.officiele-overheidspublicaties.nl/waardelijsten/rwc_gemeenten_compleet/4/json/rwc_gemeenten_compleet_4.json
#[ {
#  "@id" : "https://identifier.overheid.nl/tooi/id/gemeente/gm0003",
#  "@type" : [ "https://identifier.overheid.nl/tooi/def/ont/Gemeente" ],
#  ...
#  "https://identifier.overheid.nl/tooi/def/ont/officieleNaamExclSoort" : [ {
#    "@value" : "Appingedam"
#  } ],
#  "https://identifier.overheid.nl/tooi/def/ont/gemeentecode" : [ {
#    "@value" : "0003"
#  } ], ....]
# Obtain from governemental municipality name from municipality code (visa versa)
# Parameter: either official municipality name or municipality code (int or str).
# Returns: name or code (without leading zero's) as str.
# To Do: selection by id=? n json format to create a selection from the query
@lru_cache(maxsize=16)   # module sources this is thread save?
def Municipality_NameCode(entity:Union[str,int]) -> str:
    """Get from municipality code the municipality name and via versa"""
    url = 'https://repository.officiele-overheidspublicaties.nl/waardelijsten/rwc_gemeenten_compleet/4/json/rwc_gemeenten_compleet_4.json'
    data = execute_request(url)
    TOOIont = 'https://identifier.overheid.nl/tooi/def/ont/'
    if entity.isdigit():
        search = TOOIont+'officieleNaamExclSoort'
        key =  TOOIont+'gemeentecode'
        entity = ('0000'+str(entity))[-4:]
    else:
        search = TOOIont+'gemeentecode'
        key = TOOIont+'officieleNaamExclSoort'
    for item in data:
        id = item.get(key)
        # assert only 1 element key dict in item list
        if type(id) is list and len(id): id = id[0].get('@value')
        if not id: continue
        if entity != id: continue
        id = item.get(search)   # found it
        if type(id) is list and len(id): id = id[0].get('@value')
        else: continue
        while id[0] == '0': id = id[1:]  # municipality code: delete leading zero's
        return id
    return None
#
# test: Municipality_NameCode('Venray') -> municipality code

# =======================================================================
# ====================             = Things observation download routines
# =======================================================================
#
# Support to collect varius and tunable meta information of a 'Things' station.
#
# Reminder: Document about Pandas Dataframe reasoning:
# Dataframe Systems: Theory, Architecture, and Implementation, Devin Petersohn (aug 2021)
# See: https://www2.eecs.berkeley.edu/Pubs/TechRpts/2021/EECS-2021-193.pdf

# Things 'gost' documentation: https://gost1.docs.apiary.io/#reference/odata-$filter
# Samen Meten sql IoT sensor Things API V1.1 Open Geospatial Consortium
# ========== for Things API query functions, reference info:
# See OGC documentation: https://docs.ogc.org/is/18-088/18-088.html#overview1
# We use only database tables: Things and Locations.
# How To questions: select sub fields: e.g. $select=name,properties/gemcode ?
#                   neighbour locations results with distance ?
#
# Python3 typing kwargs examples:
# ProductID, Address, Humanise are typed Union[None,bool]
# Start, End are typed Union[None,str] where str is date string like YYYY-MM-DD HH:MM local
# Sensors is typed as Union[None,[()|str, ...]]
# Routines result styling: if value is None: defaults may overwrite parameter value
# To Do: add stations search of a list of municipalities, list of locations, reg expr stations.
from collections import OrderedDict   # observations dataframes collect in an ordered dict
class SamenMetenThings:
    """SamenMetenThings class: Samen Meten routines to Pandas dataframe"""

    # be more verbose via Message and do not mix up lib messages
    # should decorate Message
    def _Verbose(self,Line:str, ID:str, Level:int) -> None:
        # TO DO: if no controlling terminal log the message (need to review msg levels)
        if ID: ID += ': '
        if Level < 0: logging.warning(ID + Line)
        elif self.Verbose >= Level:
            if sys.stderr.isatty(): sys.stderr.write(ID + Line + '\n')
            else: logging.info(ID + Line)

    # get some content from a website server in dict format, expect json data
    # parameters URL. URL will be prependedn with class default URL on missing http method
    # returns    json decoded body (dict) or dict value from "value" dict key if defined.
    # Uses Things http error codes. Completes request string with http and domain part.
    # subject to python decorate
    def _execute_request(self,Url:str) -> Union[dict,list]:
        """_execute_request and handle errors"""
        def requestsErrors(status:int,message:str,content=Union[None,dict]) -> bool:
            """requestsErrors call back coroutine on HTTP errors"""
            # IoT Things error coding
            ThingsErrors = {
              400: "Bad Request – Something in your request is not correct.",
              401: "The API key error, unauthorized.",
              404: "The resource does not exist on the system.",
              405: "Method not allowed.",
              406: "Requested format is not available.",
              409: "A resource constraint has been violated.",
              410: "The resource requested has been removed.",
              429: "Too much load right now, try again later.",
              500: "Internal Server Error, try again later.",
              503: "Service offline for maintanance, try again later.",
            }
            msg = message
            try: msg = '\n'.join(content['error']['message'])
            except Exception: 
                try: msg = ThingsErrors[status]
                except Exception: pass
            self._Verbose(f"HTTP error status {status}: {msg}","Things HTTP error",0)
            if status < 429: return True
            else: return False

        if not re.match(r'^https?://',Url): # Things API request
            return execute_request(self.URL + Url,callBack=requestsErrors)
        else: return execute_request(Url)

    # ========================= class initialisation
    """ Global key variables used in this Python class
     Parameters in class subrotines may overwrite class defaults.
     Parameter names are not case dependent.
     Class default parameters (if None leave it to subroutines):
       Verbosity=1    Progress verbosity level.
       Meta=False     Get also station measurements header information as dict.
       Sensors="pm10 kal,pm10,pm2.5 kal,pm2.5,rh,temp" Default sensor (column) name list.
       Start=None     (from start measurements) or yyyy-mm-dd, yyyy-mm-dd-hh in local time.
       End=None       (till end measurements). period (start,end) are exclusive timestamps.
       Unit=False     May add unit information to column name.
       Sensor=False   May add sensor product ID to column name.
       Address=False  Add full adddress of location via Open Street Map.
       Utf8=False     Convert humanised names to utf-8.
       URL="https://api-samenmeten.rivm.nl/v1.0"  Is Things V1.1 supported?
       Product=True   Add manufacturer sensor product ID if available.
       Status=True    Add sensor status info to station information requests.
       Neighbours=0   Add a asc sorted cluster maximal neighbouring stations (max count)
                      within 500 meters.
       Threading=True Turns multithreading (parallel observation requests) on (dflt).
                      Verbosity level 3+: timing all workers done, 4+: timing per worker.
     """
    # Product, Address, Human, Utf8 are typed Union[None,bool]
    # Start, End are typed Union[None,str] where str is date string like YYYY-MM-DD HH:MM local
    # Sensors is typed as Union[None,list[()|str, ...]],str], str is comma seperated
    # Sensors as regular expression will filter the available sensors names for observations.
    # Meta is typed as Union[None,dict[str,Any]]
    # Verbosity is typed as int[-2,4]
    # Verbosity >2 will turn metering on with station info part
    # None as parameter option will say: yet undefined
    def __init__(self, **kwargs:Dict[str,Any]) -> None: # initialise global defaults with defined keys
        # class kwargs defaults
        inits = {}                 # dict of defaults overwritable via class arguments
        inits['Verbosity'] = 1     # minimal verbosity level on standard error stream
        # defaults, period some epoch to now for data download(s)
        inits['Start'] = inits['End'] = None # period (exclusive timestamps)
        inits['Url'] = "https://api-samenmeten.rivm.nl/v1.0" # basic Things URL
        inits['Unit'] = False      # add unit name to column names
        inits['Address'] = False   # add humanised address info to meta dict
        inits['Meta'] = None       # if True add dict with meta info
        inits['Humanise'] = False     # humanise the column names
        inits['Utf8'] = False      # humanised names in utf-8 strings
        # default list of sensors to get observasions from
        # if Sensors string is a regular expression apply this as sensor filter for observations
        inits['Sensors'] = "pm10 kal,pm10,pm2.5 kal,pm2.5,rh,temp"
        inits['Product'] = True    # add sensor manufacturer product ID
        inits['Status'] = True     # add sensor status information to station info.
        inits['Neighbours'] = 0    # amount to list as neighbours station max 500 meter.
        # note: Things GPS ordinates are rounded to 3 decimals. A 75 meters resolution.
        inits['Range'] = 500.0     # neighbours within region of N meters
        # library caller may want to separate error messages too
        inits["Threading"] = True  # do not use parallelism to obtain observations

        for key in kwargs.keys():  # overwrite defaults
            if key.title() in inits.keys():
                                   # this is rather a too simple approach
                if inits[key.title()] is None or type(inits[key.title()]) is type(kwargs[key]):
                    inits[key.title()] = kwargs[key]
                else: raise ValueError(f"Class argument {key} is of wrong type")
            else: raise ValueError(f"Class argument {key} unknown")

        # check parameters and make them available in the class object
        self.Meta = inits['Meta']               # include meta information station as dict
        self.Verbose = int(inits['Verbosity']) if inits['Verbosity'] else 0
        # TO DO: if no tty control, log the message as well?
        self.URL = inits['Url']                 # IoT Things URL
        self.Utf8 = inits['Utf8']               # sensor and symbol names in UTF-8

        # default values, can be overwritten via subroutine optional argument
                                                # adds measurement unit info to column name
        self.Units = inits['Unit']
                                                # period to download observations
        self.Start = inits['Start']; self.End = inits['End']
        self.HumaniseClass = HumaniseClass(utf8=inits['Utf8']) # humanise sensor routines
        self.Address = inits['Address']         # add humanised address from GPS location
        self.Addresses = {}                     # address cache to map GPS to address
        self.Sema_Addresses = Semaphore(1)      # semaphore for addresses cache
        self.Humanise = inits['Humanise']          # humanise sensor column names
                                                # sensor column names will be dehumanised
        # list with default (Things) types to download as Pandas columns
        self.Sensors = inits['Sensors']
        self.ProductID = inits['Product']       # add sensor product ID
        self.Status = inits['Status']           # add sensor info (first/last/count)
        self.Neighbours = inits['Neighbours']   # max asc ordered list in range 500 meters
        self.Range = inits['Range']             # get neighbours in range of N meters
        self.Threading = inits['Threading']     # get observations in multi threading modus
        self.Sema_Observe =  Semaphore(1)       # semaphores needed with threading
        return None

    # create if needed a regular expression
    def _RegExp(self, pattern:Union[str,re.Pattern]) -> re.Pattern:
        if not pattern or type(pattern) is re.Pattern: return pattern
        if type(pattern) is str:                # e.g. 'pm(25|10),no?' or 'pm25,pm10,no2'
            if pattern.find(',') > 0:
                pattern = '('+'|'.join([x.strip() for x in pattern.split(',')])+')'
            pattern = '^'+ pattern +'$'         # match full pattern
        return re.compile(pattern)

    # collect sensor operational info (first/last timestamp in a period and count)
    # push results in sensor dict baskit, period: Start/None-End/None. 
    # this can take a while ... 2 X nr of sensors * ca 15 seconds if not parallel
    # add status of sensors per station. This is time consuming!
    def _AddSensorsStatus(self, Station:str, Sensors:dict, Start:Any=None, End:Any=None) -> None:
        """ _AddSensorsStatus: add sensor details first, last, count, unit, product id
        to sensors dict. Is multi threaded. This operation can take a while."""

        if not self.Status: return None
        # if None overwrite with class initialisation values
        if not Start: Start = self.Start        # None is from start observations
        Start = ISOtimestamp(Start) if Start else None
        if not End:   End = self.End            # None is observations till recent
        End = ISOtimestamp(End) if End else None

        if not type(Sensors) is dict or not len(Sensors): return None
        baskits = 0
        for _ in Sensors.values():
            if _ and _.get('@iot.id'): baskits += 1
        if not self.Threading or baskits == 1:  # no multi threading
            for sensor,baskit in Sensors.items(): # work to do?
                if type(baskit) is dict and baskit.get('@iot.id'):
                    Sensors[sensor].update(self._SensorStatus(baskit.get('@iot.id'), Start=Start,End=End))
            return None

        # use MaxWorkers=1 when debugging this routine
        with MyWorkers(WorkerNames='StatusSensors', MaxWorkers=3, Timing=(self.Verbose > 2)) as workers:
            for sensor,baskit in Sensors.items():
                if type(baskit) is dict and baskit.get('@iot.id'):
                    workers.Submit(f'{Station} {sensor} first',self._SensorStatus,baskit.get('@iot.id'),Status='first', Start=Start, End=End)
                    workers.Submit(f'{Station} {sensor} last ',self._SensorStatus,baskit.get('@iot.id'),Status='last', Start=Start, End=End)
                    if baskit.get('symbol'):    # need to add sensor product ID
                        workers.Submit(f'{Station} {sensor} product',self._ProductID,baskit.get('@iot.id'))
            results = workers.Wait4Workers(round(float((len(Sensors)+2)/3)*30))
            if workers.Timing:
                self._Verbose(f"thread '{workers.WorkerNames}' total timing {round(workers.Timing,1)}.",f"Station {Station} sensor status",3)
        for name, value in results.items():
            # handle info about work done, synchronize results
            if not value.get('timing',None) is None:
                self._Verbose(f"{round(value.get('timing'),1)} seconds",f"Timing {Station} sensors {name}",4)
            if value.get('except',False): raise value.get('except')
            elif type(value.get('result',None)) is dict:
                try:
                    station, sensor = name.split(' ')[:2]
                    Sensors[sensor].update(value.get('result'))
                except: raise ValueError(f"Station {station} sensor status error.")
            else: raise ValueError("Error in sensors status request for station {station}.")

    # add sensor status for each station in dict Stations in a period Start - End.
    # Stations dict: station: info dict {'sensors': {}, ...}. Updating Stations dict.
    def get_SensorStatus(self, Stations:dict, Start=None, End=None) -> None:
        """get_SensorStatus() add sensor details of a dict(stations:dict()
        calls _AddSensorsStatus() multi threaded."""
        if not self.Status: return None
        for station,info in Stations.items():
            if (sensors := info.get('sensors',{})) and len(sensors):
                # next takes 15-90 secs per sensor, the thread ca 70 secs for all sensors
                self._AddSensorsStatus(station, sensors, Start=Start,End=End)

    # for a region with id:str as eg @iot.id, gemCode, municipality name, station name
    # from a list of stations get details as addresses, sensor details, etc.
    # convert Things inquiry results to internal Samen Meten Tools format: dict with stations.
    # parameters: Region: name of region, Select: reg expr to filter station names
    #         Data: list of dicts from Things data request
    #               [{iot:Union[str,int],name:str,Locations:{location:{coordinates:[]}},
    #                  Datastreams:[{name:"???-sensorName"},...] -> { stationName: {} ...}
    #         Sensors str or reg exp: sensors to select,
    #         Select str or reg expt to filter station names
    #         PropSelect list of station properties e.g. owner, project, gemcode, ...
    # returns dict(station names: dict with @iot.id's and Samen Meten Tools internal format)
    # e.g.: get_StationsInfo('IJmond',Data:list of dicts,Select=filter with '.*',) ->
    #       dict(stationName: {'@iot.id': ID, 'location':[(float,float),],
    #        'sensors': { sensor:str : {'@iot.id': int, 'symbol': str}, ... },}, ...)
    def get_StationsInfo(self,Region:Union[int,str],Data:List[dict],Sensors:Union[str,re.Pattern]=None,Select:Union[str,re.Pattern]=None, PropSelect:List[str]=[]) -> dict:
        """get_StationsInfo info details for list of stations for a Region, from list Data,
        filtered by reg exp Select"""

        if Sensors: Sensors = self._RegExp(Sensors)
        if Select: Select = self._RegExp(Select)
        stations = dict(); selected = 0; nr = 0
 
        for station in Data:
            info = dict(); name = None
            if self.Verbose:                                   # teatime music
                nr += 1
                if self.Verbose:
                    self._Verbose(f"station nr {nr} of {len(Data)}", f"Collect info for {station.get('name','unknown')} (region {str(Region)})",3)
            for item, value in station.items():
                if item == '@iot.id': info['@iot.id'] = value
                elif item == 'name':
                    if Select and not Select.match(value):     # filtering station names
                        info = dict()                          # skip this station
                        if self.Verbose:
                            self._Verbose(f"station nr {nr} of {len(Data)} not selected", f"Skip {station.get('name','unknown')})",2)
                        break
                    name = value
                elif item == 'Locations' and type(value) is list and len(value):
                    for v in value:                            # list of locations (only one)
                      if v.get('location', None):              # limit to only first location
                        if v.get('location').get('coordinates') and v.get('location'):
                          if v.get('location').get('coordinates')[:2]:
                            info['location'] = [tuple(v.get('location').get('coordinates')[:2])]
                            break
                elif item == 'properties' and type(value) is dict:
                    for n in PropSelect:
                        if (v := value.get(n)): info[n] = v
                elif item == 'Datastreams' and type(value) is list:
                    fnd = False
                    for item in value:
                        if not type(item) is dict: continue
                        sensor = item.get('name','-').split('-')[-1] # assert len > 0
                        if not info.get('sensors'): info['sensors'] = dict()
                        info['sensors'][sensor] = None
                        if Sensors and Sensors.match(sensor):  # is station sensor of interest?
                            fnd = True
                            if item.get('@iot.id'): # baskit for sensor status query
                                info['sensors'][sensor] = {'@iot.id': item.get('@iot.id')}
                                if (symbol := item.get('unitOfMeasurement')):
                                    if (symbol := symbol.get('symbol')):
                                            info['sensors'][sensor]['symbol'] = symbol
                    if not fnd:                                # no sensor of interest
                        if not info.get('sensors'): info = dict()
                        break
                    else: selected += 1

            if len(info) and name: stations[name] = info.copy() # else skip station

        if self.Verbose:
            if not len(stations):
                self._Verbose(f"Unable to identify stations",f"Municipality name or region '{Region}'",2)
                return None
            else:
                self._Verbose(f"selected {selected} (of {len(Data)}) stations with sensor observations.", f"Stations in {Region}",2)
        return dict(sorted(stations.items()))     # clustering: use geohash of GPS as sort key?
    #
    # test: with argument Sensors='pm25'  Select='LTD_21568' ->
    #     { stations['LTD_21568']:
    #      {'@iot.id':2126,'owner':'Luftdaten','project':'Luftdaten','location':[(6.026,51.5)],
    #          'sensors': {'pm10_kal': None, 'pm10': None, 'pm25_kal': None,
    #                      'pm25': {'@iot.id': 10017, 'symbol': 'ug/m3'}} } }

    # ======== ROUTINE get_InfoNeighboursList(): list of stations info for a region
    # multi threaded neighbours info if Names is list. May cause routine recursion.
    # list of station names or @iot.id's of stations
    # will call get_InfoNeighbours() routine for individial station info
    def InfoFromNeighboursList(self,Names:List[Union[str,int]], Region:int=None, By:str="id,name", Select:Union[str,re.Pattern]=None, Sensors:Union[str,re.Pattern]=None, Start=None, End=None) -> dict:
        """InfoFromNeighboursList():
        Station info from a list (multi threaded) Names (string or @iot.id station),
        in a Region, query By, Select filter stations by name, filter Sensors,
        period Start - End. Calls get_InfoNeighbours() per Name."""

        if not len(Names): return {}
        stations = dict()
        if not self.Threading or len(Names) == 1:  # no threading, usual for debugging reasons
            for station in Names:
                try:
                    station = self.get_InfoNeighbours(station,Region=Region,By=By, Select=Select, Sensors=Sensors, Start=Start,End=End)
                    stations.update(station)
                except: pass
            return stations
        # when debugging set MaxWorkers to 1       # multi threading case
        results = list()
        with MyWorkers(WorkerNames='InfoNeighbours', MaxWorkers=6, Timing=(self.Verbose > 2)) as workers:
            for station in Names:
                 workers.Submit(f'NeighbourInfo {str(station)}',self.get_InfoNeighbours,station,Region=Region,By=By, Select=Select, Sensors=Sensors, Start=Start,End=End)
                 if self.Verbose:
                     self._Verbose(f"get neighbour station info",f"Station {str(station)}",1)
            results = workers.Wait4Workers(round((len(Names)+2)/6,0)*30)       # pick up work done info (timing, events)
            workers.Shutdown()
        for work in sorted(results.items(), key=lambda item: item[1]['nr']):
            name,result, = work                    # one tuple per sensor
            if result.get('timing'):
                self._Verbose(f"info timing {result.get('timing'):.1f} seconds.",f"Neighbour '{name}'",4)
            if not result.get('result') is None: stations.update(result)
            elif not result.get('except') is None: # worker has an exception
                logging.warning(f"Neighbours '{name}' info raised exception {str(result.get('except'))}.")
        return stations

    # https://api-samenmeten.rivm.nl/v1.0/Things?$select=id,name&$filter=properties/codegemeente eq '984'
    # Since 2024-08-27: code gemeente has got a decimal e.g. 984.0 (no leading zero's.
    # {"value":[{"@iot.id":9110,"name":"LTD_78914"},{"@iot.id":8589,"name":"GLBPB_NL10937"},...]}
    # Q: structure station naming?: <DB ID>_<stationID>
    # LTD->Luftdaten DB GLB->NSL station PB->prov Brabant GM->Grenzeloos Meten OHN->Ohnics
    # OZK->?  FHW->? SSK->? LUC->? GLB->?
    # extend query with &$expand=datastreams($select=name) ->  e.g.
    #              "Datastreams": [{"name":"OHN_ma-2040-19-temp"}, ...]
    # extend query with &$expand=locations($select=location) -> e.g.
    #              "Locations": [{"location":{"coordinates":[5.986,51.548],"type":"Point"}}],
    # Municipality codes Netherlands (csv file):
    #    https://publicaties.rvig.nl/dsresource?objectid=86360a47-728a-4c10-9b95-a4ea9fcaf680
    #    Implementation uses Open Data Soft query website to solve name <-> code problem.
    #    Note: municipality code lists (Things,Open Data Soft) are not fully up to date.
    # Open Data Soft documentation:
    #       https://help.opendatasoft.com/apis/ods-explore-v2/#section/Introduction
    #       https://github.com/opendatasoft/ods-documentation-explore-api/blob/master/source/includes
    #             /v2/_dataset.md
    #             /v1/records_api.md
    # Open Data Soft api can be used with e.g. Highcharts.js
    # https://public.opendatasoft.com/explore/dataset/georef-netherlands-gemeente/api/
    #       ?disjunctive.prov_code&disjunctive.prov_name&disjunctive.gem_code
    #       &disjunctive.gem_name&sort=year
    # Other tables: e.g. georef-netherlands-postcode-pc4, ???
    #       https://opendata.cbs.nl/ODataApi/odata/85318NED/WijkenEnBuurten
    # To Do: List of municipalities? DetailRegionCode e.g. wijken, buurten?
    #       is there a need to add GPS locations in the properties field?
    #       use kmeans clustering: use municipality GPS bounding circle as region
    #       use geohash of location as clustering key in a grid?
    #       municipality as region is focus on local politics:
    #       change this to stations in a cluster in the region?
    #       See: https://medium.com/codex/clustering-geographic-data-on-an-interactive-map-in-python-60a5d13d6452
    #
    # This routine is a higher lever query, so it is doubtfull to be used with Iot.ID.
    # Parameters:
    #       'Name' (municipality code, municipality name, station name, station IoT id, GPS)
    #                 Name as list or comma separated string of name elements is supported.
    #                 E.g. Land van Cuijk, Venray, 14, NLH_012345, 14256, (5.123,61.123), ...
    #       'Name'    May be a list of 'Name's.
    #       'Region': if None Name is handled as municipality region,
    #                 if 0 get info of single low-cost station (name with _, GPS point, IotID.
    #                 if >0 region in meters from station or GPS point (GPS tuple).
    #       Optional arguments:
    #       'By':  "name,id" (dflt), "@iot.id" (station id), "owner", "project", "location",
    #             location with "address", stations with "sensors" or required 'Sensors'.
    #       'Select': (default None) reg expr to filter station names e.g. '(^(LHT|GM).*)'.
    #       'Sensors': Require sensors info per type: default all sensors.
    #                 reg exp or comma separated list 'pm25,pm10': filter sensor types.
    #       'Start/End' Start-End limit status timestamps of observations.
    # Returns list with station names optional with Things station @iot.id (option args None).
    #       or dict with key station name's: a dict: '@iot.id';, 'owner', 'project',
    #              'location': list with GPS tuple and address[str].
    #              'sensors': list of supported sensor names and installed sensor types.
    def get_InfoNeighbours(self,Name:Union[str,int,List[Union[str,int]]], Region:int=None, By:str="id,name", Select:Union[str,re.Pattern]=None, Sensors:Union[str,re.Pattern]=None, Start=None, End=None) -> dict:
        """get_InfoNeighbours: returns dict with stations within a municipality or region
           with info properties: name, iot.id, owner, project, and sensor types,
           location (with optional Address),
           Sensors: select sensors on available sensors types,
           and
           if self.Status add observations information (first,last,count,sensor type),
           if self.ProductID add sensor product type information."""

        # parse and check Name to differentiate: point,municipality,station, iot.id regions
        # Name: municipality name or gemcode, Region not used
        #       low-cost station name (string has _ char), or @iot.id station
        #             Region is None: use municipality of station
        #             Region > 0: neighbours
        #             Region == 0: station info only
        #       @iot.id station Region > 0: neighbours, Region=0 status
        if type(Name) is str and (m := re.findall(r'([\(\[]\s*\d+\.\d+\s*,\s*\d+\.\d+\s*[\)\]]|[a-z]+_[a-z0-9_-]+[a-z0-9]|[a-z][a-z\s-]+[a-z]|\d+)',Name,re.I)):
            items = []                         # only allow GPS points (homogeneous list)
            for item in m:
                if re.match(r'[\(\[]\s*\d+\.\d+\s*,\s*\d+\.\d+\s*[\)\]]',item): # Point
                    items.append(tuple([float(x.strip()) for x in item[1:-1].split(',')]))
                elif item.isdigit():           # low-cost station @iot.id or gemcode
                    item = items.append(item)
                elif re.match(r'^[a-z]+[a-z0-9\s_-]+[a-z0-9]$',item,re.I):
                    items.append(item)         # low-cost station or municipality name
                else:
                    self._Verbose("unable to find station(s).",f"Error in region '{item}'",0)
                    return {}
            Name = items
        if type(Name) is list:
            if len(Name) > 1: # handle stations via multi threading
                return self.InfoFromNeighboursList(Name,Region=Region,By=By, Select=Select, Sensors=Sensors, Start=Start,End=End)
            elif len(Name): Name = Name[0]
            else:
                self._Verbose("unable to find name, GPS point, gemcode or @iot.id.",f"Error in parsing name in '{Name}'",0)
                Name = None
        elif type(Name) is int: pass            # gemcode or @iot.id
        elif type(Name) is tuple and len(Name) == 2: pass  # GPS point
        else:
            self._Verbose("unable to find name, GPS point, gemcode or @iot.id.",f"Info Neighbours name {Name}",0)
            Name = None
        if not Name: return {}

        # generate filter query for Name type: point, municipality, statio
        gemcode = None; oneFilter = ''

        # Name is of municipality type?: get gemcode municipality
        # low-cost station name and Region is None: get gemcode of station municipality
        if type(Name) is str and Name.find('_') > 0 and Region is None:
            url = f"/Things?$select=id,properties/codegemeente&$filter=name eq '{Name}'"
            try:
                gemcode = self._execute_request(url)[0]["properties"]["codegemeente"]
            except: gemcode = ''
        elif Region is None and type(Name) is str: # municipality name
            if not Name.isdigit():
                # municipality name, get gemeente code from external resource
                gemcode = Municipality_NameCode(Name)
                if not gemcode: gemcode = ''  # error
            else: gemcode = Name              # municipality via gemcode muninicipality
        else:                                 # neighbours of GPS point, station name/@iot.id
            gemcode = None
        if gemcode:                           # stations in municipality via gemcode
            oneFilter = f"properties/codegemeente eq '{gemcode}'"
            Region = None
        if gemcode == '':                     # error municipality code
            self._Verbose(f"unable to find municipality code.",f"Municipality '{str(Name)}' regional stations inquiry",0)
            return {}

        thingsID = ''
        # GPS point, low-cost station name or @iot.id: filtering neighbours in a Region
        if gemcode is None:
          if Region is None or Region > 0: # recursion, result ordered list of station names
            return self.InfoFromNeighboursList(list(self.get_Neighbours(Name,Range=Region,Address=False).keys()),Region=0,By=By, Select=Select, Sensors=Sensors,Start=Start,End=End)
          elif Region == 0:                     # single low-cost station
            if type(Name) is int or Name.isdigit():
                oneFilter = ''; thingsID = f"({Name})"; Name = str(Name)
            else: oneFilter = f"name eq '{Name}'"
            if not (type(Name) is str or type(Name) is tuple):
                self._Verbose(f"unable to find station information",f"Station '{str(Name)}' regional stations inquiry",0)
                return {}

        # convert comma separated string to reg exp for sensors type filtering
        if Sensors is None: Sensors = self.Sensors
        Sensors = self._RegExp(Sensors)
        Select  = self._RegExp(Select)
        # select: name or id, or both. properties: e.g. owner, project
        select = []; properties = []; stationProps = []
        if By is None: By = 'name,id'
        for item in [x.strip() for x in By.split(',')]:
            if re.match(r'^(name|id)$',item): select.append(item)
            elif re.match(r'^(owner|project|(gem|knmi)code|(nh3|no2|pm[0-9]{1,2})(close|regio|stad)code)$',item):
                stationProps.append(item)      # station properties of interest
            else: properties.append(item)      # extra info of interest
        if not 'sensors' in properties:
            if Sensors: properties.append('sensors')
            else: Sensors = self._RegExp('.*') # report all supported sensors names of station
        select = set(select + ['name','id'])   # always select on name and @iot.id
        if 'address' in properties and not 'location' in properties:
            properties.append('location')
        properties = set(properties)
        
        # generate URL query
        url = f"/Things{thingsID}?$select={','.join(select)}{',properties' if len(stationProps) else ''}&$filter={oneFilter}"
        expand = ''
        if 'location' in properties: expand = "&$expand=locations($select=location)"
        if 'sensors' in properties:
            if expand: expand += ",datastreams($select=name,id)"
            else: expand = "&$expand=datastreams($select=name,id)"
            if self.Status or self.ProductID:
                expand = expand[:-1] + ',unitOfMeasurement)'           # get measurement symbol
        url += expand
        try:
            data = self._execute_request(url)
            if type(data) is list:
                data = sorted(data, key=lambda station: station['name']) # To Do: cluster sort
            else: data = [data]
        except: return None

        # convert Things format to internal Tools format
        stations = self.get_StationsInfo(Name,data,Select=Select,Sensors=Sensors,PropSelect=stationProps)
        if not stations: return {}

        # no extra info required, return dict station name:@iot.id
        if not properties:
            for n,v in stations.items():   # clean up
                if not type(v) is dict: del stations[n]
                if (v := v.get('@iot.id')): stations[n] = {'@iot.id': v}
                else: del stations[n]
            return stations

        # it is teatime from here. Next can take a while.
        # add addresses. This takes a small StreetMap while.
        if 'address' in properties: # teatime: 1-4 seconds per address, thread 9 secs
            if len(stations) > 100 and not self.Status:
                self._Verbose(f"{len(stations)} stations!. This can take a while. Try to limit it with station selection filter!", f"Attention nr of stations in {Region} region",0)
            stations = self._AddAddresses(stations)  # will now be ordered by geohash clustering

        # add sensor status. This can take a Things while.
        if self.Status:   # add sensors details: first/last/count/unit/ID
            if len(stations) > 100:
                self._Verbose(f"{len(stations)} stations!. This can take a while. Try to limit it with station selection filter!", f"Attention nr of stations in {Region} region",0)
                     # teatime: 15-75 seconds per sensor, thread 30-70 secs per station
            self.get_SensorStatus(stations, Start=Start, End=End)

        # clean up stations dict
        # warning: @iot.id (Things internal key number) may change in time!
        if not 'id' in select:              # @iot.id is not requested in return dict
            for info in stations.values():
                if '@iot.id' in info.keys(): del info['@iot.id']
                if info.get('sensors'):
                    for sensor in info['sensors'].values():
                        if not type(sensor) is dict: continue
                        if '@iot.id' in sensor.keys(): del sensor['@iot.id']
        return stations
    #
    #  returns e.g.: {'GLBPB_033-030': {'owner': 'Globe', 'project': 'Palmes', '@iot.id': 1234,
    #     'location': [(5.725, 51.721), 'Zandvoortschestraat, Langenboom, gem. Land van Cuijk, prov. Noord-Brabant'],
    #      'sensors': {'no2': {'@iot.id': 45582, 'symbol': 'ug/m3', 'product': 'Palmes buisje'}}},
    #       'LTD_60047': {'owner': 'Luftdaten', 'project': 'Luftdaten', '@iot.id': 1324,
    #        'location': [(5.842, 51.644), 'Lamperen, Wanroij, gem. Land van Cuijk, prov. Noord-Brabant'],
    #        'sensors': {'pres': None, 'rh': None, 'temp': None,
    #                    'pm10': {'@iot.id': 37489, 'symbol': 'ug/m3', 'product': 'Nova SDS011', 'first': '2022-04-26T04:00:00.000Z', 'count': 2937, 'last': '2022-12-23T16:00:00.000Z'},
    #                    'pm25': {'@iot.id': 34877, 'symbol': 'ug/m3', 'product': 'Nova SDS011', 'last': '2022-12-23T16:00:00.000Z', 'count': 2937, 'first': '2022-04-26T04:00:00.000Z'}}
    #          },...}

    # =========== routine _SensorStatus(@iot.id)   uses multi threading
    # parameters Things datastream IoT.id, Period ('last' or 'first' or None: records count)
    # returns    timestamp (ISO UTC) last observation record, first or only record count.
    #            Count: add number of observations for this sensor in the Start-End period.
    # routine can take about 10-15 secs to run
    def _SensorStatus(self, Iotid:Union[int,str], Status:Union[bool,str]=None, Start:Any=None, End:Any=None) -> dict:
        """ get Sensor Status for timestamp first/last/both and record count"""
        # if None overwrite with class initialisation values
        if not Start: Start = self.Start   # None is from start observations
        Start = ISOtimestamp(Start) if Start else None
        if not End:   End = self.End       # None is observations till recent
        End = ISOtimestamp(End) if End else None

        if Status is False: return {}
        result = {}
        if Status in ['first','last','product']:   # try to save on bandwidth and memory
            if Status == 'product': return self._ProductID(Iotid)
            timestamp = 'phenomenonTime'
            select = f'&$select={timestamp}'
            select += f"&$orderby={timestamp} {'asc' if Status == 'first' else 'desc'}"
            filtering = ''
            for idx, key in enumerate([Start,End]):
                if not key: continue
                if filtering: filtering += ' and '
                filtering += f"{timestamp} {'lt' if idx%2 else 'ge'} {key}"
            if filtering: filtering = '&$filter=' + filtering
            url = f"/Datastreams({Iotid})/Observations?$count=true{select}{filtering}&$top=1"
            status = self._execute_request(url)    # this may take some time
            if not type(status) is list or len(status) < 2:
                return {}
            try:
                result['first' if Status == "first" else "last"] = status[0].get(timestamp,'')
                result['count'] = status[1].get('@iot.count',0)
            except: pass
            return result
        if self.Threading:                         # use multi threading
            results = dict()
            with MyWorkers(WorkerNames='SensorStatus', MaxWorkers=3, Timing=(self.Verbose > 2)) as workers:
                workers.Submit(f'Sensor IoT {str(Iotid)} first',self._SensorStatus,Iotid,Status='first',End=End,Start=Start)
                workers.Submit(f'Sensor IoT {str(Iotid)} last',self._SensorStatus,Iotid,Status='last',End=End,Start=Start)
                workers.Submit(f'Sensor IoT {str(Iotid)} product',self._SensorStatus,Iotid,Status='product')
                #results = workers.Wait4Workers((round(3+2)/3,0)*40)   # wait for results, using different baskits
                results = workers.Wait4Workers()   # wait for results, using different baskits
                if workers.Timing:
                    self._Verbose(f"thread '{workers.WorkerNames}' total time {round(workers.Timing,1)}.",f"Sensor @iot.id '{str(Iotid)}' sensor status timing",3)
            for name, value in results.items():    # handle info about work done, synchronize results
                if not value.get('timing',None) is None:
                    self._Verbose(f"{round(value.get('timing'),1)} seconds",f"Timing get {name}",4)
                if value.get('except',False): raise value.get('except')
                elif type(value.get('result',False)) is dict:
                    result.update(value.get('result'))
                else: raise ValueError("No records found for sensor {str(Iotid)}.")
        else:
            result.update(self._SensorStatus(Iotid,Status='first', Start=Start,End=End))
            result.update(self._SensorStatus(Iotid,Status='last', Start=Start,End=End))
            result.update(self._SensorStatus(Iotid,Status='product'))
        return result                              # empty dict: no records found
    #
    # test: _SensorStatus(sensor IotID) ->
    #                          {'last': ISOstamp, 'first': ISOstamp, 'count': nr}

    # ============ routine _ThingsToDataFrame()
    #
    # convert    selectively Things dicts array to Pandas dataframe array
    #            [{"phenomenonTime":"2024-04-25T03:00:00.000Z","result": 1004.5,}, ...]
    # parameters Things dict with data, select column timestamp and value (list or string)
    # returns    Pandas dataframe: indexed by ascending timestamp in Pandas date format
    def _ThingsToDataframe(self, Data:dict, Timestamp:str="phenomenonTime", ValueCols:list=["result"]) -> Union[pd.core.frame.DataFrame,None]:
        """_ThingsToDataframe: cleanup an observations dataframe"""
        if not type(Data) is list and len(Data) < 1: return None
        if type(ValueCols) is str: ValueCols = [x.strip() for x in ValueCols.split(',')]
        df = pd.DataFrame.from_dict(Data)
        # convert timestamp to Pandas timestamp in UTC
        df[Timestamp] = pd.to_datetime(df[Timestamp], utc=True, yearfirst=True)
        # cleanup the dataframe
        dropping = []
        for _ in df.columns:
            if _ in [Timestamp]+ValueCols: continue
            else: dropping.append(_)
        if dropping: df.drop(columns=dropping, inplace=True)
        df.set_index(Timestamp, drop=True, inplace=True) # indexed by timestamp
        return df

    # =============== get_ThingsObservations() uses multi threading
    # parameters Things sensor datastream IoT id, period (Start dflt None, End dflt None).
    #            Period: Start (default Epoch) <= timestamp < End (default Tomorrow).
    #            timestamp as index, observation sensor data names dflt ["result"]
    # returns    dataframe indexed by ISO timestamped measurements for a sensorID
    #            dataframe index Timestamp (dflt phenomenonTime), column names Result ["result"]
    #            if Data is defined: observations dataframe will be returned in Data[Key].
    # Reminder: pm25_kal, etc. may be lacking and completed later on (granularity is 1H)
    def get_ThingsObservations(self, Iotid:int, Start:Any=None, End:Any=None, Timestamp:str="phenomenonTime", Result:list=["result"],Data:Any=None,Key:Any=None) -> Union[pd.core.frame.DataFrame,None]:
        """get_ThingsObservations: get observations of a Things sensor into dataframe"""
        if not Key: Key = Iotid
        # if None overwrite with class initialisation values
        if not Start: Start = self.Start   # None is from start observations
        Start = ISOtimestamp(Start) if Start else None
        if not End:   End = self.End       # None is observations till recent
        End = ISOtimestamp(End) if End else None
        filtering = ''                         # webside Things query
        select = f"&$select={Timestamp},{','.join(Result)}"
        select += f"&$orderby={Timestamp} asc" # default Things is desc recent first
        #if Start is None and End is None:
        #    raise ValueError("Period missing: Amount of observations can be too many!")
        for idx, key in enumerate([Start,End]):
            if not key: continue
            if filtering: filtering += ' and '
            filtering += f"{Timestamp} {'lt' if idx%2 else 'ge'} {key}"
        if filtering: filtering = '&$filter=' + filtering
        url = f"/Datastreams({Iotid})/Observations?$count=true{select}{filtering}"

        # get measurements/observations for this sensor IoT.id in this period
        dataframe = None; count = 0
        try: # needed for multi threading
          while True: # this is tricky
            self._Verbose(url,"@iot.nextLink",3)
            observations_values = self._execute_request(url) # this may take some time
            if not type(observations_values) is list: break
            if len(observations_values) < 2: break
            url =  observations_values[-1].get('@iot.nextLink',None)
            count = observations_values[-1].get('@iot.count',0)
            if not count: break
            # if @iot.count > 200 next could be done in parallel (not a friendly way).
            # if count > 24*366: url = '' # limit downloads to 1 year?
            if self.Verbose and count < observations_values[-1].get('@iot.count',1):
               self._Verbose(f"downloaded {count} of {observations_values[-1].get('@iot.count')} records.",f"Sensor IoT {Iotid}", 4)
            observations_values.pop(-1)   # ticky it was added by url request
            if not len(observations_values): break
            if dataframe is None:  # timestamp="phenomenonTime", valueCols=["result"]
                dataframe = self._ThingsToDataframe(observations_values)
            else:
                dataframe = dataframe.append(self._ThingsToDataframe(observations_values))
            if not url: break

          if isinstance(dataframe,pd.core.frame.DataFrame):
              count = len(dataframe.index)
              self._Verbose(f"downloaded in total {count} observations.",f"Sensor IoT {Iotid}",3)
          else: return None
          # Next dataframe slicing is needed if Things is not filtering well
          # if Start: dataframe = dataframe[dataframe.index > local_to_pandas(Start)]
          # if End: dataframe = dataframe[dataframe.index < local_to_pandas(End)]
          dataframe = dataframe[~dataframe.index.duplicated(keep='first')]  # remove doubles
          dataframe.sort_index(ascending=True, inplace=True)                # recent timestamps last
          dataframe.dropna(axis=1, inplace=True, how='all')                 # may cause time gaps
          if count > len(dataframe.index):
            self._Verbose(f"Cleaned {count-len(dataframe.index)} rows NaNs or doubles.",f"sensor IoT {Iotid}",3)
        except Exception as e:
          self._Verbose(f"failed with exception {str(e)}.",f"Sensor iot id: {Iotid}.",-1)
          return None
        if Data is None:
          return dataframe # observations in a period Start-End for a sensor IoT.ID
        with self.Sema_Observe: Data[Key] = dataframe
        return None

    # ============== routine _Point()
    # get location GPS coordinates from name station
    @lru_cache(maxsize=16)   # cache is thread save?
    def _Point(self,Name:str) -> list:
        """_Point: (GPS location) from station name"""
        if not Name: return []
        url = f"/Things?$filter=name eq '{Name}'&$select=id&$expand=Locations($select=location/coordinates)"
        try: return self._execute_request(url)[0]["Locations"][0]["location"]["coordinates"]
        except Exception: return []

    #
    # test: get_ThingsObservations(7605, Start='2024-06-01 00:00', Timestamp="phenomenonTime", Result=["result"])

    # ============= routine _ProductID()
    # https://api-samenmeten.rivm.nl/v1.0/Datastreams(40249)/Sensor?$select=name
    # {"name": "DHT22"}      <== name sensor product type
    # get sensor manufacturer product ID for a Things datastream IoT ID
    @lru_cache(maxsize=16)   # cache is thread save?
    def _ProductID(self,IotID:Union[str,int]) -> dict: # get sensorID (product ID)
        """_ProductID"""
        if not IotID: return {}
        url = f"/Datastreams({IotID})/Sensor?$select=name"
        try:
            prod_id = self._execute_request(url).get("name",None)
            if prod_id:
                return {'product':prod_id}
        except: pass
        return {}

    # ================ routine _AddressDone()
    # will be called by MyWorkers done with
    # {'ident': location as str,'result': address as str} from Submit Baskit is func
    # result update self.Addresses cache
    def _AddressDone(self,Result:dict) -> None:
        """call back routine when address for GPS location is found. Called from worker thread"""
        location= Result.get('ident',None)
        if not location: return                               # internal error
        address = Result.get('result', None)
        if address is None:
            logging.warning(f"Address lookup for {location} raised exception")
        if not address: address = ''
        with self.Sema_Addresses:                             # avoid concurrent cache updates
            if self.Addresses.get(location,None):
                self.Addresses[location]['address'] = address
                for baskit in self.Addresses[location].get('baskits',[]):
                    if type(baskit) is list: baskit.append(address)
                if len(self.Addresses) > 20: del self.Addresses[location]
                else:
                    self.Addresses[location]['baskits'] = []
                    self.Addresses[location]['timing'] = round(time(),1)

    # =============== routine _Address will used in multi threading
    # may use Workers thread pool and push bakit in work done result list.
    def _Address(self,Location:Union[str,tuple,list],Baskit:list=None,Workers:MyWorkers=None) -> bool:
        """update addresses cache with address requests via workers, and ready cache"""
        # GPS as string, GPS zone Nld. Things precision is 75 meters, 3 decimals.
        location = Location if type(Location) is str else f"{min(Location[:2]):.6f},{max(Location[:2]):.6f}" 
        with self.Sema_Addresses:
            if self.Addresses.get(location,False):             # used as cache
                if not self.Addresses[location].get('address') is None:
                    self.Addresses[location]['timing'] = round(time(),1)
                    if not type(Baskit) is list: return self.Addresses[location]['address']
                    return Baskit.append(self.Addresses[location]['address'])
                                                               # add to cache
            # cache: [(('5.887,51.458', {'address': 'Timmer 112, steyn, gem. Venray, prov. Limburg', 'baskits': [], 'timing': 1725808951.2}), ...]
            if not self.Addresses.get(location,False):         # place holder
                cnt = len(self.Addresses) - 20
                if cnt >= 0:                                   # make place in cache
                    lru = sorted(self.Addresses.items(), key=lambda x: x[1]['timing'])
                    for one in lru:
                        if one[1]['baskits']: continue         # len cache may get > 20
                        del self.Addresses[one[0]]
                        if len(self.Addresses) < 20: break
                self.Addresses.update({location: {'address': None,'baskits':[],'timing': None}})
            if Workers is None:                                # no threading
                address = StreetMap(location)
                self.Addresses[location]['address'] = address  # save in cache
                self.Addresses[location]['timing'] = round(time(),1)
                if Baskit is None: return address
                elif type(Baskit) is list: Baskit.append(address)
                return True                                    # do not wait
            self.Addresses[location]['timing'] = round(time(),1)
            self.Addresses[location]['baskits'].append(Baskit) # worker completes address later
        Workers.Submit(f'{location}',self._AddressDone,StreetMap,location) # start worker
        
    # =============== routine _AddAddresses() will use multi threading
    # sort dict with geohash (type of clustering) and add humanised location to GPS
    def _AddAddresses(self,stations:dict) -> dict:
        addresses = dict()                     # could be an OrderedDict()
        for n,v in stations.items():           # get locations ready for baskit values
            if not (location :=  v.get('location')): continue
            if type(location) is list and len(location) > 0 and type(location[0]) is tuple:
                addresses[n] = v['location']
        # try to cluster station locations, so cache works better
        addresses = dict(sorted(addresses.items(), key=lambda x: Geohash(x[1][0])))
        self._GetAddresses(addresses)             # query for Open Street Map: can take a while
        for n,v in addresses.items():
            stations[n]['location'] = v
        return stations

    # complete dict with stationName: [GPSlocation, optional distance, ] with humanised address
    # use multi threading if needed
    def _GetAddresses(self, Neighbours:Dict[str,list]) -> None:
        if self.Threading and len(Neighbours) > 1:
            workers = MyWorkers('neighbour addresses',
                # set Maxworkers to 1 while debugging in multi threading modus
                #MaxWorkers=min(len(Neighbours),4),Timing=(self.Verbose > 2))
                MaxWorkers=min(len(Neighbours),1),Timing=(self.Verbose > 2)) # use cache
        else: workers = None
        for baskit in Neighbours.values():                      # work for Open Street Map
            if type(baskit) is list and len(baskit[0]):
                # TO DO: for cluster detection: add geohash to location list
                self._Address(baskit[0],Baskit=baskit,Workers=workers)
        if not workers is None:
            for name, result in workers.Wait4Workers().items(): # wait till work done
                if result.get('timing',None):
                  self._Verbose(f"{result.get('timing'):.1f} seconds",f"timing {str(name)} address",4) 
                if result.get('except'):
                  logging.warning(f"Address for {str(name)} raised exception {str(result.get('except'))}")
            if workers.Timing:
                self._Verbose(f"thread '{workers.WorkerNames}' total timing {workers.Timing:.1f} seconds.","Get stations addresses",3)
            workers.Shutdown()                                  # close workers pool
    #
    # test: _GetAddresses({'LTD_68263': [(6.099,51.447),], 'OHN_gm-2135': [...],...} ->
    #       {'NL1234': [(6.123,51.123),120.5,"Hoogheide 10, Lottum, gem. Venray", ...}

    # ==================== routine get_Neighbours() may use multi threading for Address
    # get neighbour Things stations within range of 10km. (Walter thanks!)
    # https://api-samenmeten.rivm.nl/v1.0/Locations?$filter=geo.distance(location, geography'SRID=4326;POINT(6.099 51.447)') lt 0.02&$select=id,name,location/coordinates
    #{"value": [
    #  { "name": "loc-name-OHN_gm-2135", "@iot.id": 26578,
    #    "location": { "coordinates": [ 6.099, 51.447 ], "type": "Point" },
    #  },
    #  { "name": "loc-name-LTD_68263", "@iot.id": 24349,
    #    "location": { "coordinates": [ 6.099, 51.447 ], "type": "Point" },
    #  },
    #  { "name": "loc-name-LTD_61950", ""@iot.id": 21846,
    #    "location": { "coordinates": [ 6.097, 51.448 ], "type": "Point" },
    #  }]}
    #
    # Things coordinates have a resolution of 3 decimals (about 75 meters)
    # parameters  Point (list, comma sep str or Things station name), in a Range meters (dflt 200),
    #             and SRID (dflt 4326), Top=25 to avoid misuse.
    #             Select=None Use regular expression to select stations name out of the list.
    # returns     dict with neighbouring station names sorted (asc) by distance
    #             from Point, and ordinates (list) of the neighbour.
    # TO DO: add @iot.id, sensors, owners and project of the neighbour
    #        is there a query with orderby distance(location,Point) asc ???
    #        alternative to Station Info:
    #        return: dict(stationName: {'@iot.id': ID, 'location':[(float,float), address:str ],
    #            'sensors': { sensor:
    #                 {'@iot.id':ID,'last':ISOstamp, 'first':ISOstamp, 'count': nr:int}}}, ...)
    # Routine can be used in cluster detection?
    def get_Neighbours(self,Point:Union[str,List[float]],Range:int=None,Max:int=50,Select:str=None, Address:bool=None) -> Dict[str,tuple]:
        """get_Neighbours within a region opf N meters from Point"""
        if Range is None: Range = self.Range
        if Range is None: return {}
        if Address is None: Address = self.Address
        SRID=4326
        location = Point; name = None
        if type(Point) is str:
            m = re.match(r'^\s*[\(\[]?\s*([0-9][0-9\.]+[0-9]+)\s*,\s*([0-9][0-9\.]+[0-9]+)\s*[\[\)]?\s*$',Point)
            if m:
                location = [float(m.groups()[0]),float(m.groups()[1])]
            else:
                name = Point.strip()         # string is a name of a station
                location = self._Point(name) # get GPS location from station name
        if len(location[:2]) != 2: raise ValueError(f"No GPS coordinates for {Point}.")
        location = (min(location[:2]),max(location[:2])) # MET coordinate zone
        url = f"/Locations?$top={Max+1}&$filter=geo.distance(location, geography'SRID={SRID};POINT({' '.join([f'{x:.5f}' for x in location])})') le {Range/100000.0:.4f}&$select=name,location"
        try:
            neighbours = self._execute_request(url)
        except Exception: pass
        if not type(neighbours) is list or not len(neighbours):
            self._Verbose(f"no neighbours found.",f"Location {Point}",1)
            return {}
        if self.Verbose:
          if len(neighbours) > Max:
            self._Verbose(f"has more as {Max} neighbours (increase Max)",f"Location {Point}.",-1)
          self._Verbose(f"Found cluster with {len(neighbours)} stations.",f"Location {Point}{' '+str(location) if name else ''}",4)
        stations = dict()
        for station in neighbours:
            # Things names are mostly prepended with type location name
            _ = station['name'].replace('loc-name-','') # why is this prepended?
            #if name == _: continue                  # excl point station name
            # Select defines reg. expression to select from neigbours stations.
            if type(Select) is str and not re.match(Select,_): continue
            if tuple(station['location']['coordinates'][:2]) == location:
               self._Verbose(f"has same GPS ordinates with {'station' if name else 'point'} {Point}",f"Station {_}",6)
            stations[_]=tuple(station['location']['coordinates'][:2]) # or as string?
        # add distance to station value. And sort ascending of distances
        for N,L in stations.items():               # to do: add geohash?
            # [(lon,lat),meters to Point,humanised address]
            try: stations[N] = [L,GPSdistance(location,L)]  # L is hashable?
            except: stations[N] = [L,None]
        # only Max neighbours nearby Point station
        stations = dict(OrderedDict(sorted(stations.items(),key=lambda x:(Range if x[1][1] is None else x[1][1]),reverse=False)[:Max]))
        self._Verbose(f"Selected {len(stations)} {('(incl '+name+') ') if name else ''}neighbouring stations.",f"{'Station' if name else 'Point'} {Point}",3)
        if Address or self.Humanise: self._GetAddresses(stations)
        return stations
    #
    # tests: get_Neighbours('LTD_68263' or '6.099,51.447', Range=500)
    #                -> {name: [GPS:tuple,distance:float,address:str]

    # ================= ROUTINE get_StationInfo() will use multi threading
    # meta information station, returns dict with meta info: municipality,owner,project,location
    # Q: what is the properties naming procedure of XYZcodes ? Reference station?
    # Q: what is the naming procedure of station names? XYZ_idNr: XYZ?
    # OCG filtering functions: https://docs.geoserver.org/stable/en/user/
    # TO DO: select from properties only codegemeente, owner, project?
    # HowTo get Things data via station name:
    # from: https://api-samenmeten.rivm.nl/v1.0/Things?$filter=name eq 'LTD_68263'&select=id,name,description,properties&$expand=Locations,Datastreams
    #{  # station LTD_68263
    #"value": [
    #  {
    #     "@iot.id": 7605,                       <=
    #     "name": "LTD_68263",
    #     "description": "LTD_68263",
    #     "properties": {
    #        "codegemeente": "1507",             <== ?
    #        "knmicode": "knmi_06391",
    #        "nh3closecode": "NL10131",
    #        "nh3regiocode": "NL10131",
    #        "nh3stadcode": None,
    #        "no2closecode": "NL10131",
    #        "no2regiocode": "NL10131",
    #        "no2stadcode": "NL10741",
    #        "owner": "Luftdaten",               <==
    #        "pm10closecode": "NL50006",
    #        "pm10regiocode": "NL50006",
    #        "pm10stadcode": "NL10741",
    #        "pm25closecode": "NL50006",
    #        "pm25regiocode": "NL50006",
    #        "pm25stadcode": "NL10741",
    #        "project": "Luftdaten"               <==
    #     },
    #     "Locations": [ {
    #           "@iot.id": 24349, "name": "loc-name-LTD_68263",
    #           "description": "loc-desc-LTD_68263",
    #           "encodingType": "application/vnd.geo+json",
    #           "location": { "coordinates": [6.099, 51.447], "type": "Point" }  <==
    #        }] ,
    #     "Datastreams": [ {
    #          "@iot.id": 40249,                  <==
    #          "@iot.selfLink": "https://api-samenmeten.rivm.nl/v1.0/Datastreams(40249)",
    #          "name": "LTD_68263-6-pres",        <==
    #          "description": "LTD_68263-6-pres",
    #          "unitOfMeasurement": { "definition": "...", "symbol": "hPa" },     <==
    #          "observationType": "...",
    #          "Thing@iot.navigationLink": "...",
    #          "Sensor@iot.navigationLink": "https://api-samenmeten.rivm.nl/v1.0/Datastreams(40249)/Sensor",
    #          "Observations@iot.navigationLink": "https://api-samenmeten.rivm.nl/v1.0/Datastreams(40249)/Observations",               <== can be generated from @iot.id
    #          "ObservedProperty@iot.navigationLink": "https://api-samenmeten.rivm.nl/v1.0/Datastreams(40249)/ObservedProperty"
    #       }, ...]}
    # get meta information of station name
    # parameters    Name:str station, Address:bool, ProductID:bool,
    #               Neighbours: max range region for neighbouring stations (max nr self.Neighbours) 
    #               if parameter is None, value is left to class defaults
    #               Sensors (deflt None) reg. expression for senors to get
    #                       'count' of observations per sensor and first/last UTC timestamp,
    #               Using period Start-End from roution parameter or class.
    # returns       dict (gemeentecode (municipality code:int) or municipality name:str, owner, project, address,
    #                     (GPS) location [long,lat], id (IotID:int),
    #                     sensors dict SensorName: {@iot.id,symbol,product, count, last, first}, ...
    # Address on/off humanised address, productID on/off sensor product ID, Neighbours on/off
    # TO DO (discussion): iso boolean parameters give Meta dict with info shopping list as parameter
    # TO DO: get first and last date of observations of the station (use $top=1)
    #        query:
    #        Datastreams(@iot.id sensor)/Observations/?$count=true&$select={Timestamp}&$orderby={Timestamp} asc&$top=1
    #        Datastreams(@iot.id sensor)/Observations/?$count=true&$select={Timestamp}&$orderby={Timestamp} desc&$top=1
    # Reminder: @iot.id's have limited Time To Live, they may change in time!

    # next routine will be depreciated!
    def get_StationInfo(self, Name:str, Address:bool=None, Neighbours:Union[int,bool]=None, Sensors:str=None, Start:Any=None, End:Any=None) -> Dict:
        """get_StationInfo meta info about station Name optional with: Address, Product ID,
           Neighbours (default region),
           External info requests are done (default) via multi threading.
           add sensor status if self.Status (record count, timestamps first/last.
           returns dict with Things ID, project, owner, location,
           municipality, sensor Things ID's and Humanised sensor info."""

        if Address    is None: Address = self.Address     # add address from GPS
        neighbours = self.Neighbours                      # max nr neighbours
        region     = self.Range                           # default region range in meters
        if type(Neighbours) is int:
            if Neighbours > 0:
                region = Neighbours                       # not default region range?
                neighbours = True
            else: neighbours = False
        elif type(Neighbours) is bool: neighbours = Neighbours
        else: neighbours = False
        if Sensors:
            if type(Sensors) is bool: Sensors = r'^.*$'
            elif not type(Sensors) is str: Sensors = None
            elif Sensors.find(',') > 0:                   # comma separated list, convert to reg exp
                Sensors = Sensors.lower().replace('pm2.5','pm25')
                Sensors = Sensors.replace(' kal','_kal')
                Sensors = Sensors.replace(', ','|')
                Sensors = Sensors.replace(',','|')
                Sensors = Sensors.replace('%','')
                Sensors = '^('+Sensors+')$'
        # if None overwrite with class initialisation values
        if not Start: Start = self.Start   # None is from start observations
        Start = ISOtimestamp(Start) if Start else None
        if not End:  End = self.End        # None is observations till recent
        End = ISOtimestamp(End) if End else None

        # self.URL has host service method and access URL info
        url = f"/Things?$filter=name eq '{Name}'&$select=id,properties&$expand=Locations($select=location),Datastreams($select=id,name,unitOfMeasurement)"
        meta = OrderedDict()
        # identification string
        try:
            station_info = self._execute_request(url)
            if not type(station_info) is list or not station_info:
                raise ValueError(f"No information found for station {Name}")
            else: station_info = station_info[0]          # only first of list is handled
            # get meta station/node info with identified keys, key values may be None
            # prepare dict result:
            #  { id, municipality:str, owner:str, project:str, address:str,
            #    {sensor name: [@iot.id, unit symbol, optional sensor product ID],  ...},
            #    coodinates:list, neighbours: list ordered by distance asc}
            item = station_info.get("@iot.id") # needed for observation streams sensors
            if not item:
                logger.warn(f"No information found for station {Name}")
                return {}
            # identification info
            meta["Samen Meten Tools"] = f"{__version__}"
            meta[f"Station {Name}"] = (datetime.datetime.now()).strftime('%Y-%m-%d %H:%M%Z')
            meta["@iot.id"] = str(item)                   # Things @iot.id internal use

            workers = None
            if self.Threading:                            # requests with multi threading
                # use MaxWorkers=1 when debugging threads in simulation modus
                workers = MyWorkers(WorkerNames='StationInfo', MaxWorkers=8, Timing=(self.Verbose > 2))
            # filter on codegemeente, owner and project
            properties = station_info.get("properties",{}).keys()
            for item in set(station_info.get("properties",{}).keys()) & set(['codegemeente','owner','project']):
                value = station_info["properties"].get(item,None)
                if not value: continue
                if item == 'codegemeente' and Address:    # humanise municipality code
                    if workers:
                        workers.Submit('municipality',Municipality_NameCode,value)
                    else:
                        try: meta['municipality'] = Municipality_NameCode(value)
                        except: pass
                else: meta[item] = value
            # get station 'location': GPS ordinates, optional address and 'neighbours'/addresses
            try:
                # meta['location'] = list[GPS:tuple[float,float], optional address:str]
                ordinates = station_info["Locations"][0]["location"].get("coordinates",[])
                if type(ordinates) is list and len(ordinates) >= 2:
                    meta["location"] = tuple(ordinates[:2])
                    if Address:
                        if workers:
                            workers.Submit('address',StreetMap,meta["location"])
                        else:
                            meta["address"] = StreetMap(meta["location"])
                            if not meta["address"]: del meta["address"]
                    if neighbours and len(meta["location"]) and region > 0:
                        # meta['neighbours'] = dict[stationName:str,list[GPS:tuple,optional address:str}
                        meta['neighbours'] = OrderedDict()
                        if workers:
                            # next will push addresses lookup in this wokers pool
                            # this will casue another (sub)pool of workers.
                            workers.Submit('neighbours',meta['neighbours'],self.get_Neighbours,meta["location"],Range=region,Address=True)
                        else:
                            meta['neighbours'] = self.get_Neighbours(meta["location"],Range=region,Address=Address)
                            if not meta['neighbours']: del meta['neighbours']
            except Exception: pass
            # meta["sensors"] = {name: [@iot.id:int,unitSymbol:str,sensorProductID:str], ... }
            # sensorTypes may change during measurements or station with sensor types?
            # if so: more datastreams per station with same sensor type name?
            # Things maps different sensors of same type on one datastream?
            meta["sensors"] = {} 
            # { sensor:str:    { '@iot.id":str, 'symbol':str,
            #                     optional 'product':str,
            #                     optional 'status':{'count':int,'last':date,'first':date} }
            for item in station_info.get("Datastreams",[]): # 5 -10 sensors per station
                sensor = item.get("name",[]).split('-')[-1] # sensor name part
                if not sensor: continue
                try: meta["sensors"][sensor] = {"@iot.id":str(item["@iot.id"])}
                except Exception: continue
                meta["sensors"][sensor]['symbol'] = item["unitOfMeasurement"].get('symbol','')
                # next can take about 10-15 seconds per sensor
                if self.ProductID:
                    if workers:    # use dict as baskit for results of type dict
                        workers.Submit('product',meta["sensors"][sensor],self._ProductID,meta["sensors"][sensor]['@iot.id'])
                    else:
                        meta["sensors"][sensor].update(self._ProductID(meta["sensors"][sensor]['@iot.id']))
                        if not meta["sensors"][sensor]['product']:
                            del meta["sensors"][sensor]['product']
                if Sensors and re.match(Sensors,sensor):
                                   # is status last enough to request for?
                    meta["sensors"][sensor]['status'] = dict()
                    if workers:    # avoid concurrent (Sema Workers)
                        workers.Submit(f"{sensor}",meta["sensors"][sensor]['status'],self._SensorStatus,meta["sensors"][sensor]['@iot.id'], Status='first',Start=Start,End=End)
                        workers.Submit(f"{sensor}",meta["sensors"][sensor]['status'],self._SensorStatus,meta["sensors"][sensor]['@iot.id'], Status='last',Start=Start,End=End)
                    else:
                        meta["sensors"][sensor]['status'].update(self._SensorStatus(meta["sensors"][sensor]['@iot.id'], Start=Start, End=End))
                        if not meta["sensors"][sensor]['status']:
                            del meta["sensors"][sensor]['status']
                # {name:{@iot.id,unitSymbol,sensor ProductID, nr records, first, last} ...}
        except ValueError as ex:
            self._Verbose(f"{str(ex)}","WARNING",0)
        except Exception as ex:
            self._Verbose(f"failed to get meta info for Station {Name}: {str(ex)}","WARNING",0)
        if workers:
            results = workers.Wait4Workers()
            if workers.Timing:
                self._Verbose(f"thread '{workers.WorkerNames}' total timing {round(workers.Timing,1):.1f} seconds.",f"Station {Name} external requests",3)
            workers.Shutdown()
            for name, result in results.items():
                if result.get('timing',False):
                    self._Verbose(f"{str(result.get('timing'))} seconds.",f"Station info timing '{name}'",4)
                value = result.get('result',False)
                if value:
                    if   name == 'address': meta['address'] = value
                    elif name == 'municipality': meta['municipality'] = value
                    elif name == 'neighbours':   # addresses look up in this wokers pool
                        meta['neighbours'] = value
                        if Address:              # add addresses in separate workers pool
                            self._GetAddresses(meta['neighbours'])
                    elif name in meta['sensors'].keys():
                        if type(value) is dict:  # should not happen
                            meta["sensors"][name].update(value)
                        else: raise ValueError(f"Type value {str(value)} for sensor {name} not implemented.")
                    else:
                        logging.warning(f"Station info {Name}: unknown info name '{name}'.")
                   
                exc = result.get('except',None)
                if not exc is None:
                    logging.warning(f"Station {Name} info request '{name}' raised exception '{str(exc)}'.")
        return dict(meta)
    #
    # test example: get_StationInfo('NBI_BV211',Address=True) ->
    # OrderedDict([   ('Samen Meten Tools', 'SamenMetenThings.py V2.7'),
    #           ('Station NBI_BV211', '2024-08-21 10:51'), ('@iot.id', '2716'),
    #           ('project', 'Boeren en Buren'), ('owner', 'NB-IoT'),
    #           ('location', (5.921, 51.534)),
    #           ('municipality', 'Venray'),
    #           (   'address', 'Op de Ries 14, Merselo, gem. Venray, prov. Limburg'),
    #           (   'neighbours',
    #               OrderedDict([   (   'NBI_BV211',
    #                                   [   (5.921, 51.534), 0,
    #                                       'Op de Ries 14, Merselo,
    #                                       'gem. Venray, prov. Limburg'])])),
    #           (   'sensors',
    #               {   'pm10_kal': {   '@iot.id': '12949', 'symbol': 'ug/m3',
    #                                   'product': 'Nova SDS011',
    #                                   'status': {   'first': '2019-07-01T17:00:00.000Z',
    #                                                 'last': '2024-08-21T07:00:00.000Z',
    #                                                 'count': 28587}}
    #                   'pm10': {   '@iot.id': '12948', 'symbol': 'ug/m3',
    #                               'product': 'Nova SDS011',
    #                               'status': {   'first': '2019-07-01T17:00:00.000Z',
    #                                             'last': '2024-08-21T08:00:00.000Z',
    #                                             'count': 28586}}
    #                   'pm25_kal': {   '@iot.id': '12947', 'symbol': 'ug/m3',
    #                                   'product': 'Nova SDS011',
    #                                   'status': {   'first': '2019-07-01T17:00:00.000Z',
    #                                                 'last': '2024-08-21T07:00:00.000Z',
    #                                                 'count': 28586}}
    #                   'pm25': {   '@iot.id': '12946', 'symbol': 'ug/m3',
    #                               'product': 'Nova SDS011',
    #                               'status': {   'first': '2019-07-01T17:00:00.000Z',
    #                                             'last': '2024-08-21T08:00:00.000Z',
    #                                             'count': 28586}}})])

    # ==================== ROUTINE get_StationData() will use multi threading
    #
    # from: https://api-samenmeten.rivm.nl/v1.0/Things(7605)/Datastreams?$select=id,name,unitOfMeasurement
    #{  # station LTD_68263 -> @iot.id 7605
    #"value": [
    # {
    #    "@iot.id": 40249,
    #    "name": "LTD_68263-6-pres",
    #    "unitOfMeasurement": {
    #       "definition": "https://qudt.org/vocab/unit/HectoPA",
    #       "symbol": "hPa"
    #    }
    # }, ...]}

    # get per Sensor observervations from Things name:
    # Start, End are typed Union[None,str] where str is date string like YYYY-MM-DD HH:MM local
    # Sensors is typed as Union[None,[()|str, ...]] (TO DO: select Sensors as regular expression)
    # if a value is None: class defaults may overwrite parameter value.
    # parameters Name station, period: Start - End None (default) will say: infinity
    #         optional add sensor (Product) ID?, humanised Address:bool,
    #         humanised Address:bool, Humanise:bool, list of Sensors (dflt: all sensors).
    #         Humanise will say: with unit symbol and sensor prodduct ID
    #         Sensors names are converted to Things sensor names.
    #         If Sensors is regular expression: apply as filter sensor names for observations.
    #         If parameter value is not None it will overwrite class global parameter definitions.
    # returns dict with meta info and key "observations" (Pandas dataframe indexed by "timestamps"
    #         in ISO timestamp format, column sensor names humanised? if defined.
    #         e.g. 'pm25_kal' -> 'PM2.5 (gekalibreerd) ug/m3 (SPS30)' or 'pres' -> 'press hPa'
    #         Address, sensor status, Humanise are typed Union[None,bool]
    def get_StationData(self, Name:str, Address:bool=None, Humanise:bool=None, Start:Any=None, End:Any=None, Sensors:str=None, Neighbours:bool=None) -> Dict[str,Any]:
        """get_Station_Data: station meta info as dict, Things observations as Pandas dataframes.
           Things website observation requests are done with multi threading ON (default).
           Optional info for: location Address, Neigbouring stations (region boundary),
           Status Things observations Status station (record count, first/last stamps),
           Humanised info in optional Utf8 format, period (local time, default fully), 
           Sensors required (default all, regular expression, or list in Things senor format.
           Returns station info dict with entry: 'observations' (Pandas dataframe)."""

        if Start     is None: Start = self.Start     # period to download observations
        if End       is None: End = self.End         # None: as much as is available
        if Sensors   is None: Sensors = self.Sensors # default sensor names
        Range = self.Range
        if type(Neighbours) is int:
            if Neighbours > 0:
                Range = Neighbours; neighbours = True
            else: neighbours = False
        elif type(Neighbours) is bool: neighbours = Neighbours
        else: neighbours = False

        dataframes = OrderedDict()                   # observations per ordered Sensors
        # get meta info about Things station. Can take 15 upto 30 or even 60 seconds.
        Meta = {}
        # Meta info request takes between 15 secs to 50 secs with all options as True
        # Meta will have all sensors in period of time.
        Meta = self.get_InfoNeighbours(Name, Region=0, By=("id,name,location" + (",address" if Address else "")), Select=None, Sensors=Sensors, Start=Start, End=End)
        Name = list(Meta)[0]; Meta = Meta.get(Name)
        if not Name or not Meta or not Meta.get("@iot.id",False):
            logging.warning(f"Station '{str(Name)}: WARNING: Things station is unknown.")
            return {}
        Meta['name'] = Name
        if Meta.get('location') and neighbours:       # optional add neighbours info
            Meta['neighbours'] = self.get_Neighbours(Meta["location"][0],Range=Range,Address=Address)
            if not Meta['neighbours']: del Meta['neighbours']

        # the real work: add sensor observations to Things station meta info dict
        # can take about 15 secs per sensor.
        Meta['observations'] = None
        if not Sensors: # use all Things sensor for this station (default)
            Sensors = [s[0] for s in Meta['sensors'] if s and s[0]]
        if not Sensors: return Meta
        pattern = None
        if type(Sensors) is str:              # collect selection of available sensors
            Sensors = Sensors.replace('2,5','25')
            Sensors = [x.strip() for x in Sensors.split(',')]
            # need to apply a regular expression to filter sensor names
            if len(Sensors) == 1 and re.match(r'.*[\.\*\[\(^\$]',Sensors[0]):
                pattern = Sensors[0]; Sensors = []
                for sensor in Meta["sensors"].keys():
                    if re.match(pattern,sensor,re.I): Sensors.append(sensor)

        if self.Threading:                   # thread debugging? Use MaxWorkers=1
            workers = MyWorkers(WorkerNames='Things observations', MaxWorkers=min(6,len(Sensors)), Timing=(self.Verbose > 2))
            # worker ready call back routine
            #def _ObservationDone(Result:dict) -> None:
            #    """call back routine when observations worker is done.
            #    Called from worker thread when done."""
            #    sensor = Result.get('ident',None)
            #    if not sensor: return        # internal error
            #    data = Result.get('result', None)
            #    if data is None:
            #        logging.warning(f"Data request for {Name}:{sensor} raised exception")
            #        return            
            #    with self.Sema_Observe: # avoid concurrent cache updates
            #        dataframes[sensor] = data
            #
        else: workers = None

        # collect sensor observations in Pandas dataframes
        for sensor in Sensors:               # get sensor names in Things format
            sensor = self.HumaniseClass.DehumaniseSensor(sensor, strict=True)
            # Meta["sensors"] dict key Things sensor name: [IoTid,symbol,productID]
            if not sensor in Meta["sensors"].keys() or not Meta["sensors"][sensor]:
                self._Verbose(f"station has no Things {sensor} sensor or no sensor observations.",f"Station {Name}",-1)
                continue
            elif Meta["sensors"][sensor].get('count'):
               if Start and Meta["sensors"][sensor].get('last'):
                 if ISOtimestamp(Start) > Meta["sensors"][sensor].get('last'):
                     self._Verbose(f"has no observation in period {Start} - {End}.",f"Station {Name} sensor {sensor}",0)
                     continue
               if End and Meta["sensors"][sensor].get('first'):
                 if ISOtimestamp(End) < Meta["sensors"][sensor].get('first'):
                     self._Verbose(f"has no observation in period {Start} - {End}.",f"Station {Name} sensor {sensor}",0)
                     continue
            if not Meta['sensors'].get(sensor) or not Meta['sensors'][sensor].get('@iot.id'):
                logging.warning(f"Observations {name} no IoT.ID sensor {sensor} defined.")
                continue  # should not happen

            # update dict Meta['sensors'][sensor]: {sensor IoT.id,
            #     symbol, prodID, status {}}  with dataframe indexed by 'phenomenonTime',
            #     from worker 'result' with observations
            # takes about 15 secs per sensor
            if not workers:
                try:
                    dataframes[sensor] = self.get_ThingsObservations(
                        Meta['sensors'][sensor]['@iot.id'], Start=Start, End=End)
                except Exception as exc:
                    logging.warning(f"Observations {name} raised exception {str(exc)}.")
            else:
                dataframes[sensor] = None       # make sure ordered key is allocated
                #workers.Submit(f"{sensor}",_ObservationDone, # more secure (slower) way
                workers.Submit(f"{sensor}",     # only OK with sensor Submissions
                        self.get_ThingsObservations,Meta['sensors'][sensor]['@iot.id'],
                        Start=Start,End=End)
        if workers:
            self._Verbose(f"get observations from sensor {sensor}",f"Station {Name}",1)
            results = workers.Wait4Workers()  # pick up work done info (timing, events)
            if workers.Timing:
                self._Verbose(f"thread '{workers.WorkerNames}' total time {round(workers.Timing,1)}.",f"Station {Name} sensor observations",3)
            workers.Shutdown()
            # sorted as sensor names are ordered list -> list[tuple[str,dict], ...]
            for work in sorted(results.items(), key=lambda item: item[1]['nr']):
                name,result, = work           # one tuple per sensor
                if 'timing' in result.keys():
                    self._Verbose(f"request observations timing {result.get('timing'):.1f} seconds.",f"{Name}:sensor '{name}'",4)
                if not result.get('result') is None:
                    dataframes[name] = result.get('result')
                if not result.get('except') is None:
                    logging.warning(f"Station {Name} sensor observations '{name}' raised exception {str(result.get('except'))}.")

        if self.Humanise:
            for sensor in Meta['sensors'].keys():
                if not Meta['sensors'][sensor]: continue
                if Meta['sensors'][sensor].get('symbol',False): # humanise symbol
                    Meta['sensors'][sensor]['symbol'] = HumaniseClass(utf8=self.Utf8).HumaniseSensor(Meta['sensors'][sensor]['symbol'])
        Meta['observations'] = None
        for sensor in dataframes.keys():      # sorted from Sensors list
            try:
              if type(dataframes[sensor]) is pd.core.frame.DataFrame and not dataframes[sensor].empty:
                sensorName = sensor           # sensor
                if self.Humanise:
                    try:
                        sensorName = HumaniseClass(utf8=self.Utf8).HumaniseSensor(sensorName, Humanise=True)
                        if Meta['sensors'][sensor].get('symbol'):
                          sensorName += f" {Meta['sensors'][sensor]['symbol']}"
                        if Meta['sensors'][sensor].get('product'):
                          sensorName += f" ({Meta['sensors'][sensor]['product']})"
                        Meta['sensors'][sensor]['sensor'] = sensorName     # overwrite iot.id
                    except: pass
                dataframes[sensor].rename(columns={"result":sensorName}, inplace=True)
                dataframes[sensor].index.rename('timestamps',inplace=True)
              else:
                self._Verbose(f"Unable to get observation for sensor {sensor}",f"Station {Name}",0)
                continue
              if Meta['observations'] is None:
                Meta['observations'] = dataframes[sensor]
              else:
                Meta['observations'] = pd.merge(Meta['observations'], dataframes[sensor], on='timestamps', how='outer')
            except Exception as e:
                self._Verbose(f"exception {str(e)} with sensor {sensor}",f"Station {Name}",-1)
        # Meta clean up dict: empty keys. @iot.id's have limited lifetime: cleared.
        if Meta['observations'] is None or Meta['observations'].empty:
            del Meta['observations']
        # it is unclear if @iot.id survives a longer period. May need to delete those.
        # if Meta.get('@iot.id',False): del Meta['@iot.id'] and all sensors iot.id.
        for n,v in  Meta.items():             # clean up on highest dict level
            if v is None: del Meta[n]
        #for sensor in Meta['sensors'].keys(): # clean up all @iot.id sensor id's
        #    if  Meta['sensors'][sensor].get('@iot.id',False): del Meta['sensors'][sensor]['@iot.id']
        return Meta
    #
    # test ('LTD_68263',Sensors='^pm10_kal',Humanise=True,start='2023-03-01 06:00', End='2023-03-04',Address=True,Neighbours=1000) ->
    # { '@iot.id': 7605, 'name': 'LTD_68263',
    #   'neighbours': OrderedDict([ # (name, [GPS,distance,street]),
    #      ('LTD_68263', [(6.099, 51.447), 0, 'Hoog 1, Lo, gem. Horst, prov. Lmbg']),
    #      ('OHN_gm-2135', [(6.099, 51.447), 0, 'Hoog 1, Lo, gem. Horst, prov. Lmbg']),
    #      ('LTD_61950', [(6.097, 51.448), 177, 'Los 4, Lo, gem. Horst, prov. Lmbg'])])
    #   'location': [(6.099, 51.447),'Hoog 1, Lo, gem. Horst, prov. Lmbg']`],
    #   'sensors': {'pres': None, 'rh': None, 'temp': None, 'pm10': None,
    #       'pm10_kal': {'@iot.id': 40246, 'symbol': 'μg/m³', 'product': 'Nova SDS011',
    #                    'first': '2023-03-01T05:00:00.000Z', 'count': 25,
    #                    'last': '2023-03-02T06:00:00.000Z', 'sensor': 'PM₁₀ kal'},
    #       'pm25_kal': None, 'pm25': None},
    #    'observations': #     dataframe timestamps sensor type/value ...:
    #           timestamps                 PM₁₀ kal
    #           2023-03-01 05:00:00+00:00    25.704
    #           2023-03-01 06:00:00+00:00    34.304
    #           ...}

# ================================================================================
################## command line tests of (class) subroutines or command line checks
if __name__ == '__main__':

    import gzip
    import json
    def help() -> None:
        sys.stderr.write(
        f"""
Some test cases for how to use the routines:
    Address=GPSordinates (comma separated) Get humanised address of GPScoordinates
                                           e.g. '5.12345,54.12345'.
    Dehumanise=sensor_name                 Convert sensor name to Things sensor name.
    HumaniseName=sensor_name               Humanise sensor string:
                                           e.g. 'pm25_kal ug/m3 (SPS30)'.
    Select=None                            Get only these station names from output list.
    Verbosity=5                            Set verbosity level. 0 is low.
    MunicipalityName=name                  Get municipality name -> code or visa versa.
    Properties=name                        Show also these properties e.g. owner,project.
    MunicipalityStations=gemeentecode      Get list of Things stations in municipality
                                           region. Municipality code or name or
                                           station name in region.      
                                           Names can be filtered (Reg Exp Select, optional).
    Period=2030-12-31 00:00,2030-12-31 00:01 Define period of observations.
    Threading=OFF                          Do not use Thread Workers Pool.
                                           Verbosity level 3+ will turn thread timing messaging ON.
    Region=500                             Set neigbouring range to N (dflt 500) meters.
    InfoNeighbours=Things_station_name     Get list (GPS,meters)  of neighbouring
                                           Things stations with optionally within range (dflt 500)
                                           meters from station name with optionally  GPS location
                                           and humanised address. Default maximal 50 neighbours.
                                           Names can be filtered (Reg Exp Select, optional).
    InfoNeighbours=municipality_name       Get meta information about Things station.
                                           This operation can take quite some time.
    Sensors=pm10,pm25,.. (comma separated) Define sensors to get observations from.
                                           (command default:pm25).
                                           Sensors may be defined as regular expression applied to
                                           Things sensor names: e.g.
                                           '^(pm(10|25)|rh)' matches: pm25,pm25_kal,pm10,pm10_kal,rh
    StationData=Things_station_name        Get station meta info and observation in a period.
                                           This operation can take quite some time.

    Command line (test) examples (dflts: region 500, threads OFF, thread timing on, verbosity 5):
        # get 'humanised' name of a pollutant sensor
        command HumaniseName='pm25_kal ug/m3 (SPS30)'
        # get bare name of a sensor (strict may be more 'bare')
        command Dehumanise=sensor_name='PM2.5 (gecalibreerd) (SPS30)'
        # get municipality name belonging to gemeentecode 14, or other way around
        command MunicipalityName=14 MunicipalityName=Haarlem
        # get human address from Open Street Map via GPS coordinates: 'lat,lon'
        command Address="51.44700,6.09900"
        # get neighbours within range order by distance from station or GPS location
        command Threading=ON Region=1000 Neighbours=LTD_78914
        # get station names within municipality via gemeentecode,gemeente,station name
        command InfoNeighbours=14 InfoNeighbours=LTD_78914
        command Threading=ON Select='^(LTD|OHN).*' Properties=owner,project,address InfoNeighbours=Venray
        # get meta information of a station
        command Threading=OFF Region=0 ProductID=true InfoNeighbours=OHN_gm-2135
        # get calibrated PM observations of a Things station within fireworks period of time
        command Period='2024-07-14,2024-07-15' Sensors='pm25,pm10,rh' Region=200 StationData=LTD_50460
        command Period='2023-03-01 06:00,2023-03-04' Sensors='^pm(25|10)_kal' StationData=LTD_68263
        """)

    # if pprint is available use pretty print
    def print_test(key:str,val:Any,result:Any) -> None:
       print(f"'{key}' arg '{str(val)}' -> ",end='')
       try:
           import pprint  # pretty print data structure
           if type(result) is dict:
              print("dictionary item(s):")
              for item,value in result.items():
                  if type(value) is pd.core.frame.DataFrame:
                      print(f"{item} (Pandas dataframe):")
                      print(f"\tRecords: first {pandas_to_local(value.index[-1])}, last {pandas_to_local(value.index[0])}, total {len(value.index)} records")
                      print(f"\tNames: {value.index.names[0]} (index), sensors: {', '.join(list(value.columns))}.")
                      #print("\t",value.info())
                      print("\t",value.head())
                  else:
                      print(f"\t'{item}: ",end='')
                      pprint.pp(value,compact=True,indent=4)
           else:
              print("list item(s):")
              pprint.pp(result,compact=True,indent=4)
       except:
           if type(result) is dict:
              print("dictionary item(s):")
              if type(value) is list or type(value) is tuple:
                  print(f"\t'{item}: {value}'")
              elif type(value) is pd.core.frame.DataFrame:
                  print(f"{item} (Pandas dataframe):")
                  print(f"\tperiod: {value.index[-1]} upto {value.index[0]}")
                  print("\t",value.info(),'\n\t',value.head())
              else: print(f"\t'{item}: {value}'")
           elif type(result) is list:
              print("list item(s):")
              print(f"\t'{', '.join(result)}'")
           else: print(f"'{str(result)}'")


    if len(sys.argv) <= 1: help()
    Tests = {}
    for i,arg in enumerate(sys.argv[1:]):
        if not Tests:
             # tests defaults
            Tests = {
                    #'Region':200,                 # add neighbours within 200 meters range
                    #'Period':['2024-07-01 00:00',None], # get observations in period after 2030
                    'Sensors':'pm25',             # get sensors of type PM2.5
                    'Select':None,                # do not filter sensors names (dflt)
                    'Properties':'name',          # get only stations names (dflt municipality)
                    'Threading':'ON',             # do not use Threadinmg Workers Pool
                    'ProductID': False,              # add status sensors station
                    'Verbosity': 5,               # Samen Meten class verbosity level
                    }
        if re.match(r'^(--)?help$',arg,re.I):
            help()
            Tests =  {}
            break
        m = re.match(r'^(--)?([^\s]*)\s*=\s*([^\s]+(.*[^\s])*)\s*$', arg)
        if not m: continue
        # routine parameter definitions
        if m.groups()[1] == 'Region':             # 10 km max range
            Tests['Region'] = min(int(m.groups()[2]),10000)
        elif m.groups()[1] == 'Period':           # period Start upto END local date/time
            Tests['Period'] = [x.strip() for x in m.groups()[2].strip().split(',')]
            if len(Tests['Period']) < 2: Tests['Period'].append(None)
        elif m.groups()[1] == 'Sensors':          # define sensors to get observations for
            Tests['Sensors'] = m.groups()[2].strip()
            if re.match(r'^None$',Tests['Sensors']): Tests['Sensors'] = None
        elif m.groups()[1] == 'Select':           # regexp to select station names
            Tests['Select'] = m.groups()[2].strip()
        elif m.groups()[1] == 'Properties':       # regexp to select station properties
            Tests['Properties'] = m.groups()[2].strip()
        elif m.groups()[1] == 'ProductID':        # boolean sensor/station info
            Tests['ProductID'] = True if m.groups()[2].strip().lower() == 'true' else False
        elif m.groups()[1] == 'Verbosity':        # define verbosity level (default 5)
            if m.groups()[2].strip().isdigit():
                Tests['Verbosity'] = int(m.groups()[2].strip())
            else: Tests['Verbosity'] = 0
        elif m.groups()[1] == 'Threading':        # turn on/off multi threading (default OFF)
            Tests['Threading'] = m.groups()[2].strip()
            if re.match(r'(ON|TRUE)',Tests['Threading'],re.I): Tests['Threading'] = True
            else: Tests['Threading'] = False
        elif m.groups()[2].strip().isdigit():     # @iot.id
            Tests[f"test {i}: " + m.groups()[1]] = int(m.groups()[2].strip())
        else:
            Tests[f"test {i}: " + m.groups()[1]] = m.groups()[2].strip()

    # Humanise: show UTF-8 characters turned on
    if Tests:
        print(f"Multitheading is {Tests['Threading']}, verbosity level is {Tests['Verbosity']}.")
    SamenMetenPandasClass = None
    for test,val in Tests.items():
        if not re.match('test',test): continue

        # coroutines tests
        elif re.match('.+HumaniseName',test,re.I): # Humanise test
            result = HumaniseClass(utf8=True).HumaniseSensor(val, Humanise=True)
            print_test(test,val,result)
        elif re.match('.+Dehumanise',test,re.I):  # sensor dehumanise test (use strict=True)
            result = HumaniseClass(utf8=True).DehumaniseSensor(val, strict=True)
            print_test(test,val,result)
        elif re.match('.+MunicipalityName',test,re.I):
            #result = MunicipalityName(val)       # Open Data Soft faster, less up to date
            #print_test(test,val,result)
            result = Municipality_NameCode(val)   # TOOI standaarden.overheid.nl API test
            print_test(test,val,result)
        elif re.match('.+Address',test,re.I):     # Address (humanised) from Open Street Map
            result = StreetMap(str(val))
            print_test(test,val,result)

        else: # Things class routines (Select, Range, etc. are optional arguments)
            if not SamenMetenPandasClass:
                SamenMetenPandasClass = SamenMetenThings(
                        Verbosity=Tests['Verbosity'], # high verbosity level
                        Product=Tests['ProductID'] if type(Tests.get('ProductID')) is bool else None,
                        Humanise=True,Utf8=True)
            if re.match('.+InfoNeighbours',test,re.I): # get all stations in a municipality
              if not Tests.get('Region') is None:
                print(f"Collect neighbours of station/point {'@iot.id:'+str(val) if str(val).isdigit() else val} info within {Tests['Region']} meters range.")
              else:
                print(f"Collect all neighbouring station info in municipality of {'gemcode:'+str(val) if str(val).isdigit() else val}.")
              if Tests.get('ProductID'):
                print("\tstatus True: add location address, ProductID, for all sensors the status of observations.")
              if Tests.get('Period'):
                print(f"\tPeriod: '{str(Tests['Period'][0])}' upto '{str(Tests['Period'][1])}'.")
              print("This query may take quite some time per neighbour, per station ca 20 secs per sensor.")
              # Region dflt: region None: (station) municipality region, station region >=0 
              # Properties dflt: id(@iot.id),name, or e.g. id,name,gemcode,address,location
              # Select dflt: all stations or filter with reg exp e.g. '^LFT_[0-9]+',
              # Sensors dflt; all eg pm25,pm10 or reg exp  (e.g. '^pm(25|10)_kal') filter,
              # Start Period[0] dflt: None, from start installation e.g. 'one year ago'
              # End Period[1] dflt: None till today e.g. 'now' or '2024-12-01 00:30:45'
              result = SamenMetenPandasClass.get_InfoNeighbours(str(val),
                 Region=(Tests['Region'] if not Tests.get('Region') is None else None),
                 By=(Tests['Properties'] if Tests.get('Properties') else 'id,name,address'),
                 Select=(Tests['Select'] if Tests.get('Select') else None),
                 Sensors=(Tests['Sensors'] if Tests.get('Sensors') else None),
                 Start=(Tests['Period'][0] if Tests.get('Period') else None),
                 End=(Tests['Period'][1] if Tests.get('Period') else None))
              # returns dict with station names, @iot.id, location, sensor names,
              # and option details: product id, period observations, address, etc.
              print_test(test,val,result)

            # Samen Meten observations dataframe test:
            elif re.match('.+StationInfo',test,re.I): # get meta information for a station name
              print(f"Get information about station '{val}'")
              print("\twith location address, {'ProductID, ' if Tests.get('ProductID') else ''}for all sensors the status of observations.")
              if Tests.get('Region'):
                print(f"\twith neighbours within {Tests['Region']} meters range.")
              print("This query may take quite some time. E.g. 20 secs per sensor.")
              result = SamenMetenPandasClass.get_StationInfo(val, Address=True, Neighbours=Tests.get('Region'), Sensors=r'^.*$')
              if Tests['Verbosity'] > 2 or not type(result) is dict:
                  print_test(test,val,result)
              elif not type(result) is dict:
                  print_test(test,val,result)
              else:
                  print(f"'{key}' args: '{str(val)}'")
                  print(f"Created result in {val}.json.gz as dump data in gzip json format.")
                  with gzip.open(val+".json.gz", 'w') as fout:
                      fout.write(json.dumps(result).encode('utf-8'))
            elif re.match('.+StationData',test,re.I): # get sensor observations for a station name
              print(f"Period: {' upto '.join(Tests['Period'])}, Sensors: '{Tests['Sensors']}',")
              if Tests.get('Region'):
                print(f"\twith neighbours within {Tests['Region']} meters range.")
              result = SamenMetenPandasClass.get_StationData(val,
                    Address=False,Sensors=Tests['Sensors'],Neighbours=Tests.get('Region'),
                    Start=Tests['Period'][0].strip(), End=Tests['Period'][1].strip())
              if Tests['Verbosity'] > 2 or not type(result) is dict:
                  print_test(test,val,result)
              elif not type(result) is dict:
                  print_test(test,val,result)
              else:
                  print(f"'{key}' args: '{str(val)}'")
                  print(f"Created result in {val}.json.gz as dump data in gzip json format.")
                  with gzip.open(val+".json.gz", 'w') as fout:
                      fout.write(json.dumps(result).encode('utf-8'))
