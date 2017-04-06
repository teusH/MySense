# Sensordata output to (MySQL) database
## STATUS
operational from 2017/02/26
internet connectivity failure recovery not yet fully tested

## DESCRIPTION
Output sensor description and measurements to database: MySQL.

* per sensors box: For every MySense instance a table (`<project>_<serial>`) with archiving  date/time of entry, update, values of pollutants and meteo data.
* The table `Sensors` will archive the sensor instance identification information as eg location, start time, last seen data, activity, different installed sensors information.

Use eg. phpadmin or Sequel Pro (both are free applications) to easily view the archived data. And use Behoud de Parel visualisation tooling for producing graphs on your website.

## CONFIGURATION
Provide a name for the database (e.g. luchtmetingen), hostname (e.g. DatabaseHost.com) of MySQL server, user/password (e.g. myname and acacadabra) as access credentials
in the `MySense.conf` init file.

## DEPENDENCIES
Install dependenzies via the install script `./INSTALL.sh DB` or manually install the python mysql client library:
```bash
apt-get install python-mysql.connector
```
`apt-get install mysql-client` or a gui mysql-navigator if you need to access MySQL server from the command line or graphical interface.

## MySQL INSTALLATION as server
Install the database MySQL on your server (if not already present). See yout OS distribution for the instructions.

Create the database for MySense. Use the database name, host name and user name/password as you have defined in MySense.conf .
Access the MySQL database as superuser:
```bash
    mysql -u root -p
```
And create the database:
```mysql
    mysql> CREATE DATABASE IF NOT EXISTS your_database_name;
```
and add the MySense user (use '%' for localhost as wildcard for access from every host):
```mysql
    mysql> CREATE USER 'newuser'@'localhost' IDENTIFIED BY 'password';
    mysql> GRANT ALL PRIVILEGES ON * . * TO 'newuser'@'localhost';
    mysql> FLUSH PRIVILEGES;
    mysql> QUIT
```
AND *WRITE* a big sign above your bed to restrict this user for security reasons later.

MySense will create and extend the tables and table columns automaticalty when needed so.
