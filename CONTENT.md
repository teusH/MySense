# Overview of files
## General Documentation
* README.md     general README
* README.i2c    I2C bus usage for sensor modules
* README.mqtt   installation of mosquitto server (optional)
* README.mysense MySense.py usage help
* README.pi     Pi3 Jessie OS installation guide
## Plugin Documentation
docs directory:
## install/library (install dependencies)
* INSTALL.sh    Installs (bash) the dependencies and OS support: try `./INSTALL.sh help`
### sensors
* bme280.md     Adafruit / Grove BME280 humidity/temp/air pressure sensor  
* dht.md        Adafruit / Grove DHT11/22 humidity/temp sensor
* dylos.md      Dylos DC1100 Pro dust sensor
* gps.md        Grove Ultimate GPS locator
* grove_dB.md   Grove loudness sensor
* shinyei.md    Grove Shinyei PPD42NS dust sensor
### output channels
* db.md         MySQL database output channel
* gspread.md    Google gspread output channel
* http          To be done: template
* console       to be done: just console output
### Pi stuff
* led.md        led/relay/button for Pi poweroff/wifi access point search
* wifi.md       wifi/utp client and wifi access point installation
* backdoor.md   install remote access to the Pi
* grovepi.md    GrovePi shield
## Python scripts
### main
* help          Try: `python ./MySense.py --help`
* MySense.py    Main python script: command line handling, input/output plugins
* MySense.conf  MySense configuration/init file
### input plugins
* MyBME280.py   BME280 humidity/temp sensor
* MyDBGROVE.py  Grove loudness sensor
* MyDHT.py      Grove humidity/temp sensor
* MyDYLOS.py    Dylos DC1100 Pro (USB serial) dust sensor
* MyMQTTSUB.py  Input from Mosquitto server (relay/broker function)
* MyGPS.py      Grove GPS sensor
* MyARDUINO.py  Connection to Arduino Uno (for Shinyei)
* MyArduino.ino Firmware for Arduino Uno with Shinyei PPD42NS dust sensor
* MyRSSI.py     Input wifi signal strength
### output channels (plugins)
* MyMQTTPUB.py  Output channel via Mosquitto (MQTT)
* MyCONSOLE.py  Output channel to console (or file)
* MyDB.py       Output channel to MySQL database
* MyCSV.py      Output channel in CVS format
* MyGSPREAD.py  Output Google gspread (credential access not tested)
* MyEMAIL.py    Output (description sensor kit) via email
* MyBROKER.py   HTTP output channel (template)
### support modules
* MyLogger.py   Logging of MySense info
* MyInternet.py Use of internet connectivity
* MyI2C.py      Sensors via I2C bus
* MyThreading.py Multi threading library for input plugins
### OS support scripts
* MyLed.py      Script to use led/relay/button
* statistics/Calibrate.py Script to calculate best fit polynomial between two measurement data 
## testdata
* dylos-input.txt Debugging MySense.py test data (imitating Dylos sensor)
