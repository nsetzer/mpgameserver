
import unittest
from threading import Lock
import os
import time
from mpgameserver import ServerContext, EventHandler, EllipticCurvePublicKey, ConnectionStatus, EllipticCurvePrivateKey
from mpgameserver.server import UdpServerThread
from mpgameserver.connection import PacketType, PacketHeader, Packet, ClientServerConnection

class MockUDPSocket(object):
    def __init__(self):
        super(MockUDPSocket, self).__init__()
        self.other = None

        self.recv = []

        self.lk = Lock()

    def sendto(self, datagram, addr):
        with self.lk:
            self.other.recv.append((datagram, addr))

    def recvfrom(self, *args):
        if self.recv:
            with self.lk:
                if self.recv:
                    return self.recv.pop(0)
        return None, None

    @staticmethod
    def mkpair():
        server = MockUDPSocket()
        client = MockUDPSocket()
        server.other = client
        client.other = server
        return server, client

class TestHandler(EventHandler):
    def handle_message(self, client, seqnum, msg: bytes):  # pragma: no cover
        client.send(msg)

class TestClient(object):
    def __init__(self, sock):
        super(TestClient, self).__init__()
        self.addr = ("0.0.0.0", 0)
        self.sock = sock
        self.conn = ClientServerConnection(self.addr)

        self.conn._sendClientHello()

    def send(self, payload, retry=-1, callback=None):

        self.conn.send(payload, retry=retry, callback=callback)

    def update(self, delta_t=0):

        self.conn.update()

        datagram, addr = self.sock.recvfrom(Packet.RECV_SIZE)
        if datagram:
            hdr = PacketHeader.from_bytes(False, datagram)
            self.conn._recv_datagram(hdr, datagram)

        pkt = self.conn._build_packet()
        if pkt:
            datagram = self.conn._encode_packet(pkt)
            self.sock.sendto(datagram, self.addr)

class Server1TestCase(unittest.TestCase):

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

    def test_server_start_stop(self):
        # test that a server can be started then stopped

        server_sock, client_sock = MockUDPSocket.mkpair()

        ctxt = ServerContext(TestHandler())
        thread = UdpServerThread(server_sock, ctxt)

        thread.start()

        ctxt._active = False

        # append an invalid packet to wake up the server
        thread.append(("0.0.0.0", 0), None, b"")
        thread.join()

    def test_server_connect(self):
        # test that a client can connect to the server
        server_sock, client_sock = MockUDPSocket.mkpair()
        client = TestClient(client_sock)

        ctxt = ServerContext(TestHandler())
        thread = UdpServerThread(server_sock, ctxt)

        thread.start()

        timedout=None
        def callback(success):
            nonlocal timedout
            timedout = not success

        client.conn.outgoing_timeout = .25
        client.conn.connection_callback = callback

        t0 = time.time()
        connected = False
        while not connected:
            datagram, addr = server_sock.recvfrom(Packet.RECV_SIZE)
            if datagram:
                hdr = PacketHeader.from_bytes(True, datagram)
                thread.append(addr, hdr, datagram)
            client.update()
            time.sleep(1/60)

            if time.time() - t0 > .5:
                self.fail("failed to connect")

            # test that both sides are connected
            if client.conn.status == ConnectionStatus.CONNECTED:
                for addr, other in ctxt.connections.items():
                    if other.status == ConnectionStatus.CONNECTED:
                        connected = True

        self.assertEqual(client.conn.status, ConnectionStatus.CONNECTED)
        self.assertFalse(timedout)

        ctxt._active = False

        # append an invalid packet to wake up the server
        thread.append(("0.0.0.0", 0), None, b"")
        thread.join()

    def test_server_connect_timeout(self):
        # test that a client can connect to the server
        server_sock, client_sock = MockUDPSocket.mkpair()
        client = TestClient(client_sock)

        timedout=None
        def callback(success):
            nonlocal timedout
            timedout = not success

        client.conn.temp_connection_timeout = .25
        client.conn.connection_callback = callback

        ctxt = ServerContext(TestHandler())
        thread = UdpServerThread(server_sock, ctxt)

        thread.start()

        t0 = time.time()
        connected = False
        while not timedout:
            # receive and drop packets
            server_sock.recvfrom(Packet.RECV_SIZE)
            client.update()
            time.sleep(1/60)

            if time.time() - t0 > .5:
                self.fail("failed to connect")

            # test that both sides are connected
            if client.conn.status == ConnectionStatus.CONNECTED:
                for addr, other in ctxt.connections.items():
                    if other.status == ConnectionStatus.CONNECTED:
                        connected = True
        self.assertEqual(client.conn.status, ConnectionStatus.DISCONNECTED)
        self.assertTrue(timedout)

        ctxt._active = False

        # append an invalid packet to wake up the server
        thread.append(("0.0.0.0", 0), None, b"")
        thread.join()

    def test_server_connect_invalid_key(self):
        # test that a client does not connect if the public key does
        # not match the server public key
        server_sock, client_sock = MockUDPSocket.mkpair()
        client = TestClient(client_sock)
        key = EllipticCurvePrivateKey.new()
        key2 = EllipticCurvePrivateKey.new().getPublicKey()

        client.conn.setServerPublicKey(key2)

        ctxt = ServerContext(TestHandler(), key)
        thread = UdpServerThread(server_sock, ctxt)

        thread.start()

        timedout=None
        def callback(success):
            nonlocal timedout
            timedout = not success

        client.conn.outgoing_timeout = .25
        client.conn.connection_callback = callback

        t0 = time.time()
        connected = False

        with self.assertRaises(EllipticCurvePublicKey.InvalidSignature):

            while not connected:
                datagram, addr = server_sock.recvfrom(Packet.RECV_SIZE)
                if datagram:
                    hdr = PacketHeader.from_bytes(True, datagram)
                    thread.append(addr, hdr, datagram)
                client.update()
                time.sleep(1/60)

                if time.time() - t0 > .5:
                    self.fail("failed to connect")

                # test that both sides are connected
                if client.conn.status == ConnectionStatus.CONNECTED:
                    for addr, other in ctxt.connections.items():
                        if other.status == ConnectionStatus.CONNECTED:
                            connected = True

        self.assertEqual(client.conn.status, ConnectionStatus.DISCONNECTED)
        self.assertFalse(timedout)

        ctxt._active = False

        # append an invalid packet to wake up the server
        thread.append(("0.0.0.0", 0), None, b"")
        thread.join()


class Server2TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        # launch a server thread, connect one client
        self.server_sock, self.client_sock = MockUDPSocket.mkpair()
        self.client = TestClient(self.client_sock)

        self.ctxt = ServerContext(TestHandler())
        self.thread = UdpServerThread(self.server_sock, self.ctxt)

        self.thread.start()

        t0 = time.time()
        connected = False
        while not connected:
            datagram, addr = self.server_sock.recvfrom(Packet.RECV_SIZE)
            if datagram:
                hdr = PacketHeader.from_bytes(True, datagram)
                self.thread.append(addr, hdr, datagram)
            self.client.update()
            time.sleep(1/60)

            if time.time() - t0 > .5:
                self.fail("failed to connect")

            # test that both sides are connected
            if self.client.conn.status == ConnectionStatus.CONNECTED:
                for addr, other in self.ctxt.connections.items():
                    if other.status == ConnectionStatus.CONNECTED:
                        self.server_client = other
                        connected = True



        self.assertEqual(self.client.conn.status, ConnectionStatus.CONNECTED)

    def tearDown(self):

        self.ctxt._active = False

        # append an invalid packet to wake up the server
        self.thread.append(("0.0.0.0", 0), None, b"")
        self.thread.join()

    def test_server_connection_keepalive(self):

        # sleep for 1 seconds to test send/recev keep alive
        for i in range(60):
            datagram, addr = self.server_sock.recvfrom(Packet.RECV_SIZE)
            if datagram:
                hdr = PacketHeader.from_bytes(True, datagram)
                self.thread.append(addr, hdr, datagram)
            self.client.update()
            time.sleep(1/60)

        self.assertTrue(self.client.conn.stats.received >= 10)

    def test_server_disconnect(self):

        # in the real world the client is not guaranteed to
        # receive the reply from the server.
        disconnected = False
        def onDisconnectCallback(success):
            nonlocal disconnected
            disconnected = True
        self.client.conn.disconnect(onDisconnectCallback)

        t0 = time.time()
        while not disconnected:
            datagram, addr = self.server_sock.recvfrom(Packet.RECV_SIZE)
            if datagram:
                hdr = PacketHeader.from_bytes(True, datagram)
                self.thread.append(addr, hdr, datagram)
            self.client.update()
            time.sleep(1/60)

            if time.time() - t0 > .5:
                self.fail("failed to receive disconnect")

    def test_server_send_recv(self):

        self.client.send(b"hello")

        t0 = time.time()
        while not self.client.conn.incoming_messages:
            datagram, addr = self.server_sock.recvfrom(Packet.RECV_SIZE)
            if datagram:
                hdr = PacketHeader.from_bytes(True, datagram)
                self.thread.append(addr, hdr, datagram)
            self.client.update()
            time.sleep(1/60)

            if time.time() - t0 > .5:
                self.fail("failed to receive")

    def test_server_send_recv_large(self):
        # send a large payload to the server
        # send the payload back to the client
        # test sending fragmented messages in both directions

        payload = os.urandom(10*1024)
        self.client.send(payload)

        # TODO: investigate why this takes .5 seconds
        # it should be 10KB / MAX_PAYLOAD_SIZE ~= 8 packets
        # round tripping 18 packets should take around 16/60 ~= 0.25 seconds
        # the test contsistently takes double the expected time

        t0 = time.time()
        while not self.client.conn.incoming_messages:
            datagram, addr = self.server_sock.recvfrom(Packet.RECV_SIZE)
            if datagram:
                hdr = PacketHeader.from_bytes(True, datagram)
                self.thread.append(addr, hdr, datagram)
            self.client.update()
            time.sleep(1/60)

            if time.time() - t0 > 1.0:
                self.fail("failed to receive message")

        self.assertEqual(self.client.conn.incoming_messages[0][1], payload)

    def test_server_timeout(self):
        # send a large payload to the server
        # send the payload back to the client
        # test sending fragmented messages in both directions

        timedout=False
        def callback(success):
            nonlocal timedout
            timedout = not success

        self.server_client.outgoing_timeout = .25
        self.server_client.send(b'test', retry=0, callback=callback)

        # TODO: investigate why this takes .5 seconds
        # it should be 10KB / MAX_PAYLOAD_SIZE ~= 8 packets
        # round tripping 18 packets should take around 16/60 ~= 0.25 seconds
        # the test contsistently takes double the expected time

        t0 = time.time()
        while not timedout:
            # receive and drop
            self.server_sock.recvfrom(Packet.RECV_SIZE)
            self.client.update()
            time.sleep(1/60)

            if time.time() - t0 > 0.5:
                self.fail("failed to receive message")

        self.assertTrue(timedout)

    def test_server_client_timeout(self):
        # send a large payload to the server
        # send the payload back to the client
        # test sending fragmented messages in both directions

        timedout=False
        def callback(success):
            nonlocal timedout
            timedout = not success

        self.client.conn.outgoing_timeout = .25
        self.client.send(b'test', retry=0, callback=callback)

        # TODO: investigate why this takes .5 seconds
        # it should be 10KB / MAX_PAYLOAD_SIZE ~= 8 packets
        # round tripping 18 packets should take around 16/60 ~= 0.25 seconds
        # the test contsistently takes double the expected time

        t0 = time.time()
        while not timedout:
            # receive and drop
            self.server_sock.recvfrom(Packet.RECV_SIZE)
            self.client.update()
            time.sleep(1/60)

            if time.time() - t0 > 0.5:
                self.fail("failed to receive message")

        self.assertTrue(timedout)

    def test_server_send_recv_multi(self):

        self.client.send(b"hello1")
        self.client.send(b"hello2")
        self.client.send(b"hello3")

        received = 0
        t0 = time.time()
        while len(self.client.conn.incoming_messages) < 3:
            datagram, addr = self.server_sock.recvfrom(Packet.RECV_SIZE)
            if datagram:
                received += 1
                hdr = PacketHeader.from_bytes(True, datagram)
                self.thread.append(addr, hdr, datagram)
            self.client.update()
            time.sleep(1/60)

            if time.time() - t0 > .5:
                self.fail("failed to receive")

        self.assertEqual(received, 1)
        self.assertEqual(len(self.client.conn.incoming_messages), 3)

    def test_server_duplicate_datagram(self):

        self.client.send(b"hello1")
        self.client.send(b"hello2")
        self.client.send(b"hello3")

        t0 = time.time()
        while self.server_client.stats.dropped == 0:
            datagram, addr = self.server_sock.recvfrom(Packet.RECV_SIZE)
            if datagram:
                hdr = PacketHeader.from_bytes(True, datagram)
                self.thread.append(addr, hdr, datagram)
                self.thread.append(addr, hdr, datagram)
            self.client.update()
            time.sleep(1/60)

            if time.time() - t0 > .5:
                self.fail("failed to receive")
        self.assertEqual(self.server_client.stats.dropped, 1)


    def test_server_datagram_corrupt(self):

        self.client.send(b"hello1")

        t0 = time.time()
        while self.server_client.stats.dropped == 0:
            datagram, addr = self.server_sock.recvfrom(Packet.RECV_SIZE)
            if datagram:
                # valid header, invalid tag
                datagram = datagram[:-16] + b'0'*16
                hdr = PacketHeader.from_bytes(True, datagram)
                self.thread.append(addr, hdr, datagram)
            self.client.update()
            time.sleep(1/60)

            if time.time() - t0 > .5:
                self.fail("failed to receive")
        self.assertEqual(self.server_client.stats.dropped, 1)

def main():
    unittest.main()


if __name__ == '__main__':
    main()
