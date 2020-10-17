#! cd .. && python -m mpgameserver.server

"""
# Server

The server is made up of three main components: The EventHandler, ServerContext and the Server itself.

The ServerContext is used to configure the behavior of the server at runtime.
The EventHandler contains all of the game logic, and reacts to server events
such as clients connecting, disconnecting, and receiving messages.

There are two implementations for the Server: The TwistedServer is based on
the twisted python library. The GuiServer further wraps the twisted server
into a pygame gui.

"""
#hysterysis on connection latency
#    every frame add frame time to a counter if above threshold latency
#    or subtract half frame time
#    clamp value to a range +/- some maximum
#        algo only needs to run if not in best/worst tier
#    if above/below a threshold move into the next latency quality teir
#    user must be in a given tier for 1 second before
#        starting to calculate again

import os
import random
import socket
import struct
import time
import logging
import math
from threading import Thread, Lock, Condition

from .crypto import EllipticCurvePrivateKey, EllipticCurvePublicKey

from .connection import ServerContext, ConnectionStatus, \
    ServerClientConnection, PacketHeader, Packet, PacketType
from .handler import EventHandler

from .logger import LOGLEVEL_TRACE
from .timer import Timer

def sleep(duration):

    if duration < 0.001:
        return

    start = time.perf_counter()
    slept_for = 0

    while duration - slept_for > 0.0005:
        time.sleep(min((duration - slept_for)*.5, 0.0005))
        slept_for =  time.perf_counter() - start

class UdpServerThread(Thread):
    """

    The server makes use of two connection pools.
    The temporary connection pool is used for connections which
    have not sent the CHALLENGE_RESP. It prevents these connections
    from sending other messages without a proper connection.
    Clients that pass the CHALLENGE_RESP are then moved to the
    primary connection pool, and the connected event is raised in the
    event handler.

    """
    def __init__(self, sock, ctxt):
        super(UdpServerThread, self).__init__()
        self.daemon = True

        self.sock = sock
        self.ctxt = ctxt
        self.queue = []
        self.lk_queue = Lock()
        self.cv_queue = Condition(self.lk_queue)

        self.perf = [0,0,0,0,0]
        self.perf_data = [[1,0,0,0,1] for i in range(5 * 60)]
        self.frame_rate = [0] * 5 * 60
        self.received_count = 0

        # seconds per tick -- the average should track the interval
        self.spt = self.ctxt.interval

    def append(self, addr, hdr, datagram):

        with self.lk_queue:
            self.queue.append((addr, hdr, datagram))
            self.cv_queue.notify_all()

    def _wake(self):
        with self.lk_queue:
            self.cv_queue.notify_all()

    def send(self, seq):

        for pkt, key, addr in seq:
            try:
                datagram = pkt.to_bytes(key)
            except Exception as e:
                self.ctxt.log.exception("%s:%d unable to encode packet" % addr)

            self.sock.sendto(datagram, addr)

    def update_stats(self):
        self.perf_data.append(self.perf)
        if len(self.perf_data) > 5 * 60:
            self.perf_data.pop(0)
        self.perf = [0,0,0,0,0]

        self.received_count = 0
        self.frame_rate.append(1/self.spt)
        if len(self.frame_rate) > 5 * 60:
            self.frame_rate.pop(0)

    def run(self):

        _queue = []

        t0 = time.time()
        prev_report = int(t0)
        dt = self.ctxt.interval

        try:
            self.ctxt.handler.starting()
        except Exception as e:
            self.ctxt.log.exception("unhandled exception during startup")

        previous_update_time = time.time()

        self.ctxt.log.info("server main loop starting")
        while self.ctxt._active:

            p1 = time.time()

            # process messages received from the clients
            while _queue:
                addr, hdr, datagram = _queue.pop(0)
                try:
                    # process messages received from connected clients
                    if addr in self.ctxt.connections:
                        client = self.ctxt.connections[addr]
                        client._recv_datagram(hdr, datagram)

                        for seqnum, msg in client.incoming_messages:
                            try:
                                self.ctxt.handler.handle_message(client, seqnum, msg)
                            except Exception as e:
                                client.log.exception("error processing message: %s", e)
                        client.incoming_messages = []

                    # process messages from users who are connecting
                    elif addr in self.ctxt.temp_connections:
                        if hdr.pkt_type != PacketType.CHALLENGE_RESP:
                            continue

                        client = self.ctxt.temp_connections[addr]
                        client._recv_datagram(hdr, datagram)

                    # message is from a new client
                    else:
                        if hdr.pkt_type != PacketType.CLIENT_HELLO:
                            continue

                        self.ctxt.log.info("%s:%d received new client", *addr)
                        client = ServerClientConnection(self.ctxt, addr)
                        client.send_keep_alive_interval = self.ctxt.keep_alive_interval
                        client.outgoing_timeout = self.ctxt.outgoing_timeout
                        self.ctxt.temp_connections[addr] = client
                        client._recv_datagram(hdr, datagram)
                except Exception as e:
                    self.ctxt.log.exception("%s:%d error processing datagram", *addr)

            # run the handler update event
            # measure the time since the last tick update
            u0 = p2 = time.time()
            tick_time = u0 - previous_update_time
            previous_update_time = u0
            try:
                self.ctxt.handler.update(tick_time)
            except Exception as e:
                self.ctxt.log.exception("unhandled error during handler update")

            # update all of the connections, handle disconnect events
            p3 = time.time()
            sending = []
            for client in list(self.ctxt.connections.values()):
                try:
                    # if diconnecting, send a final packet to remote
                    if client.status == ConnectionStatus.DISCONNECTING:
                        # this is a bit of a hack to provide feedback to the client
                        client.disconnect() # changes state to disconnected

                    # --------------
                    # if disconnected remove the connection

                    if client.status == ConnectionStatus.DISCONNECTED or client.timedout(self.ctxt.connection_timeout):

                        try:
                            self.ctxt.onDisconnect(client)
                            msg = client.update()
                            if msg is not None:
                                sending.append(msg)
                        except Exception as e:
                            client.log.exception("unhandled error during client disconnect")
                        del self.ctxt.connections[client.addr]
                    else:
                        msg = client.update()
                        if msg is not None:
                            sending.append(msg)
                except Exception as e:
                    client.log.exception("unhandled error during client update")

            for client in list(self.ctxt.temp_connections.values()):
                try:
                    if client.status == ConnectionStatus.DISCONNECTED or client.timedout(self.ctxt.temp_connection_timeout):
                        self.ctxt.log.info("%s:%d peer timed out connecting", *client.addr)
                        del self.ctxt.temp_connections[client.addr]
                    else:
                        msg = client.update()
                        if msg is not None:
                            sending.append(msg)
                except Exception as e:
                    client.log.exception("unhandled error during client update")

            self.send(sending)

            p4 = time.time()

            # ------

            # check for incoming messages
            if not _queue:
                with self.lk_queue:

                    while self.ctxt._active and not self.queue:
                        # go to sleep if there are no connections
                        if not self.ctxt.connections:
                            self.cv_queue.wait()

                            previous_update_time = time.time()
                        else:
                            #self.cv_queue.wait(self.ctxt.interval/3)
                            #t0 = time.time()
                            break

                    self.received_count += len(self.queue)
                    _queue.extend(self.queue)
                    self.queue = []

            t1 = time.time()

            dt = min(self.ctxt.interval, t1 - t0)
            dt = t1 - t0
            sleep_for = max(0, self.ctxt.interval - dt)
            if self.spt  < self.ctxt.interval:
                sleep(sleep_for)

            p5 = t0 = time.time()

            self.perf[0] += p5 - p1 # total elapsed time
            self.perf[1] += p2 - p1 # message handler
            self.perf[2] += p3 - p2 # update
            self.perf[3] += p4 - p3 # network send
            self.perf[4] += p5 - p4 # idle time

            now = int(t0)
            if prev_report != now:
                self.update_stats()
                prev_report = now

            # alpha := 1 - exp(-1/60)
            self.spt += (0.01653) * (p5-p1 - self.spt)

        self.ctxt.log.info("server main loop exited")

        # disconnect all clients before stopping the server
        # doesnt send an ack to the remote client
        for client in list(self.ctxt.connections.values()):
            try:
                self.ctxt.onDisconnect(client)
            except Exception as e:
                client.log.exception("unhandled error during client disconnect")
            del self.ctxt.connections[client.addr]

        try:
            self.ctxt.handler.shutdown()
        except Exception as e:
            self.ctxt.log.exception("unhandled exception during shutdown")

# reference implementation for a UDP server
class _UdpServer(object):  # pragma: no cover
    def __init__(self, ctxt, addr):
        super(_UdpServer, self).__init__()
        self.addr = addr

        self.ctxt = ctxt

    def run(self):

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(self.addr)

        self.ctxt.log.info("listening on %s:%d", *self.addr)

        self.thread = UdpServerThread(self.sock, self.ctxt)
        self.thread.start()

        while self.ctxt._active:
            try:
                datagram, addr = self.sock.recvfrom(Packet.RECV_SIZE)
            except ConnectionResetError as e:
                self.ctxt.log.warning("recvfrom error: %s:%s: %s" % (type(e), e, self.sock.fileno()))
                break

            if addr[0] in self.ctxt.blocklist:
                continue

            try:
                hdr = PacketHeader.from_bytes(True, datagram)

                self.thread.append(addr, hdr, datagram)

            except Exception as e:
                msg = "%s:%d dropping packet (%d bytes) from peer: %s"
                if self.ctxt.access_log:
                    self.ctxt.access_log.warning(msg, *addr, len(datagram), e)
                else:
                    self.ctxt.log.warning(msg, *addr, len(datagram), e)
