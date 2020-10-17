[Home](../README.md)

* [Echo Server Example](./example.md)
* [PyGame Example](docs/example2.md)
* [Getting Started](./GettingStarted.md)
* [Production Deployment](./ProductionDeployment.md)

# Production Deployment Guide

> :warning: this guide is a work in progress

This guide will walk through the installation process of a game using mpgameserver.
While the guide is specific to Ubuntu 18.04 on Digital Ocean, the concepts
can be applied as needed to other environments.

By following this guide you will:

    - Install python 3.8 and dependencies
    - Configure the linux server in a secure way
    - Configure application secrets
    - Configure a linux service which can be used to start and stop the game
    - Configure a firewall to allow access to the game port (UDP 1474)

This guide is based on the following articals:

* [Digital Ocean Initial Setup](https://www.digitalocean.com/community/tutorials/initial-server-setup-with-ubuntu-18-04)

## Initial Configuration for a Digital Ocean Droplet

Create a daemon user for running the app named 'mpadmin'. In the example below, the user is not given a default shell.

> :beginner: This guide assumes 'mpadmin' as the user name, but it can be anything

```bash

sudo useradd -r -s /bin/false mpadmin

```

As the root user create the game directory and change ownership to
the game admin user.

> :beginner: This guide assumes 'mpgame' as the game directory name, but it can be anything

```bash
sudo mkdir /opt/mpgame
sudo chown mpadmin /opt/mpgame
sudo chgrp mpadmin /opt/mpgame

```



### Install Application

login as the admin user.

The user was not given a default shell for security reasons, this line logs in as that user and specifies a shell.

```bash
sudo su mpadmin -s /bin/bash
```

Create a virtual environment, Install dependencies.

```bash
python3.8 -m venv venv
pip install mpgameserver
```

Copy the game assets to `/opt/mpgame`. Make sure all files in the game directory
are owned by `mpadmin` and readable/writable only by that user and group.

### Application Secrets

Generate the game secrets once the virtual environment is set up and mpgameserver is installed.
The secrets will be owned by root and marked as readonly by root.

Generate a root key (`./crypt/root.key`) and make sure that it is only readble by root. The contents
of the key will be given to the game process when started as a service.

Then, distribute the public key (`./crypt/root.pub`) as part of the game client so that users can
authenticate your server.

> :warning: if you are currently logged in as mpadmin, type `exit` to revert to the original user.
> mpadmin should never be given root permissions, or the abililty to sudo.

```
cd /opt/mpgame
mkdir ./crypt
python -m mpgameserver genkey --name root ./crypt
sudo chmod 400 ./crypt/root.key
sudo chown -R root:root ./crypt
```

### Application Start Script

This is an example script to use for starting the game service.

Copy this script to `/opt/mpgame/start.sh` or to wherever the game is installed.

This script pipes the root key in to the game process stdin. The game should
read stdin at startup to receive the key.

> :information_source: There are other ways to solve the problem of passing the root key into the process, that won't be documented here

> :x: Don't pass the root key as an environment variable as it would provide an easy way for an attacker to extract the key.

```bash
#!/bin/bash
cd \$(dirname \$0)
source venv/bin/activate
PYTHON=\$(which python)
cat ./crypt/root.pem | exec sudo -E -u mpadmin unbuffer "\$PYTHON" server.py
```

### Application Service

create the following file:

`/etc/systemd/system/mpgame.service`

```
[Unit]
Description=run mpgame
After=network.target

[Service]
User=root
Group=mpadmin
WorkingDirectory=/opt/mpgame
Environment="PATH=/bin:/usr/bin:/usr/local/bin"
ExecStart=/opt/mpgame/start.sh

[Install]
WantedBy=multi-user.target
```

Enable and Start the service

```
sudo systemctl start mpgame
sudo systemctl enable mpgame
```

Check server status
```
sudo systemctl status mpgame
```

Check server logs.

> Useful if the server fails to start

```
sudo journalctl -u mpgame
```



### Firewall Configuration

Configure the firewall to enable UDP over port 1474.

If deplyoing to digital ocean, disable ufw and configure the firewall for the droplet

