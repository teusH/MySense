#!/usr/bin/perl -w
# $Id: forecast.pl,v 1.13 2022/03/26 14:09:30 teus Exp teus $

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

# script will download forecasting info for a location (see %locations) from
#       weather www.yr.no (two days forecast): temp, cloud, pressure, rain
#       pollutant PM2.5 www.aqicn.org (4 days forecast): AQI convert to PM2.5
# generate json for weather and pollutant Index values (LKI/AQI)
# edit the HTML template file to generate website ready HTML script to output file

use JSON;
use Time::Piece;
use POSIX qw(strftime);
use feature "state";

my $debug = 0;   # on debug output full HTML page to output
my $verbose = 0; # verbosity level
my $archive = 0; # archive downloaded forecasts
my $Dflt_template ; #   = './forecast.html';       # default HTML template

# reminder: PM10 -> PM2.5 ~= 814.2 + 0.468*PM10

# TO DO: get location URL parts automatically
my $location_dflt = 'Grubbenvorst';
# weather comes from: https://www.yr.no/storage/lookup/English.csv.zip
my %locations = (
    Grubbenvorst => { # default location
        # YR.no website location part in URL
        weather => 'lat=51.42&lon=6.14583&altitude=23',
        # 2-2755051/Netherlands/Limburg/Gemeente_Horst_aan_de_Maas/Grubbenvorst',
        # AQICN.org website location part in URL
        PM      => 'netherland/horst-a/d-maas/hoogheide/',      # PM25 forecast
        Name    => 'Grubbenvorst, Horst a/d Maas',
    },
    Horst => {
        weather => 'lat=51.45417&lon=6.05139&altitude=27',
        # 2-2753591/Netherlands/Limburg/Gemeente_Horst_aan_de_Maas/Horst',
        PM      => 'netherland/horst-a/d-maas/hoogheide/',
        Name    => 'Horst, Horst a/d Maas',
    },
    'Horst a/d Maas' => {
        weather => 'lat=51.45417&lon=6.05139&altitude=27',
        # 2-2753591/Netherlands/Limburg/Gemeente_Horst_aan_de_Maas/Horst',
        PM      => 'netherland/horst-a/d-maas/hoogheide/',
        Name    => 'Horst a/d Maas',
    },
    Venray => {
        weather => 'lat=51.54083&lon=5.86806&altitude=28',
        # 2-2745204/Netherlands/Limburg/Gemeente_Venray/Vredepeel',
        PM => 'netherland/vredepeel/vredeweg/',
        Name    => 'Venray',
    },
    MaastrichtHF => {
        weather => 'lat=50.84833&lon=5.68889&altitude=56',
        # 2-2751283/Netherlands/Limburg/Gemeente_Maastricht/Maastricht',
        PM => 'netherland/maastricht/hoge-fronten',
        Name    => 'Hoge Fronten, Maastricht',
    },
    Maastricht => {
        weather => 'lat=50.84833&lon=5.68889&altitude=56',
        # 2-2751283/Netherlands/Limburg/Gemeente_Maastricht/Maastricht',
        PM => 'netherland/maastricht/a2-nassaulaan',
        Name    => 'Nassaulaan A2, Maastricht',
    },
    Geleen => {
        weather => 'lat=50.97417&lon=5.82917&altitude=66',
        # 2-2755616/Netherlands/Limburg/Gemeente_Sittard-Geleen/Geleen',
        PM => 'netherland/geleen/asterstraat',
        Name    => 'Asterstraat, Geleen',
    },
    Heerlen => {
        weather =>'lat=50.88365&lon=5.98154&altitude=114',
        # 2-2754652/Netherlands/Limburg/Gemeente_Heerlen/Heerlen',
        PM => 'netherland/heerlen/jamboreepad',
        Name    => 'Jamboreepad, Heerlen',
    },
    HeerlenL => {
        weather => 'lat=50.88365&lon=5.98154&altitude=114',
        # 2-2754652/Netherlands/Limburg/Gemeente_Heerlen/Heerlen',
        PM => 'netherland/heerlen/looierstraat',
        Name    => 'Looierstraat, Heerlen',
    },
    Nettetal => {
        weather => 'lat=51.3335&lon=6.1975&altitude=52',
        PM => 'germany/nrw/nettetal-kaldenkirchen/',
        Name    => 'Kaldenkirche, Nettetal (Dld)',
    },
    Wijnandsrade => {
        weather => 'lat=50.90583&lon=5.88333&altitude=92',
        # 2-2744471/Netherlands/Limburg/Beekdaelen/Wijnandsrade',
        PM => 'netherland/wijnandsrade/opfergelstraat/',
        Name    => 'Opfergelstraat, Wijnandsrade',
    },
    Amsterdam => {
        weather => 'lat=52.37403&lon=4.88969&altitude=13',
        # 2-2759794/Netherlands/North_Holland/Gemeente_Amsterdam/Amsterdam',
        PM => 'netherland/amsterdam',
        Name    => 'Amsterdam',
    },
);
my $weatherUrl = "https://api.met.no/weatherapi/locationforecast/2.0/compact?";

# cached perl format data. This allows to be updated separately
# may stored/obtained as json format filesystem or DB
# cache{weather|pollutant}{data,lastupdate,nextupdate}
# time in UNIX timestamp, data in perl data format (no refs)
# TO DO: sign or decrypt the stored cache data.
my %cache;      # cached perl format data
my $cache_file = '/var/tmp/forecasts/cache-XXXX.json';
sub store_cache {
    my $json = JSON->new->allow_nonref;
    my $cast;
    if( $debug ) {
        $cast = $json->pretty->encode(\%cache); # perl hash table of the foprecast
    } else {
        $cast = $json->encode(\%cache); # perl hash table of the foprecast
    }
    my $FILE;
    if( not open $FILE, ">$cache_file" ) {
        print STDERR "Forecast WARNING: cannot write cache file $cache_file.\n";
        return 0;
    }
    print $FILE $cast; close $FILE;
    print STDERR "Forecast Updated and archived the cache to $cache_file.\n"
        if $verbose > 1;
    return 1;
}

# make sure we keep the cached data
END { store_cache(); }
    
# get ref to perl data structure for this weather or pollutant data
sub get_cache {
    my $type = shift;
    return undef if ($type !~ /^(weather|pollutant)$/);
    return \$cache{$type}{data} if (defined $cache{$type}{data}) && (time <= $cache{$type}{nextupdate});
    # have some data already downloaded?
    my $FILE;
    return undef if not open $FILE, "<$cache_file";
    local $/; # in slurp modus
    my $json = JSON->new->allow_nonref; my $strg = <$FILE>;
    %cache = %{$json->decode($strg)};
    close $FILE;
    return undef if (not defined $cache{$type}{data}) || (time > $cache{$type}{nextupdate});
    return \$cache{$type}{data};
}

# agents to use to masquerate download actions
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

use LWP::UserAgent;
# get content from a website page: argument URL
sub get_file {
    my $file = shift;
    my $URL;
    if( not $URL ){
        $agnt = ((keys %agents)[int rand keys %agents]);
        $agnt = $agents{$agnt};
        $URL=LWP::UserAgent->new(agent => $agnt);
        $URL->timeout('40');
        # use proxy to anonimize downloads and add advertise income to these sites
        if( system("pidof privoxy >/dev/null") ){
            $URL->env_proxy;
        } else {
            $URL->proxy('http', 'http://127.0.0.1:8118/');
        }
    }
    my $resp = $URL->get($file);

    if( $resp->is_success ){
        return $resp->content;
    } else {
        print STDERR "Forecast ERROR Response status line: \n\t";
        print STDERR $resp->status_line,"\n";
        print STDERR "\nForecast ERROR Cannot obtain data from URL $file\n";
    }
    return undef;
}

# convert string with leading integer part to integer
sub integer {
    my $i = shift; my @ar = split /\n/, $i; $i = $ar[0];
    return undef if not defined $i;
    $i =~ s/^[^0-9]*([0-9]+)[^0-9]*$/$1/;
    return $i;
}

# routines to be able to calculate pollutant values and LKI values
require ('/webdata/luchtmetingen/AQI.pl');
my $AQI_Indices = AQI_Index();
# calculate pm2.5 value from AQI binary search
sub Get_PM25_AQI {
    my ($AQI,$min,$max) = @_;
    $min = 0 if not defined $min; $max = 500 if not defined $max;
    my $val = ($max - $min)/2;
    my @aqi = $AQI_Indices->{AQI}{routine}->("noprint pm_25=$val");
    if( $aqi[0]+1.5 > $AQI ){ return Get_PM25_AQI($AQI,$min,$val); }
    elsif( $aqi[0] - 1.5 < $AQI ){ return Get_PM25_AQI($AQI,$val,$max); }
    else { return int($val*10+0.5)/10; }
}
# calculate pm2.5 value from AQI stepwise
sub GET_PM25 {
    my ($AQI,$val,$step) = @_;
    $val = 1 if not defined $val;
    $step = 20 if not defined $step;
    return int($val*10+0.5)/10 if $step < 1;
    for (my @cur = $AQI_Indices->{AQI}{routine}->("noprint pm_25=$val");
        $cur[0] <= $AQI; ){
        $val += $step;
        @cur = $AQI_Indices->{AQI}{routine}->("noprint pm_25=$val");
    }
    $val -= $step;
    return GET_PM25($AQI,$val,$step/2);
}

# test routine
sub Get_PM25_LKI {
    my $AQI = shift;
    my $PM25 = GET_PM25($AQI); # Get_PM25_AQI($AQI);
    my @lki = $AQI_Indices->{LKI}{routine}->("noprint pm_25=$PM25");
    printf("AQI(%d): PM2.5=%2.1f, LKI: %2.1f,'#%6.6X','%s'",
        $AQI, $PM25, $lki[0], $lki[1], $lki[2]);
}
# Get_PM25_LKI(51);

# get forecast pm2.5 AQI values from forecast URL AQICN.org in China
sub get_PM_forecast {
    state %PMforecast; 
    my ($URL, $from, $hours) = @_;
    return $PMforecast{$URL} if defined $PMforecast{$URL};
    $hours = 0 if not defined $hours;
    $from = 0 if not defined $from;
    my $cast;
    my $json = JSON->new->allow_nonref;
    my %rts;

    $cast = get_cache('pollutant');
    if( not defined $cast ) {
        my $data;
        # from World Air Quality Index (WAQI) project (AQICN.org)
        my $forecast = get_file('http://aqicn.org/city/'.$URL);
        return undef if not defined $forecast;

        my @line = split '\n', $forecast;
        # pick up from website the json pollutant forecast data
        for( my $ln = 0; $ln <= $#line; $ln++ ){
            next if $line[$ln] !~  /function showCityWindForecast.idx./;
            $line[$ln] =~ s/.*function showCityWindForecast.idx..\s+var\s+f=//;
            $line[$ln] =~ s/;try\s+.*//;
            $forecast = $line[$ln];           # the json data
            $forecast = $json->decode($forecast); # perl hash table of the foprecast
            last;
        }
        return undef if (not defined $forecast) || ($#{$forecast} < 0);
        if( (not defined $forecast->[0]{d}) || ($#{$forecast->[0]{d}} < 16) ) {
            # [0]{n} is name, [0]{d} is array of hashed entries, one per three hours
            # entries: t(temp),
            # weather info from Citizen Weather Observer Program (CWOP/APRS)
            #          wind: array (3X hash entries):
            #                       at(time), d(rain), h(pressure), ws(speed),
            #                       wg(gauge), wd(direction), rh(huminity), t(temp),
            #          aqi (c(2Xcolor),v(2Xvalue)) 8 days forecast
            # AQI forecast is is based on Copernicus Atmosphere Monitoring Service (CAMS) 
            printf STDERR ("FAILURE: get forecast from AQICN 'http://aqicn.org/city/$URL':\n\tunable to download enough pollutant values (got %d <48 hours of data).\n",
                (defined $forecast->[0]{d})? ($#{$forecast->[0]{d}}+1)*3 : 0);
            return undef;
        }
        $forecast->[0]{n} =~ s/,\s([a-z]\s[a-z]+),\s+(.*)$/, $2\/$1/i; # location
        $cache{'pollutant'}{data} = $forecast; $cast = $cache{'pollutant'}{data};
        $cache{'pollutant'}{lastupdate} = time;
        $cache{'pollutant'}{nextupdate} = time + 23*60*60;
        # the location identifier
        if( $archive > 0 && $debug ){ # save the collected pollutant PM2.5 forecast
            my $FILE;
            my $JSON = JSON->new->allow_nonref;
            my $name = strftime("PM2.5-Forecast-%Y-%m-%d_%Hh%M.json",localtime(time));
            open $FILE, ">./$name";
            print STDERR "Forecast Created pollutant PM2.5 forecast $forecast->[0]{n} file: ./$name\n"
                if $verbose;
            print $FILE $json->pretty->encode($cast);
            close $FILE;
        }
        store_cache();
    } else { $cast = ${$cast}; }
    $rts{location} = $cast->[0]{n};
    my $strt_time = 0; $last_time = 0;
    $rts{pm25} = []; my $skip = 0;
    # synchronize the date/time values with weather data
    # convert the AQI values back to PM2.5 ug/m3 values
    for( my $i=0; $i <= $#{$cast->[0]{d}}; $i++){ # walk through the data array
        next if not $cast->[0]{d}[$i]{t};
        next if not $cast->[0]{d}[$i]{aqi}{v};
        my $time = Time::Piece->strptime("$cast->[0]{d}[$i]{t} +0100","%Y-%m-%d %H:%M:%S %z")->epoch;
        if( not $strt_time ){ # only once at the start
            $strt_time = $time;
            $last_time = $time - 60*60;
            $from = $time if (not $from); # first weather date/time
            printf STDERR ("Forecast Start times: pollutant data from %s, weather data from %s\n",
                strftime("%m/%d %H:%M",localtime($time)),
                strftime("%m/%d %H:%M",localtime($from)) )
              if $verbose;
            # case: weather start > pollutant start date/time: prepend zero values
            printf STDERR ("Forecast WARNING: add %d PM2.5=0 values %s tot %s no pollutant data!\n",
                int(($time - ($from + 30*60))/3600),
                strftime("%Y/%m/%d %H:%M",localtime($from)),
                strftime("%m/%d %H:%M",localtime($time)))
              if $verbose && ($from+30*60 < $time) ;
            for( my $pt = $from + 30*60; $pt < $time; $pt += 60*60){
                # initial sync with weather hourly values
                push @{$rts{pm25}}, 0;
            }
        }
        # case: pollutant array is missing some hours (should not happen).
        if( $time > $last_time + 60*60 ){
            printf STDERR ("Forecast WARNING: between %s tot %s no AQI data!\n", strftime("%Y/%m/%d %H:%M",localtime($last_time)), strftime("%m/%d %H:%M",localtime($time)));
            while( $time > $last_time+60*60 ){ # fill the gaps
                $last_time += 60*60;
                push @{$rts{pm25}}, 0;
            }
        }
        my @aqi = (0,0,0); 
	if ( (defined $cast->[0]{d}[$i]{aqi}{v}) and (ref($cast->[0]{d}[$i]{aqi}{v}) eq "ARRAY") ) {
            $aqi[0] = $cast->[0]{d}[$i]{aqi}{v}[0] if $cast->[0]{d}[$i]{aqi}{v}[0];
            $aqi[2] = $cast->[0]{d}[$i]{aqi}{v}[1] if $cast->[0]{d}[$i]{aqi}{v}[1];
            $aqi[1] = int( ($aqi[0] + $aqi[2])/2 + 0.5)
                if $cast->[0]{d}[$i]{aqi}{v}[0] && $cast->[0]{d}[$i]{aqi}{v}[1];
	}

        for( my $i = 0; $i <= $#aqi; $i++ ){
            # case pollutant starts earlier as weather data: skip the pol data
            if( $time + 30*60 < $from ){
                $skip++;
            } else {
                push @{$rts{pm25}}, GET_PM25($aqi[$i]) if $aqi[$i];
                push @{$rts{pm25}}, 0 if not $aqi[$i];
            }
            $time += 60*60; $last_time += 60*60;
            # limit the array length to array length of weather
            last if ($last_time >= ($from + $hours*60*60)) && not $hours;
        }
        # limit the array length to array length of weather
        last if ($last_time >= ($from + $hours*60*60)) && not $hours;
    }
    printf STDERR ("Forecast Attention:\n\tskip $skip pol data\n\tfrom %s upto %s start weather data,\n\tdeleted %d values from end!\n",
        strftime("%Y/%m/%d %H:%M",localtime($strt_time)),
        strftime("%m/%d %H:%M",localtime($from)),
        $hours < ($#{$rts{pm25}}+1) ? ($#{$rts{pm25}} + 1 -  $hours): 0)
                if ($verbose > 1) && $skip;
    $rts{start} = $strt_time + $skip*60*60;
    my $nr = $#{$rts{pm25}}+1 + $skip;
    $#{$rts{pm25}} = $hours-1 if $hours < ($#{$rts{pm25}}+1); # delete unused values
    $rts{hours} = $#{$rts{pm25}}+1;
    printf STDERR ("Forecast Pollutant PM2.5 values: from %s (%d hours), corrected start: %s (%d hours).\n",
        strftime("%Y/%m/%d %H:%M",localtime($strt_time)),
        $nr,
        strftime("%Y/%m/%d %H:%M",localtime($rts{start})),
        $#{$rts{pm25}}+1) if $verbose > 1;
    printf STDERR ("Forecast Location: %s\n\tstart: %s\n\tnr hours: %d\n\tAQI/hour: %s\n",
        $rts{location},
        strftime("%Y-%m-%d %H:%M:%S",localtime($rts{start})),
        $rts{hours}, join ', ', @{$rts{pm25}})
      if $debug > 1;
    $PMforecast{$URL} = \%rts;
    return $PMforecast{$URL};
}

# get_PM_forecast($U);

# obtain the json data for PM25 forecast for next 4 days (99 hours)
sub json_PM_forecast {
    my $aqicn = shift;
    $aqicn = $locations{$location_dflt}{PM} if not defined $aqicn;
    $aqicn = $locations{$aqicn}{PM} if defined $locations{$aqicn}{PM};
    my $aqi_type = shift; $aqi_type = 'LKI' if not defined $aqi_type;
    my $from = shift;
    my $hours = shift; $hours = 0 if not defined $hours;
    my $json = JSON->new->allow_nonref;

    my $pm25 = get_PM_forecast($aqicn, $from, $hours);
    return undef if not defined $pm25;
    return $pm25 if (defined $pm25->{$aqi_type}{pm25});
    $pm25->{$aqi_type}{pm25} = [];
    $pm25->{$aqi_type}{colors} = [];
    $pm25->{$aqi_type}{qual} = [];

    # convert PM2.5 to LKI/AQI Index values
    for( my $i = 0; $i <= $#{$pm25->{pm25}}; $i++ ){
        if( (not defined $pm25->{pm25}[$i]) || (not $pm25->{pm25}[$i]) ){
            # $pm25->{$aqi_type}{pm25}[$i] = 0;
            # $pm25->{$aqi_type}{colors}[$i] = '#0f0f0f';
            # $pm25->{$aqi_type}{qual}[$i] = '?';
            $pm25->{$aqi_type}{pm25}[$i] = undef;
            $pm25->{$aqi_type}{colors}[$i] = undef;
            $pm25->{$aqi_type}{qual}[$i] = undef;
            next;
        }
        my @aqi = $AQI_Indices->{$aqi_type}{routine}->("noprint pm_25=$pm25->{pm25}[$i]");
        $pm25->{$aqi_type}{pm25}[$i] = int($aqi[0]*10+0.5)/10;
        $pm25->{$aqi_type}{colors}[$i] = sprintf("#%0.6X",$aqi[1]);
        $pm25->{$aqi_type}{qual}[$i] = $aqi[2];
    }
    printf STDERR ("Forecast Pollutant %s(pm2.5) starts at %s (%d), has %d hourly values.\n",
        $aqi_type,
        strftime("%Y-%m-%d %H:%M:%S",localtime($pm25->{start})),
        $pm25->{start},
        $#{$pm25->{pm25}}+1)
      if $verbose > 1;
    $pm25->{start} = "$pm25->{start}";
    $pm25->{$aqi_type}{pm25} = $json->encode($pm25->{$aqi_type}{pm25});
    printf("var %s_pm25 = %s;\n", $aqi_type, $pm25->{pm25})
        if $debug > 1;
    $pm25->{$aqi_type}{colors} = $json->encode($pm25->{$aqi_type}{colors});
    printf("var %s_pm25_colors = %s;\n", $aqi_type, $pm25->{$aqi_type}{colors})
        if $debug > 1;
    $pm25->{$aqi_type}{qual} = $json->encode($pm25->{$aqi_type}{qual});
    printf("var %s_pm25_qual = %s;\n", $aqi_type, $pm25->{$aqi_type}{qual})
        if $debug > 1;
    return $pm25;
}

# search a struct for a hash key (not an HASH or ARRAY) and return the address
# return a REF to the searched key
sub WalkTree {
    my $table = shift;
    my $search = shift;
    my @array;
    return @array if (not defined $search) || (not defined $table);
    $table = ${$table} if scalar $table =~ /^REF/;
    if( scalar $table =~ /^HASH/ ) {
        foreach my $key (keys %{$table} ){
            if( $key eq $search  ){
        #&& ((scalar $table->{$key}) !~ /^(ARRAY|HASH|REF)/) ){
#    print STDERR "Forecast *** FOUND key $key ***********\n";
                push @array, \$table->{$key};
            } elsif( scalar $table->{$key} =~ /^(HASH|ARRAY|REF)/ ){
#    print STDERR "Forecast walk hash table on key $key searching for $search\n";
                my @new = WalkTree(\$table->{$key}, $search);
                push @array, @new if $#new >= 0;
            }
            else {
#    print STDERR "Forecast leaf node key $key searching for $search\n";
            }
        }
    } elsif( scalar $table =~ /^ARRAY/ )  {
#    printf STDERR ("Forecast walk into array length %d for search $search\n", $#{$table});
        for( my $i = 0; $i <= $#{$table}; $i++ ) {
            if( scalar ${$table}[$i] =~ /^(HASH|ARRAY|REF)/ ) {
                my @new = WalkTree(\${$table}[$i], $search);
                push @array, @new if $#new >= 0;
#    printf STDERR "Forecast * FOUND at array nr $i\n" if $#new >= 0;
            }
        }
    }
    return @array;
}

# Norway weather forecast: 
# terms of service: https://api.met.no/doc/TermsOfService
# User Agent requirement:
#Identification
#All requests must (if possible) include an identifying User Agent-string (UA) in the request
#with the application/domain name, optionally version number.
#You should also include a company email address or a link to the company website
#where we can find contact information.
#If we cannot contact you in case of problems, you risk being blocked without warning.
#
#Examples of valid User-Agents:
#"acmeweathersite.com support@acmeweathersite.com"
#"AcmeWeatherApp/0.9 github.com/acmeweatherapp"

# https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=59.93484&lon=10.72084&altitude=59
# curl -A "MySense mysense@behouddeparel.nl" -s 'https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=51.42&lon=6.1458&altitude=23'
# or more complete:
# https://api.met.no/weatherapi/locationforecast/2.0/complete?lat=59.9348&lon=10.7208&altitude=59
# meteo symbols: https://api.met.no/weatherapi/weathericon/2.0/documentation
# define User-Agent: 
# previous xml:
#<time from="2020-05-12T11:00:00" to="2020-05-12T12:00:00">
#	<!-- Valid from 2020-05-12T11:00:00 to 2020-05-12T12:00:00 -->
#	<symbol number="4" numberEx="4" name="Cloudy" var="04"/>
#	<precipitation value="0"/>
#	<!--  Valid at 2020-05-12T11:00:00  -->
#	<windDirection deg="330.5" code="NNW" name="North-northwest"/>
#	<windSpeed mps="4.2" name="Gentle breeze"/>
#	<temperature unit="celsius" value="8"/>
#	<pressure unit="hPa" value="1003.1"/>
#</time>
# new json:
#{
#    "time": "2020-05-12T08:00:00Z",
#    "data": {
#        "instant": {
#            "details": {
#                "air_pressure_at_sea_level": 1003.1,
#                "air_temperature": 6,
#                "cloud_area_fraction": 94.6,
#                "relative_humidity": 36.3,
#                "wind_from_direction": 320.7,
#                "wind_speed": 3.9
#            }
#        },
#        "next_12_hours": {
#            "summary": {
#                "symbol_code": "cloudy"
#            }
#        },
#        "next_1_hours": {
#            "summary": {
#                "symbol_code": "cloudy"
#            },
#            "details": {
#                "precipitation_amount": 0
#           }
#        },
#        "next_6_hours": {
#            "summary": {
#                "symbol_code": "cloudy"
#            },
#            "details": {
#                "precipitation_amount": 0
#            }
#        }
#    }
#}

use XML::Simple;        # from package libxml-simple-perl
sub Get_weather_forecast { # get weather forecast data usually next day 48 hours
    state %Wcast;
    #print STDERR "Weather forecast Norway is end of life. No forecast\n";
    #print STDERR "https://developer.yr.no/doc/guides/getting-started-from-forecast-xml";
    #print STDERR "end of life since Febr 2022";
    #return undef;
    my $location = shift; my %weather; my $data; my @arr;
    my $json = JSON->new->allow_nonref; my $coordinates;
    $coordinates = $locations{$location_dflt}{weather} if not defined $location;
    $coordinates = $locations{$location}{weather} if defined $locations{$location}{weather};
    return $Wcast{$location} if defined $Wcast{$location};

    $data = get_cache('weather');
    if( not defined $data ){
        # meteo forecast via Norway weather service
        # Norwegian Meteorological Institute and the NRK
        my  $UserAgent = 'MySense mysense@behouddeparel.nl';
        my $url = "$weatherUrl$coordinates";

        # next did not work as json content should have @attribute elements
        # TO DO change the js script to use the json without @attributes
        # my $xml = get_file($url);
        # if( not defined $xml ){
        #     print STDERR "Forecast FAILURE: Cannot obtain weather forecast via $url\n";
        #     return undef;
        # }
        # 
        # # Create the object of XML Simple and convert xml to perl format
        # my $xmlSimple = new XML::Simple(KeepRoot   => 1);
        # $data = $xmlSimple->XMLin($xml);
        
        # we use php script to download the xml data, convert it to json
        # convert json to perl struct so it has @attribute keys
        # we have to get the forecast data with timestamps of generation timeing
        my $IN; open $IN, "/usr/bin/curl -A '$UserAgent' -s '$url' 2>/dev/null |";
        #my $IN; open $IN, "/usr/bin/php -r '
        #        \$xml = file_get_contents(\"$url\");
        #        \$xml = simplexml_load_string(\$xml);
        #        \$json = json_encode(\$xml);
        #        echo \"\$json\";
        #        ' 2>/dev/null |";
        if( (not defined $IN) || $? ) {
            print STDERR "Forecast FAILURE: Cannot obtain weather json forecast via $url\n";
            return undef;
        }
        local $/; 
        $data = <$IN>; close $IN;
        if( length($data) < 50 ) {
            print STDERR "Forecast FAILURE: Cannot obtain weather json forecast via $url. Connection erorr.\n";
            return undef;
        }
        $data = $json->decode($data);
        if( ($archive > 0) && $debug ){
            my $FILE;
            my $name = strftime("Weather-Forecast-%Y-%m-%d_%Hh%M.json",localtime(time));
            open $FILE, ">./$name";
            print STDERR "Forecast Created weather forecast $location ($coordinates) file: ./$name\n"
                if $verbose;
            print $FILE $json->pretty->encode($data);
            close $FILE;
        }
        
        @arr = WalkTree(\$data,'meta');
        if( $#arr >= 0 ){
            $cache{weather}{lastupdate} = Time::Piece->strptime(${$arr[0]}->{updated_at},"%Y-%m-%dT%H:%M:%SZ")->epoch;
            print STDERR "Forecast Weather: last updated at ${$arr[0]}->{updated_at}\n" if $debug;
        } else {
            $cache{weather}{lastupdate} = time;
        }
        $cache{weather}{nextupdate} = $cache{weather}{lastupdate} + 90*60;
        $cache{weather}{data} = $data;
        $data = \$cache{weather}{data};
    }
        
    store_cache();
    
    $weather{forecast} = $json->encode(${$data});
    @arr = WalkTree(${$data},'time');
    if( ($#arr < 0 ) || (not defined $arr[0]) ) {
        print STDERR "Forecast FAILURE: Weather json file has no array with timed data!.\n";
        return undef;
    }
    my $first = 2*time;
    for( my $i = 0; $i < $#arr; $i++ ) { # search for starting timestamp
        my $hr = Time::Piece->strptime(${$arr[$i]},"%Y-%m-%dT%H:%M:%SZ")->epoch;
        if( $first > $hr ) {
            $weather{start} = ${$arr[$i]}; $first = $hr;
        }
    }
    # $weather{start} = ${$arr[0]}->[0]{from}; # we think array is ordered by date
    $weather{hours} = $#arr+1;   # $#{$arr} + 1;
    printf STDERR ("Forecast Found weather first time: %s, with %d hourly values.\n",
        $weather{start}, $weather{hours}) if $verbose > 1;
    $weather{start} = sprintf("%d",Time::Piece->strptime($weather{start},"%Y-%m-%dT%H:%M:%SZ")->epoch);
    if( $verbose ){
        # $weather{start} .= sprintf("\n// Weather info start %s, %s hours\n",
        #         strftime("%Y-%m-%d %H:%M",localtime(integer($weather{start}))),
        #         $weather{hours} < 0 ? '?' : $weather{hours}); 
        printf STDERR ("Forecast var weather = %s\n",$weather{forecast}) if $debug > 1;
    }
    $Wcast{$location} = \%weather;
    return \%weather;
}
# Get_weather_forecast('Grubbenvorst');

# generate from template file with Highcharts definitions the html chart
# arguments:    aqi type (optional dflt LKI),
#               output file (dflt stdout) optional,
#               location identifier, see %locations optional dflt $location_dflt
#               div identifier,  optional default FORECASTING
#               input chart template file (optional,
#                       if not defined DATA script part
sub Generate {
    # default AQI type (LKI|AQI), template file can define AQI type as well!
    my $aqi_type = shift; $aqi_type = 'LKI' if not defined $aqi_type;
    $aqi_type = 'LKI' if $aqi_type =~ /(both|all)/; # all is not yet supported
    # JS script output, with debug on HTML will be included
    my $output = shift; $output = '/dev/stdout' if not defined $output;
    if ( $output !~ /^\/dev/ ) {
        $output =~ s/\.html//i;
        $output .= '.html' if $debug;
    }
    # default location as defined in $locations for URL download access
    my $location = shift; $location = $location_dflt if not defined $location;
    my $identifier = shift; $identifier = 'FORECASTING' if not defined $identifier;
    # HTML JS script template file
    my $template = shift; $template = $Dflt_template
        if (not defined $template) && (defined $Dflt_template);

    if ( not defined $locations{$location} ){
        print STDERR "Forecast ERROR: $location location URL info details are not defined!";
        return 0;
    }
    $cache_file =~ s/X+/$location/;      # per location a cache file
    if( $cache_file =~ /^(.*)\/[^\/]+/ ) {
        my $dir = $1; mkdir($dir,0770) if not -d $dir;
    }
    
    if ( (defined $template) && (not -r $template) ) {
        printf STDERR "Forecast ERROR: file $template does not exist or is nor readable.\n";
        return 0;
    }
    my $IN; my $OUT; my $GLOB; my $DOM; my $DBG; my $RSLT= 'ERRORS encountered';
    if ( (defined $template) && $template ) {
        open $IN, "<$template" || die ("Cannot open template file $template\n");
    }
    if( $debug ) {
        open $DBG, ">$output" || die ("Cannot open $output for generated HTML code\n");
        $RSLT="HTML page ready output on $output.\n";
        $OUT = $DBG; $GLOB = $DBG; $DOM = $DBG;
    } else {
        $output .= '.GLOB.json' if $output !~ /^\/dev\//;
        open $GLOB, ">$output" || die ("Cannot open ${output} for generated HTML code\n");
        $RSLT="File=$output with GLOBAL JS script.\n";
        $output =~ s/GLOB.json$/DOM.json/ if $output !~ /^\/dev\//;
        open $DOM, ">$output" || die ("Cannot open ${output} for generated HTML code\n");
        $RSLT .= "File=$output with DOM function JS script.\n";
        open $DBG, ">/dev/null" || die ("Cannot open /dev/null for generated HTML garbage\n");
        $OUT = $DBG;
    }
    # download weather info and convert it to json ready for Hightcharts JS scripts
    my $weather = Get_weather_forecast($location);
    if( not defined $weather ){
        print STDERR "Forecast ERROR: failed to obtain weather forecasts for $location\n";
        return 0
    }
    # use the downloaded data to generate HTML/JS script code from the template file
    my $inscript = 0; my $skip = '';
    my $PM25 = json_PM_forecast($location,$aqi_type,$weather->{start},$weather->{hours});
    if( (not defined $PM25) || (not defined $PM25->{$aqi_type}) ){
        print STDERR "Forecast ERROR: failed to obtain particular matter forecast for $aqi_type values, location $location\n";
        return 0;
    }
    my $inheader = 0; my $line_cnt = 0;
    while( 1 ){            # parse template file
        if ( $IN ) { $_ = <$IN> ; }
        else { $_ = <main::DATA> }
        last if not $_; $line_cnt++;
        print STDERR $_ if $debug > 2;
        if( /<head>/ ){ $inheader = 1; }
        if( /<\/head>/ ){ $inheader = 0; }
        if( (/<script\s/) && (not $inheader) ){ $inscript = 1; };
        if( /<\/script>/ ){ $inscript = 0; };
        next if (not $inscript) && (not $debug);
        # output switcher: debug, dom ready function part and script global part
        if( /^\/\/\s+FORECAST\s+start\s+(DOM|GLOB)/ ) {
            my $sw = $1;
            $OUT = $DOM if $sw =~ /DOM/;
            $OUT = $GLOB if $sw =~ /GLOB/;
        } elsif ( /^\/\/\s+FORECAST\s+end/ ) {
            print $OUT $_;
            $OUT = $DBG;
            next;
        } 
        if( /^\/\/\s+START\s+([a-zA-Z0-9]*).*/ ){ # insert new values
            $type = $1;
            print $OUT $_ if $debug; my $do_skip = 1;
            
            if( $type =~ /^(start)/ ){
                printf $OUT ("%se3;\n",$PM25->{start});
            } elsif( $type =~ /^LastUpdate/i ) {
                my $update = '';
                $update = $cache{'pollutant'}{lastupdate} if defined $cache{'pollutant'}{lastupdate};
                $update = $cache{'weather'}{lastupdate}
                    if (defined $cache{'weather'}{lastupdate}) && $update
                        && ($update < $cache{'weather'}{lastupdate});
                $update = strftime(" <div style=\"font-size:80%%\">(bijgewerkt op %a %d %b %k:%M)</dev>",localtime($update))
                    if $update;
                printf $OUT ("'%s';",$update);
            } elsif( $type =~ /^(LocationName)/i ) {
                printf $OUT ("'%s';",$locations{$location}{Name});
            } elsif( $type =~ /^(URL)/i ) {
                printf $OUT ("'%s';",$weatherUrl + $locations{$location}{weather});
            } elsif( $type =~ /^(pm25|colors|qual[a-z]*)\s*(LKI|AQI)?/ ){
                # insert PM aqi/color/qualifier info as json
                my $elmnt = $1; my $aqi = $2;
                if( not $aqi ){ $aqi = $aqi_type; }
                if( not defined $PM25->{$aqi} ){
                    $PM25 = json_PM_forecast($locations{$location}{PM},$aqi,$weather->{start},$weather->{hours});
                    if( not defined $PM25->{$aqi}{$elmnt} ){
                        print STDERR "Forecast ERROR: failed to obtain particular matter forecast for $aqi ($elmnt) values, location $location\n";
                    }
                }
                printf $OUT ("%s;\n",$PM25->{$aqi}{$elmnt}) if defined $PM25->{$aqi};
            } elsif( $type =~ /^(weather|forecast)/ ){
                # insert weather forecast info as json
                my $elmnt = $1; $elmnt =~ s/weather/forecast/;
                printf $OUT ("%s;\n", $weather->{$elmnt});
            } elsif( $type =~ /aqi/ ){ # insert aqi Index type: LKI or AQI
                printf $OUT ("['%s',];\n", $aqi_type) if $aqi_type !~ /all/;
                printf $OUT ("['LKI','AQI'];\n", $aqi_type) if $aqi_type =~ /all/;
            } else { $do_skip = 0; }
            if( $do_skip ){
              while(1){
                if ( $IN ) { $_ = <$IN> ; }
                else { $_ = <main::DATA> }
                last if not $_;
                print STDERR $_ if $debug > 2;
                if( /^\/\/\s+END/ ){
                    $type = '';
                    last;
                }
              }
            }
        }
        if ( /FORECASTING/ ) {     # div identifier
            s/id="FORECASTING"/id='${identifier}_${aqi_type}'/ if $aqi_type !~ /all/;
            s/FORECASTING/$identifier/g;
        }
        s/\/\/\s.*// if not $debug;
        next if /^\s*$/;
        print $OUT $_;
    }
    close $IN if $IN;
    print STDERR $RSLT if $verbose > 1;
    if( $line_cnt < 1 ) {
       print STDERR "Empty forecast file, location $location\n"; return 0;
    }
    return 1;
}
    
sub Usage {
    print "
Command:
forecast.pl [options] aqi_type output_file location [identifier] [template_file]
options: [-h|-d|-q|-v|-a|-w dir]

Generates from template file with Highcharts definitions
The forecast data is downloaded from yr.no (weather) and aqicn.org (PM2.5).
the html chart can be identified by the identifier (<div id='FORECASTING_AqiType'>...</div>).

Arguments:    aqi type          LKI or AQI or all (dflt LKI),
                                Type 'all' is not yet supported (degradated to LKI).
              output file name  (dflt stdout) (at debug HTML else JS script),
                                In debug mode extent name with .html
                                Otherwise 2 file are created:
                                with .DOM.json extension as DOM ready part
                                and .GLOB.json extension as global definitions part.
              location identifier, see %locations (dflt $location_dflt),
              div identifier (dflt FORECASTING extended with _aqi_type)
                                div identifier will be extended with '_aqi_type' .
              template input    HTML chart template file (dflt from DATA
                                embedded in the perl script),
Options:      --help|-h usage/help message
              --debug|-d increase debug level (level 1: output full HTML file)
                (debug: output is full HTML page on stdout).
              --quiet|-q quiet
              --verbose|-v increase verbose level (dflt 1)
                (level 2 output json arrays)
              --archive|-a archive downloaded json data in current directory
              --working|-w 'dir'  working directory,
                dir with all data files (dflt './')

CLI test example: forecast.pl -d -v LKI output.html Nettetal
    generates output.html file to be loaded in browser as local file.
CLI example: forecast -v LKI output Nettetal
    generates 2 files: output.DOM.json and output.DOM.json to be combined in a html file.
Installation:
    Make sure to install ./forecast.html template file in working dir.
    Add the chart lib files to force page load with these chart lib files.
    Chart needs the following files
    (install them in Drupal .../sites/all/libraries/highcharts/
        https://ajax.googleapis.com/ajax/libs/jquery/1.12.4/jquery.min.js
        https://code.highcharts.com/highcharts.js
        https://code.highcharts.com/modules/windbarb.js
        https://code.highcharts.com/modules/pattern-fill.js
        https://code.highcharts.com/modules/data.js
        https://code.highcharts.com/modules/exporting.js
        https://code.highcharts.com/modules/accessibility.js
        In header as link:
        https://netdna.bootstrapcdn.com/font-awesome/4.0.3/css/font-awesome.css
";
    exit 0;
}

while ( (defined $ARGV[0]) && ($ARGV[0] =~ /^-/) ){
    if( $ARGV[0] =~ /^--?h/ ){ Usage(); }
    if( $ARGV[0] =~ /^--?d/ ){ $debug++ ; }
    if( $ARGV[0] =~ /^--?v/ ){ $verbose++; }
    if( $ARGV[0] =~ /^--?q/ ){ $verbose = 0; }
    if( $ARGV[0] =~ /^--?a/ ){ $archive++; }
    if( $ARGV[0] =~ /^--?w/ ){ 
        if( -d $ARGV[1] ){ chdir $ARGV[1]; shift ; shift; next }
        else { print "ERROR: $ARGV[1] dir not found!\n"; exit 1; }
    }
    shift
}
$verbose += $debug;
$archive += $debug;
if( Generate(@ARGV) ){ exit 0; }
exit 1;

__DATA__
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html>
<head>
<script src='https://ajax.googleapis.com/ajax/libs/jquery/1.12.4/jquery.min.js'></script>
<script src="https://code.highcharts.com/highcharts.js"></script>
<script src="https://code.highcharts.com/modules/windbarb.js"></script>
<script src="https://code.highcharts.com/modules/exporting.js"></script>

<!--
<link href="https://netdna.bootstrapcdn.com/font-awesome/4.0.3/css/font-awesome.css" rel="stylesheet">
-->
</head>
<body>
<script type="text/javascript">
        Highcharts.setOptions({
            lang: {
                months: ['januari','februari','maart','april','mei','juni','juli','augustus','september','october','november','december'],
                shortMonths: ['jan','feb','mrt','apr','mei','jun','jul','aug','sep','oct','nov','dec'],
                weekdays: ['zondag','maandag','dinsdag','woensdag','donderdag','vrijdag','zaterdag'],
                shortWeekdays: ['zo','ma','di','wo','do','vr','za'],
                rangeSelectorTo: 'tot',
                rangeSelectorFrom: 'van',
             }
        });

// FORECAST start GLOB
var LastUpdate =
// START LastUpdate
' <div style="font-size:80%">(bijgewerkt op ma 14 mrt 13:34)</dev>';
// END LastUpdate
var LocationName =
// START LocationName
'Hoogheide, Horst ad Maas';
// END LocationName
var fijnstofStart =
// START start
0; // start PM values per 3 hours
// END start
var fijnstofAQI =
// START pm25
[0.7,0.9,1,0.7,0.7,0.9,1,1.2,2,2.2,2.5,2.7,3,3.1,3.2,3,3.1,3.2,2.7,2.7,2.7,2.2,2.5,2.7,1,1.5,2,1,1.2,1.5,2,3,3.5,3.7,3.7,3.7,2.7,3.1,3.4,1.7,2,2.2,1,1.2,1.5,0.9,0.9,1,1,1,1,1,1,1,1.2,1.5,2,1.7,2,2];
// END pm25
var AQItops = [];
for( var i = 1; i < fijnstofAQI.length-1; i++ ) {
    if( (fijnstofAQI[i-1] < fijnstofAQI[i]) && (fijnstofAQI[i] >= fijnstofAQI[i+1]) )
       AQItops.push(i);
}
var fijnstofColors =
// START colors
["#002BF7","#002BF7","#006DF8","#002BF7","#002BF7","#002BF7","#006DF8","#006DF8","#2DCDFB","#2DCDFB","#C4ECFD","#C4ECFD","#FFFED0","#FFFED0","#FFFED0","#FFFED0","#FFFED0","#FFFED0","#C4ECFD","#C4ECFD","#C4ECFD","#2DCDFB","#C4ECFD","#C4ECFD","#006DF8","#009CF9","#2DCDFB","#006DF8","#006DF8","#009CF9","#2DCDFB","#FFFED0","#FFFED0","#FFFDA4","#FFFDA4","#FFFDA4","#C4ECFD","#FFFED0","#FFFED0","#009CF9","#2DCDFB","#2DCDFB","#006DF8","#006DF8","#009CF9","#002BF7","#002BF7","#006DF8","#006DF8","#006DF8","#006DF8","#006DF8","#006DF8","#006DF8","#006DF8","#009CF9","#2DCDFB","#009CF9","#2DCDFB","#2DCDFB"];
// END colors
var fijnstofQualifications =
// START qual
["goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","matig","matig","matig","matig","matig","matig","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","matig","matig","matig","matig","matig","goed","matig","matig","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed","goed"];
// END qual
var AQIlevels = {LKI:3,AQI:50};
var AQItype =
// START aqi
['LKI',];
// END aqi
// add name to air quality index
function AQIname( aqi ) {
   if( aqi < ( AQItype[0] === 'AQI' ? 50 : 3 ) ) return 'goed';
   if( aqi < ( AQItype[0] === 'AQI' ? 100 : 7 ) ) return 'matig';
   if( aqi < ( AQItype[0] === 'AQI' ? 200 : 9 ) ) return 'opgepast';
   if( aqi < ( AQItype[0] === 'AQI' ? 300 : 10 ) ) return 'ongezond';
   return '(gevaarlijk)';
}
var weather =
// START weather
{};
// END weather

/* translate wind speed labels to Dutch
 * beaufortName: ['Calm','Light air','Light breeze','Gentle breeze','Moderate breeze',
 *                'Fresh breeze','Strong breeze','Near gale','Gale','Strong gale',
 *                'Storm','Violent storm','Hurricane'],
 */
Highcharts.seriesTypes.windbarb.prototype.beaufortName = [
                'windstil','flauwe wind','zwakke wind','vrij matige wind','matige wind',
                'vrij krachtige wind','krachtige wind','harde wind','stormachtig','storm',
                'zware storm','zeer zware storm','orkaan'];

/**
 * Get the title based on the json data
 */
Meteogram.prototype.getTitle = function () {
    return 'weersverwachting en verwachting lucht kwaliteit '+AQItype[0]+' index (PM<span style="font-size:70%">2.5</span>)';
};

/**
 * This is a complex demo of how to set up a Highcharts chart, coupled to a
 * dynamic source and extended by drawing image sprites, wind arrow paths
 * and a second grid on top of the chart. The purpose of the demo is to inpire
 * developers to go beyond the basic chart types and show how the library can
 * be extended programmatically. This is what the demo does:
 *
 * - Loads weather forecast from www.yr.no in form of a JSON service.
 * - When the data arrives async, a Meteogram instance is created. We have
 *   created the Meteogram prototype to provide an organized structure of the
 *   different methods and subroutines associated with the demo.
 * - The parseYrData method parses the data from www.yr.no into several parallel
 *   arrays. These arrays are used directly as the data option for temperature,
 *   precipitation and air pressure.
 * - After this, the options structure is built, and the chart generated with
 *   the parsed data.
 * - On chart load, weather icons and the frames for the wind arrows are
 *   rendered using custom logic.
 */

function Meteogram(json, container) {
    // Parallel arrays for the chart data, these are populated as the JSON file
    // is loaded
    this.symbols = [];
    this.precipitations = [];
    this.precipitationsError = []; // Only for some data sets
    this.winds = [];
    this.temperatures = [];
    this.pressures = [];
    this.aqi = [];

    // Initialize
    this.json = json;
    this.container = container;

    // Run
    this.parseYrData();
}

/**
 * Mapping of the symbol code in yr.no's API to the icons in their public
 * GitHub repo, as well as the text used in the tooltip.
 *
 * https://api.met.no/weatherapi/weathericon/2.0/documentation
 */
Meteogram.dictionary = {
    clearsky: {
        symbol: '01',
        text: 'heldere hemel'
    },
    fair: {
        symbol: '02',
        text: 'Fair'
    },
    partlycloudy: {
        symbol: '03',
        text: 'gedeeltelijk bewolkt'
    },
    cloudy: {
        symbol: '04',
        text: 'bewolkt'
    },
    lightrainshowers: {
        symbol: '40',
        text: 'lichte regenbuien'
    },
    rainshowers: {
        symbol: '05',
        text: 'regen buien'
    },
    heavyrainshowers: {
        symbol: '41',
        text: 'hevige regen buien'
    },
    lightrainshowersandthunder: {
        symbol: '24',
        text: 'lichte regenbuien en onweer'
    },
    rainshowersandthunder: {
        symbol: '06',
        text: 'regenbuien en onweer'
    },
    heavyrainshowersandthunder: {
        symbol: '25',
        text: 'hevige regenbuien en onweer'
    },
    lightsleetshowers: {
        symbol: '42',
        text: 'lichte ijzel'
    },
    sleetshowers: {
        symbol: '07',
        text: 'ijzel'
    },
    heavysleetshowers: {
        symbol: '43',
        text: 'hevige ijzel'
    },
    lightsleetshowersandthunder: {
        symbol: '26',
        text: 'lichte ijzel en onweer'
    },
    sleetshowersandthunder: {
        symbol: '20',
        text: 'ijzel en onweer'
    },
    heavysleetshowersandthunder: {
        symbol: '27',
        text: 'hevige ijzel en onweer'
    },
    lightsnowshowers: {
        symbol: '44',
        text: 'lichte sneeuwbuien'
    },
    snowshowers: {
        symbol: '08',
        text: 'sneeuw buien'
    },
    heavysnowshowers: {
        symbol: '45',
        text: 'hevige sneeuwbuien'
    },
    lightsnowshowersandthunder: {
        symbol: '28',
        text: 'lichte sneeuwbuien en onweer'
    },
    snowshowersandthunder: {
        symbol: '21',
        text: 'sneeuwbuien en onweer'
    },
    heavysnowshowersandthunder: {
        symbol: '29',
        text: 'zware sneeuwbuien en onweer'
    },
    lightrain: {
        symbol: '46',
        text: 'lichte regenval'
    },
    rain: {
        symbol: '09',
        text: 'regen'
    },
    heavyrain: {
        symbol: '10',
        text: 'hevige regenval'
    },
    lightrainandthunder: {
        symbol: '30',
        text: 'lichte regen en onweer'
    },
    rainandthunder: {
        symbol: '22',
        text: 'regen en onweer'
    },
    heavyrainandthunder: {
        symbol: '11',
        text: 'hevige regen en onweer'
    },
    lightsleet: {
        symbol: '47',
        text: 'lichte ijzel'
    },
    sleet: {
        symbol: '12',
        text: 'ijzel'
    },
    heavysleet: {
        symbol: '48',
        text: 'hevige ijzel'
    },
    lightsleetandthunder: {
        symbol: '31',
        text: 'lichte ijzel en onweer'
    },
    sleetandthunder: {
        symbol: '23',
        text: 'ijzel en onweer'
    },
    heavysleetandthunder: {
        symbol: '32',
        text: 'hevige ijzel en onweer'
    },
    lightsnow: {
        symbol: '49',
        text: 'lichte sneeuwval'
    },
    snow: {
        symbol: '13',
        text: 'sneeuwval'
    },
    heavysnow: {
        symbol: '50',
        text: 'hevige sneeuwval'
    },
    lightsnowandthunder: {
        symbol: '33',
        text: 'lichte sneeuwval en onweer'
    },
    snowandthunder: {
        symbol: '14',
        text: 'sneeuwval en onweer'
    },
    heavysnowandthunder: {
        symbol: '34',
        text: 'hevige sneeuwval en onweer'
    },
    fog: {
        symbol: '15',
        text: 'mist'
    }
};

/**
 * Draw the weather symbols on top of the temperature series. The symbols are
 * fetched from yr.no's MIT licensed weather symbol collection.
 * https://github.com/YR/weather-symbols
 */
Meteogram.prototype.drawWeatherSymbols = function (chart) {

    chart.series[0].data.forEach((point, i) => {
        if (this.resolution > 36e5 || i % 2 === 0) {

            const [symbol, specifier] = this.symbols[i].split('_'),
                icon = Meteogram.dictionary[symbol].symbol +
                    ({ day: 'd', night: 'n' }[specifier] || '');

            if (Meteogram.dictionary[symbol]) {
                chart.renderer
                    .image(
                        'https://cdn.jsdelivr.net/gh/nrkno/yr-weather-symbols' +
                            `@8.0.1/dist/svg/${icon}.svg`,
                        point.plotX + chart.plotLeft - 8,
                        point.plotY + chart.plotTop - 30,
                        30,
                        30
                    )
                    .attr({
                        zIndex: 5
                    })
                    .add();
            } else {
                console.log(symbol);
            }
        }
    });
};


/**
 * Draw blocks around wind arrows, below the plot area
 */
Meteogram.prototype.drawBlocksForWindArrows = function (chart) {
    const xAxis = chart.xAxis[0];

    for (
        let pos = xAxis.min, max = xAxis.max, i = 0;
        pos <= max + 36e5; pos += 36e5,
        i += 1
    ) {

        // Get the X position
        const isLast = pos === max + 36e5,
            x = Math.round(xAxis.toPixels(pos)) + (isLast ? 0.5 : -0.5);

        // Draw the vertical dividers and ticks
        const isLong = this.resolution > 36e5 ?
            pos % this.resolution === 0 :
            i % 2 === 0;

        chart.renderer
            .path([
                'M', x, chart.plotTop + chart.plotHeight + (isLong ? 0 : 28),
                'L', x, chart.plotTop + chart.plotHeight + 32,
                'Z'
            ])
            .attr({
                stroke: chart.options.chart.plotBorderColor,
                'stroke-width': 1
            })
            .add();
    }

    // Center items in block
    chart.get('windbarbs').markerGroup.attr({
        translateX: chart.get('windbarbs').markerGroup.translateX + 8
    });

};

/**
 * Build and return the Highcharts options structure
 */
Meteogram.prototype.getChartOptions = function () {
    return {
        chart: {
            renderTo: this.container,
            marginBottom: 70,
            marginRight: 40,
            marginTop: 50,
            plotBorderWidth: 1,
            height: 310,
            alignTicks: false,
            scrollablePlotArea: {
                minWidth: 720
            }
        },

        defs: {
            patterns: [{
                id: 'precipitation-error',
                path: {
                    d: [
                        'M', 3.3, 0, 'L', -6.7, 10,
                        'M', 6.7, 0, 'L', -3.3, 10,
                        'M', 10, 0, 'L', 0, 10,
                        'M', 13.3, 0, 'L', 3.3, 10,
                        'M', 16.7, 0, 'L', 6.7, 10
                    ].join(' '),
                    stroke: '#68CFE8',
                    strokeWidth: 1
                }
            }]
        },

        subtitle: {
            text: 'lokatie: ' + LocationName + LastUpdate,
            style: { fontSize: '12px', color: '#2A3B55' },
            align: 'center',
            y: 20
        },

        title: {
            text: this.getTitle(),
            align: 'center', //'left',
            style: {
                fontSize: '12px', color: '#2A3B55',
                whiteSpace: 'nowrap',
                textOverflow: 'ellipsis'
            }
        },

        credits: {
            text: 'weersverwachting: YR.no, fijnstof: AQICN.org en ESA.int (CAMS), chart techniek: highcharts.com',
            href: 'https://yr.no',
            position: { x: -40, y: -10 }
        },

        tooltip: {
            shared: true,
            useHTML: true,
            headerFormat:
                '<small>{point.x:%A, %b %e, %H:%M} - {point.point.to:%H:%M}</small><br>' +
                '<b>{point.point.symbolName}</b><br>'

        },

        xAxis: [{ // Bottom X axis
            type: 'datetime',
            tickInterval: 2 * 36e5, // two hours
            minorTickInterval: 36e5, // one hour
            tickLength: 0,
            gridLineWidth: 1,
            gridLineColor: 'rgba(128, 128, 128, 0.1)',
            startOnTick: false,
            endOnTick: false,
            minPadding: 0,
            maxPadding: 0,
            offset: 30,
            showLastLabel: true,
            labels: {
                format: '{value:%H}'
            },
            crosshair: true
        }, { // Top X axis
            linkedTo: 0,
            type: 'datetime',
            tickInterval: 24 * 3600 * 1000,
            labels: {
                format: '{value:<span style="font-size: 12px; font-weight: bold">%a</span> %b %e}',
                align: 'left',
                x: 3,
                y: -5
            },
            opposite: true,
            tickLength: 20,
            gridLineWidth: 1
        }],

        yAxis: [{ // temperature axis
            title: {
                text: null
            },
            labels: {
                format: '{value}°',
                style: {
                    fontSize: '10px'
                },
                x: -3
            },
            plotLines: [{ // zero plane
                value: 0,
                color: '#BBBBBB',
                width: 1,
                zIndex: 2
            }],
            maxPadding: 0.3,
            minRange: 8,
            tickInterval: 1,
            gridLineColor: 'rgba(128, 128, 128, 0.1)'

        }, { // precipitation axis
            title: {
                text: null
            },
            labels: {
                enabled: false
            },
            gridLineWidth: 0,
            tickLength: 0,
            minRange: 10,
            min: 0

        }, { // Air pressure
            allowDecimals: false,
            title: { // Title on top of axis
                text: 'hPa',
                offset: 0,
                align: 'high',
                rotation: 0,
                style: {
                    fontSize: '10px',
                    color: Highcharts.getOptions().colors[2]
                },
                textAlign: 'left',
                x: 3
            },
            labels: {
                style: {
                    fontSize: '8px',
                    color: Highcharts.getOptions().colors[2]
                },
                y: 2,
                x: 3
            },
            gridLineWidth: 0,
            opposite: true,
            showLastLabel: false
        }, { // AQI
            allowDecimals: false,
            title: { // Title on top of axis
            text: AQItype[0],
                offset: 0,
                align: 'high',
                rotation: 90,
                style: {
                    fontSize: '10px',
                    fontWeight: 'bold',
                    color: 'green'
                },
                textAlign: 'left',
                x: 10
            },
            labels: {
                style: {
                    fontSize: '8px',
                    color: 'black'
                },
                y: 2,
                x: 10
            },
            gridLineWidth: 0,
            opposite: true,
            showLastLabel: false
        }],
        legend: {
            enabled: false
        },

        plotOptions: {
            series: {
                pointPlacement: 'between'
            }
        },


        series: [{
            name: 'temperatuur',
            data: this.temperatures,
            type: 'spline',
            marker: {
                enabled: false,
                states: {
                    hover: {
                        enabled: true
                    }
                }
            },
            tooltip: {
                pointFormat: '<span style="color:{point.color}">\u25CF</span> ' +
                    '{series.name}: <b>{point.y}°C</b><br/>'
            },
            zIndex: 1,
            color: '#FF3333',
            negativeColor: '#48AFE8'
        }, {
            name: 'neerslag',
            data: this.precipitationsError,
            type: 'column',
            color: 'url(#precipitation-error)',
            yAxis: 1,
            groupPadding: 0,
            pointPadding: 0,
            tooltip: {
                valueSuffix: ' mm',
                pointFormat: '<span style="color:{point.color}">\u25CF</span> ' +
                    '{series.name}: <b>{point.minvalue} mm - {point.maxvalue} mm</b><br/>'
            },
            grouping: false,
            dataLabels: {
                enabled: this.hasPrecipitationError,
                filter: {
                    operator: '>',
                    property: 'maxValue',
                    value: 0
                },
                style: {
                    fontSize: '8px',
                    color: 'gray'
                }
            }
        }, {
            name: 'neerslag',
            data: this.precipitations,
            type: 'column',
            color: '#68CFE8',
            yAxis: 1,
            groupPadding: 0,
            pointPadding: 0,
            grouping: false,
            dataLabels: {
                enabled: !this.hasPrecipitationError,
                filter: {
                    operator: '>',
                    property: 'y',
                    value: 0
                },
                style: {
                    fontSize: '8px',
                    color: 'gray'
                }
            },
            tooltip: {
                valueSuffix: ' mm'
            }
        }, {
            name: 'luchtdruk',
            color: Highcharts.getOptions().colors[2],
            data: this.pressures,
            marker: {
                enabled: false
            },
            shadow: false,
            tooltip: {
                valueSuffix: ' hPa'
            },
            dashStyle: 'shortdot',
            yAxis: 2
        }, {
            name: 'PM<span style="font-size:60%">2.5</span>',
            data: this.aqi,
            type: 'spline',
            tooltip: {
                pointFormatter: function () {
                   return AQItype[0] + ' luchtkwaliteitsindex: ' + this.y + ' <b>' + AQIname(this.y) + '</b><br>';
                }
            },
            marker: {
                // enabled: false
                fillColor: 'yellow',
                radius: 1
            },
            dataLabels: {
                enabled: true,
                formatter: function () {
                    if ( AQItops.includes(this.x) ) {
                        if( this.y < 10 ) { return Math.round(this.y*10+0.5)/10; }
                        else { return Math.round(this.y); }
                    }
                },
                style: { fontSize: '8px' }
            },
            zones: [
                { color: '#6cff00' },
                { value: (AQItype[0] === 'AQI' ? AQIlevels.AQI : AQIlevels.LKI),
                  color: '#ffd800' },
                { value: (AQItype[0] === 'AQI' ? (2*AQIlevels.AQI) : (AQIlevels.LKI+2)),
                  color: '#ff9000' },
                { value: (AQItype[0] === 'AQI' ? (4*AQIlevels.AQI) : (AQIlevels.LKI+5)),
                  color: '#ff3600'}
                ],
            yAxis: 3,
            pointPlacement: 'between',
            pointWidth: 10,
            pointPadding: 0
        }, {
            name: 'wind',
            type: 'windbarb',
            id: 'windbarbs',
            color: Highcharts.getOptions().colors[1],
            lineWidth: 1.5,
            data: this.winds,
            vectorLength: 18,
            yOffset: -15,
            tooltip: {
                valueSuffix: ' m/s'
            }
        }]
    };
};

/**
 * Post-process the chart from the callback function, the second argument
 * Highcharts.Chart.
 */
Meteogram.prototype.onChartLoad = function (chart) {

    this.drawWeatherSymbols(chart);
    this.drawBlocksForWindArrows(chart);

};

/**
 * Create the chart. This function is called async when the data file is loaded
 * and parsed.
 */
Meteogram.prototype.createChart = function () {
    this.chart = new Highcharts.Chart(this.getChartOptions(), chart => {
        this.onChartLoad(chart);
    });
};

Meteogram.prototype.error = function () {
    document.getElementById('loading').innerHTML =
        '<i class="fa fa-frown-o"></i> Failed loading data, please try again later';
};

/**
 * Handle the data. This part of the code is not Highcharts specific, but deals
 * with yr.no's specific data format
 */
Meteogram.prototype.parseYrData = function () {

    let pointStart;

    if (!this.json) {
        return this.error();
    }

    // Loop over hourly (or 6-hourly) forecasts
    this.json.properties.timeseries.forEach((node, i) => {

        const x = Date.parse(node.time),
            nextHours = node.data.next_1_hours || node.data.next_6_hours,
            symbolCode = nextHours && nextHours.summary.symbol_code,
            to = node.data.next_1_hours ? x + 36e5 : x + 6 * 36e5;

        if (to > pointStart + 48 * 36e5) {
            return;
        }

        // Populate the parallel arrays
        this.symbols.push(nextHours.summary.symbol_code);

        this.temperatures.push({
            x,
            y: node.data.instant.details.air_temperature,
            // custom options used in the tooltip formatter
            to,
            symbolName: Meteogram.dictionary[
                symbolCode.replace(/_(day|night)$/, '')
            ].text
        });

        this.precipitations.push({
            x,
            y: nextHours.details.precipitation_amount
        });

        if (i % 2 === 0) {
            this.winds.push({
                x,
                value: node.data.instant.details.wind_speed,
                direction: node.data.instant.details.wind_from_direction
            });
        }

        this.pressures.push({
            x,
            y: node.data.instant.details.air_pressure_at_sea_level
        });

        //this.aqi.push({
        //    x,
        //    y: fijnstofAQI[i],
        //    color: fijnstofColors[i],
        //    // name: fijnstofQualifications[i]
        //});
        //for( indx = 0; indx <= fijnstofAQI.length; indx++ ) {
        //    /* interval is 3 hours, choose the first of 3 hours */
        //    //if ( ((fijnstofStart + indx * 3600e3) >= pointStart) && ((fijnstofStart + indx * 3600e3) < to) ) {
        //    if ( (pointStart + indx * 3600e3) < to) ) {
        //        if ( fijnstofAQI[indx-1] && fijnstofColors[indx-1] ) {
        //            this.aqi.push({
        //                x,
        //                y: fijnstofAQI[indx-1],
        //                color: fijnstofColors[indx-1],
        //                // name: fijnstofQualifications[indx-1]
        //            });
        //        }
        //        /* break ; */
        //    }
        //}
     if ( fijnstofStart == 0 ) { fijnstofStart = x; } // just for debugging
     var PrevY = 0;  var PrevX = 0; var Div = 0;
     for( indx = 0; indx <= fijnstofAQI.length; indx++ ) {
          /* interval is 3 hours, choose the first of the 3 hours */
          if ( ((fijnstofStart + indx * 3600e3) >= x) && ((fijnstofStart + indx * 3600e3) < to) ) {
              if( AQItops.includes(indx) ) AQItops.push(x);
              this.aqi.push({
                     x, // : fijnstofStart + indx * 3600e3,
                     // name: fijnstofQualifications[indx],
                     y: fijnstofAQI[indx]
              });
              break;
           }
       }

        if (i === 0) {
            pointStart = (x + to) / 2;
        }
    });

    // Create the chart when the data is loaded
    this.createChart();
};
// FORECAST end GLOB

// FORECAST start DOM
// FORECAST end DOM

document.addEventListener('DOMContentLoaded', function () {
        const meteogram = new Meteogram(weather, 'FORECASTING_'+AQItype[0]);
});
</script>
              
<figure class="highcharts-figure">
<div id="FORECASTING" style="width: 100%; height: 310px; margin: 0 auto">
</figure>

</body>
</html>
