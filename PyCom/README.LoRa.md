## Description
The LoRa gateway will forward LoRa radio data messagers from a measurement kit or LoRa node to the LoRa (TheThingsNetwork) server where the gateway and nodes has been registrated. The TTN network is a free LoRa infrastructure services from The Things Network in Amsterdam.

Here we will describe the steps to take  and wehere to find more info to build a powerfull LoRa gateway as being used in MySense.

## shopping list
* Raspberry Pi: advised is Pi-3 (ca € 40) as it has wifi on board. If one uses an outdoor LoRa antenna one can use the WiFi (or G4 with e.g. a Huawei E3531 HPSA+ USB dongle, € 30).
* use a Pi case bottumn to fixate the Pi to the housing, ca € 4
* an SDcard of minimal 16 Gb (ca € 10)
* V5 adapter and USB 2.5m charging cable (ca € 20)
* case: e.g. OBO T-serie T100 (closed cable case), ca € 10
* 8 colored Du Pont female-female wires, ca € 1
* IMST IC880-SPI, (Ideetron has them available) € 120
* pig tail for IC880A-pig € 6.50
* LoRa antenne 868 Mhz SMA90 € 7.40
* optionally an outdoor antenna, ca € 100

Total costs:  ca € 220 without delivery costs.

Gateways can be obtained completely build and tested e.g. TTN, IMST and others for ca € 130 - 500
with or without an indoor antenna.
Our experience show that a gateway is needed to cover withy a radius of a practical max of ca 2.5km. The range depends heavily on free sight. Locating the antenna on a roof of a higher building helps a lot, but mention the thunderstrike problem.
As well there is a dependeance to the antenna of the sensor kit.

## how to build the LoRa TTN gateway
Basically you need to configure the hardware (wiring), install Debian on the Pi (the official installation guide: https://www.raspberrypi.org/documentation/installation/installing-images/README.md) and use the LoRa forwarder package:
``` shell
git clone https://github.com/Lora-net/packet_forwarder.git
```
Follow the instruction from the following webpage:
* https://doc.info.fundp.ac.be/mediawiki/index.php/Setup_IC880A-SPI_(LoRaWAN_concentrator)_on_Raspberry_Pi_3

Make sure that if you are going to use an outdoor antenna to use wifi as internet communication channel.

Some warnings:
* The LoRa IC880A board is static sensitive!
* Do not poweron the LoRa board without a LoRa antenna connected.
* Do not power on the LoRa gateway within 3 meters from a LoRa node.

A good experience we had with the *RAK 7258* (ca € 160) gateway with an external antenna (ca € 75) in a weather resistant box (ca € 35). Use eg a TTN LoRa mapper (RAK or self build) app to obtain some LoRa signal strength infoirmation of the LoRa coverage.

More information you will find here:
* IC880A-SPI official Quick start guide: https://wireless-solutions.de/images/stories/downloads/Radio%20Modules/iC880A/iC880A-SPI_QuickStartGuide.pdf
* IC880A-SPI on Raspberry Pi tutorial: https://github.com/ttn-zh/ic880a-gateway/wiki
* LoRa net GitHub link: https://github.com/Lora-net
* another how to config a TTN gateway: https://sandboxelectronics.com/?p=2696

## TTN how to
You need to set up an account and password with The Things Network: https://thethingsnetwork.org/

Via the `console` register your gateway. You will get an access id for your gateway from TTN. This long identification string should be added in your configuration.

You need a data acquisition script to upload the kit data. See `TTN-datacollector.py` for this. This script will support kit event and management functions.
Different backend are supplied to archive the measurements eg to Luftdaten, MySQL database, console, InfluxDB or Mosquitto.

## LoRa node signal strength
For the LoRa LoPy-4 we discovered a variation of signal strength (watch RSSI and Signal Noise Ration or SNR) of the kit. Be aware that the pigtail should not be replaced too many, has no 90 degreehook, etc. A wire near the antenna will disturb the signal strength heavily.
An antenna outside the housing is easily damaged. However the housing material with an internal antenna may disrupt the signal strength. Our housing is made of PVC which limit the max distance to a LoRa gateway to ca 2.5 km.
Default the LoRa spreading factor (SF) for the LoPy is set to 7. Enlarging this SF will negatively influence maximum air time and datagram size.
The way out is: if the distance is a problem we can easily turn the antenna to point the antenna down to an out side situation.
The lesson learned is: collect the RSSI and SNR values provided via the LoRa gateway to TTN.

The default data rate during LoRa join phase is set to DR=0 (spreading factor 12, highest level). To change the data rate use Config.py (configuration file). The PyCom default data rate is None (SF7).

The LoRa socket data rate is set to 2. One can change this default values via the Config.py (configuration) file.
