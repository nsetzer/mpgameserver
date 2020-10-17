
import sys

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

from .server import UdpServerThread
from . import crypto
from .connection import ServerContext, ConnectionStatus, \
    ServerClientConnection, PacketHeader, Packet, PacketType

from threading import Thread

class TwistedServer(DatagramProtocol):
    """ a headless server implementation
    """

    def __init__(self, ctxt, addr):
        """
        :param ctxt: A [ServerContext](#servercontext) instance
        :param addr: 2-tuple host, port
            host can be "::" to bind to an ipv6 address
        """

        self.addr = addr

        self.ctxt = ctxt
        self.thread = UdpServerThread(None, self.ctxt)
        self.thread.send = self.sendPackets

    def sendPackets(self, seq):
        """ private send a sequence of packets
        """

        reactor.callFromThread(self.sendPacketsUnsafe, seq)

    def sendPacketsUnsafe(self, seq):
        """ private send a sequence of packets
        """

        for pkt, key, addr in seq:
            datagram = pkt.to_bytes(key)
            self.transport.write(datagram, addr)

    def datagramReceived(self, datagram, addr):
        """ private called when a datagram is receeived from addr
        """
        if addr[0] in self.ctxt.blocklist:
            return

        try:
            hdr = PacketHeader.from_bytes(True, datagram)

            self.thread.append(addr, hdr, datagram)

        except Exception as e:
            msg = "%s:%d dropping packet (%d bytes) from peer: %s"
            if self.ctxt.access_log:
                self.ctxt.access_log.warning(msg, *addr, len(datagram), e)
            else:
                self.ctxt.log.warning(msg, *addr, len(datagram), e)

    def run(self):
        """ run the server.

        """

        if sys.platform != "win32":
            # todo: install signal handler?
            pass

        self.thread.start()
        self.ctxt.log.info("server listening on %s:%d" % (self.addr))
        reactor.listenUDP(self.addr[1], self, interface=self.addr[0], maxPacketSize=2048)
        reactor.run(installSignalHandlers=0)
        self.ctxt.log.info("server stopped")

    def stop(self):
        """ stop the server
        """
        # indicate the thread should stop
        self.ctxt.shutdown()
        # send a dummy packet just to wake up the thread
        self.thread._wake()
        # wait for the thread to exit
        self.thread.join()
        # finally stop the reactor
        reactor.callFromThread(reactor.stop)


class ThreadedServer(Thread):
    """ a headless server implementation, running in a background thread
    """

    def __init__(self, ctxt, addr):
        super(ThreadedServer, self).__init__()
        self.daemon = True

        self.server = TwistedServer(ctxt, addr)

    def run(self):

        self.server.run()

    def stop(self):
        """ stop the server, wait for the thread to exit
        """
        self.server.stop()

        self.join()