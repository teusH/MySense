#!/bin/bash
# add new columns if needed so
# correct GEO location in database Sensors table
# convert street nr to street and housenr
# copyright: 2021 teus hagen, the netherlands
# Open Source license RPL 1.15
# 
# $Id: MyDB-upgrade.sh,v 1.9 2021/09/28 15:01:08 teus Exp teus $

DEBUG=${DEBUG:-0}       # be very verbose
VERBOSE=${VERBOSE:-0}   # be verbose
RESET=0                 # drop previously added columns, eg sensors
if (( $DEBUG > 0 )) ; then VERBOSE=1 ; fi
if [ -t 2 ] # if tty/terminal use color terminal output
then
    RED="\033[1;31m"
    GREEN="\033[1;32m"
    BLACK="\033[30m"
    YELLOW="\033[33m"
    BLUE="\033[34m"
    MAGENTA="\033[35m"
    CYAN="\033[36m"
    WHITE="\033[37m"
    NOCOLOR="\033[0m"
    BOLD="\033[1m"
    UNDERLINE="\033[4m"
    REVERSED="\033[7m"
    NOCOLOR="\033[0m"
else
    RED=""
    GREEN=""
    NOCOLOR=''
    BLACK=""
    YELLOW=""
    BLUE=""
    MAGENTA=""
    CYAN=""
    WHITE=""
    BOLD=""
    UNDERLINE=""
    REVERSED=""
fi

SOURCE_DB=lunar                    # host with up to date DB
export DBUSER=${DBUSER:-$USER}      # database user
export DBPASS=${DBPASS:-acacadabra} # database password for access
HOST=${HOST:-localhost}
export DBHOST=${DBHOST:-$HOST}
if [ "$DBHOST" != localhost ]
then
    echo -e "${RED}Use script only on not operational DBHOST '$DBHOST'${NOCOLOR}" >/dev/stderr
    exit 1
fi
if [ $(hostname) = ${SOURCE_DB} ]  # just a check
then
   echo -e "${RED}DO NOT RUN on life DB host: $DBHOST${NOCOLOR}" >/dev/stderr
   read -p "$RED}Are you sure to run this with DB on $DBHOST?${NOCOLOR} yes|[exit]" -t 30 YES
   if [ x$YES != xyes ] ; then exit 1 ; fi
fi
if (( $DEBUG > 0 )) ; then export DBHOST=${HOST} ; fi
export DB=${DB:-luchtmetingen}
MYSQL="mysql -u $DBUSER -p$DBPASS -N -B --silent -h $DBHOST $DB"
#export DBHOST=localhost
if which mysql_config_editor >/dev/null
then
    PASSED=$(mysql_config_editor print --login-path=$DB \
        | awk '/password =/{ print "HIDDEN" ; }')
    MYSQL="mysql --login-path=$DB -N -B --silent -h $DBHOST $DB"
fi

# we show progress when command seems to take some long time.
pid=""                          # need pid of forked process progress bar
timing=""                       # keeps start time
function progressing {
  # Sleep at least 1 second otherwise this algoritm will consume
  # a lot system resources.
  set +x
  local interval=1 message="Progressing  " count=0 chars=( "-" "\\" "|" "/" ) pos=0

  if [ -n "$1" ] ; then message="$1  " ; fi
  printf "%-60s" "$message...  " 1>&2
  while true
  do
    pos=$(($count % 4))
    echo -en "\b${chars[$pos]}" 1>&2
    count=$(($count + 1))
    sleep $interval
  done
  return 0
}

#
# Stop distraction
#
timing=""
function stop_progressing {
    # exec 2>/dev/null
    if [ -n "$pid" ] ; then kill $pid ; sleep 1; fi
    pid=""
    if [ -n "$timing" -a -t 2 ]
    then
        timing=$((`date "+%s"` - $timing))
        if [ $(($timing / 60)) -gt 0 ] ; then
            echo -en "\b \t$(($timing / 60)) min $(($timing % 60)) sec\n" 1>&2
        else
            echo -en "\b \t$(($timing % 60)) sec\n" 1>&2
        fi
    fi
    timing=""
    return 0
}

function start_progressing(){
    if [ -n "$pid" ]; then kill $pid; fi
    timing=`date "+%s"`
    if [ -t 2 ] && [ -z "$DEBUG" ]
    then
        progressing  "$1"  &
        pid=$!
    fi
    return 0
}
# convert street nr -> street and housenr
function updateHouseNR() {
    local ENTRY ENTRIES
    ENTRIES=$($MYSQL -e "SELECT CONCAT(UNIX_TIMESTAMP(id),'=',UNIX_TIMESTAMP(datum),'=',REPLACE(street,' ','@')) FROM ${1:-Sensors} WHERE NOT ISNULL(street)")
    for ENTRY in $ENTRIES
    do
        ENTRY=$(echo "$ENTRY" | perl -e 'while ($_ = <STDIN>)' -e '{' -e 's/@/ /g;' -e 'if ( /^([0-9]+)=([0-9]+)=([A-Za-z]+[\w\s\-\(\)]*)\s+([0-9]\w*)$/ ){'  -e 'print("street = \"$3\", housenr = \"$4\", datum = FROM_UNIXTIME($2) WHERE UNIX_TIMESTAMP(id) = $1\n");' -e '}}')
        if [ -n "$ENTRY" ] ; then echo "UPDATE ${1:-Sensors} SET $ENTRY;" ; fi
    done | $MYSQL
}

# add missing columns in a table
function Add_Cols() {
    local FLD TBL=${1:-Sensors}; shift
    local COLS="$*"
    local TBLCOLS=$($MYSQL -e "DESCRIBE $TBL" | awk '{ print $1; }' | grep -P "(${COLS// /\|})" )
    for FLD in $COLS
    do
      if ! echo "${TBLCOLS}" | grep -q $FLD
      then
        case $FLD in
        #location) # POINT type MySQL problem is wrong POINT(lat,lon)
        #  # depreciated as other DB's use POINT(lon,lat)
        #  $MYSQL -e "ALTER TABLE $TBL ADD COLUMN $FLD GEOMETRY DEFAULT NULL COMMENT 'geo location'"
        #;;
        geohash) # geohash is lat, lon sequence independent TBL: Sensors, measurement tables
          $MYSQL -e "ALTER TABLE $TBL ADD COLUMN $FLD varchar(12) DEFAULT NULL COMMENT 'geo hash location'"
        ;;
        geohash_valid) # geohash is lat, lon sequence independent TBL: measurement tables
          $MYSQL -e "ALTER TABLE $TBL ADD COLUMN $FLD tinyint(1) DEFAULT 0 COMMENT 'geo hash not home'"
        ;;
        altitude) # DECIMAL type TBL: Sensors, measurement tables
          $MYSQL -e "ALTER TABLE $TBL ADD COLUMN $FLD DECIMAL(7,2) DEFAULT NULL COMMENT 'geo meters above sea level'"
        ;;
        valid)    # measurements validation criteria, NULL in repair, 0 not valid, default validated
          # TBL: TTNtable
          $MYSQL -e "ALTER TABLE $TBL ADD COLUMN $FLD tinyint(1) DEFAULT 1 COMMENT 'dflt NNN_valid for measurements, if NULL then in repair, False invalid value'"
        ;;
        DBactive)    # collect TTN datagrams for this kit TBL: TTNtable
          $MYSQL -e "ALTER TABLE $TBL ADD COLUMN $FLD tinyint(1) DEFAULT 1 COMMENT 'Forward measurements to measurements DB'"
          if echo "${TBLCOLS}" | grep -q active
          then
            $MYSQL -e "UPDATE $TBL SET $FLD = active, datum = datum"
            $MYSQL -e "ALTER table $TBL DROP COLUMN active"
          fi
        ;;
        TTN_app) # add TTN app_id, default: 201082251971az TBL: TTNtable
          $MYSQL -e "ALTER TABLE $TBL ADD COLUMN $FLD varchar(32) DEFAULT '201082251971az' COMMENT 'TTN application ID'"
        ;;
        housenr) # house nr in street TBL: Sensors
          $MYSQL -e "ALTER TABLE $TBL ADD COLUMN $FLD varchar(6) DEFAULT NULL COMMENT 'house nr in street'"
          updateHouseNR $TBL
        ;;
        sensors) # installed sensors in meaurement kit TBL: Sensors
          $MYSQL -e "ALTER TABLE $TBL ADD COLUMN $FLD varchar(64) DEFAULT NULL COMMENT 'active sensor types in measurement row'"
        ;;
        *)
          echo -e "${RED}Undefined: how to add column $FLD TBL table $TBL ${NOCOLOR}" 1>&2
        ;;
        esac
      elif (( $VERBOSE > 0 ))
      then
        echo "Sensors table $TBL has already column $FLD defined!" 1>&2
      fi
    done
}

# only valid in NL/EU
function GetGEO() {
    local LONG=${1:-0} LAT=${2:-0} ALT=${3:-0} TMP

    if [ "$ALT" = 0 ] ; then ALT=NULL ; fi
    # do not use POINT():
    # MySQL uses POINT(lat,lon) e.g. POINT(51.42031,6.135564) for Grubbenvorst
    # others use POINT(lon,lat)!
    # next make sure coordinates column is formatted as "lat,lon,alt"
    # this correction can only be applied in Nld
    # do not update datum column
    case ${LAT/.*/} in
    5|6)
      # echo "location=POINT($LONG,$LAT), altitude=$ALT, coordinates='$LONG,$LAT,${ALT/NULL/0}'" 
      # swap longitude and latitude
      echo "geohash=CAST(ST_GEOHASH($LAT,$LONG,10) as NCHAR), altitude=$ALT, coordinates='$LAT,$LONG,${ALT/NULL/0}', datum = datum" 
    ;;
    5*|4*)
      # echo "location=POINT($LAT,$LONG), altitude=$ALT, coordinates='$LAT,$LONG,${ALT/NULL/0}'"
      echo "geohash=CAST(ST_GEOHASH($LONG,$LAT,10) as NCHAR), altitude=$ALT, coordinates='$LONG,$LAT,${ALT/NULL/0}', datum = datum"
    ;;
    *) echo "geohash=NULL, altitude=$ALT, coordinates='0,0,0'"
    ;;
    esac
}

# get list of sensor types last used in period last months of measurements
function LastUsedTypes() {
    local TBL=$1 LIST=$2
    declare -A TYPES DATES
    local ONE LAST_ONE TYPE
    declare -i LAST=0
    LIST=${LIST//,/ }
    LAST=$($MYSQL -e "SELECT MAX(UNIX_TIMESTAMP(datum)) FROM $TBL")
    if (( "LAST" = 0 )) ; then return ; fi # no measurements at all
    LAST=${LAST}-30*24*60*60    # only sensor types within last month of measurements
    for ONE in $LIST
    do
      LAST_ONE=$($MYSQL -e "SELECT MAX(UNIX_TIMESTAMP(datum)) FROM $TBL WHERE UNIX_TIMESTAMP(datum) >= $LAST AND sensors LIKE '%$ONE%'")
      if [ -z "$LAST_ONE" ] ; then continue ; fi
      TYPE=''
      case $ONE in
      PMS*|SPS*|SDS*)    # PM values
        TYPE=dust
      ;;
      BME*|DHT*|SHT*)    # temp, RH, pressure, VOC values
        TYPE=meteo
      ;;
      NEO*)              # location values, time
        TYPE=gps
      ;;
      ACCU*)             # energy level accu 
        TYPE=energy
      ;;
      WASPMOTE)          # meteo rain, wind, temp, RH
        TYPE=weather
      ;;
      *) echo -e "${RED}Unknown sensor type $ONE in table $TBL.${NOCOLOR}" >/dev/stderr
        TYPE=$ONE
      ;;
      esac
      if [ -z "${DATES[$TYPE]}" ] ; then DATES[$TYPE]=0 ; fi
      if (( ${DATES[$TYPE]} < $LAST_ONE ))
      then
        DATES[$TYPE]=$LAST_ONE ; TYPES[$TYPE]=$ONE
      fi
    done
    TYPE=''
    for ONE in ${!TYPES[*]}
    do
      TYPE+=",${TYPES[$ONE]}"
    done
    echo "${TYPE/,/}"
}

# search kits in Sensors to be updated
# make sure active kits have most recent datum
# change only rows where column geohash is undefined
function UpdateLocation() {
    local SRC=${1:-coordinates}
    case $SRC in
    coordinates)
      $MYSQL -e "SELECT CONCAT(UNIX_TIMESTAMP(id),'=',UNIX_TIMESTAMP(datum),'=',coordinates) FROM Sensors WHERE ISNULL(geohash) AND NOT ISNULL(coordinates) ORDER BY active, datum" | sed -e 's/,/ /g' -e 's/   */ /g' -e 's/ /@/g'
    ;;
    geohash) # correct coordionates column from geohash column
      $MYSQL -e "SELECT CONCAT(UNIX_TIMESTAMP(id),'=',UNIX_TIMESTAMP(datum),'=',CONCAT(ST_LongFromGeoHash(geohash),',',ST_LatFromGeoHash(geohash),',',(IF(ISNULL(altitude),0,altitude))) FROM Sensors WHERE ISNULL(geohash) AND NOT ISNULL(coordinates) ORDER BY datum" | sed -e 's/,/ /g' -e 's/   */ /g' -e 's/ /@/g'
    ;;
    esac
}

# get list of active measurement table names and sensor hardware from Sensors description table
# either all active kits with hardware description defined
# or project_serial (mysql like expression) measurements kits in database
# argument: project_serial kit(s), no argument: all active measurement kits
function GetTables() {
   local TBLS ONE TBL
   if [ "$1" = active ]
   then
     # only active kits are searched for
     $MYSQL -e "SELECT CONCAT(project,'_',serial,'@',description) FROM Sensors WHERE description like '%;hw: %' and active" | sed -e 's/MQTT.*;hw:/;hw:/' -e 's/x003/X003/' -e 's/,TIME//' -e 's/ proto//' -e 's/,LOPYNODE//' -e 's/NEO-6/NEO/' -e 's/NEO/NEO-6/' -e 's/;hw: //' -e 's/;.*//' -e 's/ENERGY/ACCU/' -e 's/,NEO-6//' -e 's/$/,NEO-6/' 2>/dev/null | sort | uniq
   elif [ "${1/*_*/_}" = _ ]
   then
    TBLS=''
    for ONE in $*
    do
      TBL=$($MYSQL -e "SELECT CONCAT(project,'_',serial) FROM Sensors WHERE project LIKE '${ONE/_*/}' AND serial LIKE '${ONE/*_/}'" | sort | uniq)
      if [ -z "$TBL" ]
      then
        echo -e "${RED}Unable to find table for project ${ONE/_*/}, serial ${ONE/*_/}${NOCOLOR}" >/dev/stderr
      else
        TBLS+="\n$TBL"
      fi
    done
    TBLS=$(echo -e "$TBLS" | sort | uniq)
    for ONE in $TBLS
    do
      if [ -z "${ONE/_*/}" -o -z "${ONE/*_/}" ] ; then continue ; fi
      # kit may be active or not. Last date entry is used.
      $MYSQL -e "SELECT CONCAT(project,'_',serial,'@',description) FROM Sensors WHERE project = '${ONE/_*/}' AND serial = '${ONE/*_/}' ORDER BY datum DESC LIMIT 1" | sed -e 's/MQTT.*;hw:/;hw:/' -e 's/x003/X003/' -e 's/,TIME//' -e 's/ proto//' -e 's/,LOPYNODE//' -e 's/NEO-6/NEO/' -e 's/NEO/NEO-6/' -e 's/;hw: //' -e 's/;.*//' -e 's/ENERGY/ACCU/' -e 's/,NEO-6//' -e 's/$/,NEO-6/' 2>/dev/null
    done
  fi
}

# check if sensor column in measurement table is present  and has a value in measurements
function CheckSensors() {
   local TBL=$1 IND=$2
   if ! $MYSQL -e "DESCRIBE ${TBL}" 2>/dev/null | grep -q ${IND}_valid
   then
      echo "0"
   else
      echo "1"
   fi
}

# get indicator sensor type. Guessing the sensor manufacturer from meaurement table
# return selector for getting measurement sensor type
function Indicator() {
   local IND="" TBL="$1"
   case "${2^^}" in
   PMS?003)  # Plantower serie
    if (( $(CheckSensors "$TBL" pm5_cnt) > 0 )) && (( $(CheckSensors "$TBL" pm1) > 0 ))
    then
      if (( $(CheckSensors "$TBL" pm4_cnt) > 0 ))
      then
        IND="COUNT(pm5_cnt)@NOT ISNULL(pm5_cnt) AND NOT ISNULL(pm1) AND ISNULL(pm4_cnt)"
      else
        IND="COUNT(pm5_cnt)@NOT ISNULL(pm5_cnt) AND NOT ISNULL(pm1)"
      fi
    fi
   ;;
   SPS*)     # Sensirion serie
    if (( $(CheckSensors "$TBL" pm4_cnt) > 0 )) && (( $(CheckSensors "$TBL" pm1) > 0 ))
    then
      if (( $(CheckSensors "$TBL" pm5_cnt) > 0 ))
      then
        IND="COUNT(pm4_cnt)@NOT ISNULL(pm4_cnt) AND ISNULL(pm5_cnt)"
      else
        IND="COUNT(pm4_cnt)@NOT ISNULL(pm4_cnt) AND NOT ISNULL(pm1)"
      fi
    fi
   ;;
   SDS0*)    # Nova serie
    IND=''
    if (( $(CheckSensors "$TBL" pm1) > 0 ))
    then IND="ISNULL(pm1) AND ISNULL(pm1_cnt) AND "
    fi
    if (( $(CheckSensors "$TBL" pm1_cnt) > 0 ))
    then IND+="ISNULL(pm1_cnt) AND "
    fi
    if (( $(CheckSensors "$TBL" pm25_cnt) > 0 ))
    then IND+="ISNULL(pm25_cnt) AND "
    fi
    if (( $(CheckSensors "$TBL" pm10) > 0 )) && (( $(CheckSensors "$TBL" pm25) > 0 ))
    then IND+="NOT ISNULL(pm10) AND NOT ISNULL(pm25)"
    fi
    IND="COUNT(PM10)@$IND"
   ;;
   NEO*)    # GPS NEO-6 serie
    if (( $(CheckSensors "$TBL" longitude) > 0 ))
    then IND="COUNT(longitude)@NOT ISNULL(longitude)"
    fi
   ;;
   BME680)  # Bosch meteo + VOC (gas and calculated AQI%)
    if (( $(CheckSensors "$TBL" gas) > 0 ))
    then
      IND="COUNT(aqi)+COUNT(temp)@(NOT ISNULL(gas) OR NOT ISNULL(aqi)) AND (NOT ISNULL(temp) OR NOT ISNULL(rv))"
    fi
   ;;
   BME280)  # Bosch meteo
    if (( $(CheckSensors "$TBL" gas) > 0 ))
    then
      IND="ISNULL(gas) AND ISNULL(aqi) AND "
    fi
    if (( $(CheckSensors "$TBL" luchtdruk) > 0 ))
    then
      IND+="NOT ISNULL(luchtdruk) AND (NOT ISNULL(temp) OR NOT ISNULL(rv))"
      IND="COUNT(luchtdruk)@$IND"
    else
      IND="" 
    fi
   ;;
   SHT*)   # Sensirion meteo serie or other simple meteo sensor type
    if (( $(CheckSensors "$TBL" gas) > 0 ))
    then
      IND="ISNULL(gas) AND ISNULL(aqi) AND "
    fi
    if (( $(CheckSensors "$TBL" luchtdruk) > 0 ))
    then
      IND+="ISNULL(luchtdruk) AND "
    fi
    if (( $(CheckSensors "$TBL" temp) > 0 ))
    then
      IND="(NOT ISNULL(temp) OR NOT ISNULL(rv))"
      IND+="COUNT(temp)+COUNT(rv)@$IND"
    else
      IND=""
    fi
   ;;
   ENERGY|ACCU)  # has solar/accu. To be changed to energy: accu, adapter, solar
    if (( $(CheckSensors "$TBL" accu) > 0 ))
    then
      IND="COUNT(accu)@NOT ISNULL(accu)"
    fi
   ;;
   # add weather: rain, wind
   WASPMOTE) # Libelium serie
    if (( $(CheckSensors "$TBL" prevrain) > 0 ))
    then
      IND="COUNT(wr)+COUNT(prevrain)@NOT ISNULL(ws) AND NOT ISNULL(wr)"
    fi
   ;;
   *)
    IND=""
   ;;
   esac
   echo "$IND"
}

# lossy update measurement kit table in DB with sensors typoes of that mement
# correct sensors/description column in measurement table and Sensors location info table
# no argument: all active kits, argument = project_serial kit(s)
function Upgrade_SensorTypes() {
   local TMP PROJ SER IND TYPES SENS CNT
   # local SENS1
   local S

   echo -e "${BOLD}Adding sensor types for every measurement in measurement table: ${*:-all active}${NOCOLOR}." >/dev/stderr
   for TMP in `GetTables ${*:-active}`
   do
     PROJ="${TMP/_*/}"
     SER="${TMP/*_/}" ; SER="${SER/@*/}"
     SENS="${TMP/*@/}"
     # SENS1="$SENS"
     if (( $VERBOSE > 0 ))
     then
        echo -e "${BLUE}Table ${PROJ}_${SER}: adding active sensor types for every measurement${NOCOLOR}" >/dev/stderr
     fi

     if (( $RESET > 0 )) && $MYSQL -e "DESCRIBE ${PROJ}_${SER}" | grep -q sensors
     then
       echo "Reset: clear column 'sensors' from table ${PROJ}_${SER} for all measurements." >/dev/stderr
       $MYSQL -e "UPDATE ${PROJ}_${SER} SET sensors = NULL WHERE NOT ISNULL(sensors)"
     else
       Add_Cols ${PROJ}_${SER} sensors   # make sure sensor types column exists
     fi

     # only one type of sensors is present in measurement table (subject to change)
     for S in PMSX003 SPS30 SDS011 BME680 BME280 SHT31 ACCU NEO-6 WASPMOTE
     do
       IND=$(Indicator ${PROJ}_${SER} "$S"); CNT=0
       if [ -n "$IND" ]
       then
         CNT=$($MYSQL -e "SELECT ${IND/@*/} FROM ${PROJ}_${SER} WHERE ${IND/*@/} AND (ISNULL(sensors) OR NOT sensors LIKE '%${S}%')" 2>/dev/null )
         if (( ${CNT:-0} > 0 ))
         then
           if (( $DEBUG > 0 ))
           then
            echo "Adding sensor type ${S} to $CNT rows in table ${PROJ}_${SER} with '${IND/*@/}'." >/dev/stderr
           elif (( $VERBOSE > 0 ))
           then
            echo "Adding sensor type ${S} to ca $CNT rows in table ${PROJ}_${SER}'." >/dev/stderr
           fi
           TYPES+="${S},"
         fi
         $MYSQL -e "UPDATE ${PROJ}_${SER} SET sensors = IF(ISNULL(sensors),'${S},',CONCAT(sensors,'${S},')), datum = datum WHERE ${IND/*@/} AND (ISNULL(sensors) OR NOT sensors LIKE '%${S}%')"
       fi
     done
     if [ -n "${TYPES}" ]   # found measurements rows for sensor types for this table
     then
       SENS="${SENS/[57]003/X003}"  # fix: only PMSX003 are configured in this case
       if [ -z "$SENS" ] ; then SENS="${TYPES/%,/}" ; fi
       for S in ${TYPES//,/ }
       do
        if [ -n "${SENS/*$S*/}" ]
        then
            SENS+=",${S}"
        fi
       done
       SENS="${SENS/#,/}"
     fi
     if [ -n "$SENS" ]  # [ "$SENS" != "$SENS1" ]
     then
       if (( $VERBOSE > 0 ))
       then
         echo -e "${BLUE}Table ${PROJ}_${SER} has sensor types${NOCOLOR}: ${SENS}." >/dev/stderr
       fi
       # delete hardware sensors from description
       S=$($MYSQL -e "SELECT description FROM Sensors WHERE project = '${PROJ}' AND serial = '${SER}' AND active ORDER BY datum DESC LIMIT 1" | sed -e 's/;hw:[^;]*//')
       SENS=$(LastUsedTypes ${PROJ}_${SER} $SENS)
       if (( $VERBOSE > 0 ))
       then
         echo "Deleting ;hw: part in column 'description': value now is '$S'" >/dev/stderr
         echo -e "Updating table ${BLUE}Sensors${NOCOLOR} active/last date entry of project ${PROJ} with serial ${SER} with last known sensors:\n\t'${BLUE}${SENS}${NOCOLOR}'." >/dev/stderr
       fi
       # only on active or last time used
       $MYSQL -e "UPDATE Sensors SET sensors = '$SENS', description = '${S}', datum = datum WHERE project = '${PROJ}' AND serial = '${SER}' ORDER BY active DESC, datum DESC LIMIT 1"
     fi
   done
}

# output SQL to stdout
function Update2SQL(){
    local ID=$1 DATE=$2 COORD=$3
    local GEO=$(GetGEO ${COORD//@/ })
    if (( $VERBOSE > 0 ))
    then
      echo -n "ID=$(date --date=@$ID '+%Y/%m/%d %H:%M:%S') datum=$(date --date=@$DATE '+%Y/%m/%d %H:%M:%S') coordinate=${COORD//@/,}" 1>&2
      echo "-> $GEO" 1>&2
    fi
    echo "UPDATE Sensors SET $GEO WHERE UNIX_TIMESTAMP(id) = $ID;"
}

# install new $DB database on localhost
function InstallDB() {
   echo -e "${BOLD}Installing (restoring) $DB from host ${1:-${SOURCE_DB}}${NOCOLOR}" >/dev/stderr
   if echo "mysql -u $DBUSER -p"$DBPASS" -h $DBHOST -e 'CREATE DATABASE IF NOT EXISTS $DB'"
   then
     echo "mysqldump -u "$DBUSER" -p"$DBPASS" -h ${1:-${SOURCE_DB}} $DB | $MYSQL"
   fi
   exit 0
}

function DelCoord() {
  local TBL GEO ONCE=''
  echo -e "${BOLD}Converting and deleting coordinates column in measurement table: ${*:-all active}${NOCOLOR}" >/dev/stderr
  echo "Alter table SQL on stdout:" >/dev/stderr
  if ! $MYSQL -e "DESCRIBE Sensors" | grep -q 'geohash'
  then
    echo "Unable to find geohash source column in Sensors table" >/dev/stderr
    exit 1
  fi
  for TBL in $(GetTables ${*:-active})
  do
    TBL="${TBL/@*/}"
    if ! $MYSQL -e "DESCRIBE $TBL" | grep -q longitude_valid
    then continue
    fi
    Add_Cols $TBL geohash geohash_valid
    if ! $MYSQL -e "UPDATE $TBL SET geohash = CAST(ST_GEOHASH(longitude,latitude,10) as NCHAR), geohash_valid = 1, datum = datum WHERE longitude > 0 AND latitude > 0"
    then
      echo -e "${RED}Failed to update geohash measurements for table $TBL${NOCOLOR}" >/dev/stderr
      continue
    fi
    GEO=''
    if $MYSQL -e "DESCRIBE Sensors" | grep -q geohash
    then
      GEO=$($MYSQL -e "SELECT IF(ISNULL(geohash),'',geohash) FROM Sensors WHERE project = '${TBL/_*/}' AND serial = '${TBL/*_/}' order by active DESC LIMIT 1")
    fi
    if [ -z "$GEO" ]
    then
      if $MYSQL -e "DESCRIBE Sensors" | grep -q coordinates
      then
        GEO=$($MYSQL -e "SELECT IF(ISNULL(coordinates),'',coordinates) FROM Sensors WHERE project = '${TBL/_*/}' AND serial = '${TBL/*_/}' order by active DESC LIMIT 1")
        GEO="${GEO/*,0,*/}"; GEO=${GEO//,/ }
        if [ -n "$GEO" ]
        then
            GEO=$(GetGEO $GEO); GEO=${GEO/)*/)}
            if [ -n "$GEO" ]
            then
                GEO=$($MYSQL -e "SELECT $GEO")
            fi
        fi
      fi
    fi
    if [ -z "$GEO" ] ; then confinue ; fi
    if (( $VERBOSE > 0 ))
    then
      echo -e "${BLUE}Update table $TBL geohash valids and drop column 'coordinates'.${NOCOLOR}" >/dev/stderr
    fi
    #  geohash NULL (undefined), 1 (home location), 0 (mobile)
    if $MYSQL -e "UPDATE $TBL SET geohash_valid = IF(ISNULL(geohash),NULL,IF(SUBSTR(geohash,0,9) = SUBSTR('$GEO',0,9),1,0))"
    then
      if (( $VERBOSE > 0 ))
      then
        $MYSQL -e "SELECT CONCAT('Table $TBL with ', COUNT(datum), ' records, ',COUNT(geohash), ' geohash values') FROM $TBL" >/dev/stderr
        $MYSQL -e "SELECT CONCAT(' and ', COUNT(geohash), ' not at home records.') FROM $TBL WHERE NOT ISNULL(geohash_valid) AND NOT geohash_valid" >/dev/stderr
      fi
      # delete coordinates column from table
      echo 'LOCK TABLES `$TBL` WRITE;'
      echo "ALTER TABLE $TBL DROP COLUMN coordinates;"
      echo 'UNLOCK TABLES;'
    else
      echo -e "${RED}Failure on table $TBL while converting coordinates column to geohash.${NOCOLOR}" >/dev/stderr
    fi
  done
}

# delete unused columns from a measurement table
function CompressTable() {
   local TBL SENSORS SENS SQL TMP
   echo -e "${BOLD}Deleting unused sensors columns from table: ${*:-all active}${NOCOLOR}" >/dev/stderr
   for TBL in `GetTables ${*:-active}`
   do
     TBL="${TBL/@*/}"
     SENSORS=$($MYSQL -e "DESCRIBE $TBL" | grep _valid | sed -e 's/_valid.*//' )
     if [ -z "$SENSORS" ] ; then continue ; fi
     SQL=''
     for TMP in $SENSORS
     do
        # if [ -z "${TMP// /}" ] ; then continue ; fi
        if [ -n "$SQL" ] ; then SQL+=", " ; fi
        SQL+="IF(COUNT($TMP) = 0,'$TMP ','')"
     done
     SENSORS=$($MYSQL -e "SELECT ${SQL/%,/} FROM $TBL")
     SQL=''
     for TMP in $SENSORS
     do
        if [ -n "$SQL" ]
        then
          SQL+=", "
        elif (( $VERBOSE > 0 ))
        then
            echo -e -n "${BLUE}Table $TBL drop columns${NOCOLOR}:" >/dev/stderr
        fi
        SQL+="DROP COLUMN $TMP, DROP COLUMN ${TMP}_valid"
        if (( $VERBOSE > 0 )) ; then echo -n " $TMP ${TMP}_valid" >/dev/stderr ; fi
     done
     if [ -z "${SQL}" ]
     then
       if (( $VERBOSE > 0 ))
       then
         echo -e "${BLUE}Table $TBL is clean.${NOCOLOR}" >/dev/stderr
       fi
       continue
     fi
     if (( $VERBOSE > 0 )) ; then echo >/dev/stderr ; fi
     SQL="ALTER TABLE $TBL $SQL"
     if (( $DEBUG > 0 )) ; then echo "$SQL" >/dev/stderr ; fi
     $MYSQL -e "$SQL"
   done
}

function DoMYSQL() {
   local FILE=$1
   local MSG="$2"
   local ANS=''
   if [ -s "$FILE" ] ; then return ; fi
   read -p "$RED}Are you sure to $MSG?${NOCOLOR} yes|[NO]" -t 30 ANS
   if [ x"$ANS" = yes ]
   then
    cat $FILE | $MYSQL
   fi
}

# add geohash columns altitude and housenr to Sensors, DBactive, TTN_app to TTNtable
# update Sensors with geohash, leave coordinates column as is.
function AddGeoHash() {
    echo -e "${BOLD}Upgrade from coordinate to geohash in Sensors and TTNtable.${NOCOLOR}" >/dev/stderr
    # generate SQL for upgrade from coordinates to geohash columns
    # deprecate coordinates, update 'street nr' to 'street' and 'nr'
    Add_Cols Sensors geohash altitude housenr    # alter Sensors table for geo fields
    # deprecate active in TTNtable
    Add_Cols TTNtable valid DBactive TTN_app    # alter TTNtable for measurement DB & TTN entries
  
    # upgrade for using geohash in TTNtable and Sensors
    # and generate SQL for each kit found to be updated
    echo -e "${BOLD}Update SQL on stdout.${NOCOLOR}" >/dev/stderr
    echo 'LOCK TABLES `Sensors` WRITE;'
    for KIT in $(UpdateLocation coordinates)
    do
      Update2SQL ${KIT//=/ }
    done
}

# add SensorTypes DB table
# convert deprecated Conf['sensors'] python dict to DB table
function SensorTypesTbl() {
    #   cat <<EOF | python
    cat <<EOF | python | $MYSQL
calibrations = {
    # taken from regression report 11 Feb 2021, Vredepeel period June-Sept 2020 (ca 9.000 samples)
    # group: dust
    'SDS011': { 'pm10': { 'SPS30': [1.689,0.63223],'PMSx003': [3.76,1.157], 'BAM1020':[1.437,0.4130],},
                'pm25': { 'SPS30': [2.163,0.7645], 'PMSx003': [1.619,1.545],'BAM1020':[5.759,0.3769],},
              },
    'SPS30':  { 'pm10': { 'PMSx003': [2.397,1.666], 'SDS011':[-1.689,1/0.63223],'BAM1020': [13.13,0.6438],},
                'pm25': { 'PMSx003': [-1.099,1.835],'SDS011':[-2.163,1/0.7645], 'BAM1020': [4.255,0.5371],},
              },
    'PMSx003': { 'pm10': { 'SDS011':[-3.76,1/1.157],'SPS30':[-2.397,1/1.666],'BAM1020': [13.69,0.2603],},
                 'pm25': { 'SDS011':[-1.619,1/1.545],'SPS30':[1.099,1/1.835],'BAM1020': [4.786,0.2599],},
              },
     }
     
Sensors =  [
            {  "type":"SDS011",
                "producer":"Nova","group":"dust",
                "fields":["pm25","pm10"],
                "units":["ug/m3","ug/m3"],
                "calibrations": [{ 'SPS30': [2.163,0.7645], 'PMSx003': [1.619,1.545],'BAM1020':[5.759,0.3769],},{ 'SPS30': [1.689,0.63223],'PMSx003': [3.76,1.157], 'BAM1020':[1.437,0.4130],},],
            },
            # Sensirion standard ug/m3 measurements
            {  "type":"SPS30",
                "producer":"Sensirion","group":"dust",
                "fields":["pm1","pm25","pm10","pm05_cnt","pm1_cnt","pm25_cnt","pm4_cnt","pm10_cnt","grain"],
                "units":["ug/m3","ug/m3","ug/m3","pcs/cm3","pcs/cm3","pcs/cm3","pcs/cm3","pcs/cm3","um"],
                "calibrations": [None,{ 'PMSx003': [-1.099,1.835],'SDS011':[-2.163,1/0.7645], 'BAM1020': [4.255,0.5371],},{ 'PMSx003': [2.397,1.666], 'SDS011':[-1.689,1/0.63223],'BAM1020': [13.13,0.6438],},],
            },
            # Plantower standard ug/m3 measurements
            {  "type":"PMSx003",
                "producer":"Plantower","group":"dust",
                "fields":["pm1","pm25","pm10","pm03_cnt","pm05_cnt","pm1_cnt","pm25_cnt","pm5_cnt","pm10_cnt","grain"],
                "units":["ug/m3","ug/m3","ug/m3","pcs/dm3","pcs/dm3","pcs/dm3","pcs/dm3","pcs/dm3","pcs/dm3","um"],
                "calibrations": [{ 'SDS011':[-1.619,1/1.545],'SPS30':[1.099,1/1.835],'BAM1020': [-4.786,1/0.2599],},{ 'SDS011':[-1.619,1/1.545],'SPS30':[1.099,1/1.835],'BAM1020': [-4.786,1/0.2599],},{ 'SDS011':[-3.760,1/1.157],'SPS30':[-2.397,1/1.666],'BAM1020': [-13.69,1/0.2603],},],
            },
            {  "type":"PMS7003",
                "producer":"Plantower","group":"dust",
                "fields":["pm1","pm25","pm10","pm03_cnt","pm05_cnt","pm1_cnt","pm25_cnt","pm5_cnt","pm10_cnt","grain"],
                "units":["ug/m3","ug/m3","ug/m3","pcs/dm3","pcs/dm3","pcs/dm3","pcs/dm3","pcs/dm3","pcs/dm3","um"],
                # taken similar as PMSx003
                "calibrations": [{ 'SDS011':[-1.619,1/1.545],'SPS30':[1.099,1/1.835],'BAM1020': [-4.786,1/0.2599],},{ 'SDS011':[-1.619,1/1.545],'SPS30':[1.099,1/1.835],'BAM1020': [-4.786,1/0.2599],},{ 'SDS011':[-3.760,1/1.157],'SPS30':[-2.397,1/1.666],'BAM1020': [-13.69,1/0.2603],},],
            },
            {  "type":"PMS5003",
                "producer":"Plantower","group":"dust",
                "fields":["pm1","pm25","pm10","pm03_cnt","pm05_cnt","pm1_cnt","pm25_cnt","pm5_cnt","pm10_cnt","grain"],
                "units":["ug/m3","ug/m3","ug/m3","pcs/dm3","pcs/dm3","pcs/dm3","pcs/dm3","pcs/dm3","pcs/dm3","um"],
                # taken similar as PMSx003
                "calibrations": [{ 'SDS011':[-1.619,1/1.545],'SPS30':[1.099,1/1.835],'BAM1020': [-4.786,1/0.2599],},{ 'SDS011':[-1.619,1/1.545],'SPS30':[1.099,1/1.835],'BAM1020': [-4.786,1/0.2599],},{ 'SDS011':[-3.760,1/1.157],'SPS30':[-2.397,1/1.666],'BAM1020': [-13.69,1/0.2603],},],
            },
            # Plantower the count particulates measurements
            {  "type":"PMS7003_PCS",
                "producer":"Plantower","group":"dust",
                "fields":["pm03_pcs","pm05_pcs","pm1_pcs","pm25_pcs","pm5_pcs","pm10_pcs","grain"],
                "units":["pcs/0.1dm3","pcs/0.1dm3","pcs/0.1dm3","pcs/0.1dm3","pcs/0.1dm3","pcs/0.1dm3","um"],
                "calibrations": [[0,1.0],[0,1.0],[0,1.0],[0,1.0],[0,1.0],[0,1.0],None]},
            {  "type": "PPD42NS",
                "producer":"Shiney","group":"dust",
                "fields":["pm25","pm10"],
                "units":["pcs/0.01qft","pcs/0.01qft"],
                "calibrations": [[0,1.0],[0,1.0]]},
            {  "type": "DC1100 PRO",
                "producer":"Dylos","group":"dust",
                "fields":["pm25","pm10"],
                "units":["pcs/0.01qft","pcs/0.01qft"],
                "calibrations": [[0,1.0],[0,1.0]]},
            {  "type": "DHT11",
                "producer":"Adafruit","group":"meteo",
                "fields":["temp","rv"],"units":["C","%"],
                "calibrations": [[0,1.0],[0,1.0]]},
            {  "type": "DHT22",
                "producer":"Adafruit","group":"meteo",
                "fields":["temp","rv"],"units":["C","%"],
                "calibrations": [[0,1.0],[0,1.0]]},
            {  "type": "BME280",
                "producer":"Bosch","group":"meteo",
                "fields":["temp","rv","luchtdruk"],
                "units":["C","%","hPa"],
                "calibrations": [[0,1.0],[0,1.0],[0,1.0]]},
            {  "type": "BME680",
                "producer":"Bosch","group":"meteo",
                "fields":["temp","rv","luchtdruk","gas", "aqi"],
                "units":["C","%","hPa","kOhm","%"],
                "calibrations": [[0,1],[0,1],[0,1],[0,1],[0,1]]},
            {  "type": "SHT31",
                "producer":"Sensirion","group":"meteo",
                "fields":["temp","rv"],
                "units":["C","%"],
                "calibrations": [[0,1],[0,1]]},
            {  "type": "SHT85",
                "producer":"Sensirion","group":"meteo",
                "fields":["temp","rv"],
                "units":["C","%"],
                "calibrations": [[0,1],[0,1]]},
            {  "type": "HYT221",
                "producer":"IST AG","group":"meteo",
                "fields":["temp","rv"],
                "units":["C","%"],
                "calibrations": [[0,1],[0,1]]},
            #{  "type": "TTN node",
            #    "producer":"TTN","group":"LoRa",
            #    "fields":["accu","light","temp"],
            #    "units":["mV","lux","C"],
            #    "calibrations": [[0,1.0],[0,1.0],[0,1.0]]},
            {  "type": "TTN event",
                "producer":"TTN","group":"LoRa",
                "fields":["event","value"],
                "units": ["id"],"calibrations": None},
            {  "type": "NEO-6",
                "producer":"NEO","group":"location",
                "fields":["geohash","altitude"],
                "units": ["geohash","m"],
                "calibrations": [[0,1],[0,1],[0,1],None]},
            {  "type": "PYCOM",
                "producer": "ESP", "group":"controller",
                "fields":["time"], "units":["sec"],"calibrations":[None]},
            {  "type": "MySense",
                "producer": "BdP", "group": "IoS",
                "fields": ["version","meteo","dust"],
                "units": ["nr","type","type"],
                "calibrations": None},
            # not yet activated
            { "type":"ToDo",
                "producer":"Spect", "group":"gas",
                "fields":["NO2","CO2","O3","NH3"],
                "units":["ppm","ppm","ppm","ppm"],
                "calibrations": [[0,1.0],[0,1.0],[0,1.0],[0,1.0]]},
            { "type": "energy",  # accu level status with solar panel
                "producer":"accu", "group":"energy",
                "fields":["accu"], "units": ["%"],"calibrations":[None]},
            { "type": "WASPMOTE", # deprecated Nov 2020
              "producer":"Libelium", "group":"weather",
              "fields":["accu","temp","rv","luchtdruk","rain","prevrain","dayrain","wr","ws"],
              "units":["%","C","%","hPa","mm","mm","mm","degrees","m/sec"],
              "calibrations":[[0,1],[0,1],[0,1],[0,1],[0,1],[0,1],[0,1],[0,1],[0,1]]},
            { "type": "WASPrain",
              "producer": "Libelium", "group": "rain",
              "fields":["rain","prevrain","dayrain"],
              "units":["mm/h","mm/h","mm/24h"],
              "calibrations":[[0,1],[0,1],[0,1]]},
            { "type": "WASPwind",
              "producer": "Libelium", "group": "wind",
              "fields":["wr","ws"],
              "units":["degrees","m/sec"],
              "calibrations":[[0,1],[0,1]]},

            # XYZDIY1 # Jos Wittebrood
           {  "type": "DIY1", # non mechanical wind measurement unit
              "producer": "Jos", "group": "weather",
              "fields": ["rain","wr","ws","accu"],
              "units": ["mm/h","degrees","m/sec","V"],
              "calibrations": [[0,1],[0,1],[0,1],[0,1]]},
           {  "type": "RainCounter", # mechanical rain measurement wip/wap unit
              "producer": "unknown", "group": "rain",
              "fields": ["rain"],
              "units": ["mm/h"],
              "calibrations": [[0,1]]},
           {  "type": "windDIY1", # non mechanical wind measurement unit
              "producer": "WindSonic", "group": "wind",
              "fields": ["wr","ws"],
              "units": ["degrees","m/sec"],
              "calibrations": [[0,1],[0,1]]},
           {  "type": "Argent", # mechanical wind measurement unit
              "producer": "Argentdata", "group": "wind",
              "fields": ["wr","ws"],
              "units": ["degrees","m/sec"],
              "calibrations": [[0,1],[0,1],[0,1]]},
           {  "type": "Ultrasonic", # non mechanical wind measurement unit
              "producer": "Darrera", "group": "wind",
              "fields": ["wr","ws"],
              "units": ["degrees","m/sec"],
              "calibrations": [[0,1],[0,1]]}
        ]
#    (type,producer,group,fields) VALUE ('SDS011','Nova','dust','pm1,ug/m3,NULL or 0/1.0;...')
import sys
print("""
CREATE TABLE IF NOT EXISTS SensorTypes (
    id datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'date/time row creation',
    datum timestamp DEFAULT CURRENT_TIMESTAMP COMMENT 'date/time on row update',
    product varchar(16) DEFAULT NULL COMMENT 'sensor product name',
    matching varchar(16) DEFAULT NULL COMMENT 'sensor product name in wild card',
    producer varchar(16) DEFAULT NULL COMMENT 'sensor manufacturer name',
    category varchar(16) DEFAULT NULL COMMENT 'sensor category type: dust, meteo, energy, wind, ...',
    fields varchar(512) DEFAULT NULL COMMENT 'e.g. DB column name 1,unit,calibration;name 2,unit;name3...',
    UNIQUE type_id (product)
    ) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='TTN info input table, output';""")

import re
count = 0
for one in Sensors:
  if not 'calibrations' in one.keys() or not type(one['calibrations']) is list:
    continue
  for item in 'type','producer','group','fields':
    if not item in one.keys(): one[item] = 'NULL'
  if not type(one[item]) is list and one[item] != 'NULL': one[item] = [one[item]]
  fields = []
  for i in range(len(one['fields'])):
    field = [one['fields'][i]]
    cal = []; unit = None
    try:
      # maybe serialize this via json?
      if type(one['calibrations'][i]) is dict:
        for sensor in one['calibrations'][i].keys():
          try:
            if float(one['calibrations'][i][sensor][1]) != float(1): # use second 
              cal.append('%s/%.4f/%.4f' % (sensor,one['calibrations'][i][sensor][0],one['calibrations'][i][sensor][1]))
          except:
            sys.stderr.write("Error in calibration for %s: %s\n" % (one['type'],str(one['calibrations'][i][sensor])) )
            continue
    except: pass
    try: unit = one['units'][i]
    except: pass
    field.append(unit if unit else '')
    if cal: field.append('|'.join(cal))
    fields.append(','.join(field))
  if not count:
    print("REPLACE INTO SensorTypes (product,matching,producer,category,fields) VALUES")
  if re.compile(r'DHT(11|22)',re.I).match(one['type']): one['matching'] = 'DHT(11|22)'
  elif re.compile(r'PMS.003',re.I).match(one['type']): one['matching'] = 'PMS[57X]003'
  elif re.compile(r'DC1100.*',re.I).match(one['type']): one['matching'] = 'DC1100.*'
  elif re.compile(r'SHT(21|31)',re.I).match(one['type']): one['matching'] = 'SHT[23]1'
  else: one['matching'] = one['type'].upper()
  print("%s('%s','%s','%s','%s','%s')" % (' ,' if count else '  ',one['type'],one['matching'],one['producer'],one['group'],';'.join(fields)))
  count += 1
EOF
}
# SensorTypesTbl

# 2021/03/16 database upgrades

#function main() {
    for ARG
    do
      case ${ARG} in
        VERBOSE|verbose) VERBOSE=1
        ;;
        DEBUG|debug) DEBUG=1; VERBOSE=1
        ;;
        RESET|reset) RESET=1
        ;;
        UPGRADE|upgrade)       ########## upgrade all in one swing
          echo "DB upgrading: reload DB from ${SOURCE_DB}, add geohash, delete coordinates column, add sensor types, delete unused measurement columns" >/dev/stderr
          start_progressing "Loading DB $DB. Takes 8 minutes..."
          InstallDB >/tmp/Upgrading$$  # copy DB $DB from ${SOURCE_DB}
             bash -x /tmp/Upgrading$$ "Install $DB DB from ${SOURCE_DB} to localhost"
          stop_progressing
          start_progressing "Add Geohash to Sensors and tables. Takes 1 minute ..."
          AddGeoHash >/tmp/Upgrading$$ # add geohash in meta info tables
             DoMYSQL /tmp/Upgrading$$ "GeoHash MYSQL table changes"
          stop_progressing
          start_progressing "Delete coordinates and update geohash for measurement kits. Takes 2 minutes..."
          DelCoord >/tmp/Upgrading$$   # delete deprecated coordinates from tables
             DoMYSQL /tmp/Upgrading$$ "Coordinate columns deletions MYSQL table"
          stop_progressing
          start_progressing "Add sensor types to measurement tables. Can take 10 minutes..."
          Upgrade_SensorTypes          # add sensor types on measurements, update Sensors
          start_progressing "Delete unsued sensors from measurement kits. Takes 5 minutes..."
          CompressTable                # drop unused measurement columns
          stop_progressing
          rm -f /tmp/Upgrading$$
          start_progressing "Install and/or update SensorTypes DB table with sensor type information. Takes 30 seconds..."
          SensorTypesTbl
          stop_progressing
        ;;
        InstallDB|installDB)
          shift
          InstallDB ${1:-${SOURCE_DB}}
          exit 0
        ;;
        [aA]dd[psS]ensor[tT]ype*)
          # add sensor type(s) on each measurement in measurement tables
          if [ -n "$2" -a -z "${2/*_*/}" ]
          then
            while [ "This${2/*_*/Kit}" = ThisKit ]
            do
              Upgrade_SensorTypes $2  # args: project_serial measurement table
              shift
            done
          else
            Upgrade_SensorTypes # all active measurements tables
          fi
        ;;
        [aA]dd[gG]eo[hH]ash)
          AddGeoHash
        ;;
        [dD]el[Cc]oord*)
          if [ -n "$2" -a -z "${2/*_*/}" ]
          then
            while [ "This${2/*_*/Kit}" = ThisKit ]
            do
              DelCoord $2  # args: project_serial measurement table
              shift
            done
          else
            DelCoord # all active measurements tables
          fi
        ;;
        [Cc]ompress[Tt]able*)
          if [ -n "$2" -a -z "${2/*_*/}" ]
          then
            while [ "This${2/*_*/Kit}" = ThisKit ]
            do
              CompressTable $2  # args: project_serial measurement table
              shift
            done
          else
            CompressTable # all active measurements tables
          fi
        ;;
        [Ss]ensor*[Tt]ypes*)
          start_progressing "Install and/or update SensorTypes DB table with sensor type infoprmation. Takes 30 seconds..."
          SensorTypesTbl
          stop_progressing
        ;;
        *_*)
          continue # skip measurement table arguments
        ;;
        help|HELP|-h|--[hH]*)
          cat  >/dev/stderr <<EOF
        DO NOT USE THIS SCRIPT ON LIFE LUCHTMETINGEN DB (upgrading on same host as operational DB).
        Make sure there is a dump file available.

        Upgrade MySQL database with measurement kit info and measurements.
        Script will output MySQL statements to drop coordinate(s) use in tables on stdout.
        If argument (table name(s)) to selected change function is omitted all active tables are done.

        Optional settings:
          verbose:       verbose modus (from environment VERBOSE=1).
          debug:         more verbose modus (from enironment DEBUG=1).
          reset:         drop column 'sensors' from measurement table first (redo AddSensorTypes).

        Optional functions:
          upgrade:       install DB on localhost, upgrade geohash, sensortypes, cleanup tables.
                         This can take a while, ca 1 hour.

          AddGeohash:    upgrade Sensors and TTNtable for using geohash.
          DelCoordinates [project_serial ...] convert coordinates column measurements kit table to geohash.
          InstallDB [dbhost]: install from dbhost (dflt ${SOURCE_DB}) $DB database on DBHOST.
          AddSensorTypes [project_serial ...] add sensor types on each measurement, no arg: all active tables.
          CompressTable  [project_serial ...] drop all unused sensor columns from measurement table.
          SensorTypes    Install or update SensorTypes DB table with sensor type information.
EOF
        ;;
        *) echo -e "${RED}Undefined upgrade function ${ARG}${NOCOLOR}. Skipped." >/dev/stderr
        ;;
       esac
       shift
    done
#}

#main $*
