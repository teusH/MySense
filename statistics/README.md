# Best fit Polynomial
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

The script is able to generate an image on a provided file of the graphs.

## Examples of use:
```bash
    python MyRegression.py --help
    python MyRegression.py --password XYZ -D luchtmetingen
    python MyRegression.py --password XYZ -D luchtmetingen  \
        table1/PM25/Datum/type table2/column_PM10//type2  \
        --timing yesterday/now --order 2 --show True
    python MyRegression.py -t "3 days ago/now" --multi=True \
        BdP_3f18c330/dhttemp//DHT22 BdP_8d5ba45f/dhttemp//DHT11
    python MyRegression.py --input dylos_rivm_tm020417.xlsx --SHOW True \
        -t '2017-03-14/2017-04-01 00:00:00' \
        groot33/3/2/DylosDC1100 groot38/5/2/DylosDC1100
    python MyRegression.py --input dylos_rivm_tm020417.xlsx --show True \
        -t '2017-03-14/2017-04-01 00:00:00' \
        groot33/3/2/DylosDC1100 groot38/5/2/DylosDC1100
```
The timing format is using the format as accepted by the Unix date command.

The output provide the polynomial factors (lowest order first) and R-square

Normalisation details and regression polynomial can be used to obtain calibration factors for MySense configuration. Note that if R-square is near zero there is no best fit, so calibration does not make much sense.

## OUTPUT
Statistical report: method used, Rsquared, average/deviation, and much details.

Output the graphs in an image file `--file`.

## DEPENDENCES
Install numpy (`pip install numpy`) for the regression calculations and pyplot (`pip install pyplot`) for displaying the graph.
Install SciPy for linear regression summaries `apt-get install python-statsmodels`.
## TO DO
1. Add multi linear regression: needs more thought/review

