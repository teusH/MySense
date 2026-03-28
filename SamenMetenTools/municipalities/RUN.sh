# example how to run some Samen Meten Tools
# obtain records in CSV file with Thins in a municipality e.g. Beverwijk in a period of time
python3 Things2CSV.py Expand='location,address,owner,project' Sensors='(pm25|pm10|temp|rv)' Period='2019-01-01,2026-01-01' Verbosity=3 User='Hollandse Luchten' File='Beverwijk.csv' Verbosity=3 Select='^(?!(HLL_hl_device_(291|024)|LTD_8207|LTD_47544)).*$' 'Beverwijk'
# generate from the CSV file an HTML file for an interactive map with the Things node locations
python3 Things2HTML.py Title=Beverwijk File=maps/ Beverwijk.csv
