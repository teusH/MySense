# example of obtaining CSV formatted filr with measurments of a municipality Beverwijk
# and use the CSV file to generate an interactive map for a browser to visualise the nodes.
python3 Things2CSV.py Expand='location,address,owner,project' Sensors='(pm25|pm10|temp|rv)' Period='2019-01-01,2026-01-01' Verbosity=3 User='Hollandse Luchten' File='Beverwijk.csv' Verbosity=3 Select='^(?!(HLL_hl_device_(291|024)|LTD_8207|LTD_47544)).*$' 'Beverwijk'
python3 Things2HTML.py Title=Beverwijk File=maps/ Beverwijk.csv
