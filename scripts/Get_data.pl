#!/usr/bin/perl -w

# This package will only download data from various websites:
# extract data from the Provincial Limburg (RUD Z-Limburg), RIVM/LMN website
# and/or Nord Rhein West Falen NRWF(DE) website.
# and stores the data into database.
# Use --help argument to obtain the different functions.
# Use the companion shell script Check_DB.sh to get various reports
# and diagrams.
# All access info is based in this script. The Check_DB.sh depends on it.
# Automatically add DB tables and coulmns to the database when needed.
# Create and update the RRA database as well with the data found.
# The database will automatically be created, but needs user credits to do so.

# Arguments is basically either a website dump file or a date to extract data
# If present an anonyous proxy will be used 
# and as well a random Agent string (leased # from robots) will be used
# to hide the origin a bit.
#
# See the "use ..." statements to detect missing Perl packages.
# Once run do not change the constants anymore.
#

# $Id: Get_data.pl,v 8.5 2020/04/10 12:09:41 teus Exp teus $
my $Version = '$Revision: 8.5 $, $Date: 2020/04/10 12:09:41 $.';
$Version =~ s/\$//g;

# 
# Copyright (C) 2014, Teus Hagen, the Netherlands
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
#

use Env qw(HOME DBUSER DBPASS DBHOST);	# for working from HOME dir, and DB credits
use feature "state";		# some routines keep own state variables
use POSIX qw(strftime);
use Time::Piece;		# need to parse time strings
use autodie;
use 5.010;
use LWP::UserAgent;		# for direct http access
use URI::Escape;
use Getopt::Mixed;		# need to parse command line arguments
# need next for RIVM/NSL file parsings
use File::Spec::Functions qw(splitpath); # need for path/file_name
use IO::File;			# need this for uncompress files
use IO::Uncompress::Unzip qw($UnzipError); # zip file uncompress
use File::Path qw(mkpath);	# create dirs when needed for zip and xls
use Spreadsheet::ParseExcel::Simple;     # parse xls files
use Spreadsheet::XLSX;		# parse xlsx files, need Windows convert
use Text::Iconv;
no warnings 'experimental';	# no warnings on my $_ usage


# database access
# next should go to INI file
use constant {
					# Default DB credentials
	USER => 'someuser', PASSWD => 'somepass', HOST => 'localhost',
	DB	  => 'luchtmetingen',	# default database
        LOCATION  => '06',              # default location nr
	DBTBL	  => 'HadM',		# default table of hourly measurements
					# extent DBTBL with following
	DAY_AVG	  => '_DayAVG',		# table dayly averages
	MAX_8HRS  => '_Max8HRS',	# table with max of 8 hrs avg on a day
	LOCATIONS => './locations.pl',	# perl database with locations details
	MAX_HIST  => 30,		# missing sensors max days
	MIN_HIST  => 7,			# min days report sensors are missing
	DATUMS	  => '_datums',		# table with date/time of collected measurment
	NORM	  => '_normalized',	# normalized database file name extention
	RRD_DIR	  => 'rrd_data/',	# directory with rrd databases
	RRD	  => 'luchtkwaliteit',	# default RRD database base filename
	MSMNTS	  => 24,		# amount of measurments per day
	FALSE	  => 0,
	TRUE	  => 1,
	WDIR	  => '/webdata/luchtmetingen/',   # working directory
	# next needed for RIVM/NSL data collection (Feb 2020 deprecated)
	ZIPDIR	  => 'RIVM/www.lml.rivm.nl',	       # dir monthly zip files, deprecated
	# next will hold PM xls 1992-2012 file and optional other xls files.
	# need to download as rivm.url/rivm.action/XLS2013
	XLSDIR	  => 'RIVM/xls',	# dir with xls and xlsx files, deprecated
	# if you change the next please see also get_data function!
	XLS2013   => 'Fijn stof (PM10) 1992_2012.xls', # PM 10 values RIVM, deprecated
};

# make sure we work in a well known dir
my $WDir     = WDIR;
my $rrd      = RRD_DIR . RRD;	# the file name of the RRD database
my $myhost   = HOST;	# mysql server
my $mydb     = DB;	# mysql database name
my $myuser   = USER;	# mysql user
my $mypass   = PASSWD;	# mysql password
my $mytbl    = DBTBL;   # mysql dflt table

my %locations;  # hash table with details of measurement locations from file or DB
my $AQI_Indices;     #  ref to  hash table datastructure from AQI.pl
my $AQI_enabled = '(aqi|lki)' ; # enable creation/updates of these (max) AQI columns
my $AQI_qual = 1;    # the aqi columns with color and message are generated

# 
# this file will act as a central perl type of location info database
# info is collected from:
# www.luchtkwaliteit.limburg.nl location nr < 100
# www.lml.rivm.nl website (only regional stations nr >= 100
# TO DO: if not cached try to get the location info from the database stations table
# next declaration is due to somehow the require locations fails on some machines
%locations = (
    # bron: luchtkwaliteit.limburg.nl, binary search for first and last dates
    '01' => {
	name => "Buggenum", organisation => 'RUD', id => 'NLBUG01',
	table => 'Bug',
	},
    '02' => {
	name => "Geleen Vouershof", organisation => 'RUD', id => 'NL50002',
	table => 'GV',
	},
    '03' => {
	name => "Geleen Asterstraat", organisation => 'RUD', id => 'NL50003',
	table => 'GA',
	},
    '04' => {
	name => "Maastricht A2-Nassaulaan", organisation => 'RUD', id => 'NL50004',
	table => 'MA2',
	},
    '05' => {
	name => "Roermond", organisation => 'RUD', id => 'NLROE05',
	table => 'Roer',
	},
    '06' => {
	name => "Horst aan de Maas", organisation => 'RUD', id => 'NL50006',
	table => 'HadM',
	},
    '07' => {
	name => "Maastricht Hoge Fronten", organisation => 'RUD', id => 'NL50007',
	table => 'MHF',
	},
    '09' => {
	name => "Maastricht Kasteel Hillenraadweg", organisation => 'RUD', id => 'NL50009',
	table => 'MKH',
	},

    # locations from www.lml.rivm.nl/table status dd 2014/07/22
    # www.lml.rivm.nl/tabel/?data=YYYYMMDDHH.tabel
    # www.luchtmeetnet.nl/tabel?datatime=YYYY-MM-DD%20HH:00:00
    # will provide hourly unvalidated measurement values
    # but one day measurement download will cause 24 website accesses
    # for dates older as 2 months there are
    # monthly validated data: less traffic but 2 months latency
    # for monthly validated data up to 2012 there is one xls file
    # location numbers for RIVM/NSL stations are >= 100
    '107' => {
        name => 'Posterholt-Vlodropperweg', organisation => 'RIVM', id => 'NL00107',
        table => 'NL10107',
    },
    '131' => {
        name => 'Vredepeel-Vredeweg', organisation => 'RIVM', id => 'NL00131',
        table => 'NL10131',
    },
    '133' => {
        name => 'Wijnandsrade-Opfergeltstraat', organisation => 'RIVM', id => 'NL00133',
        table => 'NL10133',
    },
    '066' => {
	name => 'Nettetal-Kaldenkirchen', organisation => 'NRWF', id => 'DENW066',
	table => 'NETT',
    },
);
if( -f $WDir . LOCATIONS ){
    my $inc = $WDir . LOCATIONS;
    require($inc);
}

# available websites to collect data
my %datahosts = (
	# website is old from April 2014, post action
	# website is redirecting to luchtmeetnet-limburg from 22 aug 2014
	first => {
	     url => 'www.luchtmeetnet-limburg.nl',
	     protocol => 'http',
	     action => '/ajax/measurement/measurement.asp',
	     content => 'h=0&s=%s&d=%d&c=',
	     organisation => 'RUD',
	     # url => 'luchtkwaliteit.limburg.nl',
	     # action => '/meetwaarden_popup/dagwaarden_popup.asp/',
	     # content => 'station=%s&dag=%d',
	},
	# website initiated from May 2014, post action
	second => {
	     url => 'www.luchtmeetnet-limburg.nl',
	     protocol => 'https',
	     action => '/ajax/measurement/measurement.asp',
	     content => 'h=0&s=%s&d=%d&c=',
	     organisation => 'RUD',
	},
	# validated data, per month, > 1 month behind now, get action
        # if still works on luchtmeetnet is not tested
	rivm => {
	     # url => 'www.lml.rivm.nl',
	     # url => 'www.luchtmeetnet.nl', # till 10 Febr 2020
             url => 'api.luchtmeetnet.nl',   # from 10 Febr 2020 use Open Data API
	     protocol => 'http',
	     # action => '/gevalideerd/data/',	# YYYYMM.zip till 10 Febr 2020
             # action => '/open_api/stations/STATION_ID/measurements?', # from 10 Febr 2020
             action => '/open_api/',
	     # content => 'validated',
	     organisation => 'RIVM',
	},
	# not validated data, max 2 month old, one page per hour, get action
        # changed due to other server nov 2019
        # changed to Open Data API effective 10th Febr 2020
	RIVM => {
	     # url => 'www.lml.rivm.nl',
	     # url => 'www.luchtmeetnet.nl', # till 10 Febr 2020
             url => 'api.luchtmeetnet.nl',
	     protocol => 'https',
	     # action => '/tabel',		# ?date=YYYYMMDDHH.tabel
             # action => '/open_api/stations/STATION_ID/', # from 10 Febr 2020
             action => '/open_api/',
	     # content => 'not validated',
	     organisation => 'RIVM',
	},
	# not validated data, per day, sliding average, only today since 14 Aug 2015
	NRWF => {
	     url => 'www.lanuv.nrw.de',
	     protocol => 'http',
	     #action => '/luft/temes',		# MMDD/ID.htm e.g. ID=NETT
	     action => '/fileadmin/lanuv/luft/temes',	# heut/ID.htm e.g. ID=NETT
	     # content => 'not validated',
	     organisation => 'DENRWF',
	     # thanks to Heike.ElGamal from lanuv.nrw.de 2015-09-23
	     # dayly averages stations NRW checked for 2014 and 2015
	     # http://www.lanuv.nrw.de/fileadmin/lanuv/luft/temes/YYYY/moMM/tagwert/DDsm.xls
	     # monthly data stations NRW for 2014 and 2015
	     # http://www.lanuv.nrw.de/fileadmin/lanuv/luft/temes/YYYY/moDD/tab.xsl
	     # another website with German day averages
	     # pollutant: PM1, NO2, O3, SO2, NO2,
	     # data types: 1TMW day max,  1SMW hour average, 1TMW one day average
	     # http://www.umweltbundesamt.de/luftdaten/data.csv?pollutant=PM1&data_type=1TMW&date=20150712&dateTo=20150929&station=DENW066
	     # http://www.umweltbundesamt.de/luftdaten/stations/locations.csv?pollutant=NO2&data_type=1SMW&date=20150919&hour=18&statename=&state=
	     # from 26 of October 2015 CSV file per sensor
	     # dayly for previous period of 365 days till yesterday
	     # of hourly validated measurements (; separated CSVC file).
	     # URL http://www.lanuv.nrw.de/fileadmin/lanuv/luft/temes/SENSOR.csv
	     # where SENSOR is NO, NO2, O3, PM10, SO2, LTEM, RFEU, WGES, WRI
	     # data per location for all sensors upto end of last year:
	     # http://www.lanuv.nrw.de/fileadmin/lanuv/luft/temes/aeltere_daten/NETT_alt.csv
	     # where NETT is the station identifier
	},
);

# denoted first  and last date of measurements
# TO DO: this should go into a database table
#	details can be obtained from websites as well (TO DO)
my $first = 0;			# first date when values are available
my $last = time() + (24*60*60);	# last date when all sensors are operational
# called with arguments: host, action, station number, day yyyy/[m]m/[d]d
# 
# try to hide non browser behaviour
my %agents = (
    'dotbot' => "Mozilla/5.0 (compatible; DotBot/1.1; http://www.opensiteexplorer.org/dotbot, help\@moz.com)",
    'butterfly' => "Mozilla/5.0 (Butterfly)",
    'baidu' => "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",
    'slurp' => "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)",
    'google' => "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    'opera' => "Opera/8.01 (Windows NT 5.1; U; nl)",
    'iphone' => "Mozilla/5.0 (iPhone; CPU iPhone OS 7_1_2 like Mac OS X) AppleWebKit/537.51.2 (KHTML, like Gecko) Version/7.0 Mobile/11D257 Safari/9537.53",
    'ipad' => "Mozilla/5.0 (iPad; CPU OS 7_1_2 like Mac OS X) AppleWebKit/537.51.2 (KHTML, like Gecko) Version/7.0 Mobile/11D257 Safari/9537.53",
    'baidu' => "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",
#    'spinn' => "Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.0.19; aggregator:Spinn3r (Spinn3r 3.1); http://spinn3r.com/robot) Gecko/2010040121 Firefox/3.0.19",
    'ahrefsbot' => "Mozilla/5.0 (compatible; AhrefsBot/5.0; +http://ahrefs.com/robot/)",
    'msnbot' => "msnbot-media/1.1 (+http://search.msn.com/msnbot.htm)",
    'majestic' => "Mozilla/5.0 (compatible; MJ12bot/v1.4.4; http://www.majestic12.co.uk/bot.php?+)",
    'windows' => "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:18.0) Gecko/20100101 Firefox/18.0",
);

$myhost      = $DBHOST if defined $DBHOST;
$mydb        = $DB if defined $DB;
$myuser      = $DBUSER if defined $DBUSER;
if( $mypass =~ /somepass/ ){
    $mypass = '';
    $mypass = $DBPASS if defined $DBPASS;
}

my $dflt_hst = 'second'; # default datahost for Limburg (RUD) from Aug 2014
my $town     = "unknown";	# town of location (received from website)

my $location;	# location number, default '06' Horst aan de Maas
my $AQI      = 0;       # fill (>1) AQI DB tables, dflt: no fill or initiation (3)
my $LKI      = 1;       # if available in downloaded data get LKI values as component values

#<ESC>[{attr};{fg};{bg}m
#{attr} is one of following
#       0       Reset All Attributes (return to normal mode)
#       1       Bright (Usually turns on BOLD)
#       2       Dim
#       3       Underline
#       5       Blink
#       7       Reverse
#       8       Hidden
#{fg} is one of the following
#       30      Black
#       31      Red
#       32      Green
#       33      Yellow
#       34      Blue
#       35      Magenta
#       36      Cyan
#       37      White
#{bg} is one of the following
#       40      Black
#       41      Red
#       42      Green
#       43      Yellow
#       44      Blue
#       45      Magenta
#       46      Cyan
#       47      White
#
my  $WARNING = "WARNING:";
my  $ERROR = "ERROR:";
my  $ATTENT = "ATTENTION:";
sub isatty( ){
    no autodie; state $isatty = open(my $tty, '+<', '/dev/tty');
    return $isatty;
}

# changes originating from the command line
my $host;	# as provided from command line, default datahost
my $action;	# as provided from command line, action to post/get data

my $debug = 0;          # debug mode, default: off
my $onlyRRD = 0; 	# only update RRD database
my $verbose = 0;        # verbosity (e.g. wait messages) mode, default: off
my $quiet = 0;          # be quiet mode, truns verbose off, default: off
my $overwrite = 0;	# overwrite existing date measurement values
# statistics
my %DB_updates;		# amount of updates per table
my %DB_inserts;		# amount of data insertions in database per table
my %updates = ();	# amount of values updated in database per table
my $normalized = 0;	# default no correction of data handling
my @RRD_updates =(0,0); # statistics for RRD database handling
my @RRD_errors =(0,0);  # statistics for RRD database handling

my $content;		# collected data from post action of website

# mysql DB handles
use DBI;
my $mysql;

END {			# on exit close connections
    if( $mysql and $mysql != 1 ){ $mysql->disconnect(); $mysql = 0; }
}

# list content of locations hash table
sub print_location {
    my $loc = shift; my $rts = 1;
    state $once = 0;
    if( $loc !~ /^[0-9]{2,}$/ ){
        for my $l (sort { $a cmp $b } keys %locations ){
            $rts += print_location($l);
        }
	return $rts;
    }
    return 0 if not $locations{$loc};
    print STDOUT "\nDetails meetstation(s):\n" if not $once++;
    print STDOUT "\nLokatie:\t\t\t$loc\n";
    for my $l ("name","geolocation","organisation","table","first","last","sense" ){
        next if not defined $locations{$loc}{$l};
        next if not $locations{$loc}{$l};
        my $strg;
        if( $l =~ /^name$/ )
            { $strg = "\tPlaats/lokatie:\t\t$locations{$loc}{$l}"; }
        elsif( $l =~ /^geolocation$/ )
	    { $strg = "\tGeo coordinaten:\t$locations{$loc}{$l}"; }
        elsif( $l =~ /^organisation$/ )
            { $strg = "\tOrganisatie:\t\t$locations{$loc}{$l}";
		$strg .= ", ID: $locations{$loc}{'id'}" if defined $locations{$loc}{'id'};
	    }
        elsif( $l =~ /^table$/ )
            { $strg = "\tDatabase:\t\t$mydb, tabel $locations{$loc}{$l}"; }
        elsif( $l =~ /^first$/ )
            { $strg = "\tOperationeel sinds:\t$locations{$loc}{$l}"; }
        elsif( $l =~ /^last$/ )
            { $strg = "\tEinddatum op:\t\t$locations{$loc}{$l}"; }
        elsif( $l =~ /^sense$/ )
            { $strg = "\tType sensors: " . (join ", ", sort { $a cmp $b } keys %{$locations{$loc}{sense}}) if ( (keys %{$locations{$loc}{sense}}) > 0 ); }
        else
            { $strg = ""; }
        print STDOUT "$strg\n" if $strg;
    }
    if( defined $locations{$loc}{norm} ){
        for( my $nrm = $locations{$loc}{norm}; defined $locations{$loc}{$nrm}; $nrm-- ){
            print STDOUT "\tCalibratie factoren voor $nrm:";
            foreach my $pm ( sort { $a cmp $b } keys %{$locations{$loc}{$nrm}} ){
                my $strg = $pm; $strg =~ s/_//; $strg =~ s/25/2.5/;
                print STDOUT " $strg=$locations{$loc}{$nrm}{$pm}";
            }
            print STDOUT "\n";
        }
    }
    return $rts;
}


my %rrd_tables = (		# RRD database init arguments
	    'so' => "DS:so:GAUGE:7200:0:60",
	    'so2' => "DS:so2:GAUGE:7200:0:60",
	    'no' => "DS:no:GAUGE:7200:0:60",
	    'no2' => "DS:no2:GAUGE:7200:0:60",
	    'nh3' => "DS:nh3:GAUGE:7200:0:60",
	    'o3' => "DS:o3:GAUGE:7200:0:60",
	    'benzeen' => "DS:benzeen:GAUGE:7200:0:60",
	    'tolueen' => "DS:tolueen:GAUGE:7200:0:60",
# PM 10 minimum 1 and max 150 ug/m3 NEN 14207
	    'pm_10' => "DS:pm_10:GAUGE:7200:1:150",
# PM 2.5 minimum 1 and max 120 ug/m3 NEN 14207
	    'pm_25' => "DS:pm_25:GAUGE:7200:1:120",
	    'roet' => "DS:roet:GAUGE:7200:0:100",
	    'wr' => "DS:wr:GAUGE:7200:0:360",
	    'ws' => "DS:ws:GAUGE:7200:0:20",
	# temperature.rrd step 3600 secs, skip 2 hours, min 30, max 60
	#	store values for N times step size: 24 * one hour
	    'temp' => "DS:temp:GAUGE:7200:-30:60",
	    'rv' => "DS:rv:GAUGE:7200:0:100",
	    'luchtdruk' => "DS:luchtdruk:GAUGE:7200:900:1200",

	    'avg_pm_25' => "DS:avg_pm_25:GAUGE:7200:0:250",
	    'min_pm_25' => "DS:min_pm_25:GAUGE:7200:0:250",
	    'max_pm_25' => "DS:max_pm_25:GAUGE:7200:0:250",
	    'avg_pm_10' => "DS:avg_pm_10:GAUGE:7200:0:250",
	    'min_pm_10' => "DS:min_pm_10:GAUGE:7200:0:250",
	    'max_pm_10' => "DS:max_pm_10:GAUGE:7200:0:250",
    
);

use IPC::Open3;
my $RRDchild = 0;
my ($RRDin, $RRDout, $RRDerr);
use Symbol 'gensym';

# open pipe in and pipe out to rrdtool process
sub rrd_open {
    if( $RRDchild < 2 ){
	return(0) if $RRDchild;
	$RRDerr = gensym;
        if( !($RRDchild=open3($RRDin, $RRDout, $RRDerr, "rrdtool -")) ){
            print STDERR "Failed to open pipe to rrdtool.\n";
            $RRDchild = 1; return(0);
        }
        local $SIG{PIPE} = sub { die "Broken pipe to rrdtool"; };
    }
    return 1;
}
    
# get array of sensors defined in rrd file
{
  my %RRD_sens = ();
  # is sensor present in RRD database?
  sub rrd_sensor {
    my $file = shift;
    my $sens = shift;
    state $warned = 0;
    return 0 if not $sens;
    return 1 if defined $RRD_sens{$file} and defined $RRD_sens{$file}{$sens};
    return 0 if not -f $file . ".rrd" ;
    return 0 if not rrd_open();
    # try to get rrd defined sensors
    print $RRDin "info $file.rrd\n";
    while( <$RRDout> ){
        if( /ERROR:/ ){
            print STDERR "$ERROR Not a correct rrd file: ${file}.rrd\n$_"
                if not $warned++;
            return 0;
        }
	if( /ds\[([^\]]+)\].index\s+=\s+/ ){
	   $RRD_sens{$file}{$1} = 1;
	}
	last if /OK u:/;
    }
    return 1 if defined $RRD_sens{$file} and defined $RRD_sens{$file}{$sens};
    return 0;
  }
}

my @RRA = (0,0);
# create new RRD database
sub New_RRA {
    my $norm = shift; # normalized RRD database?
    my $new = shift; # true if explicitly create a new one
    my $ext = ''; my $fnd = FALSE;
    my $qry;
    $ext = NORM if $norm;
    return 0 if $RRA[$norm];
    $RRA[$norm] = 1;
    system("rm -f $rrd$ext.rrd") if $new;
    return 0 if -e $rrd . $ext . '.rrd';
    if( not $first ){
        $qry = query($mytbl,"SELECT unix_timestamp(datum) FROM $mytbl ORDER BY datum LIMIT 1");
	$first = $qry->[0] - 1 if $#{$qry} >= 0;
	$first = Time::Piece->strptime("1-1-1992 00:00 +0100","%d-%m-%Y %H.%M %z")->epoch if $#{$qry} < 0;
    }
    my $command = "rrdtool create $rrd$ext.rrd --start $first --step 3600";
    # create an RRA database with multiple data streams
    # we may define too many (6 out of 11 streams are usualy used.
    $qry = query( $mytbl, "DESCRIBE $mytbl");
    @{$qry} = grep { $_ !~ /(_valid|_color|_ppb|id|datum)$/ } @{$qry} if $#{$qry} >= 0;
    for my $key (keys %rrd_tables ){ # add only sensors also defined in DB database
	for( my $i = 0; $i <= $#{$qry} ; $i++ ){
            my $gas='';
	    next if $key ne $qry->[$i];
            if( $key =~ /^([cns]o2*|o3|nh3|benzeen|tolueen|c6h[2-9][ch0-9]*)$/ ){
                $gas = ' ' . $rrd_tables{$key};
                $gas =~ s/($key)/$1_ppb/g;
            }
	    $fnd = TRUE; $command .= ' '. $rrd_tables{$key} . $gas;
	    # $command .= " RRA:AVERAGE:0.2:24:8760 RRA:MIN:0.1:24:8760 RRA:MAX:0.1:24:8760";
	    last;
        }
    }
    # the resolution of RRA db is in sync with max width graphs and per day steps
    my $W = 785; # default width in pixels of the graph
    for my $R_type ("AVERAGE", "MIN", "MAX" ){ # add rra directives
	# one day, one week, one month, one year, 3 years
	for my $steps ( 24*1, 24*7, 24*30, 24*365, 24*365*3, 24*365*6 ){
	    $command .= sprintf(" RRA:%s:0.5:%d:%d",$R_type,int(($steps+$W)/$W),$W);
	}
    }
    return 0 if not $fnd;
    if( system($command) ){
	print STDERR "$WARNING FAILURE to create rrd file: $command\n";
	print STDERR "$ATTENT rrd file: $rrd.rrd is disabled.\n";
	$RRA[$norm] = -1; return -1;
    }
    print STDERR "$ATTENT Created RRA file $rrd$ext.rrd.\n" if $verbose;
    return 1;
}

# add new RRD data
my $RRD_server = NULL;
sub Add_RRA {
    my $norm = shift;	# normalized database?
    my $type = shift;
    my $time = shift;
    my $val = shift;
    my $ext = '';
    state $warned = '';
    state $RRD_failed = FALSE;
    state $RRD_save = ""; state $RRD_time = 0;
    $ext = NORM if $norm;
    my $st = strftime("%Y/%m/%d %H:%M", localtime($time));
    $type =~ s/^://; $val =~ s/^://;
    return 0 if New_RRA( $norm, FALSE ) < 0;
    return 1 if not $rrd or (not -f $rrd.$ext.'.rrd');
    return 1 if not $type;
    return 1 if not $val;
    if( not $RRD_time || ($rrd ne $RRD_save) ){ $RRD_save = $rrd; $RRD_time = 0 ; }
    my @ds = split /:/, $type;
    my @vs = split /:/, $val;
    if( $#ds != $#vs ){
	print STDERR "$ATTENT Skip RRD insertion into $rrd$ext, template does not match nr arguments.\n";
	return 1;
    }
    # delete non existing sensor types in rrd database
    for( my $i = 0; $i >= 0 && $i <= $#ds; $i++ ){
	if( not rrd_sensor($rrd.$ext, $ds[$i]) ){
	    if( $warned !~ /;$ds[$i]:$rrd$ext/ ){
	        print STDERR "$WARNING Skip $ds[$i], as sensor is not defined in $rrd$ext.rrd\n" if not $quiet;
	        print STDERR "$ATTENT Rebuild RRD database, please\n";
                $warned = "$warned;$ds[$i]:$rrd$ext";
	    }
	    splice @ds, $i, 1; splice @vs, $i, 1;
	    $i--;
	}
    }
    return if $#ds < 0;
    $type = join ':', @ds;
    $val = join ':', @vs;
    # could send the data to the RRD daemon instead ...
    my $last_one = "0";
    if( not $RRD_time ){
	if( rrd_open() ){
            print $RRDin "last $rrd$ext.rrd\n";
	    while(<$RRDout> ){
	        chomp;
                if( /ERROR:/ ){
                    if( $warned !~ /;$rrd/ ) {
                        print STDERR "$ERROR while reading info from RRD database $rrd\n$_\n";
                        $warned = "$warned;$rrd";
                    }
                    return 0;
                }
	        $last_one = $_ if /^[0-9]+$/;
	        last if /(OK u:|ERROR:)/;
            }
	    $RRD_time = int($last_one);
	}
    }
    if( $RRD_time >= $time ){
        if ( not $quiet  && $RRD_errors[$norm] == 0 && ($warned !~ /;$rrd/ )) {
            $warned = "$warned;$rrd";
	    print STDERR sprintf("$WARNING You may want to rebuild the RRD database: $rrd$ext.rrd. Update timing: $st (last: %s)\n",strftime("%Y/%m/%d %H:%M", localtime($RRD_time)));
        }
	$RRD_errors[$norm]++;
        print STDERR sprintf("$ATTENT RRD $rrd$ext update error time preceeds last update time (%s): Skip for date/time $st.\n",strftime("%Y/%m/%d %H:%M", localtime($RRD_time))) if $verbose > 1;
        return 0;
    }
    if( rrd_open() ){
        print $RRDin "update $rrd$ext.rrd -t $type $time:$val\n";
	print STDERR sprintf("%s\r",strftime("%Y/%m/%d", localtime($time))) if $verbose > 1;
	while(<$RRDout> ){
	    last if /OK u:/;
	    if( /ERROR:/ ){
		$RRD_errors[$norm]++;
        	print STDERR "$ATTENT Updating RRD database failed\nRebuild the RRD database.\n" if not $RRD_failed;
	        $RRD_failed = TRUE;
	        print STDERR sprintf("$WARNING Failed to update RRA $rrd$ext.rrd for $type with $val value, date/time $st\nRRDtool: %s\n",$_) if $verbose;
	        print STDERR "Command: update $rrd$ext.rrd -t \"$type\" \"$time:$val\"\n" if $debug;
	        return 0;
	    }
	}
    } else { return 1; }
    $RRD_updates[$norm]++;
    print STDERR "Insert at time $st, DS $type, values $val\n" if $verbose > 2;
    return 0;
}

# normalize a value: arg1= value, arg2=station nr, arg3=year, arg4=pm type
# normalisationre4ference method NEN EN 14907, NTA 8019, NEN-EN 12341:2012
# try to find best fit, use norm element hash as reference to best year
# if not found normalisation factor = 1
# if corrector factor is defined use factor defined
# if correction factor is not defined use the one defined year before
# if not defined at all do not use correction
sub normalize {
    my ($value, $type, $year) = @_;
    return $value if $#_ != 2;
    return $value if not defined $type or not defined $year;
    return $value if not $locations{$location};
    return $value if not $locations{$location}{norm};
    if( not $locations{$location}{$locations{$location}{norm}} ){
        print STDERR "$ERROR Normalisation declaration error for $location\n";
	die "Cannot proceed, correct the Perl script locations init values first\n";
    }
    return $value if not $locations{$location}{$locations{$location}{norm}}{$type};
    my $factor = $locations{$location}{$locations{$location}{norm}}{$type};
    return ($factor * $value) if not $locations{$location}{$year};
    return ($factor * $value) if not $locations{$location}{$year}{$type};
    return ( $locations{$location}{$year}{$type} * $value );
}

# prefer to have the working directpry in user home dir

# open connection to mysql DB
sub Check_DB { # called only once from first call to query routine
    state $checkedOnce = 0;
    if( $mysql ){ return 1; }
    return 0 if length( $mydb ) < 1;
    return 0 if length( $myhost ) < 1;
    return 0 if length( $myuser ) < 1;
    return 0 if length( $mypass ) < 1;
    $mysql = DBI->connect("DBI:mysql:".$mydb.":".$myhost,$myuser,$mypass);
    if( not $mysql ){
	if( $checkedOnce > 0 ){
            print STDERR "$ERROR Cannot open mysql database ".$mydb." on host ".$myhost.", with user ".$myuser.", error: ". DBI->errstr."\n" ;
	    $mysql = 1; return 0;
	}
        print STDERR "$ERROR Cannot open mysql database ".$mydb." on host ".$myhost.", with user ".$myuser.", error: ". DBI->errstr."\nWill try to create it\n" ;
	$checkedOnce = 1;
	Create_DB();
	return Check_DB();
    }
    return 1;
}

# database: luchtmetingen, main table(s) of raw values of sensors
%DB_table = (
	     'id' => "id TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'datum/tijd laatste verandering'",
            'datum' => "datum datetime default '2001-01-01 00:00:00' COMMENT 'datum/tijd UNIX time stamp'",
	    'so' => "so DECIMAL(5,2) default NULL COMMENT 'zwavel oxyde ug/m3'",
	    'so2' => "so2 DECIMAL(5,2) default NULL COMMENT 'zwavel dioxyde ug/m3'",
	    'no' => "no DECIMAL(5,2) default NULL COMMENT 'stikstof oxyde ug/m3'",
	    'no2' => "no2 DECIMAL(5,2) default NULL COMMENT 'stikstof dioxyde ug/m3'",
	    'nh3' => "nh3 DECIMAL(6,2) default NULL COMMENT 'ammonium ug/m3'",
	    'o3' => "o3 DECIMAL(5,2) default NULL COMMENT 'ozon, tri-oxide ug/m3'",
	    'pm_10' => "pm_10 DECIMAL(5,2) default NULL COMMENT 'fijnstof 10 ug/m3'",
	    'pm_25' => "pm_25 DECIMAL(5,2) default NULL COMMENT 'fijnstof 2.5 ug/m3'",
	    'roet' => "roet DECIMAL(5,2) default NULL COMMENT 'roet (soot) ug/m3'",
	    'benzeen' => "benzeen DECIMAL(5,2) default NULL COMMENT 'benzeen ug/m3'",
	    'tolueen' => "tolueen DECIMAL(5,2) default NULL COMMENT 'tolueen ug/m3'",
	    'aqi' => "aqi DECIMAL(5,2) default NULL COMMENT 'air qual index value'",
	    'lki' => "lki DECIMAL(3,1) default NULL COMMENT 'lucht kwaliteits index value'",
	    'wr' => "wr SMALLINT(6) default NULL COMMENT 'windrichting 0-360 graden'",
	    'ws' => "ws DECIMAL(5,2) default NULL COMMENT 'windsnelheid m/sec'",
	    'temp' => "temp DECIMAL(5,2) default NULL COMMENT 'temperatuur oC'",
	    'rv' => "rv DECIMAL(5,2) default NULL COMMENT 'relatieve vochtigheid'",
	    'luchtdruk' => "luchtdruk INT(11) default NULL COMMENT 'luchtdruk mbar'",
	    'name_ppb' => "_ppb DECIMAL(7,3) default NULL COMMENT 'gas parts per billion'",
	    'name_valid' => "_valid BOOL default 1 COMMENT 'value is valid'",
	    'name_color' => "_color TEXT(6) default NULL COMMENT 'rating color html used on the publicing website'",
	    'name_mesg' => "_mesg TEXT(12) default NULL COMMENT 'rating index message used on the website'",
);

my %DB_cols = ( );	# sensors names per table
my %DB_nr_cols = ();	# number of sensors per table
# collect from database the table column names
# if table does not exists create it
sub Check_Tbl {
    my $tbl = shift; my $noprobe = shift; # probe if it exists only
    return 0 if not $tbl;
    return 1 if $DB_cols{$tbl};
    my $qry = query('',"SHOW TABLES");
    for( my $i = 0; $i <= $#{$qry}; $i++ ){
	# next if $qry->[$i] !~ /^$mytbl/;
	$DB_cols{$qry->[$i]} = {} if not $DB_cols{$qry->[$i]}; # the table already exists
    }
    return 1 if $DB_cols{$tbl};
    return 0 if (defined $noprobe) && not $noprobe;
    Create_TBL( $tbl );
    $DB_cols{$tbl} = {};
    return 1;
}

# obtain all sensors for a station in the DB table
sub Get_Sensors {
    my $tbl = shift; return 0 if not $tbl;
    Check_Tbl($tbl) if not $DB_cols{$tbl};
    if( not $DB_cols{$tbl}{"id"} ){
        # only once at the start we build a column existance cache
        my $qr = query($tbl, "DESCRIBE $tbl;");
        if( (not $qr) || ($#{$qr} < 0) ){
            print STDERR "$ERROR Cannot obtain table $tbl description\n";
            return 0;
        }
        # mysql counts cells from 0!
        $DB_nr_cols{$tbl} = 0 if not defined $DB_nr_cols{$tbl};
        for( my $index = 0; $index <= $#{$qr} ; $index++ ){
            $DB_cols{$tbl}{ $qr->[$index] } = 1;
            next if $qr->[$index] =~ /^(id|datum|.*_(color|valid|ppb|mesg))$/ ;
            $DB_nr_cols{$tbl}++;
            $DB_cols{$tbl}{$qr->[$index]} = 1;
            $locations{$location}{sense}{$qr->[$index]} = 1;
        }
    }
    return 1;
}

# add some comment to a DB COMMENT string
sub Add_comment {
    my $cmt = shift; $cmt = '' if not defined $cmt;
    my $add = shift; $add = '' if not defined $add;
    if( $cmt =~ /.*COMMENT '/ ) {
        $cmt =~ s/COMMENT '([^']*)/COMMENT '$1$add/;
    }
    return $cmt;
}

# check if sensor is available in table if not add the column
sub Check_Col {
    my $col = lc(shift);
    my $tbl = shift;
    my $comment = shift;
    return 0 if not Get_Sensors($tbl);
    $comment = "unkown name $col" if ( (not defined $comment) || (not $comment) );
    $comment .= strftime(", added: %Y/%m/%d", localtime(time));
    
    return 0 if $DB_cols{$tbl}{$col};
    my $rate = '';
    if( ( $LKI && ($col =~ /(lki)/)) || ($col !~ /(lki|aqi)/) ){
        $rate = "ADD COLUMN ".$col.$DB_table{'name_valid'};
        $rate .= ", "."ADD COLUMN ".$col.$DB_table{'name_ppb'} if $col =~ /^(so2|no|no2|nh3|o3|benzeen|c6h[2-9][ch2-9]*)$/;;
    } else {
        $rate = "ADD COLUMN ".$col.$DB_table{'name_mesg'} if $AQI_qual;
    }
    if( $DB_table{$col} ){
	print STDERR "$ATTENT Adding column $col to table $tbl\n" if $verbose > 0;
        my $cmt = Add_comment($DB_table{$col},
            strftime(", added: %Y/%m/%d", localtime(time)) );
	query($tbl, "ALTER TABLE $tbl ADD COLUMN $cmt, $rate;");
    } else {
	print STDERR "$ATTENT Adding unknown new column $col to table $tbl\n";
        query($tbl, "ALTER TABLE $tbl ADD COLUMN $col DECIMAL(5,2) default NULL COMMENT '$comment', $rate;");
    }
    $DB_cols{$tbl}{$col} = 1;
    $DB_nr_cols{$tbl}++ if $col !~ /^(id|datum|.*_(color|valid|ppb|mesg))$/ ;
    return 0;
}

# check if aqi type and/or pollutant aqi index column is present
sub Check_AQI_Col {
    return 0 if not $AQI;
    my $col = lc(shift);
    my $tbl = shift; $tbl .= '_aqi' if $tbl !~ /_aqi$/;
    my $comment = shift;
    $comment = "unkown name $col" if (not defined $comment) || (not $comment);
    $DB_nr_cols{$tbl} = 0 if not $DB_nr_cols{$tbl};
    Check_Tbl($tbl) if not $DB_cols{$tbl};
    if( $DB_cols{$tbl}{$col} ){ return 1; }
    if( not $DB_cols{$tbl}{"id"} ){
        # only once at the start we build a column existance cache
        my $qr = query($tbl, "DESCRIBE $tbl;");
        if( (not $qr) or ($#{$qr} < 0) ){
            print STDERR "$ERROR Cannot obtain table $tbl description\n";
            return 0;
        }
        # mysql counts cells from 0!
        for( my $i = 0; $i <= $#{$qr} ; $i++ ){
            $DB_cols{$tbl}{$qr->[$i]} = 1;
            if ( $qr->[$i] =~ /(.*)_(lki|aqi)$/ ) { # denote pollutant
                $DB_cols{$tbl}{$1} = 1;
                $DB_nr_cols{$tbl}++;
            }
        }
        if( $DB_cols{$tbl}{$col} ){ return 1; }
    }
    if( $col !~ /^(pm_10|pm_25|co|so2|no2|o3)/ ){
        return 0 if $col !~ /^${AQI_enabled}$/ ;
    } else { $col =~ s/_(aqi|lki)$//; }
    my $rate = '';
    foreach my $index (keys %{$AQI_Indices} ){
        if( $AQI_Indices->{$index}{require} <= 1 ){
            my @present = grep /^$col$/, split(/,\s*/,$AQI_Indices->{$index}{pollutants});
            next if $#present < 0;
            $index = lc($index);
            if( $AQI_Indices->{uc($index)}{require} <= 1
                && ($col =~ /^(pm_10|pm_25|co|so2|no2|o3)$/ )
                ){
                my $cmt = Add_comment($DB_table{'aqi'},
                    strftime(", added: %Y/%m/%d", localtime(time)) );
                $rate   .= ", ADD COLUMN ${col}_${index}".$cmt;
                if( $AQI_qual ) {
                    $rate   .= ", ADD COLUMN ${col}_${index}".$DB_table{'name_color'};
                    $rate   .= ", "."ADD COLUMN ${col}_${index}".$DB_table{'name_mesg'};
                }
                $DB_cols{$tbl}{ "${col}_${index}" } = 1;
                $DB_cols{$tbl}{$col} = 1;
                $DB_nr_cols{$tbl}++;
            }
            if( not defined $DB_cols{$tbl}{$index} ){
                # only a very few measurements station measure them all in Nld
                next if $index !~ /^${AQI_enabled}$/;      # skip these for now
                # see if there are more first
                my $fnd = 0;
                foreach my $pol (split(/,\s*/,$AQI_Indices->{uc($index)}{pollutants}) ){
                    $fnd++ if (defined $DB_cols{$tbl}{$pol}) && ($pol ne $col);
                }
                if( $fnd >= $AQI_Indices->{uc($index)}{require}
                    || ($col =~ /^${AQI_enabled}$/)
                    ){
                    my $cmt = Add_comment($DB_table{'aqi'},
                        strftime(", added: %Y/%m/%d", localtime(time)) );
                    $rate   .= ", ADD COLUMN $index".$cmt;
                    # issue on _aqiaqi and _lkiaqi reason???: patch
                    $rate =~ s/_(aqi|lki)aqi/_$1/;
                    if( $AQI_qual ) {
                        $rate   .= ", ADD COLUMN $index".$DB_table{'name_color'};
                        $rate   .= ", ADD COLUMN $index".$DB_table{'name_mesg'};
                    }
                    $DB_cols{$tbl}{$index} = 1;
                }
            }
        }
    }
    $rate =~ s/^, //;
    return 0 if not $rate;

    # collected the columns query to add required columns
    print STDERR "$ATTENT Adding column(s) for $col to table $tbl\n" if $verbose > 0;
    query($tbl, "ALTER TABLE $tbl $rate;");
    return 1;
}


# create new table if not existing
sub Create_TBL {
    my $tbl = shift;
    my $comment = '';
    if( $locations{$location} && $locations{$location}{name} ){
	my $mydate = strftime("%Y/%m/%d", localtime(time));
	$comment = "COMMENT='Lokatie $location in $locations{$location}{name}, init: $mydate";
	$comment .= ", eerste datum: $locations{$location}{first}" if $locations{$location}{first};
	$comment .= ", laatste datum: $locations{$location}{last}" if $locations{$location}{last};
    }
    return 0 if not $tbl; my $dd = DATUMS;
    my $string = "CREATE TABLE $tbl (";
    if( $tbl =~ /$dd$/ ){
	$string .= " datum TIMESTAMP default '2001-01-01 00:00:00'";
	$comment .= ", dates/times of collected measurements";
    } else {
        foreach ('id', 'datum' ){
            $string .= "\t$DB_table{$_},";
        }
        $string =~ s/,\s*$//;
    }
    if( $tbl =~ /_aqi/ ){
        $comment .= ", air quality Index data for collected measurements";
    }
    $comment .= "'";
    $string .= "
    ) ENGINE=InnoDB DEFAULT CHARSET=latin1 $comment;
    \n";
    $DB_cols{$tbl} = {};
    query( '', $string );
    return 1;
}

# routine side effect: create column if it was missing
my %validates;	# acts as a cache
sub PM_is_valid {
    my $tbl = shift; return 1 if not $tbl;
    my $timing = shift;
    my $qry = query($tbl, "DESCRIBE ${tbl}") if not (exists $validates{$tbl});
    foreach my $pm ('pm_10', 'pm_25' ){
	if( not (exists $validates{$tbl}) ){
	    my $fnd = FALSE; my $strg = FALSE;
            for( my $i = 0; $i <= $#{$qry}; $i++){
	        $fnd = TRUE if $qry->[$i] =~ /^${pm}_valid$/;
	        $strg = TRUE if $qry->[$i] =~ /^${pm}$/;
	    }
	    $validates{$tbl}{$pm} = FALSE if not $fnd;
	    next if not $strg; 	# the pm column was not present in this table
	    if( not $fnd ){
		# this updates old databases on the fly
	        print STDERR "$ATTENT adding column ${pm}_valid to table $tbl.\n";
	        query($tbl, "ALTER TABLE ${tbl} ADD COLUMN ".$pm.$DB_table{'name_valid'});
	        query($tbl, "UPDATE $tbl SET ${pm}_valid = 0 WHERE isnull($pm)");
	    }
	    $validates{$tbl}{$pm} = TRUE;
	}
	next if( (not $validates{$tbl}{$pm}) || (not $timing) );
	# happens when new values are entered. Might be updated later.
	query($tbl, "UPDATE $tbl SET ${pm}_valid = 1 WHERE not isnull($pm) and from_unixtime(datum) = $timing");
	query($tbl, "UPDATE $tbl SET ${pm}_valid = 0 WHERE isnull($pm) and from_unixtime(datum) = $timing");
    }
}

# this routine will create a correction factor table in the database
# per year correction factor for PM 10 and PM 2.5 (see array @pm)
# from first day up to last day for the $location (deflt: 06)
# from $locations hash table
# default correction factor is 1
# last year defined correction factor will define later years.
sub Put_TBL_norm {
    my $tbl = shift; my $found = TRUE;
    my $TBL = $tbl; return 0 if not $tbl; $tbl .= "_norm";
    $found = FALSE if ( (not $locations{$location}) || (not $locations{$location}{norm}) );
    # $found = FALSE if not $locations{$location}{first};
    print STDERR "$WARNING Cannot (re)build table $tbl due to missing norm factors\n" if not $found;
    return 0 if not $found;
    my @pm = ('pm_10', 'pm_25');
    my $qry = query('', "SHOW tables");
    $found = FALSE;
    for( my $i = 0; $i <= $#{$qry}; $i++ ){
        $found = TRUE if $qry->[$i] =~ /^$tbl$/; # the table already exists
    }
    if( not $found ){
	query('', "DROP TABLE IF EXISTS $tbl");
        my $string = "CREATE TABLE $tbl ( ";
        $string .= "jaar VARCHAR(4) DEFAULT NULL COMMENT 'jaar van normalisatie', ";
        $string .= "status BOOL DEFAULT 0 COMMENT 'correction factor is defined', ";
	foreach my $el (@pm ){
            $string .= "$el DECIMAL(5,2) DEFAULT 1 COMMENT 'PM normalisatie factor', ";
	}
        $string .= "UNIQUE KEY jaar (jaar) ) ENGINE=InnoDB DEFAULT CHARSET=latin1;";
        query('', $string );
    }
    my $last = strftime("%Y", localtime(time));
    # check if we need to update the table
    $qry = query($tbl, "SELECT jaar FROM $tbl WHERE jaar = $last LIMIT 1");
    return 1 if ( $#{$qry} == 0 && $qry->[0] == $last );
    my $year;
    # make sure original table has these sensors as columns
    # TO DO: delete from @pm those sensors not available in DB
    foreach my $s (@pm ){ Check_Col($s, $TBL, 'stake holder'); }
    if( $locations{$location}{first} ){
	$year = $locations{$location}{first};
    } else {
	# next query will go wrong if one PM is not defined
	my $min = 0;
	foreach my $s (@pm ){
	    $qry = query($tbl, "SELECT UNIX_TIMESTAMP(datum) FROM $TBL WHERE not isnull($s) LIMIT 1");
	    next if $#{$qry} < 0;
	    $min = $qry->[0] if not $min;
	    $min = $qry->[0] if $min > $qry->[0];
	}
	return 0 if not $min;
	$year = strftime("%Y", localtime($min));
    }
    $year =~ s/.*([12][0-9]{3}).*/$1/;
    $last = $locations{$location}{last} if $locations{$location}{last};
    $last =~ s/^[0-9]+-[0-9]+-//;
    my @factors = (); for( my $i = 0; $i <= $#pm; $i++ ){ $factors[$i] = 1; }
    for( ; $year <= $last; $year++ ){
	my @arr = (); my $string = "UPDATE $tbl SET ";
	query($tbl, "REPLACE INTO $tbl (jaar) VALUES ( $year )");
        for( my $i = 0; $i <= $#pm; $i++ ){
	    if( $locations{$location}{$year} && $locations{$location}{$year}{$pm[$i]} ){
	        $factors[$i] = $locations{$location}{$year}{$pm[$i]};
		push @arr, "status = 1";
	    }
	    push @arr, "$pm[$i] = $factors[$i]";
	}
	return 1 if $#arr < 0; $string .= join ', ', @arr;
	$string .= " WHERE jaar = $year;";
	query($tbl, $string);
    }
    return 1;
}


# create new database and add standard tables: main table, dayly averages, days
sub Create_DB {
    my $string = "
	CREATE DATABASE  IF NOT EXISTS $mydb;
	USE $mydb;\n";
    # create a table to be able to finds dates and ranges in main table
    
    open(my $MYSQL, "| /usr/bin/mysql -u $myuser -p$mypass -h $myhost" ) || die "FATAL ERROR mysql create DB $mydb and table $mytbl failed: $!\n";
    print $MYSQL $string;
    close $MYSQL;
    foreach ( $mytbl, $mytbl . DAY_AVG, $mytbl . DATUMS ){
	Create_TBL( $_ );
    }
    return 1;
}


# routine to query DB abd return results (ref to 2-D array of refs)
# one row of values from one column out of the DB table
sub query {
    return 0 if Check_DB == 0;
    my $tbl = shift; Check_Tbl($tbl) if $tbl;
    my $q = shift;
    my $old = $q;
    if( (not $mysql) or ($mysql == 1) or (not $q) ){ return undef; }
    if ( ($q =~ /(UPDATE|REPLACE)/) && ($q =~ /\.[,\s]/) ) { # temporary patch
	$q =~ s/\.([,\s])/NULL$1/g;
    }
    if ( ($q =~ /(UPDATE|REPLACE)/) && ($q =~ /-999/) ) { # temporary patch
	$q =~ s/-999/NULL/g; $q =~ s/ppb\s=\s-[0-9\.]+/ppb = NULL/g;
    }
    print STDERR "MYSQL: $q\n" if $debug > 1;
    my $sth = $mysql->prepare($q); $sth->execute();
    #  ref to 2 dimensional refs to array string values
    if( $q =~ /^\s*(show|describe|select)/i ){
        my $r = $sth->fetchall_arrayref();
        print STDERR "$ERROR mysql query: $q with error:\n" . DBI->errstr . "\n"
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

# matrix of values
sub long_query {
    return 0 if Check_DB == 0;
    my $tbl = shift; Check_Tbl($tbl) if $tbl;
    my $q = shift;
    if( (not $mysql) or ($mysql == 1) or (not $q) ){ return undef; }
    print STDERR "MYSQL: $q\n" if $debug > 1;
    my $sth = $mysql->prepare($q); $sth->execute();
    #  ref to 2 dimensional refs to array string values
    if( $q =~ /^\s*(select)/i ){
        my $r = $sth->fetchall_arrayref();
        return undef unless $r->[0];
        if( $#{$r} < 0 ){
            print STDERR "$ERROR mysql query: $q with error:\n" . DBI->errstr . "\n";
        }
        $sth->finish(); return $r;
    } else { return undef; }
}

# storage of measurements
# per date: N X (time,M X (label, value, rating)) + (dayly average, rating)
# where N: 24 hourly measurements, M: max 12 sensors
# color rating differ for measurements < May 2014 and later (name_color)
# names lower cased names of column
my @label = ();
# unit of the value e.g. micro grams per cubic meter, milli bar, grades, mters per second, etc
my @unit = ();
# values measured per hour
my @data = ();
#  color rating: green, yellow, orange, red, rating is in html hex value
# database storage is under label (name) plus "_color"
my @rating = ();

# get for one hour of a day all data in the database table
sub Get_old_values {
    my $selection = shift; $selection =~ s/^,//;
    my $qry = ();
    return $qry if not $selection;
    my $mydate = shift;
    my $tbl = shift;
    $qry = long_query($tbl, "SELECT $selection FROM $tbl WHERE datum = from_unixtime($mydate)");
    return $qry->[0] if $#{$qry->[0]} >= 0;
    return ();
}

# try to find a reference station for unknown temp and/or pressure values
sub findElsewhere {
    my $timing = shift;
    # temp in x.yC, pres in x.ymB if found
    my $type = shift;
    state %tbls; # static table found with reference value
    if ( not scalar keys %{$tbls{$type}} ) {
        # do the search only one time
        $tbls{$type}{count} = 0; # we searched once for this type
        my $qry = query('',"SHOW TABLES");
        @{$qry} = grep { $_ !~ /(_|stations)/ } @{$qry} if $#{$qry} >= 0;
        for( my $i=0; $i <= $#{$qry}; $i++ ){
            my $fnd = query('',"DESCRIBE $qry->[$i]");
            next if $#{$qry} < 0;
            @{$fnd} = grep { $_ =~ /^$type$/ } @{$fnd};
            next if $#{$fnd} < 0;
            for( my $j=0; $j <= $#{$fnd}; $j++ ){
                my $present = query($qry->[$i],
                    "SELECT count(*) FROM $qry->[$i] WHERE
                    not ISNULL($fnd->[$j])");
                next if ($#{$present} < 0) || ($present->[0] == 0);
                $tbls{$type}{$qry->[$i]} = $present->[0];
                $tbls{$type}{count}++;
            }
        }
    }
    return '' if not $tbls{$type}{count}; # no table with this type sensor
    # try table with most type entries first
    foreach my $tbl (sort { $tbls{$type}{$b} <=> $tbls{$type}{$a} } keys %{$tbls{$type}} ) {
        next if $tbl eq 'count';
        my $qry = query($tbl,"SELECT round(avg($type),1) FROM $tbl WHERE
            datum BETWEEN FROM_UNIXTIME($timing - 2*60*60)
                  AND FROM_UNIXTIME($timing+2*60*60)");
            if( ($#{$qry} >= 0) && (defined $qry->[0]) ){
                my $t =  sprintf("%5.1f", $qry->[0]);
                return $t if $t =~ /-?[0-9\.]+$/;
            }
    }
    return '';
}

# update the aqi table with aqi values at date/time from station value table
# arguments: station value table, date/time
# this way is rather DB intensive: per hour one DB call
sub Update_AQI {
    return 0 if not defined $AQI_Indices;       # loaded via AQI.pl
    my $tbl = shift; my $mtbl = $tbl . '_aqi'; my $timing = shift;
    my @senses = (); my $qry = '';
    my $temp = ''; my $druk = ''; my $fndtemp = 1;
    return 0 if not Check_Tbl($mtbl, $AQI);   # probe or create it if not not existant
    # search for aqi pollutant indicators at this location 
    foreach my $sens ('temp','luchtdruk','o3','no2','co','so2','pm_10','pm_25' ){
        next if not $locations{$location}{sense}{$sens};
        push @senses, $sens;
        $qry .= ",if(${sens}_valid,$sens,NULL)";
    }
    my $rslts = Get_old_values($qry, $timing, $tbl); # obtain the values
    return 0 if $#{$rslts} < 0;
    for( my $i=0; $i <= $#senses; $i++ ){
        last if $i > 1;
        next if not defined $rslts->[$i];
        if( $senses[$i] =~ /temp/   ){
            $temp=sprintf("%3.1fC",$rslts->[$i])
                if $rslts->[$i] =~ /[0-9\.]+$/;
            $rslts->[$i] = undef;
            $fndtemp = 0 if $temp;
        } elsif( $senses[$i] =~ /luchtdruk/   ){
            $druk=sprintf("%5.1fmB",$rslts->[$i])
                if $rslts->[$i] =~ /[0-9\.]+$/;
            $rslts->[$i] = undef;
        }  # for AQI Index we need to know temp/pressure
    }
    # delete from both arrays those rows with undef value
    my $cur = -1;
    for( my $i=0; $i <= $#senses; $i++ ){
        next if (not defined $rslts->[$i]) || (not defined $senses[$i]);
        $cur++;
        $senses[$cur]=$senses[$i]; $rslts->[$cur] = $rslts->[$i];
        if( $senses[$cur] !~ /^pm_/i && $fndtemp ){
            # try once to find temp, neglect air pressure
            $temp = findElsewhere( $timing, 'temp'); 
            $temp .= 'C' if $temp;
            $druk = findElsewhere( $timing, 'luchtdruk'); 
            $druk .= 'mB' if $druk;
            $fndtemp = 0 if $temp;
        }
    }
    $#senses = $cur; 
    return 1 if $cur < 0;       # no indicator values found

    # make sure the table row is update ready
    $qry = query($mtbl,"SELECT count(*) FROM $mtbl WHERE datum = FROM_UNIXTIME($timing)");
    return 0 if $#{$qry} < 0;   # internal mysql error, count should exists
    query($mtbl,"REPLACE INTO $mtbl (id,datum) VALUES (now(),FROM_UNIXTIME($timing))")
        if not $qry->[0];

    my @aqi = ();
    my $time1 = 0;
    $qry = query($mtbl,"SELECT UNIX_TIMESTAMP(id) FROM $mtbl
            WHERE datum = FROM_UNIXTIME($timing) LIMIT 1");
    $time1 = $qry->[0]; my $flds = 0; $query = '';
    # update per pollutant the aqi values, collect the update query
    foreach my $index (keys %{$AQI_Indices} ){
        next if $AQI_Indices->{$index}{require} > 1;
        my $type = lc($index);
        for( my $i=0; $i <= $#senses; $i++ ){
            my $none = ''; $none = 'none' if not $AQI_qual;
            next if $AQI_Indices->{$index}{pollutants} !~ /$senses[$i]/;
            @aqi = $AQI_Indices->{$index}{routine}->(
                sprintf("$none $temp $druk %s=%3.1f",${senses[$i]},$rslts->[$i]) );
            next if ($#aqi < 0) || (not $aqi[0]);
            Check_AQI_Col("${senses[$i]}_$type",$mtbl,"indicator for $index Index");
            if( not $query ){ $query = 'SET'; } else { $query .= ','; }
            $query .= sprintf(" ${senses[$i]}_$type = %3.2f", $aqi[0]);
            if( $AQI_qual ){
                $query .= sprintf(", ${senses[$i]}_${type}_color = '0x%6.6X', ${senses[$i]}_${type}_mesg = '%s'", 
                    $aqi[1], $aqi[2]);
            }
            $flds++;
        }
    }
    # update aqi with collection of pollutants (mostly the max value of indicators)
    $qry = '';
    for( my $i=0; $i <= $#senses; $i++ ){
        $qry .= " ${senses[$i]}=$rslts->[$i]";
    }
    foreach my $index (keys %{$AQI_Indices} ){
        # basic #indicators present? leave the check also to the AQI routine below
        next if $#senses < $AQI_Indices->{$index}{require};
        my $none = ''; $none = 'none' if not $AQI_qual;
        next if $index !~ /^${AQI_enabled}$/i;   # skip indicator type of aqi
        @aqi = $AQI_Indices->{$index}{routine}->("$none $temp $druk $qry");
        next if  ($#aqi < 0) || not $aqi[0];
        Check_AQI_Col(lc($index),$tbl,"$index index aqi combination");
        $index = lc($index);
        if( not $query ){ $query = 'SET'; } else { $query .= ','; }
        $query .= sprintf(" ${index} = %2.1f", $aqi[0]);
        $query .= sprintf(", ${index}_color = '0x%6.6X', ${index}_mesg = '%s'",
            $aqi[1],$aqi[2]) if $AQI_qual;
        $flds++;
    }
    $qry = query($mtbl,"UPDATE $mtbl $query WHERE datum = FROM_UNIXTIME($timing)")
            if $flds;
    if( not $flds ){
        printf STDERR ("No table record change in table $mtbl for date %s\n",
                strftime("%Y/%m/%d %H:%M", localtime($timing)) )
            if $debug && (not $flds);
        return 1;
     }
    $qry = query($mtbl,"SELECT UNIX_TIMESTAMP(id) FROM $mtbl
        WHERE datum = FROM_UNIXTIME($timing) LIMIT 1");
    printf STDERR ("%s record in table $mtbl with %d fields for date %s\n",
        ($time1 < $qry->[0] ? "Update" : "Added"),
        $flds, strftime("%Y/%m/%d %H:%M", localtime($timing)) ) if $debug;
    return ($time1 < $qry->[0] ? 3 : 2);
}

# update AQI table for a location, default by latest datum TODO: otherwise by id
# DB table name: <location_table_name>_aqi
# arguments: station table name, first operation date/time of the station,
#            from date/time (dflt 0), enddate/time (dflt now)
sub Fill_AQI_table {
    return 0 if not $AQI;
    my $tbl = shift; my $mtbl = $tbl.'_aqi'; my $frst = shift; my $endtime = shift;
    my $cnt = 0; my $qry;
    $strttime = 0 if not defined $strttime;
    $endtime = time if not defined $endtime;

    Check_Tbl($tbl);
    return 0 if not Get_Sensors($tbl);
    my $sensors = '';
    # the pollutant index indicators
    foreach my $sensor ('o3','pm_10','pm_25','no2','so2','co' ){
        next if not defined $locations{$location}{sense}{$sensor};
        $sensors .= ' OR ' if $sensors;
        $sensors .= "(not ISNULL($sensor))";
    }
    print STDERR "$ATTENT No pollutants found for AQI table $tbl. Skip this station.\n"
        if (not $quiet) && (not $sensors);
    return 0 if not $sensors;
    $sensors = "AND ($sensors)" if $sensors;

    Check_Tbl($mtbl);
    if ( $strttime ) {
        # verify start time
        $qry = query($mtbl,"SELECT UNIX_TIMESTAMP(datum) FROM $mtbl WHERE UNIX_TIMESTAMP(datum) >= $strttime ORDER BY datum LIMIT 1");
        if( ($#{$qry} >= 0) && ($qry->[0] >= $strttime ) ) {
            $strttime = $qry->[0] -60 ;
        } else { $strttime = 0 ; }
    }
    if ( not $strttime ) {
        $qry = query($mtbl,"SELECT UNIX_TIMESTAMP(datum) FROM $mtbl ORDER BY datum DESC LIMIT 1");
        # update only new ones but redo the last in case of quited job
        if( ($#{$qry} >= 0) && ($qry->[0] > $frst) ){
            return 0 if $qry->[0] > $endtime;
            $frst = $qry->[0] -60;
        }
    } else { $frst = $strttime ; }

    printf STDERR ("Adding records into table $mtbl, starting date: %s\n",
            strftime("%Y/%m/%d %H:%M",localtime($frst)) )
        if not $quiet;
    my $lastdate = $frst; my $once = 0;
    while ( $frst ){
        last if $frst > $endtime;
        $qry = query($tbl,"SELECT UNIX_TIMESTAMP(datum) FROM $tbl WHERE (UNIX_TIMESTAMP(datum) > $frst) $sensors LIMIT 1");
        last if ($#{$qry} < 0) || ("$qry->[0]" !~ /^[1-9][0-9]+/);
        $frst = $qry->[0]; $lastdate = $frst;
        printf STDERR ("Adding records into table $mtbl for date %s\r",
                strftime("%Y/%m/%d", localtime($frst)) )
            if ($verbose > 0) && ((not $once) || ((int($frst/(60*60)) % 24) == 0)); 
        $once = 1;
        my $rts = Update_AQI($tbl,$frst);
        last if not $rts;
        $cnt++ if $rts > 1;
    } 
    printf STDERR ("Adding records into table $mtbl for date %s\n",
            strftime("%Y/%m/%d", localtime($frst)) )
        if $verbose > 0;
    printf STDERR ("Adding records end date: %s\n",
            strftime("%Y/%m/%d %H:%M",localtime($frst)) )
        if (not $quiet) && (not $verbose);
    return $cnt;
}

# update AQI table for records which are updated and validated on later instance
# arguments: table name, start time (dfl 0 = all), end time.
sub Adjust_AQI_table {
    return 0 if not $AQI;
    my $tbl = shift; my $mtbl = $tbl.'_aqi'; my $timing = 0;
    my $strttime = shift; $strttime = 0 if not defined $strttime;
    my $endtime = shift; $endtime = time if not defined $endtime;
    Check_Tbl($mtbl); Check_Tbl($tbl);
    return 0 if not Get_Sensors($tbl);
    my $qry = query($mtbl,"SELECT UNIX_TIMESTAMP(datum) FROM $mtbl ORDER BY datum DESC LIMIT 1");
    if( ($#{$qry} < 0) || ($qry->[0] < 1000) ){
        # empty AQI table so fill it
        $qry = query($mtbl,"SELECT UNIX_TIMESTAMP(datum) FROM $tbl LIMIT 1");
        print STDERR "$ERROR DB tabe $tbl has no records.\n" if $#{$qry} < 0;
        return 0 if $#{$qry} < 0;
        $endtime = $qry->[0] -60;
        return Fill_AQI_table( $tbl, $strttime, $endtime )
    }
    # get the last update time of AQI table
    # and collect all entries in table updated later date as update time AQI table
    $qry = query($mtbl,"SELECT UNIX_TIMESTAMP(id) FROM $mtbl
        WHERE UNIX_TIMESTAMP(id) < $endtime ORDER BY id DESC LIMIT 1");
    return 0 if $#{$qry} < 0;
    my $latest = $qry->[0];     # latest change before endtime
    my $updates = query($tbl,"SELECT UNIX_TIMESTAMP(datum) FROM $tbl
        WHERE UNIX_TIMESTAMP(id) > $latest AND
        UNIX_TIMESTAMP(datum) >= $strttime AND
        UNIX_TIMESTAMP(datum) <= $endtime ORDER BY datum");
    my $cnt = 0;
    for( my $i=0; $i <= $#{$updates}; $i++ ){
        last if $updates->[0] > $endtime;
        printf STDERR ("Updating AQI table $mtbl for date %s\r",
                strftime("%Y/%m/%m %H:%M", localtime($updates->[$i])) )
            if $verbose;
        $cnt++ if Update_AQI($tbl, $updates->[$i]) > 1;
    }
    printf STDERR "\n" if $verbose;
    return $cnt;
}

# check if we know this sensor already
sub Sensor_is_present {
    my $sens = shift; return 1 if not $sens;
    my $datum = shift; $datum = 'unknown date' if not $datum;
    return 0 if defined $locations{$location}{sense}{$sens}++;
    print STDERR "$WARNING date:%s new sensor type \"%s\" found\n", $datum, $sens;
    $locations{$location}{sense}{$sens} = 1;
    return 1;
}

# calculate the ppb value from ug/m3 for gasses
# args: name, value in ug/m3, temperature, air pressure in mBar
# returns: ppb (parts per billion) for gaaases or ug/m3 for other pollutants
sub ppb {
    my( $sens, $value, $temp, $atm ) = @_;
    return $value if not $value;
    return $value if $sens !~ /^([cns]o2*|o3|ammonium|nh3|benzeen|tolueen|c6h[2-9][ch0-9]*)$/i;
    $temp = 15 if (not defined $temp) or ($temp !~ /^[\-0-9][0-9\.]+$/);
    $atm = 1013.25 if (not defined $atm) or ($atm !~ /^[1-9][0-9\.]+$/);
    $sens = lc($sens);
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
   if( not defined $GMOL{$sens} ){
       print STDERR "WARNING: udefined GMOL weight for $sens\n";
       return $value;
   }
   return int(1000 * $value * (((273.15 + $temp)/12.187)*($atm/1013.25))/$GMOL{$sens})/1000;
}

# put one hour of collected data for range of sensors into the database table
# label[2 .. N] has sensors names
# data[0 .. 1] has day, hour and data[2 .. N] has sensor values
# rating[0 .. N] has color value eg green .. red as used on website
# unit[0 .. N] has unit of measurement (future use) For now not used
sub processDB {
    my $tbl = shift;
    state $last_time = 0;
    state $temp = 15; state $atm = 1013.25;  # dlfts for temp and air pressure
    state $warned = 0;
    return 0 if $#data < 0;
    return 0 if ( (not defined $data[0])  || (not defined $data[1]) || (not $tbl) );
    if( ($data[0] !~ /^[0-9]+[-\/][0-9]+[-\/][0-9]+$/) || ($data[1] !~ /^[0-9]+\.[0-9]+$/) ){
	print STDERR "$WARNING Date error, Skip record \"$data[0] $data[1] ...\"\n";
	return 0;
    }
    my $cnt = 0;
    if( $data[0] =~ /(20[0-9][0-9])[-\/]([01]*[0-9])[-\/]([0-3]*[0-9])/ ){
	$data[0] = "$3-$2-$1";
    }
    $data[0] =~ s/\//-/g; $data[1] =~ s/24\.00/23.59/;
    my $timing = Time::Piece->strptime("$data[0] $data[1] +0100","%d-%m-%Y %H.%M %z")->epoch;
    
    # compile the MySQL query string
    my @used_labels = (); my $lbl_temp = -1; my $lbl_atm = -1;
    for( my $i=2; $i <= $#data; $i++ ){
	next if not defined($data[$i]);
        $lbl_temp = $i if lc($label[$i]) =~ /^temp$/;
        $lbl_atm = $i if lc($label[$i]) =~ /^luchtdruk$/;
        # change column name into alternative name
        $label[$i] = 'roet' if $label[$i] =~ /zwarte.rook/;
        $label[$i] = 'nh3' if $label[$i] =~ /ammonium/;
        $label[$i] = 'benzeen' if $label[$i] =~ /c6h6/i;
        $label[$i] = 'tolueen' if $label[$i] =~ /c6h5ch3/i;
	if( ($data[$i] !~ /^\s*$/) && Check_Col(lc($label[$i]), $tbl) ){
            # side effect Check_Col if new sensor found column sensor is added
	    # there is no column for this value in the database
	    $data[$i] = ''; next;
	}
	next if $data[$i] =~ /^\s*$/;
	Sensor_is_present($label[$i], $data[0]) if $tbl eq $mytbl;
        # Check_AQI_Col(lc($label[$i]),$tbl,"add on aqi") if ($AQI > 0) && ($tbl eq $mytbl);
	push @used_labels, lc($label[$i]);
        if( lc($label[$i]) =~ /^([cns]o2*|o3|nh3|benzeen|tolueen|c6h[2-9][ch0-9]*)$/ ){
            # it is a gas so add ppb value
            push @used_labels, lc($label[$i]) . '_ppb';
        }
	$cnt++;
    }
    $temp = $data[$lbl_temp] if ($lbl_temp >= 0) && defined $data[$lbl_temp];
    $atm = $data[$lbl_atm] if ($lbl_atm >= 0) && defined $data[$lbl_atm];
    print STDERR "$ATTENT $data[0] $data[1]: Got no values ($cnt) to add to DB $tbl.\n" if( (not $cnt) && ($verbose > 0)) && ($timing < time);
    return 0 if not $cnt;
    my $ovals = Get_old_values( join(',',@used_labels), $timing, $tbl );
    my $qry = ''; my @rpl_lbls = ("id", "datum");
    if( $#{$ovals} < 0 ){	# only new values
        $qry = 'REPLACE INTO ' . $tbl . ' (';
    } else {
	$qry = 'UPDATE ' . $tbl . ' SET id = now(), ';
    }
    my $indx = 0; my @new_values = ();
    my $fnd_pollutant = 0;      # only update DB when pollutant is found
    for( my $i=2; $i <= $#data; $i++ ){
	next if not defined($data[$i]);
	next if $data[$i] =~ /^\s*$/;
	$data[$i] =~ s/,/./;	# seems decimal comma is used sometimes
        if( lc($label[$i]) =~ /^([cns]o2*|o3|nh3|benzeen|tolueen|c6h[2-9][ch0-9]*|roet|pm_[12][05])$/ ){
	    if( $data[$i] !~ /\.$/ ) {
            	$fnd_pollutant++ if (defined $data[$i]) and ( ('null' ne lc($data[$i]) || ($data[$i] != -999)) );
	    } else { $data[$i] = -999; }
        }
        if( not defined $locations{$location}{'avg'}{$label[$i]} ){
            # do simple statistical value evaluation check and
            # set {pollutant}_valid = 0 eventualy
            my $stat = query($tbl,"DESCRIBE $tbl $label[$i]");
            if( ($#{$stat} >= 0) && $stat->[0] ) {      # check existance
                $stat = query($tbl,"SELECT count(*), AVG($label[$i]),
                    STDDEV($label[$i]) FROM $tbl WHERE ${label[$i]}_valid");
                if( ($#{$stat} == 2) && ($stat->[0] > 250) ){ # > nr of measurements
                    $locations{$location}{'avg'}{$label[$i]} = $stat->[1];
                    # 97.3% range around aberage should be ok to first validation
                    $locations{$location}{'stddev'}{$label[$i]} = 2.5 * $stat->[2];
                }
            }
        }
	if( $#{$ovals} < 0 ){
	    push @new_values, $data[$i];
	    push @rpl_lbls, $label[$i];
            if( defined $locations{$location}{'avg'}{$label[$i]} ){
                # clear measurement valid if not in 97.3 deviation range
                if(
                    ($data[$i] > ($locations{$location}{'avg'}{$label[$i]}+$locations{$location}{stddev}{$label[$i]}))
                    || ($data[$i] < ($locations{$location}{'avg'}{$label[$i]}-$locations{$location}{stddev}{$label[$i]}))
                    || (($label[$i] !~ /^temp$/) && ($date[$i] <= 0) )
                ){
                    push @new_values, 0;
                    push @rpl_lbls, "${label[$i]}_valid";
                    printf STDERR "$ATTEND $label[$i] value $data[$i] is out of range.\n"
                        if $verbose;
                }
            }
            #if( defined $rating[$i] && ($rating[$i] !~ /^\s*$/) ){
	    #   push @new_values, '"'.$rating[$i].'"';
	    #   push @rpl_lbls, $label[$i] . '_color';
            #}
            if( lc($label[$i]) =~ /^([cns]o2*|o3|nh3|benzeen|tolueen|c6h[2-9][ch0-9]*)$/ ){
                push @new_values, ppb($label[$i],$data[$i],$temp,$atm);
	        push @rpl_lbls, $label[$i] . '_ppb';
            }
	} else {
	    # there are already measurements in the database for this date/time
	    $ovals->[$indx] = -999 if not (defined $ovals->[$indx]);
	    if( $data[$i] != $ovals->[$indx] ){
		if( $verbose && ($ovals->[$indx] != -999 || ('null' !~ /$ovals->[$indx]/i)) ){
	            printf STDERR ("$ATTENT $data[0] $data[1]: overwriting value for $label[$i]: %s with new value $data[$i]\n",
		        ($ovals->[$indx] == -999 ? "NULL" : $ovals->[$indx]))
		    if int($data[$i]+0.5) != int($ovals->[$indx]+0.5);
		}
		push @new_values, lc($label[$i]) . ' = '.$data[$i];
                if( lc($label[$i]) =~ /^([cns]o2*|o3|nh3|benzeen|tolueen|c6h[2-9][ch0-9]*)$/ ){
                    # it is a gas so calculate the ppb value from ug/m3
                    push @new_values, lc($label[$i]) . '_ppb = ' . ppb($label[$i],$data[$i], $temp, $atm) 
                        if $data[$i];
                }
                if( defined $locations{$location}{avg}{$label[$i]} ){
                    # clear measurement valid if not in 97.3 deviation range
                    if( ($data[$i] > ($locations{$location}{avg}{$label[$i]}+$locations{$location}{stddev}{$label[$i]}))
                        || ($data[$i] < ($locations{$location}{avg}{$label[$i]}-$locations{$location}{stddev}{$label[$i]})) 
                    || (($label[$i] !~ /^temp$/) && ($date[$i] <= 0) )
                ){
                        push @new_values, lc($label[$i]).'_valid = 0';
                        printf STDERR "$ATTEND $label[$i] value $data[$i] is out of range.\n"
                            if $verbose;
                    }
                }
	        #if( defined $rating[$i] and $rating[$i] !~ /^\s*$/ ){
	        #    $rating[$i] = 'NULL' if not $ovals->[$indx];
		#    push @new_values, lc($label[$i]) . '_color = "'.$rating[$i].'"';
	        #}
	    } else {	# same value delete it so RRD will not get an update failure
		$data[$i] = 'NULL';
	    }
	    $indx++;
	}
    }
    if( $#{$ovals} < 0 ){
        $qry .= join(', ', @rpl_lbls ) . ") VALUES ( now(), from_unixtime($timing), " 
    }
    print STDERR "$ATTENT Nothing to change in database $tbl for $data[0] $data[1].\n"
        if ($#new_values < 0) && ($verbose > 1);
    print STDERR "$ATTENT No pollutants found for $data[0] $data[1]. Skipped.\n"
        if (not $fnd_pollutant) && ($#new_values >= 0) && (not $quiet);
    return 0 if ($#new_values < 0) || ( not $fnd_pollutant ) ;
    $DB_inserts{$tbl} = 0 if not (defined $DB_inserts{tbl});
    $DB_updates{$tbl} = 0 if not (defined $DB_updates{tbl});
    $qry .= join(', ', @new_values);
    if( $#{$ovals} < 0 ){	# only new values
	$DB_inserts{$tbl}++;
        $qry .= ');';
    } else {
	$DB_updates{$tbl}++;
	$qry .= " WHERE datum = from_unixtime($timing);";
    }
    if ( ($qry =~ /(UPDATE|REPLACE)/) && ($qry =~ /\.[,\s]/) ) { # temporary patch
	$qry =~ s/\.([,\s])/NULL$1/g;
    }
    if ( ($qry =~ /(UPDATE|REPLACE)/) && ($qry =~ /-999/) ) { # temporary patch
	$qry =~ s/-999/NULL/g; $qry =~ s/ppb\s=\s-[0-9\.]+/ppb = NULL/g;
    }
    print "$qry\n" if $debug > 0;
    # return 0;
    my $rslt = query($tbl, $qry);
    if( not defined $rslt ){
        print STDERR "$ERROR Update error on table $tbl with SQL:\n$qry\n";
    } else {
        $DB_updates{$tbl}++;
    }

    return $cnt if $tbl ne $mytbl; # for raw measurements we do more

    # and mark PM values valid if not null
    PM_is_valid( $tbl, $timing );
    ########## add AQI values for date $timing
    Update_AQI($tbl, $timing) if $tbl =~ /^[a-z0-9]+$/i;
    # update last validation time (just a speed up for other tooling)
    if( $last_time == 0 ){	# only if table exists
	$last_time++;
	my $qry = query('',"SHOW TABLES");
        for( my $i = 0; $i <= $#{$qry}; $i++ ){
            next if $qry->[$i] !~ /^stations/;
	    $last_time += $timing; last;
        }
    }
    if( $timing < $last_time ){
        query('', 
	    "SET \@t = (SELECT to_days(validated) FROM stations WHERE stations.table = '$tbl' LIMIT 1)" );
	query('',
	    "UPDATE stations SET validated = IF( \@t >= to_days(from_unixtime($timing)), from_unixtime($timing - 24*60*60), validated) WHERE stations.table = '$tbl'");
	$last_time = $timing - 24*60*60;	# set to day before as validated
    }
    # denote the date/time of measurement into separate table
    query($tbl . DATUMS, "REPLACE INTO ${mytbl}" . DATUMS . " (datum) VALUES (from_unixtime($timing));");
    if( $DB_nr_cols{$mytbl}&& ($cnt < $DB_nr_cols{$tbl}) && ($verbose > 1) ){
        my @fnd = ();
        foreach my $sens (keys %{$DB_cols{$tbl}} ){ 
            next if $sens =~ /^(id|datum|.*_(ppb|color|valid))$/;
            push @fnd, $sens;
            for( my $lbl = 2; $lbl <= $#label; $lbl++ ){
                $#fnd-- if ($label[$lbl] =~ /^$sens$/) && ($data[$lbl] !~ /^\s*$/);
                last if $label[$lbl] =~ /^$sens$/;
            }
         }  
         printf STDERR ("$ATTENT $data[0] $data[1]:\tMissing value(s) for %d of %d pollutants: %s",
                $DB_nr_cols{$mytbl} - $cnt, $DB_nr_cols{$mytbl}, join(', ', @fnd))
            if ($#fnd >= 0) && ($DB_nr_cols{$mytbl} > $cnt) && (not $warned++);
    }
    return $cnt;
}

# put collected data into RRD database via data[], label[] global variables
sub processRRD {
    return 0 if ( (not defined $data[0])  || (not defined $data[1]) );
    my $cnt = 0;
    my $timing = Time::Piece->strptime("$data[0] $data[1] +0100","%d-%m-%Y %H.%M %z")->epoch;
    print STDERR Time::Piece->strptime("$data[0] $data[1] +0100","%d-%m-%Y %H.%M %z")->strftime() if $debug > 1;
    
    my $rraDS = ''; my $year = $data[0]; $year =~ s/-[0-9].*//;
    my $rraVal0 = ''; my $rraVal1 = '';
    for( my $i=2; $i <= $#data; $i++ ){
	next if not defined($data[$i]);
	if( ($data[$i] !~ /^\s*$/) && Check_Col(lc($label[$i]), $mytbl) ){
	    # there is no column for this value in the database
	    $data[$i] = ''; next;
	}
	next if $data[$i] =~ /^\s*$/;
	next if $data[$i] =~ /^NULL$/;
	$rraDS .= ':' . lc($label[$i]) if $rrd_tables{lc($label[$i])} ;
	$cnt++;
    }
    for( my $i=2; $i <= $#data; $i++ ){
	next if not defined($data[$i]);
	next if $data[$i] =~ /^\s*$/;
	next if $data[$i] =~ /^NULL$/;
	if( $rrd_tables{lc($label[$i])} ){
	    $data[$i] =~ s/,/./;
	    $rraVal0 .= ':'. $data[$i];
	    $rraVal1 .= ':'. normalize($data[$i],$label[$i],$year) if $normalized;
	}
    }
    $rraVal0 =~ s/^://; $rraDS =~ s/^://;
    print "RRD database add: $rraDS values: $rraVal0\n" if $rrd && ($debug > 0);
    Add_RRA(0, $rraDS, $timing, $rraVal0 ) if $normalized != 1;		# add to raw database
    $rraVal1 =~ s/^:// if $normalized;
    Add_RRA(1, $rraDS, $timing, $rraVal1 ) if $normalized; # add to normalized database

    return $cnt;
}

# download a spreadsheet file from website using Get method
# stores xls or zip file local as cache
sub get_file {
    my $id = shift;
    my $file = shift;
    my $may_fail = shift;
    $may_fail = 0 if not defined $may_fail;
    my (undef, $path, $name) = splitpath($file);
    my $method = 'http';  # default protocol
    my ($my_host, $my_action) = ($host, $action);	# command argument defs?
    state $agnt;
    $my_host = $datahosts{$id}{url} if not $host;    	# default datahost
    $my_action = $datahosts{$id}{action}."$name" if not $action;
    $method = $datahosts{$id}{protocol} if defined $datahosts{$id}{protocol};
    if( (lc($id) =~ /nrwf/i) && ($file =~ /\/$/) ){
	$my_action = $file;
    }
    elsif( (lc($id) !~ /rivm/i) && (not $action) ){
	$my_action = "$datahosts{$id}{action}/$path/$name"; $path = '';
    }
    $my_action =~ s/\/\//\//g;

    if( lc($id) =~ /rivm/i && $path ){		# special for RIVM website
        return if -f $file;
        unless ( -d $path ){ mkpath($path) or die "Could not make $path $!"; }
    }
    my $URL;
    if( not $URL ){
        $agnt = ((keys %agents)[int rand keys %agents]);
        $agnt = $agents{$agnt};
        $URL=LWP::UserAgent->new(agent => $agnt);
        $URL->timeout('40');
        if( system("pidof privoxy >/dev/null") ){
            $URL->env_proxy;
        } else {
            #$URL->proxy($method, $method . '://127.0.0.1:8118/');
            $URL->proxy('http', 'http://127.0.0.1:8118/');
        }
    }
    my $resp = $URL->get($method . '://'.$my_host.$my_action);

    if( $resp->is_success ){
	# if( lc($id) =~ /rivm/i && $path ){		# special for RIVM website keep zip file
	#     open FILE, ">$file";
        #     print FILE $resp->content;
        #     close FILE;
	#     return '';
        # } else {
           return $resp->content;
        # }
    } elsif( not $may_fail ) { 
        if ( $verbose || ($resp->status_line !~ /403 /)) {
	    print STDERR "$ERROR Response status line: "; print STDERR $resp->status_line . "\n";
        }
	print STDERR "$ERROR Cannot obtain file $file from http://$my_host$my_action\n" if $verbose;
	print STDERR "Agent used: $agnt\n" if $verbose || ($resp->status_line !~ /403 /);
    }
    return undef;
}

############################ NRWF (DE) method

# parse the NRWF page for data and insert it into DB
# routine from 14 Aug 2015 with only heute (today)!
sub parse_NRWF_heute {
    my $day = shift;
    my $station = shift;
    my $lines = shift;
    my $cnt = shift;
    my $date = '';
    @label = ('datum', 'time');
    @unit = ('','');
    @data = ();
    @rating = ();
    my %labs = ( zeit => 'tijd', ozon => 'o3', n => 'no', no2 => 'no2',
		ltem => 'temp', wri => 'wr', wges => 'ws', rfeu => 'rv',
		so2 => 'so2',
		'staub/pm10' => 'pm_10', 'staub/pm2.5' => 'pm_25',
		);
    my $tblfound = 0;
    my $row = 0; my $cel = 0; my $rslts = 0;
    my $rts = 0;
    my $hr_cnt = 0;
    print STDERR "Parsing data format type \"NRWF\" for station $station.\n" if $verbose;
    for( my $i=0; $i <= $cnt; $i++ ){
	$_ = $lines->[$i]; next if not $_;
	if( $tblfound < 1 && /<th\s[^>]*>Station\s+([^<]*)</i ){
	    my $town = $1; $town =~ s/\s//g;
	    if( $town !~ /$locations{$station}{name}/i ){
		print STDERR "$WARNING Obtained data for stationnr $station \"$town\" i.s.o. the expected name $locations{$station}{name}!\n";
	    }
	    # reached start of measurements values
	    $tblfound++; next;
	}
	$tblfound = 0 if /^<\/table/;
        next if $tblfound < 1;
	if( /<th[^>]*>([0-9]{2})\.([0-9]{2})\.([0-9]{4})<.th>$/ ){
	    $date = "$3/$2/$1"; $date =~ s/\/0/\//g;
	    $day =~ s/-/\//g; $day =~ s/\/0/\//g;
	    if( $day =~ /^([0-9]{1,2})\/([0-9]{1,2})\/(20[0-9]{2})/ ){
		$day = "$3/$2/$1";
	    }
	    if( $date ne $day ){
		print STDERR "$WARNING Date is $date and should be $day.\n";
	    }
	}
	if( /^\s*<\/tr\s*>/i ){
	    if( $rslts ){	# we got data parsed so dump it
		$rts = processDB($mytbl);
        	$hr_cnt++ if $rts;
        	processRRD() if $rts;
	    }
            @rating = (); @data = ();
	    $cel = -1; $row = 0; $rslts = 0;
	    next;
	}
	$row++ if /^\s*<tr/;
	next if not $row;
	next if not /class=.mw_/;
	$cel++ if /^\s*<t[dh]\s/i ;
	if( /<t[dh]\s.*mw_leer/i ){ next; }
	if( /<th\sscope.*col.*mw_[^>]*>([^<]+)</ ){
	    my $lab = lc($1); next if $cel < 2; $lab =~ s/\s//g;
	    $label[$cel] = $lab;
	    $label[$cel] = $labs{$lab} if $labs{$lab};
	    $unit[$cel] = '';
	    next;
	}
	if( /<td\sclass=[^>]*>([^<]*)</ ){
	    my $val = $1; $val =~ s/[^0-9:\.]//g; $val =~ s/:/./;
	    $val =~ s/^\.$//;
	    if( $cel == 0 && $val ){
		my $h = $val; $h =~ s/\..*//; $h =~ s/0([0-9])/$1/;
		$h = int($h); $val =~ s/.*\.//;
		$data[1] = sprintf("%2.2d.%2.2d",$h,$val);
		$data[0] = $day; $rating[1] = '';
	    } else { $data[$cel] = $val; }
	    $rating[$cel] = ''; $rslts++ if $cel > 1 && $val;
	    next;
	}
	    
    }
    if( not $quiet ){
        print STDERR "Date $day:";
        print STDERR " no new measurements found." if $hr_cnt < 1;
        print STDERR "\n";
        print STDERR "\tProcessed $hr_cnt hourly data measurements records.\n" if $hr_cnt;
    }
    return $hr_cnt;
}

# parse the NRWF page for data and insert it into DB
# this routine was used upto 14 Aug 2015 and had date
sub parse_NRWFtill14Aug2015 {
    my $day = shift;
    my $station = shift;
    my $lines = shift;
    my $cnt = shift;
    my $date = '';
    @label = ('datum', 'time');
    @unit = ('','');
    @data = ();
    @rating = ();
    my %labs = ( zeit => 'tijd', ozon => 'o3', ltem => 'temp', wri => 'wr',
		wges => 'ws', rfeu => 'rv', 'staub/pm10' => 'pm_10',
		'staub/pm2.5' => 'pm_25',
		);
    my $tblfound = 0;
    my $row = 0; my $cel = 0; my $rslts = 0;
    my $rts = 0;
    my $hr_cnt = 0;
    print STDERR "Parsing data format type \"NRWF\" for station $station.\n" if $verbose;
    for( my $i=0; $i <= $cnt; $i++ ){
	$_ = $lines->[$i]; next if not $_;
	if( $tblfound < 1 && /<th\s[^>]*>Station\s+([^<]*)</i ){
	    my $town = $1; $town =~ s/\s//g;
	    if( $locations{$station}{name} ne $town ){
		print STDERR "$ERROR Obtained data for stationnr $station \"$town\" i.s.o. $locations{$station}{name}!\n";
	    }
	    # reached start of measurements values
	    $tblfound++; next;
	}
	$tblfound = 0 if /^<\/table/;
        next if $tblfound < 1;
	if( /<th[^>]*>([0-9]{2})\.([0-9]{2})\.([0-9]{4})<.th>$/ ){
	    $date = "$3/$2/$1"; $date =~ s/\/0/\//g;
	    $day =~ s/-/\//g; $day =~ s/\/0/\//g;
	    if( $day =~ /^([0-9]{1,2})\/([0-9]{1,2})\/(20[0-9]{2})/ ){
		$day = "$3/$2/$1";
	    }
	    if( $date ne $day ){
		print STDERR "$WARNING Date is $date and should be $day.\n";
	    }
	}
	if( /^<\/tr\s*>/i ){
	    if( $rslts ){	# we got data parsed so dump it
		$rts = processDB($mytbl);
        	$hr_cnt++ if $rts;
        	processRRD() if $rts;
	    }
            @rating = (); @data = ();
	    $cel = -1; $row = 0; $rslts = 0;
	    next;
	}
	$row++ if /^<tr/;
	next if not $row;
	next if not /class=.mw_/;
	$cel++ if /^<t[dh]\s/i ;
	if( /<t[dh]\s.*mw_leer/i ){ next; }
	if( /<th\sscope.*col.*mw_[^>]*>([^<]+)</ ){
	    my $lab = lc($1); next if $cel < 2; $lab =~ s/\s//g;
	    $label[$cel] = $lab;
	    $label[$cel] = $labs{$lab} if $labs{$lab};
	    $unit[$cel] = '';
	    next;
	}
	if( /<td\sclass=[^>]*>([^<]*)</ ){
	    my $val = $1; $val =~ s/[^0-9:\.]//g; $val =~ s/:/./;
	    if( $cel == 0 ){
		my $v = $val; $v =~ s/\..*//; $v =~ s/0([0-9])/$1/;
		$v = int($v); $v-- if $v; $val =~ s/\..*//;
		$data[1] = sprintf("%2.2d.%2.2d",$v,$val);
		$data[0] = $day; $rating[1] = '';
	    } else { $data[$cel] = $val; }
	    $rating[$cel] = ''; $rslts++ if $cel > 1 && $val;
	    next;
	}
	    
    }
    if( not $quiet ){
        print STDERR "Date $day:";
        print STDERR " no new measurements found." if $hr_cnt < 1;
        print STDERR "\n";
        print STDERR "\tProcessed $hr_cnt hourly data measurements records.\n" if $hr_cnt;
    }
    return $hr_cnt;
}

# get 0 .. 23 hour measurements for one day Nord Rhein West Falen DE
# and day is older as two month from now
sub get_a_day_NRWF {
    my ( $loc, $day ) = @_;
    my $hour = 0;
    return 1 if (not defined $locations{$loc}) || ($locations{$loc}{organisation} ne 'NRWF');
    return 0 if defined $locations{$loc}{last} && (get_YYYYMMDD($locations{$loc}{last}) < get_YYYYMMDD($day));
    return 0 if defined $locations{$loc}{first} && (get_YYYYMMDD($locations{$loc}{first}) > get_YYYYMMDD($day));
    # check first if we have validated data
    state $host_warned = 0;
    my $name = get_YYYYMMDD($day); 
    if( int(strftime("%Y%m%d",localtime(time))) != $name ){
	$name =~ s/(20[0-9][0-9])([0-9][0-9])([0-9][0-9])/$1\/$2\/$3/;
	my $timing = Time::Piece->strptime("$name 00.00 +0100","%Y/%m/%d %H.%M %z")->epoch;
	return 1 if $timing > time;   # no data in the future
	return parse_NRWF_365( $day, $loc) if (time-$timing)/(24*60*60) <= 365;
        return parse_NRWF_hist($day, $loc);
    }
    # website keeps only data for today
    if( $host_warned++ == 0 ){
        printf STDERR ("Measurements from $datahosts{NRWF}{url} ($locations{$loc}{organisation}: $locations{$loc}{name} station $loc)%s\n", $verbose > 0 ? " for day $day" : "") if not $quiet;
    }
    # only data for heute (today), so run this just before midnight!
    $name = "/heut/$locations{$loc}{table}.htm";
    my $content = get_file('NRWF', $name);
    print STDERR "$ATTENT No data for date $day for $locations{$loc}{id}\n" if not $content;
    return 1 if not $content;
    print STDERR "Parsing data from format type NRWF for Euregio ID $locations{$loc}{id}, table $mytbl\n" if $verbose;
    @label =(); @unit = (); @data = (); @rating = ();
    my @line = split '\n', $content;
    return parse_NRWF_heute( $day, $loc, \@line, $#line);
}

# routine for NRWF data from 14 Aug 2015 for date before 365 days ago
sub parse_NRWF_hist {
    my $day = shift;
    my $loc = shift;
    print STDERR "ERROR: measurements from NRWF earlier as 365 days ago not yet implemented.\n";
    @label =(); @unit = (); @data = (); @rating = ();
    return 0;
}

# routine for NRWF data from 14th August 2015 for date up to 365 days ago
# for now we only handle one location
my %NRWF;
sub get_NRWF_sensor {
   my $URL_sensor = shift;
   my $loc = shift;
   my $sensor = $URL_sensor; $sensor =~ s/\.csv//i; $sensor =~ s/.*\///;
   my $name = $URL_sensor; $name =~ s/.*\///;
   my %labs = ( ltem => 'temp', t_am1h => 'temp', wri => 'wr', wr_vm1h => 'wr',
		wges => 'ws', wg_sm1h => 'ws', rfeu => 'rv', f_am1h => 'rv',
		'no' => 'no', no_am1h => 'no', 'no2' => 'no2', no2_am1h => 'no2',
		'o3' => 'o3', o3_am1h => 'o3', 'so2' => 'so2', so2_am1h => 'so2',
		'pm10' => 'pm_10', pm10f_gm24h => 'pm10',);
   my $my_sensor = lc($sensor);
   if( not defined $labs{$my_sensor} ){
	print STDERR "NRWF file $URL_sensor has new sensor $sensor\n";
   }
   $my_sensor = $labs{$my_sensor} if defined $labs{$my_sensor};
   my $content = get_file( 'NRWF', $name);
   return 0 if not $content;
   if( not $NRWF{labels} ){
	$NRWF{labels}[0] = "date"; $NRWF{labels}[1] = "time";
   }
   my $idx;
   for( $idx = 0; $idx <= $#{$NRWF{labels}}; $idx++ ){
       last if $NRWF{labels}[$idx] =~ /^$my_sensor$/;
   }
   $NRWF{labels}[$idx] = $my_sensor if $idx > $#{$NRWF{labels}};
   my @lines = split '\n', $content;
   my $index = -1; my $cnt = 0; my $tbl = $locations{$loc}{table};
   for( my $ln = 0; $ln <= $#lines; $ln++ ){
        $lines[$ln] =~ s/\s+$//;
	next if( not $lines[$ln] || ($index < 0 && $lines[$ln] !~ /^Datum/) );
	my @flds = split ';', $lines[$ln];
        my $date = '';
	if( $index < 0 && $lines[$ln] =~ /^Datum/ ){
	    for( my $fld = 0; $fld <= $#flds; $fld++ ){
	        # get index for the location
	        next if $flds[$fld] !~ /^${tbl}\s${sensor}F*\s/;
		$index = $fld;
		last;
	    }
	    next;
	}
	next if $index < 0;
	if( $index > $#flds || not defined $flds[$index] ){
		print STDERR "WARNING: strange CVS line found at line $ln for $URL_sensor.\n"  if not $quiet and $verbose > 0;
		next;
        }
	next if $lines[$ln] !~ /^([0-9][0-9])\.([0-9][0-9])\.(20[0-9][0-9]);/;
	# convert to YYYY/MM/DD HH.MM
        $flds[0] = "$3/$2/$1"; $flds[1] =~ s/([0-9]+):([0-9]+)(:00)*/$1.$2/;
	$flds[$index] = '' if $flds[$index] =~ /^\s*$/;
	if( $flds[$index] =~ /^</ ){
	    $flds[$index] =~ s/<//;
	    $flds[$index] = sprintf("%d",int($flds[$index] * 0.5));
	}
	$NRWF{$flds[0]} = {} if not defined $NRWF{$flds[0]};
	if( not $NRWF{$flds[0]}{$flds[1]} ){
	    $NRWF{$flds[0]}{$flds[1]}[0] = $flds[0]; $NRWF{$flds[0]}{$flds[1]}[1] = $flds[1];
	}
	if( $flds[$index] =~ /[0-9]/ ){
	    $flds[$index] =~ s/,/./;
	    $NRWF{$flds[0]}{$flds[1]}[$idx] = $flds[$index]; $cnt++;
	}
    }
    if( not $cnt ){
	return 0;
        # splice on scalar forbitten!
        #splice($NRWF{labels}, $idx, 1) if $idx > 1;
	print STDERR "INFO: NRWF CSV file $URL_sensor (sensor $my_sensor) has no measurements for $tbl.\n" if not $quiet and $verbose > 0;
	return 0;
    }
    return $cnt;
}

# get one day measurements for NRWF station
# get measurements for NRWF station for dates 365 days ago up to yesterday
# side effect get also other days with values for this station
sub parse_NRWF_365 {
    my $day = shift;
    my $loc = shift;
    # create cache of values for the whole 365 days for all sensors for this station
    if( not $NRWF{labels} ){	# get the last year measurements
	my $name = "/umwelt/luft/immissionen/berichte-und-trends/tageswerte/";
	my $content = get_file('NRWF', $name);
	my $ok = index $content, '<h3>Schadstoffe';
	if( $ok < 0 ){
	    print STDERR "FAILED to download file $name with sensor names for NRWF\n";
	    return 0;
	}
	$content = substr $content, $ok;
	$content = substr $content, 0, (index $content, "</ul>\n");
	$content =~ s/<\.{0,1}ul>\s*</</;
	$content =~ s/<li><a\s+href="/@/g;
	my @line = split '@', $content;
	for( my $ln = 0; $ln <= $#line; $ln++ ){
	    next if $line[$ln] !~ /CSV-Datei\s+zum\s+Download/;
	    $line[$ln] =~ s/\.csv"\s+.*/.csv/;
	    get_NRWF_sensor( $line[$ln], $loc ) if $line[$ln] =~ /\.csv$/i;
	}
    }
    # now we have eventually filled the NRWF hash table
    return 0 if not $NRWF{$day};
    state $host_warned = 0;
    my $hr_cnt = 0;
    if( $host_warned++ == 0 ){
        printf STDERR ("Measurements from $datahosts{NRWF}{url} ($locations{$loc}{organisation}: $locations{$loc}{name} station $loc)%s\n", $verbose > 0 ? " for day $day" : "") if not $quiet;
    }
    @label = (); @unit = ('',''); @rating = ();
    push @label, @{$NRWF{labels}};
    foreach my $hour (sort keys %{$NRWF{$day}} ){
	next if $#{$NRWF{$day}{$hour}} < 0;
	@data = ();
	push @data, @{$NRWF{$day}{$hour}};
	my $rts = processDB($mytbl);
	$hr_cnt++ if $rts;
	processRRD() if $rts;
    }
    if( not $quiet ){
        print STDERR "Date $day:";
        print STDERR " no new measurements found." if $hr_cnt < 1;
        print STDERR "\n";
        print STDERR "\tProcessed $hr_cnt hourly data measurements records.\n" if $hr_cnt;
    }
    return $hr_cnt;
}

# routine used till 14 Aug 2015
# get 0 .. 23 hour measurements for one day Nord Rhein West Falen DE
# and day is older as two month from now
sub get_a_day_NRWFtillAug2015 {
    my ( $loc, $day ) = @_;
    my $hour = 0;
    return 0 if defined $locations{$loc}{last} && (get_YYYYMMDD($locations{$loc}{last}) < get_YYYYMMDD($day));
    return 0 if defined $locations{$loc}{first} && (get_YYYYMMDD($locations{$loc}{first}) > get_YYYYMMDD($day));
    # check first if we have validated data
    state $host_warned = 0;
    if( $host_warned++ == 0 ){
        printf STDERR ("Measurements from $datahosts{NRWF}{url} ($locations{$loc}{organisation}: $locations{$loc}{name} station $loc)%s\n", $verbose > 0 ? " for day $day" : "") if not $quiet;
    }
    my $name = get_YYYYMMDD($day); 
    # website keeps only data for one year (365 days)
    return 0 if int(strftime("%Y%m%d",localtime(time - (365*24*60*60)))) > $name ;
    $name =~ s/^20[0-9][0-9]//;
    $name = "/$name/$locations{$loc}{table}.htm";
    my $content = get_file('NRWF', $name);
    print STDERR "$ATTENT No data for date $day for $locations{$loc}{id}\n" if not $content;
    return 1 if not $content;
    print STDERR "Parsing data from format type NRWF for Euregio ID $locations{$loc}{id}, table $mytbl\n" if $verbose;
    @label =(); @unit = (); @data = (); @rating = ();
    my @line = split '\n', $content;
    return parse_NRWF_heute( $day, $loc, \@line, $#line);
}
########################### END of NRWF method DE website

########################################### RIVM (NL) method
# get then data file from RIVM/NSL website

my %RIVM_queue = ();	# the queue as cache for to enter data into DB table
 
# deprecated
# unzip a xls spreadsheet file (only one file)
sub unzip {
    my ($file, $dest) = @_;
    my (undef, undef, $month) = splitpath($file);
    $month =~ s/\.zip$//;
 
    die 'Need a file argument' unless defined $file;
    $dest = "." unless defined $dest;
    $dest .= '/' unless $dest =~ /\/$/;
     
    my $u = IO::Uncompress::Unzip->new($file)
        or die "Cannot open $file: $UnzipError";
 
    my $status;
    my $once = 0;
    for( $status = 1; $status > 0; $status = $u->nextStream() ){
        my $header = $u->getHeaderInfo();
        my (undef, $path, $name) = splitpath($header->{Name});
        unless(-d $dest ){
            mkpath($dest) or die "Couldn't mkdir $dest: $!";
        }
 
        if( $name =~ m!/$! ){
            last if $status < 0;
            next;
        }
	if( $name !~ /.xlsx*$/ ){
	    print STDERR "$WARNING Will not extract $name, it is not a spreadsheet.\n";
	    next;
	}
        $dest .= $month . '.xls';
	$dest .= 'x' if $name =~ /x$/;
        if( $once++ ){
	    print STDERR "$WARNING Will skip extracting: $header->{Name}\n" if $verbose > 0;
	    next;
        }
 
        my $buff;
        my $fh = IO::File->new($dest, "w")
            or die "Couldn't write to $dest: $!";
        while (($status = $u->read($buff)) > 0 ){
            $fh->write($buff);
        }
        $fh->close();
        my $stored_time = $header->{'Time'};
        utime ($stored_time, $stored_time, $dest)
            or die "Couldn't touch $dest: $!";
	print STDERR "$ATTENT Extracted $header->{Name} to $dest.\n" if $verbose;
    }
 
    print STDERR "$ERROR Error processing $file: $!\n" if $status < 0 ;
    return '' if $status < 0;
 
    return  $dest;
}

# deprecated
# check if the month zip file is present on RIVM/NSL website
sub month_present {
    my $org = shift; my $file_name = shift;
    my $URL;
    if( not $URL ){
        $agnt = ((keys %agents)[int rand keys %agents]);
        $agnt = $agents{$agnt};
        $URL=LWP::UserAgent->new(agent => $agnt);
        $URL->timeout('40');
        if( system("pidof privoxy >/dev/null") ){
            $URL->env_proxy;
        } else {
            $URL->proxy('http', 'http://127.0.0.1:8118/');
        }
    }
    my $resp = $URL->get('http://'.$datahosts{$org}{'url'}.$datahosts{$org}{'action'});

    if( $resp->is_success ){
	return 1 if ( $resp->content =~ /$file_name/ ) ;
    } else {
        print STDERR "$ERROR Response status line: \n";
        print STDERR $resp->status_line;
        print STDERR "\n$ERROR Cannot obtain listing from http://$datahosts{$org}{'url'}.$datahosts{$org}{'action'}\n";
        print STDERR "Agent used: $agnt\n";
    }
    return 0;
}

# deprecated
# convert a zip compressed file into xls[x] file
sub zip2xls {
    my $month = shift;
    if( $month =~ /^(20[0-9][0-9])\/{0,1}([1-9]|[0-9]{2})(\/[0-9]{1,2})*$/ ){
	my $yr = $1; $month = $2; $month = "0$month" if length($month) != 2;
	$month = $yr . $month;
    } elsif( $month !~ /^20[0-9]{4}$/ ){
	print STDERR "$ERROR Cannot obtain YYYYMM identification from $month\n";
	return 0;
    }
    unless( -d ZIPDIR ){
        mkpath( ZIPDIR ) or die "$ERROR Couldn't mkdir ".ZIPDIR.": $!";
    }
    # check if zip month file is present on the website
    if( (not -f ZIPDIR."/$month.zip") &&
		month_present( 'rivm',"$month.zip") ){
        get_file('rivm', ZIPDIR."/$month.zip" );
    }
    return '' if not -f ZIPDIR."/$month.zip";
    unless( -d XLSDIR ){
        mkpath(XLSDIR) or die "$ERROR Couldn't mkdir ".XLSDIR.": $!";
    }
    return unzip( ZIPDIR."/$month.zip", XLSDIR."/");
}

sub get_YYYYMMDD {
    $_ = shift;
    if( /^([0-9]{1,2})[\-\/]([0-9]{1,2})[\-\/](20[0-9][0-9])$/ ){
	$_ = "$3/$2/$1";
    }
    s/^20([0-9][0-9])([0-9][0-9])/20$1\/$2\//;
    if( /^(20[0-9][0-9])[\-\/]([1-9]|[0-9]{2})[\-\/]([0-9]{1,2})*$/ ){
	my $da = '00'; $da = $3 if $3; 
	return "$1".sprintf("%0.2d",$2).sprintf("%0.2d",$da);
    } 
    return '00000000';
}
sub get_YYYY_MM_DD {
    $_ = shift;
    if( /^([0-9]{1,2})[\-\/]([0-9]{1,2})[\-\/](20[0-9][0-9])$/ ){
        $_ = "$3/$2/$1";
    }
    s/^20([0-9][0-9])([0-9][0-9])/20$1\/$2\//;
    if( /^(20[0-9][0-9])[\-\/]([1-9]|[0-9]{2})[\-\/]([0-9]{1,2})*$/ ){
        my $da = '00'; $da = $3 if $3;
        return "$1".sprintf("-%0.2d",$2).sprintf("-%0.2d",$da);
    }
    return '0000-00-00';
}
# return month as YYYYMM
sub get_YYYYMM {
    $_ = shift;
    return substr( get_YYYYMMDD($_), 0, 6);
}

# get one hour of measurements from web site
# on success the values will be invalidated
# if no success either values are not yet available or there are
# validated monthly values

# station nr eg 131, day e.g. 2020/2/12, upload data later as $hour: e.g. hour 11
sub get_timeslice_RIVM {
    my ( $loc, $day, $from ) = @_;
    my $may_fail = 0; my $start; my $end; my $stationID = $locations{$loc}{table};
    my %RIVM_data = ( # uploaded json data
        station_number => 0,
        strt => 0,
        data => {},
    );
    if( $day =~ /^(20[0-9][0-9])\/{0,1}([1-9]|[0-9]{2})(\/[0-9]{1,2})*$/ ){
        my $f = sprintf("%0.2d", $from);
        if( int(get_YYYYMMDD($day).$f) + 2 > int(strftime("%Y%m%d%H", localtime(time))) ) {
            $may_fail = 1;
        }
        $start = Time::Piece->strptime("$day $f.30 +0100",'%Y/%m/%d %H.%M %z')->epoch;
        #$start -= 60*60 if not $from;
        $start += 30*60 if not $from;
        $end = Time::Piece->strptime("$day 23.59 +0100",'%Y/%m/%d %H.%M %z')->epoch;
        $end += 30*60+1;
    } else {
	print STDERR "$ERROR Wrong date format for $day\n";
	return 0;
    }
    if( ($RIVM_data{station_number} != $loc) || (not $RIVM_data{start}) ){
        $may_fail = 1;
        my $action = sprintf("station_number=%s&start=%s&end=%s", $stationID,
            utc_to_iso8601($start), utc_to_iso8601($end) );
        $RIVM_data{data} = ();
        $RIVM_data{strt} = $start; $RIVM_data{station_number} = $loc;
        for( my $page=1; ; $page++) { # upload all data in timeslice period from RIVM
            my $content = get_file('RIVM', 'measurements?' . $action . sprintf("&page=%d",$page), $may_fail);
            last if not $content;
            $content = decode_json($content);
            push (@{$RIVM_data{data}}, @{$$content{data}});
            last if $$content{pagination}{last_page} == $page;
        }
        for( my $page=1; $LKI > 0; $page++) {
            my $content = get_file('RIVM', 'lki?' . $action . sprintf("&page=%d",$page), $may_fail);
            last if not $content;
            $content = decode_json($content);
            push (@{$RIVM_data{data}}, @{$$content{data}});
            last if $$content{pagination}{last_page} == $page;
        }
    } else { return 0; }
    # delete unknown stations from data array
    my %time_data = (); # data stream to archive
    if( $#{$RIVM_data{data}} < 0 ) {
        print STDERR "$ERROR NSL luchtmeetnet.nl connection failure, download $stationID data for $day from $from:30:00\n";
        return 0;
    }
    print STDERR "Parsing RIVM $#{$RIVM_data{data}} json records of hourly data $day $from:30:00 json format RIVM\n" if $debug;
    for( my $i=$#{$RIVM_data{data}}; $i >= 0; $i--) {
        if( $RIVM_data{data}[$i]{station_number} !~ /^$stationID$/ ) {
            splice( @{$RIVM_data{data}}, $i, 1); next;
        }
        my $utc =  iso8601_to_utc($RIVM_data{data}[$i]{timestamp_measured});
        if( not defined $time_data{$utc}) {
            $time_data{$utc} = {
                label => ['',''], unit => ['',''],
                data => ['',''], rating => ['','']
            };
            # RIVM uses upto timestamp for avg sensor measurement for one hour
            my $time = strftime("%d-%m-%Y %H.%M", localtime($utc-30*60)); # use middle iso last
            ($time_data{$utc}{data}[0], $time_data{$utc}{data}[1]) = split /\s+/, $time;
        }
        my $pol = lc($RIVM_data{data}[$i]{formula});
        $pol =~ s/pm([0-9])\.?([0-9])/pm_$1$2/g;
        $pol =~ s/fn/pm01/; $pol =~ s/PS/pm1/i;
        my @find = grep(/^$pol$/,  @{$time_data{$utc}{label}});
        if ( $#find >= 0 ) {
            print STDERR "Found double pollutant $pol in json record station $stationID $time_data{$utc}{data}[0] $time_data{$utc}{data}[1]\n"; # if $verbose;
            next;
        }
        my $val = $RIVM_data{data}[$i]{value};
        push( @{$time_data{$utc}{label}}, $pol);
        push( @{$time_data{$utc}{data}}, $val);
        push( @{$time_data{$utc}{unit}}, '');
        push( @{$time_data{$utc}{rating}}, '');
    }
    printf STDERR ("Got %d data records of hourly data $day $from:30:00 station $locations{$loc}{table}\n", scalar keys %time_data) if $verbose;
    foreach my $k (sort { $a <=> $b } keys %time_data ) {
        next if $#{$time_data{$k}{data}} < 2;
        @label = @{$time_data{$k}{label}};
        @unit = @{$time_data{$k}{unit}};
        @data = @{$time_data{$k}{data}};
        @rating = @{$time_data{$k}{rating}};
        processRRD() if processDB( $locations{$loc}{table});
    }
    @label = ('',''); @unit = ('',''); @data = ('',''); @rating = ('','');

    return 0;
}

# RIVM Open Data API in use since 10 febr 2020
# see http://api-docs.luchtmeetnet.nl/?version=latest
use JSON;                       # data is sent via HTTP GET request. Response is JSON format
#use DateTime;
#use data::dumper;

# next routines use open data RIVM API interface from 10 Febr 2020
# get 0 .. 23 hour measurements for one day
# get data of interval start .. end hour, max is 7 days (we do one day per request)
sub get_a_day_RIVM {
    my ( $loc, $day ) = @_;
    my $hour = 0; my $last_hr = 23;
    state $my_day = '00000000';
    return 0 if defined $locations{$loc}{last} && (get_YYYYMMDD($locations{$loc}{last}) < get_YYYYMMDD($day));
    return 0 if defined $locations{$loc}{first} && (get_YYYYMMDD($locations{$loc}{first}) > get_YYYYMMDD($day));
    # check first if we have validated data
    state $host_warned = 0;
    if( $host_warned++ == 0 ){
        printf STDERR ("Measurements from $datahosts{rivm}{url} ($locations{$loc}{organisation}: $locations{$loc}{name} station $loc)%s\n", $verbose > 0 ? " for day $day" : "") if not $quiet;
    }
    my $now = int(strftime("%Y%m%d",localtime(time())));
    if( $now == int(get_YYYYMMDD($day)) ) {
        $last_hr = int(strftime("%H",localtime(time())))-1;
    }
    # pick up latest hour measurements we have in DB
    if( (not $overwrite)
        && (defined $locations{$loc}{table})
        && Check_Tbl($locations{$loc}{table}) ){
        # NSL timing is measurement ending at hour, and archive as minus 30 minutes
        my $lqr = long_query($locations{$loc}{table},"SELECT DATE_FORMAT(datum,'%Y%m%d'), hour(datum)+1 from $locations{$loc}{table} ORDER BY datum DESC LIMIT 1");
        if( ($#{$lqr} >= 0) && ($lqr->[0][0] == get_YYYYMMDD($day)) ){
            $hour = $lqr->[0][1]; # upload data later as $day + $hour
        }
    }
    if ( not get_timeslice_RIVM( $loc, $day, $hour ) ){ # upload from $hour at the day $day station nr $loc
       if( get_YYYYMM( $day) > strftime("%Y%m", localtime(time - 32*24*60*60)) ){
           print STDERR "$ATTENT Cannot obtain data for day $day hour $hour\n" if $verbose and $hour;
           return 0;
       }
       print STDERR "$ATTENT No hourly data ($day $hour:00), will try to get validated values for the whole month\n" if $verbose;
       return 0 if $my_day == get_YYYYMM($day);
       $my_day = get_YYYYMMDD($day) if $my_day =~ /00000000/;
     }

    return 1;
}

sub utc_to_iso8601{
    my $uts = shift;
    return strftime('%Y-%m-%dT%H:%M:%SZ', gmtime($uts));
}
use DateTime::Format::ISO8601;  # from libdate-iso8601-perl
sub iso8601_to_utc{
    my $iso = shift;
    return DateTime::Format::ISO8601->parse_datetime($iso)->epoch();
}

# collect all monthly RIVM location sensor data
# push the data later into the DB per month
sub queue_for_DB {
    my ($location, $sensor, $time, $value) = @_;
    $RIVM_queue{location} = $location if not defined $RIVM_queue{location};
    if( not defined $locations{$location}{table} ){
        print STDERR "$ERROR Location $location DB table is not defined!\n";
	return;
    }
    $RIVM_queue{table} = $locations{$location}{table} if not defined $RIVM_queue{table};
    print STDERR "$WARNING Location $location differs from $RIVM_queue{location}!\n"
	if $RIVM_queue{location} ne $location;
    return if $RIVM_queue{location} ne $location;
    return if not $sensor || not $time || (length($value) == 0);
    # map external name to internal sensor name
    $sensor =~ s/pm([0-9])\.?/pm_$1/; $sensor =~ s/zwr$/roet/;
    $sensor =~ s/[^0-9a-z_]//;
    $RIVM_queue{labels}[0] = 'date' if not defined $RIVM_queue{labels}[0];
    $RIVM_queue{labels}[1] = 'time' if not defined $RIVM_queue{labels}[1];
    if( not grep /^$sensor$/, @{$RIVM_queue{labels}} ){
	push @{$RIVM_queue{labels}}, $sensor;
    }
    my $col;
    for( $col = 2; $col <= $#{$RIVM_queue{labels}}; $col++ ){
	last if $RIVM_queue{labels}[$col] eq $sensor;
    }
    $RIVM_queue{data} = () if not defined $RIVM_queue{data};
    # RIVM provides the time in MET last minute of the measurement hour
    # so subtract 60 minutes if one uses the style: half of the hourly measurement
    # $time format: YY/MM/DD  HH.MM
    $time = Time::Piece->strptime("$time +0100",'%Y/%m/%d %H.%M %z')->epoch;
    $time -= 60*60; $time = strftime("%Y/%m/%d %H.%M", localtime($time));
    my ($day, $hour) = split /\s+/, $time; $fnd = -1;
    for( my $i = 0; $i <= $#{$RIVM_queue{data}}; $i++ ){
	$fnd = $i if $RIVM_queue{data}[$i]->[0] eq $day && $RIVM_queue{data}[$i]->[1] eq $hour;
	last if $fnd >= 0;
    }
    if( $fnd < 0 ){
	$fnd = $#{$RIVM_queue{data}} + 1;
	$RIVM_queue{data}[$fnd]->[0] = $day;
	$RIVM_queue{data}[$fnd]->[1] = $hour;
    }
    $value =~ s/[,\.]([0-9]{0,3}).*/.$1/;	# max 3 decimals
    $RIVM_queue{data}[$fnd]->[$col] = $value;
    print STDERR "$ATTENT Queued data row nr $fnd for location nr $location, table $locations{$location}{table}:\n\tdate: $RIVM_queue{data}[$fnd]->[0] $RIVM_queue{data}[$fnd]->[1], sensor $RIVM_queue{labels}[$col]: $RIVM_queue{data}[$fnd]->[$col]\n" if $verbose > 2;
}

sub sort_on_date {
    Time::Piece->strptime("$a->[0] $a->[1] +0100","%Y/%m/%d %H.%M %z")->epoch
        <=>
    Time::Piece->strptime("$b->[0] $b->[1] +0100","%Y/%m/%d %H.%M %z")->epoch
}

# dequeue data from queue into DB
sub dequeue_for_DB {
    return if not $RIVM_queue{location} or not $RIVM_queue{table};
    return if not $RIVM_queue{labels} or $#{$RIVM_queue{labels}} < 2;
    @label = @{$RIVM_queue{labels}};
    if( $#{$RIVM_queue{data}} >= 0 ){
        my @sorted = sort sort_on_date @{$RIVM_queue{data}};
         @{$RIVM_queue{data}} = @sorted; undef @sorted;
    }
    if( not $quiet ){
        print STDERR
	    "$ATTENT Wait for dequeuing $#{$RIVM_queue{data}} records.\n"
	    if isatty();
    }
    for( my $i = 0; $i <= $#{$RIVM_queue{data}}; $i++ ){
	next if $#{$RIVM_queue{data}[$i]} < 2;
	@unit = ();
	@rating = ();
	@data = @{$RIVM_queue{data}[$i]};
	processDB($RIVM_queue{table});
	processRRD;
	if( $verbose > 2 ){
	    print STDERR "$ATTENT Push data into table $RIVM_queue{table}, date $data[0] $data[1]:\n";
	    my @lab = @label;
	    splice(@data,0,2); splice(@lab,0,2);
	    printf STDERR (" sensors:\t%s\n    data:\t%s\n",join("\t",@lab),join("\t",@data)); 
	}
    }
    @data = (); @label = (); @unit = (); @rating = ();
    %RIVM_queue = ();
}

# parse xlsx file and queue cell by cell for one month of dayly values
# file will be cached on request 
# some spreadsheets files may have several months
sub get_cells_xlsx {
    my ($cache, $file, $loc, $month, @sensors) = @_;
    return get_cells($cache, $file, $loc, $month, @sensors) if $file =~ /\.xls$/;
    my @dat;
    return 0 if not -f $file;
    state $cached = 0;
    state $my_file = XLS2013;
    my $xls = 0;
    $xls = $cached if $file eq $my_file; # only the first cacheble file
    if( not $xls ){
        print STDERR "$ATTENT Reading xlsx spreadsheet file $file ..." if isatty();
        my $converter = Text::Iconv -> new ("utf-8", "windows-1251");
        $xls = Spreadsheet::XLSX -> new($file, $converter);
        print STDERR " DONE\n" if isatty();
	$cached = $xls if $cache;
	$my_file = $file if $cache;
    }
    if( ($#sensors >= 0) && (grep /^all/, @sensors) ){
	@sensors = ();
        foreach my $sheet (@{$xls->{Worksheet}} ){
	    my $sheetname = lc($sheet->{Name}); # lowercase sheet Name
            next if $sheetname =~ /Toelichting/i ;
	    push @sensors, $sheetname;
	}
    }
    foreach my $sheet (@{$xls->{Worksheet}} ){
        my $yr; my $mo; my $da; my $hr= 12; my $col = -1;
	my $sheetname = lc($sheet->{Name}); # lowercase sheet Name
	next if $sheetname =~ /Toelichting/i ;
	next if $#sensors >= 0 && not grep /^$sheetname$/, @sensors;
	foreach my $row ($sheet->{MinRow} .. $sheet->{MaxRow} ){
	    $_ = $sheet -> {Cells}[$row][$sheet->{MinCol}]->{Val};
	    next if not defined $sheet -> {Cells}[$row][$sheet->{MinCol}]->{Val
};
	    next if length($_) == 0;
	    if( /Station:/i ){
	 	for( my $ind = $sheet->{MinCol} + 1;  $ind <= $sheet->{MaxCol}; $ind++ ){
		    $col = $ind if $sheet -> {Cells}[$row][$ind]->{Val} eq $loc;
		    last if $col > 0;
		}
		last if $col < 0;
	    }
	    next if $col < 0;
	    if( /^[0-9]{5,}$/ ){ # got number of days after 0 jan 1900
		$_ = strftime('%d/%m/%Y', localtime( (int($_)-25569)*24*60*60));
	    }
	    if( /([0-3][0-9])[\/\-]([01][0-9])[\/\-]([12][09][0-9]{2})\s*([0-9]+[:\.][0-9]+)*$/ ){
		$yr = $3, $mo = $2, $da = $1;
		$hr = $4; $hr = '' if not defined $hr;
		next if $month ne $yr.$mo;
	        next if not defined $sheet->{Cells}[$row][$col]->{Val};
	        next if not length( $sheet->{Cells}[$row][$col]->{Val});
		if( length($hr) > 0 ){ $hr =~ s/[:\.].*//; $hr .= '.25'; }
	    } else { next; }
	    if( length($hr) < 1 ){ # day average
		for( my $i = 0; $i < 24; $i++ ){
		    queue_for_DB( $loc, $sheetname,
			sprintf("$yr/$mo/$da %0.2d.25",$i),
			$sheet->{Cells}[$row][$col]->{Val});
		}
	    } else {	#  different from hour to hour
	        queue_for_DB( $loc, $sheetname, "$yr/$mo/$da $hr",
		    $sheet->{Cells}[$row][$col]->{Val});
	    }
	}
    }
}

# parse a spreadsheet file and queue them one cell by one cell
# file will be cached on request 
# some spreadsheets files may have several months
sub get_cells {
    my ($cache, $file, $loc, $month, @sensors) = @_;
    return get_cells_xlsx($cache, $file, $loc, $month, @sensors) if $file =~ /\.xlsx$/;
    state $cached = 0; state $my_file = XLS2013;
    my $xls = 0;
    $xls = $cached if $file eq $my_file; # only the first cacheble file
    if( not $xls ){
        print STDERR "$ATTENT Reading spreadsheet file $file ..." if isatty();
        $xls = Spreadsheet::ParseExcel::Simple->read($file);
        print STDERR " DONE\n" if isatty();
        $cached = $xls if $cache;
        $my_file = $file if $cache;
    }
    # if all is defined in sensors get all sensors types
    if( $#sensors >= 0 && grep /^all/, @sensors ){
	@sensors = ();
        foreach my $sheet ($xls->sheets ){
	    my $sheetname = lc($sheet->{sheet}->{Name});
            next if $sheetname =~ /Toelichting/i ;
	    push @sensors, $sheetname;
	}
    }
    foreach my $sheet ($xls->sheets ){
        my $yr; my $mo; my $da; my $hr= 12; my $col = -1;
	my $sheetname = lc($sheet->{sheet}->{Name}); # lowercase sheet Name
	next if $sheetname =~ /Toelichting/i ;
	next if $#sensors >= 0 && not grep /^$sheetname$/, @sensors;
	while ($sheet-> has_data ){
	    my @dat = $sheet->next_row;
	    next if $#dat < 1;
	    if( $dat[0] =~ /Station:/i ){
		for( my $ind = 1; $ind <= $#dat; $ind++ ){
		    if( lc($dat[$ind]) eq $loc ){
			$col = $ind; last;
		    }
		}
		last if $col < 0;
		next;
	    } elsif( $dat[0] =~ /^[0-9]{5,}$/ ){ # got number of days after 0 jan 1900
		$dat[0] = strftime('%d/%m/%Y', localtime( ($dat[0]-25569)*24*60*60));
	    }
	    if( $dat[0] =~ /([0-3][0-9])[\/\-]([01][0-9])[\/\-]([12][09][0-9]{2})\s*([0-9]{2}[:\.][0-9]+)*$/ ){
		$yr = $3, $mo = $2, $da = $1;
		$hr = $4; $hr = '' if not defined $hr;
		next if $month ne $yr.$mo;
	        next if not defined $dat[$col];
	        next if defined $dat[$col] && (length( $dat[$col] ) == 0);
		if( length($hr) > 0 ){ $hr =~ s/[:\.].*//; $hr .= '.15'; }
	    } else { next; }
	    if( length($hr) < 1 ){ # day average
		for( my $i = 0; $i < 24; $i++ ){
		    queue_for_DB( $loc, $sheetname,
			sprintf("$yr/$mo/$da %0.2d.15",$i), $dat[$col]);
		}
	    } else { 	# different from hour to hour
	        queue_for_DB( $loc, $sheetname, "$yr/$mo/$da $hr",
		    $dat[$col]);
	    }
	}
    }
}

# get_a_day_RIVM('131', $ARGV[0], ('all',) );
########################################### end of RIVM functions

########################################### prov. Limburg: RUD
# parse data data convention based on Limburg website up to 14th Aug 2014
# identified as 'first'
sub parse_2010 {
    my $day = shift;
    my $station = shift;
    my $lines = shift;
    my $cnt = shift;
    @label = ();
    @unit = ();
    @data = ();
    @rating = ();
    my $rslt = ''; my $tblfound = 0;
    my $row = 0; my $cel = 0;
    my $rts = 0; my $skip = 0;
    my $max = 0; my $hr_cnt = 0; my $avg_cnt = 0; my $max8_cnt = 0;
    $dflt_hst = 'first';
    print STDERR "Parsing data to format type \"$dflt_hst\" operational up to 14 Aug 2014\n" if $verbose;
    for( my $i=0; $i <= $cnt; $i++ ){
	if( $tblfound < 1 && $lines->[$i] =~ /<option\s+value="([0-9]+)"\s*selected\s*>\s*[0-9]+\s+\-\s+([^<]*)<\/option>/i ){
	    if( $1 eq $station ){
		$town = $2;
	    } else {
		print STDERR "$ERROR Obtained data from station $1 i.s.o. $location!";
		return 0;
	    }
	}
        if( $lines->[$i] =~ /<tr\s+height=/i ){
	    # reached start of measurements values
	    $tblfound++;
	}
        next if $tblfound < 1;
	if( $lines->[$i] =~ /<td\s.*8-uursdaggemiddelde.*<\/td>/i ){
	    @data = ( $day, '12.00' ); $cel = 0; @rating = (); my $tr = FALSE;
	    for( ; $i <= $cnt; $i++ ){
		last if $lines->[$i] =~ /24-uursgemiddelde/;
		$tr = TRUE if $lines->[$i] =~ /<\/tr[>\s]/;
		next if $tr;
		next if $lines->[$i] !~ /<td\s+/;
		if( $lines->[$i] =~ /colspan="([0-9]+)"/ ){
			$cel += $1;
		}
	        elsif( $lines->[$i] =~ /bgcolor="#([a-fA-F0-9]+)"[^>]*>([^<]*)<\/td>/ ){
		    $rating[$cel] = uc($1);
		    $data[$cel] = $2;
	    	    $data[$cel] =~ s/\&nbsp;//g; $data[$cel] =~ s/\s+//g;
		    $max8_cnt++ if length($data[$cel]); $cel++;
	        } else { $cel++; } 
	    }
	    processDB( $mytbl . MAX_8HRS ) if $#data > 1;
	}
	if( $lines->[$i] =~ /<td\s.*24-uursgemiddelde.*<\/td>/i ){
	    @rating = (); @data = ( $day, '12.00' ); $cel = 0;
	    for( my $j=$i; $j <= $cnt; $j++ ){
		last if $lines->[$j] =~ /<\/tr[>\s]/;
		next if $lines->[$j] !~ /<td\s+/;
		if( $lines->[$j] =~ /colspan="([0-9]+)"/ ){
			$cel += $1;
		}
	        elsif( $lines->[$j] =~ /bgcolor="#([a-fA-F0-9]+)"[^>]*>([^<]*)<\/td>/ ){
		    $rating[$cel] = uc($1);
		    $data[$cel] = $2;
	    	    $data[$cel] =~ s/\&nbsp;//g; $data[$cel] =~ s/\s+//g;
		    $avg_cnt++ if length($data[$cel]); $cel++;
	       } else { $cel++; } 
	    }
	    processDB( $mytbl . DAY_AVG ) if $#data > 1;
	    # to do: add code to add average/color to database
	    # end of measurements, skip rest
	    $skip++;
	}
	next if $skip;
	if( $lines->[$i] =~ /<\/tr>/i && $row > 2 ){
	    # we have one data row and can process it
	    $rts = processDB($mytbl);
	    $hr_cnt++ if $rts;
	    processRRD() if $rts;
	    @rating = (); @data = (); $cel = 0;
	    next;
	}
        next if $lines->[$i] !~ /<t/i ;
	if( $lines->[$i] =~ /<tr/i ){ $cel=0; $row++; next; };
	next if ( $lines->[$i] !~ /<td/i );
        print STDERR "row=$row, cel=$cel, line: $lines->[$i]\n" if $debug > 1;
	$max = $cel if $cel > $max;
	if( $lines->[$i] =~ /<td.*TabHeader[^>]*>(.*)<\/td>.*/i ){
	    # has now all types of measurements
	    $label[$cel] = $1;
	    $label[$cel] =~ s/\&nbsp;//ig;
	    $label[$cel] =~ s/<[^>]*>//g;
	    $label[$cel] =~ s/\s+/_/g; $label[$cel] =~ s/[,\.]//g;
	    $label[$cel] = lc($label[$cel]);
	    $cel++; next;
	}
	elsif( $lines->[$i] =~ /<td.*middle">(.*)<\/td>.*/i ){
	    # has now all data types of measurements
	    $unit[$cel] = $1;
	    $unit[$cel] =~ s/<[^>]+>//g;
	    $unit[$cel] =~ s/\&nbsp;//g;
	    $unit[$cel] =~ s/\&mu;/u/g;
	    $unit[$cel] = lc($unit[$cel]);
	    $cel++; next;
	}
	elsif( $lines->[$i] =~ /<td\s+bgcolor\s*=\s*"?#([0-9A-F]{6})"?.*dynform"\s*>(.*)<\/td\s*>.*/i ){
	    $rating[$cel] = uc($1);
	    $data[$cel] = $2;
	    $data[$cel] =~ s/\&nbsp;//g;
	    # here we push time to half of between
	    $data[$cel] =~ s/\.00\s+-\s+[0-9]+\..*/.30/ if ( $cel == 1 );
	    $data[$cel] =~ s/\s+//g;
	    $day = $data[$cel] if $cel == 0;
	    $cel++; next;
	}
	    
    }
    $row -= 3; $max--;
    if( not $quiet ){
        print STDERR "Date $day:";
        print STDERR " no new measurements found." if $hr_cnt < 1;
        print STDERR "\n";
        print STDERR "\tProcessed $hr_cnt hourly data measurements records.\n" if $hr_cnt;
        print STDERR "\tProcessed $max8_cnt day max 8 hrs average records.\n" if $max8_cnt;
        print STDERR "\tProcessed $avg_cnt day average records.\n" if $avg_cnt;
        print STDERR "$ATTENT no max 8 hrs avg values found.\n" if not $max8_cnt && $verbose;
        print STDERR "$ATTENT no day average values found.\n" if not $avg_cnt && $verbose ;
    }
    return $hr_cnt;
}

# parse data data convention based on Limburg website after April 2014
# identified as 'second'
sub parse_2014 {
    my $day = shift;
    my $station = shift;
    my $lines = shift;
    my $cnt = shift;
    @label = ();
    @unit = ();
    @data = ();
    @rating = ();
    my $rslt = ''; my $tblfound = 0;
    my $row = 0; my $cel = 0;
    my $rts = 0; my $skip = 0;
    my $max = 0; my $hr_cnt = 0; my $avg_cnt = 0; my $max8_cnt = 0;
    $dflt_hst = 'second';
    print STDERR "Parsing data to format type \"$dflt_hst\" operational after April 2014\n" if $debug;
    $town = $locations{$station}{name} if $locations{$station};
    for( my $i=0; $i <= $cnt; $i++ ){
        if( $lines->[$i] =~ /<tr\s+height=/i ){
	    # reached start of measurements values
	    $tblfound++;
	}
        next if $tblfound < 1;
	if( $lines->[$i] =~ /<td\s.*8-uursdaggemiddelde.*<\/td>/i ){
	    @data = ( $day, '12.00' ); $cel = 0; @rating = (); my $tr = FALSE;
	    for( ; $i <= $cnt; $i++ ){
		last if $lines->[$i] =~ /24-uursgemiddelde/;
		$tr = TRUE if $lines->[$i] =~ /<\/tr[>\s]/;
		next if $tr;
		next if $lines->[$i] !~ /<td\s+/;
		if( $lines->[$i] =~ /colspan="([0-9]+)"/ ){
			$cel += $1;
		}
	        elsif( $lines->[$i] =~ /style="background-color:\s+#([a-fA-F0-9]{6})[^>]*>([^<]*)\s*<\/td>/i ){
		    $rating[$cel] = uc($1);
		    $data[$cel] = $2;
	    	    $data[$cel] =~ s/\&nbsp;//g; $data[$cel] =~ s/\s+//g;
		    $max8_cnt++ if length($data[$cel]); $cel++;
	       } else { $cel++; } 
	    }
	    processDB( $mytbl . MAX_8HRS ) if $#data > 1;
	}
	if( $lines->[$i] =~ /<td\s.*24-uursgemiddelde.*<\/td>/i ){
	    @rating = (); @data = ( $day, '12.00' ); $cel = 0;
	    for( my $j=$i; $j <= $cnt; $j++ ){
		last if $lines->[$j] =~ /<\/tr[>\s]/;
		next if $lines->[$j] !~ /<td\s+/;
		if( $lines->[$j] =~ /colspan="([0-9]+)"/ ){
			$cel += $1;
		}
	        elsif( $lines->[$j] =~ /style="background-color:\s+#([a-fA-F0-9]{6})[^>]*>([^<]*)\s*<\/td>/i ){
		    $rating[$cel] = uc($1);
		    $data[$cel] = $2;
	    	    $data[$cel] =~ s/\&nbsp;//g; $data[$cel] =~ s/\s+//g;
		    $avg_cnt++ if length($data[$cel]); $cel++;
	        } else { $cel++; }
	    }
	    processDB( $mytbl . DAY_AVG ) if $#data > 1;
	    # to do: add code to add average/color to database
	    # end of measurements, skip rest
	    $skip++;
	}
	next if $skip;
	if( $lines->[$i] =~ /<\/tr>/i && $row > 2 ){
	    # we have one data row and can process it
	    $rts = processDB($mytbl);
	    $hr_cnt++ if $rts;
	    processRRD() if $rts;
	    @rating = (); @data = (); $cel = 0;
	    next;
	}
        next if $lines->[$i] !~ /<t/i ;
	if( $lines->[$i] =~ /<tr/i ){ $cel=0; $row++; next; };
	next if $lines->[$i] !~ /<td/i;
        print STDERR "row=$row, cel=$cel, line: $lines->[$i]\n" if $debug > 1;
	$max = $cel if $cel > $max;
	if( $lines->[$i] =~ /<td\s+class=.header[^>]*>(.*)<\/td>.*/i ){
	    # has now all types of measurements
	    $label[$cel] = $1;
	    $label[$cel] =~ s/\&nbsp;//ig;
	    $label[$cel] =~ s/<[^>]*>//g;
	    $label[$cel] =~ s/\s+/_/g; $label[$cel] =~ s/[,\.]//g;
	    $label[$cel] = lc($label[$cel]);
	    $cel++; next;
	}
	elsif( $lines->[$i] =~ /<td.*unit">(.*)<\/td>.*/i ){
	    # has now all data types of measurements
	    $unit[$cel] = $1;
	    $unit[$cel] =~ s/<[^>]+>//g;
	    $unit[$cel] =~ s/\&nbsp;//g;
	    $unit[$cel] =~ s/\&mu;/u/g;
	    $unit[$cel] = lc($unit[$cel]);
	    $cel++; next;
	}
	elsif( $lines->[$i] =~ /<td\s+.*background-color\s*:\s*#([0-9A-F]{6})[^>]*>(.*)<\/td\s*>.*/i ){
	    $rating[$cel] = uc($1);
	    $data[$cel] = $2;
	    $data[$cel] =~ s/\&nbsp;//g;
	    $data[$cel] =~ s/\.00\s+-\s+[0-9]+\..*/.30/ if $cel == 1;
	    $data[$cel] =~ s/\s+//g;
	    $day = $data[$cel] if $cel == 0;
	    $cel++; next;
	}
	elsif( $lines->[$i] =~ /<td\s+class=\"?datacell[^>]*>([^<]*)<\/td\s*>.*/i ){
	    $rating[$cel] = 'FFFFFF';
	    $data[$cel] = $1;
	    $data[$cel] =~ s/\&nbsp;//g;
	    # here we push time to half of between
	    $data[$cel] =~ s/\.00\s+-\s+[0-9]+\..*/.30/ if $cel == 1;
	    $data[$cel] =~ s/\s+//g;
	    $day = $data[$cel] if $cel == 0;
	    $cel++; next;
	}
	    
    }
    $row -= 3; $max--;
    if( not $quiet ){
        print STDERR "For date $day:";
        print STDERR "\t no new measurements found." if $hr_cnt < 1;
        print STDERR "\n";
        print STDERR "\tProcessed $hr_cnt hourly data measurements records.\n" if $hr_cnt;
        print STDERR "\tProcessed $max8_cnt day max 8 hrs average records.\n" if $max8_cnt;
        print STDERR "\tProcessed $avg_cnt day average records.\n" if $avg_cnt;
        print STDERR "$ATTENT no max 8 hrs avg values found.\n" if $max8_cnt < 1 && $verbose;
        print STDERR "$ATTENT no day average values found.\n" if $avg_cnt < 1 && $verbose ;
    }
    return $hr_cnt;
}

# try to link data format to parsing method
# parse Limburg website data, e.g. 'first' (~2010-14 Aug 2014) or 'second' (2014)
sub parse {
    my $day = shift;
    my $station = shift;
    my @lines = split '\n', $content;
    @label = ();	# label/header of the cell (column) date, time, ...
    @unit = ();		# unit type of the values, eg mBar, ...
    @data = ();		# value measured
    @rating = ();	# html color or rating of the value
    for( my $i=0; $i <= $#lines; $i++ ){
	return parse_2014( $day, $station, \@lines, $#lines) if $lines[$i] =~ /<td\s+class=.datacell.\s+/;
	return parse_2010( $day, $station, \@lines, $#lines) if $lines[$i] =~ /<link\s+rel=.stylesheet.\s+type=.text\/css./;
    }
    print STDERR "$ATTENT Date $day: no dayly data found for station $station.\n";
    return 0;
}

# get the data file from Limburg website(s): 'first' or 'second'
sub get_a_day_RUD {
    my ($station,$day) = @_;
    $host = $datahosts{$dflt_hst}{url} if not $host;	# default datahost
    $action = $datahosts{$dflt_hst}{action} if not $action;
    my $protocol = 'http://';
    $protocol = $datahosts{$dflt_hst}{protocol}.'://' if defined $datahosts{$dflt_hst}{protocol};
    state $host_warned = 0;
    if( $host_warned++ == 0 ){
        printf STDERR ("Measurements from $host ($locations{$station}{organisation}: $locations{$station}{name} station $station)%s\n", $verbose > 0 ? " for day $day" : "") if not $quiet;
    }
    state $RUA;
    if( not $RUA ){
	my $agnt = ((keys %agents)[int rand keys %agents]);
	$agnt = $agents{$agnt};
        $RUA=LWP::UserAgent->new(agent => $agnt);
        $RUA->timeout(40);
        if( system("pidof privoxy >/dev/null") ){
            $RUA->env_proxy;
        } else {
            $RUA->proxy('http', 'http://127.0.0.1:8118/');
        }
    }

    $day =~ s/\//%2F/g;
    my $qry = $datahosts{$dflt_hst}{content};
    $qry =~ s/%d/$day/; $qry =~ s/%s/$station/;
    $day =~ s/%2F/\-/g;
    my $resp = $RUA->post($protocol.$host.$action,
        Content => $qry,
        );

    if( $resp->is_success ){
	if( $debug ){
    	    open FILE, ">\@meting-location_$location-$day.html";
    	    print FILE $resp->content;
    	    close FILE;
	}
	if( $verbose ){
	    open FILE, ">>Meting-dagen.txt";
	    print FILE "station $location, date $day\n";
	    close FILE;
	}
	$content = $resp->content;
	parse($day,$station);
	print STDERR "Obtained data from $host: $town, station $station, day $day\n" if $verbose;
	return 0;
    }
    else {
	print STDERR "$ERROR no data from http://$host$action :\nstation nr $station for day $day\n";
        if( $dflt_hst =~ /first/ && $datahosts{first}{url} ne $datahosts{second}{url} ){
	    $dflt_hst = 'second';	# try again via later website
            $host = $datahosts{$dflt_hst}{url}; # default datahost
            $action = $datahosts{$dflt_hst}{action};# post action to get data
	    print STDERR "$ATTENT try again via \"second\" newer choice.\n";
	    return get_a_day( $station, $day );
	}
        return 1;
    }
    return 0;
}
########################################### end of prov. Limburg routines

# collect for one day data (24 measurements) from the website
# dispatch the collection function to different specialized download functions
sub get_a_day {
    my ($station,$day) = @_;
    if( not defined  $locations{$station}{table} ){
	print STDERR "$ERROR Cannot find station $station. Use \"Get_data.pl -L all\" for a full list.\n";
	return 1;
    }
    if( $day !~ /^20[012][0-9]\/1?[0-9]\/[1-3]?[0-9]$/ ){
	print STDERR "Date format $ERROR Cannot process station $station on date $day\n";
	return 1;
    }
    my $timing = Time::Piece->strptime("$day 0.1 +0100","%Y/%m/%d %H.%M %z")->epoch;
    if( $first > $timing ){
	print STDERR "$WARNING Date $day has no measurements, skip this date.\nFirst date was $locations{$station}{first}\n" if $verbose;
	return 1;
    }
    if( $last && $last < $timing ){
	print STDERR "$WARNING Date $day has no measurements, skip this date.\nLast date was $locations{$station}{last}\n" if $verbose;
	return 1;
    }
    # do not visit websites to collect data if onlyRRD is true
    # only used to transfer DB table values into RRD database (rebuild RRD DB)
    return Fill_one_day($station,$day) if $onlyRRD > 0;
	
    # visit the website to collect data
    state $rrd_warned = 0;
    # measurements are in wintertime, mysql shows in daylight saving time
    if( strftime("%Y/%m/%d", localtime($timing))  ne strftime("%Y/%m/%d", localtime(time)) ){
        # clearly not to day on every hour possible call
        my $qr = query($mytbl, "SELECT count(datum) FROM $mytbl WHERE date_format(datum,'%Y/%c/%e') = '$day';");
        if( $#{$qr} >= 0 && $qr->[0] > (localtime)[8] ){
	    # found records for that day in the database, expect MSMNTS records per day
	    my $rest = MSMNTS - $qr->[0];
	    if( not $overwrite ){
	        printf STDERR ("$WARNING Day $day: Found already $qr->[0] data records of expected %d records\n", MSMNTS);
	        print STDERR "$ATTENT HINT: Use -O (overwrite) flag to update day $day\n";
	        return 1;
	    }
	    print STDERR "$ATTENT Update existing $qr->[0] records and add $rest records\n" if $verbose;
            if( (not $quiet) && length($rrd) && $verbose ){
	        print STDERR "$ATTENT Expect RRD errors\n" if $rrd_warned++ == 0;
	    }
        }
    }
    if( $locations{$station}{organisation} eq 'RIVM' ){
	return get_a_day_RIVM( $station, $day, ('all',) );
    } elsif( $locations{$station}{organisation} eq 'RUD' ){
	return get_a_day_RUD( $station, $day );
    } elsif( $locations{$station}{organisation} eq 'NRWF' ){
        return get_a_day_NRWF( $station, $day );
    }
    state $loc_warned = 0;
    print STDERR "$ERROR Cannot handle location $station for $day\n" if $loc_warned++ == 0;;
}

# get one day of values from DB and put it into RRD database
sub Fill_one_day {
    my ($station,$day) = @_;
    state $warned = 0;
    my $cnt = 0; my $year=$day;
    if( $station !~ /^[0-9]{2,3}$/ or $day !~ /^20[012][0-9]\/1?[0-9]\/[1-3]?[0-9]$/ ){
        print STDERR "$ERROR Cannot process station $station on date $day\n";
        return 0;
    }
    my $timing = Time::Piece->strptime("$day 0.1 +0100","%Y/%m/%d %H.%M %z")->epoch;
    $year =~ s/\/[0-9].*//;
    if( $first > $timing ){
	print STDERR "$WARNING Date $day has no measurements, skip this date.\nFirst date was $locations{$station}{first}\n" if $verbose;
	return 0;
    }
    if( $last && $last < $timing ){
	state $msg = FALSE;
	print STDERR "$WARNING Date $day has no measurements, skip this date.\n" if $verbose;
	print STDERR "$ATTENT Last date was $locations{$station}{last}\n" if ($verbose && $msg++ == FALSE);
	return 0;
    }
    Check_Col('id', $mytbl); # get all DB colums into %DB_cols
    my @cols = ('datum'); my $qrystrg = 'unix_timestamp(datum)';
    my $fnd = FALSE;
    my $validate =  '';
    for my $key (keys %{$DB_cols{$mytbl}} ){
	$validate .= " OR ${key}" if $key =~ /_valid$/;
        $fnd = TRUE if $key =~ /_valid$/i;
	next if $key =~ /(id|datum|_color|_valid|_ppb)/i;
	next if not $rrd_tables{lc($key)};
	push @cols, lc($key);
	$qrystrg .= ',' . lc($key);
	# TO DO: push only values which are marked valid
	$qrystrg .= ',' . lc($key) . '_valid';	# use valid mark
    }
    $validate =~ s/^ OR /AND \(/; $validate .= ')';
    my $lqry = long_query($mytbl, "SELECT $qrystrg FROM $mytbl WHERE date_format(datum,'%Y/%c/%e') = '$day' $validate ORDER BY datum ;");
    for( my $indx = 0; $indx <= $#{$lqry}; $indx++ ){
	my $timing = $lqry->[$indx][0]; my $rraDS = '';
	my $rraVal0 = ''; my $rraVal1 = '';
	for( $lbl = 1; $lbl <= $#{$lqry->[$indx]}; $lbl += 2 ){
	    next if not defined($lqry->[$indx][$lbl]);
	    next if $lqry->[$indx][$lbl] =~ /^\s*$/;
	    next if not $lqry->[$indx][$lbl+1];	# use valid mark
	    $rraDS .= ':' . $cols[int(($lbl+1)/2)];
	    # $rraDS .= ':' . $cols[$lbl];
	    $rraVal0 .= ':' . $lqry->[$indx][$lbl];
	    $rraVal1 .= ':' . normalize($lqry->[$indx][$lbl],$cols[int(($lbl+1)/2)],$year) if $normalized;
	    $cnt++;
	}
	$rraVal0 =~ s/^://; $rraDS =~ s/^://;
        my $rts = 0;
	$rts = Add_RRA(0, $rraDS, $timing, $rraVal0 ) if $normalized != 1;
        $rts += Add_RRA(1, $rraDS, $timing, $rraVal1 ) if $normalized;
	if( $rts ){
	    print STDERR sprintf("$ERROR processing error for day $day (time: %s) due to errors\nHINT: Clear RRD database first!\n",strftime("%Y/%m/%d %H:%M", localtime($timing))) if $warned++;
	}
	return 0 if $rts; # cannot add previous values
    }
    return $cnt;
}

# search for last day where all sensors provided a value
# warn if sensor values are missing for more as 7 days and =< 30 days.
# give simple info if some sensor is missing for > 30 days
sub Last_day {
    state $msg = FALSE;
    # see if there is a date where we need sensor value from earlier
    $qry = query( $mytbl, "DESCRIBE $mytbl");
    @{$qry} = grep { $_ !~ /(_valid|_color|_ppb|id|datum)$/ } @{$qry} if $#{$qry} >= 0;
    my @lost_sensors = ();
    for( my $i=0; $i >= 0 && $i <= $#{$qry}; $i++ ){
        my $qry_act = query($mytbl,
	    "SELECT IF( (SELECT count(*) FROM $mytbl) = (SELECT count(*) FROM $mytbl WHERE isnull($qry->[$i])), 'not', 'active')");
	my $qry2 = query($mytbl,"SELECT datediff(now(),datum), date_format(datum,'%Y/%c/%e') FROM $mytbl WHERE not isnull($qry->[$i]) ORDER BY datum DESC LIMIT 1");
	if( ($#{$qry2} >= 0 && $qry2->[0] >= MIN_HIST) || ($#{$qry2} < 0) ){ # max one week back
	    if( $qry_act->[0] =~ /active/ ){
	        if( ($#{$qry2} >= 0 && $qry2->[0] > MAX_HIST) && not $verbose ){
		    print STDERR "Not all sensors are operational anymore.\n"
                        if ($msg++ == FALSE && (not $quiet));
	        } else {
	            push @lost_sensors, "$qry->[$i] ($qry2->[0] days)" if $#{$qry2} >= 0;
	        }
	    }
	    splice @{$qry}, $i, 1; $i--;
	}
    }
    printf STDERR ("$ATTENT Sensors not longer operational:\n\t%s\n",
	join ', ', @lost_sensors) if $#lost_sensors >= 0; 

    my $strg = '';
    $strg = join ') AND NOT isnull(', @{$qry} if $#{$qry} >= 0;
    $strg = "WHERE NOT isnull($strg)" if $#{$qry} >= 0;
    # get perv data where all sensors in prev week had a value
    $qry = query( $mytbl, "SELECT unix_timestamp(datum) FROM $mytbl $strg ORDER BY datum DESC LIMIT 1;");
    if( $#{$qry} < 0 || not $qry->[0] || $qry->[0] < 946681200 ){
	# before 2000-01-01 ?
        $qry = query( $mytbl, "SELECT unix_timestamp(datum) FROM $mytbl ORDER BY datum DESC LIMIT 1;");
    }
    # the first not measured data is one hour later
    $qry->[0] += 60*60;
    my $rts = strftime("%Y/%m/%d",
	localtime( ($qry->[0] > (time - 24*60*60)) ?
	  (time - 24*60*60) : $qry->[0]) ); # max is previous day
    $rts =~ s/\/0([1-9])/\/$1/g;
    return $rts;
}

# use html file as data to parse (Limburg dependent)
sub parse_html {
    my $in = shift;
    open(my $IN, $in) or die "FATAL ERROR Cannot find $in $!\n";
    while ( <$IN> ){
        $content .= $_;
    }
    parse("",$location);
}

# standardize the date format
sub std_datum {
    my $st = shift;
    if( $st =~ /^(first|last)$/ ){
        if( defined $locations{$location}{$st} ){
            $st = $locations{$location}{$st};
	} else {
	    $st = '';
	}
    } elsif( $st =~ /^(now|today)$/ ){ $st = '' ; }
    return strftime("%Y/%m/%d", localtime(time)) if not $st;
    if( $st =~ /^([1-3]?[0-9]|0[1-9])\-(1[0-2]|0?[1-9])\-(20[0-2][0-9])$/ ){
        $st = "$3/$2/$1";
    }
    return $st
}

# obtain details for a measurements station by name, id, nr, table from DB
sub fill_location {
    my $type = shift;
    my $string = shift;
    $string = LOCATION if $type =~ /^nr$/ && not defined $string;
    $string = DBTBL if $type =~ /^table$/ && not defined $string;
    if( not defined $string ){
        print STDERR "Cannot search in stations table: undefine search key.\n";
        exit 1
    }
    my @columns; my $loc = -1;
    if( $type !~ /^(nr|name|id|table)$/ ){
        print STDERR "Invalid location search key: $type\n" ;
        return '';
    }
    my $qry = query('stations', "DESCRIBE stations");
    return '' if $#{$qry} < 0;
    for( my $i = 0; $i <= $#{$qry}; $i++ ){
        $columns[$i] =  $qry->[$i];
        $loc = $i if $columns[$i] =~ /^nr$/;
    }
    return '' if $loc < 0;
    $qry = long_query('stations',"SELECT stations." . join(', stations.', @columns) . "
        FROM stations WHERE stations.$type = '$string'");
    return '' if ($#{$qry} < 0) || ($#{$qry->[0]} < 0);
    my $loc_id = $qry->[0][$loc];
    for( my $item = 0; $item <= $#{$qry->[0]}; $item++ ){
        next if $item == $loc;
        $locations{$loc_id} = () if not defined $locations{$loc_id};
        $locations{$loc_id}{$columns[$item]} = $qry->[0][$item];
    }   
    return $loc_id;
}

############################### we start here
# parse command line arguments
my $scan = 0;
Getopt::Mixed::init(
        'H help>H '.
        'd:i debug>d '.
        'i=s input>i '.
        'v verbose>v '.
        'S start>S '.
	'p=s pass>p '.
	'u=s user>u '.
	'h=s host>h '.
	't=s table>t '.
	'D=s database>D '.
	'l=s location>l '.
	'P=s list>P '.
	'U=s URL>U '.
	'A=s action>A '.
	'W=s wdir>W '.
	'r=s rrd>r '.
	'C newDB>C '.
	'c newCor>c '.
	'R newRRD>R '.
	'a addRRD>a '.
	'n normalize>n norm>n '.
	'N nocolor>N '.
        'C color>C '.
	'O overwrite>O '.
	'q quiet>q '.
        'Q aqi>Q '.
        'L lki>L '.
        'I index>I '.
        'J noquality>J '.
	'f first>f ',
	's second>s ',
        ''
);

while( my($option, $value, $arg) = Getopt::Mixed::nextOption() ){
  OPTION: {
    $option eq 'd' and do { $verbose++; $debug++;  last OPTION; };
    $option eq 'v' and do { $verbose++;  last OPTION; };
    $option eq 'q' and do { $quiet = 1;  last OPTION; };
    $option eq 'L' and do { $LKI = 0; last OPTION; }; # switch it off
    $option eq 'Q' and do { $AQI = 2;  last OPTION; };
    $option eq 'I' and do { $AQI = 1;  last OPTION; };
    $option eq 'J' and do { $AQI_qual = 0;  last OPTION; };
    $option eq 'S' and do { $scan = 1;  last OPTION; };
    $option eq 't' and do { $mytbl = $value; $mytbl =~ s/\s//g; last OPTION; };
    $option eq 'h' and do { $myhost = $value; $myhost =~ s/\s//g; last OPTION; };
    $option eq 'D' and do { $mydb = $value; $mydb =~ s/\s//g; last OPTION; };
    $option eq 'u' and do { $myuser = $value; $myuser =~ s/\s//g; last OPTION; };
    $option eq 'p' and do { $mypass = $value; last OPTION; };
    $option eq 'l' and do { $location = $value; $location =~ s/\s//g; undef $mytbl; last OPTION; };
    $option eq 'P' and do { print_location($value); exit(0); last OPTION; };
    $option eq 'A' and do { $action = $value; $action =~ s/\s//g; last OPTION; };
    $option eq 'U' and do { $host = $value; $host =~ s/\s//g; last OPTION; };
    $option eq 'r' and do { $rrd = $value; $rrd =~ s/\s//g; last OPTION; };
    $option eq 'O' and do { $overwrite++; last OPTION; };
    $option eq 'a' and do { $onlyRRD++; last OPTION; };
    $option eq 'n' and do { $normalized++; last OPTION; };
    $option eq 'N' and do { $no_color=1; last OPTION; }; # default
    $option eq 'C' and do { undef $no_color; last OPTION; };
    $option eq 'f' and do { $dflt_hst = 'first'; last OPTION; };
    $option eq 's' and do { $dflt_hst = 'second'; last OPTION; };
    $option eq 'c' and do { $factors = TRUE; last OPTION; };
    $option eq 'R' and do { $Roption = TRUE; last OPTION; };
    $option eq 'C' and do { $Coption = TRUE; last OPTION; };
    $option eq 'W' and do { $WDir = $value; chdir($WDir); last OPTION; };
    $option eq 'i' and do {
	parse_html( $value ); $content = '';
        last OPTION;
        };
    $option eq 'H' and do {
	my $rrd_me = $rrd . '-' . DBTBL;
        print STDERR <<EOF ;
        $0 [options] [arg...] (default/no arguments: catch up to previous day)
        $0 takes the arguments and either scan luchtkwaliteit.nl site
for collecting data and insert the data into the database luchtmetingen/HadM
	argument can be html files obtained from luchtwegen.nl or
	argument is a row of dates (e.g. 2012/12/29, default: previous day)
	or -S start-date end-date for a range of days, per day scanned.
        Default location or table to be used is 06 or HadM (Horst aan de Maas).

        The Air Quality Indices (AQI/LKI/AQHI/CAQI) table maintenance can be
        turned on (deflt off) by using --index option. If so initiate the
        aqi table creation first to fill it with the table values (--aqi option).
        If the AQI index table exits, the AQI index will automatically
        be updated.
        Default the quality message and color will be added.
        This can be switched off (--noquality option).
        Sensor_color column is deprecated:
        the used quality color in the downloaded data will not
        be managed any more unless it the table column sensor_color is existant.
        Delete the sensor_color in the station table manualy e.g. using
        Check_DB.sh TBL=table_name delete _color shell command script.

	Options:
 -L|--LKI       Disable to try to download LKI values as component from (NSL) station.
 --aqi  [[start_time] end_time]
                Create/complete/update the AQI index table for the location.
                end_time (dflt: now) when trying to complete the AQI table.
                This process takes about 25 secs/day (2-3 hours/year) for a table.
                Time format should be date command format compliant.
                If start_time is omitted the first station operational date is used.
 --noquality    Do not store aqi quality messages and color info. Dflt: On.
 -I|--index     Add the updated data also to the air quality index table.
                If needed the air quality Index table will be added and updated
                for the station. Default: No index table creation/update
                if AQI table for station does not exists.
 -l|--location	The measurement location to use, default ($dflt_hst) location 06 (HadM)
 -P|--list	List available details of 'all' or the number of location(s).

 -d|--debug     Debugging on.
 -H|--help      This help or usage message.
 -v|--verbose	Increase verbosity, default: off.
 -q|--quiet	Be as quiet as possible, turns verbose off, default: off.
 -N|--nocolor	Do not use color in error messages to terminal stderr output.
 -C|--color	Do use color in error messages to terminal stderr output.

 -S|--start   	Start days from first date up to second date.
 -i|--input	The html file name for input.

 -u|--user	The DB user for DB access (default: $myuser).
 -p|--pass	The DB user password for DB access (default: X?x?X).

Next website access details can only be changed for Limburg websites
		Default website is $datahosts{$dflt_hst}{url}.
 -f|--first	Use data from first province website (upto August 2014) as default $datahosts{first}{url}.
		Deprecated after 14 Aug 2014.
 -s|--second	Use data from second province website (from May 2014) as default $datahosts{second}{url}.
		Default for Limburg (RUD).
 -h|--host	The DB host for DB access (default: $myhost).
 -A|--action	The ASP action to post for datacollection (default: $datahosts{$dflt_hst}{action}).
 -U|--URL	The host providing the measurements data (default: $datahosts{$dflt_hst}{url}).

 -D|--database	The Database name to use (default: $mydb).
 -t|--table	The Database table name to use
                (default: defined by locations: $mytbl).
		Disable DB storage by making one of the DB defs empty (name with only spaces).
 -W|--wdir	The working directory with eg rrd database in rrd_data directory.
 -r|--rrd	The RRD database file name 
                (default n working dir  ${WDir}/ :${rrd_me}.rrd)
		Disable DB storage by making it empty (name with only spaces).

		Default website to collect data from $dflt_hst:
                $datahosts{$dflt_hst}{url}.

 -O|--overwrite	Overwrite the existing measurements of that day.
		Default: skip data, overwrite is turned on on catch up days.
		If new data is found and data is equal to previous,
		the update of that data is skipped.
 -R|--newRRD	A new RRD database is created.
 -a|--addRRD	All day values taken from date added to RRD database
                ${rrd_me}.rrd.
 -n| --normalize Normalize all RRD data to NEN reference method and add data to
		${rrd_me}_normalized.rrd database. 
		Use params "-n -n" (two times) to add data to both RRD databases.
 -C|--newDB	A new database $mydb with empty table $mytbl will be created.
		Also a new RRD will be created.
		Use this with care and as last argument of the command.
		All old data in the DB will be lost.
 -c|--newCor	Create and initialize table ${mytbl}_norm in database $mydb
		with per year correction factors for local PM measurement values.
		Correction factors will be taken from program locations hash tables.

The program uses an anonymous proxy if one is running, e.g. run privoxy
on 127.0.0.1:8118

$Version
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation.
EOF
        exit(0);
        };
   };
}
Getopt::Mixed::cleanup();
if( -d $WDir ){
   chdir( $WDir) ; 
} else {
   print STDERR "Working dir current dir ./ (so default $WDir)\n";
   $WDir = './';
}
$verbose = 0 if $quiet && $debug == 0;

die "FATAL ERROR: no database user/password defined, e.g. define use environment variable DBUSER and/or DBPASS\n" if length($mypass) <= 0;

################## handle defaults
if( not -f $WDir . LOCATIONS ){
    print STDERR "$WARNING No file ./locations.pl. Will use location details from DB\n"
        if $verbose || $debug;
}
# location number default Horst aan de Maas
if( (not defined $location) && (defined $mytbl) ){
    $location = fill_location('table', $mytbl);
    $mytbl = $locations{$location}{table} if $location;
    if( not $location ){
        $location = LOCATION;
        print STDERR "$ERROR Cannot find location number for table $mytbl. Using default.\n";
    }
}
$location = LOCATION if not $location;
if( $location && (not defined $mytbl) ){
    $location = fill_location('nr', $location);
    # might be overwritten by DB value or LOCATIONS value
    $mytbl = $locations{$location}{table} if $location and (defined $locations{$location}{table});
    if( not defined $mytbl ){
        $mytbl = DBTBL;
        print STDERR "$ERROR Cannot find table name. Using default $mytbl.\n";
    }
}

$rrd .=  '-' . $locations{$location}{table} if $locations{$location}{table} && not length($rrd);

$first = Time::Piece->strptime("$locations{$location}{first} 00.00.01 +0100", "%d-%m-%Y %H.%M.%S %z")->epoch
    if $locations{$location} && (defined $locations{$location}{first}) &&
        ($locations{$location}{first} =~ /\d{1,2}-\d{1,2}-\d{4}/);
$last = Time::Piece->strptime("$locations{$location}{last} 23.59.59 +0100", "%d-%m-%Y %H.%M.%S %z")->epoch
    if $locations{$location} && (defined $locations{$location}{last}) &&
        ($locations{$location}{last} =~ /\d{1,2}-\d{1,2}-\d{4}/);

if( $Coption ){	# create new database, destroys _all_ collected data
	Create_DB();
        system("rm -f ${rrd}-$mytbl*.rrd");
	print STDERR "Create a new MySQL $mydb and RRD database ${rrd}.rrd with empty table $mytbl on host $myhost.
	Deleted existing database(s) and table(s).\n";
	exit 0;
};
if( $Roption ){	# delete RRD data files
        system("rm -f ${rrd}-$mytbl*.rrd");
	print STDERR "Create new RRD databases ${rrd}*.rrd\nDeleted existing RRD database(s).\n";
	New_RRA(0,1);
	exit 0;
}; 

if ( not $AQI ) { # enable AQI updates if AQI table exists for the location
    my $qry = query('',"SHOW TABLES");
    for( my $i = 0; $i <= $#{$qry}; $i++ ){
        next if $qry->[$i] !~ /^$mytbl/;
        $AQI = 1 if $qry->[$i] =~ /_aqi$/;
    }
}
if( $AQI ){
    require('./AirQualityIndex.pl');
    $AQI_Indices = AQI_Index();
}
if( $AQI == 2 ){      # update (and create) AQI table for $mytbl
        my $endtime = time; my $timing = time;
        my $strttime = 0;
        if( (defined $ARGV[1]) && $ARGV[1] ) {
            use IPC::Run 'run';
            run [ "date", "--date=$ARGV[1]", "+%s" ], ">", \my $stdout;
            $endtime = int($stdout) if $stdout =~ /^[0-9]{10}/;
            $strttime = 1;
        }
        if( (defined $ARGV[0]) && $ARGV[0] ){
            use IPC::Run 'run';
            run [ "date", "--date=$ARGV[0]", "+%s" ], ">", \my $stdout;
            if( not $strttime ) {
                $endtime = int($stdout) if ($stdout =~ /^[0-9]{10}/);
            } else {
                $strttime = int($stdout) if ($stdout =~ /^[0-9]{10}/);
            }
        }
        printf STDERR ("Update AQI table for location $location table ${mytbl}_aqi upto %s.\nWill initiate the AQI table if not existant.\n",
            strftime("%Y/%m/%d %H:%M", localtime($endtime)) )
            if not $quiet;
        my $cnt = Fill_AQI_table($mytbl,$first,$strttime,$endtime);
        printf STDERR "Added into the AQI table $cnt records\n"
            if ($verbose? 1 : $cnt)  && (not $quiet);
        $cnt = Adjust_AQI_table($mytbl,$strttime,$endtime);
        printf STDERR "Updated the AQI table with $cnt records\n"
            if ($verbose? 1 : $cnt) && (not $quiet);
        printf STDERR ("\tProcessing time: %d minutes, %d seconds\n",int((time - $timing)/60),(time-$timing)%60)
            if not $quiet;
        exit 0;
}

# provide colored error output
if( (not defined($no_color)) && isatty() ){
    $WARNING = "\033[1;35mWARNING\033[0m:";
    $ERROR = "\033[1;31mERROR\033[0m:";
    $ATTENT = "\033[1;32mATTENTION\033[0m:";
}

# the only function which does not collect data from websites
if( $normalized || $factors ){	# create tables with calibrated values
	# database table corrections factors should exist
	Put_TBL_norm($mytbl) || exit(1);
}
# and die if work was done
die "Created ${mytbl}_norm database table with correction factors\n" if $factors;

############################## start collecting data, parsing the data
############################## and pushing results into database(s)
my $start_time = time;
if( $ARGV[0] ){	###### process day {YYYY/MM/DD|first|last} [end date]
    while( $ARGV[0] ){ next unless length($ARGV[0]);
	# date format should be yyyy/mm/dd (internal format of the website
	# dd-mm-yyyy will be converted to yyyy/mm/dd
	$ARGV[0] = std_datum( $ARGV[0] );
	if( $ARGV[0] !~ /^20[0-2][0-9]\/[01]?[0-9]\/[0-3]?[0-9]$/ ){
	    parse_html( $ARGV[0] );
	} else {
	    if( $scan > 0 ){	# range of days
		$ARGV[1] = std_datum((not $ARGV[1]) ? '' : $ARGV[1]);
	        if( $ARGV[1] =~ /^20[0-2][0-9]\/[01]?[0-9]\/[0-3]?[0-9]$/ ){
		    $ARGV[0] =~ s/\/0([1-9])/\/$1/g;
		    $ARGV[1] =~ s/\/0([1-9])/\/$1/g;
	            get_a_day( $location, $ARGV[0] );    
		    my $timing = Time::Piece->strptime("$ARGV[0] 23.59 +0100","%Y/%m/%d %H.%M %z")->epoch;
		    my $timing2 = Time::Piece->strptime("$ARGV[1] 0.29 +0100","%Y/%m/%d %H.%M %z")->epoch;
		    while( $timing < $timing2 ){
		        $timing = Time::Piece->strptime("$ARGV[0] 23.59 +0100","%Y/%m/%d %H.%M %z")->epoch;
		        $timing +=  6*60;
	                $ARGV[0] = strftime("%Y/%m/%d", localtime($timing));
		        $ARGV[0] =~ s/\/0([1-9])/\/$1/g;
		        last if $timing > $timing2;
		        get_a_day( $location, $ARGV[0] );
		    }
	            last;
	        }
	    }
	    $ARGV[0] =~ s/\/0([1-9])/\/$1/g;
	    get_a_day( $location, $ARGV[0] );    
	}
	shift;
	}
} else {
	# default: from last day with data up to previous day from now
	# we try to catch up from last day in DB up to day now minus one
	my $start_day = Last_day(); $overwrite++;
        get_a_day( $location, $start_day );
	my $timing = Time::Piece->strptime("$start_day 23.59 +0100","%Y/%m/%d %H.%M %z")->epoch;
	my $prev_day = strftime("%Y/%m/%d", localtime(time - 24*60*60));
	$prev_day =~ s/\/0([1-9])/\/$1/g;
	my $timing2 = Time::Piece->strptime("$prev_day 0.29 +0100","%Y/%m/%d %H.%M %z")->epoch;
	while( $timing < $timing2 ){
	    $timing = Time::Piece->strptime("$start_day 23.59 +0100","%Y/%m/%d %H.%M %z")->epoch;
	    $timing +=  6*60;
            $start_day = strftime("%Y/%m/%d", localtime($timing));
	    $start_day =~ s/\/0([1-9])/\/$1/g;
	    last if $timing > $timing2;
	    get_a_day( $location, $start_day );
	}
	$overwrite--;
}

close( $RRDin ) if $RRDchild > 1;

# some statistics from the collected data
if( not $quiet ){
   my $ff = FALSE; my $msg = FALSE;
   printf STDERR ("Scan on date/time: %s, processing time %d secs.\n",
	strftime("%Y/%m/%d %H:%M", localtime($start_time)), time - $start_time);
   for my $tb ( $mytbl, $mytbl . DAY_AVG, $mytbl . MAX_8HRS ){
       print STDERR "Statistics on DB $mydb changes:" if not $ff++;
       printf STDERR ("\n\tchanged $DB_updates{$tb} records to \"$mydb.$tb\"")
	   if $DB_updates{$tb};
       $msg++ if $DB_updates{$tb};
       printf STDERR ("\n\tupdated $DB_updates{$tb} records to \"$mydb.$tb\"")
	   if $DB_updates{$tb};
       $msg++ if $DB_inserts{$tb};
    }
    if( length($rrd) && ($verbose || $DB_updates{$mytbl}) ){
       print STDERR "Statistics on DB $mydb changes:" if not $ff++;
       printf STDERR ("\n\tAdded $RRD_updates[0] records to RRD database.")
	   if $RRD_updates[0];
       $msg++ if $RRD_updates[0];
       printf STDERR ("\n\tEncountered $RRD_errors[0] errors to RRD database.")
	   if $RRD_errors[0];
	$msg++ if  $RRD_errors[0];
       printf STDERR ("\n\tAdded $RRD_updates[1] records to RRD normalized database.")
	   if $RRD_updates[1];
	$msg++ if $RRD_updates[1];
       printf STDERR ("\n\tEncountered $RRD_errors[1] errors to RRD normalized database.")
	   if $RRD_errors[1];
	$msg++ if $RRD_errors[1];
    }
    printf STDERR ("%s.\n\n", ($ff > 0 && $msg == FALSE) ? " none" : "");
}

1;
