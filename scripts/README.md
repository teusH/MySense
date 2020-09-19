<img src="../RPi/images/MySense-logo.png" align=right width=100>

# MySense
Last update of the README on 29 June 2020

## Description
Various scripts to maintain and manage MySense measurements.

### Outline
MySense measurements from the measurements kits arrive via LoRaWan (The Things Network) to a server which interfaces to Internet via Mosquitto (MQTT).

From there *TTN-datacollector* will do data acqui9sition into a MySQL database, forward measurements to various data portals like Luftdaten.info and dependent (sub) dataportals like RIVM Nld, AirTube, etc., as well maintain/manage the measurements via email/Slack notices.
In this way keep track of the behaviour of known, noit yet regsitrated measurement kit and out of band measurements and kit events.

### TTN-datacollector
Use: data acquisition, data forwarding, kit maintenance

Use --help option to obtain various options. The data collector will use a color scheme to prioritise messages and loggings. The data collector is able to log to a pipe.
TTN-datacollector has a monitor output channel to view status.

TTN-datacollector will use various general library routines. The library routines can be used stand alone.
Like:
- MyLogger.py logging routines (multi threaded)
- MyCONSOLE.py full output to terminal
- MyLUFTDATEN.py forwarder to Luftdaten.info
- MyDB.py forwarder to MySQL measurements database
- MyPrint.py  logging
- WebDB.py website database interface

### MyDB
Use: database library module and meta info DB insertion
The module can be used in stand alone version. The use is to insert meta measurement
kit information (location, oeperational details, ect) into the database tables Sensors (lataion details,...) and TTNtable (TTN forwarding, database data forwarding).

### GeneratePMcharts
Use: visualisation, data filtering, data correction, calibration

Bash shell script a wrapper to maintain (filter spikes) measurements in the database, generate various graphs on CMS (Drupal) website, generate overviews of measurements, etc.

The script uses FilterShow.py (spikes removal), ChartsPM.pl (HighCharts website page graphs).

### SyncWebDB
Use: meta data maintenance

Synchronize and update visa versa measurement kit meta information between website database pages and measurements database.
SyncWebDB uses WebDB.py (website database interface), AirQualityIndex.pl (LKI marker coloring) and MyDB.py (measurements database interface).

### CheckDeadSensors
Use: check for malfunctioning and not active measurement kits over a long period.
Send notices if problems are detected.

Use DB environment variables for database credentials definitions. REGION and arguments may be string patterns as supported by regexp of MySQL. Use command help for help.
Script will save dates of sent notices and will only resend email notices again after 3 days.
