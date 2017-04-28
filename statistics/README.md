# Best fit Polynomial
## STATE
operational: 11-04-2017
## DESCRIPTION
Calculates the best fit polynomial for two timed rows of values. The (time,value) tuples are taken from a database MySQL table (default) or xlsx spreadsheet. Database credentials can be defined as environment variables.
For linear regession give statistical summary (e.g. R-squared and others).

For spreadsheet input you need to have Python pandas (`apt-get install python-pandas`) installed.

Polynomial order (order 1 is linear regression best fit line) can be defined from the command line.

The arguments define the table/column/sensor_date_column_name/sensor_type (database) or name/column_nr/date_column_nr/sensor_type (spreadsheet) to be used to collect measurement values. For an empty name (or column nr)  the name of the previous argument will be used.

The command with no arguments an overview of tables or column numbers will be shown of the input resource. One argument will give details details of named table(s) (column names) of the database table(s). Table names can be delimited with a / character. 

The graphs can be shown (default it is turned off) as a graph plot using pyplot.
The -show True will show in an X11 window the scatter graph. The -S True option will also show the graph(s) of the measurements per time frame.

The script is able to generate an image on a provided file of the graphs.

Example of use:
```bash
    python MyRegression.py --help
    python MyRegression.py --password XYZ -D database  \
        -1 table/column/type -2 table2/column2/type2  \
        --timing yesterday/now --order 2 --show True
```
The timing format is using t5he format as accepted by the Unix date command.

The output provide the polynomial factors (lowest order first) and R-square

Normalisation details and regression polynomial can be used to obtain calibration factors for MySense configuration. Note that if R-square is near zero there is no best fit, so calibration does not make much sense.
## DEPENDENCES
Install numpy (`pip install numpy`) for the regression calculations and pyplot (`pip install pyplot`) for displaying the graph.
Install SciPy for linear regression summaries `apt-get install python-statsmodels`.
## TO DO
0. Input to be read e.g. via `panda` python library for: CSV and other input formats.
1. Add multi regression best fit (best fit hyper plane to more dependences per value (multi column). More columns in one table.
2. All multi dimentional regression to more then two tables.

