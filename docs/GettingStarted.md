[Home](../README.md)

* [Echo Server Example](./example.md)
* [PyGame Example](docs/example2.md)
* [Getting Started](./GettingStarted.md)
* [Production Deployment](./ProductionDeployment.md)

# Getting Started Guide

The goal of this document is to provide a complete template which can be used to start a new multi-player game.

## Server

This is a complete example of the boilerplate code needed for a multiplayer server
```python

import os
import sys
import logging

from mpgameserver import EventHandler, ServerContext, TwistedServer, \
    GuiServer, EllipticCurvePrivateKey

class MyGameEventHandler(EventHandler):

    def starting(self):
        pass

    def shutdown(self):
        pass

    def connect(self, client):
        pass

    def disconnect(self, client):
        pass

    def update(self, delta_t):
        pass

    def handle_message(self, client, seqnum, msg):
        pass

def main():
    """
    Usage:
        python template_server.py [--gui]

        --gui : optional, display the metrics UI
    """

    # bind to an IPv4 address that can be accessed externally.
    host = "0.0.0.0"
    port = 1474
    key = None

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)-15s %(levelname)s %(filename)s:%(funcName)s():%(lineno)d:%(message)s')

    ctxt = ServerContext(MyGameEventHandler())

    # command line switch controls running in headless mode (default)
    # or with the built-in gui server
    if '--gui' in sys.argv:
        server = GuiServer(ctxt, (host, port))
    else:
        server = TwistedServer(ctxt, (host, port))

    server.run()

if __name__ == '__main__':
    main()


```

## Client

This is a complete example of the boilerplate code needed for a pygame multiplayer game.

```python

import sys
import pygame
from mpgameserver import UdpClient, EllipticCurvePublicKey

bg_color = (0,0,200)

def onConnect(connected):
    global bg_color

    if connected:
        # on connection success change the background to green
        bg_color = (0,200,0)
    else:
        # on connection timeout change the background to red
        bg_color = (200,0,0)

def main():
    """
    Usage:
        python template_client.py [--dev]

        --dev: optional, use development keys
    """
    pygame.init()

    clock = pygame.time.Clock()
    FPS = 60
    host = 'localhost'
    port = 1474

    screen = pygame.display.set_mode((640, 480))

    client = UdpClient()
    client.connect((host, port), callback=onConnect)

    while True:

        dt = clock.tick(FPS) / 1000

        # TODO: process events, update game world, render frame, send messages

        screen.fill(bg_color)

        client.update()

        for msg in client.getMessages():
            try:
                # TODO: process message
                print(msg)
            except Exception as e:
                logging.exception("error processing message from server")

        pygame.display.flip()

    pygame.quit()

    if client.connected():
        client.disconnect()
        client.waitForDisconnect()

if __name__ == '__main__':
    main()

```


## Project Structure

Both the client and server will need to send and receive byte encoded messages.
It makes sense to separate the common logic into a separate package.
The following is an example directory hierarchy for structuring the files.

```

mygame/
    client/
        __init__.py
        client.py
    server/
        __init__.py
        server.py
    common/
        __init__.py
        message.py
```

## Message encoding

This Gaffer on Games article on [Reading and Writing Packets](https://www.gafferongames.com/post/reading_and_writing_packets) does a good job of explaining the motivation of a byte representation of messages.

It is highly recommended to use a third party library for encoding messages.
For example, [protobuf](https://pypi.org/project/protobuf) or [msgpack](https://pypi.org/project/msgpack)

Read [Serialization](serializable.md) for more information.