# $Id: AirQualityIndex.pl,v 1.1 2020/02/17 19:32:55 teus Exp teus $
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
#   if [ ! -f "./AQI.pl" ]
#   then
#	echo "ERROR no AQI.pl script found" 1>&2
#	exit 1
#   fi
#   perl -e "require './AQI.pl'; $CMD ('$*');"
#}
#
#INDEX AQI PM_10 7 PM_25 6
#INDEX LKI urban aqi no2 17 o3 48 PM_25 7
#INDEX AQHI gom no2=17 o3=48 PM25=7
#INDEX CAQI traffic all NO2=17 O3=48 PM25h24 7

# Air Qua.lity Index details and constants

%AQI_indices = (
    AQI => {    # Air Quality Index (USA, China)
        routine => \&maxAQI,
        type => 'element',
        pollutants => 'pm_10,pm_25,co,so2,no2,o3',
        max => 500,
        require => 1,
        colors => [ 0x0f0f0f,
            0x00e400, 0xffff00, 0xff7e00, 0xff0000, 0x8f3f97, 0x7e0023,
            ],
        colors_index => [0,
            1,50,100,150,200,300
            ],
        quality => [ AQI_t('unknown'),
            AQI_t('good'),AQI_t('moderate'), AQI_t('beware'),
            AQI_t('unhealthy'),AQI_t('dangerous'), AQI_t('hazardus')],
        quality_index => [0,
            1, 50,100,
            150,200,300
            ],
    },
    LKI => {    # Lucht Kwaliteits Index (NL)
        routine => \&maxLKI,
        type => 'element',
        pollutants => 'pm_10,pm_25,no2,o3',
        max => 11,
        require => 1,
        colors => [ 0x0f0f0f,
            0x0020c5, 0x002bf7, 0x006df8, 0x009cf9, 0x2dcdfb,
            0xc4ecfd, 0xfffed0, 0xfffda4, 0xfffd7b, 0xfffc4d,
            0xf4e645, 0xffb255, 0xff9845, 0xfe7626, 0xff0a17,
            0xdc0610, 0xa21794,
            ],
        colors_index => [ 0,
            0.05, 0.5, 1.0, 1.5, 2.0,
            2.5, 3.0, 3.6, 4.2, 4.8,
            5.4, 6.0, 6.7, 7.4, 8.0,
            9.0, 10,
            ],
        quality => [ AQI_t('unknown'),
            AQI_t('good'),AQI_t('moderate'),
            AQI_t('unhealthy'),AQI_t('critical'),
            ],
        quality_index => [0,
            0.05, 3,
            6, 8
            ],
    },
    CAQI => {   # Common Air Quality Index (EU)
        routine => \&maxCAQI,
        type => 'indicators',
        pollutants => 'pm_10,pm_25,co,so2,no2,o3',
        max => 125,
        areas => ['background','rural'],
        require => 3,
        colors => [ 0x0f0f0f,
            0x79bc6a, 0xb9ce45, 0xedc100, 0xf69208, 0xf03667,
            ],
        colors_index => [0,
            1, 25, 50, 75, 100
            ],
        quality => [ AQI_t('unknown'),
            AQI_t('very low'),AQI_t('low'),AQI_t('medium'),
            AQI_t('high'),AQI_t('very high')
            ],
        quality_index => [0,
            1, 25, 50,
            75, 100
            ],
    },
    AQHI => {   # Air Quality Health Index (Canada)
        routine => \&AQHI,
        type => 'indicators',
        pollutants => 'pm_25,no2,o3',
        max => 11,
        require => 3,
        colors => [ 0xf0f0f0,
            0x00ccff, 0x0099cc, 0x006699, 0xffff00, 0xffcc00,
            0xff9933, 0xff6666, 0xff0000, 0xcc0000, 0x990000,
            0x660000
            ],
        colors_index => [0,
            0.1,1,2,3,4,
            5,6,7,8,9,10
            ],
        quality  => [ AQI_t('unknown'),
            AQI_t('low risk'), AQI_t('moderate'),
            AQI_t('high risk'), AQI_t('very high'),
            ],
        quality_index => [0,
            0.01, 4,
            7, 10
            ],
    },
);

# routines to calculate AQI, AQHI, LKI and other Index values
# returns an array with index value, std grade color, grade string, grade index and
# Google-o-meter URL for image png, size 200x150
# on error or unknow index value is zero
{

   # table taken from:
   # http://www.lenntech.nl/calculators/ppm/converter-parts-per-million.htm
   # conversion from ug/m3 for gas 1 atm, 20 °C
   # convert parts per billion to micro grams per cubic for gas
   # 1 μg/m3 = ppb*12.187*M / (273.15 + °C) dflt: 1 atm, 15 oC
   # 1 ppb = (273.15 + °C) /(12.187*M) μg/m3
   # where M is molecular weight
   use constant {
        K       => 273.15,
        # X ug/m3 = ((273.15 + oC) / (12.187 * GMOL)) * (mbar / 1013.25) ppb
        A       => 1013.25,        # mBar
        T       => 15,          # dflt oC
   };
   my  %GMOL = (
        co      => 28.011,
        co2     => 44.0095,
        no      => 30.006,
        no2     => 46.0055,
        ozon    => 47.998,
        o3      => 47.998,
        so      => 48.0644,
        so2     => 64.0638,
        ammonium => 17.03052,
        nh3     => 17.03052,
        benzeen => 78.11184,
        c6h6    => 78.11184,
        tolueen => 92.13842,
        c6h5ch3 => 92.13842,
   );
   sub AQI_t {
        my %AQImsg = (
            'unknown'   => 'onbekend',
            'good'      => 'goed',
            'moderate'  => 'matig',
            'beware'    => 'opgepast',
            'unhealthy' => 'ongezond',
            'dangerous' => 'gevaarlijk',
            'hazardus'  => 'hachelijk',
            'low risk'  => 'laag',
            'high risk' => 'hoog',
            'very high' => 'zeer hoog',
            'very low'  => 'zeer laag',
            'low'       => 'laag',
            'medium'    => 'risico',
            'high'      => 'hoog risico',
            'very high' => 'zeer hoog',
            'critical'  => 'slecht',
            ' a.o.'     => ' e.a.',
        );
        my $msg = shift;
        return $msg if (defined $ENV{LANGUAGE}) && ($ENV{LANGUAGE} =~ /en[_:]/);
        return $msg if not defined $AQImsg{$msg};
        return $AQImsg{$msg};
    }
    # give access to Index data definitions hash table
    sub AQI_Index {
        return \%AQI_indices;
    }

    # return rounded up to a value proposinal to max val
    # called with args: value and max of scale
    sub round{
        return undef if $#_ != 1;
        my $val = shift;
        my $rnd = 2-int(log(shift)/log(10));
        return int((10**$rnd)*$val+0.5*(10**($rnd-1)))/(10**$rnd);
    }

#   sub AQIindexing {
#       # general routine
#        my $AQIrefs = (
#            'aqi'  => \&maxAQI,
#            'aqhi' => \&AQHI,
#            'lki'  => \&maxLKI,
#            'caqi' => \&CAQI,
#        );
#        return undef if $#_ < 0;
#        my $type = lc($_[0]); my $arg = $_[0];
#        $type =~ s/^(max)?(aqi|aqhi|lki|caqi).*/$1$2/i if ( $#_ < 1 ); 
#        $type =~ s/max//;
#        if ( (not defined $AQIrefs{$type}) ) { $type = 'lki'; }
#        if ( $#_ < 1 ) { $arg =~ s/^(max)?(aqi|aqhi|lki|caqi)\s+//i;  }
#        else { shift @_; $arg = $_[0]; }
#        return $AQIrefs{$type}->( $arg ) if $AQIrefs{$type};
#        return undef;
#   }

   # filter pol,value pairs
   sub Pol_filter {
       my $strg = $_[0]; return '' if (not defined $strg) || (not $strg);
        $strg =~ s/((sub)?urban|rural[^\s]*|traffic|background)\s+//;
        $strg =~ s/[\-\?]/0/g;  $strg =~ s/\!//g; $strg =~ s/=/ /g;
        $strg =~ s/^\s+//; $strg =~ s/\s+$//;
        return $strg;
   }

   # create an array with Index value, Index color, Index quality msg, Gom gauge URL
   # args: aqi_type pollutant 
   sub AQI_view {
        my @args = @_;
        if( $#args == 0 ) {                     # just for shell command line usage
            $args[0] =~ s/^\s+//; $args[0] =~ s/^\s+$//;
            @args = split /\s+/, $args[0];
        }
        my ($type, $pol, $value, $print) = @args;
        if( ($#args != 3)
            || (not $type) || (not $pol) || ($value <= 0)
            ) {
            $pol = '' if (not defined $pol);
            $type = '' if (not defined $type);
            return (
            $AQI_indices{AQI}{colors}[0], $AQI_indices{AQI}{quality}[0], 0,
            GoogleMeter($type,0,"index|$pol|".$AQI_indices{AQI}{quality}[0],$pol)
            );
        }
        $type = uc($type);
        $pol =~ s/(^|\s)([onpcs][ohm1-9]+)/$1\U$2/g;
        $pol =~ s/PM_/PM/ig; $pol =~ s/_/ /g; $pol =~ s/PM25/PM2.5/ig;
        $value = $AQI_indices{$type}{max} if ($value > $AQI_indices{$type}{max});
        $value = round($value, $AQI_indices{$type}{max});
        printf STDOUT ("%3.1f\n",$value) if $print =~ /(all|aqi)/i;
        my @rts = (); my $class = 0;
        foreach my $qualifier ('colors','quality') { # quality always last!
            for( $class= 0; defined $AQI_indices{$type}{${qualifier}.'_index'}[$class+1]; $class++){
                last if $value < $AQI_indices{$type}{${qualifier}.'_index'}[$class+1];
            }
            push @rts, $AQI_indices{$type}{$qualifier}[$class];
            printf STDOUT ("0x%6.6X\n",$AQI_indices{$type}{$qualifier}[$class])
                if ($print =~ /(all|color)/i) && ($qualifier eq 'colors');
            printf STDOUT ("%s\n",$AQI_indices{$type}{$qualifier}[$class])
                if ($print =~ /(all|qual)/i) && ($qualifier eq 'quality');
        }
        push @rts, $class;                       # class msg index value
        printf STDOUT ("%d\n",int($rts[$#rts])) if $print =~ /(all|index)/i;
        my $title = $pol;
        if($pol =~ /\s/){ $pol = ''; }           # "and other pollutants" case
        push @rts,
            GoogleMeter($type,$value,   
              "index|$title|" . uc($AQI_indices{$type}{quality}[$class]),$pol);
        printf STDOUT ("%s\n",$rts[$#rts]) if $print =~ /(all|gom)/i;
        return @rts;
   }

   ############################## AQI index range 0, 1 .. 500
   ############################## gas in ppb/ppm,
   ############################## pollutants O3, PM10, PM2.5, NO2, SO2, CO
   ############################## calculation base: dayly average measurements
   # taken from: Guidelines for the Reporting of Dailyt Air Quality -
   #	the Air Quality Index (AQI)
   # EPA-454/B-06-001, May 2006, U.S. Environmental Protection Agency, 
   # Research Triangle Park, Office of Air Quality Planning and Standards,
   # North Carolina 27711
   # taken from: http://www.epa.gov/airnow/aqi_tech_assistance.pdf
   #
   # Good	Green	0x00e400	# RGB	0 288 0
   # Moderate	Yellow	0xffff00	# RGB	255 255 0
   # LightUnhealthy	Orange	0xff7e00	# RGB	255 126 0
   # Unhealthy	Red	0xff0000	# RGB	255 0 0
   # VeryUnhealty	Purple	0x99004c	# RGB	153 0 76
   # Hazardous	Maroon	0x7e0024	# RGB	126 0 36
   # 
   # sensor	hours	Good	Mod	LUnh	Unh	VUnh	Haz	Haz
   # o3	8h	8h/ppb	0.060	0.076	0.096	0.116	0.374	
   # o3	1h	1h/ppb	0	0.125	0.165	0.205	0.405	0.505	0.600
   # pm_10	24h/ugm3 55	155	255	355	425	505	605
   # pm_25 standard of EPA June 14, 2012 (yr avg 15, day avg 35, max AQI 100)
   # pm_25	24h/ugm3 12.1	35.5	55.5	150.5	250.5	350.5	500
   # co		8h/ppm	4.5	9.5	12.5	15.5	30.5	40.5    50.4
   # so2	1h/ppb	36	76	186	305	605	805	1004
   # no2	1h/ppb	54	101	361	650	1250	1650 	2049
   # AQI		51	101	151	201	301	401	500
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
   my %AQItable = (
	o3h8 =>	 [0,    60,    76,    96,   116,   374,   405,   505],
	o3 =>	 [0,     0,   125,   165,   205,   405,   505,   604],
	pm_10 => [0,    55,   155,   255,   355,   425,   505,   604],
	pm_25 => [0,  12.1,  35.5,  55.5, 150.5, 250.5,	350.5, 500.4],
	co =>	 [0,   4.5,   9.5,  12.5,  15.5,  30.5,  40.5,  50.4],
	so2 =>	 [0,    36,    76,   186,   305,   605,	  805,	1004],
	no2 =>	 [0,    54,   101,   361,   650,  1250,	 1650,	2049],
   );


   my @AQIs =	 (0,	51,	101,	151,	201,	301,	401, );
   # calculations and table taken from:
   # http://www3.epa.gov/airnow/aqi-technical-assistance-document-dec2013.pdf
   # this subroutine maps sensor values to the AQI (integers) quality space
   # arguments: arg 1: sensor name, arg2: sensor value
   # returns ref to array with AQI index value and quality colour
   # pollutant name may have h24 (one hour or day iso h8 8 hours) added to the name
   # arg1: pollutant, arg2: value (ug/m3 or ppb), optional arg3: 'ppb' for arg2 in ppb
   # optional arg3 temp oC (dflt 15), optional arg4 atm (mBar) 
   sub AQI {
      if ( $_[0] =~ /(traffic|urban|rural|background)/ ) { shift @_; }
      my ($pol, $val, $T, $A) = @_;
      # temp argument will force ug/m3 conversion to ppb/ppm
      my $ppb = 0; $ppb = 1 if (defined $T) && ($T !~ /[0-9]/);
      $T = T if (not defined $T) || ($T !~ /[0-9]/);
      $A = A if not defined $A;
      my $rts = 0;
      $pol =~ s/h(1|24)$//;
      $pol = 'roet' if $pol =~ /(soot|zwarte_rook)/;
      if ( (not $pol) || (not $val) || (not defined $AQItable{$pol}) ) {
        return $rts;
      }
      my @pollutant = @{$AQItable{$pol}};
      my $index = 0;
      # / $ugm3_pp{$pol}; # convert ug/m3 to ppm or ppb
      $T = ((273.15 + $T) / 12.187) * $A/A;  # convert to Kelvin
      $val *= ($T / $GMOL{$pol})
        if (not $ppb) && ($pol !~ /(pm_|roet)/); # to ppb for gas
      $val *= 1000 if $pol =~ /(co|nh)/;        # in ppm for CO, CO2 and NH3
      if( $pol =~ /(o3)/ ) { $val = int($val*1000)/1000; } # for O3 3 decimals
      elsif ( $pol =~ /(pm_25|co)/ ) { $val = int($val*10)/10; } # 1 decimal
      else { $val = int($val + 0.5); }  # pm_10, so2, no2 no decimals
      for ( $index = 0; $index < $#pollutant; $index++ ) {  # get index
	last if $val < $pollutant[$index+1];
      }
      $index-- if $index == $#AQIs;
      $index-- if $index == $#pollutant;
      # get the index in the pollutant domain
      $rts = (($AQIs[$index+1] - 1) - $AQIs[$index])
		 / (($pollutant[$index+1] - $pollutant[$index+1]/1000) - $pollutant[$index])  
		 * ($val - $pollutant[$index] )
		 + $AQIs[$index] ;
      $rts = int($rts + 0.5); # for AQI only integer values (0 .. 500)
      $rts = 500 if $rts > 500;
      return $rts;
   }

   # returns ref to array (tuple) with the max AQI vales of
   # arguments with row of sensor name,sensor value pairs
   # arguments example:
   # arg0: [traffic|background|urban|rural] default background
   # arg1: [all|aqi|color|index|qual|gom|none] default none
   # argn: [ppb|nC|nmB] pol value       default 15C, 1013.25
   sub maxAQI {
      return undef if $#_ < 0;
      my @args = @_; $args[0]  =~ s/^\s+//;
      @args = split /\s+/, Pol_filter(join(' ',@args));
      my $max_pol = 'unknown', $max_val = 0; $min_val = 999; $min_pol = $max_pol;
      my $type = shift @args;
      return undef if not defined $type;
      if ( $type !~ /(noprint|all|aqi|color|index|qual|gom|none)/i ) { unshift @args, $type; $type = 'noprint'; }
      my $ppb = 0;      # dflt values are in ug/m3
      my $T = T;        # dflt temp is 15 oC
      my $A = A;        # dflt is 1013.25 mBar or 1 atm
      # parse arguments for ppb/ugm3, temp, bar and (pol,value) pairs
      my $cnt = 0; my $avg = 0;
      while ( 1 ) {
        last if $#args < 0;
        next if $args[0] =~ /(traffic|urban|rural|background)/;
        if ( $args[0] =~ /ppb/ ) { $ppb = 1 ; shift @args ; next ; }
        if ( $args[0] =~ /ug\.?m3/ ) { $ppb = 0 ; shift @args ; next ; }
        if ( $args[0] =~ /^[0-9\.]+C$/ ) { $T = shift @args; $T =~ s/C//; next; }
        if ( $args[0] =~ /^[0-9\.]+mB$/ ) { $A = shift @args; $A =~ s/mB//; next; }
	my $pol = shift @args; last if $#args < 0;
	$val = shift @args; last if $val !~ /[0-9\.]+/;
	$pol = lc($pol); $pol =~ s/pm(10|2\.?5)/pm_$1/; $pol =~ s/pm_2.5/pm_25/;
	my $new = 0;
        next if $val < 0.0001;
        $new  = AQI( $pol, $val, $T, $A ) if not $ppb;
        $new  = AQI( $pol, $val, 'ppb' ) if $ppb;
        next if $new < 0.01;   # AQI is not defined for this pollutant
        $avg = ($avg*$cnt + $new)/($cnt+1);
        $cnt++;
        # calculate the min-max values if AQI is defined
        if( $new > $max_val ) { $max_val = $new; $max_pol = $pol; }
        if( $new < $min_val ) { $min_val = $new; $min_pol = $pol;}
      }
      # default (none) return max/min (value,pollutant) pairs in array
      return ( $max_val, $max_pol, ($min_val < 999 ? $main_val : 0), $min_pol, $avg )
        if $type =~ /none/i;
      if ( ($cnt > 1 )
          && (($min_val + 25 ) >= $max_val) ) {   # AQI's are in same range
            $max_val += 25; # we SHOULD higher up one class as cummulative effect
      }
      my @rts = ($max_val); 
      $max_pol = $max_pol . AQI_t(' a.o.');
      push @rts, AQI_view('AQI',$max_pol,$max_val,$type);
      return @rts;
   }

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
   # if argument "ppb" following arg values are in ppb
   # if argument "valueC" argument is temp, if "valuemB" value is atm

   # Canadian Air Quality Health Index
   # (1000/10.4)*(exp(0.000537*o3)-1)*(exp(0.000871*no2)-1)*(exp(0.000487*pm25)-1)

   # arguments example:
   # arg0: [traffic|background|urban|rural] default background
   # arg1: [all|aqi|color|index|qual|gom|none] default none
   # argn: [ppb|nC|nmB] pol value       default 15C, 1013.25
   sub AQHI {
      return undef if $#_ < 0;
      my @args = @_; $args[0]  =~ s/^\s+//;
      @args = split /\s+/, Pol_filter(join(' ',@args));
      my $type = shift @args;
      return undef if not defined $type;
      if ( $type !~ /(noprint|all|aqi|color|qual|index|gom|none)/i ) { unshift @args, $type; $type = 'noprint'; }
      my %pol;
      my $ppb = 0;
      my $T = T; my $A = A; # dflts for temp and atm
      for( my $i = 0; $i <= $#args; $i++ ) {
            last if $#args < 0;
            next if $args[0] =~ /(traffic|urban|rural|background)/;
            if ( $args[$i] =~ /^ppb$/ ) { $ppb = 1; next ; }
            if ( $args[0] =~ /ug\.?m3/ ) { $ppb = 0 ; shift @args ; next ; }
            if ( $args[$i] =~ /^[0-9\.]+C$/ ) {
                $T = $args[$i]; $T =~ s/C//; next ;
            }
            if ( $args[$i] =~ /^[0-9\.]+mB$/ ) {
                $A = $args[$i]; $A =~ s/mB// ; next ;
            }
	    next if $args[$i] =~ /^[0-9\.]+$/;          # skip nameless values
            $args[$i] = lc($args[$i]);                  # got a pollutant now
	    $args[$i] =~ s/pm(2\.?5|10)/pm_$1/; $args[$i] =~ s/pm_2.5/pm_25/;
	    next if $args[$i] !~ /(o3|no2|pm_25)/;      # skip if not an indicator
	    next if $args[$i+1] !~ /^[0-9\.]+$/;        # skip if not a value
	    $pol{lc($args[$i])} = $args[$i+1];          # collect this value pair
            # convert value to ppb if in ug/m3
	    $pol{lc($args[$i])} = $args[$i+1]
                * ((273.15 + $T) / 12.187) * ($A/A)
                / $GMOL{$args[$i]}
		if ($args[$i] !~ /(pm_|roet)/) && (not $ppb);
            # next will not happen
	    $pol{lc($args[$i])} *= 1000 if $args[$i] =~ /(co|nh)/; # in ppm
	    $i++;
      }
      my $aqhi = 0;
      # make sure we have all three indicator values
      if ( (defined $pol{o3}) && (defined $pol{pm_25}) && (defined $pol{no2}) ) {
	  # $aqhi = int(0.084*$pol{no2}+0.052*$pol{o3}+0.047*$pol{pm_25}+0.5)
	  $aqhi = (1000/10.4)*
		(
		  (exp(0.000537*$pol{o3})-1)+
		  (exp(0.000871*$pol{no2})-1)+
		  (exp(0.000487*$pol{pm_25})-1)
		)
	     if ($pol{o3} > 0) && ($pol{no2} > 0) && ($pol{pm_25} > 0);
	  $aqhi = 11 if $aqhi > 11;
	  # $aqhi = int($aqhi + 0.5);
          # round up to 2 decimals so we can compare with AQI values
	  $aqhi = int($aqhi*100 + 0.5)/100;
      }
      my @rts = ($aqhi);
      return @rts if $type =~ /none/i;
      push @rts, AQI_view( 'AQHI', 'O3 NO2 PM2.5', $aqhi, $type);
      return @rts;
   }
   sub maxAQHI {
        return AQHI(@_);
   }

    ####################################### LKI index
    ####################################### gas in ug/m3
    ####################################### pollutants: PM10, PM2.5, O3, NO2, (soot)
    ####################################### calculation base: hourly measurement base
    # Lucht Kwaliteits Index LKI (from: RIVM report 2014-0050)
    # all measurements values of gases are in ug/m3!
    my %LKItable = (
	o3    =>[ 0,  15, 30,  40, 60,   80,  100,  140,  180,  200, 1000],
	pm_10 =>[ 0,  10, 20,  30, 45,   60,   75,  100,  125,  150, 1000],
        pm_25 =>[ 0,  10, 15,  20, 30,   40,   50,   70,   90,  100, 1000],
	no2   =>[ 0,  10, 20,  30, 45,   60,   75,  100,  125,  150, 1000],
        # roet is not yet defined
        #roet  =>[0, 0.01,10,  20,  30, 40,   50,   70,   90,  100, 200],
    );
   # index boundaries: 0 = unknown, range 1 .. 11, 12 error, index has one decimal
   my @LKIs =    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12);

   # calculations table for dutch LuchtKwaliteitsIndex range: 0 - 11
   # http://www.rivm.nl/Documenten_en_publicaties/Wetenschappelijk/Rapporten/
   #    2015/mei/
   #    Luchtkwaliteitsindex_Aanbevelingen_voor_de_samenstelling_en_duiding
   # arguments: arg 1 sensors name, arg2: sensors value in ug/m3
   # accepted sensors are defined in LKI hash table
   # 
   sub LKI {
	my ($pol, $val, $T, $A) = @_;
        my $ppb = 0; $ppb = 1 if (defined $T) && ($T !~ /[0-9]/);
	$T = T if (not defined $T) || ($T !~ /[0-9]/);
	$A = A if not defined $A;
	my $rts = 0;
        $pol = lc($pol); $pol =~ s/pm(10|2\.?5)/pm_$1/; $pol =~ s/pm_2.5/pm_25/;
	$pol =~ s/h(1|24)$//; $pol = 'roet' if $pol =~ /(soot|zwarte_rook)/;
	if ( (not $pol) || (not $val) || (not defined $LKItable{$pol}) ) {
            return 0;
        }
	my @pollutant = @{$LKItable{$pol}};
	my $index = 0;
        # / $ugm3_pp{$pol}; # convert ppm or ppb to ug/m3
        $T = ((273.15 + $T) / 12.187) * $A/A;
	$val *= ($GMOL{$pol}/$T) if $ppb && ($pol !~ /(pm_|roet)/);
        $val /= 1000 if ($pol =~ /(co|nh)/) && $ppb;        # in ppm
        if( $pol =~ /(o3)/ ) { $val = int($val*1000)/1000; }
	elsif ( $pol =~ /(pm_25|co)/ ) { $val = int($val*10)/10; }
        else { $val = int($val); }  # pm_10, so2, no2
	for ( $index = 0; $index < $#pollutant; $index++ ) {
            last if $val < $pollutant[$index+1];
        }
        $index-- if $index >= $#pollutant -1;
	$rts = ($LKIs[$index+1] - $LKIs[$index])
                 / (($pollutant[$index+1] - $pollutant[$index+1]/1000) - $pollutant[$index])
                 * ($val - $pollutant[$index] )
                 + $LKIs[$index] ;
        return $rts;
   }

   # returns ref to array (tuple) with the max LKI vales of
   # arguments with row of sensor name,sensor value pairs
   # arguments example:
   # arg0: [traffic|background|urban|rural] default background
   # arg1: [all|aqi|color|index|qual|gom|none] default none
   # argn: [ppb|nC|nmB] pol value       default 15C, 1013.25
   sub maxLKI {
      return undef if $#_ < 0;
      my @args = @_; $args[0]  =~ s/^\s+//;
      @args = split /\s+/, Pol_filter(join(' ',@args));
      my $type = shift @args;
      if ( $type !~ /(noprint|all|aqi|color|qual|gom|index|none)/i ) {
         unshift @args, $type; $type = 'noprint';
      }
      my $max_pol = 'unknown', $max_val = 0; $min_val = 100; $min_pol = $max_pol;
      return undef if not defined $type;
      my $ppb = 0;      # dflt values are in ug/m3
      my $T = T;        # dflt temp is 15 oC
      my $A = A;        # dflt is 1013.25 mBar or 1 atm
      my $cnt = 0; $avg = 0;
      while ( 1 ) {
        last if $#args < 0;
        next if $args[0] =~ /(traffic|urban|rural|background)/;
        if ( $args[0] =~ /ppb/ ) { $ppb = 1 ; shift ; next ; }
        if ( $args[0] =~ /^[0-9\.]+C$/ ) { $T = shift @args; $T =~ s/C//; next; }
        if ( $args[0] =~ /^[0-9\.]+mB$/ ) { $A = shift @args; $A =~ s/mB//; next; }
        my $pol = shift @args; last if not defined $pol;
        my $val = shift @args; last if not defined $val;
        $pol = lc($pol); $pol =~ s/pm(10|2\.?5)/pm_$1/; $pol =~ s/pm_2\.5/pm_25/;
        my $new;
        next if $val < 0.001;
        $new  = LKI( $pol, $val, $T, $A ) if $ppb;
        $new  = LKI( $pol, $val ) if not $ppb;
        next if $new <= 0.01;
        $avg = ($avg*$cnt + $new) / ($cnt+1);
        $cnt++; # we registrate amount of valid indexes found
        if( $new > $max_val ) { $max_val = $new; $max_pol = $pol; }
        if( $new < $min_val ) { $min_val = $new; $min_pol = $pol; }
      }
      if ( ($cnt > 1) && (int($min_val+0.5) >= int($max_val)) ) {
        # all pollutants are near max: cummulative effect: higher up one class value
        $max_val += 1.0;
      }
      return ($max_val,$max_pol,$min_val,$min_pol,$avg)
        if $type =~ /none/i;
      $max_pol = $max_pol . AQI_t(' a.o.') if $cnt > 1;
      my @rts = ($max_val);
      push @rts, AQI_view( 'LKI', $max_pol, int(($max_val+0.05)*10)/10, $type);
      return @rts;
   }

   ############################## CAQI index range 0, 1 .. 500
   ############################## gas in ppb/ppm,
   ############################## pollutants O3, PM10, PM2.5, NO2, SO2, CO
   ####################################### calculation base: hourly measurement base
   # taken from: EU CiteAir II, Oct 2008 updated 2012,
   # Common Information to European Air: 
   #	the Common Air Quality Index (CAQI)
   # DCMR, PO Box 843, 3100AV Schiedam, the Netherlands
   # 
   # Very Low	Green	0x79BC6A	# RGB	121 188 106
   # Low	Yellow	0xB9CE45	# RGB	185 206  69
   # Medium	Yellow	0xEDC100	# RGB	237 193   0
   # High	Orange	0xF69208	# RGB	246 146   8
   # Very high	Red	0xF03667	# RGB	240  54 103
   # 
#  Pollutants and calculation grid for the revised CAQI hourly
#                    and daily grid (all changes in italics)
# Index class   Gri           Traffic              City Background
#                   core pollutants pollutants   core pollutants pollutants
#                   mandated      optional       mandated         optional
#                   NO2  PM10     PM2.5       CO NO2  PM10     O3 PM2.5     CO SO2
#                        1h. 24h. 1h. 24h.            1h. 24h.    1h. 24h.
# Very Low      0     0   0    0   0    0      0   0   0    0   0  0   0     0   0
#              25    50  25   15  15   10   5000  50  25   15  60 15  10  5000  50
# Low          25    50  25   15  15   10   5000  50  26   15  60 15  10  5000  50
#              50   100  50   30  30   20   7500 100  50   30 120 30  20  7500 100
# Medium       50   100  50   30  30   20   7500 100  50   30 120 30  20  7500 100
#              75   200  90   50  55   30  10000 200  90   50 180 55  30 10000 350
# High         75   200  90   50  55   30  10000 200  90   50 180 55  30 10000 350
#             100   400 180  100 110   60  20000 400 180  100 240 110 60 20000 500
# Very High*> 100   400 180  100 110   60  20000 400 180  100 240 110 60 20000 500
# NO2, O3, SO2: hourly value / maximum hourly value in μg/m3
# CO 8 hours moving average / maximum 8 hours moving average in μg/m3
# PM10 hourly value / daily value in μg/m3
# * An index value above 100 is not calculated but reported as “ > 100”

   # website measurement values are in ugm3 convert it from ppm (1 ppm = 1000 ppb)
   my %CAQItable = (
        traffic => {
            no2      => { level    => [0,   50,  100,   200,  400,  800,],
                          mandated => 0, # mandated
                        },
            pm_10    => { level    => [0,   25,   50,    90,  180,  360,],
                          mandated => 0, # mandated
                        },
            pm_10h24 => { level    => [0,   15,   30,    50,  100,  200,],
                          mandated => 0, # mandated
                        },
            pm_25    => { level    => [0,   15,   30,    55,  110,  220,],
                          mandated => -1, # optio3al
                        },
            pm_25h24 => { level    => [0,   10,   20,    30,   60,  120,],
                          mandated => -1, # optional
                        },
            co       => { level    => [0, 5000, 7500, 10000, 2000, 4000,],
                          mandated => -1, # optional
                        },
        },
        # background
        background => {
            no2      => { level    => [0,   50,  100,   200,  400,  800,],
                          mandated => 0, # mandated
                        },
            pm_10    => { level    => [0,   25,   50,    90,  180,  360,],
                          mandated => 0, # mandated
                        },
            pm_10h24 => { level    => [0,   15,   30,    50,  100,  200,],
                          mandated => 0, # mandated
                        },
            o3       => { level    => [0,   60,  120,   180,  240,  480,],
                          mandated => 0, # mandated
                        },
            pm_25    => { level    => [0,   15,   30,    55,  110,  220,],
                          mandated => -1, # optional
                        },
            pm_25h24 => { level    => [0,   10,   20,    30,   60,  120,],
                          mandated => -1, # optional
                        },
            co       => { level    => [0, 5000, 7500, 10000, 2000, 4000,],
                          mandated => -1, # optional
                        },
            so2      => { level    => [0,   50,  100,   350,  500, 1000,],
                          mandated => -1, # optional
                        },
        },
   );

   my @CAQIclass =	 (0,	25,	50,	75,	100, 125,);

   # this subroutine maps sensor values to the CAQI (integers) quality space
   # arguments: arg 1: sensor name, arg2: sensor value
   # returns ref to array with CAQI index value and quality colour
   # pollutant name may have h24 (one hour or day) added to the name
   # arg1: pollutant, arg2: value (ug/m3 or ppb), optional arg3: 'ppb' for arg2 in ppb
   # optional arg3 temp oC (dflt 15), optional arg4 atm (mBar) 
   # default is traffic table
   sub CAQI {
      if ( $_[0] !~ /(traffic|background|urban|rural)/i ) { unshift @_, 'background' ; }
      my ($env, $pol, $val, $T, $A) = @_;
      $env = lc($env);
      $env = 'traffic' if $env =~ /(urban)/;
      $env = 'background' if $env !~ /(traffic)/;
      my $ppb = 0; $ppb = 1 if (defined $T) && ($T !~ /[0-9]/);
      $T = T if (not defined $T) || ($T !~ /[0-9]/);
      $A = A if not defined $A;
      my $rts = 0;
      $pol =~ s/h1$//; $pol = 'roet' if $pol =~ /(soot|zwarte_rook)/;
      $pol =~ s/h24$// if $pol !~ /pm_/;
      if ( (not $pol) || (not $val) || (not defined $CAQItable{$env}{$pol}) ) { return $rts; }
      my @pollutant = @{$CAQItable{$env}{$pol}{level}};
      my $index = 0;
      if ( $ppb ) {
          # / $ugm3_pp{$pol}; # convert ppm or ppb to ug/m3
          my $T = ((273.15 + $T) / 12.187) * $A/A;
          $val /= ($GMOL{$pol}/$T) if $pol !~ /(pm_|roet)/; # only for gas
          $val /= 1000 if $pol =~ /(co|nh)/;        # in ppm
      }
      for ( $index = 0; $index < $#pollutant; $index++ ) {
	last if $val < $pollutant[$index+1];
      }
      $index-- if $index == $#pollutant;
      $rts = (($CAQIclass[$index+1] - $CAQIclass[$index+1]/1000) - $CAQIclass[$index])
		 / (($pollutant[$index+1] - $pollutant[$index+1]/1000) - $pollutant[$index])  
		 * ($val - $pollutant[$index] )
		 + $CAQIclass[$index] ;
      $rts = int($rts + 0.5); $rts = 120 if $rts > 120;
      return $rts;
   }

   # returns ref to array (tuple) with the max CAQI vales of
   # arguments with row of sensor name,sensor value pairs
   # arguments example:
   # arg0: [traffic|background|urban|rural] default background
   # arg1: [all|aqi|color|index|qual|gom|none] default none
   #       [ppb|<value>C|<value>mB] pol value       default 15C, 1013.25
   sub maxCAQI {
      return undef if $#_ < 0;
      my @args = @_; $args[0]  =~ s/^\s+//;
      @args = split /\s+/, Pol_filter(join(' ',@args));
      my $env = 'background';
      my $max_pol = 'unknown', $max_val = 0; $min_val = 999; $min_pol = $max_pol;
      my %CAQIpols = ();
      my $type = shift @args;
      if ( $type !~ /(all|aqi|color|index|qual|gom|none)/i ) {
        unshift @args, $type; $type = 'noprint';
      }
      if ( $args[0] =~ /(traffic|background|urban|rural)/ ) {
          $env = $1; 
          if( $env =~ /(traffic|urban)/ ) { $env = 'traffic' ; }
          else { $env = 'background' ; }
          shift @args;
      }
      my $ppb = 0;      # dflt values are in ug/m3
      my $T = T;        # dflt temp is 15 oC
      my $A = A;        # dflt is 1013.25 mBar or 1 atm
      foreach my $CAQIpol ( keys %{$CAQItable{$env}} ) {
            # 0 is mandated, -1 is optional
            $CAQIpols{$CAQIpol} = $CAQItable{$env}{$CAQIpol}{mandated};
      } 
      my $cnt = 0; my $avg = 0;
      while ( 1 ) {
        last if $#args < 0;
        if ( $args[0] =~ /ppb/ ) { $ppb = 1 ; shift ; next ; }
        if ( $args[0] =~ /^[0-9\.]+C$/ ) { $T = shift @args; $T =~ s/C//; next; }
        if ( $args[0] =~ /^[0-9\.]+mB$/ ) { $A = shift @args; $A =~ s/mB//; next; }
	my $pol = shift @args; last if not defined $pol;
	my $val = shift @args; last if not defined $val;
	$pol = lc($pol); $pol =~ s/pm(10|2\.?5)/pm_$1/; $pol =~ s/pm_2\.5/pm_25/;
	my $new = 0;
        next if ($val < 0.001) || (not defined $CAQIpols{$pol});
        $new  = CAQI( $env, $pol, $val, $T, $A ) if $ppb;
        $new  = CAQI( $env, $pol, $val, ) if not $ppb;
        next if $new < 0.01;
        $avg = ($avg*$cnt + $new)/($cnt+1); $cnt++;
        $CAQIpols{$pol}++ if ($CAQIpols{$pol}>=0) ;       # count if mandated
        $CAQIpols{$pol.'h24'}++
            if (defined $CAQIpols{$pol.'h24'}) && ($CAQIpols{$pol.'h24'}>=0);
        if ( $pol =~ /h24$/ ) {
            my $h1 = $pol; $h1 =~ s/h24$//;
            $CAQIpols{$h1}++ if ($CAQIpols{$h1}>=0);
        }
        if( $new > $max_val ) { $max_val = $new; $max_pol = $pol; }
        if( $new < $min_val ) { $min_val = $new; $min_pol = $pol; }
      }
      foreach my $CAQIpol ( keys %CAQIpols ) {
        if( $CAQIpols{$CAQIpol} == 0 ) {
            # mandated but not in the offered set of pols
            $max_val = $min_val = 0; last;
        }
      }
      return ($max_val,$max_pol,($min_val < 999 ? $main_val : 0),$min_pol,$avg)
        if $type =~ /none/i;
      if ( ($min_val + 25 ) >= $max_val ) {   # all CAQI are in same range
        $max_val += 50; # we SHOULD higher up one class as cummulative effect
      }
      my @rts = ($max_val);
      push @rts, AQI_view('CAQI', $max_pol, $max_val, $type );
      return @rts;
   }

   use POSIX qw(strftime);
   use POSIX qw(locale_h);
   setlocale(LC_TIME, 'nl_NL.UTF-8');
   # return URL to get from Google image with Google meter
   sub GoogleMeter {
	my ( $Atype, $value, $title, $pol ) = @_; $Atype = uc($Atype);
	my $tijd = strftime('%a %e %b %Y', localtime(time - 24*60*60));
	return "https://chart.googleapis.com/chart?chs=175x150&chst=d_weather&chld=thought|cloudy|$tijd|$Atype|geen+index" if not $value;
        my $scale = $AQI_indices{$Atype}{max};
        my $MinMSG = $AQI_indices{$Atype}{quality}[1];
        my $MaxMSG = $AQI_indices{$Atype}{quality}[$#{$AQI_indices{$Atype}{quality}}];
        my @colors = ();
        my $step = $AQI_indices{$Atype}{colors_index}[2]; my $cur = 0;
        for ( my $i=1; ; $i++ ) {
            my $max;
            if( defined $AQI_indices{$Atype}{colors_index}[$i+1] ) {
                $max = $AQI_indices{$Atype}{colors_index}[$i+1];
            } else { $max = $AQI_indices{$Atype}{max} ; }
            # compile a color spread of colors to scale 100% for Google Maps
            while( $cur <= $max ) {
                push @colors, sprintf('%6.6X',$AQI_indices{$Atype}{colors}[$i]);
                $cur += $step;
            }
            last if not defined $AQI_indices{$Atype}{colors_index}[$i+1];
        }
	return '' if $#{colors} < 0;
	$pol = '' if not defined $pol;
        $MinMSG = '' if not defined $MinMSG;
        $MaxMSG = '' if not defined $MaxMSG;
	$pol = uc($pol);
	$pol =~ s/_//g; $pol =~ s/PM25/PM2.5/i;
	$pol = "$pol|" if $pol;
	# chts color,size,alignment
	$title =~ s/\s/+/g; $title =~ s/PM_25/PM2.5/i; $title =~ s/PM_10/PM10/i;
	$title = "&chtt=$Atype+$title&chts=003088,11,c" if $title;
	my $col =  ''; $col = '&chco='.join(',', @colors) if $#colors >= 0;
	# my $label = int($value); $label = "&chl=$label";
	$value = $scale * 0.99 if $value > $scale;
	my $perc = int( $value * 100 / $scale + 0.5 ); # use 0 .. 100% scale
	if( $scale < 30 ) {     # show one decimal if scale is less 30
	    $value = int($value*10+0.5)/10;
	    # $value = int($value+0.5);
	    $perc += 15; $perc = 100 if $perc > 100;	# index is from 1 .. 10
	} else {
	    $value = int($value+0.5);
	}
	return "https://chart.googleapis.com/chart?chs=175x150&cht=gom&chd=t:$perc&chls=4,15,20|15&chxt=x,y&chxl=0:|$value|1:|$MinMSG++++++++++|+|++++++++++$MaxMSG$col$title";
   }
} # end of AQI calculation routines

   # module tests:

   #  print("AQI: pm_10 21.0 ug/m3 pm_25 7 ug/m3 -> ?\n");
   #  maxAQI("all pm_10 21.0 pm_25 7");
   #  print("AQI: O3 12 ug/m3 -> 53\n") ;
   #  maxAQI("all o3 12");
   # # O3 8h 73 ppb -> 104
   # # PM2.5 35.9 ug/m3-> 102
   # # CO 8.4 ppm      -> 90
   #  print("PM2.5 35.9 ug/m3 -> 102 ug/m3\n");
   #  maxAQI("all pm_25 35.9");
   #  print("PM10 50 ug/m3 -> 46 ug/m3\n");  
   #  maxAQI("all pm_10 50");
   # #  print("NO2 100 ppb -> 100\n");  
   #  # maxAQI(sprintf("all no2 %f",14 * $ugm3_pp{no2}));
   #  print("NO2 14 ug/m3 -> 6\n");    
   #  maxAQI("gom no2 14");

   # # o3 31 pm_25 2 no2 2 -> 2
   # # o3 21 pm_25 5 no2 14 -> 2
   # print ("AQHI -> 2\n");
   # @rts = AQHI(sprintf("all ppb o3 %f pm_25 %f no2 %f",31,2,2));
   # printf("%3.2f\n", $rts[0]);
   # print ("AQHI: -> 3\n");
   # @rts = AQHI(sprintf("aqi ppb o3 %f pm_25 %f no2 %f",21,5,14));
   # printf("%s\n%s\n%s\n%s\n%s\n", $rts[0],$rts[1],$rts[2],$rts[3],$rts[4]);

   # print ("LKI -> 3.5 via indexing call\n"); # does not work as expected
   # AQIindexing("index pm_10 37");

   # print ("LKI: PM10 18 O3 124 NO2 6 PM2.5 7 -> 6.6\n");
   # maxLKI("all PM10 18 O3 124 NO2 6 PM2.5 7");
   # print ("LKI -> 5.5\n");
   # maxLKI("all o3 90 pm_10 37 pm_25 25 no2 25 co2 12"); 
   # print ("LKI no2 17 no 9 pm_10 30 pm_25 19 roet 1 -> 4.2, matig\n");
   # maxLKI("all no2 17 no 9 pm_10 30 pm_25 19 roet 1");

   # print ("CAQI: urban pm10 22.00 pm2.5 17.0 -> 32\n");
   # maxCAQI("all urban no2 17 no 9 pm_10 30 pm_25 19 roet 1");

