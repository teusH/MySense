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
  var dustTypes = ['unknown','PPD42NS','SDS011','PMS7003','unknown','unknown','unknown'];
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
