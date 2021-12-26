
import unittest
import os

from mpgameserver.connection import SeqNum, BitField, ConnectionBase, \
    Packet, PacketHeader, PacketType, ConnectionStatus, \
    PacketError, DuplicationError, PendingMessage, \
    ClientServerConnection, ServerClientConnection, ServerContext, RetryMode

from mpgameserver.serializable import Serializable
from mpgameserver.handler import EventHandler
from mpgameserver.crypto import EllipticCurvePrivateKey, EllipticCurvePublicKey

class MockUDPSocket(object):
    """docstring for MockUDPSocket"""
    def __init__(self):
        super(MockUDPSocket, self).__init__()
        self.other = None

        self.sent = []

    def sendto(self, datagram, addr):
        self.sent.append((datagram, addr))

    def recvfrom(self, *args):
        return self.sent.pop(0)

class ConnectionInitTestCase(unittest.TestCase):

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

    def test_seqnum(self):

        self.assertEqual(SeqNum(1) - 1, 65535)
        self.assertEqual(SeqNum(1) - 2, 65534)
        self.assertEqual(SeqNum(10) - 1, 9)

        self.assertEqual(SeqNum(0x000A).diff(SeqNum(0xFFF0)), 25)

        self.assertEqual(SeqNum(0xFFF0).diff(SeqNum(0x000A)), -25)

        self.assertEqual(SeqNum(0x000A) + SeqNum(1), 0xB)

        self.assertEqual(SeqNum(0xFFFF) + SeqNum(1), 1)

        self.assertEqual(SeqNum(0xFFFF) - (-1), 1)

        self.assertEqual(SeqNum(1) + (-1), 0xFFFF)

        self.assertTrue(SeqNum(10) > SeqNum(5))

        self.assertFalse(SeqNum(10) < SeqNum(5))

        self.assertEqual(SeqNum.maximum(), 0xFFFF)

        with self.assertRaises(ValueError):
            SeqNum(0x10000)

        with self.assertRaises(ValueError):
            SeqNum(-1)

    def test_seqnum_v2(self):

        a = SeqNum(10)
        b = SeqNum(16)
        c = SeqNum(0xFFF0)

        self.assertTrue(a.newer_than(c))
        self.assertTrue(b.newer_than(a))

    def test_bitfield(self):

        field = BitField(32)
        field.insert(SeqNum(10))
        field.insert(SeqNum(16))

        self.assertFalse(field.contains(SeqNum(11)))
        self.assertTrue(field.contains(SeqNum(10)))
        self.assertFalse(field.contains(SeqNum(9)))

        self.assertTrue(field.contains(SeqNum(16)))

        s = repr(field)

        self.assertEqual(s, "<BitField(0400_0000)>")

    def test_conn_handle_first(self):
        """
        two packets are received in the correct sequential order
        """

        conn = ConnectionBase(False, None)
        conn.bitfield_pkt.insert(SeqNum(1))

        self.assertEqual(SeqNum(1), conn.bitfield_pkt.current_seqnum)
        self.assertEqual("0x0", hex(conn.bitfield_pkt.bits))

    def test_conn_handle_seq_sequential_1(self):
        """
        two packets are received in the correct sequential order
        """

        conn = ConnectionBase(False, None)
        conn.bitfield_pkt.current_seqnum = SeqNum(1233)
        conn.bitfield_pkt.bits = 0xAAAAAAAA
        conn.bitfield_pkt.insert(SeqNum(1234))

        self.assertEqual(SeqNum(1234), conn.bitfield_pkt.current_seqnum)
        self.assertEqual("0xd5555555", hex(conn.bitfield_pkt.bits))

    def test_conn_handle_seq_sequential_2(self):
        """
        two packets are received in the correct sequential order
        """

        conn = ConnectionBase(False, None)
        conn.bitfield_pkt.current_seqnum = SeqNum(1233)
        conn.bitfield_pkt.bits = 0xAAAAAAAA
        conn.bitfield_pkt.insert(SeqNum(1235))

        self.assertEqual(SeqNum(1235), conn.bitfield_pkt.current_seqnum)
        self.assertEqual("0x6aaaaaaa", hex(conn.bitfield_pkt.bits))

    def test_conn_handle_seq_sequential_31(self):
        """
        two packets are received in the correct sequential order
        """

        conn = ConnectionBase(False, None)
        conn.bitfield_pkt.current_seqnum = SeqNum(1233)
        conn.bitfield_pkt.bits = 0xAAAAAAAA
        conn.bitfield_pkt.insert(SeqNum(1264))

        self.assertEqual(SeqNum(1264), conn.bitfield_pkt.current_seqnum)
        self.assertEqual("0x3", hex(conn.bitfield_pkt.bits))

    def test_conn_handle_seq_sequential_32(self):
        """
        two packets are received in the correct sequential order
        """

        conn = ConnectionBase(False, None)
        conn.bitfield_pkt.current_seqnum = SeqNum(1233)
        conn.bitfield_pkt.bits = 0xAAAAAAAA
        conn.bitfield_pkt.insert(SeqNum(1265))

        self.assertEqual(SeqNum(1265), conn.bitfield_pkt.current_seqnum)
        self.assertEqual("0x1", hex(conn.bitfield_pkt.bits))

    def test_conn_handle_seq_sequential_33(self):
        """
        two packets are received in the correct sequential order
        """

        conn = ConnectionBase(False, None)
        conn.bitfield_pkt.current_seqnum = SeqNum(1233)
        conn.bitfield_pkt.bits = 0xAAAAAAAA
        conn.bitfield_pkt.insert(SeqNum(1266))

        self.assertEqual(SeqNum(1266), conn.bitfield_pkt.current_seqnum)
        self.assertEqual("0x0", hex(conn.bitfield_pkt.bits))

    def test_conn_handle_seq_revered_order_1(self):
        """
        two packets are received in reversed order
        """

        conn = ConnectionBase(False, None)
        conn.bitfield_pkt.current_seqnum = SeqNum(1234)
        conn.bitfield_pkt.bits = 0x0AAAAAAA
        conn.bitfield_pkt.insert(SeqNum(1233))

        self.assertEqual(SeqNum(1234), conn.bitfield_pkt.current_seqnum)
        self.assertEqual("0x8aaaaaaa", hex(conn.bitfield_pkt.bits))

    def test_conn_handle_seq_revered_order_2(self):
        """
        two packets are received in reversed order
        """

        conn = ConnectionBase(False, None)
        conn.bitfield_pkt.current_seqnum = SeqNum(1234)
        conn.bitfield_pkt.bits = 0x0AAAAAAA
        conn.bitfield_pkt.insert(SeqNum(1232))

        self.assertEqual(SeqNum(1234), conn.bitfield_pkt.current_seqnum)
        self.assertEqual("0x4aaaaaaa", hex(conn.bitfield_pkt.bits))

    def test_conn_handle_seq_out_of_order_33(self):
        """
        two packets are received out of order with more
        than 32 sequence numbers in between
        """

        conn = ConnectionBase(False, None)
        conn.bitfield_pkt.current_seqnum = SeqNum(1234)
        conn.bitfield_pkt.bits = 0x8AAAAAAA
        conn.bitfield_pkt.insert(SeqNum(1201))

        self.assertEqual(SeqNum(1234), conn.bitfield_pkt.current_seqnum)
        self.assertEqual("0x8aaaaaaa", hex(conn.bitfield_pkt.bits))

    def test_conn_handle_duplicate_last(self):
        """
        the most recent packet is duplicated
        """

        conn = ConnectionBase(False, None)
        conn.bitfield_pkt.current_seqnum = SeqNum(1234)
        conn.bitfield_pkt.bits = 0x8AAAAAAA
        with self.assertRaises(DuplicationError) as e:
            conn.bitfield_pkt.insert(SeqNum(1234))

    def test_conn_handle_duplicate_acked(self):
        """
        a previously acked packet is received again
        """

        conn = ConnectionBase(False, None)
        conn.bitfield_pkt.current_seqnum = SeqNum(1234)
        conn.bitfield_pkt.bits = 0x8AAAAAAA
        with self.assertRaises(DuplicationError) as e:
            conn.bitfield_pkt.insert(SeqNum(1233))

    def test_conn_build_packet_keep_alive(self):
        """
        build a keepalive packet if there is nothing else to send
        """

        conn = ConnectionBase(False, None)
        conn.status = ConnectionStatus.CONNECTED
        conn.bitfield_pkt.current_seqnum = SeqNum(1234)
        conn.bitfield_pkt.bits = 0xAAAAAAAA

        pkt = conn._build_packet()

        self.assertEqual(PacketType.KEEP_ALIVE, pkt.hdr.pkt_type)

    def test_conn_build_packet_single(self):
        """
        build a packet with a single message
        """

        conn = ConnectionBase(False, None)
        conn.bitfield_pkt.current_seqnum = SeqNum(1234)
        conn.bitfield_pkt.bits = 0xAAAAAAAA
        conn.status = ConnectionStatus.CONNECTED
        conn.session_key_bytes = b"0" * 16

        payload = b"hello world"
        conn.send(payload)

        pkt = conn._build_packet()

        self.assertEqual(PacketType.APP, pkt.hdr.pkt_type)
        self.assertEqual(1, pkt.hdr.count)
        self.assertEqual(Packet.overhead(1) + len(payload), pkt.hdr.length)
        self.assertEqual(payload, pkt.msg[2:])

    def test_conn_build_packet_multi_v1(self):
        """
        build a packet with one new message and one old message
        """

        current_time = 0

        def clock():
            nonlocal current_time
            current_time += 1
            return current_time

        conn = ConnectionBase(False, None)
        conn.clock = clock
        conn.bitfield_pkt.current_seqnum = SeqNum(1234)
        conn.bitfield_pkt.bits = 0xAAAAAAAA
        conn.status = ConnectionStatus.CONNECTED
        conn.session_key_bytes = b"0" * 16


        payload1 = b"hello world1"
        conn.send(payload1)

        #_ = conn._build_packet()

        payload2 = b"hello world2"
        conn.send(payload2)

        pkt = conn._build_packet()

        self.assertEqual(PacketType.APP, pkt.hdr.pkt_type, pkt.hdr.pkt_type)
        self.assertEqual(2, pkt.hdr.count)
        self.assertEqual(Packet.overhead(2) + len(payload1) + len(payload2), pkt.hdr.length)

    def test_conn_receive_datagram_1(self):

        key = b"0"*16
        hdr = PacketHeader.create(True, 0, PacketType.APP, SeqNum(1), SeqNum(1), 0)
        msgs = [PendingMessage(SeqNum(1), PacketType.APP, b"hello world1", None, 0)]

        pkt = Packet.create(hdr, msgs)

        datagram = pkt.to_bytes(key)

        conn = ConnectionBase(False, None)
        conn.session_key_bytes = key

        conn._recv_datagram(PacketHeader.from_bytes(False, datagram), datagram)
        self.assertEqual(SeqNum(1), conn.bitfield_pkt.current_seqnum)
        self.assertEqual(1, len(conn.incoming_messages))
        self.assertEqual(msgs[0].payload, conn.incoming_messages[0][1])

    def test_packet_max_size(self):
        # test that forming a packet of max payload size
        # correctly builds a packet with the maximum number of
        # bytes for the default MTU size (1500)

        hdr = PacketHeader()
        dat = os.urandom(Packet.MAX_PAYLOAD_SIZE)

        msg = PendingMessage(SeqNum(1), PacketType.APP, dat, None, 0)

        pkt = Packet.create(hdr, [msg])

        datagram = pkt.to_bytes(b"0"*16)
        self.assertEqual(len(datagram), Packet.MAX_SIZE)
        self.assertEqual(len(datagram), 1472) # mtu - 28

        datagram = pkt.to_bytes(None)
        self.assertEqual(len(datagram), Packet.MAX_SIZE_CRC)

    def test_packet_set_max_size(self):
        # test that forming a packet of max payload size
        # correctly builds a packet with the maximum number of
        # bytes for a custom MTU size.
        #
        Packet.setMTU(512)

        hdr = PacketHeader()
        dat = os.urandom(Packet.MAX_PAYLOAD_SIZE)

        msg = PendingMessage(SeqNum(1), PacketType.APP, dat, None, 0)

        pkt = Packet.create(hdr, [msg])

        datagram1 = pkt.to_bytes(b"0"*16)
        datagram2 = pkt.to_bytes(None)

        self.assertEqual(len(datagram1), 484) # mtu - 28
        self.assertEqual(len(datagram1), Packet.MAX_SIZE)
        self.assertEqual(len(datagram2), Packet.MAX_SIZE_CRC)
        # reset mtu for subsequent tests
        Packet.setMTU(1500)

class ConnectionTestCase(unittest.TestCase):

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

    def test_conn_send_datagram_simple(self):
        """
        """
        payload = b"hello world"
        conn = ConnectionBase(False, None)
        conn._send_type(PacketType.CLIENT_HELLO, payload, RetryMode.NONE, None)

        pkt = conn._build_packet()
        datagram = conn._encode_packet(pkt)

        self.assertEqual(PacketHeader.SIZE + PacketHeader.CRC_SIZE + Packet.overhead(1) + len(payload), len(datagram))

        hdr = PacketHeader.from_bytes(True, datagram)
        pkt = Packet.from_bytes(hdr, None, datagram)
        self.assertEqual(pkt.msg[2:], payload)

    def test_conn_sendrecv_datagram_encrypted(self):
        """
        """
        key = b"0" * 16

        payload = b"hello world"
        client = ConnectionBase(False, None)
        client.session_key_bytes = key
        client.status = ConnectionStatus.CONNECTED

        server = ConnectionBase(True, None)
        server.session_key_bytes = key

        client.send(payload)

        pkt = client._build_packet()
        datagram = client._encode_packet(pkt)

        hdr = PacketHeader.from_bytes(True, datagram)
        server._recv_datagram(hdr, datagram)

        self.assertEqual(1, len(server.incoming_messages))
        self.assertEqual(payload, server.incoming_messages[0][1])

    def test_conn_handshake(self):
        """
        run through the entire handshake

        happy path integration test
        """
        current_time = 0

        def clock():
            nonlocal current_time
            current_time += 1
            return current_time

        client = ClientServerConnection(('0.0.0.0', 1234))
        client.clock = clock
        #client.status = ConnectionStatus.CONNECTED

        ctxt = ServerContext(EventHandler(), None)
        server = ServerClientConnection(ctxt, ('0.0.0.0', 1235))
        server.clock = clock
        #server.status = ConnectionStatus.CONNECTED

        #with self.subTest(mode='send client hello'):
        client._sendClientHello()
        datagram = client._encode_packet(client._build_packet())

        self.assertEqual(len(datagram), Packet.MAX_PAYLOAD_SIZE + PacketHeader.CRC_SIZE)
        hdr = PacketHeader.from_bytes(True, datagram)

        # update the context with a reference to the server side client connection
        # user later to finalize the connection
        ctxt.temp_connections[server.addr] = server
        server._recv_datagram(hdr, datagram)
        datagram = server._encode_packet(server._build_packet())

        with self.subTest(mode='recv server hello'):
            hdr = PacketHeader.from_bytes(False, datagram)
            client._recv_datagram(hdr, datagram)

        with self.subTest(mode='recv challenge response'):
            datagram = client._encode_packet(client._build_packet())
            hdr = PacketHeader.from_bytes(True, datagram)
            server._recv_datagram(hdr, datagram)

        self.assertEqual(ConnectionStatus.CONNECTED, server.status)
        self.assertEqual(ConnectionStatus.CONNECTED, client.status)

        with self.subTest(mode='server send test'):
            greeting = b"hello client"
            server.send(greeting)
            datagram = server._encode_packet(server._build_packet())
            hdr = PacketHeader.from_bytes(False, datagram)
            client._recv_datagram(hdr, datagram)
            self.assertEqual(1, len(client.incoming_messages))
            self.assertEqual(b"hello client", client.incoming_messages[0][1])

        with self.subTest(mode='client send test'):

            greeting = b"hello server"
            client.send(greeting)
            datagram = client._encode_packet(client._build_packet())
            hdr = PacketHeader.from_bytes(True, datagram)
            server._recv_datagram(hdr, datagram)
            self.assertEqual(1, len(server.incoming_messages))
            self.assertEqual(greeting, server.incoming_messages[0][1])

        self.assertTrue(server.latency > 0)

    def test_conn_send_retry(self):
        """
        """
        key = b"0" * 16
        payload = b"test"
        ctime = 0.0
        retry_delay = .150

        client = ConnectionBase(False, None)
        client.session_key_bytes = key
        client.status = ConnectionStatus.CONNECTED


        client.send(payload, retry=1)

        pkt1 = client._build_packet_impl(ctime, False, retry_delay)

        ctime += retry_delay + 1/60

        pkt2 = client._build_packet_impl(ctime, False, retry_delay)


        self.assertEqual(pkt1.msg, pkt2.msg)
        self.assertNotEqual(pkt1.hdr.seq, pkt2.hdr.seq)

        self.assertEqual(len(client.pending_retry), 2)

        client._handle_ack(pkt1.hdr.seq)
        self.assertEqual(len(client.pending_retry), 1)

        client._handle_ack(pkt2.hdr.seq)
        self.assertEqual(len(client.pending_retry), 0)

    def test_conn_send_retry_timeout(self):
        """
        """
        key = b"0" * 16
        payload = b"test"
        ctime = 0.0
        retry_delay = .150

        client = ConnectionBase(False, None)
        client.session_key_bytes = key
        client.status = ConnectionStatus.CONNECTED


        client.send(payload, retry=1)

        pkt1 = client._build_packet_impl(ctime, False, retry_delay)

        ctime += retry_delay + 1/60

        pkt2 = client._build_packet_impl(ctime, False, retry_delay)


        self.assertEqual(pkt1.msg, pkt2.msg)
        self.assertNotEqual(pkt1.hdr.seq, pkt2.hdr.seq)

        self.assertEqual(len(client.pending_retry), 2)

        client._handle_timeout(pkt1.hdr.seq)
        self.assertEqual(len(client.pending_retry), 1)

        client._handle_ack(pkt2.hdr.seq)
        self.assertEqual(len(client.pending_retry), 0)

def main():
    unittest.main()


if __name__ == '__main__':
    main()
