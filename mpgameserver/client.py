#! cd .. && python -m mpgameserver.client

"""
# Client


"""
import socket
import time
import select
from typing import Callable
from .connection import ClientServerConnection, Packet, PacketHeader, \
    ConnectionStatus, SendCallback, ConnectionStats
from . import crypto
from .timer import Timer
from .util import is_valid_ipv6_address
import logging

class UdpClient(object):
    """

    This class manages UDP socket connection to the server.

    The Client is designed to be non-blocking so that it can be run inside the main loop of the game.
    The update() function should be called once per frame to perform the actual send and receive
    of messages. Messages can be queued at any time using send()

    The server public key is a Elliptic Curve public key that should be
    generated once from the server private key and stored and distributted
    with the client. The key is used to authenticate that the server this
    client is connecting to is in fact a genuine server.
    """
    def __init__(self, server_public_key=None):
        """
        :param server_public_key: the public key used to identify the server
        """
        super(UdpClient, self).__init__()
        self.conn = None
        self.sock = None

        self.disconnect_acked = False

        if server_public_key is None:
            self.server_public_key = crypto.EllipticCurvePublicKey.unsafeTestKey()
        else:
            self.server_public_key = server_public_key

        self.keep_alive_interval = .1
        self.temp_connection_timeout = 2.0
        self.outgoing_timeout = 1.0

    def _make_socket(self, addr):
        mode = socket.AF_INET
        if is_valid_ipv6_address(addr[0]):
            mode = socket.AF_INET6
        return socket.socket(mode, socket.SOCK_DGRAM)

    def setKeepAliveInterval(self, interval):
        """ configure the timeout for sending keep alive datagrams to clients.

        :param timeout: the timeout in seconds. The default is .1 seconds.
        """
        self.keep_alive_interval = interval
        if self.conn:
            self.conn.send_keep_alive_interval = interval

    def setConnectionTimeout(self, timeout):
        """ configure the timeout for waiting for the response to the connection request.

        :param timeout: the timeout in seconds. The default is 5 seconds.
        """
        self.temp_connection_timeout = timeout
        if self.conn:
            self.conn.temp_connection_timeout = interval

    def setMessageTimeout(self, timeout):
        """ configure the timeout for waiting for the ack for a datagram

        :param timeout: the timeout in seconds. The default is 1 second.
        """
        self.outgoing_timeout = timeout
        if self.conn:
            self.conn.outgoing_timeout = interval

    def connect(self, addr, callback: Callable[[bool], None]=None):
        """ connect to a udp socket server

        :param addr: a 2-tuple (host, port)
        :param callback: a callable object to handle connection success or timeout
            callback signature: `fn(connected: bool)`
        """



        self.addr = addr
        self.sock = self._make_socket(addr)
        self.conn = ClientServerConnection(addr)
        self.conn.setServerPublicKey(self.server_public_key)
        self.conn.connection_callback = callback
        self.conn.keep_alive_interval = self.keep_alive_interval
        self.conn.temp_connection_timeout = self.temp_connection_timeout
        self.conn.outgoing_timeout = self.outgoing_timeout

        self.conn._sendClientHello()

    def token(self):
        """ get the client token. This is a unique id generated when
        the client connects used internally to represent the client.

        :return: the unique id for this client
        """
        return self.conn.token

    def connected(self)  -> bool :
        """
        :return: True if the client is connected to the server
        """
        return self.conn and self.conn.status == ConnectionStatus.CONNECTED

    def status(self) -> ConnectionStatus:
        """
        :return: the ConnectionStatus
        """
        if self.conn:
            return self.conn.status
        return ConnectionStatus.DISCONNECTED

    def disconnect(self):
        """ disconnect from the server.

        This method only sets an internal flag to disconnect.
        use waitForDisconnect() to send a disconnect to the server
        and wait for the subsequent ack.

        """

        if self.conn:
            self.disconnect_acked = False
            self.conn.disconnect(self.onDisconnectCallback)

    def onDisconnectCallback(self, success):
        """ private disconnect callback
        """
        self.disconnect_acked = True

    def waitForDisconnect(self):
        """
        block the current thread until the server has responded
        that it received the disconnect event.

        blocks up to 1 second before giving up

        """

        if self.conn:
            t0 =  self.conn.clock()
            elapsed = 0
            while not self.disconnect_acked and elapsed < 1.0:
                self.update()
                time.sleep(self.conn.send_interval)
                elapsed = self.conn.clock() - t0

        self.conn = None

        if self.sock:
            self.sock.close()
            self.sock = None

    def update(self):
        """ send and receive messages

        On every frame one datagram is sent to the server if there are pending messages to be sent.
        Each datagram will contain as many messages that can possibly fit into the packet size.
        The packet size is limited by the MTU size of the network, which is typically 1500 bytes.
        In practice the maximum packet size is 1472 bytes.


        This function should be called once per game frame. This function is not
        thread safe, and should be called from the same thread that is also calling
        send()

        """
        if self.conn:
            try:
                self.conn.update()

                r, w,_ = select.select([self.sock], [self.sock], [], 0)

                if r:
                    datagram, addr = self.sock.recvfrom(Packet.RECV_SIZE)
                    hdr = PacketHeader.from_bytes(False, datagram)
                    self.conn._recv_datagram(hdr, datagram)

                t0 = self.conn.clock()
                if t0 - self.conn.last_send_time > self.conn.send_interval:
                    pkt = self.conn._build_packet()

                    if pkt is not None:
                        datagram = self.conn._encode_packet(pkt)
                        self.sock.sendto(datagram, self.addr)

                    self.conn._check_timeout(t0)

            except ConnectionResetError as e:
                self.conn = None
                raise

    def send(self, msg: bytes, retry:int=-1, callback:SendCallback=None):
        """
        send a message to the server

        The message is not sent immediatly,
        Instead on the next call to update() a datagram will be sent.

        The message will be fragmented if the length is greater than
        Packet.MAX_PAYLOD_SIZE

        :param msg: the bytes to send
        :param retry: the RetryMode, default to RetryMode.NONE
        :param callback: a function which is called when the message has been
            acked or after a timeout. The function should accept a single
            boolean which is true when the message is acked and false otherwise.
            If retry is negative then the callback will be called when the message
            is finally acked.
        """
        self.conn.send(msg, retry=retry, callback=callback)

    def send_guaranteed(self, payload: bytes, callback:SendCallback=None):
        """ send the message and guarantee delivery by using RetryMode.RETRY_ON_TIMEOUT

        """
        self.conn.send(payload, retry=RetryMode.RETRY_ON_TIMEOUT, callback=callback)

    def hasMessages(self):
        """ :return: True if there are unprocessed messages from the server
        """
        if self.conn:
            return bool(self.conn.incoming_messages)
        return False

    def getMessage(self):
        """ get a single message received from the server

        :return: a tuple (seqnum, msg)

        raises IndexError if the incoming message queue is empty

        This is a destructive call. It removes one message from the queue

        """
        return self.conn.incoming_messages.pop(0)

    def getMessages(self):
        """ :return: The list of unprocessed messages from the server, or an empty list

        This is a destructive call. It removes all messages from the internal queue
        """
        if self.conn:
            messages = self.conn.incoming_messages
            self.conn.incoming_messages = []
            return messages
        return []

    def latency(self):
        """ :return: The connection latency

        latency is half of the moving average of round trip time, calculated
        when a packet is acked.
        """
        if self.conn:
            return self.conn.latency
        return 0

    def stats(self)-> ConnectionStats:

        if self.conn:
            return self.conn.stats
        return ConnectionStats()