

import unittest
from threading import Lock
import os
import time
import socket
import select
from mpgameserver import ServerContext, EventHandler, EllipticCurvePublicKey, ConnectionStatus
from mpgameserver.client import UdpClient
from mpgameserver.server import UdpServerThread
from mpgameserver.context import ServerContext
from mpgameserver.connection import PacketType, PacketHeader, \
    Packet, ClientServerConnection, ServerClientConnection, ConnectionStatus


class TestHandler(EventHandler):
    def handle_message(self, client, seqnum, msg: bytes):  # pragma: no cover
        client.send(msg)

def recvinto(sock, thread):
    r, w, x = select.select([sock], [], [], 0)
    if r:
        datagram, addr = sock.recvfrom(Packet.RECV_SIZE)
        hdr = PacketHeader.from_bytes(True, datagram)
        thread.append(addr, hdr, datagram)

class Client1TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cls.addr = ('0.0.0.0', 14740)
        cls.ctxt = ServerContext(TestHandler())


        cls.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cls.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        cls.sock.bind(cls.addr)

        cls.thread = UdpServerThread(cls.sock, cls.ctxt)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):

        cls.ctxt._active = False

        # append an invalid packet to wake up the server
        cls.thread.append(("0.0.0.0", 0), None, b"")
        cls.thread.join()

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_client_simple(self):

        connected = None
        def callback(success):
            nonlocal connected
            connected = success

        client = UdpClient()
        client.connect(('localhost', 14740), callback=callback)

        t0 = time.time()
        while not connected:
            recvinto(self.sock, self.thread)
            client.update()
            time.sleep(1/60)
            if time.time() - t0 > .5:
                self.fail("timed out")
        self.assertTrue(connected)
        self.assertTrue(client.connected())
        self.assertEqual(client.status(), ConnectionStatus.CONNECTED)
        self.assertTrue(client.token() > 0)

        client.disconnect()

        # normally the server is threaded, and we can avoid this part
        client.update()
        time.sleep(1/60)
        client.update()
        recvinto(self.sock, self.thread)

        # now that all messages have been sent/received, wait
        # for the disconnect
        client.waitForDisconnect()


        #self.assertTrue(client.disconnect_acked)

        self.assertEqual(client.status(), ConnectionStatus.DISCONNECTED)


    def test_client_send_recv(self):

        connected = None
        def callback(success):
            nonlocal connected
            connected = success

        client = UdpClient()
        client.connect(('localhost', 14740), callback=callback)

        t0 = time.time()
        while not connected:
            recvinto(self.sock, self.thread)
            client.update()
            time.sleep(1/60)
            if time.time() - t0 > .5:
                self.fail("timed out")

        self.assertTrue(connected)
        self.assertTrue(client.connected())
        self.assertEqual(client.status(), ConnectionStatus.CONNECTED)
        self.assertTrue(client.token() > 0)


        # --------------------------------------------------------------------
        # --------------------------------------------------------------------

        client.send(b"test1", retry=0)
        client.send(b"test2", retry=0)

        t0 = time.time()
        while not client.hasMessages():
            client.update()
            recvinto(self.sock, self.thread)
            time.sleep(1/60)
            if time.time() - t0 > .5:
                self.fail("timed out")

        seq1, msg1 = client.getMessage()

        self.assertEqual(msg1, b"test1")

        msgs = client.getMessages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0][1], b"test2")


        # --------------------------------------------------------------------
        client.disconnect()

        # normally the server is threaded, and we can avoid this part
        client.update()
        time.sleep(1/60)
        client.update()
        recvinto(self.sock, self.thread)

        # now that all messages have been sent/received, wait
        # for the disconnect
        client.waitForDisconnect()


        #self.assertTrue(client.disconnect_acked)

        self.assertEqual(client.status(), ConnectionStatus.DISCONNECTED)


def main():
    unittest.main()


if __name__ == '__main__':
    main()
