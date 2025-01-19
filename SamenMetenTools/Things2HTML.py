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

__license__ = 'Open Source Initiative RPL-1.5'
__author__  = 'Teus Hagen'

import os, sys
__version__ = os.path.basename(__file__) + " V" + "$Revision: 1.2 $"[-5:-2]
import pandas as pd
from typing import Union,List,Tuple,Set
import math
import re
import datetime
import logging
logger = logging.getLogger(__name__)

import folium
from folium import plugins
from folium.plugins import GroupedLayerControl

HELP = f"""Generate HTML file with an Open Street Map
    Municipality or (station name or GPS) region with low-cost Things stations
    from Pandas series indexed by station name.
    Test command line: python3 {os.path.basename(__file__)} CSV-archive-file-name ....
    Command line options:  help, debug, verbosity=N,
                        title=regionName,   or name of file without .csv
                        period=YYYY-MM-DD HH:MM,YYYY-MM-DD HH:MM Dflt auto detect
    To use map in your website page use iframe: https://www.w3schools.com/tags/tag_iframe.ASP"""

# read from json file or use Samen Meten Things API neighbouring stations
# and convert to pandas dataframe
#
# stations = Things.get_InfoNeighbours(RegionName, Region=region, Select=Select, By=Expand, Start=First, End=Last)
# stations as dict: {
# 'OHN_gm-2138':
#    {'@iot.id': 8238,
#     'owner': 'Ohnics', 'project': 'GM',
#     'location': [(6.087, 51.511), 'Hoofd 4, Meer, gem. Horst, prov. Limburg'],
#     'sensors': {
#         'temp': {'@iot.id': 42891, 'symbol': 'C',
#                  'first': '2023-10-05T08:00:00.000Z', 'count': 9160,
#                  'last': '2024-10-28T11:00:00.000Z', 'product': 'DS18B20'},
#         'pm25_kal': {'@iot.id': 42890, 'symbol': 'ug/m3',
#                  'first': '2023-10-05T08:00:00.000Z', 'count': 9096,
#                  'last': '2024-10-28T11:00:00.000Z', 'product': 'Sensirion SPS030'},
#         'pm25': {'@iot.id': 42889, 'symbol': 'ug/m3',
#                  'first': '2023-10-05T08:00:00.000Z', 'count': 9160,
#                  'last': '2024-10-28T11:00:00.000Z', 'product': 'Sensirion SPS030'}
#      }},
#     ...
# }
# Pandas dataframe columns with indexes per row station (index Things ID):
#   'Things ID':str,
#      # optional indexes
#     'GPS':Tuple[float, float],  # longitude,altitude
#     'address':str, 'owner':str, 'project':str,
#     '<sensor-i> first':YYYY-MM-DDTHH:mm:ssZ, '<sensor-i> last:YYYY-MM-DDTHH:mm:ssZ,
#     '<sensor-i> count':int, '<sensor-i> product':str, ...

# read from csv file as pandas dataframe
# https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html
# CSV example:
# Things ID;longitude;latitude;address;owner;project;PM₂.₅ first;PM₂.₅ last;PM₂.₅ count;PM₁₀ first;PM₁₀ last;PM₁₀ count;temperatuur first;temperatuur last;temperatuur count;RH first;RH last;RH count;luchtdruk first;luchtdruk last;luchtdruk count;NH₃ first;NH₃ last;NH₃ count;NO₂ first;NO₂ last;NO₂ count
# LTD_80345;5.824;51.66;Mulderspad, Wanroij;Luftdaten;Luftdaten;2024/08/13;2024/08/31;153;2024/08/13;2024/08/31;153;2024/08/13;2024/08/31;153;2024/08/13;2024/08/31;153;2024/08/13;2024/08/31;153;;;;;;

# To Do: data['longitude'],data['altitude'] -> data['GPS']:Tuple[float,float]
# convert CSV to Pandas series. Evaluate column names: Things ID, GPS
# convert date/time to Pandas timestamps, GPS strings to tuples.
# timedate columns have local pandas timestamps!
def GetDataFromCSV(file_name:str) -> Tuple[pd.Series,pd.Timestamp,pd.Timestamp]:
    global Verbosity
    from pathlib import Path
    import os.path
    import datetime
    def addGPS(a:Union[str,float],b:Union[str,float]) -> Tuple[float]:      # create GPS tuple
        return (float(a),float(b))
    if not os.path.isfile(file_name) or not Path(file_name).suffix == '.csv':
        raise IOError(f"File {file_name} does not exists or is not a CSV file")
    data = pd.read_csv(file_name, sep=';', header=0, skiprows=0, skip_blank_lines=True, comment='#', )

    import ast
    if not 'GPS' in data.keys():
        if 'longitude' in data.keys() and 'altitude' in data.keys():
            data['GPS'] = data['longitude'].combine(data['altitude'],addGPS,pd.NaN)
            # data.drop(label=['longitude','altitude'])
    if 'GPS' in data.keys():
        # drop rows with no GPS
        data = data.dropna(subset=["GPS"])
        # convert string to list value for GPS location
        data['GPS'] = data['GPS'].apply(ast.literal_eval)
        # GPS data = (latitude, longitude) round 3 decimals = ca 100 meter grid
    # timestamps are converted to local timezone aware
    for idx in [ _ for _ in data.keys() if re.match(r'.*\s(last|first)$',_)]:
        try:
            data[idx] = [ pd.Timestamp(_).tz_localize(tz=datetime.datetime.now().astimezone().tzname()) for _ in data[idx] ]
        except: raise ValueError(f"Convert to pd.timestamp error in column '{idx}'")
    logger.info(f'Data from {file_name}: nr of (info) columns: {len(data.keys())}, (stations) rows: {len(data)}')
    return data

# get Period with local timestamps from Things Data pd.Series
def getPeriod(Data:pd.Series) -> Tuple[pd.Timestamp,pd.Timestamp]:
    first = last = pd.NaT
    for idx in Data.columns:
        if re.match(r'.*\s(last|first)$',idx,re.I):
            _ = Data[idx].min()
            if first is pd.NaT: first = _
            elif not _ is pd.NaT: min(first,_)
            _ = Data[idx].max()
            if last is pd.NaT: last = _
            elif not _ is pd.NaT: max(last,_)
    return first,last

# ========================================== Open Street Map generation via Folium
class GenerateThingsMap:
    """GenerateThingsMap(): generate HTML Open Street Map with regional meetstations
       Period List first,last date/time, Title:str, Verbosity:int.
       Usage: GenerateThingsMap().Data2Map(data:pandas.dataframe)."""
    def __init__(self, Period:List[str]=[None,None], Verbosity:int=0, Title:str='Regional Samen Meten Things low-cost lucht kwaliteits meetstations') -> None:
        self.Verbosity = Verbosity
        for _ in Period:
            if _ and not re.match(r'20\d\d',_):
                raise ValueError("Period should be of format YYYY[-MM-DD]...")
        # for comments on top of map
        self.First = Period[0]    # None: parse data for first and last timestamp
        self.Last = Period[1]
        self.Title = Title

    # Intro to Folium: https://python-visualization.github.io/folium/latest/getting_started.html
    # To Do: legend see https://www.geeksforgeeks.org/create-a-legend-on-a-folium-map-a-comprehensive-guide/
    # initialize the centered map, zommed, with title on top, returns the folium OSMap
    def InitMap(self, Center:List[float], Zoom:int=None, Title:str=None) -> folium.Map:
        map = folium.Map(location=Center, tiles="OpenStreetMap", zoom_start=Zoom)
    
        folium.plugins.Fullscreen(
                position="topleft",
                title="vollege scherm",
                title_cancel="verlaat volledige scherm",
                force_separate_button=True,
            ).add_to(map)
    
        # map title
        if Title: # show title
            #map.get_root().html.add_child(folium.Element(Title))  # before map
            # title on top of map
            title_html = f'<h1 style="position:absolute;z-index:100000;left:40vw" >{Title}</h1>'
            map.get_root().html.add_child(folium.Element(title_html))
    
        # show user position on this map
        # https://www.dash-leaflet.com/components/controls/locate_control
        # https://github.com/domoritz/leaflet-locatecontrol
        #locateOptions={'enableHighAccuracy': True}
        folium.plugins.LocateControl(auto_start=False, strings={'popup': 'locatie gebruiker, nauwkeurigheid: {distance} {unit}', 'title': 'lokaliseer gebruiker'}, returnToPrevBounds=True,keepCurrentZoomLevel=True,flyTo=True).add_to(map)
    
        # cluster colors kings blue: #4169e1
        folium.Element("""
            <style>
                .marker-cluster-small {
                    //background-color: rgba(100, 0, 0, 0.6) !important;
                    background-color: rgba(89, 172, 236, 0.6) !important; // border
                }
                .marker-cluster-small div {
                    //background-color: rgba(255, 0, 0, 0.6) !important;
                    background-color: rgba(89, 172, 236, 0.2) !important; // mid
                }
                .marker-cluster-medium {
                    background-color: rgba(66, 152, 219, 0.6) !important;
                }
                .marker-cluster-medium div {
                    background-color: rgba(66, 152, 219, 0.2) !important;
                }
                .marker-cluster-large {
                    background-color: rgba(0, 0, 100, 0.6) !important;
                }
                .marker-cluster-large div {
                    background-color: rgba(0, 0, 255, 0.6) !important;
                }
            </style>
            """).add_to(map._parent.header)
        return map
    
    # initialize map overlays and clustering in a dict to enable adding markers
    def InitOverlays(self, Map:folium.Map, Period:List[str]) -> dict:
        # init overlays with FeatureGroupSubGroup for markers
        overlays = {}
    
        # cluster all overlays
        # cluster all overlays
        # folium overlay args:
        # show=True layer shown on opening
        # control=True included in LayerControls
        # overlay=True add as optionallayer else base layer
        # FeatureGroupSubGroup: group argument MarkerCluster or FeatureGroup
        cluster = folium.plugins.MarkerCluster(name='stations zonder metingen',
                control=True, show=False, overlay=True,
                disableClusteringAtZoom=14)
        Map.add_child(cluster)
        _ = folium.plugins.FeatureGroupSubGroup(cluster, "stations zonder metingen")
        overlays[None] = { 'overlay': _, 'count': 0, 'cluster': cluster }
        cluster = folium.plugins.MarkerCluster(name='low-cost meetstations',
                    control=False, show=True, overlay=False,
                    disableClusteringAtZoom=14)
        Map.add_child(cluster)
        # Period:['YYYY-MM-DD hh:mm:ss','YYYY-MM-DD hh:mm:ss'] local time
        for year in range(int(Period[0][:4]),int(Period[1][:4])+1): # observations in the period First - Last
            _ = folium.plugins.FeatureGroupSubGroup(cluster, f"actief in {year}",show=(False if year < int(Period[1][:4]) else True))
            overlays[year] = { 'overlay': _, 'count': 0, 'cluster': cluster }
        # add cluster info on legendum
        self.AddMarker2Legend(description='cluster, click of zoom in', icon='cluster', prefix='fa', icon_color='white', color='rgba(89, 172, 236, 0.6)')
        return overlays
    
    # callect legends items
    LegendItems = {}
    def AddMarker2Legend(self, description:str=None, icon:str='circle', prefix:str='fa', icon_color:str='white', color:str='black') -> None:
        for _ in [('PM10','PM₁₀'),(r'PM2[\.,].*5','PM₂.₅'),('PM1','PM₁')]:
            description = re.sub(_[0],_[1],description)
        if self.LegendItems.get(description): return
        self.LegendItems[description] = {'icon':icon, 'prefix':prefix, 'icon_color': icon_color, 'color':color}
    
    # add Legend collection to the map
    def AddLegend(self, Map) -> None:
        if not self.LegendItems: return
    
        import branca
        legend = branca.element.MacroElement()
        legend_html = '''{% macro html(this, kwargs) %}'''+'''
            <div style="position: fixed;
                 bottom: 30px; left: 30px; width: 200px; height: {len(LegendItems)*30+30}px;
                 border:2px solid grey; z-index:9999; font-size:11px;
                 background-color:white; opacity: 0.85;">
                 <h5><b>Legendum markers:</h5><ul style="list-style-type:none;">
         '''
        for desc, icon in self.LegendItems.items():
            # legend_html += f'''<br><i class="fa fa-circle" style="color:{icon.get('color','white')}"></i>&nbsp;<i class="{icon.get('prefix','fa')} {icon.get('prefix','fa')}-{icon.get('icon','circle')}" style="color:{icon.get('icon_color','black')}"></i>&nbsp;{desc}</br>
            if icon.get('icon') == 'cluster':
                legend_html += f'''<li><i class="fa fa-circle" style="font-size:17px;color:{icon.get('color','red')}"></i> &nbsp;&nbsp;{desc}</li>'''
            else:
                legend_html += f'''<li><i class="fa fa-map-marker" style="font-size:15px;color:{icon.get('color','red')}"></i> &nbsp;<i class="{icon.get('prefix','fa')} {icon.get('prefix','fa')}-{icon.get('icon','circle')}" style="color:black"></i>&nbsp;{desc} metingen</li>
         '''
        legend_html += '''</ul></div>
            {% endmacro %}'''
        legend._template = branca.element.Template(legend_html)
    
        # Add the legend to the map
        Map.get_root().add_child(legend)
    
    # generate marker color from sensor type
    # returns dict with color, icon shape
    # overview of icon colors
    # {'darkblue', 'blue', 'lightred', 'green', 'darkred', 'white', 'lightgreen',
    #  'darkpurple', 'orange', 'darkgreen', 'gray', 'pink', 'purple', 'lightgray',
    #  'cadetblue', 'lightblue', 'black', 'red', 'beige'}
    # see: https://fontawesome.com/v4/icons/ use prefix='fa'
    # fa-solid fa-smoke triple cloud from https://fontawesome.com/icons/smoke?f=classic&s=solid
    # get marker attributes (marker color and icon shape/color from set of sensor types
    def GetMarkerAttr(self, Typing:Union[Set[str],List[str],str]) -> dict:
        # icon color default (white)
        rts = {'color': 'lightgray', 'icon': 'guestion', 'prefix': 'fa'}
        if not type(Typing) is str: m = ','.join(Typing)
        else: m = Typing
        if not m: return rts
        # ‘red’, ‘blue’, ‘green’, ‘purple’, ‘orange’, ‘darkred’,
        # ’lightred’, ‘beige’, ‘darkblue’, ‘darkgreen’, ‘cadetblue’,
        # ‘darkpurple’, ‘white’, ‘pink’, ‘lightblue’, ‘lightgreen’,
        # ‘gray’, ‘black’, ‘lightgray’
        # get different colors for sensor types (dust blue-ish or gas)
        if (matches := len(tuple(re.finditer(r'pm',m,re.I)))):  # dust sensor type
            rts['prefix'] = 'fa'
            if matches >= 2: rts['icon'] = 'cogs'
            else: rts['icon'] = 'cog'
            if matches >= 3:
                rts['icon'] = 'spinner'
                rts['color'] = 'cadetblue'   # PM1,PM2.5 and PM10 sensor
                rts['description'] = 'PM₁, PM₂.₅, PM₁₀'
            elif matches == 2 and re.match(r'.*pm(10|₁₀)',m,re.I):
                rts['color'] = 'cadetblue'   # PM2.5 and PM10 sensor
                rts['description'] = 'PM₂.₅, PM₁₀'
            elif matches == 2 and re.match(r'.*pm(2[\.,]{0,1}5|₂.₅)',m,re.I):
                rts['color'] = 'cadetblue'   # PM1 and PM2.5 sensor
                rts['description'] = 'PM₁, PM₂.₅'
            elif re.match(r'.*pm(1|₁)[^\d]',m,re.I):
                rts['color'] = 'lightblue'   # PM1 sensor
                rts['description'] = 'PM₁'
            elif re.match(r'.*pm(2[\.,]{0,1}5|₂.₅)',m,re.I):
                rts['color'] = 'cadetblue'   # PM2.5 sensor
                rts['description'] = 'PM₂.₅'
            elif re.match(r'.*pm(10|₁₀)',m,re.I):
                rts['color'] = 'blue'        # PM10 sensor
                rts['description'] = 'PM₁₀'
            #rts['icon']: f'{matches}'        # dust sensor
        elif re.match(r'.*(co)\d',m,re.I):  # gas sensor type
            rts['color'] = 'lightgray'
            rts['icon'] = 'cloud'
            rts['icon_color'] = 'white'
            rts['description'] = 'CO₂'
        elif re.match(r'.*(no)\d',m,re.I):  # gas sensor type
            rts['color'] = 'lightgray'
            rts['icon'] = 'cloud'
            rts['icon_color'] = 'white'
            rts['description'] = 'stikstof'
        elif re.match(r'.*(o)\d',m,re.I):  # gas sensor type
            rts['color'] = 'lightgray'
            rts['icon'] = 'cloud'
            rts['icon_color'] = 'white'
            rts['description'] = 'ozon'
        elif re.match(r'.*(nh)\d',m,re.I):  # gas sensor type
            rts['color'] = 'lightgray'
            rts['icon'] = 'cloud'
            rts['icon_color'] = 'white'
            rts['description'] = 'ammoniak'
        elif re.match(r'.*(palmes)',m,re.I): # Palmes
            rts['color'] = 'lightgray'
            rts['icon_color'] = 'white'
            rts['icon'] = 'cloud-downloud'
            rts['description'] = 'gas (Palmes)'
        elif re.match(r'.*(temperatuur|RH)',m,re.I): # temp and RH sensor only
            rts['color'] = 'lightgray'
            rts['icon_color'] = 'white'
            rts['icon'] = 'thermometer-3'
            rts['description'] = '°C en RH%'
        self.AddMarker2Legend(**rts)
        return rts
    
    # how-to: user defined icon
    # div = folium.DivIcon(html=(
    #        '<svg height="100" width="100">'
    #        '<circle cx="50" cy="50" r="40" stroke="yellow" stroke-width="3" fill="none" />'
    #        '<text x="30" y="50" fill="black">9000</text>'
    #        '</svg>'
    # ))
    # folium.Marker((0, 0), icon=div).add_to(map)
    
    # how-to: legend for markers colors
    # Define the legend's HTML
    # legend_html = '''
    # <div style="position: fixed;
    #  bottom: 50px; left: 50px; width: 200px; height: 150px;
    #  border:2px solid grey; z-index:9999; font-size:14px;
    #  background-color:white; opacity: 0.85;">
    #  &nbsp; <b>Legend</b> <br>
    #  &nbsp; Blue Circle &nbsp; <i class="fa fa-circle" style="color:blue"></i><br>
    #  &nbsp; Green Circle &nbsp; <i class="fa fa-circle" style="color:green"></i><br>
    #  &nbsp; Red Circle &nbsp; <i class="fa fa-circle" style="color:red"></i><br>
    # </div>
    # '''
    # # Add the legend to the map
    # m.get_root().html.add_child(folium.Element(legend_html))
    # how-to: custom icon style
    # url = "https://leafletjs.com/examples/custom-icons/{}".format
    # icon_image = url("leaf-red.png")
    # shadow_image = url("leaf-shadow.png")
    # icon = folium.CustomIcon(
    #      icon_image,
    #      icon_size=(38, 95),
    #      icon_anchor=(22, 94),
    #      shadow_image=shadow_image,
    #      shadow_size=(50, 64),
    #      shadow_anchor=(4, 62),
    #      popup_anchor=(-3, -76),
    #   )
    
    # add a marker to an overlay
    def AddMarker2Layer(self, Overlays:dict, Location:List[float],Year:Union[int,str],Popup:str=None,Station:str=None, Pols:dict={}) -> bool:
        if not (item := Overlays.get(Year)): return # not in period
        location = [round(_,3) for _ in Location][:2]
        if not location or len(Location) != 2 or not Station or (Year and not Pols):
            # not on the map
            if self.Verbosity > 2:
                logger.info(f"Skip marker for station '{Station}': location '{str(Location)}', overlay year '{str(Year)}'.")
            return False
        if type(Year) is str and Year.isdigit(): Year = int(Year)
        if not (overlay := Overlays.get(Year)): return # not in period
        if Year and not Pols.get('pols') and not Pols.get('types'):
            # no observations this year
            return False
    
        # get marker attributes defined by pollutants or sensor type
        if not (attrs := Pols.get('pols')): attrs = Pols.get('types',{})
        attrs = self.GetMarkerAttr(attrs)           # get marker color, icon defs
    
        if 1 < self.Verbosity < 3:
            logger.info(f"Add marker for station '{Station}': icon '{attrs.get('icon','None')}', {'circle' if not Year else ' '}marker color '{attrs.get('color','red')}', overlay year '{Year}'.")
        elif self.Verbosity >= 3:
            logger.debug(f"Add marker for station '{Station}': marker/icon '{attrs.get('icon','None')}', {'circle' if not Year else ' '}marker color '{attrs.get('color','red')}', overlay year '{Year}', tooltip '{Popup}'.")
        item['count'] += 1
        if not Year and not Pols.get('pols'):       # no data this period
            folium.CircleMarker(
                    location=list(location[0:2]),
                       stroke=False,
                       fill=True,
                       fill_opacity=0.6,
                       radius=10,
                       color="cadetblue",
                       tooltip=folium.Tooltip(Station, sticky=True),
                       popup=Popup+"<h5>Geen metingen</h5>",
                ).add_to(item['overlay'])
        else:
            text = Popup
            for _ in [('pols','Sensors'),('types','Fabrikant')]:
                if Pols.get(_[0]):
                    text += f"""<h5><i>{_[1]}</i>: {','.join(Pols[_[0]])}</h5>"""
            # # Year(None) layer gets all stations active
            # if (yearNone := Overlays.get(None)):
            #     folium.CircleMarker(
            #         location=list(location[0:2]),
            #            stroke=False,
            #            fill=True,
            #            fill_opacity=0.7,
            #            radius=10,
            #            color="cornflowerblue",
            #            tooltip=folium.Tooltip(Station, sticky=True),
            #            popup=Popup,
            #     ).add_to(yearNone['overlay'])
            #     yearNone['count'] += 1
            folium.Marker( location=list(location[0:2]),
                    tooltip=folium.Tooltip(Station, sticky=True),
                    #color='black',
                    popup=text,
                    #icon=folium.Icon(**icon),
                    icon=folium.Icon(**attrs),
                    # opacity
                ).add_to(item['overlay'])
        return True
    
    # last: add overlay controls to map
    def AddMapControls(self, Map,Overlays:dict) -> None:
        metingen = []
        for idx, year in Overlays.items():
            if not year['count']: continue
            if idx:
                metingen.append(year['overlay'])
            Map.add_child(year['overlay'])
    
        folium.LayerControl(collapsed=True).add_to(Map)
        if metingen:
            GroupedLayerControl(
                groups={'operationele stations': metingen},
                exclusive_groups=False,  # may show all selected
                collapsed=False,
            ).add_to(Map)
    
    # check is the pandas series data is compliant with Things series
    def isThingsData(self, Data:pd.Series) -> bool:
        try:
            if type(Data['Things ID']) is pd.Series and type(Data['GPS']) is pd.Series:
                return True
        except: pass
        logger.warning("Provided Pandas data series fails 'Things ID' or 'GPS' location columns.")
        return False

    # add the stations as markers with data info on OpenStreet interactive  map
    # returns a map
    # Data pd series: [str:Things,str:period],tuple:location,
    #       optional str:address,str:project,str:owner,
    #       sensors, ...:
    #       stamp:<sensor> first,stamp:<sensor> last,int:<sensor> count[,str:<sensor> type])]
    # e.g.:
    # Index(['Things ID', 'in period', 'GPS', 'address', 'project', 'owner',
    #       'PM₂.₅ first', 'PM₂.₅ last', 'PM₂.₅ count', 'PM₂.₅ type', 'PM₁₀ first',
    #       'PM₁₀ last', 'PM₁₀ count', 'PM₁₀ type', 'temperatuur first',
    #       'temperatuur last', 'temperatuur count', 'temperatuur type', 'RH first',
    #       'RH last', 'RH count', 'RH type', 'NO₂ first', 'NO₂ last', 'NO₂ count',
    #       'NO₂ type', 'NH₃ first', 'NH₃ last', 'NH₃ count', 'NH₃ type'],
    #      dtype='object')
    def Data2Map(self, Data:pd.Series) -> folium.Map:
        # https://python-graph-gallery.com/312-add-markers-on-folium-map/
        from statistics import mean
        if not self.isThingsData(Data):
            logger.warning("Info data lack Things ID stations or has no GPS locations info.")
            return False
        center = [round(mean(x[1] for x in Data['GPS']),3), round(mean(x[0] for x in Data['GPS']),3)]
    
        if not self.First or not self.Last:  # try to get timestamps from data
            strt, end = getPeriod(Data)
            if not self.First:
                self.First = None if strt is pd.NaT else strt.strftime("%Y-%m-%d")
            if not self.Last:
                self.Last = None if end is pd.NaT else end.strftime("%Y-%m-%d")
        title = f"""<h3 align="center" style="font-size:12;font-outline:solid" color="white">low-cost meetstations in de regio: <b>{self.Title}</b></h3>
                     <h4 align="center" style="font-size:10" color="white"><b>in de periode {'van '+self.First if self.First else ''} {'t/m '+self.Last if self.Last else ''}</b></h4>"""
        map = self.InitMap(center, Zoom=11, Title=title)
        sw =  [round(min(x[1] for x in Data['GPS']),3), round(min(x[0] for x in Data['GPS']),3)]
        ne =  [round(max(x[1] for x in Data['GPS']),3), round(max(x[0] for x in Data['GPS']),3)]
        map.fit_bounds([sw, ne])
        # prepair overlays for the map
        overlays = self.InitOverlays(map,[self.First,self.Last])
    
        # get set of sensor names in data
        sensors = set(); sensorTypes = set()
        for idx in Data.keys():  # column name format: <sensor name>space<date count type>
            if m := re.match(r'(.*)\s+(first|last|count)$',idx): sensors |= set([m[1]])
            if m := re.match(r'(.*)\s+(type)$',idx): sensorTypes |= set([m[1]])
    
        # for each station get location, map marker+attributes per overlay year
        # every year has own overlay with markers
        # run over all stations to identify markers per overlay (a year in operation)
        for idx, row in Data.iterrows():
            station=row['Things ID']
            start = None; end = None     # period with observations for this station
            # years: dict with pollutant (sensor) and sensor type per year for this station
            years = dict()               # years = { year: { sensors=set(), types=set() } }
            def add_year(ayear:int,asensor:str) -> None: # add sensor info in years dict
                if not years.get(ayear): years[ayear] = {'pols': set(), 'types': set()}
                if not asensor: return
                years[ayear]['pols'] |= set([asensor])
                if row[asensor + ' type'] and type(row[asensor + ' type']) is str:
                    years[ayear]['types'] |= set([re.sub(r'\s.*','',row[asensor+' type'])])
            # get marker attrs per year, start-end period seen
            for sensor in sensors:       # for each sensor get marker attributes
                first = None; last = None     # period of observations for this sensor
                if sensor+' count' in row.keys() and not math.isnan(row[sensor + ' count']):
                    # station sensor has observations
                    if sensor+' first' in row.keys() and not row[sensor+' first'] is pd.NaT:
                        first = row[sensor+' first']
                        if not start: start = first
                        elif first: start = min(start,first)
                    if sensor+' last' in row.keys() and not row[sensor+' last'] is pd.NaT:
                        last = row[sensor+' last']
                        if not end: end = last
                        elif last: end = max(end,last)
                if first is None or last is None: add_year(None,None)  # no shown
                else:                    # active sensor within main period
                    for year in range(first.year,last.year+1): add_year(year,sensor)
    
            tooltip_text = f"""
                <h4 align="left" style="font-size:9"><b>Station </b>{station}</h4>"""
            # [('lokatie','address'),('projekt','project'),('eigenaar','owner')]:
            for _ in [('Projekt','project'),('Eigenaar','owner')]:
                if _[1] in row.keys() and type(row[_[1]]) is str and row[_[1]]:
                    tooltip_text += f"""<h5 style="font-size:8"<i>{_[0]}</i>: {row[_[1]]}</h5>"""
            if not start or not end:  # not active in period
                tooltip_text += f"""<br><i>Geen metingen</i></br>"""
            else:                     # add active period to marker popup text
              if start:
                tooltip_text += f"""<br>Eerste meting: {start.strftime("%Y-%m-%d")}</br>"""
              if end:
                tooltip_text += f"""<br>Laatste meting: {end.strftime("%Y-%m-%d")}</br>"""
            for year in overlays.keys():
                # show marker if seen in this year and add popup info: pollutant and sensor branch
                self.AddMarker2Layer(overlays, [row['GPS'][1],row['GPS'][0]], year, Pols=years.get(year,{}),
                                Popup=tooltip_text, Station=station)
    
        self.AddLegend(map)                # add marker legend
        self.AddMapControls(map, overlays) # add layer controls
        return map
    
# ================================================================================
################## command line tests of (class) subroutines or command line checks
# command line options:  help, debug, verbosity=N,
#                        title=regionName,   or name of file without .csv
#                        period=YYYY-MM-DD HH:MM,YYYY-MM-DD HH:MM or auto detect
if __name__ == '__main__':
    Verbosity = 0
    DEBUG = False
    Period = [None,None]; Title = None
    if not len(sys.argv[1:]) and HELP: sys.stderr.write(HELP+'\n')
    for arg in sys.argv[1:]:
        if re.match(r'(-+)*h(elp)*',arg,re.I):              # print help info
            sys.stderr.write(HELP+'\n')
            exit(0)
        elif re.match(r'(-+)*d(ebug)*',arg,re.I):             # use debug .csv file
            DEBUG = True; arg = 'Land van Cuijk.csv'
        elif re.match(r'(-+)*v(erbos)*',arg,re.I):            # verbosity level
            if (m := re.match(r'Verbosity=(\d)$',arg,re.I)):
                Verbosity = int(m[0])
            else: Verbosity += 1
            continue
        elif (m := re.match(r'Title=(.*)',arg,re.I)):          # title of map page
            Title = m[0]
            continue
        elif (m := re.match(r'Period=(20\d\d-\d\d-\d\d.*),\s*(20\d\d-\d\d-\d\d.*)',arg,re.I)):
            Period = [m[0],m[1]]
            continue
        if not re.match(r'.*\.csv',arg,re.I):                 # should be csv file
            sys.stderr.write(f"File {arg} is not an CSV file. Skipped\n")
            continue

        if Title is None: Title = re.sub(r'.csv','',os.path.basename(arg),re.I)
        if Verbosity >= 3:
            logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
        elif Verbosity:
            logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
        logger = logging.getLogger(__name__)

        logger.info(f"Generate OS map from {arg}, period {str(Period)}, title {Title}")
        Map = None
        Data = GetDataFromCSV(arg)  # convert csv file to panda series
        logger.info(f'Collected info for {len(Data)} stations')
        Map = GenerateThingsMap(Verbosity=Verbosity,Title=Title,Period=Period).Data2Map(Data)
        if Map:
            arg = arg.replace('.csv','')+'.html'
            Map.save(arg)
            sys.stderr.write(f"Generated map htmp file: '{arg}'\n")
        
