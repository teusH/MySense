# LoPy BME280/SDS011 MySense sensor kit
Operational: 2018/02/23

## DESCRIPTION
The sensor kit is build with a LoPy-4 (PyCom) ESP controller. The controller has on board LoRa, WiFi and BlueTooth. Use an external LoRa Wan 868/915 LoRa antenna. The LoPy can be programmed via embedded python. To access the baord use the Atom (atom-beta) from PyCom. Atom is interfacing either via WiFi or serial (USB) connection to the controller.

## MySense LoPy description
The python script uses the Adafruit BME280 python module and SDS011 module from Rex Fue Feinstaub `https://github.com/rexfue/Feinstaub_LoPy` and Telenor weather station `https://github.com/TelenorStartIoT/lorawan-weather-station`.

In the test phase one should not download main.py to the LoPy controller. Use `sense.py` in this phase instead.
Use (open) the directory `firmware` as base for the atom project and upload all file by pressing the upload key.
On the console prompt `>>>` use the following:
```python
import sense
sense.runMe()
```
After this initial test rename sense.py to main.py. And upload main.py to the LoPy.

### how to reset the LoPy
You can delete old firmware using the instruction by PyCom. Moslty you only need to delete all uploaded file as follows:

Use the reset button on the LoPy to get the atom prompt `>>>` and do the following:
```python
    import os
    os.mkfs('/flash')
```
And upload your new files.

## MySense LoPy status
The console will print status as will the flashing led on the LoPy will flash different collors: red to establish LoRa connectivity, blue when LoRa is ready, green when measuremnts are arriving, and blue when data is sent, and white when SDS011 fan is turned off to save the fan and laser as well LoPy is in idle state. LoPy will send every 5 minutes (`sleep_time`) a measurement sample  to the TTN data concentrator.

## LoPy-4 BME/SDS wiring
Orientate the LoPy with the flash light up (if you use the recommanded development shield the small USB connecter will be on top). The name `pycom lopy` will face to the left side. The left side pins are numbererd top down as RST, P0, P1 ,...,P12.
The right side pins top down are numbered as: Vin V3.3/V5, Gnd, 3V3, P23, P22, ..., P13.

SDS011 TTL Uart connection:
* SDS Gnd (black) -> LoPy Gnd (on right side 2nd pin, same pin as for BME)
* SDS V5 (red) -> LoPy V5 (on right side, top pin)
* SDS Rx (white) -> LoPy P3 / Tx1 (on left side, 5th pin from top)
* SDS Tx (yellow)-> LoPy P4 / Rx1 (on left side, 6th pin from top)

BME280 I2C  connection (default I2C address):
* BME Gnd (black) -> LoPy Gnd (on right side, same pin as for SDS)
* BME V3/5 (red) -> LoPy 3V3 (on right side, 3rd pin from top)
* BME SDA (white) -> LoPy SDA (on left side, 11th pin from top)
* BME SCL (yellow) -> LoPy CLK (on left side, 12th pin from top)

## To Do
Add ssd1306 display, add GPS

## TTN how to
You need to set up an account and password with The Things Network: https://thethingsnetwork.org/

Via the `console` add an application with a name: https://console.thethingsnetwork.org/applications/add
If done so click on the added application name and register a device: 
://console.thethingsnetwork.org/applications/NAME_APPLICATION/devices/register
Write down the following information to be entered in the LoRaConfig.py:
```python
dev_eui = "XXXXXXXXXXXXXXXX"
app_eui = "YYYYYYYYYYYYYYYY"
app_key = "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"
```
If you want to access (and you want to do that during tests) the TTN MQTT server you need to write down the App ID (NAME_APPLICATION) and Access Key (bottom of the App Id page).

If the LoPy sensor kit is running you
### TTN how to configure TTN decode to json MQTT
TTN data formats, decoder example.
Test this with payload: 02 02 01 04 03 FE 00 32 00 2E
```java
function Decoder(bytes, port) {
  // Decode an uplink message from a buffer
  // (array) of bytes to an object of fields.
  var decoded = {};

  // if (port === 1) decoded.port = bytes[0];
  decoded.temperature = ((bytes[0]<<8)+bytes[1])/10.0-30.0;
  decoded.humidity = ((bytes[2]<<8)+bytes[3])/10.0;
  decoded.pressure = (bytes[4]<<8)+bytes[5];
  decoded.pm10 = ((bytes[6]<<8)+bytes[7])/10.0;
  decoded.pm25 = ((bytes[8]<<8)+bytes[9])/10.0;
  decoded.dust = 'SDS011';
  decoded.meteo = 'BME280';

  return decoded;
}
```

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
    "payload_fields":{
        "dust":"SDS011","humidity":26,"meteo":"BME280",
        "pm10":5.7,"pm25":5.2,"pressure":1023,"temperature":20.7},
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
