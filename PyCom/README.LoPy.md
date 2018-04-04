## Description
The LoPy is a low cost (€ 35) ESP controller which support mi8cropython and has wifi, bluetooth and LoRaWan capabilities. MySense is using the PyCom expansion board (€ 16) for the wiring and programming.

MySense operates with TTN as LoRa dataconcentrator. MySense will initialy try for a period of 5 seconds to join the LoRa network. On failuer it will skip to send measurements to TTN and will continue to show locally the measurements.

For installation, and firmware update see:
* reference: https://docs.pycom.io

## LoPy-4 BME/SDS wiring

Orientate the LoPy with the flash light up (if you use the recommanded development shield the small USB connecter will be on top). The name `pycom lopy` will face to the left side. The left side pins are numbererd top down as RST, P0, P1 ,...,P12.
The right side pins top down are numbered as: Vin V3.3/V5, Gnd, 3V3, P23, P22, ..., P13.

<img src="images/PyCom-wiring-BME-SDS-PMS-SSD-GPS.png" align=right width=400>

SDS011/PMS7003 TTL Uart connection:
* SDS Gnd (black) -> LoPy Gnd (on right side 2nd pin, same pin as for BME)
* SDS V5 (red) -> LoPy V5 (on right side, top pin)
* SDS Rx (white) -> LoPy P3 / Tx1 (on left side, 5th pin from top)
* SDS Tx (yellow)-> LoPy P4 / Rx1 (on left side, 6th pin from top)

BME280/680 I2C  connection (default I2C address):
* BME Gnd (black) -> LoPy Gnd (on right side, same pin as for SDS)
* BME V3/5 (red) -> LoPy 3V3 (on right side, 3rd pin from top)
* BME SDA (white) -> LoPy SDA (on left side, 11th pin from top)
* BME SCL (yellow) -> LoPy CLK (on left side, 12th pin from top)

SSD1306 SPI connection (using GPIO pins):
* SSD CS (blue) -> LoPi P22
* SSD DC (purple) -> LoPy P20
* SSD RST (gray) -> LoPy P21
* SSD D1 (white) -> LoPy P23
* SSD D0 (orange) -> LoPy P19
* SSD VCC (red) -> LoPy 3V3 (shared with BME280)
* SSD GND (black) -> LoPy Gnd (on right side, same pin as for SDS)

Grove GPS TTL Uart connection:
* GPS Gnd (black) -> LoPy Gnd (on right side, shared pin)
* GPS Vcc (red) -> LoPy 3V3 (shared with others)
* GPS Rx (green) -> LoPy P12 / Tx2 (on left side, 1st pin from bottom)
* GPS Tx (yellow) -> LoPy P11 / Rx2 (on left side, 2nd pin from bottom)

## To Do
remote command handling

## TTN how to
You need to set up an account and password with The Things Network: https://thethingsnetwork.org/

Via the `console` add an application with a name: https://console.thethingsnetwork.org/applications/add
If done so, click on the added application name and register a device: 
://console.thethingsnetwork.org/applications/NAME_APPLICATION/devices/register
Write down the following information to be entered in the Config.py:
```python
dev_eui = "XXXXXXXXXXXXXXXX"
app_eui = "YYYYYYYYYYYYYYYY"
app_key = "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"
```
If you want to access (and you want to do that during tests) the TTN MQTT server you need to write down the App ID (NAME_APPLICATION) and Access Key (bottom of the App Id page).

If the LoPy sensor kit is running you

## LoRa test
### Send test data to TTN
Use the script `lora_test.py` to test your configuration and LoRa connectivity.
```python
    >>>import lora_test # this will send MySense info and MySense data
```
### Reading at TTN the data
The payload format at TTN console may be configured like:
```java script
function round(value, decimals) {
  return Number(Math.round(value+'e'+decimals)+'e-'+decimals);
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
  var decoded = {};

  // if (port === 3) decoded.led = bytes[0];
  if ( port === 2 ) {
    if ( bytes.length == 10 ) {
      if( notZero(bytes,0) ){ decoded.temperature = bytes2(bytes,0,10.0); } // oC
      if( notZero(bytes,2) ){ decoded.humidity = bytes2(bytes,2,10.0); } // %
      if( notZero(bytes,4) ){ decoded.pressure = bytes2(bytes,4,1.0); } // hPa
      if( notZero(bytes,6) ){ decoded.pm10 = bytes2(bytes,6,10.0); }    // ug/m3
      if( notZero(bytes,8) ){ decoded.pm25 = bytes2(bytes,8,10.0); }    // ug/m3
    }
    if ( bytes.length >= 16 ) {
      if( notZero(bytes,0) ){ decoded.pm1 = bytes2(bytes,0,10.0); }   // ug/m3
      if( notZero(bytes, 2) ){ decoded.pm25 = bytes2(bytes,2,10.0); } // ug/m3
      if( notZero(bytes, 4) ){ decoded.pm10 = bytes2(bytes,4,10.0); } // ug/m3
      if( notZero(bytes, 6) ){ decoded.temperature = bytes2(bytes,6,10.0)-30.0; } // oC
      if( notZero(bytes, 8 ) ){ decoded.humidity = bytes2(bytes,8,10.0); } // %
      if( notZero(bytes, 10) ){ decoded.pressure = bytes2(bytes,10,1.0); }   // hPa
      if( notZero(bytes, 12) ){ decoded.gas = bytes2(bytes,12,1.0); }         // kOhm
      if( notZero(bytes, 14) ){ decoded.aqi = bytes2(bytes,14,1.0); }        // %
      if( bytes.length >= 20 ){ 
        // timestamp base is Unix Epoch (GPS) or time power on LoPy
        if( notZero(bytes,16) || notZero(bytes,18) ){ // Unix timestamp
            decoded.utime = (bytes2(bytes,16,1)<<32) + bytes2(bytes,18,1);
        }
      }
    }
  }
  var dustTypes = ['','PPD42NS','SDS011','PM7003','','','','','','','','','','','',''];
  var meteoTypes = ['','DHT11','DHT22','BME280','BME680','','','','','','','','','','',''];
  if ( port === 3 ){
    decoded.version = bytes[0]/10.0;
    if( bytes[1]&0x0f ) { decoded.dust = dustTypes[bytes[1]&017]; }
    if( bytes[1]&0xf0 ) { decoded.meteo = meteoTypes[bytes[1]>>4]; }
    var lat = bytes2rat(bytes,2);
    if( lat ) {
      decoded.latitude = round(lat/100000.0,6);
      decoded.longitude = round(bytes2rat(bytes,6)/100000.0,6);
      decoded.altitude = round(bytes2rat(bytes,10)/10.0,6);
    }
    
  }

  return decoded;
}
```
Try this with a payload as showed on the tab 'data'.

### how to collect the data from TTN MQTT server
Here is an example how your sensor kit will show at the TTN MQTT server via the command:
```bash
mosquitto_sub -v -h eu.thethings.network -p 1883 -u "$APPID" -P "$ACCES_KEY"  -t '+/devices/+/up'
```

The json string from the server, something like:
```json
2021802118025917/devices/lopyprototype/up {
    "app_id":"20215z","dev_id":"lopyprototype","hardware_serial":"D495613",
    "port":2,"counter":25,
    "payload_raw":"AfsBBAP/ADkANA==",
    "payload_fields":{ 'temperature': -12.3, 'humidity': 80, ...
        "utime": 12345678
    },
    "metadata":{
        "time":"2018-02-23T19:49:29.919556985Z","frequency":868.5,
        "modulation":"LORA","data_rate":"SF7BW125","airtime":61696000,
        "coding_rate":"4/5","gateways":[
            {"gtw_id":"eui-b827befff65b8e9","timestamp":1663804715,
            "time":"2018-02-23T19:49:29.891823Z",
            "channel":2,"rssi":-37,"snr":7.8,"rf_chain":1,
            "latitude":15.40283,"longitude":2.15341,"altitude":230}
    ]}}
```

### LoRa port usage
The LoRa connect routine supports to open more ports as the default LoRa port 2. Use the argument: `ports=3` to open 3 ports. The LoRa send routine supports an argument to discriminate to which port to send the payload.
Currently ports used by MySense:
* port 2 (default) to send measurement data: PM2.5, PM10, temp, humidity, pressure, unix timestamp, etc.
* port 3 to send meta data as which sensors and location if available.

The LoRa implementation supports to collect data sent to the sensor kit. Define the argument `callback=commandRoutine` on the connect initialisation. The callback rooutin on reception of data on any LoRa port will be called as: `commandRoutine(port,receieved_data)`. See lora_test.py for examples. 
