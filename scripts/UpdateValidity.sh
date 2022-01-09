#!/bin/bash
DB=${DB:-luchtmetingen}
DBHOST=${DBHOST:-localhost}
RDBHOST=${RDBHOST}   # host with TTN V2 measurements DB
MYSQL="mysql --login-path=$DB -N -B --silent -h $DBHOST $DB"

# $Id: UpdateValidity.sh,v 1.4 2022/01/09 15:35:37 teus Exp teus $
# script to invalidate measurements if kit is not at home location

ACTIVE=()  # active measurement kits
KITS=()    # list of measurement tables

# get list of measurement tables
function GetTables() {
   local TBLS TMP ANS
   for TMP in $@
   do
     for TBL in $($MYSQL -e "SELECT CONCAT(project,'_',serial) FROM Sensors" | sort | uniq | grep -P "$TMP")
     do
       if ! $MYSQL -e "SHOW TABLES" | grep -q $TBL
       then
         echo "Table $TMP not not in database. Skipped." 1>&2
       else
         KITS+=($TBL)
       fi
     done
     for TBL in $($MYSQL -e "SELECT CONCAT(project,'_',serial) FROM Sensors WHERE active" | grep -P "$TMP")
     do
       if echo "${KITS[@]}" | grep -q $TMP
       then
         ACTIVE+=($TBL)
       fi
     done
   done
   if [ -n "$@" ] ; then return ; fi
   declare -a TBL
   TBL=$($MYSQL -e 'SHOW tables like "%_%"' | grep -P '[A-Za-z]{3,}_[A-Za-z0-9]{6,}')
   TBLS=$($MYSQL -e 'SELECT CONCAT(project,"_",serial) FROM Sensors' | sort | uniq)
   for TMP in ${TBL}
   do
     if echo "${TBLS}" | grep -q "$TMP"
     then
       KITS+=($TMP)
     else
       echo "Table $TMP not in Sensors" 1>&2
       read -p "Drop this table $TMP? no|[yes] " ANS
       if [ "${ANS:-yes}"  = yes ]
       then
          if $MYSQL -e "DROP TABLE $TMP" ; then echo "Table $TMP removed" ; fi
       fi
     fi
   done
   TBL=$($MYSQL -e 'SELECT CONCAT(project,"_",serial) FROM Sensors WHERE active' )
   for TMP in ${KITS[@]}
   do
     if echo "${TBLS}" | grep -q "$TMP"
     then
       ACTIVE+=($TMP)
     else
       echo "Measurement table $TMP is inactive" 1>&2
       echo -n $($MYSQL -e "SELECT count(*) FROM $TMP") "measurements " 1>&2
       echo -n "from " $($MYSQL -e "SELECT datum FROM $TMP ORDER BY datum LIMIT 1") 1>&2
       echo " to " $($MYSQL -e "SELECT datum FROM $TMP ORDER BY datum DESC LIMIT 1") 1>&2
       read -p "Drop this table $TMP? no|[yes] " ANS
       if [ "${ANS:-yes}"  = yes ]
       then
          if $MYSQL -e "DROP TABLE $TMP" ; then echo "Table $TMP removed" ; fi
       fi
     fi
   done
}

# use end date from TTN V2 measurements database
# if not defined use FROM Posix seconds timestamp from environment FROM
function StartTime(){
   local RTS='' TBL=$1
   if [ -n "$RDBHOST" ]
   then
      RTS=$(${MYSQL/$DBHOST/$RDBHOST} -e "SELECT UNIX_TIMESTAMP(datum) FROM ${TBL} ORDER BY datum DESC LIMIT 1")
   else
      if ! echo "$FROM" | grep -q -P '^[0-9]{8}$'        
      then
         RTS=$(date --date="${FROM}" +%s)
         if ! $?
         then
           RTS=''
         fi
       fi
   fi
   echo $RTS
}

# returns from a timestamp the date returning to home location.
# if undefined kit mis now not at home location
# st_distance_sphere(point(51.4823,6.08252),point(51.4204702,6.135521))
function LastLocs() {
   local TBL=$1 FROM=$2
   local DISTdate=''
   if ! $MYSQL -e "DESCRIBE $TBL" | grep -q -P '^geohash.*varchar' 
   then
     echo "WARNING table $TBL has no geo locations column" 1>&2
     echo $FROM
     #$MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM $TBL ORDER BY datum DESC LIMIT 1"
     return 1
   fi
   local Distance='python3 lib/MyGPS.py --distance'
   if [ ! -f lib/MyGPS.py ]
   then 
     echo 'unable to locate python script lib/MyGPS.py' 1>&2
     return 1
   fi
   if [ -z "$FROM" ]
   then
     FROM=$(StartTime $TBL)
     if [ -z "$FROM" ] ; then return 1 ; fi
   fi
   local HLOC=''
   # MySQL Point expects as args: Point(long,lat): HLOC gives "Point(long,lat)"
   HLOC=$($MYSQL -e "SELECT CONCAT('Point(',ST_LongFromGeoHash(geohash),',',ST_LatFromGeoHash(geohash),')') FROM Sensors WHERE project = '${TBL/_*/}' AND serial = '${TBL/*_/}' AND NOT ISNULL(geohash) ORDER BY active DESC, datum DESC LIMIT 1")
   if [ -z "$HLOC" ] ; then return 0 ; fi
   declare -i BACK=$(date --date=tomorrow +%s ) T
   DISTdate=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM $TBL WHERE UNIX_TIMESTAMP(datum) > $FROM AND NOT ISNULL(geohash) AND ST_Distance_Sphere($HLOC,Point(ST_LongFromGeoHash(geohash),ST_LatFromGeoHash(geohash)))> 118 ORDER BY datum DESC LIMIT 1")
   if [ -z "$DISTdate" ] ; then DISTdate=$FROM ; fi
   local LASTdate=''
   LASTdate=$($MYSQL -e "SELECT UNIX_TIMESTAMP(datum) FROM $TBL WHERE UNIX_TIMESTAMP(datum) > $DISTdate AND NOT ISNULL(geohash) AND ST_Distance_Sphere(${HLOC},Point(ST_LongFromGeoHash(geohash),ST_LatFromGeoHash(geohash))) <= 118 ORDER BY datum LIMIT 1")
   # if [ -z "LASTdate" ] ; then LASTdate=$(date +%s) ; fi
   echo $LASTdate
   return 0
}

# get the columns to invalidate
function Valid_Cols() {
   local TBL=$1
   local COLS
   COLS=$($MYSQL -e "DESCRIBE $TBL" | awk '{ print $1; }' | grep -P '(pm|grain|temp|rv|luchtdruk|gas|aqi).*_valid$' | sed 's/$/=NULL/')
   echo $COLS | sed 's/ /,/g'
}

# invalidate measurements in a period of time
function InvalidateVals() {
  if ! $MYSQL -e 'SHOW TABLES' | grep -q "$TBL" ; then return 0 ; fi
  local TBL=$1 FROM=$2 TO=$3 COLS
  if [ -z "$TO" ] ; then TO=$(date --date=tomorrow +%s) ; fi
  declare -i CNT=0
  CNT=$($MYSQL -e "SELECT COUNT(*) FROM $TBL WHERE UNIX_TIMESTAMP(datum) > $FROM AND UNIX_TIMESTAMP(datum) < $TO")
  # echo "Invalid settings are disabled" 1>&2
  # return )0
  if (( $CNT > 0 ))
  then
    echo "Invalidate $CNT measurements table $TBL from $(date --date=@$FROM +'%y-%m-%d %H:%M') up to $(date --date=@$TO +'%y-%m-%d %H:%M')" 1>&2
    COLS=$(Valid_Cols $TBL )
    if [ -z "$COLS" ] ; then return 1 ; fi
  
    if ! $MYSQL -e "UPDATE $TBL SET $COLS WHERE UNIX_TIMESTAMP(datum) > $FROM AND UNIX_TIMESTAMP(datum) < $TO"
    then
      echo "ERROR invalidating measurements table $TBL" 1>&2
      return 1
    fi
  fi
  if (( $TO > $(date +%s) )) # handle default invalid setting for valid TTNtable column
  then
    echo "Measurements project ${TBL/_*/} serial ${TBL/*_/} is set to invalid (NULL) in TTNtable" 1>&2
    if ! $MYSQL -e "UPDATE TTNtable SET valid = NULL WHERE project = '${TBL/_*/}' and serial = '${TBL/*_/}'"
    then
      echo "ERROR set valid in TTNtable" 1>&2
      return 1
    fi
  fi 
}

# show kit info with operational status
# optional CSV output on arg2
ListKitHdr=''
function ListKit() {
  local OUTPUT=${2:-/dev/stdout}  # output in CSV format
  local STRT='' TO=''
  
  local TBL=$1 KITinfo="KIT project ${TBL/_*/} serial ${TBL/*_/}"
  ACT=true
  if echo ${ACTIVE[@]} | grep -q $TBL
  then
    echo "$KITinfo is ACTIVE" 1>&2
  elif echo ${KITS[@]} | grep -q $TBL
  then
    echo "$KITinfo is NOT ACTIVE" 1>&2
    ACT=false
    # return
  else
    echo "$KITinfo is UNKNOWN" 1>&2
    return
  fi
  if $MYSQL -e 'SHOW TABLES' | grep -q "$TBL"
  then   # only if measurements are there
    STRT=$(StartTime $TBL)
    if [ -n "$STRT" ]
    then
      TO=$(LastLocs $TBL $STRT)
    fi
  fi
  local STMP  # location info
  if [ -z "$ListKitHdr" ]
  then
     ListKitHdr='"project";"serial";"active"'
     ListKitHdr+=';"label";"street";"long";"lat";"geohash"'
     ListKitHdr+=';"TTN app";"TTN id";"validity"'
     ListKitHdr+=';"from date";"upto"'
     echo "$ListKitHdr" >>${OUTPUT}
  fi
  local QRY="SELECT CONCAT(';\"',if(ISNULL(label),'None',label),'\"',';\"',if(ISNULL(street),'None',street),'\"',';\"',if( not ISNULL(geohash),round(ST_LongFromGeoHash(geohash),6),'undefined'),'\"',';\"',if( not ISNULL(geohash),round(ST_LatFromGeoHash(geohash),6),'undefined'),'\"',';\"',if(not ISNULL(geohash),geohash,'undefined'),'\"' ) FROM Sensors WHERE project = '${TBL/_*/}' AND serial = '${TBL/*_/}' ORDER BY active DESC, datum DESC LIMIT 1"
  STMP=$($MYSQL -e "$QRY")
  if [ -z "$TO" ] ; then TO=$(date --date='tomorrow 00:00' +%s) ; fi
  local DTMP
  if [ "$STRT" = "$TO" ]
  then
    DTMP=";;\"$(date --date=@$TO +'%y-%m-%d %H:%M')\""
    STRT=''
  else
    DTMP=";\"$(date --date=@$STRT +'%y-%m-%d %H:%M')\";\"$(date --date=@$TO +'%y-%m-%d %H:%M')\""
  fi
  
  if [ -z "$STRT" ] ; then return ; fi  # nothing to invalidate
  if echo ${ACTIVE[@]} | grep $TBL
  then
     declare -i CNT
     CNT=$($MYSQL -e "SELECT COUNT(*) FROM $TBL WHERE UNIX_TIMESTAMP(datum) > $STRT AND UNIX_TIMESTAMP(datum) < $TO")
     if [ -n "$RDBHOST" ] ; then CNT+=1 ; fi  # make sure to invald valid in TTNtable
     if  (( $CNT > 0 ))
     then
       local ANS
       read -p "Invalidate $CNT measurements of table $TBL period $(date --date=@$STRT +'%y-%m-%d %H:%M') upto $(date --date=@$TO +'%y-%m-%d %H:%M')? no|[yes] " ANS
       if [ "${ANS:-yes}" = yes ]
       then
          InvalidateVals $TBL $STRT $TO
       else
          echo "$CNT measurements of table $TBL are not invalidated" 1>&2
       fi
     fi
  fi
  local TTMP  # TTN info
  QRY="SELECT CONCAT(';\"',if(ISNULL(TTN_app),'None',TTN_app),'\"',';\"',if(ISNULL(TTN_id),'None',TTN_id),'\"',';\"',if(ISNULL(valid),'None',if(valid,'true','false')),'\"') FROM TTNtable WHERE project = '${TBL/_*/}' AND serial = '${TBL/*_/}' LIMIT 1"
  TTMP=$($MYSQL -e "$QRY")
  echo "\"${TBL/_*/}\";\"${TBL/*_/}\";\"$ACT\"${STMP}${TTMP}${DTMP}" >>${OUTPUT}
}

#  main routine: OUTPUT defines CSV file iso std out for administrative info
#  arguments expression to identify measurements tables, dflt all kits in Sensors
#  and/or has measurmeents (measurement table).
#  measurement table is looked up in Sensors database table:
#  is it active, is measurement table existant
if [ -n  "$OUTPUT" ] ; then OUTPUT+='.csv' ; fi
ACTIVE=()  # active measurement kits
KITS=()    # list of measurement tables
# get list of measurement tables

GetTables  $@  # obtain list of kits: active, not active, has measurements

# give administrative info, drop unadminsitered measurement tables,
# update validity of measurements in measurements table and validity in TTNtable
# DB changes will only be done interactively ([yes]/no).
# RDBHOST will define host for the search of from which date search for validity
# will start.
# if not defined as environment the environment var FROM is used as start timestamp
# default (FROM is undefined): no validity check is done.
# FROM maybe Posix sec timestamp or date cmd date format (--date='string').
for TBL in ${KITS[@]}
do
   ListKit $TBL ${OUTPUT}
done
if [ -n "$OUTPUT" ] ; then echo "Info in CVS output on $OUTPUT" 1>&2 ; fi
