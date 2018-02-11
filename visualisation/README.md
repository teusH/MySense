<img src="images/MySense-logo.png" align=right width=100>

### STATUS
operational 2018/01/12

### DESCRIPTION
<img src="images/HighCharts.png" align=right width=200>
The ChartsPM.pl Perl script will generate the HTML body of a webpage with using HighCharts graphs for visualisation of measurments. The measurments are taken from a MySQL database using measurments values over a period of time and location meta information.

In debug modus a full HTML page will be gebarted, so the graphs can be locally shown with a browser.

### USAGE
Use the perl script with --help so look into the many commandline options to choose from.

The script has the possibility to generate two or more charts on one webpage. A button will be generated which allows the end user to select a particular chart of graphs.


```shell
    DBUSER=me DBPASS=acacadabra DBHOST=localhost perl ./ChartsPM.pl \\
        --pollutants pm10,pm25 --buttons PM10,PM2.5 \\
        --debug --verbose --web /tmp \\
        --last now --output OutputPage \\
            Vuurwerk_Sensorkit1 Vuurwerk_Sensorkit2 HadM
```

* DBUSER etc. defines the database credentials
* buttons/pollutants to switch from PM10 (dflt) table into PM2.5 table.
* Option `--debug` will force debug modus (complete HTML page OutputPage.html in the directory /tmp) 
* last defines measurements available up to now, default period is 3 weeks

### APPLICATION
The graphs on the chart will allow to visualize the correlation between different sensorkits as well sensors.

Experimental: the `--correct` option will enable an apllication of a correction coeeficient to PM measurments. The rel. humidity of the station or neighbour will be used to apply a correction. The coefficient is a best fit calculated from PM measurments and humidy of a reference station. This is fully experimental yet.
