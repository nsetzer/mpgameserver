#! cd .. && python -m demo.echoserver

from mpgameserver import EventHandler, ServerContext, TwistedServer
import logging

class EchoHandler(EventHandler):
    def __init__(self):
        super(EchoHandler, self).__init__()

    def connect(self, client):
        client.log.info("connect: %s", client)

    def disconnect(self, client):
        client.log.info("disconnect: %s", client)

    def handle_message(self, client, seqnum, msg):
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