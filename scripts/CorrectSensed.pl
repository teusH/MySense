# $Id: CorrectSensed.pl,v 1.3 2021/05/13 15:18:15 teus Exp teus $
# Copyright (C) 2021, Teus Hagen, the Netherlands
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the Reciprocal Public License as published by
# the Open Source Initiative https://opensource.org/licenses/RPL-1.5:
#
#   Unless explicitly acquired and licensed from Licensor under another
#   license, the contents of this file are subject to the Reciprocal Public
#   License ("RPL") Version 1.5, or subsequent versions as allowed by the RPL,
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
#

##!/bin/bashbash
# # calculate sensor type per manufacturer correction for pollutants 
# # usage: CORRECT {TBL=project_serial|TBL=station} REF=ReferencedSensorType [REG=0.6] SENSOR=SensorType polI[=valueI] ....
# # where (Referenced)SensorType is eg SDS011, PMS[xA157]003, SPS30 or Nova, Plantwoer, Sensirion
# # and polI is either pm_10,pm10,pm_25,pm25,pm1 and valI the value to be corrected
# # value may be a comma separated list. Field separator is automatically detected
# # REG is minimal regression factor for selecting correction algorithm. Default 0.6.
# # returns corrected values or in case of empty value the correction algorithm
# function CORRECT()
# {
#    local P SENSOR REF ARG REG SEP=' '
#    declare -a POLS
#    declare -i I
#    for ARG in $*
#    do
#        case "${ARG}" in
#        REF=*) REF="${ARG/*=/}" ; REF="${REF^^}"  # reference sensor type, default SPS30
#        ;;
#        SENSOR=*) SENSOR="${ARG/*=/}" ; SENSOR="${SENSOR^^}" # sensor type of manufacturer eg SPS30
#        ;;
#        REG=*) REG="${ARG/*=/}"                   # minimal regression selection correction criterium
#        ;;
#        pm*=*|PM*=*)                              # yet only PM sensors type are supported
#            POLS[$I]="${ARG/=*/}=${ARG/*=/}" ; I+=1
#            SEP=' '
#        ;;
#        *)
#           if echo "$ARG" | grep -q -P ',[a-zA-Z]' ; then ARG="${ARG//,/ }" ; SEP=',' ; fi
#           for P in $ARG
#           do
#                 if ! echo  "$P" | grep -q -P '^[A-Za-z0-9_]+$'
#                 then
#                     echo "ERROR: unsupportant pollutant ${P/=*/}. Skipped." >/dev/stderr
#                 else
#                     POLS[$I]="$P" ; I+=1   # maybe pollutant (e.g. rv) will not get correction
#                 fi
#           done
#        ;;
#        esac
#    done
#    if [ -z "$REF" ] || [ -z "$SENSOR" ]
#    then
#        echo "ERROR in command CORRECT arguments (missing REF or one of TBL/SENSOR) $*" >/dev/stderr
#    fi
#    ARG=''
#    for (( I=0; I < ${#POLS[@]}; I++ ))
#    do
#        if [ -z "$ARG" ]
#        then ARG="${POLS[$I]}"
#        else ARG+="${SEP}${POLS[$I]}"
#        fi
#    done
#    if [ "$REF" = "$SENSOR" ] # no correction to be applied
#    then
#        echo "${ARG}"
#        return 0
#    fi
#    if [ -z "$SENSOR" ]
#    then
#        echo "ERROR: sensor type not defined! Missing SENSOR or PROJ_SERIAL definition." >/dev/stderr
#        return 1
#    fi
#    SENSOR="\$SENSOR = '$SENSOR';"
#    if [ -n "$REG" ]  # minimal regression factor for alg selection
#    then SENSOR="$SENSOR \$REG = $REG;"
#    fi
#    # SENSOR+=" \$debug = 2;"
#    ARG="\$REF = '$REF'; $SENSOR print(CORRECT('${ARG}'));"
#    perl -e "require './CorrectSensed.pl';" -e "$ARG"
# }
# # test examples:
# CORRECT REF=SPS30 SENSOR=PMSX003 pm10=35.5 pm25=25.8 pm1=20.7
# CORRECT SENSOR=SAN_30aea4509eb4 REF=SPS30 "pm10=35.5 pm25=25.8 pm1=20.7"
# CORRECT REF=SPS30 SENSOR=SDS011 pm10,pm25,pm1,rv,luchtdruk,temp
# CORRECT SENSOR=BAM1020 REF=SPS30 pm25 pm10
# CORRECT SENSOR=NL1031 REF=SPS30 "pm25 pm10"

# Air Quality Index details and constants

# correction of senor values, focussed on PM sensors
use Env qw(HOME DBUSER DBPASS DBHOST);  # for working from HOME dir, and DB credits
use feature "state";            # some routines keep own state variables
# use Data::Dumper; # just for debugging purposes

use constant {
        USER => 'someuser', PASSWD => 'somepass', HOST => 'localhost',
        DB        => 'luchtmetingen',   # default database
        FALSE     => 0,
        TRUE      => 1,
};
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

# my $debug = 2;

# one row of values from one column out of the DB table
sub query {
    return 0 if !Check_DB();
    my $tbl = shift; Check_Tbl($tbl) if $tbl;
    my $q = shift;
    if( (not $mysql) or ($mysql == 1) or (not $q) ){ return undef; }
    #print STDERR "MYSQL: $q\n" if (defined $debug) && ($debug > 1);
    my $sth = $mysql->prepare($q); $sth->execute();
    #  ref to 2 dimensional refs to array string values
    if( $q =~ /^\s*(show|describe|select)/i ){
        my $r = $sth->fetchall_arrayref();
        print STDERR "ERROR: mysql query: $q with error:\n" . DBI->errstr . "\n"
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

# obtain all sensors for a station in the DB table
sub Get_Columns {
    my $tbl = shift; return 0 if not $tbl;
    Check_Tbl($tbl) if not $DB_cols{$tbl};
    if( not (scalar keys %{$DB_cols{$tbl}}) ){
        # only once at the start we build a column existance cache
        my $qr = query($tbl, "DESCRIBE $tbl;");
        if( (not $qr) || ($#{$qr} < 0) ){
            print STDERR "ERROR: Cannot obtain table $tbl description\n";
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
        Get_Columns($qry->[$i]);        # mark sensors present in the table
    }
    return 1 if defined $DB_cols{$tbl};
    return 0;
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
            print STDERR "ERROR: Cannot open mysql database ".$mydb." on host ".$myhost.", with user ".$myuser.", error: ". DBI->errstr."\n" ;
            exit 1;
        }
    }
    return 1;
}

my %DB_cols = ( );      # sensors names per table, unused in AqI.pl

# default sensor pollutant correction template
$SENSOR = '';      # sensor manuafacturer type
$REF    = '';      # reference sensor type. Has to be defined.
$REG    = 0;       # minimal regression algorithm selection criterium
# default template
my $SensorRegressionsRef = 'SPS30';  # reference sensor type Sensirion
my $SensorRegressionsReg = 0.6;       # minimal regression factor
# using SPS30 Sensirion as reference
my %SensorRegressions = (
    # Sensirion serie is default, ref. sensor type
    # Plantower serie
    'PMSX003' => {pm10 => [-4.65/1.452,1/1.452],     # R2=0.8025
                  pm25 => [-0.0217/1.713,1/1.713],   # R2=0.9432
                  pm1 => [-0.0217/1.713,1/1.713],    # using PM25
                 },
    # Nova serie
    'SDS011'  => {pm10 => [-0.5402/1.202,1/1.202],   # R2=0.7956
                  pm25 => [0.8843/1.042,1/1.042],    # R2=0.8938
                  pm1 => [0.8843/1.042,1/1.042],     # using PM25
                 },
    # BAM1020 <-> dust sensor XYZ R2:
    # SPS30:   PM10 R2 0.1976, PM25 R2 0.7391
    # PMSx003: PM10 R2 0.1378, PM25 R2 0.6467
    # SDS011:  PM10 R2 0.1462, PM25 R2 0.5815
    'BAM1020' => {# pm10 => [5.506,0.4303],          # R2=0.1976
                  pm25 => [-2.297,1.402],            # R2=0.7391
                  pm1 => [-2.297,1.402],             # using PM25
                 },
    'default' => [0,1],
);

# try to identify the hardware sensor via data DB table Sensors
sub GetSensorType {
  my ($table, $pol) = @_;
  $pol = 'pm' if not defined $pol;
  if( $table =~ /^(\w+)_(\w+)$/ ) {
    my $project = $1; my $serial = $2;
    my $qry = query('Sensors',"SELECT CONCAT(description,';') FROM Sensors WHERE active AND project = '$project' AND serial = '$serial' ORDER BY datum DESC");
    for( my $i = 0; $i <= $#{$qry}; $i++ ) {
      if( $qry->[$i] =~ /.*hw:\s*([^;]*);/ ) {
        my $ST = $1;
        if( $pol =~ /pm/ ) { $ST =~ s/^.*(PMS[xa157]003|SPS[0-9]{2}|SDS[0-9]{3}).*$/\1/i; }
        elsif( $pol =~ /(temp|rv|luchtdruk|aqi)/ )
            { $ST =~ s/^.*(SHT[0-9]{2}|BME[0-9]{3}|DHT[0-9]{2}).*$/\1/i; }
        else { $ST = ''; }
        if( $ST ) { return $ST; }
      }
     }
  } else { return 'BAM1020' ; } # governmental sensor type dflt
  return '';
}

# define sensor type correction to be done. If needed obtain correction info from database
# called with eg 'pm10= pm25=25.8 pm1=20.7,15.3'
# returns either with correction algorithm or list of corrected values per pol type
sub CORRECT {
  my $values = shift;
  my $sep = ' ';
  $REF = $SensorRegressionsRef if not $REF;      # reference sensor type. Has to be defined.
  $REG = $SensorRegressionsReg if not $REG;      # minimal regression algorithm selection criterium
  # may need to improve these checks on supported REF sensors and sensors in type table
  if( not $REF =~ /(SPS[0-9]{2}|PMS[0-9xX]{4}|SDS[0-9]{3})/ ) {
    print STDERR "WARNING: unknown sensor type '$REF'. No correction.\n";
    return $values;
  }
  if( $SENSOR =~ /.+_.+/ ) { # get SENSOR from DB Sensors HW description
    $SENSOR = GetSensorType( $SENSOR, $values );
  }
  if( not $SENSOR ) {
    print STDERR "WARNING: Unable to detect used sensor type via DB table or otherwise. No correction.\n";
    return $values;
  }
  $REF = uc $REF;
  my $sensor = uc $SENSOR; $SENSOR = '';
  print STDERR "DEBUG: ref $REF, sensor $sensor, values: $values\n" if (defined $debug) && $debug;
  return $values if $REF eq $sensor;
  $values =~ s/=(\s|,)/\1/g;
  if( $values =~ /^([a-z][a-z0-9_]+)(=[0-9,\.]+)*(.)/ ){ $sep=$3; } # auto detect separator
  if ( $REF ne $SensorRegressionsRef || $REG != $SensorRegressionsReg ) {
    InstallRegressions( $REF, $REG );
  }
  my @all = split(/$sep/,$values);
  my @rslt;
  for( my $i = 0; $i <= $#all; $i++ ) {
    next if $all[$i] !~ /^pm/; # for now only PM pollutants are corrected
    if( $all[$i] =~ /(pm.*)=(.*)/ ) {
       my $pol = $1; my @vals = split(/,/,$2);
       for( my $j = 0; $j <= $#vals; $j++) {
            $vals[$j] = sprintf("%.2f",SensorCorrection($sensor,$pol,$vals[$j]));
       }
       $all[$i] = $pol.'='.join(',',@vals);
    } else { # return algorithm
       $all[$i] = SensorCorrection($sensor,$all[$i]);
    }
  }
  $values = join($sep,@all);
  print STDERR "DEBUG: ref $REF, sensor $sensor, adjusted values: $values\n" if (defined $debug) && $debug;
  return $values;
}


# try to initialyze $SensorRegressions from database
sub InstallRegressions {
    my ($Ref, $Reg) = @_;
    $Ref =~ s/PMS./PMSX/i if $Ref =~ /^PMS[xX57]/i; # map all to PMSx003
    $Ref = uc $Ref;
    if (($SensorRegressionsRef eq $Ref) && $SensorRegressionsReg == $Reg ) {
       return $SensorRegressionsRef;
    }
    my $qry = query("SensorRegression",
              "SELECT CONCAT(LOWER(pol),';',TypeRef,';',TypeFrom,';',R2,';',Taylor)
              FROM SensorRegression WHERE TypeRef = '$Ref' OR TypeFrom = '$Ref' ORDER BY datum");
    %SensorRegressions = (); $SensorRegressions{'default'} = [0,1]; my $rslt = 0;
    for( my $i=0; $i <= $#{$qry}; $i++ ) {
        my ($pol,$typeRef,$typeFrom,$R2,$Taylor) = split(/;/,$qry->[$i]);
        next if $R2 < $Reg;
        my @AR = split(/,/,$Taylor);
        if ( $typeFrom =~ /$Ref/ ) { # inverse Taylor sequence
           next if $#{AR} > 1; # inverse Taylor is a bit complex for O(2)
           if ( $AR[1] ) { $AR[1] = 1.0/$AR[1]; $AR[0] = -$AR[0]*$AR[1]; }
           $typeFrom = $typeRef;
        }
        $SensorRegressions{$typeFrom} = {} if not defined $SensorRegressions{$typeFrom};
        $SensorRegressions{$typeFrom}{$pol} = \@AR;
        if ( $pol =~ /pm25/ ) {
            $SensorRegressions{$typeFrom}{pm1} = \@AR;
        }
        $rslt++;
    }
    $SensorRegressionsRef = $Ref;
    $SensorRegressionsReg = $Reg;
    return '' if not $rslt;
    return $Ref;
}

# per manufactorer type the measurement may be corrected via regression correction
# returns reference to Taylor sequence a0+a1*x**1+a2*x**2+... (a0,a1,a2,...)
# here we use one reference: Sensirion SPS30
sub SensorCFactors {
    my ($type, $pol) = @_;
    if (($REF ne $SensorRegressionsRef) || ($REG != $SensorRegressionsReg)) {
        $REF = InstallRegressions($REF,$REG);
    }
    return \$SensorRegressions{default} if not $REF;
    $type =~ s/PMS./PMSX/i if $type =~ /^PMS[xX57]/i; # map all to PMSx003
    return \$SensorRegressions{default} if (not $type) || (not $pol) || (not defined $SensorRegressions{uc $type});
    return \$SensorRegressions{uc $type}{lc $pol} if defined $SensorRegressions{uc $type}{lc $pol};
    return \$SensorRegressions{default}
}

sub SensorCorrection {
    my ($type, $pol, $val) = @_;
    $pol =~ s/_//; $pol = lc $pol;
    return $val if not $REF;
    return $val if $pol !~ /pm.*/i;
    return $val if $REF eq $SENSOR;
    my $taylor = SensorCFactors($type, $pol);
    if( not defined $val ) { # return MySQL qry select item
        my $rts = '';
        return $pol if (${$$taylor}[0] == 0) && (${$$taylor}[1] == 1);
        for( my $i = 0; $i <= $#{$$taylor}; $i++ ) {
            if ( $i == 0 ) { $rts = sprintf("%.4f",${$$taylor}[$i]); }
            elsif( $i == 1 ) { $rts .= sprintf("+(%.4f*$pol)",${$$taylor}[$i]) ;}
            else { $rts .= sprintf("+(%.4f*POW($pol,$i))",${$$taylor}[$i]) ;}
        }
        return $rts;
    } else {
        my $rts = 0;
        return $val if (${$$taylor}[0] == 0) && (${$$taylor}[1] == 1);
        for( my $i = 0; $i <= $#{$$taylor}; $i++ ) {
            $rts += ${$$taylor}[$i]*$val**$i;
        }
        return $rts;
   }
}

# routines to calculate AQI, AQHI, LKI and other Index values
# returns an array with index value, std grade color, grade string, grade index and
# Google-o-meter URL for image png, size 200x150
# on error or unknow index value is zero
{
   if( (defined $debug) && ($debug > 1) ) {
   # module tests:
   print("REF = 'SPS30'; SENSOR = 'SDS011'; CORRECT('pm10,pm25,pm1,rv,luchtdruk,temp');\n");
   $REF = 'SPS30'; $SENSOR = 'SDS011';
   print(CORRECT('pm10,pm25,pm1,rv,luchtdruk,temp')); print("\n");

   print("SENSOR='SAN_cc50e39c8cc4';REF=''; CORRECT('pm_10=35.8 pm25=25.8 pm1=20.7,15.3');\n");
   $SENSOR='SAN_cc50e39c8cc4';$REF='SPS30';
   print(CORRECT('pm_10=35.8 pm25=25.8 pm1=20.7,15.3')); print("\n");

   print("REF='SPS30';SENSOR='PMSX003'; CORRECT('pm10 pm25 pm1');\n");
   $REF='SPS30';$SENSOR='PMSX003';
   print(CORRECT('pm10 pm25 pm1')); print("\n");

   print("REF='SPS30';SENSOR='PMSX003'; CORRECT('pm10,pm25,pm1');\n");
   $SENSOR='PMSX003';
   print(CORRECT('pm10,pm25,pm1')); print("\n");
   } else { 1; }

} # end of AQI calculation routines
