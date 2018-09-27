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

Gateways can be obtained completely build and tested e.g. TTN, IMST and others for ca € 330 - 500
with or without an indoor antenna.
Our experience show that a gateway is needed to cover withy a radius of ca 2.5km. The range depends heaviloy on free sight. Locating the antenna on a roof of aa higher building helps a lot, but mention the thunderstrike problem.

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

More information you will find here:
* IC880A-SPI official Quick start guide: https://wireless-solutions.de/images/stories/downloads/Radio%20Modules/iC880A/iC880A-SPI_QuickStartGuide.pdf
* IC880A-SPI on Raspberry Pi tutorial: https://github.com/ttn-zh/ic880a-gateway/wiki
* LoRa net GitHub link: https://github.com/Lora-net

## TTN how to
You need to set up an account and password with The Things Network: https://thethingsnetwork.org/

Via the `console` register your gateway. You will get an access id for your gateway from TTN. This long identification string should be added in your configuration.
