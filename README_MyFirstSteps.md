## My First Steps
### Intro
For the first steps with MySense we make use of a Pi (hopefully a Pi 3) with eg Jessie installed as Linux OS. See the various Pi install instruction for a How To install Debian Jessie on the Pi. Use a Pi say with a micro SD card of about 32GB. Hook the Pi up with internet and login as pi user.

At first one is advised to use the Python debugger and step throught the MySense main module. The main MySense routine is `sensorread`. So set the break to this routine.
If anythings break the debugger will give you much inside what is going wrong.
### Step 1
Installation of MySense as simple as possible with one input sensor (we use the build in wifi rssi as sensor in the case) and one output channel: console.

1. update the Linux OS:
```shell
sudo apt-get update
sudo apt-get upgrade
sudo install python git pip
```
2. install Internet of Sense user "ios":
```shell
sudo useradd ios
sudo passwd ios # and remember the password entered
```
3. login as user ios:
```shell
ssh ios@localhost
```
4. get the MySense software:
```shell
git clone https://github.com/teusH/Mysense
cd MySense
# and see the MySense command line options
python MySense.py --help
```
### Step 2 your first real simple sensor
(Remote) login as the ios user and go to the MySense working directory `cd MySense`.
1. Configure the MySense configuration file with as input plugin the Pi build-in wifi signal strength "sensor":
```
cp MySense.conf.example MySense.conf # copy
ed MySense.conf # edit with your favorite editor
```
Edit the MySense.conf file and decomment the part of `[rssi]`
2. And run MySense:
```shell
python MySense.py -i rssi -o console -l debug
```
That's it!

If you are not so confident with the first step use the Python debugger `pdb` as:
```shell
pdb MySense.py -i rssi -o console -l debug
```
And set the break to the main routine as follows: `b sensorread` and step via the debug command `n` (next) till the input plugin entry as `getdata`. Step in via `s` debug command into the routine if you want to or net to `Out` the output channel part.

If the rssi wifi signal strength is available from the Pi you will see every minute the signal strength on the Pi console.
### Step 3 attach a real sensor e.g. temperature
Do the steps after Step 2 one by one: sensor plugin or output channel.
Use e.g. a meteo sensor from Adafruit e.g. DHT22 or BME280 (better one). See the dht.md or bme280.md documentation file for a detailed how to.

What you need to do is install the hardware (for simplicity use Grove shield and Grove modules so you does not need to use soldier). Attach the hardware on the Digital data sockets and use the numbers as proposed in the MySense configuration file.

Decomment the `[dht]` or `[bme280]` section in the configuration file.

Install the Adafruit libraries on the Pi. Or use the `MyINSTALL.sh DHT` to do it for you.

And try it:
```shell
pdb MySense.py -i dht -o console -l debug
b sensorread
n ...
```
At first things go wrong. The input channel uses multi threading: the input plugin will run in the background and delivers every sample unit of N seconds (default a minute) the collected measurement to the MySense part. A command interrupt (<cntrl>C) will stop MySense but NOT the input sensor thread. Stop the process as follows: hit the key <cntrl>z (pauze command) and use `kill %1` to kill the process.

### Step 4 attach an output channel
Attach e.g. a database output channel. See the documentation for mysql.md for the steps: installation of mysql client Python library. Configration of user access credentials to the database and configuration of the database. MySense will add the tables and sensor columns automatically if the user credentials are allowed to do so.

Enable the `[mysql]` section in the MySense configuration file and define the MySQL user access credentails there.

And try it:
```shell
python MySense.py -i dht -o console,db
# or python MySense.py start
```
### Next steps
What you need to understand:
1. input sensor plugins run in the background as threads
2. input and output channels and needed libraries for the modules are only used if the corresponding section is defined in the MySense configuration file.
3. input and output channels can be switched on and off in the configuration file. The modules will if switched off be unloaded by MySense. 
4. input and output channels switched on from the command line will overwrite the input/output switch from the configuration file.
5. If an input broker plugin is switched on MySense will act as proxy. So MySense can be used to chain MySense instances from sensor input reader to another MySense which pushed the data to other output channels as databases, spreadsheets, etc.

