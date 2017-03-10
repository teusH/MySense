# REMOTE ACCESS to Pi
To easy remote control of the Pi and MySense you may install a backdoor.
A backdoor will weaken your Pi as others may access the Pi by using credentials or weak points on the Pi.

Remote control of the Pi is impossible if your Pi cannot be accessed via internet or the wifi is not configured as wifi Access Point (see hostap/virtual wifi installation part).

There are three ways default ways to have remote management of the Pi installed:
0. access via wifi via wifi host access point installation. Use INSTALL.sh.
Access the Pi on IPV4 address: 10.0.0.1 (dflt) , and wifi (defaults) MySense/BehoudDeParel.
1. ssh
2. ssh with a tunnel to your main (home) server
3. webmin (system management via web interface) on default port 10000
4. Pi access services as Weaved (remote3.it)

## ssh access
### local ssh access
If the Pi is directly (not behind a firewall/router) accessable, e.g. local, and you know the IP number you should be able to access the Pi via `ssh pi@IPNUMBER` or use `Putty`.
Usualy the router or better dhcp server will show you the IPV4 number of the Pi.
Advised is to configure the router always to lease the same IP number.

Generate on both sites (Pi and PC/laptop) an ssh key, and transfer it to the other:
```shell
    ssh-keygen   # no password, less secure it saves the trouble on each ssh run
    /usr/bin/ssh-copy-id other-side-user@other-side-IP-number
```
Warning: no password protection on the identity key is less secure: key can be stolen.
### remote ssh access
This is hacking for dummies...

If you do not have direct access to any port of the Pi from internet:

You may install a simple shell file which is run in the back ground and watching the tunnel to stay alive. Say every 10 minutes from crontab. Install the file in `/usr/local/bin/watch_my_tunnel.sh`.
```shell
    #!/bin/bash
    # note the identity should be for Pi user root in /root/.ssh/!
    ME=${1:-me}            # <--- your local user name
    IP=${2:-my-laptop-IP}  # <--- your local IP number, must be a static number
    # generate/copy key as root first!
    if ! /bin/nc -w 1 -z ${IP} 22 ; then exit 1 ; fi     # is there connectivity?
    if ! /bin/ps ax | /bin/grep "ssh -R 10000:" | grep -q $ME # is tunnel alive?
    then
        /usr/bin/ssh -R 10000:localhost:10000 "${ME}@${IP}" -nTN & # webmin
        echo "Watchdog restart tunnel to ${ME}@${IP}:10000 for webmin"
    fi
    if ! /bin/ps ax | /bin/grep "ssh -R 10001:" | grep -q "$ME" # is tunnel alive?
    then
        /usr/bin/ssh -R 10001:localhost:22 "${ME}@${IP}" -nTN &    # ssh
        echo "Watchdog restart tunnel to ${ME}@${IP}:10001 for ssh"
    fi
    exit 0
```
And use `crontab -e` to add `*/10 10-23 * * * /usr/local/bin/watch_my_tunnel.sh user IP-number`.

This creates and maintains two tunnels to access the Pi via port on my-laptop-IP:
1. http for webmin. Acces via your laptop browser on https://localhost:10000
2. ssh access to the Pi via `ssh -p 10001 pi@localhost`

TO DO: use eg netcat and (proxy) key server to cure the following:
Disadvantage: if your laptop or server changes from IP number or new OS install the authorisation key will be unknown and your ssh tunnel will be gone forever.

Script kiddies, please have fun somewhere else.

## webmin
The standard way to do system administration work on a Linux machine as eg the Pi via a browser interface is `webmin`.
When installed eg via the INSTALL.sh script (takes quite some time to install) you can access webmin via wifi Access Point, internet or via remote ssh.

## Weaved or remote3.it
Weaved services (free try) a tunneling via internet to your Pi. For this a weaved connect deamon needs to be installed on your Pi. From anywhere with your weaved login credentials you are able to access the tunnel to your Pi, e.g. ssh port 22 and/or webmin 10000 port.
Create a free "try" account with Weaved.com and use the INSTALL.sh script to install weaved. The try-account gives is free for maximum of 5 devices and 30 minutes connect time.
TO DO: webmin operates via https. Did not get it working yet.

Reminder: a third party knowing the prxy port is able to use the backdoor. Or anyone else who has access to the proxy port number or guessing that number served to you by Weaved.

Advantage: you can group Pi's together and use one script to eg update all your Pi's.
