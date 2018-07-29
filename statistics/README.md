# Delete outiers and spikes from measurments
## STATE
* scatter plotting and outliers removal operational: 17-07-2018.
* average spline plotting in beta: 27-07-2018.
* correction factor weighted curved fitting: in development.
# DESCRIPTION
The grubb.py script will walk throught the database for a period op time *invalidating* the measurement value in de database as follows:
- outliers which are manually configured for each type of measurment
- so called spikes: values which are filtered out with the Grubb Z-score.

A sliding window size on the command line  of the filtering can be defined to research a better Z-score elimation. By default (option) the script will first reset the validate boolean of the measurment.

Use the help option to obtain a glance into all options of the script.

The script may show <img src="reports/PM25-PM10-June2618.png" align=right height=150> a chart with all scatter graphs visualising the valid measurements, the spikes and the outliers.
On UNIX machinery one is able to zoom and scroll through the chart interactively.

The graphs can be: scatter plot of measurements, average spline plot (average per period of time, dft one hour), average spline plot of corrected values with instalable correction factor per pollutant.
To Do: with ref. measurements collect a (weighted) correction factor via curved fitting technic.

De note that Z-score is defined on values sets larger as 15 values. Best is if the values have a Normal distribution.
On dust measurements the script seems to work well enough. Note that the measurement values will not be altered by the script.
To Do: use a better algorithm to enable automatic outlier filtering.

The advise is to use `grubb.py` first before using the regression script.

Currently the script uses the MySQL database configuration as defined by MySense.

To Do: add best fit polynomial to the measurement graph in the chart.

# Regression: Best fit Polynomial
## STATE
operational: 11-04-2017
## DESCRIPTION
Calculates the best fit polynomial for at least two timed rows of values. The (time,value) tuples are taken from a database MySQL table (default), xlsx spreadsheet or CSV file.
There is support for multi linear regression calculation (--multi modus).

Database credentials can be defined as environment variables.
For linear regression give statistical summary (e.g. R-squared and others).

For spreadsheet input you need to have Python pandas (`apt-get install python-pandas`) installed.

Polynomial order (order 1 is linear regression best fit line) can be defined from the command line.

The arguments define the table/column/sensor_date_column_name/sensor_type (database) or name/column_nr/date_column_nr/sensor_type (spreadsheet) to be used to collect measurement values. For an empty name (or column nr)  the name of the previous argument will be used.

The command with no arguments an overview of tables or column numbers will be shown of the input resource. One argument will give details details of named table(s) (column names) of the database table(s). Table names can be delimited with a / character. 

The graphs can be shown (default it is turned off) as a graph plot using pyplot.
The -show True will show in an X11 window the scatter graph. The -S True option will also show the graph(s) of the measurements per time frame.

The script is able to generate an image in PNG format on a provided path/file of the graphs.

## Examples of use:
```bash
    python MyRegression.py --help
    # default sensor values from MySQL database over default (24 hours) period
    # DB credentials taken from command environment
    # shows tables, sensor names no graphs
    DBUSER=metoo DBPASS=acacadabra python MyRegression.py --password XYZ -D luchtmetingen
    # show for period yesterday till now table1 and table2 sensorkits graphs
    # polinomial info upto order 2 (default is linear or order 1)
    python MyRegression.py --password XYZ -D luchtmetingen  \
        table1/PM25/Datum/type table2/column_PM10//type2  \
        --timing yesterday/now --order 2 --show True
    # over 3 day period in multi modus
    python MyRegression.py -t "3 days ago/now" --multi=True \
        BdP_3f18c330/dhttemp//DHT22 BdP_8d5ba45f/dhttemp//DHT11
    # use data from XLSX spreadsheet for a period last two weeks in March
    # spreadsheet columns 3 and 5, time defined in col 2
    python MyRegression.py --input dylos_rivm_tm020417.xlsx --SHOW True \
        -t '2017-03-14/2017-04-01 00:00:00' \
        groot33/3/2/DylosDC1100 groot38/5/2/DylosDC1100
    # use measurements from influxdb server
    # note: one must have admin db server credentials to show list of databases
    # next will show overview of measurements on InFluxDB server
    DBUSER=metoo DBPASS=acacadabra DBHOST=behouddeparel.nl python MyRegression.py -T influx BdP_33040d54
    # use measurents on the server for period of last 24 hours and show graph
    # output in HTML format, graphs are saved in PPD42NS.png file.
    DBUSER=metoo DBPASS=acacadabra DBHOST=theus.xs4all.nl python MyRegression.py -T influx -HTML --file PPD42NS.p0ng BdP_33040d54/pm25_pcsqf/time/PPD42NS/raw BdP_3f18c330/pm25_pcsqf/time/PPD42NS/raw
```
The timing format is using the format as accepted by the Unix date command.

The output provide the polynomial factors (lowest order first) and R-square

Normalisation details and regression polynomial can be used to obtain calibration factors for MySense configuration. Note that if R-square is near zero there is no best fit, so calibration does not make much sense.

## Correlation report generator (HTML and/or PDF)
The shell command file `MakeReports.sh` uses an influxdb server (DBHOST) with credentials (DBUSER/DBPASS) to extract `raw` measurment values and generate correlation report in HTML and PDF (make sure you install the html to pdf converter /usr/local/wkhtmltox/bin/wkhtmltopdf from wkhtmltopdf.org) formats.
```shell
Makereport.sh help
DBHOST=localhost DBUSER=myname DBPASS=acacadabra START=2017-07-01 END=now Makereport.sh dust temp rh
```

## OUTPUT of MyRegression.py
Statistical report: method used, Rsquared, average/deviation, and much details.

Output the graphs in an image file `--file`. Use `--HTML` option to turn output in html format on.

As an example to generate an HTML correlation report report for several sensors over several sensor kits the bash shell script `MakeReports.sh` is supplied. It takes raw measurements (one per minute) for different sensors (Dylos, SDS011, PPD42NS, DHT22, BME280) from several sensor kits in the project BdP in the time period from 20th of June. The average interval of 900 seconds is used to limit the values a bit and smooth the outliers. Note that longer periods as eg one week just gives too much values and the overview becomes difficult.

## DEPENDENCES
Install numpy (`pip install numpy`) for the regression calculations and pyplot (`pip install pyplot`) for displaying the graph.
Install SciPy for linear regression summaries `apt-get install python-statsmodels`.

## TO DO
1. Add multi linear regression: needs more thought/review
2. Support database/spreadsheet per sensor (now: only one database/spreadsheet)

