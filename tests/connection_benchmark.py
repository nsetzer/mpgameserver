#! cd .. && python -m tests.connection_benchmark
import os
import timeit
import unittest

from mpgameserver.connection import SeqNum, ConnectionBase, \
    Packet, PacketHeader, PacketType, \
    PacketError, \
    ClientServerConnection, ServerClientConnection, ServerContext

from mpgameserver.serializable import Serializable
from mpgameserver import crypto

from cryptography.hazmat.primitives.constant_time import bytes_eq

def encodedecode(pkt_size, key):

    pkt = Packet()
    typ = PacketType.APP if key else PacketType.CLIENT_HELLO
    typ = PacketType.APP
    pkt.msg = os.urandom(pkt_size)
    pkt.hdr = PacketHeader.create(False, 0, typ, SeqNum(1), SeqNum(1), 0)
    pkt.hdr.length = len(pkt.msg)
    pkt.hdr.count = 1
    datagram = pkt.to_bytes(key)
    hdr = PacketHeader.from_bytes(True, datagram)
    pkt = Packet.from_bytes(hdr, key, datagram)

def benchmark_encodedecode():
    key = b"\x00"*32

    pkt_size = 128
    for pkt_size in [0, Packet.MAX_PAYLOAD_SIZE//4, Packet.MAX_PAYLOAD_SIZE//2, Packet.MAX_PAYLOAD_SIZE]:
        for n in [10,50,100,500,1000,5000]:
            result = timeit.timeit(lambda: encodedecode(pkt_size, key), number=n)
            print("%5d %5d %.9f %.9f %d" % (pkt_size, n, result, result/n, 1/(result/n)))

def encryptdecrypt(fn_enc, fn_dec, key, iv, aad, data):

    ct = fn_enc(key, iv, aad, data)

    pt = fn_dec(key, iv, aad, ct)

    assert bytes_eq(data, pt)

def benchmark_encryptdecrypt():

    algos = [
        'gcm',
        'ccm',
        'ctr',
    ]

    key = os.urandom(16)
    aad = os.urandom(20)
    iv = aad[:12]
    data = os.urandom(32)


    for algo in algos:

        fn_enc = getattr(crypto, 'encrypt_%s' % algo)
        fn_dec = getattr(crypto, 'decrypt_%s' % algo)

        for n in [10,50,100,500,1000,5000,10000]:
            result = timeit.timeit(lambda: encryptdecrypt(fn_enc, fn_dec, key, iv, aad, data), number=n)
            print("%s %5d %.9f %.9f %d" % (algo, n, result, result/n, 1/(result/n)))




def main():

    #print(Packet.MAX_PAYLOAD_SIZE*0x2000)
    #print(Packet.MAX_PAYLOAD_SIZE*0x2000/1024)

    #key = None

    benchmark_encryptdecrypt()

if __name__ == '__main__':
    main()