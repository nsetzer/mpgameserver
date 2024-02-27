[Home](../README.md)

* [Echo Server Example](./example.md)
* [PyGame Example](docs/example2.md)
* [Getting Started](./GettingStarted.md)
* [Production Deployment](./ProductionDeployment.md)

# Example

* [Echo Server](#echo-server)
* [Echo Client](#echo-client)

## Echo Server

The Echo Server creates a minimally complete event handler that echoes messages back to the client.

The server can be run from the root of the checkout with:

```bash
python -m demo.echoserver
```

The full code is reproduced below.

```python
from mpgameserver import EventHandler, ServerContext, TwistedServer
import logging

class EchoHandler(EventHandler):
    def __init__(self):
        super(EchoHandler, self).__init__()

    def connect(self, client):
        client.log.info("connect: %s", client)

    def disconnect(self, client):
        client.log.info("disconnect: %s", client)

    def handle_message(self, client, msg):
        client.send(msg)

def main():

    logging.basicConfig(level=logging.DEBUG)

    host = "0.0.0.0"
    port = 1474

    ctxt = ServerContext(EchoHandler())

    server = TwistedServer(ctxt, (host, port))

    server.run()

if __name__ == '__main__':  # pragma: no cover
    main()
```

## Echo Client

The Echo Client connects to the server and then begins sending a message every second.
A KeyboardInterrupt will stop the client and gracefully disconnect

The client can be run from the root of the checkout with:

```bash
python -m demo.echoclient
```

The full code is reproduced below.

```python
from mpgameserver import UdpClient, Timer
import time
import sys

def main():  # pragma: no cover

    addr = ('localhost', 1474)
    client = UdpClient()

    dt = 0
    interval = 1/30

    def send_message():
        if client.connected():
            client.conn.send(b"hello")

    def onConnect(connected):
        if not connected:
            print("unable to connect to server")
            sys.exit(1)

    timer = Timer(.5, send_message)

    client.connect(addr, callback=onConnect)

    try:
        while True:
            timer.update(interval)
            client.update()
            while msg := client.getMessage():
                print(msg, "Latency: %dms" % int(1000*client.latency()))
            time.sleep(interval)
    except KeyboardInterrupt as e:
        pass

    client.disconnect()
    client.waitForDisconnect()

if __name__ == '__main__':
    main()
```
