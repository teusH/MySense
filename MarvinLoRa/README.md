## Marvin LoRa controller based sensor kit
### STATUS
2017-12-24 operational via TTN Europe

### DESCRIPTION
The sensorkit is build with a Marvin LoRa controller (ca  84 euro), an dust SDS011 sensor (ca 20 euro) and a waether  DHT22 (ca 10 euro).
This sensorkit fits in a small outdoor V220 connectionbox.

### FIRMWARE
Change the TTN keys in the ino files to the settings at the TTN data concentrator.

Add the Marvin LoRa controller to the Arduine IDE controllers.
Point Arduino IDE to the ion formware files and and upload the firmware to the Marvin controller.

### HARDWARE
The Marvin LoRa uses Grove connectors: 3X analogue, 1 X digital and one I2C bus.

SDS011 Rx -> P15, SDS011 Tx -> P16. Pins are on the back of the Marvin board.

DHT22 is connected with a Grove connecytor to the second (analogue) connector position on the Marvin board.

Wiring:
* SDS011
```
    |_._._._._._| SDS011 connector
      | | | | |
     nc R B b y   R=Red-Vcc B=Black-Gnd b=Blew-Rx y=Yellow-Tx
```
* Marvin Uart backside board, 6 pins at board side
```
    ---------
    | 1  2R |             2 Red-VCC
    | 3B 4Y |  3 Blew-Rx  4 Yellow-Tx
    | 5  6B |             6 Black-Grnd
    ---------
_______________board side
```
* DHT22
```
              -----
   Gnd black -|    \
   Vcc red   -|    o|
       nc    -|     |
   sig yellow-|    /
              -----
```
* Marvin Lora Grove connector for DHT22
```
      -----------------------------
      |  ||  ||  XX  ||   ------- |   DHT22 Grove connector
      |  ||  ||  XX  ||   | RN  | |   . Black-Grnd
      |                   |     | |   . Red-VCC
      |  Marvin LoRa      ------- |   . White
      -----------------------------   . Yellow-signal
```
### ANTENNA
The Marvin has an on board antenna. Make sure if installed that one of the antenna end point is pointing into the direction of the TTN data forwarder.

### TEST
Look at the TTN data concentrator dashboard to see if data is forwarded to the TTN data concentrator.

### PAYLOAD
If the LoRa payload fields are not defined, the `MyTTNMQTT.py` input handler will unpack the payload into the expected format as defined by the Marvin firmware.

### META DATA
The GPS coordinates of the sensor kit are taken from the manual entered TTN data concentrator profile `devices`. However the coordinates as well more meta data can be defined from the meta data file of MyTTNMQTT. Make sure one has defined the TTN device names as well in the MyTTNMQTT config part as well.

Serial numbers is strange with the Marvin controller. So these can be defined from the meta desciption file of MyTTNMQTT or are calculated from a hash of the topics/device naming of TTN.
