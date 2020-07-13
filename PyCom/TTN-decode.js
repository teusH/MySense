/*
 * Copyright 2018, Teus Hagen, GPL4
 * decode LoRa payload sent by MySense node
 * copy/paste this JavaScript into format area at TTN server
 */
var version = "$Version: 1.6$".slice(10,-1);
/*
var payloads = [
  "00000050007901C4033003FC000000000000",
  "87002500360037031403140314CECECE01D1023103E30A64039E"
];

function PrtDecoded(strg,items) {
  document.write("&nbsp;&nbsp;" + strg + ": <br>");
  for ( var one in items ) {
     document.write("&nbsp;&nbsp;&nbsp;&nbsp;" + one + "&nbsp;: " + items[one] + "<br>");
   }
}
function myPrt(output) {
  document.write("Debug print: " + output + "<br>");
}
*/

// test data
/*
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
  return Number(Math.round(value + 'e' + decimals) + 'e-' + decimals);
}
function bytes2rat(b, nr) {
  return (b[nr] << 24) + (b[nr + 1] << 16) + (b[nr + 2] << 8) + b[nr + 3];
}
function bytes2(b, nr, cnt) {
  return round(((b[nr] << 8) + b[nr + 1]) / cnt, 1);
}
function notZero(b, nr) {
  if ((b[nr] | b[nr + 1])) {
    return true;
  } else {
    return false;
  }
}
function DecodePrt4(bytes) { /* PM count type HHHHHH */
    var decoded = { };
    // myPrt("port 2 PM cnt bytes " + bytes.length + ": " + bytes);
    var expl = true; var pm_4 = false;
    try {
      if (bytes[0]&0x80) { expl = false; bytes[0] = bytes[0] & 0x7F; }
      if (bytes[4]&0x80) { pm_4 = true; bytes[4] = bytes[4] & 0x7F; }
      var pm45 = 0.0;
      decoded.pm10_cnt = round(bytes2(bytes, 0, 10), 1);
      decoded.pm05_cnt = round(bytes2(bytes, 2, 10), 1);
      decoded.pm1_cnt = round(bytes2(bytes, 4, 10), 1);
      decoded.pm25_cnt = round(bytes2(bytes, 6, 10), 1);
      pm45 = round(bytes2(bytes, 8, 10), 1);
      if ( expl ) { decoded.pm03_cnt = round(bytes2(bytes, 10, 10), 1); }
      else { 
        decoded.grain = round(bytes2(bytes, 10, 100), 2); /* avg PM size */
        /* PMi - PMj conversion to PM0.3 - PMx */
        decoded.pm1_cnt += decoded.pm05_cnt;
        decoded.pm25_cnt += decoded.pm1_cnt;
        pm45 += decoded.pm25_cnt;
        decoded.pm10_cnt += pm45;
      }
      if (pm_4 ) { decoded.pm4_cnt = pm45; } /* Sensirion */
      else { decoded.pm5_cnt = pm45; }       /* Plantower */
    }
    catch(e) { }
    finally {  
      // PrtDecoded("decode PM cnt port 4",decoded);
      return decoded;
    }
}

function decodePM(bytes) { /* ug/m3 [H]HH */
    var decoded = {}; var strt = 0;
    // myPrt("PM bytes " + bytes.length + ": " + bytes);
    try {
      if ( bytes.length > 4 ) {
        if (notZero(bytes, 0)) {
          decoded.pm1 = round(bytes2(bytes, 0, 10), 1);
        }
        strt += 2;
      }
      if (notZero(bytes, strt)) {
        round(decoded.pm25 = bytes2(bytes, strt, 10), 1);
      }
      if (notZero(bytes, strt+2)) {
        decoded.pm10 = round(bytes2(bytes, strt+2, 10), 1);
      }
    }
    catch(e) {}
    finally {
      // PrtDecoded("decodePM decoded",decoded);
      return decoded;
    }
}

function DecodePrt2(bytes) { /* PM counts HHHBBB */
    var decoded = {};
    // myPrt("port 2 PM cnt bytes " + bytes.length + ": " + bytes);
    try {
      if (notZero(bytes, 0)) {
        decoded.pm03_cnt = round(bytes2(bytes, 0, 10), 1);
      }
      if (notZero(bytes, 2)) {
        decoded.pm05_cnt = round(bytes2(bytes, 2, 10), 1);
      }
      if (notZero(bytes, 4)) {
        decoded.pm1_cnt = round(bytes2(bytes, 4, 10), 1);
      }
      if (bytes[6]) {
        decoded.pm25_cnt = round(bytes[6] / 10, 1);
      }
      if (bytes[7]) {
        decoded.pm5_cnt = round(bytes[7] / 10, 1);
      }
      if (bytes[8]) {
        decoded.pm10_cnt = round(bytes[8] / 10, 1);
      }
    }
    catch(e) {}
    finally { 
      // PrtDecoded("decode PM cnt port 2",decoded);
      return decoded;
    }
}

function decodeMeteo(bytes) { /* BME, SHT HH[H[HH]] */
    var decoded = {};
    // myPrt("Meteo decode bytes " + bytes.length + ": " + bytes);
    try {
      if (notZero(bytes, 0)) {
        decoded.temperature = round(bytes2(bytes, 0, 10) - 30, 1);
      }
      if (notZero(bytes, 2)) {
        decoded.humidity = round(bytes2(bytes, 2, 10), 1);
      }
      if ( bytes.length <= 4 ) return decoded;
      if (notZero(bytes, 4)) {
        decoded.pressure = round(bytes2(bytes, 4, 1), 1);
      }
      if ( bytes.length <= 6 ) return decoded;
      if (notZero(bytes, 6)) { /* BME680 */
        decoded.gas = round(bytes2(bytes, 6, 1), 1);
      } // kOhm
      if (notZero(bytes, 8)) {
        decoded.aqi = round(bytes2(bytes, 8, 10), 1);
      }
    }
    catch(e) {}
    finally {
      // PrtDecoded("decode Meteo decoded",decoded);
      return decoded;
    }
}

function decodeGPS(bytes) { /* GPS NEO 6 */
    var lat = 0.0; var decoded = {};
    // myPrt("decode GPS bytes " + bytes.length + ": " + bytes);
    try { 
        lat = bytes2rat(bytes, 0);
        if (lat) {
            decoded.latitude = round(lat / 100000, 6);
            decoded.longitude = round(bytes2rat(bytes, 4) / 100000, 6);
            decoded.altitude = round(bytes2rat(bytes, 8) / 10, 6);
        }
    }
    catch(e) {}
    finally {
      // PrtDecoded("decode GPS decoded",decoded);
      return decoded;
    }
}

function decodeAccu(bytes) { /* voltage */
    var decoded = {};
    // myPrt("Accu bytes " + bytes.length + ": " + bytes);
    try {
      if( bytes[0] > 0 ) decoded.accu = round(bytes[0]/10.0,2); 
    }
    catch(e) {}
    finally {
       // PrtDecoded("decodeAccu decoded",decoded);
      return decoded;
    }
}

function decodeWind(bytes) { /* speed m/sec, direction 0-359 */
    var decoded = {}; var speed = 0.0; var direct = 0;
    // myPrt("Wind bytes " + bytes.length + ": " + bytes);
    try {
      speed = round(bytes[0]/5.0,1);
      if ( (bytes[1] & 0x80)) speed += 0.1;
      decoded.wspeed = speed;
      direct = (bytes[1] & 0x7F);
      if (direct > 0 ) decoded.wdirection = (direct*3)%360;
    }
    catch(e) {}
    finally {
       // PrtDecoded("decodeWind decoded",decoded);
      return decoded;
    }
}

function DecodeMeta(bytes) {
  var decoded = {}
  // myPrt("Info/Meta decode bytes " + bytes.length + ": " + bytes);
  var dustTypes = [
    'unknown',
    'PPD42NS',
    'SDS011',
    'PMS7003',
    'SPS30',
    'unknown',
    'unknown'
  ];
  var meteoTypes = [
    'unknown',
    'DHT11',
    'DHT22',
    'BME280',
    'BME680',
    'SHT31'
  ];
  try {
    decoded.version = bytes[0] / 10;
    if (bytes[1] == 0) { decoded.event = bytes[bytes.length-1]; return decoded; }
    decoded.dust = dustTypes[(bytes[1] & 7)];
    if ((bytes[1] & 8)) {
      decoded.gps = 1;
    }
    if (((bytes[1] >> 4) & 15) > meteoTypes.length) {
      bytes[1] = 0;
    }
    decoded.meteo = meteoTypes[((bytes[1] >> 4) & 15)];
    var lati = bytes2rat(bytes, 2);
    if (lati) {
      decoded.latitude = round(lati / 100000, 6);
      decoded.longitude = round(bytes2rat(bytes, 6) / 100000, 6);
      decoded.altitude = round(bytes2rat(bytes, 10) / 10, 6);
    }
  }
  catch(e) {}
  finally {
      // PrtDecoded("decode meta info decoded",decoded);
      return decoded;
  }
}

function combine(decoded,addon) { /* combine 2nd arg object to first, return rtlt */
  for ( var item in addon ) decoded[item] = addon[item];
  return decoded;
}

function Decoder(bytes, port) {
  // Decode an uplink message from a node
  // (array) of bytes to an object of fields.
  // myPrt("port" + port + ", length " + bytes.length + ": " + bytes);
  if ( port == 3 ) return DecodeMeta(bytes);
  if ( port == 10 ) return {};
  var decoded = { "TTNversion": version }; var type = 0x0;
  var strt = 0; var end = 1;
  /* dust [H]HH[HHH[BBB|HHH]] */
  if (bytes[0] & 0x80) { strt = 1; type = bytes[0]; } /* version >0.0 */
  else if ( port == 2 ) { /* deprecated packing style */
      if ( bytes.length == 10 ) { /* deprecated packing style */
          decoded = combine(decoded,decodeMeteo(bytes.slice(0,6)));
          decoded = combine(decoded,decodePM(bytes.slice(6,10)));
          var tmp = decoded.pm10; decoded.pm10 = decoded.pm25; decoded.pm25 = tmp;
          return decoded;
      }
      else if ( bytes.length >= 16 ) type |= 0x5; // PM1 gas/aqi
  }
  /* PM ug/m3 [H]HH */
  end = strt + 4;
  if (type & 0x1) end += 2; // PM1
  decoded = combine(decoded,decodePM(bytes.slice(strt,end)));
  strt = end;
  if ((type & 0x2)) { /* PM pcs/0.1dm3 */
      var PNdecoded = {};
      if (port === 2) { /* HHHBBB */
          decoded = combine(decoded,DecodePrt2(bytes.slice(strt,strt+9)));
          strt += 9;
      }
      if (port === 4){ /* HHHHHH */
          decoded = combine(decoded,DecodePrt4(bytes.slice(strt,strt+12)));
          strt += 12;
      }
  }
  /* meteo HHH[HH] */
  end = strt+6; if ( bytes.length < end ) return decoded;
  if ( (type & 0x4) ) end += 4; /* add gas & aqi */
  decoded = combine(decoded,decodeMeteo(bytes.slice(strt,end))); strt = end;
  if ( bytes.length >= strt+3*4-1 ){ /* gps location */
      if ( (type & 0x8) ) {
          decoded = combine(decoded,decodeGPS(bytes.slice(strt,strt+3*4)));
          strt += 3*4;
      }
  }
  if ( bytes.length >= strt+1) { /* wind dir/speed */
      if ( (type & 0x10) ) {
          decoded = combine(decoded,decodeWind(bytes.slice(strt,strt+2)));
          strt += 2;
      }
  }
  if (bytes.length >= strt ){ /* accu/battery volt */
      if ( (type & 0x20) ) {
          decoded = combine(decoded, decodeAccu(bytes.slice(strt,strt+1)));
          strt += 1;
      }
  }
  return decoded;
}

/*
var test = {};
var rslt = {}; 

//PrtDecoded(tests[1]["result"]);
//rslt = Decoder(tests[1]["payload"],tests[1]["port"]);
//PrtDecoded(rslt);

for ( test in tests ) {
   rslt = Decoder(tests[test]["payload"],tests[test]["port"]);
   document.write("<br>port nr " + tests[test]["port"] + ":<br>")
   for ( var one in rslt ) {
     document.write("&nbsp;&nbsp;&nbsp;&nbsp;" + one + "&nbsp;" + tests[test]["result"][one] + " --> " + rslt[one]+"<br>");
   }
}
*/
