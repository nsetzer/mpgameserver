
import sys

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import ssl, reactor
try:
    from twisted.internet import ssl
except ImportError as e:
    pass

from .server import UdpServerThread
from . import crypto
from .connection import ServerContext, ConnectionStatus, \
    ServerClientConnection, PacketHeader, Packet, PacketType
from .http_server import HTTPFactory

from threading import Thread
import signal

class TwistedServer(DatagramProtocol):
    """ a headless server implementation
    """

    def __init__(self, ctxt, addr, install_signals=True):
        """
        :param ctxt: A [ServerContext](#servercontext) instance
        :param addr: 2-tuple host, port
            host can be "::" to bind to an ipv6 address
        :param install_signals: whether to install a default signal handler
            when running on UNIX style operating systems
        """

        self.addr = addr

        self.ctxt = ctxt
        self.thread = UdpServerThread(None, self.ctxt)
        self.thread.send = self.sendPackets

        self._tcp_router = None
        self._tcp_addr = None
        self._tcp_privkey_path = None
        self._tcp_cert_path = None

        self.install_signals = install_signals

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

    def listenTCP(self, router, addr, privkey=None, cert=None):
        """
        Enable a TCP listener. Must be called prior to run.

        :param router:  an router instance containing mapped endpoints
        :param addr:    a 2-tuple (host: str, port: int)
        :param privkey: the path to a ssl private key
        :param cert:    the path to a ssl full chain certificate (pem file)
        """
        self._tcp_router = router
        self._tcp_addr = addr
        self._tcp_privkey_path = privkey
        self._tcp_cert_path = cert

    def _handle_signal(self, *args):
        self.stop()

    def run(self):
        """ run the server.

        """

        if self.install_signals and sys.platform != "win32":
            for sig in (signal.SIGABRT, signal.SIGILL, signal.SIGINT, signal.SIGSEGV, signal.SIGTERM):
                signal.signal(sig, self._handle_signal)

        self.thread.start()

        self.ctxt.log.info("udp server listening on %s:%d" % (self.addr))
        reactor.listenUDP(self.addr[1], self, interface=self.addr[0], maxPacketSize=2048)

        cert = None
        if self._tcp_privkey_path is not None:
            keyAndCert = ""
            with open(self._tcp_privkey_path) as key:
                keyAndCert += key.read()
            with open(self._tcp_cert_path) as cert:
                keyAndCert += cert.read()

            cert = ssl.PrivateCertificate.loadPEM(keyAndCert)

        if self._tcp_addr:


            if cert:
                # https://stackoverflow.com/questions/57812501/python-twisted-is-it-possible-to-reload-certificates-on-the-fly
                opts = cert.options()
                # TODO: setting opts._context = None should force a reload of the cert file
                port = reactor.listenSSL(self._tcp_addr[1],
                    HTTPFactory(router=self._tcp_router),
                    opts,
                    interface=self._tcp_addr[0])
                self.ctxt.log.info("tls server listening on %s:%d" % (self._tcp_addr))
            else:
                port = reactor.listenTCP(self._tcp_addr[1],
                    HTTPFactory(router=self._tcp_router),
                    interface=self._tcp_addr[0])
                self.ctxt.log.info("tcp server listening on %s:%d" % (self._tcp_addr))

            for endpt in self._tcp_router.endpoints:
                print("%-7s %s" % (endpt.method, endpt.pattern))


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

        self.server = TwistedServer(ctxt, addr, install_signals=False)

    def listenTCP(self, router, addr, privkey=None, cert=None):
        """
        Enable a TCP listener. Must be called prior to run.

        :param router:  an router instance containing mapped endpoints
        :param addr:    a 2-tuple (host: str, port: int)
        :param privkey: the path to a ssl private key
        :param cert:    the path to a ssl full chain certificate (pem file)
        """
        self.server.listenTCP(router, addr, privkey, cert)

    def run(self):

        self.server.run()

    def stop(self):
        """ stop the server, wait for the thread to exit
        """
        self.server.stop()

        self.join()
