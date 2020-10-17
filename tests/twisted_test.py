
import unittest
from mpgameserver.twisted import ThreadedServer
from mpgameserver import ServerContext, EventHandler, EllipticCurvePublicKey, ConnectionStatus
from mpgameserver.client import UdpClient

from twisted.internet import reactor

import time

class TestHandler(EventHandler):

    def __init__(self):
        super().__init__()

        self._starting = False;
        self._shutdown = False;

    def starting(self):
        self._starting = True

    def shutdown(self):
        self._shutdown = True

    def handle_message(self, client, seqnum, msg: bytes):  # pragma: no cover
        client.send(msg)

ctxt = None
hdlr = None
server = None

class TwistedTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_1_run(self):
        global server, ctxt, hdlr

        addr = ('0.0.0.0', 14741)

        hdlr = TestHandler()
        ctxt = ServerContext(hdlr)
        server = ThreadedServer(ctxt, addr)
        server.start()

        time.sleep(.5)

        self.assertTrue(hdlr._starting)

    def test_2_connect(self):

        connected = None
        def callback(success):
            nonlocal connected
            connected = success

        client = UdpClient()
        client.connect(('localhost', 14741), callback=callback)

        t0 = time.time()
        while not connected:
            client.update()
            time.sleep(1/60)
            if time.time() - t0 > .5:
                self.fail("timed out")
        self.assertTrue(connected)
        self.assertTrue(client.connected())
        self.assertEqual(client.status(), ConnectionStatus.CONNECTED)
        self.assertTrue(client.token() > 0)

    def test_9_stop(self):
        global server, ctxt, hdlr

        server.stop()
        self.assertTrue(hdlr._shutdown)

def main():
    unittest.main()


if __name__ == '__main__':
    main()
