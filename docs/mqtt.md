<img src="images/MySense-logo.png" align=right width=100>

# gas sensors from Spec
## Status
STATUS: BETA operational

## Description
The interaction with the Mosquitto (MQTT) broker has three types of operation:
1. mqtt as broker server.
This service is the central point of communication: the broker service.
The installation is fully independent of the other two:
2. the MQTTPUB publisher and
3. MQTTSUB subscriber MySense ouput/input modules/plugins.

The MQTT service will define the access point (hostname/port), user/password and access (ACL) rights for the node. (See later for more).

## INSTALLATION
MQTTPUB and MQTTSUB: 
    (missing pip? sudo install python-pip)
    sudo pip install paho-mqtt

MQTT broker server
    sudo apt-get install mqtt
You are strongly advised to add user/password for the publishing and subscriber user names.
The following programs are interesting for you:
```
mosquitto_passwd        add users/passwords for mosquitto
mosquitto_pub           try to publish a message for a topic
mosquitto_sub           try to subscribe to a topic
MySense uses dflt: IoS/<project>/<serialnr> as topics for sensor data messages.
```
As well to restrict publishing/subscribing for these users:
E.g. the file /etc/mosquitto/conf.d/local.conf:
```
    acl_file /etc/mosquitto/acl.conf
    allow_anonymous true
    # auth_plugin file_path
    # to do: https://github.com/jpmens/mosquitto-auth-plug
    clientid_prefixes IoS_
    # message_size_limit 5000
    password_file /etc/mosquitto/pwfile
    # add X.509 configuration
    # TO DO later
The prefix used for topcs is IoS_ (change this here and in the MySense config file)
```

and the authentication access control file /etc/mosquitto/acl.conf:
```
    user IoS
    pattern readwrite IoS/#
    user ios
    topic read IoS/#
    user BdP
    pattern readwrite IoS/BdP/#
    user MqTT
    topic read #
    topic write #
```
You need the user/password/hostname in the MySense config file.
* MqTT user for all messages
* IoS user for reading and writing
* ios user to subscribe to sensor data and to forrward it to another output channel.

## Testing your configuration
After the setup of the MQTT server e.g. use MySense `python MyMQTTPUB.py` to sent some data to your server. Please adjust hostname, user and password in the Conf dictionary first.

The mosquitto server deamon can be started not as daemon. The `-v` option will increase the verbosity, so you can warch connections in a separate window on your server.

The `topic` is defined by:
```
    Conf['topic']/ident 'project'/ident 'serial' e.g. IoS/BdP/+ (+ is wildcard)
```
The tegegram or message sent to the MQTT server is defined as json data:
```json
    { 'data': {}, 'metadata': {} }
```
You should be able to use the mosquitto subscription standard command:
```shell
    msquitto_sub -u ios -P acacadabra -h server_name -t IoS/BdP/+
```
