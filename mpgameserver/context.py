
import os
import sys
import logging
import struct

from .crypto import EllipticCurvePrivateKey, EllipticCurvePublicKey
from .logger import log, setupLogger
from typing import Set

class ServerContext(object):
    """
    The ServerContext holds the configuration for the server.

    This class is not thread safe. the configuration should be set prior to calling the run method of the server
    """
    def __init__(self, handler, root_key=None):
        """

        :param handler: an instance of an EventHandler
        :param root_key: an EllipticCurvePrivateKey used for signing messages.
            The client will use the public to to verify the signature.
            If not given a debug key is used.
        """

        super(ServerContext, self).__init__()

        self.handler = handler

        if root_key is None:
            self.server_root_key = EllipticCurvePrivateKey.unsafeTestKey()
        else:
            self.server_root_key = root_key

        self.connections = {}  # addr ->client
        self.temp_connections = {}  # addr ->client

        self.interval = 1/60
        self._maximum_sleep_time = 1/60

        self.blocklist = set()

        self.access_log = None

        self.log = log

        self.connection_timeout = 5.0
        self.temp_connection_timeout = 2.0
        self.keep_alive_interval = .1
        self.outgoing_timeout = 1.0

        self._active = True

    def get_token(self):
        """ private generate a unique token """
        token, = struct.unpack(">L", os.urandom(4))
        while token == 0 or token in self.connections or token in self.temp_connections:
            token, = struct.unpack(">L", os.urandom(4))
        return token

    def setInterval(self, interval: float):
        """
        configure the server tick rate (server frame rate)

        :param interval: the seconds per server tick
        """
        self.interval = interval
        self._maximum_sleep_time = interval

    def setKeepAliveInterval(self, interval):
        """ configure the timeout for sending keep alive datagrams to clients.

        :param timeout: the timeout in seconds. The default is .1 seconds.
        """
        self.keep_alive_interval = interval

    def setConnectionTimeout(self, timeout):
        """ configure the timeout for closing a connection if no message is
        received after a period of time.

        :param timeout: the timeout in seconds. The default is 5 seconds.
        """
        self.connection_timeout = timeout

    def setTempConnectionTimeout(self, timeout):
        """ configure the timeout for closing a connection if the
        connection handshake is not completed in time

        :param timeout: the timeout in seconds. The default is 2 seconds.
        """
        self.temp_connection_timeout = timeout

    def setMessageTimeout(self, timeout):
        """ configure the timeout for waiting for the ack for a datagram

        :param timeout: the timeout in seconds. The default is 1 second.
        """
        self.outgoing_timeout = timeout

    def setBlockList(self, blocklist: Set[str]):
        """ set IP addresses to block.

        blocked IP addresses will have any datagrams received dropped before processing

        :param blocklist: a set of IP addresses to block
        """
        self.blocklist = blocklist

    def enableAccessLogs(self, path):
        """ configure an alternative file path for logging IP addresses that connect to the server

        :param path: a file path or None to disable access logging
        """

        if not path:
            self.access_log = None
        else:
            self.access_log = setupLogger('mpgameserver.AccessLog', path)

    def _validateChallengeResponse(self, client, token):
        """ validate the challenge resposne"""
        other = self.temp_connections.get(client.addr, None)
        if other and other.token == token:
            return True
        return False

    def _onConnect(self, client):
        """ called when the challenge resposne is validated """

        if client.addr in self.temp_connections:
            del self.temp_connections[client.addr]
            self.connections[client.addr] = client

            self.onConnect(client)

    def onConnect(self, client):
        """ private call the handler connect event """
        if self.access_log is not None:
            self.access_log.info("client connected %s:%d (%d)", *client.addr, len(self.connections))
        else:
            client.log.info("client connected (%d)", len(self.connections))
        try:
            self.handler.connect(client)
        except Exception as e:
            client.exception("unhandled error during connect")


    def onDisconnect(self, client):
        """ private call the handler disconnect event """
        client.log.info("client disconnected (%d)", len(self.connections)-1)
        try:
            self.handler.disconnect(client)
        except Exception as e:
            client.exception("unhandled error during disconnect")

    def shutdown(self):
        """ stop the server if it is running


        """
        self._active = False