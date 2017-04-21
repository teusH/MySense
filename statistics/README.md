# Best fit Polynomial
## STATE
operational: 11-04-2017
## DESCRIPTION
Calculates the best fit polynomial for two timed rows of values. The (time,value) tuples are taken from a database table. Database credentials can be defined as environment variables.

Polynomial order (order 1 is linear regression best fit line) can be defined from the command line.

The graphs can be shown (default it is turned off) as a graph plot using pyplot.

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
## TO DO
0. Input to be read e.g. via `panda` python library for: CSV, xlsx spreadsheet, an others.
1. Add multi regression best fit (best fit hyper plane to more dependences per value (multi column). More columns in one table.
2. All multi dimentional regression to more then two tables.

