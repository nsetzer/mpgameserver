
__version__ = "0.2.0"

from mpgameserver.auth import Auth
from mpgameserver.client import UdpClient
from mpgameserver.connection import SeqNum, ConnectionStatus, ProtocolError, RetryMode
from mpgameserver.context import ServerContext
from mpgameserver.crypto import EllipticCurvePrivateKey, EllipticCurvePublicKey
from mpgameserver.handler import EventHandler
from mpgameserver.logger import setupLogger
from mpgameserver.serializable import SerializableType, Serializable, SerializableEnum, Default
from mpgameserver.task import TaskPool
from mpgameserver.timer import Timer
from mpgameserver.twisted import TwistedServer, ThreadedServer
from mpgameserver.http_server import get, put, delete, post, \
    Router, Resource, HTTPServer, \
    Response, JsonResponse, SerializableResponse
from mpgameserver.http_client import HTTPClient
from mpgameserver.dispatch import ServerMessageDispatcher, ClientMessageDispatcher, \
    server_event, client_event

# pygame is an optional dependency
try:
    from mpgameserver.graph import LineGraph, AreaGraph
    from mpgameserver.guiserver import GuiServer
except ImportError as e:  # pragma: no cover
    # print(e.name)
    # print(e.msg)
    pass

# pil + pygame are optional
try:
    from mpgameserver.captcha import Captcha
except ImportError as e:  # pragma: no cover
    # print(e.name)
    # print(e.msg)
    pass