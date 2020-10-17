#! cd .. && python demo/tankclient.py

"""

# Network protocol

This document describes the implementation details of the UDP network protocol

The protocol is based on these documents:

* https://www.gafferongames.com/post/packet_fragmentation_and_reassembly/
* https://www.gafferongames.com/post/sending_large_blocks_of_data/
* https://pvigier.github.io/2019/09/08/beginner-guide-game-networking.html
* https://technology.riotgames.com/news/valorants-128-tick-servers

## Establishing a Connection

In order for a client to connect to the server a series of 3 special
messages are sent back and forth. After the first two messages are received
all subsequent messages are encrypted.

1. Client sends packet 'CLIENT_HELLO'

The client sends an ephemeral public key and a version identifier.

This packet is unencrypted. A simple crc32 is used to verify the integrity.

2. Server responds with packet 'SERVER_HELLO'

The server responds with an ephemeral public key unique to this client,
as well as a salt and token. The salt is used by the client to derive a shared
secret key for encryption. The token should be encrypted and sent back to
the server to validate both sides of the connection are using the correct protocol.

This packet is unencrypted. A simple crc32 is used to verify the integrity.
In addition, the datagram payload is signed using the server root key.
This will allow the client to verify that the content came from the server.

3. Client responds with 'CHALLENGE_RESP'

The client then sends the token back to the server.

This packet is encrypted. The server uses this packet to prove that both
sides were able to generate the same shared secret.

## Message Size

The maximum message size is limited by the MTU of the network.
Thats 1500 bytes for a UDP datagram, minus 28 bytes for the UDP header.
A further 20 bytes are used for the MpGameServer header.

User defined messages have an additional 2 byte overhead. When multiple messages are
encoded into a single packet the overhead increases to 5 bytes per message.
This leaves a maximum of 1450 useable bytes for a single user defined message.


todo: sequence diagram


"""

import os
import sys
import time
import struct
import logging
import select
import random
from typing import Callable, List
from io import BytesIO
from .serializable import SerializableType, Serializable, SerializableEnum, serialize_value, deserialize_value
from . import crypto
from .crypto import EllipticCurvePrivateKey, EllipticCurvePublicKey

from .timer import Timer
from .logger import PeerLogger
from .context import ServerContext
from collections import namedtuple

class PendingMessage(object):
    def __init__(self, seq, type, payload, callback, retry):
        super(PendingMessage, self).__init__()
        self.seq = seq
        self.type = type
        self.payload = payload
        self.callback = callback
        self.retry = retry
        self.assembled_time = 0 #

    def __repr__(self):
        return "<PendingMessage(%s, %s, %s, %s)>" % (self.seq, self.type, self.payload, self.retry)

class SeqNum(int):
    """
    A sequence number is an integer which wraps around after reaching
    a maximum value.

    A value of zero marks an invalid or uninitialized sequnce number
    The first sequence number sent by the server will be 1, and after
    wrapping around the maximum will be set to 1 again.

    Sorting is undefined over a large range
    """

    _bytesize: int = 2
    _max_sequence: int = 2**(8*_bytesize) - 1
    _threshold: int = (_max_sequence - 1) // 2

    @classmethod
    def maximum(cls) -> int:
        return cls(cls._max_sequence)

    def __new__(cls, value=None) -> "SeqNum":
        if value is None:
            value = 0
        elif value > cls._max_sequence:
            raise ValueError("value exceeds maximum sequence number")
        elif value < 0:
            raise ValueError("sequence numbers must not be negative")
        return super(SeqNum, cls).__new__(cls, value)  # type: ignore

    def __add__(self, other) -> "SeqNum":
        """
        implement subtraction on a ring. wrapping from maximum back
        to the minimum sequence and vice-versa
        """

        result = super().__add__(other)
        # this strategy ensures that 0 will never be produced
        # while allowing for 0 to be a valid initial sequence number
        if result < 1:
            result += self._max_sequence
        if result > self._max_sequence:
            result -= self._max_sequence
        return self.__class__(result)

    def __sub__(self, other) -> "SeqNum":
        """
        implement subtraction on a ring. wrapping from minimum back
        to the maximum sequence and vice-versa
        """
        result = super().__sub__(other)
        if result < 1:
            result += self._max_sequence
        if result > self._max_sequence:
            result -= self._max_sequence
        return self.__class__(result)

    def diff(self, other) -> int:
        """
        returns the difference between two sequence numbers

        This implements 'traditional integer' subtraction as opposed
        to what __sub__ implements

        The sign of the output will be corrected if the numbers wrapped

        Example:
            0xFFF0 - 0x000A = -25
            0x000A - 0xFFF0 = +25

        Proof Example 1:
            0xFFF0 - (0xFFF0 + 25) = x
            0xFFF0 - 0xFFF0 - 25 = x
            - 25 = x

        Proof Example 2:

            (0xFFF0 + 25) - 0xFFF0 = x
            0xFFF0 + 25 - 0xFFF0 = x
            + 25 = x

        """

        result = super().__sub__(other)
        if result > self._threshold:
            result -= self._max_sequence
        elif result < -self._threshold:
            result += self._max_sequence
        return int(result)

    def newer_than(self, other):
        """ Test

        :return: True if this SeqNum is more recent than the given SeqNum
        """
        return self.diff(other) > 0

    def __lt__(self, other) -> bool:
        if isinstance(other, SeqNum):
            return super().__lt__(super().__add__((other.diff(self))))
        else:
            raise TypeError(str(other))

    def __gt__(self, other) -> bool:
        if isinstance(other, SeqNum):
            return super().__gt__(super().__add__((other.diff(self))))
        else:
            raise TypeError(str(other))

class BitField(object):
    """ The bitfield keeps track of recently received messages.
    It uses a one hot encoding to indicate received SeqNum using
    a fixed number of bits.

    """
    def __init__(self, nbits=32):
        """
        :param nbits: the number of bits to use for encoding the history of inserted messages
        """
        super(BitField, self).__init__()

        if nbits%8 != 0:
            raise ValueError("bitfield size must be multiple of 8")

        self.nbits = nbits
        self.bits = 0
        self.current_seqnum = SeqNum()

        self.mask = 2**(self.nbits) - 1
        self.onehot = 1 << (self.nbits - 1)

    def insert(self, seqnum: SeqNum):
        """ insert a sequence number

        raises a DuplicationError if an exception is thrown

        :param seqnum: The Sequence Number
        """

        if self.current_seqnum == 0:
            self.current_seqnum = seqnum
            return

        diff = self.current_seqnum.diff(seqnum)

        if diff < 0:
            self.current_seqnum = seqnum
            n = -diff
            if n <= self.nbits:
                self.bits >>= n
                self.bits |= self.onehot >> (n - 1)
            else:
                self.bits = 0
        elif diff == 0:
            raise DuplicationError("duplication error: %d" % seqnum)
        else:
            mask = self.onehot >> (diff - 1)
            if mask & self.bits:
                raise DuplicationError("duplication error: %d" % seqnum)
            self.bits |= mask

    def contains(self, seqnum: SeqNum):
        """ test if the bitfield currently contains the Sequence Number

        :param seqnum: The Sequence Number
        """
        diff = self.current_seqnum.diff(seqnum)
        if diff == 0:
            return True
        elif diff > 0:
            mask = self.onehot >> (diff - 1)
            if mask & self.bits:
                return True
        return False

    def __repr__(self):
        s = hex(self.bits)[2:]
        s = s.zfill(self.nbits//4)
        s = s[::-1]
        parts = [s[i:i+4] for i in range(0, len(s), 4)]
        s = '_'.join(parts)[::-1]

        return "<BitField(%s)>" % s

class PacketError(Exception):
    pass

class ProtocolError(Exception):
    pass

class DuplicationError(ProtocolError):
    pass

class PacketIdentifier(SerializableEnum):
    """
    The packet magic number. Used to cheaply identify a packet as originating
    from a client or server implementing the MpGameServer protocol

    :attr TO_SERVER: Indicates a packet being sent to the server
    :attr TO_CLIENT: Indicates a packet being sent to a client

    """
    TO_SERVER = b"FSOS"
    TO_CLIENT = b"FSOC"

class PacketType(SerializableEnum):

    """

    """
    UNKNOWN          = 0x00  #
    CLIENT_HELLO     = 0x01  #
    SERVER_HELLO     = 0x02  #
    CHALLENGE_RESP   = 0x03  #
    KEEP_ALIVE       = 0x04  #
    DISCONNECT       = 0x05  #
    APP              = 0x06  #
    APP_FRAGMENT     = 0x07  #

class PacketHeader(object):
    """
    The Packet Header structure is composed of the following:

    | Num. Bytes | Field Name | Description |
    | -----: | :--- | :---------- |
    | 3 | magic number           | packet protocol version identifier |
    | 1 | direction identifier   | identify whether the packet is to be
                                         decrypted by the client or server.
                                         Used to prevent IV reuse between
                                         client and server |
    | 4 | send time              | time packet was constructed.
                                         used to generate a unique IV when
                                         combined with incrementing seq num |
    | 2 | seq num                | incrementing packet counter |
    | 2 | previous acked seq num | sequence number of the last
                                         received packet |
    | 1 | packet type            | descrbies payload content |
    | 2 | length                 | number of bytes in the payload
                                         excluding any CRC or AES-GCM tag |
    | 1 | count                  | number of messages in this packet |
    | 4 | ack_bits               | bit field indicating what messages
                                         have been received from remote |

    The first 12 bytes of the header are used as the IV when encrypting
    a packet. The entire header is 20 bytes. When encrypting a packet
    the header is included as part of the AAD, and not encrypted.

    :attr isServer: True when it is the server constructing the header
    :attr ctime: the current time
    :attr pkt_type: The type of this packet
    :attr seq: the SeqNum for this Packet
    :attr ack: the SeqNum of the last packet received from remote
    :attr ack_bits: 32-bit integer bit-field indicating received packets
    :attr length: number of data bytes in packet
    :attr count: number of messages included in the packet

    """

    IV_SIZE = 12
    AAD_SIZE = 8
    CRC_SIZE = 4
    TAG_SIZE = crypto.ENCRYPTION_TAG_LENGTH
    SIZE = IV_SIZE + AAD_SIZE
    OVERHEAD = SIZE + TAG_SIZE

    def __init__(self):
        super(PacketHeader, self).__init__()
        self.isServer = False
        self.ctime = 0
        self.pkt_type = PacketType.UNKNOWN
        self.seq = 0
        self.ack = 0
        self.ack_bits = 0
        self.length = 0
        self.count = 0

    def __repr__(self):
        return "<PacketHeader(%s:%04X,%08X)>" % (self.pkt_type, self.seq, self.ack_bits)

    def to_bytes(self):
        """ Serialize the packet header to a byte array
        """

        # set direction identifier and magic number
        ident = PacketIdentifier.TO_CLIENT if self.isServer else PacketIdentifier.TO_SERVER
        # build the IV
        hdr = struct.pack(">4sLHH", ident.value, self.ctime, self.seq, self.ack)
        # additional bytes for AAD
        hdr += struct.pack(">BHBL", self.pkt_type.value, self.length, self.count, self.ack_bits)

        return hdr

    @staticmethod
    def create(isServer, ctime, pkt_type, seq, ack, ack_bits):
        """ contruct a new header

        :param isServer: True when it is the server constructing the header
        :param ctime: the current time
        :param pkt_type: The type of this packet
        :param seq: the SeqNum for this Packet
        :param ack: the SeqNum of the last packet received from remote
        :param ack_bits: 32-bit integer bit-field indicating received packets
        """
        hdr = PacketHeader()
        hdr.isServer = isServer
        hdr.ctime = ctime
        hdr.pkt_type = pkt_type
        hdr.seq = seq
        hdr.ack = ack
        hdr.ack_bits = ack_bits
        return hdr

    @staticmethod
    def from_bytes(isServer, datagram):
        """ extract the header from a datagram

        :param isServer: True when it is the server that is extracting the header
        :param datagram: the bytes to decode
        """
        hdr = PacketHeader()
        ident, time, seq, ack, pkt_type, hdr.length, hdr.count, ack_bits = \
            struct.unpack(">4sLHHBHBL", datagram[:PacketHeader.SIZE])
        hdr.ctime = time
        hdr.pkt_type = PacketType(pkt_type)
        hdr.isServer = ident == PacketIdentifier.TO_SERVER.value
        hdr.seq = SeqNum(seq)
        hdr.ack = SeqNum(ack)
        hdr.ack_bits = ack_bits

        if ident != PacketIdentifier.TO_SERVER.value and ident != PacketIdentifier.TO_CLIENT.value:
            raise PacketError("invalid magic number")
        if hdr.isServer != isServer:
            raise PacketError("direction error")

        return hdr

class Packet(object):
    # verified using :
    # ping  -s 1472  -D 8.8.4.4
    # > PING 8.8.4.4 (8.8.4.4) 1472(1500) bytes of data.

    # the absolute maximum length of a datagram
    MTU = 1500
    UDP_HEADER_SIZE = 28
    MAX_SIZE = MTU - UDP_HEADER_SIZE
    # the maximum length of a datagram when unencrypted and using a crc
    MAX_SIZE_CRC = MAX_SIZE - PacketHeader.TAG_SIZE + PacketHeader.CRC_SIZE

    MESSAGE_OVERHEAD_0 = 0 # no overhead for sending an empty packet (duh)
    MESSAGE_OVERHEAD_1 = 2 # 2 bytes of overhead to send a single message in a datagram
    MESSAGE_OVERHEAD_N = 5 # 5 bytes or overhead for each message to send more than one message in a datagram
    FRAGMENT_OVERHEAD = 6 # 2 bytes each for seq, count and index

    # maximum payload size assuming an encrypted + tagged packet
    # packets larger than this value must be fragmented
    MAX_PAYLOAD_SIZE = MAX_SIZE - PacketHeader.SIZE - PacketHeader.TAG_SIZE - MESSAGE_OVERHEAD_1

    # allow room for other messages
    MAX_FRAGMENT_SIZE = 1024

    MAX_FRAGMENTS = 0x2000 # ~11mb
    RECV_SIZE = 2048


    def __init__(self):
        super(Packet, self).__init__()

        self.hdr = None
        self.msg = b''
        self.msgs = []

    def __repr__(self):
        return "<Packet(%s,%d,%d,%04X,%08X)>" % (self.hdr.pkt_type, len(self.msg), self.hdr.count, self.hdr.seq, self.hdr.ack_bits)

    def to_bytes(self, key):

        if key and self.hdr.pkt_type != PacketType.SERVER_HELLO:
            hdr = self.hdr.to_bytes()

            iv = hdr[:PacketHeader.IV_SIZE]
            ct_withtag = crypto.encrypt_gcm(key, iv, hdr, self.msg)

            return hdr + ct_withtag

        else:

            datagram = self.hdr.to_bytes() + self.msg
            datagram += struct.pack(">L", crypto.crc32(datagram))
            return datagram

    def total_size(self, key):
        """
        return the size of the encoded packet
        """

        if key and self.hdr.pkt_type != PacketType.SERVER_HELLO:
            return len(self.msg) + PacketHeader.SIZE + PacketHeader.TAG_SIZE
        else:
            return len(self.msg) + PacketHeader.SIZE + PacketHeader.CRC_SIZE

    @staticmethod
    def setMTU(mtu):
        """ set the MTU size for the network protocol, and adjust global constants accordingly.

        calling this function will change the size of packets that are constructed by the protocol.

        The default MTU is 1500 bytes. Values larger than this will result in packets that are
        likely to not be delivered. The MTU can be decreased if the network is dropping
        packets.

        The UDP header size is assumed to be 28 bytes.

        :param mtu: Maximum transmission unit.
        """
        Packet.MTU = mtu
        Packet.MAX_SIZE = Packet.MTU - Packet.UDP_HEADER_SIZE
        Packet.MAX_PAYLOAD_SIZE = Packet.MAX_SIZE - PacketHeader.SIZE - PacketHeader.TAG_SIZE - Packet.MESSAGE_OVERHEAD_1

        Packet.MAX_SIZE_CRC = Packet.MAX_SIZE - PacketHeader.TAG_SIZE + PacketHeader.CRC_SIZE

        if Packet.MAX_PAYLOAD_SIZE < 1024 + Packet.FRAGMENT_OVERHEAD:
            Packet.MAX_FRAGMENT_SIZE = Packet.MAX_PAYLOAD_SIZE - Packet.FRAGMENT_OVERHEAD
        else:
            Packet.MAX_FRAGMENT_SIZE = 1024

        Packet.RECV_SIZE = mtu + 512

    @staticmethod
    def overhead(n):
        """
        return the amount of overhead for n messages in a packet

        there is 2 bytes of overhead for a single message to include
        the message sequence number. There is 5 bytes of overhead for 2 or more
        messages to include the length, type, and message sequence number

        """

        if n == 0:
            return 0

        elif n == 1:
            return 2

        return 5 * n

    @staticmethod
    def from_bytes(hdr, key, datagram):
        pkt = Packet()
        pkt.hdr = hdr
        length = PacketHeader.SIZE + hdr.length
        if length > len(datagram):
            raise PacketError("length error")

        if key and hdr.pkt_type not in (PacketType.CLIENT_HELLO, PacketType.SERVER_HELLO):
            # packet is encrypted, decrypt using the given key
            length += PacketHeader.TAG_SIZE
            iv = datagram[:PacketHeader.IV_SIZE]
            aad = datagram[:PacketHeader.SIZE]
            data = datagram[PacketHeader.SIZE:length]
            pkt.msg = crypto.decrypt_gcm(key, iv, aad, data)
        else:
            # packet is not encrypted: validate the crc
            data = datagram[:length]
            crc_actual = crypto.crc32(data)
            crc_expected, = struct.unpack(">L", datagram[length:length+PacketHeader.CRC_SIZE])
            if crc_actual != crc_expected:
                raise PacketError("crc error")
            pkt.msg = data[PacketHeader.SIZE:]

        # unpack the payload into a list of PendingMessage instances

        msgs = []

        if pkt.hdr.count == 1:
            seq, = struct.unpack(">H", pkt.msg[:2])
            seq = SeqNum(seq)
            msgs.append(PendingMessage(seq, pkt.hdr.pkt_type, pkt.msg[2:], None, 0))

        elif pkt.hdr.count > 1:
            payload = pkt.msg
            for i in range(pkt.hdr.count):
                length, seq, typ = struct.unpack(">HHB", payload[:5])
                typ = PacketType(typ)
                seq = SeqNum(seq)
                msg = payload[5: 5 + length]

                msgs.append(PendingMessage(seq, typ, msg, None, 0))

                payload = payload[5+length:]

        pkt.msgs = msgs

        return pkt

    @staticmethod
    def create(hdr: PacketHeader, msgs: List[PendingMessage]):
        """
        create a new packet given a header and a list messages

        hdr: PacketHeader
        msgs: list of PendingMessage
        """

        if len(msgs) == 0:
            payload = b""
        elif len(msgs) == 1:
            payload = struct.pack(">H", msgs[0].seq) + msgs[0].payload
        else:
            payload = []
            for msg in msgs:
                payload.append(struct.pack(">HHB", len(msg.payload), msg.seq, msg.type.value))
                payload.append(msg.payload)
            # join can be faster than byte addition
            payload = b"".join(payload)

        pkt = Packet()

        hdr.length = len(payload)
        hdr.count = len(msgs)

        pkt.hdr = hdr
        pkt.msg = payload
        pkt.msgs = msgs

        return pkt

class HandshakeClientHelloMessage(Serializable):
    """
    Client Hello is used by a client to initiate a new connection

    the packet contains a public key and the client version.

    the packet is padded to the maximum length with random data. this
    prevents the message from being easy to compress and gaurds against
    a form of UDP DDOS when forged UDP packets are received by the server

    """
    client_pubkey: object = None
    client_version: int = 0

    def serialize(self, stream, **kwargs):
        s = stream.tell()

        serialize_value(stream, self.client_pubkey.getBytes())
        serialize_value(stream, self.client_version)

        e = stream.tell()
        to_write = Packet.MAX_PAYLOAD_SIZE - 2 - PacketHeader.SIZE - (e - s) -2
        stream.write(os.urandom(to_write))

    def deserialize(self, stream, **kwargs):
        s = stream.tell()
        der = deserialize_value(stream, **kwargs)
        self.client_pubkey = EllipticCurvePublicKey.fromBytes(der)
        self.client_version = deserialize_value(stream, **kwargs)
        e = stream.tell()

        to_read = Packet.MAX_PAYLOAD_SIZE - 2 - PacketHeader.SIZE - (e - s) - 2
        read = stream.read(to_read)
        if len(read) != to_read:
            raise ValueError("unable to read packet padding")
        return self

class HandshakeServerHelloMessage(Serializable):
    """
    Server Hello is sent back to the client when a Client Hello is received

    The packet contains the server public key as well as the salt that
    was used to derive the shared secret key. It also contains
    a token that is used to uniquely identifiy this client.

    When serializing/deserializing this message, the server root key
    or server root public key are used to sign/verify the contents
    of the message.

    """
    server_pubkey: object = None
    salt: bytes = b""
    token: int = 0

    def serialize(self, stream, **kwargs):
        temp = BytesIO()

        serialize_value(temp, self.server_pubkey.getBytes())
        serialize_value(temp, self.salt)
        serialize_value(temp, self.token)

        payload = temp.getvalue()

        signature = kwargs['server_root_key'].sign(payload)

        serialize_value(stream, payload)
        serialize_value(stream, signature)

    def deserialize(self, stream, **kwargs):
        payload = deserialize_value(stream, **kwargs)
        signature = deserialize_value(stream, **kwargs)

        kwargs['server_public_key'].verify(signature, payload)

        temp = BytesIO(payload)

        der = deserialize_value(temp, **kwargs)
        self.server_pubkey = EllipticCurvePublicKey.fromBytes(der)
        self.salt = deserialize_value(temp, **kwargs)
        self.token = deserialize_value(temp, **kwargs)

        return self

class HandshakeClientChallengeResponseMessage(Serializable):
    """
    The Challenge Response confirms the client and server are using the same protocol

    The server uses this message to move the connection from a temporary connection
    pool to the primary connection pool

    """
    token: int = 0

class ConnectionStatus(SerializableEnum):
    """ The connection status


    :attr CONNECTING: the client is attempting to connect, keys are not set
    :attr CONNECTED: the client is connected, keys are set
    :attr DISCONNECTING: the client is closing the connection gracefully
    :attr DISCONNECTED: the client is not connected
    """
    CONNECTING    = 1
    CONNECTED     = 2
    DISCONNECTING = 3
    DISCONNECTED  = 4

class ConnectionQuality(SerializableEnum):
    EXCELLENT = 1
    GOOD   = 2
    BAD    = 3

class ConnectionStats(Serializable):
    """
    Structure containing all of the connection statistics.

    The attributes for packets sent/recv, bytes sent/recv and latency
    are sequence types where each bin is the statistics for a particular second.
    The list is treated as a FIFO queue, meaning lower indexes are older
    samples. The last index is the most recent data.

    :attr assembled: the lifetime count of outgoing packets created
    :attr sent: the lifetime count of outgoing packets sent
    :attr dropped: the lifetime count of received packets dropped
    :attr received: the lifetime count of received packets
    :attr acked: the lifetime count of outgoing packets acked
    :attr timeouts: the lifetime count of outgoing packets that timed out
    :attr pkts_sent: a rolling list of integers. packets sent.
    :attr pkts_recv: a rolling list of integers. packets received.
    :attr bytes_sent: a rolling list of integers. total bytes sent.
    :attr bytes_recv: a rolling list of integers. total bytes received.
    :attr latency: a rolling list of integers. mean latency

    """
    assembled: int = 0
    sent: int = 0
    dropped: int = 0
    received: int = 0
    acked: int = 0
    timeouts: int = 0
    pkts_sent: list = None
    pkts_recv: list = None
    bytes_sent: list = None
    bytes_recv: list = None
    latency: list = None

class RetryMode(SerializableEnum):
    """
    The RetryMode is a per-message setting which controls how the message
    is delivered.

    When using one of the retry modes, it is possible for the same
    message to be included in multiple datagrams. The protocol automatically
    detects and drops duplicate messages.

    :attr NONE: Send the message, with no attempt at guaranteeing delivery or
        retrying.
    :attr BEST_EFFORT: Send the message. Then resend on the keep alive interval
        until the message is acked or the timeout duration is reached.
        Note: It is possible for the message to be received, but the timeout
        may still trigger.
    :attr RETRY_ON_TIMEOUT: Send the message. If a timeout occurs
        automatically resend the message. The message will be sent in this
        fashion until received or the connection is closed.
    """
    NONE=0
    BEST_EFFORT=1
    RETRY_ON_TIMEOUT=-1

SendCallback = Callable[[bool], None]

qualityIntervals = {
    ConnectionQuality.EXCELLENT: 1/60,
    ConnectionQuality.GOOD: 2/60,
    ConnectionQuality.BAD: 4/60,
}

qualityLatencyThreshold = {
    ConnectionQuality.EXCELLENT: .1,
    ConnectionQuality.GOOD: .25,
    ConnectionQuality.BAD: .5,
}

class FragmentSender(object):
    """ Fragment a payload and manage sending fragments to remote
    """
    def __init__(self, conn, frag_id, retry, callback):
        super(FragmentSender, self).__init__()
        self.conn = conn

        self.frag_id = frag_id
        self.retry = retry
        self.user_callback = callback

        self.fragments = []
        self.acks = []

    def build(self, payload):

        if len(payload) > Packet.MAX_FRAGMENT_SIZE * Packet.MAX_FRAGMENTS:
                raise ValueError("packet too large")

        self.fragments = []
        while len(payload) > 0:
            if len(payload) < Packet.MAX_PAYLOAD_SIZE - Packet.FRAGMENT_OVERHEAD:
                # allow the final fragment to use as much space as possible
                self.fragments.append(payload)
                payload = b""
            else:
                # intermediate fragments should leave room for other
                # messages
                self.fragments.append(payload[:Packet.MAX_FRAGMENT_SIZE])
                payload = payload[Packet.MAX_FRAGMENT_SIZE:]

        self.acks = [None] * len(self.fragments)

        for index, fragment in enumerate(self.fragments):

            payload = struct.pack(">HHH", self.frag_id, 1 + index, len(self.fragments))
            payload += fragment
            meta_callback = lambda success, idx=index: self.callback(idx, success)

            yield payload, meta_callback

    def callback(self, index, success):

        if not success and self.retry != RetryMode.NONE:
            # resend the fragment that timed out
            cbk = lambda success, idx=index: self.callback(idx, success)
            self.conn._send_type(PacketType.APP_FRAGMENT, self.fragments[index], self.retry, cbk)
        else:
            self.acks[index] = success

    @staticmethod
    def parsePayload(payload):
        hdr = payload[:6]
        msg = payload[6:]

        frag_id, index, count = struct.unpack(">HHH", hdr)

        return frag_id, index, count, msg

class FragmentReceiver(object):
    """
    Receive fragments from remote belonging to a single fragment seqnum

    keep track of when the last received fragment was to allow for a timeout
    to cancel the fragment entirely.
    """
    def __init__(self, conn, frag_count, ctime):
        super().__init__()
        self.ctime = time.time()
        self.conn = conn
        self.fragments = [None] * frag_count
        self.ctime = ctime
        self.msgseq = SeqNum()
        self.frag_count = frag_count

    def expired(self):
        """
        expect to receive all fragments within a certain time range
        assuming poor latency (500ms rtt, 250ms one direction)
        allow 2x latency for each message

        behavior depends on client send rate.
        """
        age = time.time() - self.ctime
        max_age = 1.0 + .5 * self.frag_count
        return age > max_age

    def receive(self, index, msgseq, fragment):
        if 1 <= index <= len(self.fragments):
            if self.fragments[index-1] is None:
                self.fragments[index-1] = fragment

        if index == 1:
            self.msgseq = msgseq

    def isComplete(self):
        return all(self.fragments)

    def payload(self):
        return b"".join(self.fragments)

class RetrySender(object):
    """ functor for re-sending a payload on timeout

    """
    def __init__(self, conn, seq_message, pkt_type, payload, callback):
        super(RetrySender, self).__init__()
        self.conn = conn
        self.seq_message = seq_message
        self.pkt_type = pkt_type
        self.payload = payload
        self.callback = callback

    def __call__(self, success):
        # keep re-trying until it succeeds
        if not success:

            msg = PendingMessage(self.seq_message, self.pkt_type,
                self.payload, self, RetryMode.RETRY_ON_TIMEOUT)

            self.conn.outgoing_messages.append(msg)

        elif self.callback:
            self.callback(True)

class Bytes(bytes):
    seq = SeqNum()

class ConnectionBase(object):
    """

    ConnectionBase is independant of the socket.
    It handles parsing/assembling datagrams, and can be
    integrated with any transport mechanism
    """

    def __init__(self, isServer, addr):
        super(ConnectionBase, self).__init__()
        self.log = PeerLogger(addr)

        self.clock = time.time
        self.isServer = isServer
        self.addr = addr

        self.session_key_bytes = None # datagram encryption key

        self.incoming_messages = [] # queue of received messages
        self.outgoing_messages = [] # queue of messages to send

        self.pending_acks = {}      # seqnum -> send time
        self.pending_callbacks = {} # seqnum -> fn(success)
        #self.pending_messages = {}  # seqnum -> (typ, msg)
        self.pending_fragments = {} # frag_seq -> FragmentSender
        self.received_fragments = {} # frag_seq -> FragmentReceiver

        self.pending_retry = {}      # msgseq -> msg
        self.pending_retry_msg = {}      # seqnum -> list-of-msgseq

        self.seq_sending = SeqNum()
        self.seq_message = SeqNum()
        self.seq_fragment = SeqNum()

        self.bitfield_pkt = BitField(32)
        self.bitfield_msg = BitField(256)

        self.outgoing_timeout = 1.0
        self.temp_connection_timeout = 2.0
        # the keep alive interval is used to control how often a
        # a keep alive is sent when nothing else needs to be sent
        # or how often previously sent un-acked messages are attempted
        # to be resent.
        self.send_interval = 1/60
        self.send_keep_alive_interval = 6/60

        # here latency is the weighted average time it takes from sending a
        # packet until it is acked. In other words the round trip time
        # recently acked packets are weighted higher.
        self.latency = 0

        self.last_recv_time = -1
        self.last_send_time = -1
        self.last_send_keep_alive_time = -1

        self.status = ConnectionStatus.DISCONNECTED

        self.stats = ConnectionStats()
        self.stats.pkts_sent = [0]*5*60
        self.stats.pkts_recv = [0]*5*60
        self.stats.bytes_sent = [0]*5*60
        self.stats.bytes_recv = [0]*5*60
        self.stats.latency = [0]*5*60

    def timedout(self, timeout):
        """ Test if the connection has timed out.

        :return: True if more than timeout seconds have elapsed since the last message was received
        """
        age = self.clock() - self.last_recv_time
        return age >= timeout

    def send(self, payload: bytes, retry:RetryMode=RetryMode.NONE, callback:SendCallback=None):
        """ send a message to the remote client/server

        :param msg: the bytes to send
        :param retry: the RetryMode, default to RetryMode.NONE
        :param callback: a function which is called when the message has been
            acked or after a timeout. The function should accept a single
            boolean which is true when the message is acked and false otherwise.
        """

        if isinstance(retry, int):
            retry = RetryMode(retry)

        if self.status != ConnectionStatus.CONNECTED:
            return

        if not isinstance(payload, bytes):
            raise TypeError(type(payload))

        if len(payload) > Packet.MAX_PAYLOAD_SIZE:
            # fragmented messages use different retry logic
            self.seq_fragment += 1
            sender = FragmentSender(self, self.seq_fragment, retry, callback)

            if retry == RetryMode.RETRY_ON_TIMEOUT:
                retry = RetryMode.NONE

            for frag, cbk in sender.build(payload):
                self._send_type(PacketType.APP_FRAGMENT, frag, retry, cbk)

            self.pending_fragments[self.seq_fragment] = sender

        else:


            self._send_type(PacketType.APP, payload, retry, callback)

    def disconnect(self, callback=None):
        """
        close this connection

        base connection cannot close the socket because it does not own it
        """
        if self.status == ConnectionStatus.CONNECTED or self.status == ConnectionStatus.DISCONNECTING:
            # drop all messages
            self.outgoing_messages = []
            self.incoming_messages = []

            self.pending_callbacks = {}
            self.pending_retry = {}
            self.pending_acks = {}
            # cancel all pending messages
            #for seq in list(self.pending_acks):
            #    self._handle_timeout(seq)

            self._send_type(PacketType.DISCONNECT, b"", RetryMode.NONE, callback)

        self.status = ConnectionStatus.DISCONNECTED

    def _check_timeout(self, t0):
        for seqnum in list(self.pending_acks):
            if t0 - self.pending_acks[seqnum] >= self.outgoing_timeout:
                self._handle_timeout(seqnum)

    def _send_type(self, pkt_type, payload, retry, callback):
        self.seq_message += 1

        if retry == RetryMode.RETRY_ON_TIMEOUT:
            callback = RetrySender(self, self.seq_message, pkt_type, payload, callback)

        msg = PendingMessage(self.seq_message, pkt_type, payload, callback, retry)

        self.outgoing_messages.append(msg)
        self.stats.sent += 1

    def _build_packet_impl(self, current_time: float, send_keep_alive: bool, resend_delay: float):
        """
        build a new packet and update internal state.

        The messages are pulled from the pending message queue in the order they
        were received. Multiple messages will be packaged together in order
        to use as much space as available in the datagram.

        :param current_time: the time at which the packet was created
        :param send_keep_alive: True when the keep alive timer has expired.
        :param resend_delay: The number of seconds to wait before resending any message
            that has retry set to 1.

        :return: a new Packet, or None if there is nothing to be sent
        """

        pkt_type = PacketType.UNKNOWN
        msgs = [] # messages (seq, typ, msg) to include in this packet
        msg_length = 0 # sum of length of messages in msgs, excluding overhead

        # resend any messages that had the resend flag set
        # and have not yet timed out or been acked. the resend_delay is a
        # function of connection latency
        if self.pending_retry_msg:
            items = list(sorted(self.pending_retry_msg.items()))
            idx = 0
            while idx < len(items):
                msgseq, msg = items[idx]

                if current_time - msg.assembled_time < resend_delay:
                    idx += 1
                    continue

                size = len(msg.payload) + Packet.overhead(1+len(msgs)) + msg_length
                if size <= Packet.MAX_PAYLOAD_SIZE:
                    del self.pending_retry_msg[msgseq]
                    msgs.append(msg)
                    msg_length += len(msg.payload)

                idx += 1


        # if there are any messages to send, select as many messages
        # as possible that will fit in the packet size
        idx = 0
        while idx < len(self.outgoing_messages):
            pending = self.outgoing_messages[idx]

            size = len(pending.payload) + Packet.overhead(1+len(msgs)) + msg_length
            if size <= Packet.MAX_PAYLOAD_SIZE:
                msg = self.outgoing_messages.pop(idx)
                msgs.append(msg)
                msg_length += len(msg.payload)
            else:
                idx += 1

        # if there are no messages to send, then send a keep alive
        # if a keep alive was sent recently then there is nothing to send
        if len(msgs) == 0:
            # if there are no messages to include and it is not time to
            # send a keep alive return none
            if send_keep_alive and self.status == ConnectionStatus.CONNECTED:
                pkt_type = PacketType.KEEP_ALIVE
        else:
            pkt_type = msgs[0].type

        # nothing to send
        if pkt_type == PacketType.UNKNOWN:
            return None

        # register this packet so that acks, timeouts, callbacks
        # can be processed later
        self.seq_sending += 1
        self.pending_acks[self.seq_sending] = current_time
        callbacks = []
        retries = []
        for msg in msgs:
            if msg.callback:
                callbacks.append(msg.callback)
            if msg.retry != RetryMode.NONE:
                self.pending_retry_msg[msg.seq] = msg
                retries.append(msg.seq)

            msg.assembled_time = current_time

        if callbacks:
            self.pending_callbacks[self.seq_sending] = callbacks

        if retries:
            self.pending_retry[self.seq_sending] = retries

        hdr = PacketHeader.create(self.isServer, int(current_time), pkt_type,
            self.seq_sending, self.bitfield_pkt.current_seqnum,
            self.bitfield_pkt.bits)
        pkt = Packet.create(hdr, msgs)

        return pkt

    def _build_packet(self):
        """ build a packet, if there are any pending messages

        """

        t0 = self.clock()

        if t0 - self.last_send_time < self.send_interval:
            return None

        send_keep_alive = t0 - self.last_send_keep_alive_time > self.send_keep_alive_interval

        #resend_delay = max(self.send_keep_alive_interval, self.latency)
        resend_delay = self.send_keep_alive_interval

        pkt = self._build_packet_impl(t0, send_keep_alive, resend_delay)

        if pkt:
            # assume that this packet will be sent, update metrics
            if int(t0) != int(self.last_send_time):
                self.stats.pkts_sent.append(0)
                self.stats.bytes_sent.append(0)
            if len(self.stats.bytes_sent) > 5 * 60:
                self.stats.pkts_sent.pop(0)
                self.stats.bytes_sent.pop(0)
            self.last_send_time = t0

            # whether anything is sent at all, update this value
            # to restart the keep alive timer
            self.last_send_keep_alive_time = t0

            self.stats.assembled += 1
        return pkt

    def _encode_packet(self, pkt):
        try:
            datagram = pkt.to_bytes(self.session_key_bytes)
        except Exception as e:
            raise

        self.stats.pkts_sent[-1] += 1
        self.stats.bytes_sent[-1] += len(datagram)

        return datagram

    def _recv_datagram(self, hdr, datagram):

        # first, decrypt or check the CRC
        # ensure that this packet validates correctly

        try:
            pkt = Packet.from_bytes(hdr, self.session_key_bytes, datagram)
        except Exception as e:
            self.log.exception("unable to decode packet %s", hdr)
            self.stats.dropped += 1
            return False

        try:
            # TODO: log warning for packet flooding
            # if inserting dropped unacked bits then those packets will time out
            # the user may want to know to slow down the sending rate
            # and/or the protocol may want to back off.

            self.bitfield_pkt.insert(pkt.hdr.seq)
        except DuplicationError:
            self.stats.dropped += 1
            return False

        self.stats.received += 1

        t0 = self.clock()
        if int(t0) != int(self.last_recv_time):
            self.stats.pkts_recv.append(0)
            self.stats.bytes_recv.append(0)
        self.stats.pkts_recv[-1] += 1
        self.stats.bytes_recv[-1] += len(datagram)
        if len(self.stats.bytes_recv) > 5 * 60:
            self.stats.pkts_recv.pop(0)
            self.stats.bytes_recv.pop(0)
        self.last_recv_time = t0

        self._handle_ack_bits(hdr)

        for msg in pkt.msgs:
            self._recv_message(msg.type, msg.seq, msg.payload)

        return True

    def _recv_message(self, pkt_typ, msgseq, msg):

        try:
            self.bitfield_msg.insert(msgseq)
        except DuplicationError:
            print("drop duplicated seq", msgseq, Serializable.loadb(msg))
            return

        if pkt_typ == PacketType.CLIENT_HELLO:
            self._recvClientHello(msg)

        elif pkt_typ == PacketType.SERVER_HELLO:
            self._recvServerHello(msg)

        elif pkt_typ == PacketType.CHALLENGE_RESP:
            self._recvChallengeResponse(msg)

        elif pkt_typ == PacketType.KEEP_ALIVE:
            self._recvKeepAlive(msg)

        elif pkt_typ == PacketType.DISCONNECT:
            self._recvDisconnect(msg)

        elif pkt_typ == PacketType.APP_FRAGMENT:
            self._recvAppFragment(msgseq, msg)

        elif pkt_typ == PacketType.APP:
            self._recvApp(msgseq, msg)

    def _handle_ack_bits(self, hdr):

        #self.log.warning("proc ack bits %08X %d", hdr.ack_bits, len(self.pending_acks))

        for seqnum in list(self.pending_acks):
            diff = hdr.ack.diff(seqnum)
            if diff == 0 or (1 <= diff <= 32 and (hdr.ack_bits&(0x80000000>>(diff-1)))):
                self._handle_ack(seqnum)
            elif self.last_recv_time - self.pending_acks[seqnum] > self.outgoing_timeout:
                self._handle_timeout(seqnum)

    def _handle_ack(self, seqnum):

        #self.log.warning("ack %04X %+d", seqnum)
        rtt = self.clock() - self.pending_acks[seqnum]
        # this measure the round trip time from sending (assembling) the packet
        # until it was received. assume sending the message took the same
        # amount of time as sending the response. thus the latency is half
        # of the round trip time (rtt)
        self._update_latency(rtt/2.0)
        self.stats.acked += 1


        # run the callback for any message that has one
        if seqnum in self.pending_callbacks:
            for cbk in self.pending_callbacks[seqnum]:
                try:
                    cbk(True)
                except Exception as e:
                    self.log.exception("error processing callback")
            del self.pending_callbacks[seqnum]

        # clear the message from the retry queue
        if seqnum in self.pending_retry:
            for msgseq in self.pending_retry[seqnum]:
                if msgseq in self.pending_retry_msg:
                    del self.pending_retry_msg[msgseq]
            del self.pending_retry[seqnum]


        #if seqnum in self.pending_messages:
        #    del self.pending_messages[seqnum]
        del self.pending_acks[seqnum]

    def _handle_timeout(self, seqnum):
        #self.log.warning("timeout %04X", seqnum)
        self.stats.timeouts += 1
        if seqnum in self.pending_callbacks:
            for cbk in self.pending_callbacks[seqnum]:
                try:
                    cbk(False)
                except Exception as e:
                    self.log.exception("error processing callback")
            del self.pending_callbacks[seqnum]

        # clear the message from the retry queue
        if seqnum in self.pending_retry:
            for msgseq in self.pending_retry[seqnum]:
                if msgseq in self.pending_retry_msg:
                    del self.pending_retry_msg[msgseq]
            del self.pending_retry[seqnum]

        #if seqnum in self.pending_messages:
        #    del self.pending_messages[seqnum]
        del self.pending_acks[seqnum]

    def _update_latency(self, latency):

        self.latency += 0.1 * (latency - self.latency)

    def _recvClientHello(self, msg):  # pragma: no cover
        # to be implemented in a child class
        self.log.warning("received invalid packet type: client hello")

    def _recvServerHello(self, msg):  # pragma: no cover
        # to be implemented in a child class
        self.log.warning("received invalid packet type: server hello")

    def _recvChallengeResponse(self, msg):  # pragma: no cover
        # to be implemented in a child class
        self.log.warning("received invalid packet type: challenge response")

    def _recvKeepAlive(self, msg):  # pragma: no cover
        pass

    def _recvDisconnect(self, msg):
        self.log.info("received disconnect")
        self.status = ConnectionStatus.DISCONNECTING

    def _recvAppFragment(self, msgseq, fragment):

        # TODO: remove context from self.received_fragments after a timeout

        frag_id, index, count, msg = FragmentSender.parsePayload(fragment)

        # for the first fragment received from a message,
        # create a context object to store all fragments
        if frag_id not in self.received_fragments:
            self.received_fragments[frag_id] = FragmentReceiver(self, count, self.clock())

        # store the current fragment
        self.received_fragments[frag_id].receive(index, msgseq, msg)

        # check if this is the last fragment, and decode the complete message
        if self.received_fragments[frag_id].isComplete():
            receiver = self.received_fragments[frag_id]
            self._recvApp(receiver.msgseq, receiver.payload())
            del self.received_fragments[frag_id]

        # remove expired fragments
        # these are likely a result of duplicate packets being received after
        # the fragment was successfully completed
        keys = [frag_id for frag_id, receiver in self.received_fragments.items() if receiver.expired()]
        for key in keys:
            del self.received_fragments[key]

    def _recvApp(self, msgseq, msg):
        self.incoming_messages.append((msgseq, msg))

    def __repr__(self):
        return "<%s(%s:%d:%s)>" % (self.__class__.__name__, *self.addr, self.status)

class ClientServerConnection(ConnectionBase):
    def __init__(self, addr):
        super(ClientServerConnection, self).__init__(False, addr)

        self.server_public_key = None
        # ephemeral key used for this session
        self.session_key = EllipticCurvePrivateKey.new()
        self.session_salt = None
        self.session_key_bytes = None
        self.token = 0

        self.version = 1

        self.last_latency_update_time = 0

        self.time_client_hello_sent = 0
        self.connection_callback = None

    def setServerPublicKey(self, key):
        self.server_public_key = key

    def update(self):

        t0 = self.clock()

        i0 = int(t0)
        if i0 != self.last_latency_update_time:
            self.stats.latency.append(self.latency)
            self.last_latency_update_time = i0
            if len(self.stats.latency) > 5 * 60:
                self.stats.latency.pop(0)

        if self.time_client_hello_sent and self.connection_callback:
            # TODO: its possible for the server hello to come in after the timeout
            #   solution: uid in client hello that must be returned
            #             discard unrecognised or old server hello messages
            if t0 - self.time_client_hello_sent > self.temp_connection_timeout:
                self.status = ConnectionStatus.DISCONNECTED
                self.connection_callback(False)
                self.time_client_hello_sent = 0

    def _sendClientHello(self):
        self.log.debug("send client hello")
        if self.server_public_key is None:
            raise ProtocolError("no public key set")

        msg = HandshakeClientHelloMessage()
        msg.client_pubkey = self.session_key.getPublicKey()
        msg.client_version = self.version

        self._send_type(PacketType.CLIENT_HELLO, msg.dumpb(),
            RetryMode.NONE, self._ClientHelloTimeout)

        self.status = ConnectionStatus.CONNECTING

        self.time_client_hello_sent = self.clock()

    def _recvServerHello(self, data):
        self.log.debug("received server hello")

        try:
            msg = Serializable.loadb(data, server_public_key=self.server_public_key)
        except EllipticCurvePublicKey.InvalidSignature as e:
            self.status = ConnectionStatus.DISCONNECTED
            raise


        self.token = msg.token
        self.session_salt = msg.salt
        self.session_key_bytes = crypto.ecdh_client(self.session_key, msg.server_pubkey, msg.salt)


        reply = HandshakeClientChallengeResponseMessage()
        reply.token = self.token

        self._send_type(PacketType.CHALLENGE_RESP, reply.dumpb(),
            RetryMode.NONE,self._ChallengeResponseTimeout)

        self.status = ConnectionStatus.CONNECTED

        self.time_client_hello_sent = 0

        if self.connection_callback:
            self.connection_callback(True)

    def _ClientHelloTimeout(self, success):
        if not success:
            logging.error("unable to connect to server")

    def _ChallengeResponseTimeout(self, success):
        if not success:
            # expecting a keep alive or other message
            logging.error("no response to challenge")

class ServerClientConnection(ConnectionBase):
    """ Many of the events in EventHandler receive a client. That client implements
    the public API defined here.

    :attr addr: the client remote address. a 2-tuple: (host, port). This is unique per client, but may also contain PII and should not be sent to other clients
    :attr token: unique id for this client session. It is safe to use this token to uniquely identify a client as well as share the token value with other users
    :attr log: an instance of logging.Logger which logs with client context
    :attr stats: this connections ConnectionStats
    :attr latency: this current connection latency (average time it takes for the remote to receive the datagram)

    """

    def __init__(self, ctxt, addr):
        super(ServerClientConnection, self).__init__(True, addr)

        self.ctxt = ctxt

        self.server_public_key = None
        # ephemeral key used for this session
        self.session_key = EllipticCurvePrivateKey.new()
        self.session_salt = None
        self.session_key_bytes = None
        self.token = 0

        self.version = 1

    def _recvClientHello(self, data):
        msg = Serializable.loadb(data)

        # TODO: API to expose setting protocol version
        if msg.client_version != self.version:
            return

        self.token = self.ctxt.get_token()

        self.session_salt, self.session_key_bytes = crypto.ecdh_server(
            self.session_key, msg.client_pubkey)

        reply = HandshakeServerHelloMessage()
        reply.token = self.token
        reply.server_pubkey = self.session_key.getPublicKey()
        reply.salt = self.session_salt

        payload = reply.dumpb(server_root_key=self.ctxt.server_root_key)
        self.status = ConnectionStatus.CONNECTING
        self._send_type(PacketType.SERVER_HELLO, payload, RetryMode.NONE, None)

    def _recvChallengeResponse(self, data):
        msg = Serializable.loadb(data)

        if self.ctxt._validateChallengeResponse(self, msg.token):
            self.status = ConnectionStatus.CONNECTED
            self.ctxt._onConnect(self)
        else:
            client.log.warning("challenge failed")
            self.status = ConnectionStatus.DISCONNECTED

    def disconnect(self):
        """ force the server to drop the connection
        """
        super().disconnect()

    def update(self):
        """ private send queued messages to remote

        returns the packet to be sent
        """

        pkt = None
        if self.clock() - self.last_send_time > self.send_interval:
            pkt = self._build_packet()

            t0 = self.clock()
            for seqnum in list(self.pending_acks):
                if t0 - self.pending_acks[seqnum] > self.outgoing_timeout:
                    self._handle_timeout(seqnum)

        if pkt:
            self.stats.pkts_sent[-1] += 1
            self.stats.bytes_sent[-1] += pkt.total_size(self.session_key_bytes)

            return pkt, self.session_key_bytes, self.addr
        return None

    def send_guaranteed(self, payload: bytes, callback:SendCallback=None):

        """ send the message and guarantee delivery by using RetryMode.RETRY_ON_TIMEOUT

        :param msg: the bytes to send
        :param callback: a function which is called when the message has been
            acked or after a timeout. The function should accept a single
            boolean which is true when the message is acked and false otherwise.
        """
        self.send(payload, retry=RetryMode.RETRY_ON_TIMEOUT, callback=callback)

SerializableType.next_type_id = 256