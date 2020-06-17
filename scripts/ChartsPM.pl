#!/usr/bin/perl -w
# Copyright (C) 2016, Teus Hagen, the Netherlands
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
# If yuo have improvements please do not hesitate to email the author.

# $Id: ChartsPM.pl,v 2.6 2020/06/17 10:09:46 teus Exp teus $
# use 5.010;
my $Version = '$Revision: 2.6 $, $Date: 2020/06/17 10:09:46 $.';
$Version =~ s/\$//g;
$Version =~ s/\s+,\s+Date://; $Version =~ s/Revision: (.*)\s[0-9]+:[0-9]+:[0-9]+\s\.*\s*/$1/;
# Description:
# script will generate JS script Highchart graphs from pollutant data.
# The data is collected from the measurement stations and sensors tables
# in the database.
# DEPENDS on: yui-compressor java script to compress javascript parts
# TO DO:
#       allow the user to select different the levels for EU/WHO/LKI/AQI/AQI_LKI etc.
use List::MoreUtils qw(uniq);
use feature "state"; # some output is done only once
use constant {
                                        # Default DB credentials
        USER => 'someuser', PASSWD => 'somepass', HOST => 'localhost',
        DB        => 'luchtmetingen',   # default database

        TITLE     => 'Samen Meten aan Luchtkwaliteit', # chart
        SUBTITLE  => '',        # chart

        # following defaults can be altered on the command line with an option choice
        LOCATION  => 'VW2017_93d73279dc',    # default location nr, sensor label
        REGION    => 'Horst aan de Maas',    # default region
        SN        => '93d73279dc',      # default serial table of hourly measurements
        ID        => 'BdP',             # javascript prefix for vars
        COORDINATES => '51.42083,6.13541', # default location coordinates
        PROJECT   => 'VW2017',          # default project id
        SENSORS   => 'Sensors',         # name of sensors desciption table
        REF       => 'HadM',            # most recent measurement station PLIM
        POLLUTANTS => 'pm25|pm10',      # dflt choices of pollutants to show in graph
        BUTTONS   =>  'BdP',            # dflt button name

        AQI       => 'EU',              # plotbands accoringly to EU/WHO,LKI,AQI
        MINHOURS  => 12,                # minimal nr hours to show a graph
        MINGRAPHS => 2,                 # minimal nr of graphs requirement
        PERIOD    => 60*60*24*7*3,      # total of period on chart 3 weeks
        WDIR      => '/webdata/luchtmetingen/',   # working directory
                                        # the website dir for chart page
        WEBDIR    => '/webdata/Drupal/cmsdata/BdP/files/luchtmetingen/',
        WWWGRP    => 'www-data',        # if output file name has full path name

        FALSE     => 0,
        TRUE      => 1,
        LANGUAGE  => 'NL',              # default output language
};

use JSON;
use Time::Piece;
use POSIX qw(strftime);
use Date::Parse;
use feature "state";
use Env qw(HOME DBUSER DBPASS DBHOST);  # for working from HOME dir, and DB credits
use feature "state";            # some routines keep own state variables
use POSIX qw(strftime);
use Time::Piece;                # need to parse time strings
use autodie;
use 5.010;
use LWP::UserAgent;             # for direct http access
use URI::Escape;
use Getopt::Mixed;              # need to parse command line arguments

my $debug = 0;   # on debug output full HTML page to output
my $verbose = 1; # verbosity level
my $myhost   = HOST;    # mysql server
$myhost      = $DBHOST if defined $DBHOST;
my $mydb     = DB;      # mysql database name
$mydb        = $DB if defined $DB;
my $myuser   = USER;    # mysql user
$myuser      = $DBUSER if defined $DBUSER;
my $mypass   = PASSWD;  # mysql password
if( $mypass =~ /somepass/ ){
    $mypass = '';
    $mypass = $DBPASS if defined $DBPASS;
}

use DBI;
my $mysql;

END {                   # on exit close connections
    if( $mysql and $mysql != 1 ){ $mysql->disconnect(); $mysql = 0; }
}

# make sure we work in a well known dir
my $WDir = WDIR;
if( -d $WDir ){
   chdir( $WDir) ;
} else {
   print STDERR "Warning: Cannot chdir to working dir $WDir.\n";
   print STDERR "Working dir (current): .\n";
   $WDir = './';
}

Getopt::Mixed::init(
        '? help>? '.
        'd:i debug>d '.
        'v verbose>v '.
        'q quiet>q '.
        'p=s pass>p '.
        'u=s user>u '.
        'h=s host>h '.
        'D=s database>D '.
        'l=s location>l '.
        'i=s serial>i '.
        'j java>j  '.
        'P=s project>P '.
        'H=s alias>H '.
        'm=s meteo>m '.
        'e=s pollutants>e '.
        'E export>E '.
        'g=i graphs>g '.
        'O=s output>O ',
        'a:i aggregation>a '.
        'c correct>c '.
        't=s title>t '.
        's=s subtitle>s '.
        'r=s region>r '.
        'R=s reference>R '.
        'L=s last>L '.
        'S=s first>S ',
        'f first>f ',
        'A=s aqi>A '.
        'b=s buttons>b '.
        'AQI>A '.
        'B bands>B '.
        'M mean>M '.
        'index>A '.
        'w=s web>w '.
        'W=s wd>W '.
        'x=i timeshift>x '.
        'X=s timematch>X '.
        'Z=s avoid>Z '.
        'T=s language>T lang>T '.
        ''
);

my $label       = LOCATION;
my $identifier  = SN;
my $coordinates = COORDINATES;
my $project     = PROJECT;
my $title       = TITLE;
my $subtitle    = SUBTITLE;
my $mingraphs   = MINGRAPHS;
my $myRegion    = '';   # overwrite region definition
my $region      = '';
my $AQI         = AQI;
my $webdir      = WEBDIR;
my $wwwgrp      = WWWGRP;
my $meteo       = '';       # table to use for meteo data
my $HTMLalias       = '';   # prepend href alias (table name) with this string
# example: pm25|pm10,temp|rv for two buttons and selection of pollutants
my $pollutants  = POLLUTANTS; # comma separated pol select per button
                        # example: stof,weer
my $buttons     = BUTTONS;      # comma separated button names to switch tables
my $output      = '/dev/stdout';
my $aggregation = 30;   # minimal aggregration in minutes (use avg in this period)
my $correctPM   = FALSE; # correct PM value with RIVM Joost value
                        # may ruin the AQI/LKI values arithmetic!
                        # needed for optional pm corrections 
my %RVstations  = ();   # dict of stations table names with humidity values
                        # will have "default" key with default values of LML station
my $timeshift   = 6*30*60; # timeshift of dates for tables with timematch eg NL10131
my $timematch   = '(NL10131|HadM)'; # table pattern to apply timeshift
my $reference   = REF;
my $last_time   = '';   # last date/time used for end date/time graphs
my $first_time  = '';   # first time if defined calculation of period of chart
my $use_first   = FALSE;# use the first time seen in Sensors to calc period
                        # next do not seem to work properly, why?
my $exportChart = FALSE;# enable/disable button to export Chart Graph
                        # > 1 will say: print button (no download)
my $ShowBands   = FALSE;# show AQI or LKI bands in the chart for LML stations
my $language    = LANGUAGE; # default output language either NL or UK
my $poltype     = 'stof';# type of pollutants, e.g. fijnstof
my $barb        = FALSE;# load barb JS from highcharts (wind speed/direction)
my $java        = FALSE;# add HighChart javascript URL iso in <head> part
my $leftAxis    = 0;    # number of left axis for legend spacing
my $Mean        = FALSE;# do not show individual graphs on bigger overviews
my $AvgAvoid    = 'xyz'; # do not use data of pattern table names in regio average calculation

while( my($option, $value, $arg) = Getopt::Mixed::nextOption() ){
  OPTION: {
    $option eq 'd' and do { $verbose++; $debug++;  last OPTION; };
    $option eq 'v' and do { $verbose++;  last OPTION; };
    $option eq 'a' and do { $aggregation = 60;
            $aggregation = $value if defined $value;
            $aggregation = 6 if ($aggregation < 6);
            $aggregation = 60 if ($aggregation >= 60);
            last OPTION;
        };
    $option eq 'q' and do { $verbose = 0;  last OPTION; };
    $option eq 'h' and do { $myhost = $value; $myhost =~ s/\s//g; last OPTION; };
    $option eq 'D' and do { $mydb = $value; $mydb =~ s/\s//g; last OPTION; };
    $option eq 'E' and do { $exportChart++; last OPTION; };
    $option eq 'B' and do { $ShowBands = TRUE; last OPTION; };
    $option eq 'c' and do {
            # $correctPM = TRUE; disabled: js errors
            last OPTION;
            };
    $option eq 'm' and do { $meteo = $value; last OPTION; };
    $option eq 'M' and do { $Mean = TRUE; last OPTION; };
    $option eq 'e' and do {
            $value = lc($value); $pollutants = $value;
            $value =~ s/\|/,/g;
            # TO DO: add PMxy_cnt
            $value =~ s/^/,/; $value =~ s/[,\|](pm(10?|25)?|temp|rv|luchtdruk|wind|(prev|day)?rain|([A-O][0-3]?)+|rssi)//g;
            if( $value ) {
                print STDERR "Unknown pollutant in pollutant choice: $pollutants.\n";
                $pollutants = POLLUTANTS;
            }
            if( $pollutants !~ /pm/ ) { $poltype = ''; }
            if( $pollutants =~ /(temp|luchtdruk|wind|(day|prev)?rain)/ ) {
                if( $language =~ /UK/ ) {
                    $poltype .= ", meteo";
                } else {
                    $poltype .= ", klimaat";
                }
                $poltype =~ s/^, //;
            }
            if( $pollutants =~ /([A-O][0-3]?)+/ ) {
                if( $language =~ /UK/ ) {
                    $poltype .= ", gasses";
                } else {
                    $poltype .= ", gassen";
                }
                $poltype =~ s/^, //;
            }
            if( $language =~ /UK/ ) {
                $poltype =~ s/(.*),/$1 and/;
            } else {
                $poltype =~ s/(.*),/$1 en/;
            }
            $poltype =~ s/[\(\)]//g;
            $pollutants =~ s/\s//g; # something alike pm10|pm25,rv|temp 2 charts
            last OPTION;
        };
    $option eq 'u' and do { $myuser = $value; $myuser =~ s/\s//g; last OPTION; };
    $option eq 'p' and do { $mypass = $value; last OPTION; };
    $option eq 'P' and do { $project = $value; last OPTION; };
    $option eq 'H' and do { $HTMLalias = $value; last OPTION; };
    $option eq 'g' and do { $mingraphs = $value; last OPTION; };
    $option eq 'b' and do {  # names of the buttons for pollutants in the charts
            $buttons = $value;
            $buttons =~ s/\s*([\|,])\s*/$1/g;
            $buttons = ID if length($buttons) < 1;
            $buttons =~ s/pm/PM/g; $buttons =~ s/PM2.5/PM25/g;
            last OPTION;
        };
    $option eq 'l' and do { $label = $value; $label =~ s/\s//g; last OPTION; };
    $option eq 'L' and do { 
            if( $value =~ /^now/ ) {
                $last_time = int(time());
            } else {
                $last_time = str2time($value);
                if( not $last_time ) {
                    print STDERR "last time: Unable to parse date/time from $value\n";
                    exit(1);
                }
            };
        };
    $option eq 'S' and do {
            $first_time = str2time($value);
            if( not $first_time ) {
                print STDERR "first time: Unable to parse date/time from $value\n";
                    exit(1);
                }
        };
    $option eq 'f' and do {
            $use_first = TRUE;
        };
    $option eq 't' and do { $title = $value; last OPTION; };
    $option eq 's' and do { $subtitle = $value; last OPTION; };
    $option eq 'R' and do { $reference = $value; last OPTION; };
    $option eq 'r' and do { $myRegion = $value; last OPTION; };
    $option eq 'i' and do {
            $identifier = $value; $identifier =~ s/\s//g;
            last OPTION;
        };
    $option eq 'j' and do { $java = TRUE; last OPTION; };
    $option eq 'W' and do { $WDir = $value; chdir(WDir); last OPTION; };
    $option eq 'w' and do { $webdir = $value; last OPTION; };
    $option eq 'O' and do { $output = $value; last OPTION; };
    $option eq 'A' and do { $AQI = $value; last OPTION; };
    $option eq 'T' and do { if( $value =~ /^(NL|dutch)/i ) {
                                $language = 'NL';
                            } elsif( $value =~ /^(UK|english|EN)/ ) {
                                $language = 'UK';
                            } else {
                                fprintf STDERR ("Unknown language %s\n", $value);
                            }
                        };
    $option eq 'x' and do { $timeshift = $value*60; last OPTION; };
    $option eq 'X' and do { $timematch = $value; last OPTION; };
    $option eq 'Z' and do { $AvgAvoid = $value; last OPTION; };
    $option eq '?' and do {
        my $ref = REF;
        print STDERR <<EOF ;
        $0 [options] [arg...] (default/no arguments: catch up to latest sensor data
            for the default location/identifier $identifier)
        $0 argument uses a name (MySQL table id): e.g. ${project}_${identifier}.
        Second argument is the reference measurement station, e.g. ${ref}.
        Tooltip synchronisation: The start time of the graphs are shifted to the
        minute in the hour the first graph was started. Usually the low budget
        sensor graph.
        First try:
        $0 -d -v -O ./file_name ${project}_${identifier} $ref as first test.
        The -d for debug mode, -v be more versatile,
        ${project}_${identifier}, station $ref DB table names should be
        present in database $mydb.
        By default the graphs of PM2.5 (ie also the cheaper PM sensor) is made visible.
        The others can be switched on.

        Options:
 -O|--output    The output file with HTML/JS code. Default: $output
                If the output filename has no slash the file will be stored
                in the website directory (default: $webdir).
 -l|--location  The measurement location to use, default ($identifier) location $label
 -t|--title     The title in the chart, default '$title'.
 -s|--subtitle  The subtitle in the chart, default '$subtitle'.
 -r|--region    The region of measurements, default '$myRegion'.
 -R|--reference The MySQL table with measurements to reference to in the chart, default '$reference'.
                Empty will disable refence to national measurement station use.
 -i|--serial    The measurement serial nr to use, default $identifier
                The database table is defined by {project_ID}_identifier (${project}_$identifier)
 -j|--java      Add HighChart javascript URL iso via <head> part. Dflt OFF.
                When wind barb (wind direction/speed) is discovered ON.
 -d|--debug     Debugging on.
 -Q|--help      This help or usage message.
 -v|--verbose   Increase verbosity, default: off.
 -q|--quiet     Be as quiet as possible, turns verbose off, default: off.

 -D|--database  The Database name to use (default: $mydb). Or env variable DB.
 -h|--host      The DB host for DB access (default: $myhost). Or env var. DBHOST.
 -u|--user      The DB user for DB access (default: $myuser). Or env. var. DBUSER.
 -p|--pass      The DB user password for DB access (default: X?x?X). Or env. var. DBPASS.

 -P|--project   The project name (default: VW2017). Is used as component in data DBtable name.
 -g|--graphs    The minimal amount of graphs in the chart (default: $mingraphs).
 -m|--meteo     The DB table to be used for meteo measurements.
                Dflt same DB table as pollutant table.
 -e|--pollutants The pollutants choice for the graphs shown (default: $pollutants)
                The pollutant identifier is the DB table column name: eg pm, o3, temp
                Per button a comma separated name can be given e.g.
                    pm25|pm10,rv|temp for button name e.g. dust,weather
                    or pm25,pm10 for button names PM25,PM10
                Dflt: $pollutants with name $buttons
 -E|--export    Enable button to export the chart. If repeated: export to print only.
 -b|--buttons   Comma separated names of button names for table switch: eg PM25,PM10
                Will need to generate more then one time per button and
                to combine all generated scripts.
                Use id as one of the buttons. No button is displayed if there is
                only one button name provided.
 -A|--{AQI,aqi,index} {LKI|AQI|EU|none} colored bands in background for quality levels.
                Band is only shown with national station graph.
                DEPRECATED.
 -B|--bands     Turn show of AQI or LKI color bands on with official stations graphs.
                Currently bands are not working any more for some reason.
 -M|--mean      Change default if (nr of args > 4) TRUE value.
                Default show mean of graphs and individual
                measurements are first made invisual.
 -L|--last      Use this date/time as last date iso last 'datum' of referenced
                station measurement.
 -S|--start     Use this date/time as start point of the chart. Dflt 3 weeks
                before last time of measurement.
 -f|--first     Use as start point of chart the first date of of measurement
                for chart period. Dflt: use period (3 weeks before last measurement).
 -W|--wdir      The working directory with own modules.
 -w|--web       The website private page directory to store the page.
                The website path is not prepended if output file name start with
                ./ or /
 -c|--correct   The PM values are corrected with rel. humidity correction factor
                factor = 4.65 * (100 - hum)**-0.65
                Humidity measurements is one element of correction arithmetic.
                Humidity of stations will be collected per station if present.
 -a|--aggregation [number] Use nr of minutes as minimal period to calculate average values.
                Default: 6 minutes for small periods. Script will search minimal
                period of minutes between measurements.
                Max (eg LML stations)  is one hour.
 --timeshift    Time to be shifted earlier in minutes for station name with pattern '$timematch'.
                Default NL10131 for 150 minutes.
 --timematch    Pattern expression to match station/table name, e.g. (NL1|NL2).
                Default Vredepeel and Horst ad Maas: (NL10131|HadM).
 --avoid        Pattern: if match pattern do not use this table name(s) in regio average calculation.
                Default: use all tables.

Software revision version: $Version
This program is free software: you can redistribute it and/or modify
                Humidity measurments is one element of correction arithmetic.
                Humidity of stations will be collected per station if present.
it under the terms of the GNU General Public License as published by
the Free Software Foundation.
The script depends om mysql, yui-compressor,
and perl modules (JSON,Posix,Time,autodie,LWP,URI and DBI). 
See the script constant declaration for the default configuration values.
EOF
        exit(0);
        };
   };
}
Getopt::Mixed::cleanup();
$verbose = 3 if $debug;
if( $language =~ /UK/ ) {
    $poltype     =~ s/stof/particular matter/;
    $title =~ s/Samen Meten aan Luchtkwaliteit/Together we Measure Air Quality/;
}

die "FATAL ERROR: no database user/password defined, e.g. define use environment variable DBUSER and/or DBPASS\n" if length($mypass) <= 0;


# the Joost fit correction factor to correct PM values with rel. hum  values
# correction coefficients come from RIVM VW2017 project 
# routine is unused if javascript does corrections
# this is purely EXPIRIMENTAL. Correction factor is still in development
sub CorrectPM {
    my ($PM,$PMval,$HUMval) = @_;
    return $PMval if not $correctPM;
    return 'null' if $PM !~ /PM_?(10|25)/i;
    return 'null' if (not defined $PMval) or (not defined $HUMval);
    return 'null' if ($PMval eq 'null') or ($HUMval eq 'null');
    my $rts = $PMval;
    return 'null' if $PMval <= 0;
    $HUMval = 99.0 if $HUMval >= 99.0;
    $HUMval = 1.0 if $HUMval <= 1.0;
    if ( $PM =~ /PM_?10/i ) {
        # correction factor PM10 from RIVM jan 2018 for SDS011 sensor
        # $rts = int( ($PMval * 4.65 * ((100.0-$HUMval)**-0.65)) * 100.0)/100.0;
        # correction factor from RIVM report may 2018
        $rts = int( ($PMval * 4.31 * (($HUMval)**-0.409)) * 100.0)/100.0;
    }
    elsif ( $PM =~ /PM_?25/i ) {
        # correction factor PM2.5 from RIVM may 2018 for SDS011 sensor
        $rts = int( ($PMval * 3.9 * (($HUMval)**-0.409)) * 100.0)/100.0;
    }
    return $rts
}

# if not done from javascript next is called
# correct PM values in the data strings for PM with RV values 
# TO DO: second arg should be an array of data indexes
sub CorrectPMdata {
    my( $data, $pmIndex) = @_;
    return undef if not defined $data->[$pmIndex];
    return undef if not defined $data->[$pmIndex]{data};
    my $PMtype;
    $PMtype = $data->[$pmIndex]{pol} if defined $data->[$pmIndex]{pol};
    $PMtype = $data->[$pmIndex]{sense} if defined $data->[$pmIndex]{sense};
    return $data->[$pmIndex]{data} if (not defined $PMtype) || ($PMtype !~ /pm/i);
    # no correction for governmental measurements
    return $data->[$pmIndex]{data} if not defined $data->[$pmIndex]{table};
    return $data->[$pmIndex]{data} if $data->[$pmIndex]{table} !~ /_/;
    return $data->[$pmIndex]{data} if not $data->[$pmIndex]{label};
    my $RVdata;
    if( not defined $RVstations{$data->[$pmIndex]{table}} ){
        if( (not defined $RVstations{default}) || (not defined $RVstations{default}{rv}) ){
            $correctPM = 0;
            print STDERR "Missing humidity measurments to do corrections. Switched off\n";
            return $data->[$pmIndex]{data};
        }
        $RVdata = $RVstations{default}{rv};
    } else { $RVdata = $RVstations{$RVstations{$data->[$pmIndex]{table}}}{rv}; }
    my @RV = split(/,/,substr($RVdata,1,-1));

    my @PM = split(/,/,substr($data->[$pmIndex]{data},1,-1));

    for( my $i = 0; $i <= $#PM; $i++ ) {
        $PM[$i] = CorrectPM($PMtype,$PM[$i],$RV[$i]);
    }
    return '['.join(',',@PM).']';
}

sub Check_DB { # called only once from first call to query routine
    state $checkedOnce = 1;
    if( $mysql ){ return 1; }
    return 0 if length( $mydb ) < 1;
    return 0 if length( $myhost ) < 1;
    return 0 if length( $myuser ) < 1;
    return 0 if length( $mypass ) < 1;
    $mysql = DBI->connect("DBI:mysql:".$mydb.":".$myhost,$myuser,$mypass);
    if( not $mysql ){
        if( $checkedOnce > 0 ){
            print STDERR "ERROR Cannot open mysql database ".$mydb." on host ".$myhost.", with user ".$myuser.", error: ". DBI->errstr."\n" ;
            exit 1;
        }
    }
    return 1;
}

my %DB_cols = ( );      # sensors names per table
# obtain all sensors for a station in the DB table
sub Get_Sensors {
    my $tbl = shift; return 0 if not $tbl;
    Check_Tbl($tbl) if not $DB_cols{$tbl};
    if( not (scalar keys %{$DB_cols{$tbl}}) ){
        # only once at the start we build a column existance cache
        my $qr = query($tbl, "DESCRIBE $tbl;");
        if( (not $qr) || ($#{$qr} < 0) ){
            print STDERR "ERROR Cannot obtain table $tbl description\n";
            return 0;
        }
        # mysql counts cells from 0!
        $DB_nr_cols{$tbl} = 0 if not defined $DB_nr_cols{$tbl};
        for( my $index = 0; $index <= $#{$qr} ; $index++ ){
            
            next if $qr->[$index] =~ /^((id|datum)|.*_(valid|ppb|color))$/ ;
            next if $meteo and ($meteo ne $tbl) and ($qr->[$index] =~ /(temp|rv|luchtdruk|w(s|r)|(prev|day)?rain)/);
            $DB_cols{$tbl}{ $qr->[$index] } = 1;
            $DB_nr_cols{$tbl}++;
            $DB_cols{$tbl}{$qr->[$index]} = 1;
        }
    }
    return 1;
}

# check if sensor is available in table if not add the column
sub Check_Sensor {
    my $tbl = shift;
    my $col = lc(shift);
    my $comment = shift;
    return 0 if not Get_Sensors($tbl);
    return 1 if defined $DB_cols{$tbl}{$col};
    return 0;
}

# one row of values from one column out of the DB table
sub query {
    return 0 if Check_DB == 0;
    my $tbl = shift; Check_Tbl($tbl) if $tbl;
    my $q = shift;
    if( (not $mysql) or ($mysql == 1) or (not $q) ){ return undef; }
    print STDERR "MYSQL: $q\n" if $debug > 1;
    my $sth = $mysql->prepare($q); $sth->execute();
    #  ref to 2 dimensional refs to array string values
    if( $q =~ /^\s*(show|describe|select)/i ){
        my $r = $sth->fetchall_arrayref();
        print STDERR "ERROR mysql query: $q with error:\n" . DBI->errstr . "\n"
            if ( DBI->errstr &&  $#{$r} < 0 );
        return undef unless $r->[0];
        my @rts = ();
        for( my $i=0; $i <= $#{$r}; $i++ ){
            $rts[$i] = $r->[$i][0] if $#{$r->[$i]} >= 0;
        }
        if( not @rts ){
            # print STDERR "$WARNING mysql query: $q with empty array:\n" . DBI->errstr . "\n";
        }
        $sth->finish(); return \@rts;
    } else { return (DBI->errstr ? undef : 1); }
}

# collect from database the table column names
# if table does not exists create it
sub Check_Tbl {
    my $tbl = shift;
    return 0 if not $tbl;
    return 1 if defined $DB_cols{$tbl};
    my $qry = query('',"SHOW TABLES");
    for( my $i = 0; $i <= $#{$qry}; $i++ ){
        next if $qry->[$i] !~ /^$tbl$/;
        $DB_cols{$qry->[$i]} = {} if not $DB_cols{$qry->[$i]}; # the table already exists
        Get_Sensors($qry->[$i]);        # mark sensors present in the table
    }
    return 1 if defined $DB_cols{$tbl};
    return 0;
}

# collect info from database SENSORS table. Return hash table with info
sub Get_Info {
    my $id = shift; return undef if (not defined $id) || (not $id);
    my $qry; my %info; my $indx = '';
    my $sensors = SENSORS; Check_Tbl($sensors);
    my $project = shift;
    if( defined $project ) { $project = " AND project =  '$project'"; }
    else { $project = ''; }
    foreach my $i ('serial','label') {
        $qry = query($sensors,"SELECT count(*) FROM $sensors WHERE  $i = '$id'$project");
        if( $qry->[0] ) {
            $indx = $i; $info{$i} = $id; last;
        }
    }
    return %info if not $indx;
    $qry = query($sensors,"SELECT
            CONCAT(serial,
                '\t', if( isnull(label),'',label),
                '\t', if( isnull(coordinates),'',coordinates),
                '\t', UNIX_TIMESTAMP(first),
                '\t',if( isnull(street),'',street),
                '\t',if( isnull(village),'',village),
                '\t',if( isnull(municipality),'',municipality),
                '\t',if( isnull(description),'',description))
            FROM $sensors WHERE $indx = '$id' ORDER BY active DESC, datum DESC");
    return undef if ($#{$qry} < 0) or (not defined $qry->[0]);
    my @in = split /\t/, $qry->[0];
    $info{serial}=$in[0];
    $info{label}=$in[1];
    $info{coordinates}=$in[2];
    $info{first}=$in[3] if defined $in[3];
    $info{street}=$in[4] if defined $in[4];
    $info{street} =~ s/\s+[0-9].*// if defined $in[4];
    $info{street} = 'A73' if $info{street} =~ /.*Wust.*/;
    $info{village}=$in[5] if defined $in[5];
    $info{municipality}=$in[6] if defined $in[6];
    $info{location}=$in[4] if defined $in[4];
    $info{location} =~ s/\s+[0-9].*// if defined $in[4];
    $info{location} = $info{location} . ' '.$info{village}
        if defined $in[5];
    $info{location} = 'Noord Limburg' if $info{location} =~ /(Castenray|Oirlo)/;
    if( $language =~ /UK/ ) {
      $info{location} = $info{location} . ' (Twsp. '.$info{municipality}.')'
        if( (defined $in[6]) and ($info{village} ne $info{municipality}));
    } else {
      $info{location} = $info{location} . ' (gem. '.$info{municipality}.')'
        if( (defined $in[6]) and ($info{village} ne $info{municipality}));
    }
    $info{location} =~ s/,\s+\(/ (/g;
    $info{location} = $info{label} if not defined $info{location};
    $info{sensors} = '';
    if( defined $in[7] && $in[7] =~ /hw:\s/i ) { # try to guess sensor types
        my @ar;
        if( $in[7] =~ /(PMS.003)/i ) { push(@ar,"PM:Plantower"); }
        elsif ($in[7] =~ /(SPS..)/i ) { push(@ar,"PM:Sensirion"); }
        elsif( $in[7] =~ /(SDS...)/i ) { push(@ar,"PM:Nova"); }
        if( $in[7] =~ /(BME..0)/i ) { push(@ar,"meteo:Bosch"); }
        elsif ($in[7] =~ /(SHT..)/i ) { push(@ar,"meteo:Sensirion"); }
        elsif( $in[7] =~ /(DHT..)/i ) { push(@ar,"meteo:Adafruit"); }
        if( $in[7] =~ /NEO/i ) { push(@ar,"GPS:Neo"); }
        #if( $in[7] =~ /(PMS.003)/i ) { push(@ar,"PM(Plantower $1)"); }
        #elsif ($in[7] =~ /(SPS..)/i ) { push(@ar,"PM(Sensirion $1)"); }
        #elsif( $in[7] =~ /(SDS...)/i ) { push(@ar,"PM(Nova $1)"); }
        #if( $in[7] =~ /(BME..0)/i ) { push(@ar,"meteo(Bosch $1)"); }
        #elsif ($in[7] =~ /(SHT..)/i ) { push(@ar,"meteo(Sensirion $1)"); }
        #elsif( $in[7] =~ /(DHT..)/i ) { push(@ar,"meteo(Adafruit $1)"); }
        #if( $in[7] =~ /NEO/i ) { push(@ar,"GPS(Neo-6)"); }
        $info{sensors} = join(' ',@ar) if $#ar >= 0;
    }
    return %info;
}

# last timestamp of one value from sensor station
sub Get_last {
    my $polSelect = shift;
    my $Ref = shift; $Ref = REF if not defined $Ref;
    my $thisLast = 0; my $pol = '';
    my $last = 0;
    # check the available pollutants from the pollutant choice
    $polSelect =~ s/[\(\)]//g;
    my @pols;
    if ( $meteo and ($Ref eq $meteo) ){
        return $last if $polSelect !~ /(temp|rv|luchtdruk|w[sr]|(prev|day)?rain)/;
    }
    @pols = split(/\|/,$polSelect);
    foreach (@pols) {
        $pol = $_;
        next if not Check_Sensor($Ref,$_);
        my $qry = query($Ref,"SELECT UNIX_TIMESTAMP(datum) FROM $Ref WHERE ${pol}_valid ORDER BY datum DESC LIMIT 1");
        next if $#{$qry} < 0;
        $last = $qry->[0] if $qry->[0] > $last;
        # do not bother timeshift of 2-3 hours with measurements of official stations here
    }
    if (not $last) {
        my @NoPol = ();
        foreach my $p (@pols) {
            next if $meteo and ($p =~ /(temp|rv|luchtdruk|w[sr]|(prev|day)?rain)/);
            $NoPol[$#NoPol+1] = $p;
        }
        printf STDERR ("Could not find any pollutant of %s in $Ref table\n",join(', ',@NoPol))
           if $#NoPol >= 0;
    }
    return $last;
}

# we need to provide HighCharts a row of measurements at fixed intervals: unit
sub Array2Units {
    my ($data, $end, $correct, $limit) = @_;
    $correct = 0 if not defined $correct;
    my $unit = 5*24*60*60;
    my $time = 0; my $value = 0.0;
    my @pairs;
    return 60*60 if $#{$data} <= 0;
    my $strt = 0;
    # last time with time zone bug/error is: 2018/01/10 02:27:18 on correction needed
    # epoch time was:  1515547638 secs
    for( my $i = 0; $i <= $#{$data}; $i++) { # build an array of time,value pairs
        $value = $time = $data->[$i];
        $time =~ s/=.*//; $value =~ s/.*=//;
        if( $correct && ($time <= $limit ) ) { $time += $correct; }
        push(@pairs,[$time,$value]);
        if( not $i ) {
            $strt = $time; next;
        }
        my $diff = abs($pairs[$i-1][0] - $pairs[$i][0]);
        $unit = $diff if $diff < $unit;
    }
    # we use two aggregation models: 5*60 (5 minutes) and 60*60 (1 hour)
    $unit = int(($unit+59)/60)*60; # use units in minutes
    $unit = $aggregation*60 if $unit < $aggregation*60; # use commandline minimal
    # build a new array with fixed $unit intervals
    my %rts; my @values; my $count = 0;
    my $last = $pairs[0][0];
    push(@values, $pairs[0][1]);
    for( my $i = 1; $i <= $#pairs; ) {
        while( $last+$unit < $pairs[$i][0] ) {
            $last += $unit; $count++;
            # push(@times,$last);
            push(@values,'null');
        }
        $cnt = 0, $sum = 0.0;
        $last += $unit;
        for( ; ($i <= $#pairs) && ($pairs[$i][0] < $last); $i++ ) {
            $cnt++; $sum += $pairs[$i][1];
        }
        $sum /= $cnt if $cnt;
        if( $sum < 0.1 ) {
            push(@values,'null');
        } else {
            push(@values,int($sum*10+0.4)/10.0); $count++;
        }
    }
    while( $last+$unit < $end ) {
         $count++; $last += $unit;
         push(@values,'null');
    }
    $rts{first} = $pairs[0][0]; $rts{last} = $last; $rts{values} = \@values;
    $rts{count} = $count; $rts{unit} = $unit;
    return \%rts;
}

# extract data from DB for a pollutant and serialize it into json data struct
# return ref to hash table with name, location, pollutant, string as json data
sub Get_data {
    my ($tbl,$pol,$last,$secs,$period) = @_; my %rslt;
    # printf("Get data from %s for pol %s\n",$tbl,$pol);
    $period = PERIOD if not defined $period;
    return \%rslt if not defined $DB_cols{$tbl}{$pol}; 
    # take average in the hour of measurement
    # VM2017 is using Zulu time minus 1 hour, we need to correct this
    # TO DO: correct the MySql DB entries!
    # software had timezone bug of one hour before 1515547638 epoch time
    # last time with time zone bug/error is: 2018/01/10 02:27:18 on correction needed
    my $corr = 0 ; $corr += 3600 if $tbl =~ /_/;
    my $first = 0;
    if( $first_time && ($first_time < $last) && ($first_time < ($last - PERIOD)) ) {
        $period = $last - $first_time ;
    }
    $first = $last-$period;
    $last -= $corr if $last <= 1515547638;
    $first -= $corr if $first <= 1515547638;
    my $Ufactor = '';
    $Ufactor = '*10/36' if $pol =~ /^ws$/i; # WASP windspeed km/h -> m/sec
    # there is a timeshift of minus 2-3 hours for official measurements stations
    # should be corrected in the database station table
    my $tShift = 0;
    $tShift = $timeshift if $tbl =~ /$timematch/;
    my $data = query($tbl,"SELECT CONCAT(UNIX_TIMESTAMP(datum) -$corr -$tShift ,'=',ROUND(${pol}${Ufactor},1)) FROM $tbl
                WHERE (UNIX_TIMESTAMP(datum)-$tShift >= $first) AND 
                    (UNIX_TIMESTAMP(datum)-$tShift <= $last) AND
                    NOT ISNULL($pol) AND ${pol}_valid
                    ORDER BY datum");
    return \%rslt if $#{$data} < MINHOURS*(60*60/$secs); # MINHOURS hours minimal
    my $values = Array2Units($data,$last,$corr,1515547638);
    $rslt{pol}=$pol; $rslt{table}=$tbl; $rslt{data} = '[';
    $rslt{first} = $values->{first}; $rslt{last} = $values->{last};
    $rslt{count} = $values->{count}; $rslt{unit} = $values->{unit};
    if( ${$values->{values}}[$#{$values->{values}}] eq 'null' ) {
        $#{$values->{values}} -= 1; $rslt{count} -= 1;
    }
    $rslt{data} .= join(',',@{$values->{values}}) . ']';
    printf STDERR ("WARNING: for table %s, period %d days ending at %s: not enough values found: %d values, expected %d values.\n",
            $tbl, int(($period/(24*60*60))+0.5),
            strftime("%Y-%m-%d %H:%M",localtime($last)),
            $rslt{count}, int(($period/$rslt{unit})+0.5) )
        if not defined $rslt{data};
    printf STDERR ("For table %s, sensor %s: found %d values,\n\tstarts at %s, ends at %s\n",
            $tbl, $pol, $rslt{count}, 
            strftime("%Y-%m-%d %H:%M",localtime($rslt{first})),
            strftime("%Y-%m-%d %H:%M",localtime($rslt{last})))
        if $verbose > 1;
    return \%rslt;
}

# collect humidity values for a station
sub addRVstation {
    my ($table, $last, $overWrite) = @_;
    $overWrite = FALSE if not defined $overWrite;
    return FALSE if not $correctPM;
    return TRUE if defined $RVstations{$table};
    foreach my $S (keys %{$DB_cols{$table}}) {
       next if $S !~ /(rv)$/i;
       my %flt = ( cnt => 0 );
       $RVstations{$table} = \%flt;
       $RVstations{$table}{$S} = Get_data($table,$S,$last,60*60);
       $RVstations{$table}{$S} = $RVstations{$table}{$S}->{data};
       if( $overWrite || (not defined $RVstations{default}) ) {
           my %new = ( cnt => 0 );
           $RVstations{default} = \%new;
           $RVstations{default}{$S} = $table;
       }
       return TRUE;
    }
    return FALSE;
}
    
# sort polutant types
sub polType {
    $_ = shift;
    if ( /pm_?[0-9]/i ) { # dust
        s/.*pm_?//i; s/25/2.5/; s/_cnt//; s/0([1-9])/0.$1/; my $z = $_;
        return sprintf("%d",100-int(10*$z));
    }
    if (/(temp|rv|luchtdruk|w[sr]|rain)/) { # meteo
        return '101' if /temp/;
        return '105' if /rv/;
        return '110' if /luchtdruk/;
        return '154' if /dayrain/;
        return '152' if /prevrain/;
        return '150' if /rain/;
        return '160' if /ws/;
        return '162' if /wr/;
        return '190';
    }
    if ( /[onch]{1,2}[0-9]/i ) { # gasses
        return '201' if /o3/i;
        return '220' if /no2/i;
        return '232' if /co2/i;
        return '230' if /co/i;
        return '240' if /nh3/i;
        return '290';
    }
    return $_;
}

sub byPol { # to sort polutants
    polType($b) cmp polType($a);
} 

# combine 2 of more data streams into first one
sub Combine {
    my $newpol = shift; my @list = @_;
    my $first = $list[0]->{first}; my @data;
    for( my $j = 0; $j <= $#list; $j++) {
        $first = $list[$j]->{first} if $list[$j]->{first} < $first;
    }
    my $last = $list[0]->{last};
    for( my $j = 0; $j <= $#list; $j++) {
        $last = $list[$j]->{last} if $list[$j]->{last} > $last;
        my @tmp = split(/[\[\],]/,$list[$j]->{data}); shift(@tmp);
        $data[$j] = \@tmp;
    }
    my @newdata; my $time = $first; my $unit = $list[0]->{unit};
    for( my $i = 0;;$i++) {
       my @new;
       for( my $j = 0; $j <= $#list; $j++) {
          my $elmnt = 'null';
          if( ($time >= $list[$j]->{first}-60) || ($time <= $list[$j]->{last}+60) ){
            $elmnt = $data[$j][0]; shift(@{$data[$j]});
          }
          push @new, $elmnt;
        }
        last if not defined $new[0];
        if( $#new >= 0 ) {
            $newdata[$i] = '['.join(',',@new).']';
        } else {
            $newdata[$i] = '['.']';
        }
        $time += $unit;
        last if $time > $last;
    }
    $list[0]->{data} = '['.join(',',@newdata).']';
    $list[0]->{sense} = $newpol;
    $list[0]->{pol} = $newpol;
    $list[0]->{last} = $last; $list[0]->{first} = $first;
    # add combi fie statements
    return $list[0];
}

# collect the data for a serie of stations (DB table names)
# return a ref to array of hashes: table name, location name, pm name
sub Collect_data {
    my $pols = shift; my @stations = @_; my $last = 0;  my %info;
    if( $last_time ) {   $last = $last_time ; }
    else {
        $last = Get_last($pols,$stations[0]);
        my $lt;
        for ( my $i = 1; $i <= $#stations; $i++) {
          $lt = Get_last($pols,$stations[$i]);
          $last = $lt if $lt > $last;
        }
        $lt = 0; $lt = Get_last($pols,$reference) if $reference;
        $last = $lt if $lt > $last;
    } # default last date/time of REF station
    my @data; my $first = time;
    if( not $last ) {
        print STDERR "Cannot find last measurement date/time\n";
        return 0;
    }
    for( my $i = 0; $i <= $#stations; $i++ ) {
        if( not Check_Tbl($stations[$i]) ){ next; }
        if( $stations[$i] =~ /_/ ) { # sensor kits only
            my $CorrectME = 0; my @stationData;
            my $id = $stations[$i] ; $id =~ s/^[^_]*_//;
            my $project = $stations[$i]; $project =~ s/_.*//;
            %info = Get_Info($id,$project); # search serial or label with this id
            print STDERR "Cannot find station $stations[$i] in database.\n"
                if not defined $info{serial};
            next if not defined $info{serial};
            my $tbl = $stations[$i];
            $tbl = "${project}_$info{serial}";
            next if not Check_Tbl($tbl);
            if( $use_first ) {
                if( $first_time ) {
                    print STDERR ("ATTENT: Use of '-f' option is redefining '-S' (start) argument!\n");
                    if ( $first_time > $info{first} ){
                        $first_time = $info{first};
                    }
                } else { $first_time = $info{first};
                }
            }
            Get_Sensors($tbl);
            addRVstation($tbl,$last);
            # sort keys first
            my %wind;
            foreach my $S (sort byPol keys %{$DB_cols{$tbl}}) {
                # next if $S =~ /(^id|^datum|_valid)/;
                #next if $S =~ /_cnt/; # do not handle eg pm25_cnt etc
                if( ($S !~ /w[rs]/i) || ($pols !~ /wind/i) ) {
                    next if $S !~ /^$pols$/i; # only pollutants choice
                }
                # interval of measurements should be 5*60 seconds
                $D = Get_data($tbl,$S,$last,60*60);
                next if not defined $D->{data};
                my $c = () = $D->{data} =~ /,/g; # count number of elements-1
                next if $c*$D->{unit} < 12*60;   # minimal 12 hours of values
                $first = $D->{first} if $D->{first} < $first;
                $last = $D->{last} if $D->{last} > $last;
                $D->{location} = $info{location};
                $D->{village} = $info{village};
                $D->{label} = $info{label}; # mark for low cost sensor
                $D->{sense} = $S;
                $D->{organisation} = 'MySense';
                $D->{municipality} = $info{municipality} if defined $info{municipality};
                $D->{sensors} = $info{sensors} if defined $info{sensors};
                if ( defined $info{street} ) {
                    $D->{street} = $info{street};
                    $D->{street} =~ s/\s+[0-9].*//;
                    $D->{href} = lc "?q=content/$D->{village} $D->{street}";
                    $D->{href} =~ s/\.*\s+/-/g;
                    $D->{street} =~ s/straat/str/;
                } else { $D->{href} = ''; }
                if( $correctPM && ($S =~ /pm/i) ) {
                    my $dflt = $tbl;
                    if( not defined $RVstations{$tbl} ) {
                        $dflt = 'default';
                        if( not defined $RVstations{$dflt} ) {
                            my %flt = ( cnt => 0 );
                            $RVstations{$dflt} = \%flt;
                        }
                    }
                    $D->{CorrectME} = $dflt; # flag it to obtain index rv
                    $RVstations{$dflt}{cnt} += 1;
                }
                if ( ($S =~ /w[rs]/) && ($pols =~ /wind/) ){
                    $wind{$S} = $D;
                } else {
                    if( $#data < 0 ) { # always first in array
                        push @data, $D;
                    } else {
                        push @data, $data[0];
                        $data[0] = $D;
                    }
                }
            }
            # defeat ws and wr only from one table
            if ( (defined $wind{'ws'}) && (defined $wind{'wr'}) ){
                if( $wind{'ws'}->{unit} == $wind{'wr'}->{unit} ) {
                    push @data, Combine('wind',$wind{'ws'},$wind{'wr'});
                } else {
                    print STDERR "wind ws and wr unit size differ in table $wind{'wr'}->{table} and $wind{'ws'}->{table}. Skipped\n";
                }
                $barb = TRUE; $java = TRUE;  # use javascript from HighCharts
            }
        } else {
            if( not Check_Tbl($stations[$i]) ){
                print STDERR "Cannot find station $stations[$i] in database.\n";
                next;
            }
            Get_Sensors($stations[$i]);
            addRVstation($stations[$i],$last,TRUE);
            my @info = ('','','');
            my $qry = query("stations","SELECT CONCAT(name,';;',organisation,';',municipality,';',id,';',aqi_url) 
                        FROM stations WHERE stations.table = '$stations[$i]' LIMIT 1");
            if( $#{$qry} < 0 ) {
                my $serial = $stations[$i] ; $serial =~ s/^[^_]*_//;
                $qry = query("Sensors","SELECT CONCAT(street,';',village,';','BdP',';',municipality,';$stations[$i]') 
                        FROM Sensors WHERE Sensors.serial = '$serial' and Sensors.active order by active desc, id desc LIMIT 1");
            }
            @info = split /;/,$qry->[0] if $#{$qry} >= 0;
            $info[0] =~ s/\s+[0-9].*//;  # shorten the street string a bit
            $info[0] =~ s/straat/str/;
            foreach my $S (keys %{$DB_cols{$stations[$i]}}) {
                next if $S =~ /(^id|^datum|_(valid|color|pp))/;
                # may add here more sensors
                next if $S !~ /$pols/; # only pollutants of choice
                my $D = Get_data($stations[$i],$S,$last,60*60);
                next if not defined $D->{data};
                my $c = () = $D->{data} =~ /,/g;
                next if $c < 12;            # minimal 12 hours of values
                $D->{sense} = $_;
                $first = $D->{first} if $D->{first} < $first;
                $last = $D->{last} if $D->{last} > $last;
                # location = street, village
                $D->{location} = $info[0];  # station name or sensor street
                $D->{street} = ''; $D->{village} = '';
                $D->{href} = '';
                if( defined $info[1] ) {
                    $info[0] =~ s/\s+[0-9].*//;  # shorten the street string a bit
                    if (defined $info[4] ) {
                        $D->{href} = lc "?q=content/$info[1] $info[0]";
                        $D->{href} =~ s/ /-/g;
                    }
                    $info[0] =~ s/straat/str/;
                    $D->{street} = $info[0];
                    $D->{village} = $info[1];
                    $D->{location} .= " $info[1]"; # station village
                }
                if ( defined $info[3] ) {
                    if( $info[3] !~ $info[1] ) {
                        $D->{location} =~ s/,\s*//;
                        if( $language =~ /UK/ ) {
                          $D->{location} .= " (Twsp. $info[3])";
                        } else {
                          $D->{location} .= " (gem. $info[3])";
                        }
                    }
                    $D->{href} = $info[5] if defined $info[5];
                }
                $D->{organisation} = "MySense";
                $D->{organisation} = $info[2] if defined $info[2];
                push @data, $D;
            }
        }
    }
    printf STDERR ("Collected chart data from %s upto %s\n",
              strftime("%Y-%m-%d %H:%M",localtime($first)),
              strftime("%Y-%m-%d %H:%M",localtime($last)) )
          if $verbose;
    $#data = -1 if ($#data+1) < $mingraphs;  # at least MINGRAPHS graphs
    push @data, $first, $last if $#data > 0; # end of array has first and last date
    return \@data;
}

my %Sense2Unit = (
    'pm25'    => '\\u00B5g/m\\u00B3',
    'pm10'    => '\\u00B5g/m\\u00B3',
    'pm1'     => '\\u00B5g/m\\u00B3',
    'at_pm25' => 'p/dm\\u00B3',
    'at_pm10' => 'p/dm\\u00B3',
    'pm_cnt'  => '\\u00B5m #p',
    'luchtdruk' => 'hPa',
    'pressure' => 'pHa',
    'rv'       => '\\u0025',
    'rain'     => 'mm/h',  # current hour accumulated Wasp Mote
    'dayrain'  => 'mm/24h',# last 24 hours WaspMote
    'prevrain' => 'mm/h',  # prev hour Wasp Mote
    'wr'       => '\\u00B0',
    'ws'       => 'km/h', # Wasp Mote: km/h
    'wind'     => 'barb',
    'humidity' => '\\u0025',
    'temp'     => '\\u2103',
    'temperature'     => '\\u2103',
);
# convert sensor type to measurement units
sub ConvertS2U {
    my ($sense) = @_; my $s = lc($sense);
    $s =~ s/<[^>]*>//g; $s =~ s/[^_a-z0-9]//g; $s =~ s/pm[0-9]{1,2}_cnt/pm_cnt/;
    return $sense if not defined $Sense2Unit{$s};
    if( ($Sense2Unit{$s} =~ /barb/) && ($language !~ /UK/) ){ return 'weerhaak'; } 
    return $Sense2Unit{$s};
}
            
# Intro to use chrt with button or not
sub InsertTableHdr {
    my ($buts, $pols) = @_; my @BUTS = @{$buts}, @POLS = @{$pols};
    my @Buts = @{$buts};
    my $but = $buttons;
    for( my $i =0; $i <= $#BUTS; $i++ ) {
        $BUTS[$i] =~ s/pm([0-9]+)/PM$1/g; $BUTS[$i] =~ s/(PM[02])\./$1/;
        $BUTS[$i] =~ s/PM([0-9]+)/PM<sub>$1<\/sub>/g;
        $BUTS[$i] =~ s/PM<sub>([02])([0-9)])/PM<sub>$1.$2/g;
        $BUTS[$i] =~ s/\|.*//; $Buts[$i] = $BUTS[$i]; $Buts[$i] =~ s/<\/?sub>//g;
        $POLS[$i] =~ s/\|(dtemp|pm_[0-9]+)//g;
        if( $language =~ /UK/ ){
            $POLS[$i] =~ s/temp/temperature/; $POLS[$i] =~ s/rv/rel.humidity/;
            $POLS[$i] =~ s/ws/wind speed/; $POLS[$i] =~ s/wr/wind direction/;
            # Wasp Mote specific
            $POLS[$i] =~ s/prevrain/rain\/hour/; $POLS[$i] =~ s/dayrain/rain\/day/;
        } else {
            $POLS[$i] =~ s/temp/temperatuur/; $POLS[$i] =~ s/rv/rel.vochtigheid/;
            $POLS[$i] =~ s/ws/windsnelheid/; $POLS[$i] =~ s/wr/windrichting/;
            # Wasp Mote specific
            $POLS[$i] =~ s/prevrain/mm\/h/; $POLS[$i] =~ s/dayrain/mm\/dag/;
            $POLS[$i] =~ s/rain/mm/;
        }
        $POLS[$i] =~ s/[\)\(]//g; $POLS[$i] =~ s/\|/, /g;
        $POLS[$i] =~ s/(.*), /$1 en /;
        $POLS[$i] =~ s/PM([0-9]+)/PM<sub>$1<\/sub>/ig;
    }
    my $measurements = join(', ',@POLS); $measurements =~ s/(.*), /$1, en /;
    my $meteoStrg = '';
    if( $language =~ /UK/ ) {
    $meteoStrg = ' In the case of meteo data the meteo measurements are taken from one special air quality measurement kit. ' if $meteo;
    return 'In the legendum one can enable or disable one of the graphs in the chart. Click on "show" for this.<br />The chart support you to scroll and zoom though a period of time. Use the slider for this.' if $#BUTS < 1;

    return '<table width=100% border=0 bordercolor=white><tr><td style=\'padding-right:25px\'><div class="table-button" title="Push the button to switch from'.
    join(' or ',@Buts) .
    ' switch from type of display of the measurements for ' . $measurements .'"><span style="position:relative;left:1px;top:-1px;font-size:9px;">'.
    join('&nbsp;&nbsp;',@BUTS) .
    '</span><button id="tableButton"><div style="margin-right:-4px;font-size:12px">'.
    $BUTS[0] .
    "</div></button><span style='position:absolute;top:-20px;left:+8px;text-shadow:none;text-weight:bold;color:#3b5d9c'>select</span></div></td><td>The table below with recent measurement values in the region. $meteoStrg<br />Using the select button one is able to switch the type of dust measurement: " .
    join(' or ',@BUTS) .
    '.</td></tr><tr><td colspan=2>In the legendum one can enable or disable a graph of a location. Click "show" to enable a graph.<br />You should be able to relocate the legendum by moving the :: mark of the legendum.<br />By dragging the slider one is able to change the period and zooming of the graphs.</td></tr></table><br />'
    } else {
    $meteoStrg = ' Tav meteo data is gebruik gemaakt van een speciale meteo sensor kit. ' if $meteo;
    return "Als achtergronds kleur (en nivo) wordt bij vertoning van een fijnstof grafiek het gezondheidsrisico weergegeven volgens de <a href='https://www.epa.gov/sites/production/files/2016-04/documents/2012_aqi_factsheet.pdf'>U.S. Environmental Protection Agency</a> PM<sub>2.5</sub> of PM<sub>10</sub> 24-uurs tabellen.<p>In de legendum kan door aanklikken een grafiek voor een enkele sensorkit meting aan- of uitgezet worden. Klik 'toon' aan voor het aan- of uitzetten van de betreffende grafiekweergave." .
        ($Mean ? 
        "<br />Bij 'regionale overzichts grafieken' worden er een grafiek getoond met de gemiddelde waarden samen met 50% en 90% spreidingsgrafiek. De individuele grafieken kunnen apart aan- of uitgezet worden door deze een voor een aan te klikken in de legendum. Tav de metingen die bovengemiddeld hoog zijn worden maximaal 3 grafieken direct zichtbaar gemaakt."
          : ""). 
        "<br />De chart biedt de mogelijkheid om met de 'slider' (onderin de chart) in een bepaalde periode van de grafiek in of uit te zoomen. Door te schuiven over de tijdas kan de weergave periode veranderd worden." if $#BUTS < 1;

    return '<table width=100% border=0 bordercolor=white><tr><td style=\'padding-right:25px\'><div class="table-button" title="Druk (click) op deze knop om van '.
    join(' of ',@Buts) .
    ' weergave te wisselen tav de metingen voor ' . $measurements .'"><span style="position:relative;left:1px;top:-1px;font-size:9px;">'.
    join('&nbsp;&nbsp;',@BUTS) .
    '</span><button id="tableButton"><div style="margin-right:-4px;font-size:12px">'.
    $BUTS[0] .
    '</div></button><span style="position:absolute;top:-20px;left:+8px;text-shadow:none;text-weight:bold;color:#3b5d9c">keuzeknop</span></div></td><td>De onderstaande tabel met de recente meetwaarden in de regio.<br />Met de keuzeknop kan gewisseld worden van type fijnstof: ' .
    join(' of ',@BUTS) .  $meteoStrg .
    ".</td></tr><tr><td colspan=2>Als achtergronds kleur (en nivo) wordt bij vertoning van een fijnstof grafiek het gezondheidsrisico weergegeven volgens de <a href='https://www.epa.gov/sites/production/files/2016-04/documents/2012_aqi_factsheet.pdf'>U.S. Environmental Protection Agency</a> PM<sub>2.5</sub> of PM<sub>10</sub> 24-uurs tabellen.<br />In de legendum kan door aanklikken de grafiek van een bepaalde lokatie aan- of uitgezet worden. Klik 'toon' aan voor het aan- of uitzetten van de betreffende grafiekweergave." .
        ($Mean ? 
        "<br />Bij 'regionale overzichts grafieken' worden er een grafiek getoond met de gemiddelde waarden samen met 50% en 90% spreidingsgrafiek. De individuele grafieken kunnen apart aan- of uitgezet worden door deze een voor een aan te klikken in de legendum. Tav de metingen die bovengemiddeld hoog zijn worden maximaal 3 grafieken direct zichtbaar gemaakt."
          : "").
        "<br />Zo nodig kan de legendum door met de linker muisknop op de plaats :: ingedrukt te houden, verplaatst worden.<br />De grafiek heeft de mogelijkheid om een bepaalde periode van de grafiek te laten zien. Met de 'slider' kan de periode vergroot, verkleind of verschoven worden.</td></tr></table><br />"
    }
}

sub InsertButtonStyle {
    state $once = 0;
    return '' if $once; $once = 1;
    return '' if index($buttons,',') < 1;
    return <<EOF ;
<!-- BUTTON STYLE -->
<style>
    .table-button {
        margin: 5px 0;
        border-radius: 20px;
        border: 2px solid #D0D0D0;
        border:1px solid #7d99ca; padding-top:8px;
        -webkit-border-radius: 20px;
        -moz-border-radius: 20px;
        font-size:9px;
        font-family:arial, helvetica, sans-serif;
        text-decoration:none; display:inline-block;
        text-shadow: -1px -1px 0 rgba(0,0,0,0.3);
        font-weight:normal;
        color: #FFFFFF;
        background-color: #A5B8DA;
        background-image: -webkit-gradient(linear, left top, left bottom, from(#A5B8DA), to(#7089B3));
        background-image: -webkit-linear-gradient(top, #A5B8DA, #7089B3);
        background-image: -moz-linear-gradient(top, #A5B8DA, #7089B3);
        background-image: -ms-linear-gradient(top, #A5B8DA, #7089B3);
        background-image: -o-linear-gradient(top, #A5B8DA, #7089B3);
        background-image: linear-gradient(to bottom, #A5B8DA, #7089B3);
        filter:progid:DXImageTransform.Microsoft.gradient(GradientType=0,startColorstr=#A5B8DA, endColorstr=#7089B3);
        -webkit-box-shadow: #B4B5B5 3px 3px 3px;
        -moz-box-shadow: #B4B5B5 3px 3px 3px;
        box-shadow: #B4B5B5 3px 3px 3px  ;
        height: 24px;
        cursor: pointer;
        width: 50px;
        position: relative;
        display: inline-block; user-select: none;
        -webkit-user-select: none;
        -ms-user-select: none;
        -moz-user-select: none;
    }
    .table-button button:hover{
        background-color: #d4dee1; background-image: -webkit-gradient(linear, left top, left bottom, from(#d4dee1), to(#a9c0c8));
        background-image: -webkit-linear-gradient(top, #d4dee1, #a9c0c8);
        background-image: -moz-linear-gradient(top, #d4dee1, #a9c0c8);
        background-image: -ms-linear-gradient(top, #d4dee1, #a9c0c8);
        background-image: -o-linear-gradient(top, #d4dee1, #a9c0c8);
        background-image: linear-gradient(to bottom, #d4dee1, #a9c0c8);
        filter:progid:DXImageTransform.Microsoft.gradient(GradientType=0,startColorstr=#d4dee1, endColorstr=#a9c0c8);
    }
    .table-button button {
        margin: 0px 0 0 -3px;
        cursor: pointer;
        outline: 0;
        display:block;
        position: absolute;
        left: 0; top: 0; border-radius: 100%;
        width: 32px; height: 32px;
        background-color: white;
        float: left;
        border: 2px solid #D0D0D0;
        transition: left 0.4s;
        font-size:10px;
        font-family:arial, helvetica, sans-serif;
        text-decoration:none; display:inline-block;
        text-shadow: -1px -1px 0 rgba(0,0,0,0.3);
        font-weight:bold;
        color: #3b5d9c;
        background-color: #f2f5f6;
        background-image: -webkit-gradient(linear, left top, left bottom, from(#f2f5f6), to(#c8d7dc));
        background-image: -webkit-linear-gradient(top, #f2f5f6, #c8d7dc);
        background-image: -moz-linear-gradient(top, #f2f5f6, #c8d7dc);
        background-image: -ms-linear-gradient(top, #f2f5f6, #c8d7dc);
        background-image: -o-linear-gradient(top, #f2f5f6, #c8d7dc);
        background-image: linear-gradient(to bottom, #f2f5f6, #c8d7dc);
        filter:progid:DXImageTransform.Microsoft.gradient(GradientType=0,startColorstr=#f2f5f6, endColorstr=#c8d7dc);
    }
    .table-button-selected {
        background-color: #83B152;
        border: 2px solid #7DA652;
    }
    .table-button-selected button {
        left: 26px; top: -2px; margin: 0;
        box-shadow: 0 0 4px rgba(0,0,0,0.1);
    }
    </style>
<!-- BUTTON STYLE -->
EOF
}

# insert button javascript handling for choice of table
sub InsertButtonJava {
    state $once = 0;
    return '' if $once; $once = 1;
    my (@but) = @_;
    return '' if $#but <= 0;
    my $tbl = '"C0table"';
    for( my $i =1; $i <= $#but; $i++) {
        $tbl .= ",\"C${i}table\"";
    }
    return '
// BUTTON JAVA
var index=0, messg=["' . join('", "',@but) . '"];
tables=['. $tbl . ',"null"];
function toggleButton(){
        var a=document.getElementById(tables[index++]);
        a.style.display="none";
        index=(index%messg.length);
        a=document.getElementById(tables[index]);
        a.style.display="block";
        var b=document.getElementById("tableButton");
        b.innerHTML=messg[(index+1)%messg.length]
}

$(document).on("click",".table-button",function(){
        $(this).toggleClass("table-button-selected");
        var a=document.getElementById(tables[index++]);
        a.style.display="none";
        index=(index%messg.length);
        a=document.getElementById(tables[index]);
        a.style.display="block";
        var b=document.getElementById("tableButton");
        b.innerHTML=messg[index]});
// BUTTON JAVA END
';
}

# insert the javascript part for an identified chart of graphs
sub InsertHighChartGraph {
    my ($nr,$units,$series,$yAxis) = @_;
    # $units =~ s/\|.*//; $units =~ s/\s//g; # first pollutant defines units
    # $units = 'pm10' if $units =~ /BdP/; # dflt ug/m3
    # $units = ConvertS2U( $units ); # get measurements units
    $series = $$series if ref($series) eq 'SCALAR';
    $yAxis = $$yAxis if ref($yAxis) eq 'SCALAR';
    $series = '
            { type: \'spline\',
              pointStart: BdPstart1,
              pointInterval: BdPunit1,
              name: BdPtitle1,
              data: BdPdata1,
              lineWidth: 1+1,
              visible: BdPvisible1,
              zIndex: 2,
              marker:{
                radius: 0
              }
            },
            ' if not $series;
    my $exportPrint = '';
    $exportPrint = 'exporting: {
            buttons: {
                contextButton: {
                    enabled: false
                },
                // exportButton: {
                //     text: \'Download\',
                //     menuItems: Highcharts.getOptions().exporting.buttons.contextButton.menuItems.splice(2)
                // },
                printButton: {
                    text: \'Print\',
                    onclick: function () {
                        this.print();
                    }
                }
            }
        },
        ' if $exportChart > 1;
    my $navigator = ''; $navigator = 'navigator: { margin: 55 },' if $barb;
    my $buttonPos = 180;
    my $legend = -25; $legend = -20 if not $barb;
    my $string = "
    \$('#${nr}SENSORS').highcharts('StockChart',{
            rangeSelector: {
            selected: 1,
            height: 40,
            buttonPosition: { y: $buttonPos, x: +5 },
            buttons: [
                { type: 'day', count: 1, text: 'dag',
                 // dataGrouping: { forced: true, units:[['day',[1]]]}
                },
                { type: 'day', count: 3, text: '3 dagen',
                 // dataGrouping: { forced: true, units:[['day',[1]]]}
                },
                { type: 'week', count: 1, text: 'week',
                 // dataGrouping: { forced: true, units:[['day',[1]]]}
                },
                { type: 'month', count: 1, text: 'maand',
                 // dataGrouping: { forced: true, units:[['day',[1]]]}
                },
            ],
            buttonTheme: { // styles for the buttons
                fill: 'none',
                stroke: 'none',
                'stroke-width': 0, r: 10, 'height': 12, y:-5,
                style: {
                    color: '#37508f',
                    fontWeight: 'bold',
                    fontSize: '60\%'
                },
                states: {
                    hover: {
                    },
                    select: {
                        fill: '#37508f',
                        style: {
                            color: 'white'
                        }
                    }
                    // disabled: { ... }
                }
            },
            inputPosition: { y: -42, x: +25 },
            inputBoxBorderColor: 'rgba(0,0,0,0)',
            inputBoxWidth: 65,
            inputBoxHeight: 15,
            inputDateFormat: '\%a \%e \%b \%H:\%M',
            inputEditDateFormat: '\%e \%b \%H:\%M',
            inputStyle: {
                color: '#37508f',
                fontWeight: 'bold',
                fontSize: '80\%'
            },
            labelStyle: {
                color: '#37508f',
                fontWeight: 'bold',
                fontSize: '80\%'
            },
            scrollbar: { enabled: false },
            inputEnabled: true
        },
        
          title: {
           text: ${nr}title,
            y: -5,
            align: 'center',
            style: {
                fontSize: '120\%',
                textShadow: '1px 1px 3px #777777',
                color: '#314877'
            }
          },
          subtitle: {
           text: ${nr}subtitle,
            y: -5+14,
            align: 'center',
            style: {
                fontSize: '110\%',
                textShadow: '1px 1px 3px #777777',
                color: '#314877'
            },
          },
        chart: {
            type: 'spline',
            borderRadius: 3,
            borderWidth: 1,
            backgroundColor: '#ffffff',
            borderColor: 'silver',
            shadow: true,
            margin: [28,6,7,6],
            spacing: [25,12,10,5],
            
        },
        legend: {
            layout: 'vertical',
            borderRadius: '3px',
            backgroundColor: 'rgba(196,206,228,0.1)',
            align: 'left',
            y: $legend, x: 10*$leftAxis,
            itemStyle: { fontSize: '75\%', color: '#314877' },
            itemHiddenStyle: { color: '#4a6396' },
            verticalAlign: 'center',
            maxHeight: 145,
            floating: true,
            draggable: true,
            title: {
                text: '::'
            },
            enabled: true,
            labelFormatter: function() { if( this.visible ) { return this.name ; } else { return this.name + ' (click voor toon graph)' }; }
        },
        credits: { enabled: false },
        tooltip: {
/*
formatter: function() {
          if(this.points[0].key < (this.points[0].series.xData.length -2)){
                return false;
          }
          var s = []; var t = new Date(this.x).toISOString().substr(11, 8);
          s.push(t);
          this.points.forEach(function(point) {
            s.push('<br><b>' + point.series.name + '</b>: ' + point.y);
          });

          return s;
        },
*/
            shared: true,
            split: false,
            valueDecimals: 0,
            dateTimeLabelFormats: {
                hour:\"\%a \%e \%b om \%H uur\",
                day: '\%e \%B \%Y'
            }
        },
        xAxis: {
            labels: {
                style:{fontSize:'100\%'},
                reserveSpace: false,
                y: -8,
                step: 1
            },
            tickInterval: 7 * 86400 * 1000, // per 6 hours or per 7 days
            type: 'datetime',
            tickPosition: \"outside\",
            tickLength: 5,
            minorTickInterval: 2,
            minorTickLength: 22,
            minorTickPosition: 'outside',
            // minorGridLineDashStyle: 'solid',
            lineWidth: 1,
            opposite: true,
            dateTimeLabelFormats: { day:\"\%a \%e \%b\", hour:\"\%Hh\" },
            crosshair: { dashStyle: 'dot' }
        },
        yAxis: [
            ${yAxis}
        ],
        plotOptions: {
            series: { groupPadding: 0, borderWidth: 0.3, pointPadding: 0.03 },
            column: { shadow: true, colorByPoint: true, showInLegend: false },
            spline: { shadow: false }
        },
        $navigator
        $exportPrint
        series: [ 
            ${series}
             ]
        }, function (chart) {
            \$('#update-legend').click(function () {
                chart.legend.toggle();
            });
    });
    ";
    if( $language =~ /UK/ ) {
        $string =~ s/dagen/days/;
        $string =~ s/dag/day/;
        $string =~ s/maand/month/;
        $string =~ s/toon/show/g;
    }
    return \$string;
}

use Graphics::ColorNames;
sub Col2Hex {
    my $col = shift; return "000000" if not defined $col;
    return $col if $col =~ /^#?[0-9a-f]{6}$/i;
    return "000000" if $col !~ /^[a-z]+$/i;
    my $po = new Graphics::ColorNames;
    return $po->hex($col);
}

sub Col2RGBA {
    my ($col,$trans) = @_;
    $trans = 1 if (not defined $trans) || (not length($trans));
    $trans = 1 if "$trans" !~ /^(0(\.[0-9]+)?|1)$/;
    $col = Col2Hex($col); $col =~ s/^#//;
    my @rgb = map $_, unpack "C*", pack "H*", $col;
    return sprintf("rgba(%s,%3.2f)", join(",",@rgb),$trans);
}
 
# mean &  stddev series
sub AvgStdSeries {
    my ($id, $sense, $color) =  @_;
    my %col = (
        'pm25' => '#bb0000', 'pm10' => '#8b4600', 'pm1' =>  '#bb7700',
        'o3' =>   '#003f8b', 'no2' =>  '#07008b', 'so2' =>  '#7e5000',
        'co' =>   '#006400', 'co2' =>  '#006437', 'roet' => '#373737',
        'aqi' =>  '#6a30f0', 'lki' =>  '#bb30f0',
    );
    if( not defined $color ) {
        $sense =~ s/[_\.\s]//g; 
        $color = '#222222';
        $color = $col{lc($sense)} if defined $col{lc($sense)};
    }
    my $series = '';
    my $suffix = ' ppm'; $suffix = ' \u00B5g/m\u00B3' if $sense =~ /^(pm|roet)/;
    $series .= "{
        type: 'spline',
        pointStart: Avg${id}Start, pointInterval: Avg${id}unit,
        name: Avg${id}Title + 'gemiddelde, spreiding 50%-90%',
        data: Avg${id}data,
        color: '$color',
        shadow: { color: '$color',
            width: 5, offsetX: 0, offsetY: 0
          },
        zIndex: 10,
        lineWidth: 1+1,
        visible: false,
        tooltip: { valueSuffix: '$suffix', radius: 1+1 },
        showInNavigator: true,
        marker:{
            fillColor: '$color',
            radius: 1+1
          },
        pointPlacement: 'between'
      },
     ";
     for( my $r = 1; $r <= 2; $r++ ){
      for( my $s = 1; $s <= 2; $s++) {
        $series .= "{
        type: 'areaspline',
        pointStart: Avg${id}Start, pointInterval: Avg${id}unit,
        name: ";
        $series .= sprintf("Avg${id}Title + 'std deviatie %s %d%%',\n",
                        ($s == 1? 'max' : 'min'), 10 + $r*40);
        # $series .= sprintf("        zIndex: %d,",-2*$r - 1 + $s);
        $series .= "\n\tzIndex: -4," if ($s == 1) && ($r == 1);
        $series .= "\n\tzIndex: -3," if ($s == 2) && ($r == 1);
        $series .= "\n\tzIndex: -2," if ($s == 1) && ($r == 2);
        $series .= "\n\tzIndex: -1," if ($s == 2) && ($r == 2);
        $series .= "
        data: Range${id}Area${r}${s},
        tooltip: { valueSuffix: '$suffix', radius: 1 },
        lineWidth: 0,
        yAxis: 0,
        linkedTo: 0,
        fillOpacity: 0.9,
        visible: true,
        showInLegend: false,
        showInNavigator: true,
        selected: false,
        marker:{
            enabled: false,
            fillColor: '#ffffff',
            radius: 0
          },
        pointPlacement: 'between',
        fillColor: ";
        $series .= "'#e1e2e5'," if ($s == 2) && ($r == 1); # #e5cacb
        $series .= "'#e5fae5'," if ($s == 2) && ($r == 2);
        $series .= "'rgba(187,0,0,0.30)'," if ($s == 1) && ($r == 1);
        $series .= "'rgba(187,0,0,0.10)'," if ($s == 1) && ($r == 2);
        $series .= sprintf("\n\tcolor: '%s'\n    },\n", Col2RGBA($color,0.40-$r*0.10));
      }
    }

    return $series;
}

sub CompareSeries {
    # if( $a < $b ) { return -1; }
    # elsif ( $a == $b ,) { return 0; }
    # else { return 1; }
    if( ($a->{table} =~ /_/) && ($b->{table} =~ /_/) ){
        return $a->{street} cmp $b->{street};
    }
    elsif( $b->{table} =~ /_/ ) { return 1; }
    elsif( $a->{table} =~ /_/ ) { return -1; }
    else { $a->{table} cmp $b->{table} }
}

# generate one chart for a set of series
sub ChartSerie {
    my ($StNr, $data) = @_;
    my $id = "C$StNr";
    # sort it...
    # my @dat = sort CompareSeries @{$data};
    my $series = ''; $series = AvgStdSeries($StNr,$data->[0]{sense}) if $Mean;
    # seems there is a time shift of 3 hours in DLT MET with official stations timestamp */
    for( my $i = 0; $i <= $#{$data}; $i++ ){
        my $ugm3 = '\\u00B5g/m\\u00B3';
        my $visible = 0;
        $visible = 1 if (defined $data->[$i]{visible}) && $data->[$i]{visible};
        if( $Mean ) { $visible = 1 if $data->[$i]{table} !~ /_/; }
        elsif( $data->[$i]{table} =~ /_/ ){ $visible = 1; }
        # pm2.5 pollutants are all visible
        # graph not visible if not local sensor kit (has _ in name)
        my $corr = '';
        if( ($data->[$i]{sense} =~ /pm_?(10|25)/i) && (defined $data->[$i]{CorrectME}) ) {
            my $name = $data->[$i]{CorrectME}; $name =~ s/.*_//g;
            # for now only rv TO DO: extent this with a row of indicators!
            if( $data->[$i]{sense} =~ /pm_?(10|25)/i ) {
                $series .= "\n\t{";
                $series .= sprintf("\n\tpointStart: ${id}start%d, pointInterval: ${id}unit%d,",$i,$i);
                $series .= "\n\'ttype: 'spLine', /* $data->[$i]{table} */";
                $series .= sprintf("\n\tname: ${id}title%d + ' gecorrigeerd',",$i);
                $series .= sprintf("\n\tdata: correctPMs('%s',${id}data%d,humrv%s),",$data->[$i]{sense}, $i, $name);
                $series .= sprintf("\n\tlineWidth: 1+%d", $i);
                $series .= sprintf("\n\tvisible: %s,",($visible?'true':'false'));
                if ( $Mean && ($data->[$i]{table} !~ /_/) ) {
                    $series .= "\n\tlineWidth: 2,";
                }
                $series .= sprintf("\n\tzIndex: %d,",$i+1);
                $series .= sprintf("\n\ttooltip: { valueSuffix: ' %s' },",($data->[$i]{pol}?ConvertS2U($data->[$i]{pol}):$ugm3));
                # $series .= sprintf("\n\tyAxis: %d,", ($data->[$i]{table} =~ /_/?0:1));
                $series .= sprintf("\n\tyAxis: %d,", $i);
                $series .= "\n\tpointPlacement: 'between',";
                $series .= sprintf("\n\t marker:{ radius: 1+%d }",
                    ($data->[$i]{table} =~ /_/?1:0) );
                $series .= "\n\t}\n";
            }
            if( $language =~ /UK/ ) {
                $corr = ' uncorrected';
                $series =~ s/gecorrigeerd/corrected/g;
            } else {
                $corr = ' ongecorrigeerd';
            }
        }

        my $datavar = sprintf("${id}data%d", $i);
        if( ($data->[$i]{sense} =~ /(rv)$/i) && (defined $RVstations{$data->[$i]{table}}) ){
            $datavar = $data->[$i]{table}; $datavar =~ s/.*_//g;
            $datavar = "humrv$datavar";
        }
        $series .= "\n\t{";
        $series .= "\n\ttype: 'spline', /* $data->[$i]{table} */" if $data->[$i]{sense} !~ /(rain|wind)/;
        $series .= "\n\ttype: 'area'," if $data->[$i]{sense} =~ /rain/;
        $series .= "\n\ttype: 'windbarb',\n\tid: 'windbarbs'," if $data->[$i]{sense} =~ /wind/;
        $series .= sprintf("\n\tpointStart: ${id}start%d, pointInterval: ${id}unit%d,",$i, $i);
        $series .= sprintf("\n\tname: ${id}title%d + '$corr',",$i);
        $series .= "\n\tdata: $datavar,";
        $series .= "\n\tdashStyle: 'shortdot'," if $data->[$i]{sense} =~ /luchtdruk/;
        $series .= "\n\tdashStyle: 'shortdash'," if $data->[$i]{sense} =~ /rv$/;
        $series .= "\n\tcolor: '#739fe8'," if $data->[$i]{sense} =~ /rv$/;
        $series .= "\n\tcolor: '#37dcb4'," if $data->[$i]{sense} =~ /luchtdruk/;
        my @c = ('5a005a','2e0052','001f47','164700','6b2b00'); # color selection for official station series
        $series .= sprintf("\n\tcolor: '#%s',", $c[$i % $#c]) if $data->[$i]{table} !~ /_/;
        if ($data->[$i]{sense} =~ /rain/ ) {
            $series .= "\n\tzIndex: 0,";
        } elsif ( $data->[$i]{sense} =~ /(luchtdruk|rv)/ ) {
            $series .= "\n\tzIndex: 1,";
        } else {
            $series .= sprintf("\n\tzIndex: %d,", $i+2);
        }
        if( $data->[$i]{sense} =~ /wind/ ) {
            $series .= "\n\tlineWidth: 1.5,";
            $series .= "\n\tcolor: '#531257',\n\tvectorlength: 13,";
            $series .= "\n\tyOffset: 171,\n\tshowInLegend: false,";
            $series .= "\n\ttooltip: { valueSuffix: ' m/sec' },";
        } else {
            $series .= sprintf("\n\tlineWidth: 1+%d,",(($data->[$i]{table} =~ /_/) ? 1:0));
            if ( $Mean && ($data->[$i]{table} !~ /_/) ) {
                $series .= "\n\tlineWidth: 2,";
            }
            $series .= sprintf("\n\tvisible: %s,",($visible?'true':'false'));
            if ( $Mean ) {
                $series .= sprintf("\n\tyAxis: %d,",($data->[$i]{table} =~ /_/?6:7));
            } else {
                $series .= sprintf("\n\tyAxis: %d,",($data->[$i]{table} =~ /_/?0:1));
            }
            #$series .= sprintf("\n\tyAxis: %d,",$i);
            $series .= sprintf("\n\ttooltip: { valueSuffix: ' %s' },",
                (defined $data->[$i]{pol}?ConvertS2U($data->[$i]{pol}):$ugm3));
            $series .= sprintf("\n\tmarker:{ radius: 1+%d },",
                ($data->[$i]{table} =~ /_/?1:0) );
            $series .= "\n\tpointPlacement: 'between',";
            if( $data->[$i]{sense} !~ /(pm[12])/ ) {
                $series .= "\n\tshowInNavigator: true,";
            }
            elsif( not $Mean ) {
                $series .= sprintf("\n\tshowInNavigator: %s,",($visible?'true':'false'));
            }
            # $series .= "\n\tshowInNavigator: true," if $data->[$i]{sense} =~ /(pm10|rv|temp)/;
        }
        if ( $data->[$i]{sense} =~ /rain/ ) {
            $series .= "\n\tcolor: Highcharts.color('#0264c9')
                .setOpacity(0.65).get(),
            fillColor: {
              linearGradient: { x1: 0, x2: 0, y1: 0, y2: 1 },
              stops: [
                [0, Highcharts.color('#0264c9')
                        .setOpacity(0.55).get()
                ],
                [1, Highcharts.color('#0264c9')
                        .setOpacity(0.10).get()
                ]
              ]
          },";
        }
        $series .= "\n\tcolor: '#FF3333', negativeColor: '#48AFE8'," if $data->[$i]{sense} =~ /temp/;
        $series .= "\n\t},\n";
    }  # end of for loop series
    return \$series;
}

# create a new yaxis configuration or return old one
my %yAxis = ();
sub MyLength {
    my ($str) = @_;
    $str =~ s/\\u[0-9]{4}/u/g;
    return length($str);
}

sub newYaxis {
    my ($nr,$units,$bands) = @_;
    state $lastLoc = -1; # right inner, left inner, right out, left out, invis
    $lastLoc = -1 if not $nr; %yAxis = () if not $nr; # reset
    my $Tbands = ''; # $Tbands = 'B_' if $bands;
    #    {color:"rgba(1,109,255,0.1)", from:0, to:20, label:{text:"goed",rotation:-90,style:{color:"rgba(1,109,255,0.6)",fontWeight:"bold",fontSize:"75%"},x:15} },
    #    {color:"rgba(2,216,255,0.1)",from:20,to:40,label:{text:"matig",rotation:-90,style:{color:"rgba(2,216,255,0.95)",fontWeight:"bold",fontSize:"75%"},x:15}},
    #    {color:"rgba(54,255,0,0.1)",from:40,to:60,label:{text:"opgepast",rotation:0,style:{color:"rgba(54,255,0,0.6)",fontWeight:"bold",fontSize:"75%"},x:15}},
    #    {color:"rgba(255,204,0,0.1)",from:60,to:80,label:{text:"ongezond",rotation:0,style:{color:"rgba(255,204,0,0.6)",fontWeight:"bold",fontSize:"75%"},x:15}},
    #    {color:"rgba(253,72,1,0.1)",from:80,to:100,label:{text:"gevaarlijk",rotation:0,style:{color:"rgba(253,72,1,0.6)",fontWeight:"bold",fontSize:"75%"},x:15}},
    #    {color:"rgba(171,3,188,0.1)",from:100,to:500,label:{text:"hachelijk",rotation:0,style:{color:"rgba(171,3,188,0.6)",fontWeight:"bold",fontSize:"75%"},x:15}}
    if( $bands =~ /pm(25|2.5)/i) {
    $Tbands = '
      /* U.S. Environmental Protection Agency 24-hour PM2.5 color scheme https://www.epa.gov/sites/production/files/2016-04/documents/2012_aqi_factsheet.pdf */
      plotBands:[
        {color:"rgba(0,204,0,0.1)", from:0, to:12, label:{text:"goed",rotation:-90,style:{color:"rgba(0,204,0,0.6)",fontWeight:"bold",fontSize:"55%"},x:15} },
        {color:"rgba(255,255,0,0.1)",from:12,to:35.5,label:{text:"matig",rotation:-90,style:{color:"rgba(220,192,1,0.95)",fontWeight:"bold",fontSize:"55%"},x:15}},
        {color:"rgba(235,138,20,0.1)",from:35.5,to:55.5,label:{text:"opgepast",rotation:0,style:{color:"rgba(235,138,20,0.6)",fontWeight:"bold",fontSize:"55%"},x:15}},
        {color:"rgba(255,0,0,0.1)",from:55.5,to:150.5,label:{text:"ongezond",rotation:0,style:{color:"rgba(255,0,0,0.6)",fontWeight:"bold",fontSize:"55%"},x:15}},
        {color:"rgba(161,0,73,0.1)",from:150.5,to:250.5,label:{text:"gevaarlijk",rotation:0,style:{color:"rgba(161,0,73,0.6)",fontWeight:"bold",fontSize:"55%"},x:15}},
        {color:"rgba(126,0,36,0.1)",from:250.5,to:500,label:{text:"hachelijk",rotation:0,style:{color:"rgba(126,0,36,0.6)",fontWeight:"bold",fontSize:"55%"},x:15}}
     ],
      ' ; }
    elsif( $bands =~ /pm10/i ) {
      $Tbands = '
        /* U.S. Environmental Protection Agency 24-hour PM10 color scheme https://www.leg.state.mn.us/docs/2015/other/150681/PFEISref_2/USEPA%202004.pdf */
    plotBands:[
        {color:"rgba(0,204,0,0.1)", from:0, to:54, label:{text:"goed",rotation:-90,style:{color:"rgba(0,204,0,0.6)",fontWeight:"bold",fontSize:"55%"},x:15} },
        {color:"rgba(255,255,0,0.1)",from:54,to:154,label:{text:"matig",rotation:-90,style:{color:"rgba(220,192,1,0.95)",fontWeight:"bold",fontSize:"55%"},x:15}},
        {color:"rgba(235,138,20,0.1)",from:154,to:254,label:{text:"opgepast",rotation:0,style:{color:"rgba(235,138,20,0.6)",fontWeight:"bold",fontSize:"55%"},x:15}},
        {color:"rgba(255,0,0,0.1)",from:254,to:354,label:{text:"ongezond",rotation:0,style:{color:"rgba(255,0,0,0.6)",fontWeight:"bold",fontSize:"55%"},x:15}},
        {color:"rgba(161,0,73,0.1)",from:354,to:425,label:{text:"gevaarlijk",rotation:0,style:{color:"rgba(161,0,73,0.6)",fontWeight:"bold",fontSize:"55%"},x:15}},
        {color:"rgba(126,0,36,0.1)",from:425,to:600,label:{text:"hachelijk",rotation:0,style:{color:"rgba(126,0,36,0.6)",fontWeight:"bold",fontSize:"55%"},x:15}}
     ],
    '; }
    return "    { 
            visible: false,
            linkedTo: $yAxis{$Tbands.$units}
            },\n" if defined $yAxis{$Tbands.$units} ;
    return " {},\n" if $units =~ /(weerhaak|barb)/; # wind barb
    my $plotType;
    $plotType = "
            plotLines: [{ // zero plane
                value: 0,
                color: '#BBBBBB',
                width: 1,
                zIndex: 2
            }]," ; # if not $Tbands;
    $lastLoc++;
    my $opposite = 'true';
    $opposite = 'false' if ($lastLoc % 2);
    my $visible = 'true';
    $visible = 'false' if $lastLoc > 3; # for now no more as 4 visible axes
    my $textAlign = 'left';
    # $textAlign = 'center' if ($lastLoc % 2);
    my $rotation = '0' ; $rotation = '270' if MyLength($units) >= 2;
    my $x = -10; $x = -15 if $lastLoc > 0;
    $x = -$x if $opposite eq 'true';
    my $lx = -15; # label x offset
    $lx = 5 if $opposite eq 'true';
    if ($lastLoc > 1) {
        $lx = -18; $lx = 0 if $opposite eq 'true';
        $x = -24; $x = 22 if $opposite eq 'true';
    }
    my $offset = int(($lastLoc+1)/2 + 0.5);
    my $tickInterval = 'tickInterval: 10,';
    my $color = '';
    my $addOn = '';
    if( $units =~ /^\\u2103$/ ) { # temp
        $tickInterval = "tickInterval:2,";
        $addOn .= 'allowDecimals: true,';
        $color = "color: '#FF3333'";
    } elsif( $units =~ /^\\u0025$/ ) { # rv
        $addOn .= 'floor: 0, ceil: 100, max: 100,';
        $color = "color: '#739fe8'";
    } elsif( $units =~ /^mm\/h/ ) { # rain
        $color = "color: '#0264c9'"
    } elsif( $units =~ /hPa/ ) { # luchtdruk
        $color = "color: '#37dcb4'";
    }
    $addOn .= 'allowDecimals: false,' if $units !~ /^\\u2103$/;
    $leftAxis += $lastLoc % 2;
    my $Max = ''; # $Max = "\n            max: 65," if $Mean;
    my $newY = "
          { title: {
                text: '$units',
                offset: -10,
                align: 'high',
                rotation: $rotation,
                style: {
                    fontSize: '10px', $color
                },
                textAlign: '$textAlign',
                x: $x, y: -5,
            },
            labels: {
                format: \"{value}\",
                align: '$textAlign',
                style: {
                    fontSize: '8px', $color
                },
                x: $lx,
            },
            $Tbands
            $plotType
            $addOn
            offset: -15*$offset,
            showLastLabel: false,$Max
            maxPadding: 0.3,
            opposite: $opposite,
            $tickInterval
            visible: $visible,
            gridLineColor: (Highcharts.theme && Highcharts.theme.background2) || '#F0F0F0'
          },\n";
    $yAxis{$Tbands.$units} = $nr;
    return $newY;
}

# generate yAxis for a set of series
sub ChartyAxis {
    my ($data, $bands) = @_; $yAxis = '';
    $leftAxis = 0;  # reset nr left axis spacing
    for( my $i = 0; $i <= $#{$data}; $i++) {
        my $units = ConvertS2U($data->[$i]{pol});
        # $yAxis .= newYaxis($i, $units, (($data->[$i]{table} !~ /_/)? $bands : ''));
        $yAxis .= newYaxis($i, $units, $data->[$i]{sense});
        if ( ($i == 0) && ($Mean) ) {
            for( my $i = 0; $i < 5; $i++ ) {
                $yAxis .= "    { visible: true, linkedTo: 0 },\n";
            }
        }
    }
    return \$yAxis;
}

# generate plotBands none,EU-WHO or LKI
# boundaries are for PM2.5  [from,to,quality mark]
my %bands = (
    EU => [
        [0,20,'EU norm, PM\u2081\u2080 fase 2'],
        [20,25,'WHO norm, PM\u2082.\u2085'],
        [25,40,'EU norm, PM\u2081\u2080 jaargem.'],
        [40,50,'EU norm, PM\u2081\u2080 daggemiddelde'],
        [50,200,''],
        ],
    LKI => [
        [0,20,'LKI Index PM\u2082.\u2085 goed'],
        [20,50,'LKI Index PM\u2082.\u2085 matig'],
        [50,89,'LKI Index PM\u2082.\u2085 ongezond'],
        [89,200,'LKI Index PM\u2082.\u2085 slecht'],
        ],
    AQI => [
        [0,12,'AQI Index PM\u2082.\u2085 goed'],
        [12,36,'AQI Index PM\u2082.\u2085 matig'],
        [36,56,'AQI Index PM\u2082.\u2085 opgepast'],
        [56,150,'AQI Index PM\u2082.\u2085 ongezond'],
        [150,200,'AQI Index PM\u2082.\u2085 gevaarlijk'],
        ],
    AQI_LKI => [
        [0,12,'AQI Index PM\u2082.\u2085 goed'],
        [12,20,'AQI Index PM\u2082.\u2085 matig'],
        [20,36,'LKI Index PM\u2082.\u2085 matig'],
        [36,50,'AQI Index PM\u2082.\u2085 opgepast'],
        [50,56,'LKI Index PM\u2082.\u2085 ongezond'],
        [56,89,'AQI Index PM\u2082.\u2085 ongezond'],
        [89,150,'LKI Index PM\u2082.\u2085 slecht'],
        [150,200,'AQI Index PM\u2082.\u2085 gevaarlijk'],
        ],
);
        
sub plotBands {
    my $NRM = shift;
    return '' if not $ShowBands;  # dflt turned off, deprecated, display problem
    return '' if (not $NRM) || ($NRM =~ /none/);
    print STDERR "Unknown quality level identifier $NRM\n" if not defined $bands{$NRM};
    return '
                {color:"rgba(0, 32, 197, 0.05)",from: 0,to:19.5 },
                {color:"rgba(244, 230, 69, 0.15)",from: 20 ,to: 25 },
                {color:"rgba(254, 118, 38, 0.15)",from: 25.5,to: 40},
                {color:"rgba(220, 6, 16, 0.15)",from: 40.5,to:50 },
                {color:"rgba(162,23,148,0.15)",from:50.5,to:200}
            ' if not defined $bands{$NRM};
    my @colors = (
        # maybe we shoud use the colors as defined by the ref doc, see AQI.pl
        ['0, 32, 197, 0.05','0, 32, 197, 0.45'],
        ['244, 230, 69, 0.15','175, 158, 44, 1'], # yellow text needs more contrast
        ['254, 118, 38, 0.15','254, 118, 38, 0.45'],
        ['220, 6, 16, 0.15','220, 6, 16, 0.45'],
        ['162,23,148,0.15','162,23,148,0.45'],
        ['162,23,148,0.15','162,23,148,0.45'],
        ['162,23,148,0.15','162,23,148,0.45'],
        ['162,23,148,0.15','162,23,148,0.45'],
    );
    my $template = "
        {color:'rgba(COLB)',from:FROM,to:TO,
            label:{
                text:'TEXT',
                rotation:0,
                align: 'center',
                verticalAlign: 'top',
                style:{
                    color:'rgba(COLT)',
                    fontWeight:'bold',
                    fontSize: '80%',
                },
                y: 10,
            }
        },
        ";
    my @levels = @{$bands{$NRM}}; my $rslt = '';
    for( my $i = 0; $i <= $#levels; $i++ ) {
        my $strg = $template; my ($from,$to,$text) = @{$levels[$i]};
        last if $i > $#colors;
        my $colb = $colors[$i][0]; my $colt = $colors[$i][1];
        $to -= 0.30; # keep a white line
        $strg =~ s/FROM/$from/m; $strg =~ s/TO/$to/m;
        $strg =~ s/COLB/$colb/m; $strg =~ s/COLT/$colt/m;
        $strg =~ s/TEXT/$text/m;
        $rslt .= $strg;
    }
    return $rslt;
}

# compress JS script string
sub JScompress {
    my $string = shift; my $rslt = '';
    return ${$string} if $debug;
    return '' if not ${$string};
    my $JSin;
    open $JSin,  ">/var/tmp/VW2017_IN.js" || return ${$string};
    print $JSin ${$string}; close $JSin;
    local $/;
    if( not -x "/usr/bin/yui-compressor" ) {
        print STDERR "WARNING yui-compressor is not installed. No JS compression.\n";
        return ${$string};
    }
    open $JSin, "/usr/bin/yui-compressor --type js /var/tmp/VW2017_IN.js 2>/dev/null |" || return ${$string};
    
    $rslt = <$JSin>;
    if ( not $rslt ) {
        print STDERR "WARNING yui-compressor failed. JS data saved in /var/tmp/VW2017_IN.js\n";
        print STDERR "No JS compression is done.\n";
        return ${$string};
    }
    close $JSin;
    system("/bin/rm -f /var/tmp/VW2017_IN.js");
    return $rslt;
}

# some help text if PM values are corrected
sub correctPMtext {
    my $txt;
    if( $language =~ /UK/ ) { $txt = "
<p>The timestamp of measurements of some stations may have been shifted. This is corrected in the graphs.</p>
<p>Note: Together with the national health research center RIVM we look into improvements for measuring fine dust particles (Particle Matter or PM).
Experiments show a good relation to the refence sensor equipment of RIVM if the correction based on the influence of rel. humidity.
"       ;
    }
    else { $txt = "
<p>Het blijkt dat de metingen van enkele meetstations om een of andere reden verschoven zijn in de tijd. Hiervoor is zonodig een tijdscorrectie toegepast.</p>
<p>Samen met het RIVM wordt gekeken of de procedures voor het meten van PM fijnstof waarden verbeterd kunnen worden.
Als experiment worden de PM<sub>1</sub>, PM<sub>2.5</sub> en PM<sub>10</sub> fijnstof waarden gecorrigeerd door de rel. vochtigheidsmeting er in te betrekken.
Door toepassing van deze correcties worden de lokale metingen redelijk tot goed vergelijkbaar met de referentie fijnstof metingen van een RIVM/PLIM meetstation in de buurt.
"       ;
    }
    return $txt if not $correctPM;
    if( $language =~ /UK/ ) {
    return $txt . "
<br />The chart will also be able to show the uncorrected values as well the graphs of PM<sub>10</sub> and PM<sub>2.5</sub> of a nearby reference station.</p>
    ";
    } else {
    return $txt . "
<br />Door te clicken met de muis op 'ongecorrigeerd' worden ook de ongecorrigeerde waarden in de grafiek getoond.
</p>
    ";
    }
}
    
my $OUT;
sub MyPrint {
    my $inscript = shift; my $strg = shift;
    state $JS = '';
    $strg = $$strg if ref($strg) eq 'SCALAR';
    return 0 if not $strg;
    if ( $debug ) {
        print $OUT $strg;
    } elsif ( $inscript ) {
        $JS .= $strg;
    } else {
        if ( $JS ) {
            print $OUT JScompress(\$JS);
            $JS = '';
        }
        print $OUT $strg;
    }
}

use Statistics::Basic qw(:all nofill);

# return average distance between 2 graphs
# start in units
sub AverageDist {
    my ($strt1,$graph1,$strt2,$graph2) = @_;
    return AverageDist($strt2,$graph2,$strt1,$graph1) if $strt1 > $strt2;
    my @vec1 = ();
    for( my $i = 0; $i <= $#{$graph1}; $i++) {
        next if not defined $graph1->[$i];
        next if $graph1->[$i] =~ /null/;
        my $j =  $i-($strt2-$strt1);
        next if $j < 0;
        last if $j > $#{$graph2};
        next if not defined $graph2->[$j];
        next if $graph2->[$j] =~ /null/;
        push(@vec1, $graph2->[$j]-$graph1->[$i]);
    }
    return 0 if $#vec1 <= 0;
    my $vec  = vector(@vec1);
    # print("Distance avg-graph: $vec, ");
    $vec = avg($vec); $vec =~ s/,/./;
    return $vec;
}

# return hash with average and stddev per time unit when more as 5 data sequences
# synchronize start times, check on equal time units and sense type
sub GetAvgStdDev {
    my $data = shift; $data = $$data;
    return undef if not $Mean;  # less as 5 locations no average show
    return undef if not defined $$data[0];
    my $sense =  ${$data}[0]{sense}; my $unit = ${$data}[0]{unit};
    my $Tmin = ${$data}[0]{first}; my $Tmax = $Tmin; my $Scnt = -1; my $Dcnt = -1;
    for( my $i = 0; $i < $#{$data}; $i++) {
        # print("nr $i, sense ${$data}[$i]{sense}, first ${$data}[$i]{first}, last ${$data}[$i]{last}, unit ${$data}[$i]{unit}\n");
        if( (${$data}[$i]{sense} !~ /$sense/) || (${$data}[$i]{unit} != $unit ) ){
            print STDERR ("Found different type of sensor or time unit. Skip average/stddev graphs.\n");
            print STDERR ("nr $i, sense ${$data}[$i]{sense}, first ${$data}[$i]{first}, last ${$data}[$i]{last}, unit ${$data}[$i]{unit}\n");
            return undef;
        }
        $Tmin = ${$data}[$i]{first} if ${$data}[$i]{first} < $Tmin;
        $Tmax = ${$data}[$i]{first} if ${$data}[$i]{first} > $Tmax;
    }
    my @row = (); my @cols = ();
    for( my $i = 0; $i < $#{$data}; $i++) {
        next if ${$data}[$i]{table} =~ /$AvgAvoid/; 
        next if ${$data}[$i]{table} !~ /_/ ; $Scnt++;
        my $col = ${$data}[$i]{data}; $col =~ s/[\[\]]//g; $col =~ s/null//g;
        my $free = int((${$data}[$i]{first} - $Tmin) /  $unit)-1;
        $cols[$i] = ();
        $#{$cols[$i]} = int((${$data}[$i]{first} - $Tmin) /  $unit)-1;
        push(@{$cols[$i]},split(/,/,$col));
        $Dcnt = $#{$cols[$i]} if $#{$cols[$i]} >  $Dcnt;
    }
    for( my $i = 0; $i <= $Dcnt; $i++) {
        for( my $j = 0; $j <= $Scnt; $j++) {
            $row[$i][$j] = $cols[$j][$i] if (defined $cols[$j][$i]) && ($cols[$j][$i] =~ /^[0-9\.]+$/);
        }
    }
    my %rslt = (
        'sense' => ${$data}[0]{sense},
        'first' => $Tmin,
        'last' => $Tmax,
        'unit' => $unit,
        'average' => '[]',
        'stddev'  => '[]',
        'area1'   => '[]',
        'area2'   => '[]',
    ); 
    $rslt{sense} =~ s/pm25/pm2.5/; $rslt{sense} = lc($rslt{sense});
    my @avg; my @dev; my @ext = ();
    # my @area1 = (); my @area2 = ();
    for( my $i = 0; $i < $#row; $i++) {
        my @tmp = (); my @ind = ();
        for( my $j = 0; $j <= $#{$row[$i]}; $j++) {
            push(@tmp,$row[$i][$j]) if (defined $row[$i][$j]) && ($row[$i][$j] > 0);
            if( (defined $row[$i][$j]) && ($row[$i][$j] > 0)) { push(@ind,$row[$i][$j]); }
            else { push(@ind,0); }
        }
        my $average = 'null'; my $stddev = 'null';
        if( $#tmp >= 1 ) {
            my $vec  = vector(@tmp);
            # print("Vector $i: $vec, ");
            $average = avg($vec); $average =~ s/,/./;
            $stddev  = stddev($vec); $stddev =~ s/,/./;
            # print("Vector avg $i: $average and $stddev\n");
        }
        push(@avg,$average); push(@dev,$stddev);
    }
    $rslt{average} = '['.join(',',@avg).']'; $rslt{stddev} = '['.join(',',@dev).']';
    my @distances = ();
    for( my $i = 0; $i < $#{$data}; $i++) { # get distances for graph to average graphs
        next if ${$data}[$i]{table} =~ /$AvgAvoid/; 
        next if ${$data}[$i]{table} !~ /_/;
        my $str = ${$data}[$i]{data}; $str =~ s/[\[\]]//g;
        my @data = split(/, */,$str);
        $data->[$i]{distance} = AverageDist(int($rslt{first}/$rslt{unit}),\@avg,int(${$data}[$i]{first}/${$data}[$i]{unit}),\@data);
        push(@distances,$data->[$i]{distance});
        ${$data}[$i]{visible} = FALSE;
    }
    @distances = sort { $a <=> $b } @distances;
    for( my $i = 1; $i >= 0; $i-- ) {
        next if not defined $distances[$#distances-$i];
        $rslt{distance} = $distances[$#distances-$i]; last;
    }
    if( defined $rslt{distance} ) { # turn visibility on for graphs exceeding average
        for( my $i = 0; $i <= $#{$data}; $i++ ) {
            next if not defined $data->[$i]{distance};
            ${$data}[$i]{visible} = TRUE if $data->[$i]{distance} >= $rslt{distance};
        }
    }
    return \%rslt;
}

sub Generate {
    $#_ -= 1 if not $_[$#_]; # $reference may be empty
    $_[$#_+1] = $meteo if $meteo;
    my @stations = uniq @_; my @DATA;
    my $IN;
    # strings to be used in generated HTML code
    my @Mlbls; my @Slbls; my $Olbls; my $first = 0; my $last = 0;
    my @BUTTONS = split(/,\s*/,$buttons);
    my @POLLUTANTS = split(/,\s*/, $pollutants);
    if( $#BUTTONS != $#POLLUTANTS ) {
        print STDERR "number of buttons defined does not correspond with number of pollutant expressions\n";
        return 1;
    }
    for ( my $i=0; $i <= $#BUTTONS; $i++ ) {
        # convert user provided names to reg. exp and button names
        $BUTTONS[$i] =~ s/[_\|].*//; # allow one name
        $BUTTONS[$i] =~ s/pm/PM/;
        $BUTTONS[$i] =~ s/PM([0-9])([1-9])/PM$1.$2/;
        $BUTTONS[$i] =~ s/^(.{1,5}).*/$1/;  # max 5 chars as button name
        $BUTTONS[$i] =~ s/\s//g;
        $BUTTONS[$i] =~ s/[^a-zA-Z0-9\.]//g;
        $POLLUTANTS[$i] =~ s/PM/pm/; $POLLUTANTS[$i] =~ s/\s//g;
        $POLLUTANTS[$i] =~ s/pm(10|25)/pm$1|pm_$1/g;
        $POLLUTANTS[$i] =~ s/temp/temp|dtemp|stemp/;  # SHT, DHT
        $POLLUTANTS[$i] =~ s/(.*)/($1)/;  # we have now a reg. expression

        my $data = Collect_data($POLLUTANTS[$i],@stations);
        if( $#{$data} <= 2 ) {
            printf STDERR ("Unable to find chart data for %s stations, pollutants: %s\n",
                join(', ', @stations), $POLLUTANTS[$i]);
            return 0;
        }
        # this may be incorrect
        
        my $tt = pop @{$data};
        $last = $first = $tt if not $last;
        $last = $tt if $tt > $last;
        $tt = pop @{$data}; $first = $tt if $tt < $first;
        printf STDERR ("Found data for %d sensors for button %s with pollutants %s.\n", $#{$data}+1, $BUTTONS[$i],$POLLUTANTS[$i])
            if $verbose;
        $DATA[$i] = $data;
    }
    $last = strftime("%a %e %b %Y %H:%M", localtime($last));
    $first = strftime("%a %e %b %Y", localtime($first));
    my $prev = 'X';
    my $tshift = 0;  # we try to start all plot intervals on same minute
    my $nrLegends = 0;
    # so the tooltip values will be shown in parallel
    # the stations have avg values per hour. It is unclear from the documentation
    # if the given value is of the previous hour, or that hour.
    # The database thinks the time is half of the hour: 30 minute boundary.
    # the shift is done on the last start time provided. Usualy a station.
    for( my $j = 0; $j <= $#DATA; $j++ ) {
      $Mlbls[$j] = $Slbls[$j] = $Olbls[$j] = '';
      my $data = $DATA[$j];
      $nrLegends = $#{$data} if $#{$data} > $nrLegends; 
      for( my $i = 0; $i <= $#{$data}; $i++ ){    # collect all locations
        $tshift = $data->[0]{first}%3600 if $i == 0;
        $data->[$i]{first} -= ($data->[$i]{first}%3600) - $tshift; # shift graph
        my $loc = $data->[$i]{location}; # $loc =~ s/^(.*)\s*,\s*(.*)$/$1 \($2\)/;
        my $S = $data->[$i]{pol}; $S = uc($S) if $S !~ /(w[sr]|rv|temp|luchtdruk|(prev|day)?rain)/;
        $data->[$i]{sense} = $data->[$i]{pol};
        $S =~ s/PM_/PM/; $S =~ s/PM([0-9])([1-9])/PM$1.$2/;
        $S =~ s/([A-Z])([0-9\.]+)/$1<span style="font-size:80\%">$2<\/span>/g;
        $data->[$i]{pol}=$S;
        if( $loc ne $prev ) {   # create a text list in Dutch language
            if( $data->[$i]{table}  =~ /_/ ){ # sensor kits have labels defined
                if ( defined $data->[$i]{municipality}) {
                    if( not $region ) {
                        $region = $data->[$i]{municipality} ;
                    } elsif ( $region !~ /$data->[$i]{municipality}/ ) {
                        if( $language =~ /UK/ ) {
                            $region =~ s/ and /, /; $region .= ' and ';
                        } else {
                            $region =~ s/ en /, /; $region .= ' en ';
                        }
                        $region .= $data->[$i]{municipality};
                    }
                } elsif ( defined $data->[$i]{village} ) {
                    if( not $region ) {
                        $region = $data->[$i]{village} ;
                    } elsif ( $region !~ /$data->[$i]{village}/ ) {
                        $region =~ s/ en /, /; $region .= ' en ';
                        $region .= $data->[$i]{village};
                    }
                }
                if ( $Slbls[$j] ) {
                    if( $language =~ /UK/ ) {
                        $Slbls[$j] =~ s/ and /, /; $Slbls[$j] .= ' and ';
                    } else {
                        $Slbls[$j] =~ s/ en /, /; $Slbls[$j] .= ' en ';
                    }
                }
                my $strt = $loc; $strt =~ s/\s+[0-9].*//; # hide street nr
                if( $data->[$i]{href} ) {
                    $href = $data->[$i]{href};
                    if( $HTMLalias ) {
                        $href = "${HTMLalias}$href";
                    }
                    $Slbls[$j] .= "<a href='/$href' alt='details sensorkit'>$strt</a>";
                    $Slbls[$j] .= " ($data->[$i]{sensors})" if (defined $data->[$i]{sensors}) && length($data->[$i]{sensors});
                } else {
                    $Slbls[$j] .= $strt;
                }
                if( not $Olbls[$j] ) { $Olbls[$j] = $data->[$i]{organisation}; }
                if( (defined $data->[$i]{organisation}) && ($data->[$i]{organisation} !~ /$Olbls[$j]/) && ($data->[$i]{organisation} !~ /MySense/)) {
                    if( $language =~ /UK/) {
                      $Slbls[$j] .= " of the organisation $data->[$i]{organisation}";
                    } else {
                      $Slbls[$j] .= " van de organisatie $data->[$i]{organisation}";
                    }
                }
            } else {
                if ( $Mlbls[$j] ) {
                    if( $language =~ /UK/ ) {
                        $Mlbls[$j] =~ s/ and /, /; $Mlbls[$j] .= ' and ';
                    } else {
                        $Mlbls[$j] =~ s/ en /, /; $Mlbls[$j] .= ' en ';
                    }
                }
                my $strt = $loc; $strt =~ s/\s+[0-9].*//; # hide street nr
                if( $data->[$i]{href} ) {
                    $Mlbls[$j] .= "<a href='/$data->[$i]{href}' alt='details sensorkit'>$strt</a>";
                } else {
                    $Mlbls[$j] .= $strt;
                }
                if( (defined $data->[$i]{organisation}) && ($data->[$i]{organisation} !~ /MySense/)) {
                  if( $language =~ /UK/) {
                    $Mlbls[$j] .= " of the organisation $data->[$i]{organisation}";
                  } else {
                    $Mlbls[$j] .= " van de organisatie $data->[$i]{organisation}";
                  }
                }
            }
        }
        # collect subtitle if defined will overwrite region
        if( (not defined $subtitle) || (not $subtitle) ){
            my $locals = 0;
            foreach my $item (@stations) {
                $locals++ if $item =~ /_/;
            }
            if( $locals <= 1 ) {
            if( (defined $data->[$i]{street}) and $data->[$i]{street} ){
                $subtitle = $data->[$i]{street};
                $subtitle =~ s/\s[0-9]+.*//;  # delete house nr
                if( (defined $data->[$i]{village}) and $data->[$i]{village} ){
                    $subtitle .= " in $data->[$i]{village}";
                }
            }
            } else { # more as one local measurment kit/station
                if( (defined $data->[$i]{municipality}) and $data->[$i]{municipality} ){
                $subtitle = 'regio ' . $data->[$i]{municipality};
                } elsif( (defined $data->[$i]{village}) and $data->[$i]{village} ){
                $subtitle = 'regio ' . $data->[$i]{village};
                }
            }
            if ( (not defined $subtitle) || (not $subtitle) ){
                if( $language =~ /UK/ ) {
                    $subtitle = 'the region ' . $region;
                } else {
                    $subtitle = 'de regio ' . $region;
                }
            }
        }
        $prev = $loc;
      }
    }

    if( $output !~ /^\/dev\// ) {
        $output =~ s/\.html//i;
        $output .= '.html' if $debug;
        $output = $webdir . $output if $output !~ /\.?\//;
    }
    if( $debug ) {
        $RSLT=sprintf("Debugmodus: HTML page ready output on %s , working dir %s\n",$output,WDIR);
    } else {
        $output .= '.html' if $output !~ /^\/dev\//;
        $RSLT=sprintf("File=%s with compressed JS script. Working directory: %s\n",$output,WDIR);
    }
    open $OUT, ">$output" || die ("Cannot open ${output} for generated HTML code\n");

    my $indoc = 0; my $skip = 0; my $inscript = 0;
    my $other = 1; # skip to get this language
    while( TRUE ){            # parse template file
        INPUT:
        if ( $IN ) { $_ = <$IN> ; }
        else { $_ = <main::DATA> }
        last if not $_;
        $other = 0 if /^__${language}__/;
        next if /^__${language}__/;
        next if $other;
        if( /^__[A-Z]+__/ ) {
            $other = 1 if not /^__${language}__/;
            next;
        }
        print STDERR $_ if $debug > 2;
        if( /<body/ ){ $indoc = 1;  next if not $debug; }
        if( /<\/body/ ){ $indoc = 0;  next if not $debug; }
        next if (not $debug) && (not $indoc);
        next if $debug && (not $indoc) && /script src=/ && $java;
        if( (/<script\s/) && $indoc ){
            # HighCharts JS libraries from HighChart outside the <head> part
            MyPrint($inscript,'<script src=\'https://ajax.googleapis.com/ajax/libs/jquery/1.12.4/jquery.min.js\'\></script>'."\n") if $java;
            MyPrint($inscript,'<script src=\'http://code.highcharts.com/stock/highstock.js\'></script>'."\n") if $java;
            MyPrint($inscript,'<script src=\'http://code.highcharts.com/highcharts-more.js\'></script>'."\n") if $java;
            MyPrint($inscript,'<script src=\'https://code.highcharts.com/modules/windbarb.js\'></script>'."\n") if $barb and $java;
            # enable support to drag legend
            MyPrint($inscript,'<script src=\'http://code.highcharts.com/modules/exporting.js\'></script>'."\n") if $exportChart;
            MyPrint($inscript,'<script src=\'https://rawgit.com/highcharts/draggable-legend/master/draggable-legend.js\'></script>'."\n");
            MyPrint($inscript,InsertButtonStyle());     # insert graph button styling

            MyPrint($inscript,$_); $inscript = 1;
            # from here we collect javastript statements
            MyPrint($inscript,InsertButtonJava(@BUTTONS));
            next;
        } 
        if( /<\/script>/ ){ $inscript = 0; };
        next if (not $indoc) && (not $debug);
        # output switcher: debug, dom ready function part and script global part
        if( /^(\/\/|<!--\s+)START\s+(DOM|GLOB)/ ) {
            my $sw = $2;
            if( $sw =~ /GLOB/ ){        # global var definitions
              if( $correctPM ) {
                my $correct = '
                var PMcorrect = true; // use this with alert question for correction
                function correctOnePM(sense,pm,rv) {
                    if( pm == null ) return null;
                    if( rv == null ) return null;
                    if( rv > 99.5 ) rv = 99.5;
                    if( rv < 0 ) rv = 0;
                    if( pm < 1 ) pm = 1;
                    // 20180714 replaced return pm * (4.56 * Math.pow(100-rv,-0.65));
                    if( sense.match(/pm10/) )
                        return pm * (4.31 * Math.pow(rv,-0.47));
                    else if( sense.match(/pm25/) )
                        return pm * (3.9003 * Math.pow(rv,-0.409));
                    else return pm
                }
                function correctPMs(sense,pm,rv) { // arg rv should be an array of indicators
                    if( !sense.match(/(pm10|pm25)/i) ) return pm;
                    if( !PMcorrect ) return pm;
                    var PM = [];
                    for( var i = 0; i < pm.length; i++ )
                        PM.push(correctOnePM(sense,pm[i],rv[i]));
                    return PM;
                }
                ';
                MyPrint($inscript,$correct);
                if( (defined $RVstations{default}) && $RVstations{default}{cnt} ){
                    foreach my $S (keys %{$RVstations{default}}) {
                        next if $S eq 'cnt'; 
                        next if not defined $RVstations{$RVstations{default}{$S}};
                        $RVstations{$RVstations{default}{$S}}{cnt} += $RVstations{default}{cnt};
                    }
                }
                foreach my $stat (keys %RVstations) {
                    next if $stat eq 'default';
                    my $stat_ = $stat; $stat_ =~ s/.*_//g;
                    MyPrint($inscript,sprintf("var humrv%s = %s;\n", $stat_, $RVstations{$stat}{rv}));
                }
              }
              for( my $j = 0; $j <= $#DATA; $j++ ) {
                my $data = $DATA[$j];
                # generate the javascript variables and data for graphs
                MyPrint($inscript,sprintf("var C%dtitle = '%s';\n", $j, $title));
                MyPrint($inscript,sprintf("var C%dsubtitle = '%s';\n",
                    $j, $subtitle));
                my $equal = -1;
                for( my $i = 0; $i <= $#{$data}; $i++ ){
                    if ( $i > 0 ) {
                        $equal++ if $data->[$i]{pol} =~ /$data->[$i-1]{pol}/;
                    } else { $equal++; }
                }
                $equal = ($equal == $#{$data});
                my $AvgStd = GetAvgStdDev( \$data );
                for( my $i = 0; $i <= $#{$data}; $i++ ){
                    if( defined $AvgStd ) {
                        MyPrint($inscript,sprintf("var Avg%dTitle = '%s regio ';\n",$j,$AvgStd->{sense}));
                        MyPrint($inscript,sprintf("var Avg%dStart = %d*1000;\n", $j, $AvgStd->{first}));
                        MyPrint($inscript,sprintf("var Avg%dunit = %d*1000;\n", $j, $AvgStd->{unit}));
                        MyPrint($inscript,sprintf("var Avg%ddata = %s;\n", $j, $AvgStd->{average}));
                        MyPrint($inscript,sprintf("var StdDev%ddata = %s;\n", $j, $AvgStd->{stddev}));
                        # MyPrint($inscript,sprintf("var Area%ddata1 = %s;\n", $j, $AvgStd->{area1}));
                        # MyPrint($inscript,sprintf("var Area%ddata2 = %s;\n", $j, $AvgStd->{area2}));
                        for( my $r = 1; $r <= 2; $r++ ){
                            MyPrint($inscript,"var Range${j}Area${r}1 = new Array(Avg${j}data.length);
var Range${j}Area${r}2 = new Array(Avg${j}data.length);
    for (var i = 0; i < Avg${j}data.length; i++) {
        if ( Avg${j}data[i] == null ) {
          Range${j}Area${r}1[i] = null; Range${j}Area${r}2[i] = null; continue;
        }
        Range${j}Area${r}1[i] = Avg${j}data[i] + $r * StdDev${j}data[i];
        Range${j}Area${r}2[i] = Avg${j}data[i] - $r * StdDev${j}data[i];
        if( Range${j}Area${r}2[i] < 0.05 ) { Range${j}Area${r}2[i] = 0.05; }
    }\n");
                        }
                        $AvgStd = undef; # only once
                    }
                    MyPrint($inscript,sprintf("var C%dstart%d = %d*1000;\n", $j, $i, $data->[$i]{first}));
                    MyPrint($inscript,sprintf("var C%dunit%d = %d*1000;\n", $j, $i, $data->[$i]{unit}));
                    if( $correctPM && (defined $RVstations{$data->[$i]{table}})
                        && (defined $RVstations{$data->[$i]{table}}{$data->[$i]{sense}}) ){
                        my $name = $data->[$i]{table}; $name =~ s/.*_//g;
                        # extend this not only for rv
                        $data->[$i]{data} = "humrv$name";
                    }
                    MyPrint($inscript,sprintf("var C%ddata%d = %s;\n", $j, $i, $data->[$i]{data}));
                    if( $data->[$i]{table} =~ /_/ ) {
                        my $pol = $data->[$i]{pol};
                        if ( $equal ) {
                            $pol = $data->[$i]{table};
                            $pol = $data->[$i]{label} if defined $data->[$i]{label};
                            $pol = lc $pol;
                            $pol =~ s/^(.*)[_-][0-9a-fA-F]+(....)$/$1-$2/;
                        }
                        $pol = ($language !~ /UK/? 'regen':'rain') if $pol =~ /rain/;
                        $pol =~ s/wind/wind snelheid/i;
                        $pol =~ s/snelheid/speed/ if $language =~ /UK/;
                        MyPrint($inscript,sprintf("var C%dtitle%d = '%s (%s)';\n", $j,
                            $i,
                            defined $data->[$i]{street} ? $data->[$i]{street} : $data->[$i]{label},
                            $pol));
                    } else {
                        my $loc = $data->[$i]{location};
                        $loc =~ s/,\s[A-Za-z\s]+//;
                        my $id = $data->[$i]{pol};
                        if ( $equal ) {
                            if ( defined $data->[$i]{label} ) { $id = $data->[$i]{label}; }
                            elsif( defined $data->[$i]{table} ) { $id = $data->[$i]{table};}
                            $id = lc $id;
                            $id =~ s/^(.*)[_-][0-9a-fA-F]+(....)$/$1-$2/;
                        }
                        MyPrint($inscript,sprintf("var C%dtitle%d = '%s (%s)';\n",
                            $j, $i, $loc,$id));
                    }
                }
              }
            }
            $skip++ if $sw =~ /GLOB/; next;
        } elsif ( /^(\/\/|<!--\s+)END\s+(GLOB|DOM)/ ) {
            $skip = 0;
            next;
        }
        if( $subtitle =~ /$region/i ) {
            $region = $Slbls[0];
        }
        if( /^(\/\/\s*|<!--\s+)START\s+([a-zA-Z0-9]*).*/ ){ # insert new values
            my $type = $2; $skip++;
            if( $type =~ /stations/ ){      # all stations text
                MyPrint($inscript, "$Mlbls[0].\n");
            } elsif( $type =~ /organisation/ ) { # all others from organisation
                if( $Olbls[0] && ($Olbls[0] !~ /MySense/) ) { 
                    if (  $language =~ /UK/ ) {
                        MyPrint($inscript, "of the organisation $Olbls[0]\n");
                    } else {
                        MyPrint($inscript, "van organisatie $Olbls[0]\n");
                    }
                }
            } elsif( $type =~ /locations/ ){     # all locations of sensors text
                my @locs = split(/, */, $Slbls[0]);
                if ( $#locs < 3 ) {
                    MyPrint($inscript, "$Slbls[0].\n");
                } else {
                    $locs[$#locs+1] = $locs[$#locs]; $locs[$#locs-1] =~ s/ (en|and) .*/ $1/;
                    $locs[$#locs] =~ s/.* (en|and) //;
                    MyPrint($inscript, "<ul><li>".join('<li>',@locs).".</ul>\n");
                }
            } elsif( $type =~ /type/ ) {         # class of pollutants
                MyPrint($inscript, "($poltype)\n");
            } elsif( $type =~ /version/ ){       # version of software generator
                MyPrint($inscript, 'V'. $Version);
            } elsif( $type =~ /updated/ ){       # last update of chart
                MyPrint($inscript, 'data geactualiseerd op ' . strftime("%Y-%m-%d %H:%M\n",localtime(time)));
            } elsif( $type =~ /Legend/i ) {       # insert button Legend off/on
                MyPrint($inscript, '<button id="update-legend" class="autocompare">legendum uit/aan</button>' . "\n")
                    if $nrLegends >= 2;
            } elsif( $type =~ /first/ ){         # first date in chart
                MyPrint($inscript, $first . "\n");
            } elsif( $type =~ /last/ ){          # last date in chart
                MyPrint($inscript, $last . "\n");
            } elsif( $type =~ /regio/ ){         # region text
                MyPrint($inscript, $region."\n");
            } elsif( $type =~ /straat/ ){        # street name text
                MyPrint($inscript, 'straat naam'."\n");
            } elsif( $type =~ /revision/ ){      # script revision nr and date
                MyPrint($inscript, "<!-- HighCharts generator Version ".$Version." -->\n");
            } elsif( $type =~ /TableHdr/ ) {     # table with button or not
                MyPrint($inscript,InsertTableHdr(\@BUTTONS,\@POLLUTANTS) ."\n");
            } elsif( $type =~ /correctPM/ ) {    # add text info on PM corrections
                MyPrint($inscript,correctPMtext());
            } elsif( $type =~ /showBands/ ){           # AQI text lines
                # next should be compiled from %bands
                my %AQItxt = (
                    LKI => 'luchtkwaliteit LKI (RIVM) Index',
                    EU  => 'EU en WHO normen',
                    AQI => 'internationale luchtkwaliteit AQI Index',
                    # complete but complex overview and differences,
                    # discouraged to be shown
                    AQI_LKI => 'AQI en LKI luchtkwaliteits Index niveaux',
                );
                next if not $ShowBands;
                next if (not defined $AQItxt{$AQI}) || (not defined $bands{$AQI});
                my $levels = '';
                for(my $i = 1; $i <= $#{$bands{$AQI}}; $i++) {
                    # compile a list of levels
                    $level =~ s/ en /, / if $level;
                    $level .= ' en ' if $level;
                    $level .= $bands{$AQI}[$i][0];
                }
                $AQItxt{$AQI} .= ' grensen (resp. LEVEL';
                $AQItxt{$AQI} =~ s/LEVEL/$level/;
                $AQItxt{$AQI} .= ' &micro;g/m&sup3;)';
                my $string = "
<p>Bij de grafieken van de meetstations worden tevens met de achtergrondskleur de verschillende " . $AQItxt{$AQI} . " voor fijnstof weergegeven. </p>\n";
                if( $language =~ /UK/ ) {
                $string = "
<p>The chart will also show the background color of the different ".$AQItxt{$AQI} . " for dust particles.</p>\n";
                }
                MyPrint($inscript, $string);
            } elsif( $type =~ /HIGHCHART/ ) {
                for( my $i = 0; $i <= $#BUTTONS; $i++ ) {
                    my $str = sprintf("<div id=\"C${i}SENSORS\" style=\"width:510px; height:340px;margin:0 auto\"></div>");
                    $str = sprintf("<div class=\"C${i}table\" id=\"C${i}table\" style=\"display: %s\">%s</div>\n", ($i == 0? 'block' : 'none'),$str) if $#BUTTONS > 0;  
                    MyPrint($inscript,$str);
                }
            } elsif( $type =~ /SERIES/ ){     #one graph
                MyPrint($inscript,"\tHighcharts.seriesTypes.windbarb.prototype.beaufortName = [
                              'stil', 'zeer zwak', 'zwak', 'vrij matig','matig',
                              'vrij krachtig', 'krachtig','hard','stormachtig','storm',
                              'zware storm','orkaan'];\n") if $barb;
                for( my $j = 0; $j <= $#DATA; $j++ ) {
    # sort it...
    my @dat = sort CompareSeries @{$DATA[$j]};
    MyPrint($inscript,InsertHighChartGraph("C$j",$BUTTONS[$j],ChartSerie($j,\@dat),ChartyAxis(\@dat,plotBands($AQI))));
                    # MyPrint($inscript,InsertHighChartGraph("C$j",$BUTTONS[$j],ChartSerie($j,$DATA[$j]),ChartyAxis($DATA[$j],plotBands($AQI))));
                }
            }
            while( TRUE ){                         # skip rest
                if( $IN ){ $_ = <$IN> ; }
                else { $_ = <main::DATA> }
                if( not $_ ) { $skip = 0; last; }
                print STDERR $_ if $debug > 2;
                if( /^(\/\/\s*|<!--\s+)END/ ){
                    $skip = 0;
                    if( $IN ){ $_ = <$IN> ; }
                    else { $_ = <main::DATA> }
                    last;
                }
            }
        }
        s/\/\/\s.*// if not $debug;
        s/<!--\s.*\s-->// if not $debug;
        next if /^\s*$/;
        MyPrint($inscript, $_) if not $skip;
    }
    system("/bin/chgrp --silent $wwwgrp $output") if $output =~ /^\//;
    chmod 0644, $output;
    print STDERR $RSLT if $verbose;
    return 0;
}

die "Cannot access database $mydb. Correct user/password?\n" if not Check_DB();

$Mean = TRUE if ($#ARGV >= 4) && (not $Mean);
if( $#ARGV >= 0 ) {     # at least 2 sensor locations
    Generate(@ARGV,$reference);
} else {                # default
    Generate(LOCATION,$reference);
}

__DATA__
__NL__
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html><head>
            <script src='https://ajax.googleapis.com/ajax/libs/jquery/1.12.4/jquery.min.js'></script>
            <script src='http://code.highcharts.com/stock/highstock.js'></script>
            <script src='http://code.highcharts.com/highcharts-more.js'></script>
</head><body>
<script type="text/javascript">
//START GLOB data defs
//END GLOB data
Highcharts.Legend.prototype.toggle = function () {
    if (this.display) {
        this.group.hide();
        this.box.hide();
    } else {
        this.group.show();
        this.box.show();
    }
    this.display = !this.display;
    this.chart.isDirtyBox = true;
    this.chart.redraw();
};

$(function () { // on DOM ready
//START DOM
    Highcharts.setOptions({
        lang: {
                months: ['januari','februari','maart','april','mei','juni','juli','augustus','september','october','november','december'],
                shortMonths: ['jan','feb','mrt','apr','mei','jun','jul','aug','sep','oct','nov','dec'],
                weekdays: ['zondag','maandag','dinsdag','woensdag','donderdag','vrijdag','zaterdag'],
                shortWeekdays: ['zo','ma','di','wo','do','vr','za'],
                rangeSelectorTo: 'tot',
                rangeSelectorFrom: 'zoom:',
            }
        }
    );
//START SERIES
//END SERIES
//END DOM
});
</script>
<p>
<a id="metingen" name="metingen"></a>
<!-- START TableHdr -->
<!-- END TableHrd -->
</p>
<p>
<!-- Highchart graphics -->
<!-- START Legend -->
<!-- END Legend -->
<table style='color:black;background:#f9f9f9;border-radius:7px;-moz-border-radius:7px;-webkit-border-radius:7px;box-shadow: 0px 7px 10px 0px #a0a0a0;text-align:left;padding:0px;padding-top:3px;padding-bottom:0.3%;margin:0px;border-spacing:0px;border:0px solid black;width:100%;'>
<caption valign=top align=center><span style='color:#0376ab'><a href="http://samenmeten.rivm.nl/dataportaal/" title="meer meetplaatsen met de sensor van het project SamenMetenAanLuchtkwaliteit.nl van het RIVM">Lokale Luchtkwaliteit</a>: de grafieken
<!-- START type -->
(fijnstof)
<!-- END type -->
metingen<br >in de regio
<!-- START regio -->
Horst a/d Maas
<!-- END regio -->
</span>.<br /><span valign=bottom style='font-size:85%;color:#2e3b4e;text-align:right'>Gebaseerd op Samen Meten  metingen en data van o.a. <a href="https://www.luchtmeetnet.nl/stations/limburg/alle-gemeentes/alle-stoffen" title="Bezoek website met actuele metingen">het RIVM</a><br />
van
<!-- START first -->
zo 11 dec
<!-- END first -->
tot
<!-- START last -->
ma 12 dec 04:26
<!-- END last -->
.
</span>
</caption>
<tbody>
<tr>
<td style='padding:1%'><div title="De metingen zijn niet gevalideerd.">
<!-- START HIGHCHART -->
<div id="VUURWERK" style="width:510px; height:340px;margin:0 auto"></div>
<!-- END HIGHCHART -->
</div></td>
</tr>
<tr>
<td colspan=5 style='vertical-align:bottom;padding-left:10px;padding-bottom:6px;padding-right:10px'>
<div style='text-align:left;font-size:50%'>
<!-- START version -->
V0.00 2018/01/01
<!-- END version -->
</div><div style='text-align:right;font-size:70%'>
<!-- START updated -->
za 17 dec 12:41
<!-- END updated -->
</div>
</td></tr>
</tbody>
</table>
<!-- START GraphTableEnd -->
<!-- End GraphTableEnd -->
</p>
<p>
<table width=100% border=0 bordercolor=white>
<tr><td title="Gebruik de cursor om een selectie te maken van de periode en/of meer detail informatie over een meting.">
De bovenstaande tabel met de recente luchtkwaliteits metingen voor de regio
//START regio
Regio Limburg
//END regio
</p><p>
In de grafieken worden de sensorkit metingen weergegeven van de meetstation(s) &#150;
<!-- START stations -->
Landelijk Meetstation, Limburg (PLIM)
<!-- END stations -->
&#150;
in vergelijking met de grafiek van metingen met de eenvoudiger en betaalbare Plantower, Sensirion of Nova sensor uitgeruste MySense meetkit
<!-- START organisation -->
<!-- END organisation -->
op de locatie(s):
<!-- START locations -->
Fake Adres, Location ERROR (Fake)
<!-- END locations -->
<br />Pas op: hoewel de grafieken van de landelijke meetstations met referentie apparatuur en de eenvoudiger sensors elkaar redelijk lijken te volgen is de schaal van de grafieken anders: aan de rechterzijde wordt de schaal vermeld van de metingen van de referentie apparatuur, links staat de schaal van de eenvoudiger sensoren vermeld.
</p>
<!-- START correctPM -->
<!-- END correctPM -->
<p>
De fijnstof sensor van deze meetkits telt het aantal fijnstof deeltjes (PM<span style="font-size:80%">1</span>, PM<span style="font-size:80%">2.5</span> en PM<span style="font-size:80%">10</span>) in een minuut in een periode van telkens  ca 15 minuten. De fijnstof meting wordt door de fabrikant vervolgens omgerekend naar het gewicht van de deeltjes in &micro;g/m&sup3;.
In de omrekening door de fabrikant wordt geen rekening gehouden met relatieve vochtigheid, regen en andere lokale invloeden.
<br />De fijnstof metingen van de RIVM/PLIM landelijke meetstations zijn ook gewichtsmetingen (&micro;g/m&sup3;) van gemiddelden per uur.
De apparatuur van het landelijk meetstation wordt periodiek (lokaal) geijkt. 
<br />Notitie: Elke sensor is verschillend. De onderlinge verschillen zijn met met tijdrovende regressie tests te corrigeren.
Hiervoor is begin 2020 een aanvang gemaakt. Voorlopig wordt alleen gebruik gemaakt van de ruwe meetwaarden van de sensor en tav fijnstof waarden van de door de fabrikant geconverteerde massa waarden. 
<br />
Om de hoeveelheid data te beperken zijn de meetwaarden geaggredeerd - een gemiddelde over een periode van 30 minuten voor de sensors en 60 minuten voor de landelijke meetstations. De getoonde periode is de afgelopen 3 dagen. Eens per uur wordt de grafiek ververst.
</p>
<!-- START showBands -->
<!-- END showbands -->
</td></tr>
</table>
</p>
<p>De grafieken zijn onder voorbehoud. Het kan zijn dat er zich nog probleempjes voordoen, er aanbevelingen voor verbeteringen zijn of vragen zijn. Meldt ze aub aan MySense @ BehoudDeParel.nl.
</p>
<p>HighCharts luchtkwaliteit Perl script
<!-- START revision -->
Revision 101 Zondag 24 juni 2018
<!-- END revision -->
</p>
</body>
</html>
__UK__
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html><head>
            <script src='https://ajax.googleapis.com/ajax/libs/jquery/1.12.4/jquery.min.js'></script>
            <script src='http://code.highcharts.com/stock/highstock.js'></script>
        
<script src='http://code.highcharts.com/highcharts-more.js'></script>
</head><body>
<script type="text/javascript">
//START GLOB data defs
//END GLOB data
Highcharts.Legend.prototype.toggle = function () {
    if (this.display) {
        this.group.hide();
    } else {
        this.group.show();
    }
    this.display = !this.display;
    this.chart.isDirtyBox = true;
    this.chart.redraw();
};

$(function () { // on DOM ready
//START DOM
    Highcharts.setOptions({
        lang: {
                months: ['January','February','March','April','May','June','July','August','September','October','November','December'],
                shortMonths: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
                shortWeekdays: ['Su','Mo','Tu','We','Th','Fr','Sa'],
                rangeSelectorTo: 'till',
                rangeSelectorFrom: 'from',
            }
        }
    );
//START SERIES
//END SERIES
//END DOM
});
</script>
<p>
<a id="metingen" name="metingen"></a>
<!-- START TableHdr -->
<!-- END TableHrd -->
</p>
<p>
<!-- Highchart graphics -->
<!-- START Legend -->
<!-- END Legend -->
<table style='color:black;background:#f9f9f9;border-radius:7px;-moz-border-radius:7px;-webkit-border-radius:7px;box-shadow: 0px 7px 10px 0px #a0a0a0;text-align:left;padding:0px;padding-top:3px;padding-bottom:0.3%;margin:0px;border-spacing:0px;border:0px solid black;width:100%;'>
<caption valign=top align=center><span style='color:#0376ab'><a href="http://samenmeten.rivm.nl/dataportaal/" title="more locations of measurements with sensors from the project SamenMetenAanLuchtkwaliteit.nl national health org. RIVM">Local Air Quality</a>: the graphs
<!-- START type -->
(fijnstof)
<!-- END type -->
measurements<br >in the region
<!-- START regio -->
Horst a/d Maas
<!-- END regio -->
</span>.<br /><span valign=bottom style='font-size:85%;color:#2e3b4e;text-align:right'>Based on Together we Measure measurements and data from e.g.<a href="https://www.luchtmeetnet.nl/stations/limburg/alle-gemeentes/alle-stoffen" title="Visit the website for actual measurements and data">the RIVM</a><br />
from
<!-- START first -->
zo 11 dec
<!-- END first -->
till
<!-- START last -->
ma 12 dec 04:26
<!-- END last -->
.
</span>
</caption>
<tbody>
<tr>
<td style='padding:1%'><div title="The measurements are not validated.">
<!-- START HIGHCHART -->
<div id="VUURWERK" style="width:510px; height:340px;margin:0 auto"></div>
<!-- END HIGHCHART -->
</div></td>
</tr>
<tr><td colspan=5 style='vertical-align:top;text-align:right;padding-right:10px;padding-bottom:6px;font-size:70%'>Last updated on
<!-- START updated -->
za 17 dec 12:41
<!-- END updated -->
</td></tr>
</tbody>
</table>
<!-- START GraphTableEnd -->
<!-- End GraphTableEnd -->
</p>
<p>
<table width=100% border=0 bordercolor=white>
<tr><td title="Use your cursor to make a selection of the period and/or to obtain more detailed information of the measurement.">
The table shows recent measurements for the region
//START regio
Regio Limburg
//END regio
</p><p>
The graphs show the sensor kit measurements for the location(s) &#150;
<!-- START stations -->
Landelijk Meetstation, Limburg (PLIM)
<!-- END stations -->
&#150;
compared with the graphs of the measurements of the more affortable e.g. Plantower, Sensirion or Nova sensor equipped MySense measurement kit
<!-- START organisation -->
<!-- END organisation -->
on the location
<!-- START locations -->
Fake Adres, Location ERROR (Fake)
<!-- END locations -->
.<br />Reminder: the sensor values do correlate with the reference sensors used in the governmental stations. On the right side the scale is shown of the reference sensors. At the left side we show the scale of the more affortable sensor kits.
</p>
<!-- START correctPM -->
<!-- END correctPM -->
<p>
The dust sensor does a counting of particles flying by (PM<span style="font-size:80%">2.5</span> and PM<span style="font-size:80%">10</span>) every minute in a sample of 5 minutes.
The measurement value shown is recalculated by the manufacturer to particles weight:
&micro;g/m&sup3;.
In the calculation the influence of humidity to the count is however neglected.
The dust values from the reference sensors used e.g. by RIVM or PLIM is showed as
(&micro;g/m&sup3;) as average per hour.
The reference sensor are calibrated on a regular base.
<br />Note:
the values of the local sensor kits differ amongst each other and among manufacturer in a linear way. They need still to be calibrated.
<br />
To limit the amount of data the values have been aggregated: periods of 30 minutes for the local sensorkits and 60 minutes for the reference sensors.
The default period of time shown on the zoomed chart is 3 days. Once per hour the chart is updated.
</p>
<!-- START showBands -->
<!-- END showbands -->
</td></tr>
</table>
</p>
<p>
The shown charts are automatically generated. So the may have errors. If so and if you see improvements please do not hesitate to contact us:
MySense @ BehoudDeParel.nl.
</p>
<p>HighCharts air quality Perl script
<!-- START revision -->
Revision 101 Zondag 24 juni 2018
<!-- END revision -->
</p>
</body>
</html>
