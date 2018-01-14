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


``shell
perl ./ChartsPM.pl --debug --verbose --web /tmp --pollutants pm10,pm25 --buttons PM10,PM2.5 --last now --output OutputPage Vuurwerk_Sensorkit1  Vuurwerk_Sensorkit2 HadM
```
* Option `--debug` will force debug modus (complete HTML page OutputPage.html in the directory /tmp) 
* button to switch from PM10 (dflt) table into PM2.5 table.

### APPLICATION
The graphs on the chart will allow to visualize the correlation between different sensorkits as well sensors.
