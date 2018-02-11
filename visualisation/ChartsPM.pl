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

# $Id: ChartsPM.pl,v 4.2 2018/02/11 16:43:41 teus Exp teus $
my $Version = '$Revision: 4.2 $, $Date: 2018/02/11 16:43:41 $.';
$Version =~ s/\$//g;
$Version =~ s/\s+,\s+Date://; $Version =~ s/([0-9]+:[0-9]+):[0-9]+/$1/;
# Description:
# script will generate JS script Highchart graphs from pollutant data.
# The data is collected from the measurement stations and sensors tables
# in the database.
# DEPENDS on: yui-compressor java script to compress javascript parts
# TO DO:
#       allow the user to select different the levels for EU/WHO/LKI/AQI/AQI_LKI etc.
use feature "state"; # some output is done only once
use constant {
                                        # Default DB credentials
        USER => 'someuser', PASSWD => 'somepass', HOST => 'localhost',
        DB        => 'luchtmetingen',   # default database

        TITLE     => 'Samen Meten aan Luchtkwaliteit', # chart
        SUBTITLE  => 'metingen',        # chart

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
   print STDERR "Cannot chdir to working dir $WDir\n";
   $WDir = './';
}

Getopt::Mixed::init(
        'H help>H '.
        'd:i debug>d '.
        'v verbose>v '.
        'q quiet>q '.
        'p=s pass>p '.
        'u=s user>u '.
        'h=s host>h '.
        'D=s database>D '.
        'l=s location>l '.
        'i=s serial>i '.
        'P=s project>P '.
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
        'A=s aqi>A '.
        'b=s buttons>b '.
        'AQI>A '.
        'B bands>B '.
        'index>A '.
        'w=s web>w '.
        'W=s wd>W '.
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
my $poltype     = 'fijnstof';# type of pollutants, e.g. fijnstof
my $AQI         = AQI;
my $webdir      = WEBDIR;
my $wwwgrp      = WWWGRP;
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
my %TimeShifts  = (     # time shift for some stations, in seconds
    'HadM' => -5*30*60,
    );
my $reference   = REF;
my $last_time   = '';   # last date/time used for end date/time graphs
                        # next do not seem to work properly, why?
my $exportChart = FALSE;# enable/disable button to export Chart Graph
                        # > 1 will say: print button (no download)
my $ShowBands   = FALSE;# show AQI or LKI bands in the chart for LML stations

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
    $option eq 'c' and do { $correctPM = TRUE; last OPTION; };
    $option eq 'e' and do {
            $pollutants = $value;
            $value =~ s/\|/,/g;
            $value =~ s/^/,/; $value =~ s/[,\|](pm(10|25)?|temp|rv|luchtdruk|w[sr]|([A-O][0-3]?)+|rssi)//g;
            if( $value ) {
                print STDERR "Unknown pollutant in pollutant choice: $pollutants.\n";
                $pollutants = POLLUTANTS;
            }
            if( $pollutants !~ /pm/ ) { $poltype = ''; }
            if( $pollutants =~ /(temp|luchtdruk|w[sr])/ ) {
                $poltype .= ", klimaat"; $poltype =~ s/^, //;
            }
            if( $pollutants =~ /([A-O][0-3]?)+/ ) {
                $poltype .= ", gassen"; $poltype =~ s/^, //;
            }
            $poltype =~ s/(.*),/$1 en/;
            $poltype =~ s/[\(\)]//g;
            $pollutants =~ s/\s//g; # something alike pm10|pm25,rv|temp 2 charts
            last OPTION;
        };
    $option eq 'u' and do { $myuser = $value; $myuser =~ s/\s//g; last OPTION; };
    $option eq 'p' and do { $mypass = $value; last OPTION; };
    $option eq 'P' and do { $project = $value; last OPTION; };
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
                    print STDERR "Unable to parse date/time from $value\n";
                    exit(1);
                }
            };
        };
    $option eq 't' and do { $title = $value; last OPTION; };
    $option eq 's' and do { $subtitle = $value; last OPTION; };
    $option eq 'R' and do { $reference = $value; last OPTION; };
    $option eq 'r' and do { $myRegion = $value; last OPTION; };
    $option eq 'i' and do {
            $identifier = $value; $identifier =~ s/\s//g;
            last OPTION;
        };
    $option eq 'W' and do { $WDir = $value; chdir(WDir); last OPTION; };
    $option eq 'w' and do { $webdir = $value; last OPTION; };
    $option eq 'O' and do { $output = $value; last OPTION; };
    $option eq 'A' and do { $AQI = $value; last OPTION; };
    $option eq 'H' and do {
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
 -i|--serial    The measurement serial nr to use, default $identifier
                The database table is defined by {project_ID}_identifier (${project}_$identifier)
 -d|--debug     Debugging on.
 -H|--help      This help or usage message.
 -v|--verbose   Increase verbosity, default: off.
 -q|--quiet     Be as quiet as possible, turns verbose off, default: off.

 -D|--database  The Database name to use (default: $mydb). Or env variable DB.
 -h|--host      The DB host for DB access (default: $myhost). Or env var. DBHOST.
 -u|--user      The DB user for DB access (default: $myuser). Or env. var. DBUSER.
 -p|--pass      The DB user password for DB access (default: X?x?X). Or env. var. DBPASS.

 -P|--project   The project name (default: VW2017). Is used as component in data DBtable name.
 -g|--graphs    The minimal amount of graphs in the chart (default: $mingraphs).
 -e|--pollutants The pollutants choice for the graphs shown (default: $pollutants)
                The pollutant identifier is the DB table column name: eg pm, o3, temp
                Per button a comma separated name can be given e.g.
                    pm25|pm10,rv|temp for buutun name e.g. dust,weather
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
                Deprecated.
 -B|--bands     Turn show of AQI or LKI color bands on with official stations graphs.
                Currently bands are not working any more for some reason.
 -L|--last      Use this date/time as last date iso last 'datum' of referenced
                station measurement.
 -W|--wdir      The working directory with own modules.
 -w|--web       The website private page directory to store the page.
                The website path is not prepended if output file name start with
                ./ or /
 -c|--correct   The PM values are corrected with rel. humidity correction factor
                factor = 4.65 * (100 - hum)**-0.65
                Humidity measurments is one element of correction arithmetic.
                Humidity of stations will be collected per station if present.
 -a|--aggregation [number] Use nr of minutes as minimal period to calculate average values.
                Default: 6 minutes for small periods. Script will search minimal
                period of minutes between measurements.
                Max (eg LML statrions)  is one hour.

$Version
This program is free software: you can redistribute it and/or modify
                Humidity measurments is one element of correction arithmetic.
                Humidity of stations will be collected per station if present.
it under the terms of the GNU General Public License as published by
the Free Software Foundation.
The script depends om mysql, yui-compressor,
and perl modules (JSON,Posix,,Time,autodie,LWP,URI and DBI). 
See the script constant declaration for the default configuration values.
EOF
        exit(0);
        };
   };
}
Getopt::Mixed::cleanup();
$verbose = 3 if $debug;

die "FATAL ERROR: no database user/password defined, e.g. define use environment variable DBUSER and/or DBPASS\n" if length($mypass) <= 0;


# the Joost fit correction factor to correct PM values with rel. hum  values
# correction coefficients come from RIVM VW2017 project 
# routine is unused if javascript does corrections
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
    if ( $PM =~ /PM_?(10|25)/i ) {
        # correction factor PM10 from RIVM jan 2018 for SDS011 sensor
        $rts = int( ($PMval * 4.65 * ((100.0-$HUMval)**-0.65)) * 100.0)/100.0;
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
    return $data->[$pmIndex]{data} if not defined $data->[$pmIndex]{label};
    return $data->[$pmIndex]{data} if not $data->[$pmIndex]{label};
    return $data->[$pmIndex]{data} if not defined $data->[$pmIndex]{table};
    my $RVdata;
    if( not defined $RVstations{$data->[$pmIndex]{table}} ){
        if( (not defined $RVstations{default}) || (not defined $RVstations{default}{rv}) ){
            $correctPM = 0;
            print STDERR "Missing humidity measurments to do corrections. Switched off\n";
            return $data->[$pmIndex]{data};
        }
        $RVdata = $RVstations{default}{rv};
    } else { $RVdata = $RVstations{$RVstations{$data->[$pmIndex]{table}}}{rv}; }
    #$RVdata =~ s/[\[\]]//g;
    #my @RV = split(/,/,$RVdata);
    my @RV = split(/,/,substr($RVdata,1,-1));

    #my $PMdata = $data->[$pmIndex]{data};
    #$PMdata =~ s/[\[\]]//g;
    #my @PM = split(/,/,$PMdata);
    my @PM = split(/,/,substr($data->[$pmIndex]{data},1,-1));

    # return undef if $#PMdata != $#RVdata;
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
    foreach my $i ('serial','label') {
        $qry = query($sensors,"SELECT count(*) FROM $sensors WHERE  $i = '$id'");
        if( $qry->[0] ) {
            $indx = $i; $info{$i} = $id; last;
        }
    }
    return %info if not $indx;
    $qry = query($sensors,"SELECT
            CONCAT(serial,';', label,';', coordinates,';', UNIX_TIMESTAMP(first),
                ';',street,';',village,';',municipality)
            FROM $sensors WHERE $indx = '$id' ORDER BY datum DESC");
    return undef if $#{$qry} < 0;
    my @in = split /;/, $qry->[0];
    $info{serial}=$in[0];
    $info{label}=$in[1];
    $info{coordinates}=$in[2];
    $info{first}=$in[3] if defined $in[3];
    $info{street}=$in[4] if defined $in[4];
    $info{street} =~ s/\s+[0-9].*// if defined $in[4];
    $info{village}=$in[5] if defined $in[5];
    $info{municipality}=$in[6] if defined $in[6];
    $info{location}=$in[4] if defined $in[4];
    $info{location} =~ s/\s+[0-9].*// if defined $in[4];
    $info{location} = $info{location} . ' '.$info{village}
        if defined $in[5];
    $info{location} = $info{location} . ' (gem. '.$info{municipality}.')'
        if( (defined $in[6]) and ($info{village} ne $info{municipality}));
    $info{location} =~ s/,\s+\(/ (/g;
    $info{location} = $info{label} if not defined $info{location};
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
    @pols = split(/\|/,$polSelect);
    foreach (@pols) {
        $pol = $_;
        next if not Check_Sensor($Ref,$_);
        my $qry = query($Ref,"SELECT UNIX_TIMESTAMP(datum) FROM $Ref WHERE ${pol}_valid ORDER BY datum DESC LIMIT 1");
        next if $#{$qry} < 0;
        $last = $qry->[0] if $qry->[0] > $last;
    }
    printf STDERR ("Could not find any pollutant of %s in $Ref table\n",join(', ',@pols))
        if not $last;
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
    # my @times;
    my %rts; my @values; my $count = 0;
    my $last = $pairs[0][0];
    # push(@times,$last);
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
        # push(@times,$last);
        if( $sum < 0.1 ) {
            push(@values,'null');
        } else {
            push(@values,int($sum*10+0.4)/10.0); $count++;
        }
    }
    while( $last+$unit <= $end ) {
         $count++; $last += $unit;
         push(@values,'null');
    }
    #for( my $j = 0; $j < 9; $j++) {
    #    printf("pair [%d,%.2f], values [%d,%.2f]\n", 
    #        $pairs[$j][0]-$pairs[0][0],$pairs[$j][1], $j * $unit, $values[$j]);
    #}
    $rts{first} = $pairs[0][0]; $rts{last} = $last; $rts{values} = \@values;
    $rts{count} = $count; $rts{unit} = $unit;
    return \%rts;
}

# extract data from DB for a pollutant and serialize it into json data struct
# return ref to hash table with name, location, pollutant, string as json data
sub Get_data {
    my ($tbl,$pol,$last,$secs,$period) = @_; my %rslt;
    $period = PERIOD if not defined $period;
    return \%rslt if not defined $DB_cols{$tbl}{$pol}; 
    # take average in the hour of measurement
    # VM2017 is using Zulu time minus 1 hour, we need to correct this
    # TO DO: correct the MySql DB entries!
    # software had timezone bug of one hour before 1515547638 epoch time
    # last time with time zone bug/error is: 2018/01/10 02:27:18 on correction needed
    my $corr = 0 ; $corr += 3600 if $tbl =~ /^VW[0-9]{4}_/;
    my $first = $last-$period;
    $last -= $corr if $last <= 1515547638;
    $first -= $corr if $first <= 1515547638;
    my $data = query($tbl,"SELECT CONCAT(UNIX_TIMESTAMP(datum),'=',$pol) FROM $tbl
                WHERE (UNIX_TIMESTAMP(datum) >= $first) AND 
                    (UNIX_TIMESTAMP(datum) <= $last) AND
                    NOT ISNULL($pol) AND ${pol}_valid
                    ORDER BY datum");
    return \%rslt if $#{$data} < MINHOURS*(60*60/$secs); # MINHOURS hours minimal
    my $values = Array2Units($data,$last,$corr,1515547638);
    $rslt{pol}=$pol; $rslt{table}=$tbl; $rslt{data} = '[';
    $rslt{first} = $values->{first}; $rslt{last} = $values->{last};
    $rslt{count} = $values->{count}; $rslt{unit} = $values->{unit};
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
    
# collect the data for a serie of stations (DB table names)
# return a ref to array of hashes: table name, location name, pm name
sub Collect_data {
    my $pols = shift; my @stations = @_; my $last;  my %info;
    if( $last_time ) {   $last = $last_time ; }
    else { $last = Get_last($pols,$reference); } # default last date/time of REF station
    my @data; my $first = time;
    if( not $last ) {
        print STDERR "Cannot find last measurement date/time\n";
        return 0;
    }
    for( my $i = 0; $i <= $#stations; $i++ ) {
        if( $stations[$i] =~ /^VW[0-9]{4}_/ ) { # sensor kits only
            my $CorrectME = 0; my @stationData;
            my $id = $stations[$i] ; $id =~ s/VW[0-9]{4}_//;
            %info = Get_Info($id); # search serial or label with this id
            print STDERR "Cannot find station $stations[$i] in database.\n"
                if not defined $info{serial};
            next if not defined $info{serial};
            my $tbl = 'VW2017_'.$info{serial};
            next if not Check_Tbl($tbl);
            Get_Sensors($tbl);
            addRVstation($tbl,$last);
            foreach my $S (keys %{$DB_cols{$tbl}}) {
                # next if $S =~ /(^id|^datum|_valid)/;
                next if $S !~ /$pols/i; # only pollutants choice
                # interval of measurements should be 5*60 seconds
                my $D = Get_data($tbl,$S,$last,60*60);
                next if not defined $D->{data};
                my $c = () = $D->{data} =~ /,/g; # count number of elements-1
                next if $c*$D->{unit} < 12*60;   # minimal 12 hours of values
                $first = $D->{first} if $D->{first} < $first;
                $last = $D->{last} if $D->{last} > $last;
                $D->{location} = $info{location};
                $D->{village} = $info{village};
                $D->{label} = $info{label}; # mark for low cost sensor
                $D->{sense} = $S;
                $D->{organisation} = 'BdP/Fontys';
                $D->{href} = $tbl;
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
                if( $#data < 0 ) { # always first in array
                    push @data, $D;
                } else {
                    push @data, $data[0];
                    $data[0] = $D;
                }
            }
        } else {
            if( not Check_Tbl($stations[$i]) ){
                print STDERR "Cannot find station $stations[$i] in database.\n";
                next;
            }
            Get_Sensors($stations[$i]);
            addRVstation($stations[$i],$last,TRUE);
            my @info = ('','','');
            my $qry = query("stations","SELECT CONCAT(name,';;',organisation,';',municipality,';',id) 
                        FROM stations WHERE stations.table = '$stations[$i]' LIMIT 1");
            if( $#{$qry} < 0 ) {
                my $serial = $stations[$i] ; $serial =~ s/VW.*_//;
                $qry = query("Sensors","SELECT CONCAT(street,';',village,';','BdP/Fontys',';',municipality,';$stations[$i]') 
                        FROM Sensors WHERE Sensors.serial = '$serial' order by id desc LIMIT 1");
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
                if( defined $info[1] ) {
                    $D->{street} = $info[0];
                    $D->{village} = $info[1];
                    $D->{location} .= " $info[1]"; # station village
                }
                if ( defined $info[3] ) {
                    if( $info[3] !~ $info[1] ) {
                        $D->{location} =~ s/,\s*//;
                        $D->{location} .= " (gem. $info[3])";
                    }
                }
                $D->{organisation} = "BdP";
                $D->{organisation} = $info[2] if defined $info[2];
                $D->{href} = '';
                $D->{href} = $info[4] if defined $info[4];
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
    'at_pm25' => 'p/dm\\u00B3',
    'at_pm10' => 'p/dm\\u00B3',
    'luchtdruk' => 'pHa',
    'pressure' => 'pHa',
    'rv'       => '\\u0025',
    'humidity' => '\\u0025',
    'temp'     => '\\u2103',
    'temperature'     => '\\u2103',
);
# convert sensor type to measurement units
sub ConvertS2U {
    my ($sense) = @_; my $s = lc($sense);
    $s =~ s/<[^>]*>//g; $s =~ s/[^_a-z0-9]//g;
    return $sense if not defined $Sense2Unit{$s};
    return $Sense2Unit{$s};
}
            
# Intro to use chrt with button or not
sub InsertTableHdr {
    my ($buts, $pols) = @_; my @BUTS = @{$buts}, @POLS = @{$pols};
    my $but = $buttons;
    for( my $i =0; $i <= $#BUTS; $i++ ) {
        $BUTS[$i] =~ s/pm([0-9]+)/PM$1/g; $BUTS[$i] =~ s/PM([0-9]+)/PM<sub>$1<\/sub>/g;
        $BUTS[$i] =~ s/<sub>25/<sub>2.5/g;
        #$BUTS[$i] =~ s/.*\|/ en /; $BUTS[$i] =~ s/\|/, /g; 
        $BUTS[$i] =~ s/\|.*//;
        $POLS[$i] =~ s/\|(dtemp|pm_[0-9]+)//g;
        $POLS[$i] =~ s/temp/temperatuur/; $POLS[$i] =~ s/rv/rel.vochtigheid/;
        $POLS[$i] =~ s/[\)\(]//g; $POLS[$i] =~ s/\|/, /g;
        $POLS[$i] =~ s/(.*), /$1 en /;
        $POLS[$i] =~ s/PM([0-9]+)/PM<sub>$1<\/sub>/ig;
    }
    my $measurements = join(', ',@POLS); $measurements =~ s/(.*), /$1, en /;
    return 'In de legendum kan door aanklikken een grafiek voor een enkele sensorkit meting aan- of uitgezet worden. Klik "toon" aan voor het aan- of uitzetten van de betreffende grafiekweergave.<br />De chart biedt de mogelijkheid om met de "slider" (onder in de chart) in een bepaalde periode van de grafiek in of uit te zoomen. Door te schuiven over de tijdas kan de weergave periode veranderd worden.' if $#BUTS < 1;

    return '<table width=100% border=0 bordercolor=white><tr><td style=\'padding-right:25px\'><div class="table-button" title="Druk (click) op deze knop om van '.
    join(' of ',@BUTS) .
    ' weergave te wisselen tav de metingen voor ' . $measurements .'"><span style="position:relative;left:1px;top:-1px;font-size:9px;">'.
    join('&nbsp;&nbsp;',@BUTS) .
    '</span><button id="tableButton"><div style="margin-right:-4px;font-size:12px">'.
    $BUTS[0] .
    '</div></button><span style="position:absolute;top:-20px;left:+8px;text-shadow:none;text-weight:bold;color:#3b5d9c">keuzeknop</span></div></td><td>De onderstaande tabel met de recente meetwaarden in de regio.<br />Met de keuzeknop kan gewisseld worden van type fijstof: ' .
    join(' of ',@BUTS) .
    '.</td></tr><tr><td colspan=2>In de legendum kan door aanklikken de grafiek van een bepaalde lokatie aan- of uitgezet worden. Klik "toon" aan voor het aan- of uitzetten van de betreffende grafiekweergave.<br />Zo nodig kan de legendum door met de linker muisknop op de plaats :: ingedrukt te houden, verplaatst worden.<br />De grafiek heeft de mogelijkheid om een bepaalde periode van de grafiek te laten zien. Met de "slider" kan de periode vergroot, verkleind of verschoven worden.</td></tr></table><br />'
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
        font-size:12px;
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
    my $string = "
    \$('#${nr}SENSORS').highcharts('StockChart',{
            rangeSelector: {
            selected: 1,
            height: 40,
            buttonPosition: { y: 2 },
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
                'stroke-width': 0, r: 8,
                style: {
                    color: '#37508f',
                    fontWeight: 'bold',
                    fontSize: '70\%'
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
            inputPosition: { y: -23 },
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
            y: 40-30,
            align: 'center',
            style: {
                fontSize: '120\%',
                textShadow: '1px 1px 3px #777777',
                color: '#314877'
            }
          },
          subtitle: {
           text: ${nr}subtitle,
            y: 40-30+14,
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
            y: 60,
            itemStyle: { fontSize: '75\%', color: '#314877' },
            itemHiddenStyle: { color: '#4a6396' },
            verticalAlign: 'center',
            floating: true,
            draggable: true,
            title: {
                text: '::'
            },
            enabled: true,
            labelFormatter: function() { if( this.visible ) { return this.name ; } else { return this.name + ' (toon)' }; }
        },
        credits: { enabled: false },
        tooltip: {
            shared: true,
            valueDecimals: 1,
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
    return \$string;
}
 
# generate one chart for a set of series
sub ChartSerie {
    my ($StNr, $data) = @_;
    my $id = "C$StNr";
    my $series = '';
    for( my $i = 0; $i <= $#{$data}; $i++ ){
        my $ugm3 = '\\u00B5g/m\\u00B3';
        my $visible = 1;
        $visible = 0 if not defined $data->[$i]{label};
        # pm2.5 pollutants are all visible
        # $visible = 1 if (defined $data->[$i]{sense}) && ($data->[$i]{sense} =~ /pm_25/);
        # graph not visible if not vuurwerk (VW20NN)  sensor kit
        $visible = 0 if $data->[$i]{table} !~ /^VW[0-9]{4}_/i;
        my $corr = '';
        if( ($data->[$i]{sense} =~ /pm_?(10|25)/i) && (defined $data->[$i]{CorrectME}) ) {
            my $name = $data->[$i]{CorrectME}; $name =~ s/.*_//g;
            # for now only rv TO DO: extent this with a row of indicators!
            if( $data->[$i]{sense} =~ /pm_?(10|25)/i ) {
                $series .= sprintf("
            { type: 'spline', pointStart: ${id}start%d, pointInterval: ${id}unit%d,
              name: ${id}title%d + ' gecorrigeerd',
              data: correctPMs('%s',${id}data%d,humrv%s),
              lineWidth: 1+%d, visible: %s, zIndex: 2,
              tooltip: { valueSuffix: ' %s' },
              yAxis: %d,
              pointPlacement: 'between', marker:{ radius: 1+%d }
            },\n",
                $i,$i,
                $i,
                $data->[$i]{sense}, $i, $name,
                (defined $data->[$i]{label}?1:0), ($visible?'true':'false'),
                (defined $data->[$i]{pol}?ConvertS2U($data->[$i]{pol}):$ugm3),
                (defined $data->[$i]{label}?0:1),
                (defined $data->[$i]{label}?1:0) );
                $visible = 0;
            }
            $corr = ' ongecorrigeerd';
        }
        my $datavar = sprintf("${id}data%d", $i);
        if( ($data->[$i]{sense} =~ /(rv)$/i) && (defined $RVstations{$data->[$i]{table}}) ){
            $datavar = $data->[$i]{table}; $datavar =~ s/.*_//g;
            $datavar = "humrv$datavar";
        }
        $series .= sprintf("
            { type: 'spline',
              pointStart: ${id}start%d, pointInterval: ${id}unit%d,
              name: ${id}title%d + '$corr',
              data: $datavar,
              lineWidth: 1+%d,
              visible: %s,
              zIndex: 2,
              tooltip: { valueSuffix: ' %s' },
              yAxis: %d,
              pointPlacement: 'between',
              marker:{
                radius: 1+%d
              }
            },\n",
                $i,$i,$i,(defined $data->[$i]{label}?1:0),
                ($visible?'true':'false'),
                (defined $data->[$i]{pol}?ConvertS2U($data->[$i]{pol}):$ugm3),
                (defined $data->[$i]{label}?0:1),
                (defined $data->[$i]{label}?1:0) );
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
    my $Tbands = ''; $Tbands = 'B_' if $bands;
    return "    { 
            visible: false,
            linkedTo: $yAxis{$Tbands.$units}
            },\n" if defined $yAxis{$Tbands.$units} ;
    my $plotType;
    $plotType = "
            plotLines: [{ // zero plane
                value: 0,
                color: '#BBBBBB',
                width: 1,
                zIndex: 2
            }]," if not $Tbands;
    $plotType = "
            plotBands: [
                $bands
            ]," if $Tbands;
    $lastLoc++;
    my $opposite = 'true';
    $opposite = 'false' if ($lastLoc % 2);
    my $visible = 'true';
    $visible = 'false' if $lastLoc > 3; # for now no more as 4 visible axes
    my $textAlign = 'right';
    $textAlign = 'left' if ($lastLoc % 2);
    my $rotation = '0' ; $rotation = '270' if MyLength($units) >= 5;
    my $x = 0; $x = 5 if $opposite eq 'true';
    my $y = 0; $y = 5 if MyLength($units) >= 5;
    my $offset = int(($lastLoc+1)/2 + 0.5);
    my $ceilFloor = '';
    $ceilFloor = 'floor: 0, ceil: 100, max: 100;' if $units eq ConvertS2U('rv');
    my $newY = "
          { title: {
                text: '$units',
                offset: -10,
                align: 'high',
                rotation: $rotation,
                style: {
                    fontSize: '10px',
                },
                textAlign: '$textAlign',
                x: -20+7*$x, // -1*$y,
                y: -5-3*$y,
            },
            labels: {
                format: \"{value}\",
                align: '$textAlign',
                style: {
                    fontSize: '10px'
                },
                x: 0+2*$x
            },
            $plotType
            offset: -15*$offset,
            showLastLabel: false,
            maxPadding: 0.3,
            opposite: $opposite,
            tickInterval: 10,
            visible: $visible,
            gridLineColor: (Highcharts.theme && Highcharts.theme.background2) || '#F0F0F0'
          },\n";
    $yAxis{$Tbands.$units} = $nr;
    return $newY;
}

# generate yAxis for a set of series
sub ChartyAxis {
    my ($data, $bands) = @_; $yAxis = '';
    for( my $i = 0; $i <= $#{$data}; $i++) {
        my $units = ConvertS2U($data->[$i]{pol});
        $yAxis .= newYaxis($i, $units, ((not defined $data->[$i]{label})? $bands : ''));
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
    return '' if not correctME;
    return "
<p>Samen met het RIVM wordt gekeken of de procedures voor het meten van PM fijnstofwaarden verbeterd kunnen worden.
Als experiment worden de PM<sub>10</sub> fijnstofwaarden gecorrigeerd. Door toepassing van de correctie worden de metingen vergelijkbaar met de referentie fijnstofmetingen van een RIVM/PLIM meetstation in de buurt.
Door te clicken met de muis op 'ongecorrigeerd' worden ook de ongecorrigeerde waarden in de grafiek getoond.
Het blijkt dat de metingen van Hoogheide verschoven zijn in de tijd. Hierop is ook gecorrigeerd.
<br />Pas op: Voor de PM<sub>2.5</sub> fijnstofwaarden wordt in afwachting van een betere correctie factor nog dezelfde correctie toegepast.
</p>
    ";
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

sub Generate {
    my @stations = @_; my @DATA;
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
        $BUTTONS[$i] =~ s/pm/PM/; $BUTTONS[$i] =~ s/PM25/PM2.5/;
        $BUTTONS[$i] =~ s/^(.{1,5}).*/$1/;  # max 5 chars as button name
        $BUTTONS[$i] =~ s/\s//g;
        $BUTTONS[$i] =~ s/[^a-zA-Z0-9]//g;
        $POLLUTANTS[$i] =~ s/PM/pm/; $POLLUTANTS[$i] =~ s/\s//g;
        $POLLUTANTS[$i] =~ s/pm(10|25)/pm$1|pm_$1/g;
        $POLLUTANTS[$i] =~ s/temp/temp|dtemp/;
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
    my $timeshift = 0;  # we try to start all plot intervals on same minute
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
        $timeshift = $data->[0]{first}%3600 if $i == 0;
        $data->[$i]{first} -= ($data->[$i]{first}%3600) - $timeshift; # shift graph
        my $loc = $data->[$i]{location}; # $loc =~ s/^(.*)\s*,\s*(.*)$/$1 \($2\)/;
        my $S = $data->[$i]{pol}; $S = uc($S) if $S !~ /(ws|rv|temp|luchtdruk)/;
        $data->[$i]{sense} = $data->[$i]{pol};
        $S =~ s/PM_/PM/; $S =~ s/PM25/PM2.5/;
        $S =~ s/([A-Z])([0-9\.]+)/$1<span style="font-size:80\%">$2<\/span>/g;
        $data->[$i]{pol}=$S;
        if( $loc ne $prev ) {   # create a text list in Dutch language
            if( defined $data->[$i]{label} ){ # sensor kits have labels defined
                if ( defined $data->[$i]{village} ) {
                    if( not $region ) {
                        $region = $data->[$i]{village} ;
                    } elsif ( $region !~ /$data->[$i]{village}/ ) {
                        $region =~ s/ en /, /; $region .= ' en ';
                        $region .= $data->[$i]{village};
                    }
                }
                if ( $Slbls[$j] ) { $Slbls[$j] =~ s/ en /, /; $Slbls[$j] .= ' en '; }
                my $strt = $loc; $strt =~ s/\s+[0-9].*//; # hide street nr
                if( $data->[$i]{href} ) {
                    $Slbls[$j] .= "<a href='/$data->[$i]{href}' alt='details sensorkit'>$strt</a>";
                } else {
                    $Slbls[$j] .= $strt;
                }
                if( not $Olbls[$j] ) { $Olbls[$j] = $data->[$i]{organisation}; }
                if( $data->[$i]{organisation} !~ /$Olbls[$j]/ ) {
                    $Slbls[$j] .= " van de organisatie $data->[$i]{organisation}" if defined $data->[$i]{organisation}; 
                }
            } else {
                if ( $Mlbls[$j] ) { $Mlbls[$j] =~ s/ en /, /; $Mlbls[$j] .= ' en '; }
                my $strt = $loc; $strt =~ s/\s+[0-9].*//; # hide street nr
                if( $data->[$i]{href} ) {
                    $Mlbls[$j] .= "<a href='/$data->[$i]{href}' alt='details sensorkit'>$strt</a>";
                } else {
                    $Mlbls[$j] .= $strt;
                }
                $Mlbls[$j] .= " van de organisatie $data->[$i]{organisation}" if defined $data->[$i]{organisation}; 
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
        $RSLT=sprintf("Debugmodus: HTML page ready output on %s, working dir %s\n",$output,WDIR);
    } else {
        $output .= '.html' if $output !~ /^\/dev\//;
        $RSLT=sprintf("File=%s with compressed JS script. Working directory: %s\n",$output,WDIR);
    }
    open $OUT, ">$output" || die ("Cannot open ${output} for generated HTML code\n");

    my $indoc = 0; my $skip = 0; my $inscript = 0;
    while( TRUE ){            # parse template file
        INPUT:
        if ( $IN ) { $_ = <$IN> ; }
        else { $_ = <main::DATA> }
        last if not $_;
        print STDERR $_ if $debug > 2;
        if( /<body/ ){ $indoc = 1;  next if not $debug; }
        if( /<\/body/ ){ $indoc = 0;  next if not $debug; }
        next if (not $debug) && (not $indoc);
        if( (/<script\s/) && $indoc ){
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
                    return pm/(4.56 * Math.pow(100-rv,-0.65));
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
                    # TO DO if more indicators are in correction scheme
                    # javascript does not allow _-char in names
                    # foreach my $S (keys %{$RVstations{$stat}}) {
                    #     next if $S eq 'cnt';
                    #     my $S_ = $S; $S_ =~ s/_//g;
                    #     MyPrint($inscript,sprintf("var humrv%s%s = %s;\n", $S_, $cwstat_name,
                    #         $RVstations{$stat}{$S}))
                    #         if $RVstations{$stat}{cnt};
                    # }
                }
              }
              for( my $j = 0; $j <= $#DATA; $j++ ) {
                my $data = $DATA[$j];
                # generate the javascript variables and data for graphs
                MyPrint($inscript,sprintf("var C%dtitle = '%s';\n", $j, $title));
                # subtitle if defined will overwrite region
                MyPrint($inscript,sprintf("var C%dsubtitle = '%s%s';\n", $j,
                    $subtitle ? $subtitle: '',' regio '.($myRegion ? $myRegion : $region)));
                for( my $i = 0; $i <= $#{$data}; $i++ ){
                    my $timeShift = 0;
                    $timeShift = $TimeShifts{$data->[$i]{table}}
                        if defined $TimeShifts{$data->[$i]{table}};
                    MyPrint($inscript,sprintf("var C%dstart%d = %d*1000 + (%d*1000);\n", $j, $i, $data->[$i]{first},$timeShift));
                    MyPrint($inscript,sprintf("var C%dunit%d = %d*1000;\n", $j, $i, $data->[$i]{unit}));
                    if( $correctPM && (defined $RVstations{$data->[$i]{table}})
                        && (defined $RVstations{$data->[$i]{table}}{$data->[$i]{sense}}) ){
                        my $name = $data->[$i]{table}; $name =~ s/.*_//g;
                        # extend this not only for rv
                        $data->[$i]{data} = "humrv$name";
                    }
                    MyPrint($inscript,sprintf("var C%ddata%d = %s;\n", $j, $i, $data->[$i]{data}));
                    if( defined $data->[$i]{label} ) {
                        MyPrint($inscript,sprintf("var C%dtitle%d = '%s (%s)';\n", $j,
                            $i,
                            defined $data->[$i]{street} ? $data->[$i]{street} : $data->[$i]{label},
                            $data->[$i]{pol}));
                    } else {
                        my $loc = $data->[$i]{location};
                        $loc =~ s/,\s[A-Za-z\s]+//;
                        MyPrint($inscript,sprintf("var C%dtitle%d = '%s (%s)';\n",
                            $j, $i, $loc,$data->[$i]{pol}));
                    }
                }
              }
            }
            $skip++ if $sw =~ /GLOB/; next;
        } elsif ( /^(\/\/|<!--\s+)END\s+(GLOB|DOM)/ ) {
            $skip = 0;
            next;
        }
        if( /^(\/\/\s*|<!--\s+)START\s+([a-zA-Z0-9]*).*/ ){ # insert new values
            my $type = $2; $skip++;
            if( $type =~ /regio/ ){              # for the region text
                MyPrint($inscript, $region . "\n");
            } elsif( $type =~ /stations/ ){      # all stations text
                MyPrint($inscript, "$Mlbls[0]\n");
            } elsif( $type =~ /organisation/ ) { # all others from organisation
                if( $Olbls[0] ) { 
                    MyPrint($inscript, "van organisatie $Olbls[0]\n");
                }
            } elsif( $type =~ /locations/ ){     # all locations of sensors text
                MyPrint($inscript, "$Slbls[0]\n");
            } elsif( $type =~ /type/ ) {         # class of pollutants
                MyPrint($inscript, "($poltype)\n");
            } elsif( $type =~ /updated/ ){       # last update of chart
                MyPrint($inscript, strftime("%Y-%m-%d %H:%M\n",localtime(time)));
            } elsif( $type =~ /Legend/ ) {       # insert button Legend off/on
                MyPrint($inscript, '<button id="update-legend" class="autocompare">legendum uit/aan</button>' . "\n")
                    if $nrLegends > 4;
            } elsif( $type =~ /first/ ){         # first date in chart
                MyPrint($inscript, $first . "\n");
            } elsif( $type =~ /last/ ){          # last date in chart
                MyPrint($inscript, $last . "\n");
            } elsif( $type =~ /regio/ ){         # region text
                MyPrint($inscript, $region."\n");
            } elsif( $type =~ /straat/ ){        # street name text
                MyPrint($inscript, 'straat naam'."\n");
            } elsif( $type =~ /revision/ ){      # script revision nr and date
                MyPrint($inscript, $Version."\n");
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
                MyPrint($inscript, $string);
            } elsif( $type =~ /HIGHCHART/ ) {
                for( my $i = 0; $i <= $#BUTTONS; $i++ ) {
                    my $str = sprintf("<div id=\"C${i}SENSORS\" style=\"width:510px; height:340px;margin:0 auto\"></div>");
                    $str = sprintf("<div class=\"C${i}table\" id=\"C${i}table\" style=\"display: %s\">%s</div>\n", ($i == 0? 'block' : 'none'),$str) if $#BUTTONS > 0;  
                    MyPrint($inscript,$str);
                }
            } elsif( $type =~ /SERIES/ ){     #one graph
              for( my $j = 0; $j <= $#DATA; $j++ ) {
                my $data = $DATA[$j];
                MyPrint($inscript,InsertHighChartGraph("C$j",$BUTTONS[$j],ChartSerie($j,$data),ChartyAxis($data,plotBands($AQI))));
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
    system("/bin/chgrp $wwwgrp $output") if $output =~ /^\//;
    chmod 0644, $output;
    print STDERR $RSLT if $verbose;
    return 0;
}

die "Cannot access database $mydb. Correct user/password?\n" if not Check_DB();

if( $#ARGV >= 0 ) {     # at least 2 sensor locations
    Generate(@ARGV,$reference);
} else {                # default
    Generate(LOCATION,$reference);
}

__DATA__
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
                months: ['januari','februari','maart','april','mei','juni','juli','augustus','september','october','november','december'],
                shortMonths: ['jan','feb','mrt','apr','mei','jun','jul','aug','sep','oct','nov','dec'],
                weekdays: ['zondag','maandag','dinsdag','woensdag','donderdag','vrijdag','zaterdag'],
                shortWeekdays: ['zo','ma','di','wo','do','vr','za'],
                rangeSelectorTo: 'tot',
                rangeSelectorFrom: 'van',
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
</span>.<br /><span valign=bottom style='font-size:85%;color:#2e3b4e;text-align:right'>Gebaseerd op data van o.a. <a href="https://www.luchtmeetnet.nl/stations/limburg/alle-gemeentes/alle-stoffen" title="Bezoek website met actuele metingen">het RIVM</a>
van
<!-- START first -->
zo 11 dec 01:13
<!-- END first -->
uur tot
<!-- START last -->
ma 12 dec 04:26
<!-- END last -->
uur.
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
<tr><td colspan=5 style='vertical-align:top;text-align:right;padding-right:10px;padding-bottom:6px;font-size:70%'>geactualiseerd op 
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
in vergelijking met de grafiek van metingen met de eenvoudiger en betaalbare Nova SDS011 sensor
<!-- START organisation -->
<!-- END organisation -->
op de locatie
<!-- START locations -->
Fake Adres, Location ERROR (Fake)
<!-- END locations -->
. Pas op: hoewel de grafieken van de landelijke meetstations met referentie apparatuur en de eenvoudiger sensors elkaar redelijk lijken te volgen is de schaal van de grafieken anders: aan de rechterzijde wordt de schaal vermeld van de metingen van de referentie apparatuur, links staat de schaal van de eenvoudiger sensoren vermeld.
</p>
<!-- START correctPM -->
<!-- END correctPM -->
<p>
De Nova fijnstof sensor telt het aantal fijnstofdeeltjes (PM<span style="font-size:80%">2.5</span> en PM<span style="font-size:80%">10</span>) in een minuut in een periode van telkens 5 minuten. De fijnstofmeting wordt door de Nova fabrikant vervolgens omgerekend naar het gewicht van de deeltjes in &micro;g/m&sup3;. In de omrekening wordt geen rekening gehouden met relatieve vochtigheid, regen en andere invloeden. De fijnstof metingen van de RIVM/PLIM landelijke meetstations zijn ook gewichtsmetingen (&micro;g/m&sup3;) van gemiddelden per uur. De apparatuur van het landelijk meetstation is geijkt. 
<br />Tav de meetgegevens van goedkope sensoren in deze testperiode zijn wel onderling gecalibreerd.
Om de hoeveelheid data te bepreken zijn de meetwaarden geaggredeerd - een gemiddelde over een periode van 30 minuten voor de sensors en 60 minuten voor de landelijke meetstations. De getoonde periode is de afgelopen 3 dagen. Eens per uur wordt de grafiek ververst.
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
Revision 100 Zondag 15 januari 2017
<!-- END revision -->
</p>
</body>
</html>
