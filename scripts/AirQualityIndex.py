# $Id: AirQualityIndex.py,v 1.1 2020/02/17 19:32:55 teus Exp teus $
# Copyright (C) 2015, Teus Hagen, the Netherlands
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

# the script calculates air quality pollutant measurements into different 
# air quality indices: AQI (EPA USA), LKI (Nld RIVM), AQHI (Canada) and CAQI (EU)

##bash
# get AQ[H]I index: args: [all|index|color|aqi|gom] pol1 value1 ...
#function INDEX()
#{
#   local CMD=maxAQI
#   case "$1" in
#   AQI)
#        shift
#   ;;
#   AQHI)
#        CMD=AQHI ; shift
#   ;;
#   esac
#   if [ ! -f "./AQI.py" ]
#   then
#      echo "ERROR no AQI.py script found" 1>&2
#      exit 1
#   fi
#   python -e "import './AQI.py'; $CMD ('$*');"
#}
#
#INDEX AQI PM_10 7 PM_25 6
#INDEX LKI urban aqi no2 17 o3 48 PM_25 7
#INDEX AQHI gom no2=17 o3=48 PM25=7
#INDEX CAQI traffic all NO2=17 O3=48 PM25h24 7

import re       # for manupulation with string expressions

# Air Qua.lity Index details and constants

AQI_indices = { }

# routines to calculate AQI, AQHI, LKI and other Index values
# returns an array with index value, std grade color, grade string, grade index and
# Google-o-meter URL for image png, size 200x150
# on error or unknow index value is zero

# table taken from:
# http://www.lenntech.nl/calculators/ppm/converter-parts-per-million.htm
# conversion from ug/m3 for gas 1 atm, 20 oC
# convert parts per billion to micro grams per cubic for gas
# 1 ug/m3 = ppb*12.187*M / (273.15 + oC) dflt: 1 atm, 15 oC
# 1 ppb = (273.15 + oC) /(12.187*M) ug/m3
# where M is molecular weight
K       = '273.15'
# X ug/m3 = ((273.15 + oC) / (12.187 * GMOL)) * (mbar / 1013.25) ppb
A       = '1013.25'     # mBar
T       = '15'          # dflt oC

GMOL = {
     "co":      28.011,
     "co2":     44.0095,
     "no":      30.006,
     "no2":     46.0055,
     "ozon":    47.998,
     "o3":      47.998,
     "so":      48.0644,
     "so2":     64.0638,
     "ammonium":17.03052,
     "nh3":     17.03052,
     "benzeen": 78.11184,
     "c6h6":    78.11184,
     "tolueen": 92.13842,
     "c6h5ch3": 92.13842,
}

# translate message to NL
def AQI_t(msg):
     AQImsg = {
         'unknown':   'onbekend',
         'good':      'goed',
         'moderate':  'matig',
         'beware':    'opgepast',
         'unhealthy': 'ongezond',
         'dangerous': 'gevaarlijk',
         'hazardus':  'hachelijk',
         'low risk':  'laag',
         'high risk': 'hoog',
         'very high': 'zeer hoog',
         'very low':  'zeer laag',
         'low':       'laag',
         'medium':    'risico',
         'high':      'hoog risico',
         'very high': 'zeer hoog',
         'critical':  'slecht',
         ' a.o.':     ' e.a.',
     }
     import os
     try:
         if os.getenv('LANGUAGE').index('en') >= 0: return msg
     except: pass
     if msg not in AQImsg.keys(): return msg
     return AQImsg[msg]
 
# return rounded up to a value proposinal to max val
# called with args: value and max of scale
def roundup(val,rnd):
     import math
     rnd = 2-int(math.log(rnd)/math.log(10))
     return round((10**rnd)*val+0.5*(10**(rnd-1)))/(10**rnd)

# filter pol,value pairs
def Pol_filter(strg):
    if not type(strg) is str: return ''
    strg = re.sub(r'((sub)?urban|rural[^\s]*|traffic|background)\s+',r'', strg)
    strg = re.sub(r'[\-\?]',r'0', strg)
    strg.replace('!',''); strg.replace('=',' ')
    strg.strip()
    return strg

# create an array with Index value, Index color, Index quality msg, Gom gauge URL
# args: aqi_type pollutant 
def AQI_view(type, pol='', value=0, prt=''):
     if not pol:             # just for shell command line usage
         type.strip()
         while type.find('\t') >= 0: type.replace('\t',' ')
         while type.find('  ') >= 0: type.replace('  ',' ')
         str = type.split(' ')
         while len(str) < 4: str.append('')
         (type,pol,value,prt) = str
     if (not type) or (not pol) or (value <= 0):
         if not pol: pol = ''
         if not type: type = ''
         return [
             AQI_indices['AQI']['colors'][0],
             AQI_indices['AQI']['quality'][0],
             0,
             GoogleMeter(type,0,"index|%s|"%pol + AQI_indices['AQI']['quality'][0],pol)
         ]
     type = type.upper()
     #pol =~ s/(^|\s)([onpcs][ohm1-9]+)/$1\U$2/g;
     pol = re.sub(r'(^|\s)([onpcs][ohm1-9]+)',r'\1\U\2', pol.strip())
     #pol =~ s/PM_/PM/ig; pol =~ s/_/ /g; pol =~ s/PM25/PM2.5/ig;
     pol = re.sub(r'[Pp][Mm]_?',r'PM', pol);  
     pol = re.sub(r'PM25',r'PM2.5', pol);  
     pol = re.sub(r'_',r' ', pol);  
     if value > AQI_indices[type]['max']:
         value = AQI_indices[type]['max']
     value = roundup(value, AQI_indices[type]['max']);
     if re.search(r'(all|aqi)', prt.lower()):
         print("%3.1f" % value)
     rts = []; clas = 0
     for qualifier in ['colors','quality']:  # quality always last!
         for clas in range(0,len(AQI_indices[type][qualifier + '_index'])):
             if value < AQI_indices[type][qualifier+'_index'][clas+1]:
                 break
         rts.append(AQI_indices[type][qualifier][clas])
         if re.search(r'(all|color)', prt.lower()) and (qualifier is 'colors'):
             print("0x%6.6X" % AQI_indices[type][qualifier][clas])
         if re.search(r'(all|qual)', prt.lower()) and (qualifier is 'quality'):
             print("%s" % AQI_indices[type][qualifier][clas])
     rts.append(clas)                       # clas msg index value
     if re.search(r'(all|index)',prt.lower()):
         print("%d" % rts[-1])
     title = pol
     if re.search(r'\s',pol): pol = ''       # "and other pollutants" case
     rts.append(
         GoogleMeter(type,value,
           "index|%s|" % title + AQI_indices[type]['quality'][clas].upper(),pol))
     if re.search(r'(all|gom)',prt.lower()):
         print("%s" % rts[-1])
     return rts

############################## AQI index range 0, 1 .. 500
############################## gas in ppb/ppm,
############################## pollutants O3, PM10, PM2.5, NO2, SO2, CO
############################## calculation base: dayly average measurements
# taken from: Guidelines for the Reporting of Dailyt Air Quality -
#      the Air Quality Index (AQI)
# EPA-454/B-06-001, May 2006, U.S. Environmental Protection Agency, 
# Research Triangle Park, Office of Air Quality Planning and Standards,
# North Carolina 27711
# taken from: http://www.epa.gov/airnow/aqi_tech_assistance.pdf
#
# Good                  Green   0x00e400        # RGB   0 288 0
# Moderate              Yellow  0xffff00        # RGB   255 255 0
# LightUnhealthy        Orange  0xff7e00        # RGB   255 126 0
# Unhealthy             Red     0xff0000        # RGB   255 0 0
# VeryUnhealty          Purple  0x99004c        # RGB   153 0 76
# Hazardous             Maroon  0x7e0024        # RGB   126 0 36
# 
# sensor        hours   Good    Mod     LUnh    Unh     VUnh    Haz     Haz
# o3	8h	8h/ppb	0.060	0.076	0.096	0.116	0.374	
# o3	1h	1h/ppb	0	0.125	0.165	0.205	0.405	0.505	0.600
# pm_10	24h/ugm3 55	155	255	355	425	505	605
# pm_25 standard of EPA June 14, 2012 (yr avg 15, day avg 35, max AQI 100)
# pm_25	24h/ugm3 12.1	35.5	55.5	150.5	250.5	350.5	500
# co		8h/ppm	4.5	9.5	12.5	15.5	30.5	40.5    50.4
# so2	1h/ppb	36	76	186	305	605	805	1004
# no2	1h/ppb	54	101	361	650	1250	1650 	2049

# AQI           51      101     151     201     301     401     500
# 
# Ip = (IHl - ILo)/(BPHl - BPLo)*(Cp - BPLo) + ILo
# Ip = index for pollutant p
# Cp = rounded concentration of pollutant p
# BPHl = breakpoint greater then equal to Cp (minus 0.001)
# BPLo = breakpoint less then or equal to Cp
# IHl = AQI value corresponds to BPHl (minus 1)
# ILo = AQI value corresponds to BPLo
# 
# example:
# 03 Cp = 0.08753333 -> 0.087 is between 0.085 - 0.105 -> index values 101 - 150
# (150 - 101) / (.104 - .085) * (.087 - .085) + 101 = 106
# more pollutants? take max of all any pollutant as index value 
# handle same pollutant of multiple hour measurenets as different pollutant (take max)
# more examples:
# O3 8h 0.073 ppm  = 0.0000154 ug/m3 -> 104
# PM2.5 35.9 ug/m3                   -> 102
# CO 8.4 ppm       = 0.0170184 ug/m4 -> 90

# website measurement values are in ugm3 convert it from ppm (1 ppm = 1000 ppb)
AQItable = {
    "o3h8":  [0,    60,    76,    96,   116,   374,   405,   505],
    "o3":    [0,     0,   125,   165,   205,   405,   505,   604],
    "pm_10": [0,    55,   155,   255,   355,   425,   505,   604],
    "pm_25": [0,  12.1,  35.5,  55.5, 150.5, 250.5,   350.5, 500.4],
    "co":    [0,   4.5,   9.5,  12.5,  15.5,  30.5,   40.5,   50.4],
    "so2":   [0,    36,    76,   186,   305,   605,  805,   1004],
    "no2":   [0,    54,   101,   361,   650,  1250,  1650,  2049],
}

AQIs = [0, 51, 101, 151, 201, 301, 401, ]

AQI_indices["AQI"] = {    # Air Quality Index (USA, China)
        "routine": None,
        "type": 'element',
        "pollutants": 'pm10,pm25,co,so2,no2,o3',
        "max": 500,
        "require": 1,
        "colors": [ 0x0f0f0f,
            0x00e400, 0xffff00, 0xff7e00, 0xff0000, 0x8f3f97, 0x7e0023,
            ],
        "colors_index": [0,
            1,50,100,150,200,300
            ],
        "quality": [ AQI_t('unknown'),
            AQI_t('good'),AQI_t('moderate'), AQI_t('beware'),
            AQI_t('unhealthy'),AQI_t('dangerous'), AQI_t('hazardus')],
        "quality_index": [0,
            1, 50,100,
            150,200,300
            ],
    }

# calculations and table taken from:
# http://www3.epa.gov/airnow/aqi-technical-assistance-document-dec2013.pdf
# this subroutine maps sensor values to the AQI (integers) quality space
# arguments: arg 1: sensor name, arg2: sensor value
# returns ref to array with AQI index value and quality colour
# pollutant name may have h24 (one hour or day iso h8 8 hours) added to the name
# arg1: pollutant, arg2: value (ug/m3 or ppb), optional arg3: 'ppb' for arg2 in ppb
# optional arg3 temp oC (dflt 15), optional arg4 atm (mBar) 

def AQI(pol, val='', aT='', aA='', res=''):
   global A, T
   #if ( $_[0] =~ /(traffic|urban|rural|background)/ ) { shift @_; }
   if re.search(r'(traffic|urban|rural|background)',pol.lower()):
       pol = val; val = aT; aT = aA; aA = res
   # temp argument will force ug/m3 conversion to ppb/ppm
   ppb = 0
   if aT and not re.search(r'[0-9]', aT): ppb = 1
   if not aT or not re.search(r'[0-9]', aT): aT = T
   if not aA: aA = A
   rts = 0;
   #$pol =~ s/h(1|24)$//;
   pol = re.sub(r'h(1|24)$',r'',pol)
   #$pol = 'roet' if $pol =~ /(soot|zwarte_rook)/;
   if re.search(r'(soot|zwarte.rook)', pol.lower()): pol = 'roet'
   if (not pol) or (not val) or (not pol in AQItable.keys()):
       return rts
   pollutant = AQItable[pol]
   indx = 0; val = float(val)
   # / $ugm3_pp{$pol}; # convert ug/m3 to ppm or ppb
   aT = ((273.15 + float(aT)) / 12.187) * float(aA)/float(A) # convert to Kelvin
   if (not ppb) and not re.search(r'(pm_|roet)',pol.lower()):
       val *= (aT / GMOL[pol]) # to ppb for gas
   if re.search(r'(co|nh)',pol.lower()):
       val *= 1000 # in ppm for CO, CO2 and NH3
   if re.search(r'(o3)', pol.lower()):
       val = round(val,3) # for O3 3 decimals
   elif re.search(r'(pm_25|co)', pol.lower()):
       val = round(val,1) # 1 decimal
   else: val = round(val)  # pm_10, so2, no2 no decimals
   for indx in range(0,len(pollutant)):  # get indx
       if val < pollutant[indx+1]: break
   if indx == len(AQIs)-1: indx -= 1
   if indx == len(pollutant)-1: indx -= 1
   # get the indx in the pollutant domain
   rts = float((AQIs[indx+1] - 1) - AQIs[indx]) \
           / ((pollutant[indx+1] - pollutant[indx+1]/1000.0) - pollutant[indx]) \
           * (val - pollutant[indx] ) + AQIs[indx]
   rts = int(round(rts)) # for AQI only integer values (0 .. 500)
   if rts > 500: rts = 500
   return rts;

# returns ref to array (tuple) with the max AQI vales of
# arguments with row of sensor name,sensor value pairs
# arguments example:
# arg0: [traffic|background|urban|rural] default background
# arg1: [all|aqi|color|index|qual|gom|none] default none
# argn: [ppb|nC|nmB] pol value       default 15C, 1013.25
def maxAQI( *args ):
   if not len(args): return None
   args[0].strip()
   args = re.split(r'\s+',Pol_filter(' '.join(args)))
   max_pol = 'unknown'; max_val = 0; min_val = 999; min_pol = max_pol
   atype = args.pop(0)
   if not atype: return None
   if not re.search(r'(noprint|all|aqi|color|index|qual|gom|none)', atype.lower()):
       args.insert(0,atype); atype = 'noprint'
   ppb = 0      # dflt values are in ug/m3
   aT = T       # dflt temp is 15 oC
   aA = A       # dflt is 1013.25 mBar or 1 atm
   # parse arguments for ppb/ugm3, temp, bar and (pol,value) pairs
   cnt = 0; avg = 0
   while True:
       if not len(args): break
       if re.search(r'(traffic|urban|rural|background)', args[0].lower()):
           args.pop(0); continue
       if args[0].lower().find('ppb') >= 0:
           ppb = 1; args.pop(0); continue
       if re.search(r'ug.?m3',args[0].lower()):
           ppb = 0; args.pop(0); continue
       if re.search(r'^[0-9\.]+C$', args[0]):
           aT = args.pop(0); aT.replace('C',''); continue
       if re.search(r'^[0-9\.]+mB$', args[0]):
           aA = args.pop(0); aA.replace('mB',''); continue
       pol = args.pop(0)
       if not len(args): break
       val = args.pop(0)
       if not re.search(r'^[0-9\.]+$', val): break
       pol = re.sub(r'pm(10|2\.?5)',r'pm_\1', pol.lower())
       pol = re.sub(r'pm_2.5',r'pm_25',pol)
       new = 0;
       if val < 0.0001: continue
       if not ppb: new  = AQI( pol, val, aT, aA )
       else: new = AQI( pol, val, 'ppb' )
       if new < 0.01: continue   # AQI is not defined for this pollutant
       avg = (avg*cnt + new)/(cnt+1)
       cnt += 1
       # calculate the min-max values if AQI is defined
       if new > max_val:
           max_val = new; max_pol = pol
       if new < min_val:
           min_val = new; min_pol = pol
   # default (none) return max/min (value,pollutant) pairs in array
   if atype.lower().find('none') >= 0:
       return [ max_val, max_pol, (mail_val if min_val < 999 else 0), min_pol, avg ]
   if cnt > 1 and ((min_val + 25 ) >= max_val):  # AQI's are in same range
         max_val += 25 # we SHOULD higher up one clas as cummulative effect
   rts = [max_val]
   max_pol = max_pol + AQI_t(' a.o.')
   rts += AQI_view('AQI',max_pol,max_val,atype)
   return rts;

AQI_indices["AQI"]["routine"] = maxAQI

####################################### LKI index
####################################### gas in ug/m3
####################################### pollutants: PM10, PM2.5, O3, NO2, (soot)
####################################### calculation base: hourly measurement base

AQI_indices["LKI"] = {    # Lucht Kwaliteits Index (NL)
    "routine": None, #maxLKI,
    "type": 'element',
    "pollutants": 'pm_10,pm_25,no2,o3',
    "max": 11,
    "require": 1,
    "colors": [ 0x0f0f0f,
        0x0020c5, 0x002bf7, 0x006df8, 0x009cf9, 0x2dcdfb,
        0xc4ecfd, 0xfffed0, 0xfffda4, 0xfffd7b, 0xfffc4d,
        0xf4e645, 0xffb255, 0xff9845, 0xfe7626, 0xff0a17,
        0xdc0610, 0xa21794,
        ],
    "colors_index": [ 0,
        0.05, 0.5, 1.0, 1.5, 2.0,
        2.5, 3.0, 3.6, 4.2, 4.8,
        5.4, 6.0, 6.7, 7.4, 8.0,
        9.0, 10,
        ],
    "quality": [ AQI_t('unknown'),
        AQI_t('good'),AQI_t('moderate'),
        AQI_t('unhealthy'),AQI_t('critical'),
        ],
    "quality_index": [0,
        0.05, 3,
        6, 8
        ],
}

# Lucht Kwaliteits Index LKI (from: RIVM report 2014-0050)
# all measurements values of gases are in ug/m3!
LKItable = {
    'o3':   [ 0,  15, 30,  40, 60,   80,  100,  140,  180,  200, 1000],
    'pm_10':[ 0,  10, 20,  30, 45,   60,   75,  100,  125,  150, 1000],
    'pm_25':[ 0,  10, 15,  20, 30,   40,   50,   70,   90,  100, 1000],
    'no2':  [ 0,  10, 20,  30, 45,   60,   75,  100,  125,  150, 1000],
    # roet is not yet defined
    #'roet':[0, 0.01,10,  20,  30, 40,   50,   70,   90,  100, 200],
}
# index boundaries: 0 = unknown, range 1 .. 11, 12 error, index has one decimal
LKIs =      [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

# calculations table for dutch LuchtKwaliteitsIndex range: 0 - 11
# http://www.rivm.nl/Documenten_en_publicaties/Wetenschappelijk/Rapporten/
#    2015/mei/
#    Luchtkwaliteitsindex_Aanbevelingen_voor_de_samenstelling_en_duiding
# arguments: arg 1 sensors name, arg2: sensors value in ug/m3
# accepted sensors are defined in LKI hash table

def LKI( pol, val='', aT='', aA='', res=''):
    global A, T
    ppb = 0
    if aT and not re.search(r'[0-9]', aT): ppb = 1
    if not aT or not re.search(r'[0-9]', aT): aT = T
    if not aA: aA = A
    rts = 0
    pol = re.sub(r'pm(10|2\.?5)',r'pm_\1',pol)
    pol.replace('pm_2.5','pm_25')
    pol = re.sub(r'h(1|24)$',r'',pol.lower())
    if re.search(r'(soot|zwarte.rook)', pol.lower()): pol = 'roet'
    if (not pol) or (not val) or (not pol in LKItable.keys()):
        return 0;
    pollutant = LKItable[pol]
    indx = 0; val = float(val)
    # / $ugm3_pp{$pol}; # convert ppm or ppb to ug/m3
    aT = ((273.15 + float(aT))/12.187) * float(aA)/float(A) # convert to Kelvin
    if ppb and not re.search(r'(pm_|roet)',pol.lower()):
        val *= (GMOL[pol]/float(aT)) # to ppb for gas
    if re.search(r'(co|nh)',pol.lower()) and ppb:
        val /= 1000.0 # in ppm for CO, CO2 and NH3
    if re.search(r'(o3)', pol.lower()):
       val = round(val,3) # for O3 3 decimals
    elif re.search(r'(pm_25|co)', pol.lower()):
       val = round(val,1) # 1 decimal
    else: val = round(val)  # pm_10, so2, no2 no decimals
    for indx in range(0,len(pollutant)):  # get indx
       if val < pollutant[indx+1]: break
    if indx >= len(pollutant)-2: indx -= 1
    # get the indx in the pollutant domain
    rts = float(LKIs[indx+1] - LKIs[indx]) \
           / ((pollutant[indx+1] - pollutant[indx+1]/1000.0) - pollutant[indx]) \
           * (val - pollutant[indx] ) + LKIs[indx]
    if rts > 11: rts = 11
    return rts;

# returns ref to array (tuple) with the max LKI vales of
# arguments with row of sensor name,sensor value pairs
# arguments example:
# arg0: [traffic|background|urban|rural] default background
# arg1: [all|aqi|color|index|qual|gom|none] default none
# argn: [ppb|nC|nmB] pol value       default 15C, 1013.25
def maxLKI( *args ):
    global A, T
    if not len(args): return None
    args[0].strip()
    args = re.split(r'\s+',Pol_filter(' '.join(args)))
    max_pol = 'unknown'; max_val = 0; min_val = 100; min_pol = max_pol
    atype = args.pop(0)
    if not atype: return None
    if not re.search(r'(noprint|all|aqi|color|index|qual|gom|none)', atype.lower()):
       args.insert(0,atype); atype = 'noprint'
    ppb = 0      # dflt values are in ug/m3
    aT = T       # dflt temp is 15 oC
    aA = A       # dflt is 1013.25 mBar or 1 atm
    # parse arguments for ppb/ugm3, temp, bar and (pol,value) pairs
    cnt = 0; avg = 0.0
    while True:
      if not len(args): break
      if re.search(r'(traffic|urban|rural|background)', args[0].lower()):
           args.pop(0); continue
      if args[0].lower().find('ppb') >= 0:
           ppb = 1; args.pop(0); continue
      if re.search(r'ug.?m3',args[0].lower()):
          ppb = 0; args.pop(0); continue
      if re.search(r'^[0-9\.]+C$', args[0]):
          aT = args.pop(0); aT.replace('C',''); continue
      if re.search(r'^[0-9\.]+mB$', args[0]):
          aA = args.pop(0); aA.replace('mB',''); continue
      pol = args.pop(0)
      if not len(args): break
      val = args.pop(0)
      if not re.search(r'^[0-9\.]+$', val): break
      pol = re.sub(r'pm(10|2\.?5)',r'pm_\1', pol.lower())
      pol = re.sub(r'pm_2.5',r'pm_25',pol)
      new = 0;
      if float(val) < 0.001: continue
      if ppb: new  = LKI( pol, val, aT, aA )
      else: new  = LKI( pol, val )
      if new <= 0.01: continue
      avg = (avg*cnt + new) / (cnt+1)
      cnt += 1 # we registrate amount of valid indexes found
      if new > max_val:
          max_val = new; max_pol = pol
      if new < min_val:
          min_val = new; min_pol = pol
    # if all pollutants are near max: cummulative effect
    #                            higher up one class value
    if (cnt > 1) and (round(min_val) >= round(max_val)):
      max_val += 1.0
    if re.search(r'(none)', atype.lower()): return [max_val,max_pol,min_val,min_pol,avg]
    if cnt > 1: max_pol = max_pol + AQI_t(' a.o.')
    rts = [max_val]
    rts += AQI_view( 'LKI', max_pol, round(max_val,1), atype)
    return rts

AQI_indices["LKI"]["routine"] = maxLKI    # Lucht Kwaliteits Index (NL)

############################## CAQI index range 0, 1 .. 500
############################## gas in ppb/ppm,
############################## pollutants O3, PM10, PM2.5, NO2, SO2, CO
############################## calculation base: hourly measurement base
# taken from: EU CiteAir II, Oct 2008 updated 2012,
# Common Information to European Air:
#                            the Common Air Quality Index (CAQI)
# DCMR, PO Box 843, 3100AV Schiedam, the Netherlands
#
# Very Low   Green   0x79BC6A        # RGB   121 188 106
# Low        Yellow  0xB9CE45        # RGB   185 206  69
# Medium     Yellow  0xEDC100        # RGB   237 193   0
# High       Orange  0xF69208        # RGB   246 146   8
# Very high  Red     0xF03667        # RGB   240  54 103
#
#  Pollutants and calculation grid for the revised CAQI hourly
#                    and daily grid (all changes in italics)
# Index class Gri           Traffic              City Background
#                 core pollutants pollutants   core pollutants pollutants
#                 mandated      optional       mandated         optional
#                 NO2  PM10     PM2.5       CO NO2  PM10     O3 PM2.5     CO SO2
#                      1h. 24h. 1h. 24h.            1h. 24h.    1h. 24h.
# Very Low    0     0   0    0   0    0      0   0   0    0   0  0   0     0   0
#            25    50  25   15  15   10   5000  50  25   15  60 15  10  5000  50
# Low        25    50  25   15  15   10   5000  50  26   15  60 15  10  5000  50
#            50   100  50   30  30   20   7500 100  50   30 120 30  20  7500 100
# Medium     50   100  50   30  30   20   7500 100  50   30 120 30  20  7500 100
#            75   200  90   50  55   30  10000 200  90   50 180 55  30 10000 350
# High       75   200  90   50  55   30  10000 200  90   50 180 55  30 10000 350
#           100   400 180  100 110   60  20000 400 180  100 240 110 60 20000 500
# Very High*> 100 400 180  100 110   60  20000 400 180  100 240 110 60 20000 500
# NO2, O3, SO2: hourly value / maximum hourly value in ug/m3
# CO 8 hours moving average / maximum 8 hours moving average in ug/m3
# PM10 hourly value / daily value in ug/m3
# An index value above 100 is not calculated but reported as " > 100"

AQI_indices["CAQI"] = {   # Common Air Quality Index (EU)
    "routine": None, # maxCAQI,
    "type": 'indicators',
    "pollutants": 'pm10,pm25,co,so2,no2,o3',
    "max": 125,
    "areas": ['background','rural'],
    "require": 3,
    "colors": [ 0x0f0f0f,
        0x79bc6a, 0xb9ce45, 0xedc100, 0xf69208, 0xf03667,
        ],
    "colors_index": [0,
        1, 25, 50, 75, 100
        ],
    "quality": [ AQI_t('unknown'),
        AQI_t('very low'),AQI_t('low'),AQI_t('medium'),
        AQI_t('high'),AQI_t('very high')
        ],
    "quality_index": [0,
        1, 25, 50,
        75, 100
        ],
}

# website measurement values are in ugm3 convert it from ppm (1 ppm = 1000 ppb)
CAQItable = {
   'traffic': {
       'no2': { 'level': [0, 50, 100, 200, 400, 800,],
                'mandated': 0, # mandated
              },
       'pm_10': { 'level': [0, 25, 50, 90, 180, 360,],
                  'mandated': 0, # mandated
                },
       'pm_10h24': { 'level': [0, 15, 30, 50, 100, 200,],
                     'mandated': 0, # mandated
                   },
       'pm_25': { 'level': [0, 15, 30, 55, 110, 220,],
                  'mandated': -1, # optio3al
                },
       'pm_25h24': { 'level': [0, 10, 20, 30, 60, 120,],
                     'mandated': -1, # optional
                   },
       'co': { 'level': [0, 5000, 7500, 10000, 2000, 4000,],
               'mandated': -1, # optional
             },
   },
   # background
   'background': {
       'no2': { 'level': [0, 50, 100, 200, 400, 800,],
                'mandated': 0, # mandated
              },
       'pm_10': { 'level': [0, 25, 50, 90, 180, 360,],
                  'mandated': 0, # mandated
                },
       'pm_10h24': { 'level': [0, 15, 30, 50, 100, 200,],
                     'mandated': 0, # mandated
                   },
       'o3': { 'level': [0, 60, 120, 180, 240, 480,],
               'mandated': 0, # mandated
             },
       'pm_25': { 'level': [0, 15, 30, 55, 110, 220,],
                  'mandated': -1, # optional
                },
       'pm_25h24': { 'level': [0, 10, 20, 30, 60, 120,],
                     'mandated': -1, # optional
                   },
       'co': { 'level': [0, 5000, 7500, 10000, 2000, 4000,],
               'mandated': -1, # optional
             },
       'so2': { 'level': [0, 50, 100, 350, 500, 1000,],
                'mandated': -1, # optional
              },
   },
}

CAQIclass =  [0, 25, 50, 75, 100, 125,]

# this subroutine maps sensor values to the CAQI (integers) quality space
# arguments: arg 1: sensor name, arg2: sensor value
# returns ref to array with CAQI index value and quality colour
# pollutant name may have h24 (one hour or day) added to the name
# arg1: pollutant, arg2: value (ug/m3 or ppb), optional arg3: 'ppb' for arg2 in ppb
# optional arg3 temp oC (dflt 15), optional arg4 atm (mBar)
# default is traffic table
def CAQI(pol, val='', aT='', aA='', res=''):
    global A, T
    #if ( $_[0] !~ /(traffic|background|urban|rural)/i ) { unshift @_, 'background' ; }
    env = 'background'
    if re.search(r'(traffic|background|urban|rural)', pol.lower()):
       env = pol.strip().lower(); pol = val; val = aT, aT = aA; aA = res
    if re.search(r'(urban)', env): env = 'traffic'
    if re.search(r'(traffic)', env): env = 'background'
    ppb = 0
    if aT and not re.search(r'[0-9]', aT): ppb = 1
    if not aT or not re.search(r'[0-9]', aT): aT = T
    if not aA: aA = A
    rts = 0
    pol = re.sub(r'h1$',r'', pol.lower())
    pol = re.sub(r'(soot|zwarte_rook)',r'roet',pol)
    if pol.find('pm_') < 0: pol = re.sub(r'h24$',r'', pol)
    if (not pol) or (not val) or (not pol in CAQItable[env].keys()):
        return rts
    pollutant = CAQItable[env][pol]['level']
    indx = 0; val = float(val)
    if ppb:
        # / $ugm3_pp{$pol}; # convert ppm or ppb to ug/m3
        aT = ((273.15 + float(aT)) / 12.187) * float(aA)/float(A) # convert to Kelvin
        if not re.search(r'(pm_|roet)', pol):
            val /= (GMOL[pol]/aT)
        if re.search(r'(co|nh)',pol):
            val /= 1000.0   # in ppm
    for indx in range(0,len(pollutant)):
        if val < pollutant[indx+1]: break
    if indx == len(pollutant): indx -= 1
    rts = ((CAQIclass[indx+1] - CAQIclass[indx+1]/1000.0) - CAQIclass[indx]) \
          / ((pollutant[indx+1] - pollutant[indx+1]/1000.0) - pollutant[indx]) \
          * (val - pollutant[indx] ) + CAQIclass[indx]
    rts = round(rts)
    if rts > 120: rts = 120
    return rts;

# returns ref to array (tuple) with the max CAQI vales of
# arguments with row of sensor name,sensor value pairs
# arguments example:
# arg0: [traffic|background|urban|rural] default background
# arg1: [all|aqi|color|index|qual|gom|none] default none
#       [ppb|<value>C|<value>mB] pol value       default 15C, 1013.25
def maxCAQI( *args ):
    global T, A
    if not len(args): return None
    args[0].strip()
    args = re.split(r'\s+',Pol_filter(' '.join(args)))
    max_pol = 'unknown'; max_val = 0; min_val = 999; min_pol = max_pol
    env = 'background';
    CAQIpols = {}
    atype = args.pop(0)
    if not atype: return None
    if not re.search(r'(noprint|all|aqi|color|index|qual|gom|none)', atype.lower()):
        args.insert(0,atype); atype = 'noprint'
    if re.search(r'(traffic|background|urban|rural)', args[0].lower()):
        env = args.pop(0).lower(); env = re.sub(r'(traffic|urban)',r'traffic', env) 
        if not env.find('traffic'): env = 'background'
    ppb = 0      # dflt values are in ug/m3
    aT = T       # dflt temp is 15 oC
    aA = A       # dflt is 1013.25 mBar or 1 atm
    for CAQIpol in CAQItable[env].keys():
          # 0 is mandated, -1 is optional
          CAQIpols[CAQIpol] = CAQItable[env][CAQIpol]['mandated']
    cnt = 0; avg = 0
    while True:
        if not len(args): break
        if args[0].lower().find('ppb') >= 0:
           ppb = 1; args.pop(0); continue
        if re.search(r'ug.?m3',args[0].lower()):
           ppb = 0; args.pop(0); continue
        if re.search(r'^[0-9\.]+C$', args[0]):
           aT = args.pop(0); aT.replace('C',''); continue
        if re.search(r'^[0-9\.]+mB$', args[0]):
           aA = args.pop(0); aA.replace('mB',''); continue
        pol = args.pop(0)
        if not len(args): break
        val = args.pop(0)
        if not re.search(r'^[0-9\.]+$', val): break
        pol = re.sub(r'pm(10|2\.?5)',r'pm_\1', pol.lower())
        pol = re.sub(r'pm_2.5',r'pm_25',pol)
        new = 0;
        if val < 0.0001: continue
        if not ppb: new  = CAQI( env, pol, val, aT, aA )
        else: new  = CAQI( env, pol, val, 'ppb')
        if new < 0.01: continue   # CAQI is not defined for this pollutant
        avg = (avg*cnt + new)/(cnt+1)
        cnt += 1
        if CAQIpols[pol] >= 0: CAQIpols[pol] += 1
        if (pol+'h24' in CAQIpols.keys()) and (CAQIpols[pol+'h24'] >= 0):
            CAQIpols[pol+'h24'] += 1
        if re.search(r'h24$',pol.lower()):
            h1 = re.sub(r'h24$',r'',pol.lower())
            if CAQIpols[h1] >= 0: CAQIpols[h1] += 1
        if new > max_val:
            max_val = new; max_pol = pol
        if new < min_val:
            min_val = new; min_pol = pol
    for CAQIpol in CAQIpols.keys():
        if CAQIpols[CAQIpol] == 0:
            # mandated but not in the offered set of pols
            max_val = min_val = 0; break
    if atype.lower().find('none') >= 0:
       return (max_val,max_pol,(main_val if min_val < 999 else 0),min_pol,avg)
    if (min_val + 25 ) >= max_val:   # all CAQI are in same range
        max_val += 50; # we SHOULD higher up one class as cummulative effect
    rts = [max_val]
    rts += AQI_view('CAQI', max_pol, max_val, atype )
    return rts

AQI_indices["CAQI"]["routine"] = maxCAQI # Common Air Quality Index (EU)

##########################  AQHI index range 0, 1 .. 10
########################## gas in ppb/ppm, pollutants: NO2, PM2.5, O3
########################## calculation base: daily average measurements
# calculation taken from:
# https://en.wikipedia.org/wiki/Air_Quality_Health_Index_%28Canada%29
# http://airqualityontario.com/science/aqhi_description.php for class/color defs
# website measurement values are in ug/m3,
# AQHI values are in ppb (parts per billion) for gas O3 and NO2
# (1000/10.4)*(exp(0.000537*o3)-1)*(exp(0.000871*no2)-1)*(exp(0.000487*pm25)-1)
# Taylor approximation:
# 0.084*NO2 + 0.052*O3 + 0.047*PM2.5
# see also:
# Review of AQI and AQHI index, Jan 2013, Ontario Health Care
# http://www.publichealthontario.ca/en/eRepository/Air_Quality_Indeces_Report_2013.pdf

AQI_indices["AQHI"] = {   # Air Quality Health Index (Canada)
     "routine": None, # AQHI,
     "type": 'indicators',
     "pollutants": 'pm25,no2,o3',
     "max": 11,
     "require": 3,
     "colors": [ 0xf0f0f0,
         0x00ccff, 0x0099cc, 0x006699, 0xffff00, 0xffcc00,
         0xff9933, 0xff6666, 0xff0000, 0xcc0000, 0x990000,
         0x660000
         ],
     "colors_index": [0,
         0.1,1,2,3,4,
         5,6,7,8,9,10
         ],
     "quality": [ AQI_t('unknown'),
         AQI_t('low risk'), AQI_t('moderate'),
         AQI_t('high risk'), AQI_t('very high'),
         ],
     "quality_index": [0,
         0.01, 4,
         7, 10
         ],
 }
# if argument "ppb" following arg values are in ppb
# if argument "valueC" argument is temp, if "valuemB" value is atm

# Canadian Air Quality Health Index
# (1000/10.4)*(exp(0.000537*o3)-1)*(exp(0.000871*no2)-1)*(exp(0.000487*pm25)-1)

# arguments example:
# arg0: [traffic|background|urban|rural] default background
# arg1: [all|aqi|color|index|qual|gom|none] default none
# argn: [ppb|nC|nmB] pol value       default 15C, 1013.25
def AQHI( *args ):
   if not len(args): return None
   args[0].strip()
   args = re.split(r'\s+',Pol_filter(' '.join(args)))
   atype = args.pop(0)
   if not atype: return None
   if not re.search(r'(noprint|all|aqi|color|index|qual|gom|none)', atype.lower()):
       args.insert(0,atype); atype = 'noprint'
   pol = {}
   ppb = 0    # dflt values are in ug/m3
   aT = T       # dflt temp is 15 oC
   aA = A       # dflt is 1013.25 mBar or 1 atm
   for i in range(0, len(args)): # scan args for pollutant values
         if not len(args): break
         if re.search(r'(traffic|urban|rural|background)', args[0].lower()):
           continue
         if args[i].lower().find('ppb') >= 0:
           ppb = 1; continue
         if re.search(r'ug.?m3',args[i].lower()):
           ppb = 0; continue
         if re.search(r'^[0-9\.]+C$', args[i]):
           aT = args[i]; aT.replace('C',''); continue
         if re.search(r'^[0-9\.]+mB$', args[i]):
           aA = args[i]; aA.replace('mB',''); continue
         if re.search(r'^[0-9\.]+$', args[i]):
            continue                                 # skip nameless values
         # got a pollutant now
         args[i] = re.sub(r'pm(2\.?5|10)',r'pm_\1', args[i].lower())
         args[i].replace('pm_2.5','pm_25')
         # skip if not an indicator
         if not re.search(r'(o3|no2|pm_25)', args[i]): continue
         try:
             if not re.search(r'^[0-9\.]+$',args[i+1]): continue
         except: continue
         # collect this value pair
         pol[args[i].lower()] = float(args[i+1]);
         # convert value to ppb if in ug/m3
         if not re.search(r'(pm_|roet)', args[i]) and not ppb:
             pol[args[i].lower()] = float(args[i+1]) \
                 * ((273.15 + float(aT)) / 12.187) * (float(aA)/float(A)) \
                 / GMOL[args[i]]
         # next will not happen
         if re.search(r'(co|nh)', args[i]):
             pol[args[i].lower()] *= 1000.0 # in ppm
         i += 1
   aqhi = 0
   # make sure we have all three indicator values
   from math import exp
   try:
       # aqhi = round(0.084*pol['no2']+0.052*pol['o3']+0.047*pol[pm_25']+0.5)
       if (pol['o3'] > 0) and (pol['no2'] > 0) and (pol['pm_25'] > 0):
           aqhi = (1000/10.4)* \
             ( \
               (exp(0.000537*pol['o3'])-1)+ \
               (exp(0.000871*pol['no2'])-1)+ \
               (exp(0.000487*pol['pm_25'])-1) \
             )
   except: pass
   if aqhi > 11: aqhi = 11
   # round up to 2 decimals so we can compare with AQI values
   aqhi = round(aqhi,2)
   rts = [aqhi]
   if atype.find('none') >= 0: return rts
   rts += AQI_view('AQHI', 'O3 NO2 PM2.5', aqhi, atype)
   return rts

   def maxAQHI( *args ):
        return AQHI(args)

AQI_indices["AQHI"]["routine"] = AQHI   # Air Quality Health Index (Canada)

import locale; locale.setlocale(locale.LC_TIME, 'nl_NL.UTF-8')

# return URL to get from Google image with Google meter
def GoogleMeter(Atype, value, title, pol=''):
     Atype = Atype.upper()
     if not value:
         from datetime import datetime
         from time import time
         tijd = datetime.fromtimestamp(time() - 24*60*60).strftime('%a %e %b %Y')
         return "https://chart.googleapis.com/chart?chs=175x150&chst=d_weather&chld=thought|cloudy|%s|%s|no+index" % (tijd,Atype)
     scale = AQI_indices[Atype]['max']
     try: MinMSG = AQI_indices[Atype]['quality'][1]
     except: MinMSG = ''
     try: MaxMSG = AQI_indices[Atype]['quality'][-1]
     except: MaxMSG = ''
     colors = [];
     step = AQI_indices[Atype]['colors_index'][2]; cur = 0; i = 0
     while True:
         i += 1
         try:
             max = AQI_indices[Atype]['colors_index'][i+1]
         except:
             max = AQI_indices[Atype]['max']
         # compile a color spread of colors to scale 100% for Google Maps
         while cur <= max:
             colors.append('%6.6X' % AQI_indices[Atype]['colors'][i])
             cur += step
         try:
             AQI_indices[Atype]['colors_index'][i+1]
         except: break
         if not len(colors): return ''
         pol = pol.upper()
     pol.replace('_',''); pol.replace('PM25','PM2.5')
     if pol: pol += "|"
     # chts color,size,alignment
     title.replace(' ','+')
     title.replace('PM_25','PM2.5'); title.replace('PM_10','PM10')
     if title: title = "&chtt=%s+%s&chts=003088,11,c" % (Atype, title)
     col =  ''
     if len(colors): col = '&chco=' + ','.join(colors)
     # my $label = int($value); $label = "&chl=$label";
     if value > scale: value = scale * 0.99
     perc = round(value * 100 / scale) # use 0 .. 100% scale
     if scale < 30:     # show one decimal if scale is less 30
         value = round(value,1)
         perc += 15
         perc = min(100,perc)  # index is from 1 .. 10
     else:
         value = round(value)
     return "https://chart.googleapis.com/chart?chs=175x150&cht=gom&chd=t:%s&chls=4,15,20|15&chxt=x,y&chxl=0:|%s|1:|%s++++++++++|+|++++++++++%s%s%s" % (perc,value,MinMSG,MaxMSG,col,title)
# end of AQI calculation routines

# module tests:

# print("AQI: pm_10 21.0 ug/m3 pm_25 7 ug/m3 -> ?")
# maxAQI("all pm_10 21.0 pm_25 7")
# print("AQI: O3 12 ug/m3 -> 53")
# maxAQI("all o3 12")
# # O3 8h 73 ppb -> 104
# # PM2.5 35.9 ug/m3-> 102
# # CO 8.4 ppm      -> 90
# print("PM2.5 35.9 ug/m3 -> 102 ug/m3")
# maxAQI("all pm_25 35.9")
# print("PM10 50 ug/m3 -> 46 ug/m3")  
# maxAQI("all pm_10 50")
# print("NO2 14 ug/m3 -> 6")    
# maxAQI("gom no2 14")

# # o3 31 pm_25 2 no2 2 -> 2
# # o3 21 pm_25 5 no2 14 -> 2
# print ("AQHI -> 2")
# rts = AQHI("all ppb o3 %f pm_25 %f no2 %f" % (31,2,2))
# print(rts[0])
# print ("AQHI: -> 3")
# for rts in AQHI("aqi ppb o3 %f pm_25 %f no2 %f" % (21,5,14)):
#    print(rts)

print ("LKI: PM10 18 O3 124 NO2 6 PM2.5 7 -> 6.6");
maxLKI("all PM10 18 O3 124 NO2 6 PM2.5 7");
print ("LKI -> 5.5");
maxLKI("all o3 90 pm_10 37 pm_25 25 no2 25 co2 12"); 
print ("LKI no2 17 no 9 pm_10 30 pm_25 19 roet 1 -> 4.2, matig");
maxLKI("all no2 17 no 9 pm_10 30 pm_25 19 roet 1");

print ("CAQI: urban pm10 22.00 pm2.5 17.0 -> 32");
maxCAQI("all urban no2 17 no 9 pm_10 30 pm_25 19 roet 1");

