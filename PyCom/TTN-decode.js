/* $Revision: 1.2 $
 * Copyright 2018, Teus Hagen, GPL4
 * decode LoRa payload sent by MySense node
 * copy/paste this JavaScript into format area at TTN server
 */
/* test data
var tests = [
  {"port": 2,
  "payload": [0x00, 0x00, 0x00, 0x75, 0x00, 0x79, 0x01, 0x7E, 0x04, 0x3B, 0x04, 0x11, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
  "result": {
    "humidity": 108.3,
    "pm10": 12.1,
    "pm25": 11.7,
    "pressure": 1041,
    "temperature": 8.2
  }
},{
  "port": 2,
  "payload": [0x87, 0x00, 0x1B, 0x00, 0x26, 0x00, 0x4C, 0x02, 0x63, 0x02, 0x63, 0x02, 0x63, 0xE0, 0xE0, 0xE0, 0x01, 0x93, 0x02, 0x82, 0x03, 0xEB, 0x09, 0xA2, 0x02, 0x76],
  "result": {
    "aqi": 63,
    "gas": 2466,
    "humidity": 64.2,
    "pm03_cnt": 61.1,
    "pm05_cnt": 61.1,
    "pm1": 2.7,
    "pm10": 7.6,
    "pm10_cnt": 22.4,
    "pm1_cnt": 61.1,
    "pm25": 3.8,
    "pm25_cnt": 22.4,
    "pm5_cnt": 22.4,
    "pressure": 1003,
    "temperature": 10.3
  }
},{
  "port": 2,
  "payload": [0x87, 0x00, 0x21, 0x00, 0x37, 0x00, 0x3B, 0x02, 0xF5, 0x02, 0xF5, 0x02, 0xF5, 0x95, 0x95, 0x95, 0x01, 0x92, 0x02, 0x79, 0x03, 0xEA, 0x11, 0xFE, 0x03, 0xB4],
  "result": {
    "aqi": 94.8,
    "gas": 4606,
    "humidity": 63.3,
    "pm03_cnt": 75.7,
    "pm05_cnt": 75.7,
    "pm1": 3.3,
    "pm10": 5.9,
    "pm10_cnt": 14.9,
    "pm1_cnt": 75.7,
    "pm25": 5.5,
    "pm25_cnt": 14.9,
    "pm5_cnt": 14.9,
    "pressure": 1002,
    "temperature": 10.2
  }
},{
  "port": 3,
  "payload": [0x02, 0x43, 0x00, 0x4E, 0x76, 0x36, 0x00, 0x09, 0x5C, 0xA8, 0x00, 0x00, 0x00, 0xEB],
  "result": {
    "altitude": 23.5,
    "dust": "PMS7003",
    "latitude": 51.4207,
    "longitude": 6.13544,
    "meteo": "BME680",
    "version": 0.2
  }
},{
  "port": 3,
  "payload": [0x02, 0x4B, 0x00, 0x4E, 0x76, 0x2B, 0x00, 0x09, 0x5C, 0xB9, 0x00, 0x00, 0x01, 0x03],
  "result": {
    "altitude": 25.9,
    "dust": "PMS7003",
    "gps": 1,
    "latitude": 51.42059,
    "longitude": 6.13561,
    "meteo": "BME680",
    "version": 0.2
  }
}
];

*/

function round(value, decimals) {
  return Number(Math.round(value+'e'+decimals)+'e-'+decimals);
}
function bytes2rat(b,nr) {
  return (b[nr]<<24)+(b[nr+1]<<16)+(b[nr+2]<<8)+b[nr+3];
}
function bytes2(b,nr,cnt) {
  return round(((b[nr]<<8)+b[nr+1])/cnt,1);
}
function notZero(b,nr) {
  if( (b[nr]|b[nr+1]) ){ return true; } else { return false; }
}

function Decoder(bytes, port) {
  // Decode an uplink message from a buffer
  // (array) of bytes to an object of fields.
  var decoded = {}; var lat = 0.0;

  // if (port === 3) decoded.led = bytes[0];
  if ( port === 2 ) {
    if ((bytes[0] & 0x80)) {
      strt = 1;
      if ((bytes[0]&0x1)) {
        if( notZero(bytes,strt) ){ decoded.pm1 = round(bytes2(bytes,strt,10.0),1); }
        strt += 2;
      }
      if( notZero(bytes,strt) ){ round(decoded.pm25 = bytes2(bytes,strt,10.0),1); }
      strt += 2;
      if( notZero(bytes,strt) ){ decoded.pm10 = round(bytes2(bytes,strt,10.0),1); }
      strt += 2;
      if( (bytes[0]&0x2)) {
        if( notZero(bytes,strt) ){ decoded.pm03_cnt = round(bytes2(bytes,strt,10.0),1); }
        strt += 2;
        if( notZero(bytes,strt) ){ decoded.pm05_cnt = round(bytes2(bytes,strt,10.0),1); }
        strt += 2;
        if( notZero(bytes,strt) ){ decoded.pm1_cnt = round(bytes2(bytes,strt,10.0),1); }
        strt += 2;
        if( bytes[strt] ) { decoded.pm25_cnt = round(bytes[strt]/10,1); }
        strt += 1;
        if ( bytes[strt]) { decoded.pm5_cnt = round(bytes[strt]/10,1); }
        strt += 1;
        if ( bytes[strt]) { decoded.pm10_cnt = round(bytes[strt]/10,1); }
        strt += 1;
      }
      if( notZero(bytes,strt) ){ decoded.temperature = round(bytes2(bytes,strt,10.0)-30.0,1); }
      strt += 2;
      if( notZero(bytes,strt) ){ decoded.humidity = round(bytes2(bytes,strt,10.0),1); }
      strt += 2;
      if( notZero(bytes,strt) ){ decoded.pressure = round(bytes2(bytes,strt,1.0),1); }
      strt += 2;
      if( (bytes[0] & 0x4) ) {
        if( notZero(bytes, strt) ){ decoded.gas = round(bytes2(bytes,strt,1.0),1); }        // kOhm
        strt += 2;
        if( notZero(bytes, strt) ){ decoded.aqi = round(bytes2(bytes,strt,10.0),1); }
        strt += 2;
      }
      if( (bytes[0] & 0x8) ){
        lat = bytes2rat(bytes,strt);
          if( lat ) {
              decoded.latitude = round(lat/100000.0,6);
              decoded.longitude = round(bytes2rat(bytes,strt+4)/100000.0,6);
              decoded.altitude = round(bytes2rat(bytes,strt+8)/10.0,6);
          }
      }
    }
    else {
      if ( bytes.length == 10 ) {
        if( notZero(bytes,0) ){ decoded.temperature = bytes2(bytes,0,10.0)-30.0; } // oC
        if( notZero(bytes,2) ){ decoded.humidity = bytes2(bytes,2,10.0); } // %
        if( notZero(bytes,4) ){ decoded.pressure = bytes2(bytes,4,1.0); } // hPa
        if( notZero(bytes,6) ){ decoded.pm10 = bytes2(bytes,6,10.0); }    // ug/m3
        if( notZero(bytes,8) ){ decoded.pm25 = bytes2(bytes,8,10.0); }    // ug/m3
      }
      if ( bytes.length >= 16 ) {
        if( notZero(bytes,0) ){ decoded.pm1 = bytes2(bytes,0,10.0); }   // ug/m3
        if( notZero(bytes, 2) ){ decoded.pm25 = bytes2(bytes,2,10.0); } // ug/m3
        if( notZero(bytes, 4) ){ decoded.pm10 = bytes2(bytes,4,10.0); } // ug/m3
        if( notZero(bytes, 6) ){ decoded.temperature = round(bytes2(bytes,6,10.0)-30.0,1); } // oC
        if( notZero(bytes, 8 ) ){ decoded.humidity = round(bytes2(bytes,8,10.0),1); } // %
        if( notZero(bytes, 10) ){ decoded.pressure = bytes2(bytes,10,1.0); }   // hPa
        if( notZero(bytes, 12) ){ decoded.gas = round(bytes2(bytes,12,1.0),1); }         // kOhm
        if( notZero(bytes, 14) ){ decoded.aqi = round(bytes2(bytes,14,10.0),1); }        // %
        if( bytes.length >= 20 ){ 
          if( notZero(bytes,16) || notZero(bytes,18) ){
              decoded.utime = ((bytes[16]<<24)+(bytes[17]<<16)+(bytes[18]<<8)+bytes[19]);
            }
        }
      }
      if( bytes.length >= 26) {
          lat = bytes2rat(bytes,20);
          if( lat ) {
             decoded.latitude = round(lat/100000.0,6);
             decoded.longitude = round(bytes2rat(bytes,24)/100000.0,6);
             decoded.altitude = round(bytes2rat(bytes,28)/10.0,6);
          }
      }
    }
  }
  var dustTypes = ['unknown','PPD42NS','SDS011','PMS7003','SPS30','unknown','unknown'];
  var meteoTypes = ['unknown','DHT11','DHT22','BME280','BME680','SHT31'];
  if ( port === 3 ){
    decoded.version = bytes[0]/10.0;
    decoded.dust = dustTypes[(bytes[1]&0x7)];
    if( (bytes[1]&0x8) ) { decoded.gps = 1; }
    if ( ((bytes[1]>>4)&0xf) > meteoTypes.length ) { bytes[1] = 0;}
    decoded.meteo = meteoTypes[((bytes[1]>>4)&0xf)];
    var lati = bytes2rat(bytes,2);
    if( lati ) {
      decoded.latitude = round(lati/100000.0,6);
      decoded.longitude = round(bytes2rat(bytes,6)/100000.0,6);
      decoded.altitude = round(bytes2rat(bytes,10)/10.0,6);
    }
    
  }

  return decoded;
}

/*
var test = {};
var rslt = {};
document.write(rslt["pm25"]);
for ( test in tests ) {
   rslt = Decoder(tests[test]["payload"],tests[test]["port"]);
  document.write("<br>port nr " + tests[test]["port"] + ":<br>")
   for ( var one in rslt ) {
     document.write("&nbsp;&nbsp;&nbsp;&nbsp;" + one + "&nbsp;" + tests[test]["result"][one] + " --> " + rslt[one]+"<br>");
   }
}
*/

