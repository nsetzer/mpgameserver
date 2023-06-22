#! cd .. && python -m demo.http
import os
import sys
import json
import time
import gzip
import io
import threading
import base64
import hashlib
import struct
from enum import Enum

from threading import Thread
from typing import Dict, Tuple, IO
from collections import defaultdict, OrderedDict

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from twisted.web import http

from urllib.parse import urlparse, unquote, parse_qs
import re

from . import crypto
from .serializable import Serializable


from .logger import mplogger

# https://twistedmatrix.com/documents/21.2.0/api/twisted.web.http.Request.html

def path_join_safe(root_directory: str, filename: str):
    """
    join the two path components ensuring that the returned value
    exists with root_directory as prefix.

    Using this function can prevent files not intended to be exposed by
    a webserver from being served, by making sure the returned path exists
    in a directory under the root directory.

    :param root_directory: the root directory. This must allways be provided by a trusted source.
    :param filename: a relative path to a file. This may be provided from untrusted input
    """

    root_directory = root_directory.replace("\\", "/")
    filename = filename.replace("\\", "/")

    # check for illegal path components
    parts = set(filename.split("/"))
    if ".." in parts or "." in parts:
        raise ValueError("invalid path")

    path = os.path.join(root_directory, filename)
    path = os.path.abspath(path)

    return path

class Response(object):
    def __init__(self, payload=None, status_code=200, headers=None, compress=False):
        super(Response, self).__init__()
        self.status_code = status_code
        self.headers = {} if headers is None else headers
        self.payload = b"" if payload is None else payload
        self.compress = compress
        self.upgrade = False # true if the response is an upgrade to websockets

        if isinstance(self.payload, str):
            self.payload = self.payload.encode("utf-8")

    def _get_payload(self, request):
        """ return the payload in a form suitable for sending to the client
        """

        if self.compress:
            # TODO: check if request headers suport compression

            gzip_buffer = io.BytesIO()
            gzip_file = gzip.GzipFile(mode='wb',
                                      fileobj=gzip_buffer)
            gzip_file.write(self.payload)
            gzip_file.close()

            self.payload = gzip_buffer.getvalue()

            self.headers['Vary'] = 'Accept-Encoding'
            self.headers['Content-Encoding'] = 'gzip'

        return self.payload

    def __repr__(self):
        return "<%s(%d)>" % (self.__class__.__name__, self.status_code)

    def __str__(self):
        return "<%s(%d)>" % (self.__class__.__name__, self.status_code)

class ErrorResponse(Response):
    """ Represents an http error response returned from the server

    Clients will use this class to hold the original exception raised
    by urllib.

    """

    def __init__(self, obj, status_code=400, headers=None):
        super(ErrorResponse, self).__init__(obj, status_code, headers)

class JsonResponse(Response):
    def __init__(self, obj, status_code=200, headers=None):
        super(JsonResponse, self).__init__(obj, status_code, headers)

    def _get_payload(self, request):
        """ return the payload in a form suitable for sending to the client
        """

        # TODO: support compression (copy from above)

        payload = super()._get_payload(request)
        encoded = json.dumps(payload).encode('utf-8') + b"\n"
        self.headers['Content-Type'] = "application/json"
        self.headers['Content-Length'] = str(len(encoded))
        return encoded

class WebsocketUpgradeResponse(Response):
    def __init__(self, endpt, headers):
        super(WebsocketUpgradeResponse, self).__init__(b"", 101, headers)
        self.upgrade = True
        self.endpt = endpt

class SerializableResponse(Response):
    def __init__(self, obj, status_code=200, headers=None):
        super(SerializableResponse, self).__init__(obj, status_code, headers)

    def _get_payload(self, request):
        """ return the payload in a form suitable for sending to the client
        """

        payload = super()._get_payload(request)
        encoded = payload.dumpb()
        self.headers['Content-Type'] = "application/x-serializable"
        self.headers['Content-Length'] = str(len(encoded))
        return encoded

# https://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-09.html#rfc.section.4.7

class WebSocketOpCodes(Enum):
    Open = 0xFF # non standard
    Close = 0x8
    Ping = 0x9
    Pong = 0xA
    Text = 0x1  # utf-8
    Binary = 0x2

class WebSocketFrame(object):
    def __init__(self):
        super(WebSocketFrame, self).__init__()

        self.flags = lambda: None
        self.flags.fin    = 0
        self.flags.rsv1   = 0
        self.flags.rsv2   = 0
        self.flags.rsv3   = 0
        self.flags.opcode = 0
        self.flags.mask   = 0
        self.flags.length = 0
        self.payload_length = 0
        self.masking_key = b"\x00\x00\x00\x00"
        self.payload = b""

    def parseHeader(self, hdr):
        flags, length = struct.unpack("!BB", hdr)

        self.flags.fin    = (flags & 0x80) >> 7
        self.flags.rsv1   = (flags & 0x40) >> 6
        self.flags.rsv2   = (flags & 0x20) >> 5
        self.flags.rsv3   = (flags & 0x10) >> 4
        self.flags.opcode = WebSocketOpCodes((flags & 0x0F) >> 0)
        self.flags.mask   = 1 if (length & 0x80) else 0
        self.flags.length = length & 0x7F

    def readHeader(self, socket):

        hdr = socket.recv(2)
        if not hdr:
            raise ValueError()
        if hdr:
            self.parseHeader(hdr)
            return True
        return False

    def readDataHeader(self, socket):

        length = self.flags.length

        if length == 126:
            length, = struct.unpack("!H", socket.recv(2))
        if length == 127:
            length, = struct.unpack("!Q", socket.recv(8))

        self.payload_length = length

        if self.flags.mask:
            self.masking_key = socket.recv(4)

    def readData(self, socket):

        self.payload = bytearray(socket.recv(self.payload_length))

        if self.flags.mask:
            for i in range(len(self.payload)):
                self.payload[i] ^= self.masking_key[i%4];

    def serializeHeader(self):

        flags = ((self.flags.fin) << 7) | \
                ((self.flags.rsv1) << 6) | \
                ((self.flags.rsv2) << 5) | \
                ((self.flags.rsv3) << 4) | \
                ((self.flags.opcode.value) << 0)

        if self.payload_length <= 125:
            length = self.payload_length
        elif self.payload_length <= 0xFFFF:
            length = 126
        else:
            length = 127

        length |= self.flags.mask << 7

        return struct.pack("BB", flags, length)

    def writeHeader(self, socket):

        hdr = self.serializeHeader()
        socket.sendall(hdr)

    def serializeDataHeader(self):
        hdr = []

        if self.payload_length > 125:
            if self.payload_length < 0XFFFF:
                hdr.append(struct.pack("!H", self.payload_length))
            else:
                hdr.append(struct.pack("!Q", self.payload_length))

        if self.flags.mask:
            hdr.append(self.masking_key)

        return b"".join(hdr)

    def writeDataHeader(self, socket):

        hdr = self.serializeDataHeader()
        if hdr:
            socket.sendall(hdr)

    def writeData(self, socket):

        socket.sendall(self.payload)

    def __repr__(self):
        opcode = self.flags.opcode.name
        return f"WebSocketFrame({opcode}){{{self.payload}}}"

    @staticmethod
    def Ping(message=b'hello'):
        frame = WebSocketFrame()
        frame.flags.fin = 1
        frame.flags.opcode = WebSocketOpCodes.Ping
        frame.payload = message
        frame.payload_length = len(frame.payload)
        return frame

    @staticmethod
    def Pong(message=b'hello'):
        frame = WebSocketFrame()
        frame.flags.fin = 1
        frame.flags.opcode = WebSocketOpCodes.Pong
        frame.payload = message
        frame.payload_length = len(frame.payload)
        return frame

    @staticmethod
    def Close(status=200, message=b'OK'):
        frame = WebSocketFrame()
        frame.flags.fin = 1
        frame.flags.opcode = WebSocketOpCodes.Close
        frame.payload = struct.pack("!H", status) + message
        frame.payload_length = len(frame.payload)
        return frame

    @staticmethod
    def Text(message=''):
        frame = WebSocketFrame()
        frame.flags.fin = 1
        frame.flags.opcode = WebSocketOpCodes.Text
        frame.payload = message.encode("utf-8")
        frame.payload_length = len(frame.payload)
        return frame

    @staticmethod
    def Binary(message=b''):
        frame = WebSocketFrame()
        frame.flags.fin = 1
        frame.flags.opcode = WebSocketOpCodes.Binary
        frame.payload = message
        frame.payload_length = len(frame.payload)
        return frame

def readFrameFactory(socket):

    def readFrame():

        frame = WebSocketFrame()
        frame.readHeader(socket)
        frame.readDataHeader(socket)
        frame.readData(socket)

        return frame

    return readFrame

def writeFrameFactory(socket):

    def writeFrame(frame):

        frame.writeHeader(socket)
        frame.writeDataHeader(socket)
        frame.writeData(socket)

        return b""

    return writeFrame

class WebSocketTemporaryRingBuffer(object):
    """ this is a sample ring buffer designed to figure out the api
        replace with a better implementation
    """
    def __init__(self, request):
        super(WebSocketTemporaryRingBuffer, self).__init__()
        self.request = request
        self.buf = b""

    def _push(self, data):
        self.buf += data

    def recv(self, n):
        data = self.buf[:n]
        self.buf = self.buf[n:]
        return data

    def sendall(self, data):
        self.request.chunked = 0
        self.request.write(data)

class WebSocketTemporaryHandler(object):
    """ this is a simple handler designed to figure out the api
        replace with a better implementation

        the handler has all of the state context for
        websocket connect and disconnect events
    """
    next_uid = 1

    def __init__(self, hostport, query, headers, buffer, endpt):

        self._buffer = buffer
        self._endpt = endpt
        self.closed = False

        self.hostport = hostport
        self.query = query
        self.headers = headers

        self.uid = WebSocketTemporaryHandler.next_uid
        WebSocketTemporaryHandler.next_uid += 1

        self._readFrame = readFrameFactory(self._buffer)
        self._writeFrame = writeFrameFactory(self._buffer)

    def send(self, message):

        if isinstance(message, str):
            frame = WebSocketFrame.Text(message)
        else:
            raise TypeError(type(message))

        self._writeFrame(frame)

    def open(self):
        self._endpt.callback(self, WebSocketOpCodes.Open, None)

    def close(self):
        if not self.closed:
            frame = WebSocketFrame.Close()
            self._writeFrame(frame)
        self.closed = True

    def __call__(self, data):
        self._buffer._push(data)

        frame = self._readFrame()

        if not frame.flags.mask:
            raise Exception("client mask bit not set")

        if frame.flags.opcode == WebSocketOpCodes.Text:
            frame.payload = frame.payload.decode("utf-8")

        # TODO: catch and close?
        self._endpt.callback(self, frame.flags.opcode, frame.payload)

        if frame.flags.opcode == WebSocketOpCodes.Close:
            self.close()

def get(path):
    """decorator which registers a class method as a GET handler"""
    def decorator(f):
        f._route = path
        f._methods = ['GET']
        return f
    return decorator

def put(path, max_content_length=5*1024*1024):
    """decorator which registers a class method as a PUT handler"""
    def decorator(f):
        f._options = {'max_content_length': max_content_length}
        f._route = path
        f._methods = ['PUT']
        return f
    return decorator

def post(path, max_content_length=5*1024*1024):
    """decorator which registers a class method as a POST handler"""
    def decorator(f):
        f._options = {'max_content_length': max_content_length}
        f._route = path
        f._methods = ['POST']
        return f
    return decorator

def delete(path):
    """decorator which registers a class method as a DELETE handler"""
    def decorator(f):
        f._route = path
        f._methods = ['DELETE']
        return f
    return decorator

def websocket(path):
    def decorator(f):
        f._route = path
        f._methods = ['GET']
        f._websocket = True
        return f
    return decorator

def header(header):
    def decorator(f):
        if not hasattr(f, '_header'):
            f._header = []
        f._header.append(header)
        return f
    return decorator

def param(param):
    def decorator(f):
        if not hasattr(f, '_param'):
            f._param = []
        f._param.append(param)
        return f
    return decorator

def ratelimit(rate):
    """ not implemented

    this could be used to set a per-route ratelimit
    currently there is a global rate limit for all routes instead.

    """

    parts = rate.split("/")
    if len(parts) != 2:
        raise ValueError(rate)
    if parts[1] not in ("second", "minute", "hour", "day"):
        raise ValueError(rate)

    count = int(parts[0])
    unit = parts[1]

    def decorator(f):
        f._ratelimit = (count, unit)
        return f

    return decorator

class CacheDict(OrderedDict):

    def __init__(self, *args, cache_len: int = 128, **kwargs):
        assert cache_len > 0
        self.cache_len = cache_len

        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        super().move_to_end(key)

        while len(self) > self.cache_len:
            oldkey = next(iter(self))
            super().__delitem__(oldkey)

    def __getitem__(self, key):
        val = super().__getitem__(key)
        super().move_to_end(key)

        return val

class CaseInsensitiveDict(dict):
    def __setitem__(self, key, value):
        super().__setitem__(key.upper(), value)

    def __getitem__(self, key):
        return super().__getitem__(key.upper())

    def __in__(self, key):
        return super().__in__(key.upper())

    def __contains__(self, key):
        return super().__contains__(key.upper())

    def get(self, key, default=None):
        return super().get(key.upper(), default)

class OrderedPropertyMap(dict):
    # https://www.python.org/dev/peps/pep-3115/
    def __init__(self):
        self.member_names = []

    def __setitem__(self, key, value):
        # if the key is not already defined, add to the
        # list of keys.
        if key not in self:
            self.member_names.append(key)

        # Call superclass
        dict.__setitem__(self, key, value)

class OrderedClass(type):

    # The prepare function
    @classmethod
    def __prepare__(metacls, name, bases): # No keywords in this case
        return OrderedPropertyMap()

    # The metaclass invocation
    def __new__(cls, name, bases, classdict):
        # Note that we replace the classdict with a regular
        # dict before passing it to the superclass, so that we
        # don't continue to record member names after the class
        # has been created.
        result = type.__new__(cls, name, bases, dict(classdict))
        result.member_names = classdict.member_names
        return result

class RollingCounter(object):
    """

    """
    def __init__(self, interval_ms, bins=4):
        super(RollingCounter, self).__init__()

        self.interval_ms = interval_ms // bins
        self._current_index = 0
        self._bins = bins
        self._counts = []
        self._count = 0

    def increment(self):

        ms = int(time.time()*1000)

        # this counts events within a given window
        # if the interval is 1000ms and there are 4 bins
        # then it counts the number of events within a
        # 250 ms window.
        # However the windows may not be consecutive in time.
        # which may do better at capturing bursty activity

        index = ms // self.interval_ms
        if index != self._current_index:
            # if more than one period elapsed since the last event
            # reset the counter completely
            if index - self._current_index > self._bins:
                self._counts = [0]
            else:
                self._counts.append(0)
                while len(self._counts) > self._bins:
                    self._counts.pop(0)
                self._current_index = index

        self._counts[-1] += 1
        self._count =sum(self._counts)

        return self._count

    def value(self):
        return self._count

class RateLimiter(object):
    def __init__(self, limit, interval_ms, capacity):
        super(RateLimiter, self).__init__()

        self.counter = CacheDict(capacity=capacity)
        self.blocked = CacheDict(capacity=capacity)
        self.limit = limit
        self.interval_ms = interval_ms

    def insert(self, k):

        if k not in self.counter:
            self.counter[k] = RollingCounter(self.interval_ms, bins=4)

        count = self.counter[k].increment()

        return count > self.limit

class Route(object):

    def __init__(self, name, method, pattern, callback, websocket=False):
        super(Route, self).__init__()
        self.name = name
        self.method = method
        self.pattern = pattern
        self.callback = callback
        self.websocket = websocket

        self.ratelimit = None
        self.options = {}


    def __repr__(self):
        return "<Route %s>" % self.name

class Resource(object, metaclass=OrderedClass):
    """ A Resource is a collection of related routes that can be
    registered with a Router.

    Subclass this class and define methods with the annotations: get, put, post, delete
    to automatically register routes. Each method takes a single argument, the request.
    Then register the resource with a Router. When the server receives an HTTP
    request the url path will be matched with a route and the corresponding function
    will be called.


    When using HTTP verb annotations, the path may include named wildcards using
    a colon prefix. The special characters ?, +, * allow for changing how the
    wildcard matching is performed.

    ```
    /abc        - match exactly. e.g. '/abc'
    /:abc       - match a path component exactly once. e.g. '/one' or '/two'
    /:abc?      - match a path component 0 or 1 times. e.g. '/' or '/one'
    /:abc+      - match a path component 1 or more times. e.g. '/one' or '/one/two'
    /:abc*      - match a path component 0 or more times. e.g. '/' or '/one' or '/one/two'
    ```

    When the router is attempting to match a path to a registered route,
    the first successful match is used.

    Example:

    ```
    class MyResource(Resource):

        @get("/user/:username")
        def get_user(self, request):
            pass

        @post("/user/:username"):
        def create_user(self, request):
            pass

        @delete("/user/:username"):
        def delete_user(self, request):
            pass


    ```



    """
    def __init__(self):
        super(Resource, self).__init__()

        self._routes = []

        for name in self.member_names:
            if name.startswith("_"):
                continue
            attr = getattr(self, name)
            if hasattr(attr, '_route'):
                func = attr
                path = func._route
                methods = func._methods
                isws = getattr(func, '_websocket', False)

                cls_name = self.__class__.__name__.replace(
                    "Resource", "").lower()
                name = cls_name + "." + func.__name__
                endpt = Route(name, methods[0], path, attr, websocket=isws)
                endpt.ratelimit = getattr(func, '_ratelimit', (1, "second"))
                endpt.options = getattr(func, '_options', {})
                self._routes.append(endpt)

    def routes(self):
        """

        :returns: a list-of-3-tuples: [(http_method, url_pattern, callback)]
        """
        return self._routes

def upgrade_websocket(endpt, request):

    headers = {
        "Upgrade": "websocket",
        "Connection": "Upgrade",
    }

    if b'Upgrade' not in request.headers:
        return JsonResponse({'error': 'upgrade header missing'}, 400)

    if b'Sec-WebSocket-Key' not in request.headers:
        return JsonResponse({'error': 'websocket key missing'}, 400)

    upgrade = request.headers.get(b'Upgrade')
    if upgrade:
        if upgrade[0] != b"websocket":
            return JsonResponse({'error': 'invalid upgrade header'}, 400)

    key = request.headers.get(b'Sec-WebSocket-Key')
    if key:
        guid = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        secret = key[0] + guid
        digest = hashlib.sha1(secret).digest()
        value = base64.b64encode(digest).decode()
        headers['Sec-WebSocket-Accept'] = value

    # TODO: handle protocol correctly
    ws_protocol = request.headers.get(b'Sec-WebSocket-Protocol')
    if ws_protocol:
        protocol = ws_protocol[0].split(b",")[0].decode()
        headers['Sec-WebSocket-Protocol'] = protocol

    ws_version = request.headers.get(b'Sec-WebSocket-Version')
    if ws_protocol and ws_version[0] != b'13':
        logging.warning("unexpected web socket version %s", ws_version)

    # TODO: SEC-WEBSOCKET-EXTENSIONS : support for deflate

    # other headers:
    # b'SEC-FETCH-DEST' [b'websocket']
    # b'SEC-FETCH-MODE' [b'websocket']
    # b'SEC-FETCH-SITE' [b'same-origin']
    print("upgrade", headers)

    return WebsocketUpgradeResponse(endpt, headers)

def request_response(endpt, request):

    response = None

    # check the put/post options and validate the incoming request.
    # ensure that the input is not too large
    max_content_length = endpt.options.get('max_content_length', None)
    if max_content_length is not None:
        request_content_length = 0

        if b'Content-Length' not in request.headers:
            response = JsonResponse({'error': 'Content-Length not specified'}, 411)
        else:
            try:
                request_content_length = int(request.headers[b'Content-Length'][0])
                if request_content_length < 0:
                    request_content_length = 0
            except ValueError as e:
                request_content_length = 0
            except Exception as e:
                request_content_length = 0

        if request_content_length > max_content_length:
            response = JsonResponse({'error': 'Payload too large'}, 413)

    # if the validations passed, run the user callback
    if response is None:
        try:
            response = endpt.callback(request)
        except Exception as e:
            mplogger.exception("user callback failed")
            response = None

    if response is None:
        response = JsonResponse({'error':
            'route failed to return a response'}, 500)

    if not isinstance(response, Response):
        raise TypeError(type(response))

    return response

class Router(object):
    """


    """
    def __init__(self):
        super(Router, self).__init__()
        self.route_table = {
            "DELETE": [],
            "GET": [],
            "POST": [],
            "PUT": [],
        }
        self.routes = []

        # a rate limiter which limits requests per IP
        # to 100 requests per minute, for up to 1024 clients
        self.limiter = RateLimiter(5, 60*1000, 1024)

    def registerRoutes(self, routes):
        """ register routes with the router


        :param routes: either a Resource instance,
            or a list-of-3-tuples: [(http_method, url_pattern, callback)]
        """

        if isinstance(routes, Resource):
            routes = routes.routes()

        for route in routes:
            regex, tokens = self.patternToRegex(route.pattern)
            if route.method not in self.route_table:
                raise ValueError("Unsupported method: %s" % route.method)
            self.route_table[route.method].append((regex, tokens, route))
            self.routes.append(route)

    def getRoute(self, method, path):
        """ private method

        Get the route for a given method and path
        """
        if method not in self.route_table:
            mplogger.error("unsupported method: %s", method)
            return None

        for re_ptn, tokens, endpt in self.route_table[method]:
            m = re_ptn.match(path)
            if m:
                return endpt, {k: v for k, v in zip(tokens, m.groups())}
        return None

    def patternToTemplate(self, pattern):
        """ private method
        convert a url pattern into a regular expression


        ```
        /abc        - match exactly. e.g. '/abc'
        /:abc       - match a path compenent exactly once. e.g. '/one' or '/two'
        /:abc?      - match a path component 0 or 1 times. e.g. '/' or '/one'
        /:abc+      - match a path component 1 or more times. e.g. '/one' or '/one/two'
        /:abc*      - match a path component 0 or more times. e.g. '/' or '/one' or '/one/two'
        ```

        """

        parts = [part for part in pattern.split("/") if part]
        tokens = []
        template = ""
        required = 0
        for part in parts:
            if part.startswith(':'):
                if part[-1] in '?*':
                    tokens.append(part[1: -1])
                elif part[-1] in '+':
                    tokens.append(part[1: -1])
                    required += 1
                else:
                    tokens.append(part[1:])
                    required += 1
                template += "/{%s}" % tokens[-1]
            else:
                template += '/' + part

        return (template, tokens, required)

    def patternToRegex(self, pattern):
        """ private method
        convert a url pattern into a regular expression


        ```
        /abc        - match exactly. e.g. '/abc'
        /:abc       - match a path compenent exactly once. e.g. '/one' or '/two'
        /:abc?      - match a path component 0 or 1 times. e.g. '/' or '/one'
        /:abc+      - match a path component 1 or more times. e.g. '/one' or '/one/two'
        /:abc*      - match a path component 0 or more times. e.g. '/' or '/one' or '/one/two'
        ```

        """

        parts = [part for part in pattern.split("/") if part]
        tokens = []
        re_str = "^"
        final = False
        for part in parts:
            if part.startswith(':'):
                c = part[-1]
                if c == '?':
                    if final:
                        raise ValueError(pattern)
                    tokens.append(part[1: -1])
                    re_str += "(?:\\/([^\\/]*)|\\/)?"
                    final = True
                elif c == '*':
                    if final:
                        raise ValueError(pattern)
                    # match the first forward slash but do not include
                    # match everything after a slash
                    # and store in a capture group
                    tokens.append(part[1: -1])
                    re_str += "(?:\\/(.*)|\\/)?"
                    final = True
                elif c == '+':
                    if final:
                        raise ValueError(pattern)
                    tokens.append(part[1: -1])
                    re_str += "\\/?(.+)"
                    final = True
                else:
                    tokens.append(part[1:])
                    re_str += "\\/([^\\/]+)"
            else:
                re_str += '\\/' + part

        if re_str != "^\\/":
            re_str += "\\/?"

        re_str += '$'
        return (re.compile(re_str), tokens)

    def dispatch(self, request):

        response = None
        if self.limiter.insert(request.client_address[0]):
            response = JsonResponse({'error': 'Too Many Requests'}, 429)
        else:

            result = self.getRoute(request.method, request.path)

            if not result:
                response = JsonResponse({'error': 'path not found'}, 404)
            else:

                endpt, matches = result
                request.matches = matches
                if endpt.websocket:
                    response = upgrade_websocket(endpt, request)
                else:
                    response = request_response(endpt, request)

        return response

class TestClient(object):
    def __init__(self, router):
        super(TestClient, self).__init__()

        self.router = router

        for route in router.routes:
            name = route.name.replace(".", "_")
            fn = lambda *args, _route=route, **kwargs: self._call(_route, args, **kwargs)

            setattr(self, name, fn)

    def _coerce_dict(self, datadict):

        bytesdict = {}
        if datadict:
            for name, values in datadict.items():

                if isinstance(name, str):
                    name = name.encode("utf-8")
                if not isinstance(name, bytes):
                    raise TypeError("expected str in header parameter name")

                if values is None:
                    values = []

                if isinstance(values, (int, str)):
                    values = [values]

                bytesdict[name] = []
                for value in values:
                    if value is not None:
                        if isinstance(value, int):
                            value = str(value)
                        if isinstance(value, str):
                            value = value.encode("utf-8")

                        if not isinstance(value, bytes):
                            raise TypeError("expected str in header parameter value")
                    bytesdict[name].append(value)

        return bytesdict

    def _build_request(self, route, args, params=None, fragment=None, headers=None, body=None):
        template, tokens, required = self.router.patternToTemplate(route.pattern)

        if len(args) < required:
            raise ValueError("expected %d positional arguments, found %d" % (
                len(tokens), len(args)))

        kwargs = {k:"" for k in tokens}
        kwargs.update({k:v for k,v in zip(tokens, args)})

        path = template.format(**kwargs)
        # append wild card args
        if len(args) > len(tokens):
            path += "".join(["/%s" % s for s in args[len(tokens):]])

        headers = self._coerce_dict(headers)

        req = Request(('127.0.0.1', 54321), route.method, path, params, fragment, headers, body)
        req.matches = {tok:arg for tok, arg in zip(tokens, args)}

        return req

    def _call(self, route, args, params=None, fragment=None, headers=None, body=None):

        req = self._build_request(route, args, params, fragment, headers, body)

        try:
            result = router.getRoute(request.method, request.path)

            if not result:
                response = JsonResponse({'error': 'path not found'}, 404)

            else:
                endpt, matches = result
                request.matches = matches
                if endpt.websocket:
                    response = JsonResponse({'error': 'websocket not supported in testing'}, 500)
                else:
                    response = request_response(endpt, req)
        except Exception as e:
            e.request = req
            raise

        response._payload = response.payload
        response.payload = response._get_payload(req)

        # make the original request available to tests
        response.request = req

        return response

def parse_url(path):

    parsed = urlparse(path)

    query = defaultdict(list)
    parts = parsed.query.split(b"&")
    for part in parts:
        if part:
            if b'=' in part:
                name, value = part.split(b"=", 1)
                name = unquote(name.decode("utf-8"))
                value = unquote(value.decode("utf-8"))
            else:
                name = unquote(part.decode("utf-8"))
                value = None
            query[name].append(value)

    return parsed.path, dict(query), parsed.fragment

class Request(object):
    """ A Request contains the information received from a client


    :attr client_address: the clients IP and port
    :attr method: a string containing the HTTP method
    :attr path: a string containing the resource path
    :attr params: dictionary str=>List[str] of decoded query parameters
    :attr fragment: a string the request fragment
    :attr headers: a dictionary bytes=>List[bytes] of HTTP headers
    :attr stream: a File-like object containig the request content
    :attr matches: dictionary of matched path components. See the Resource documentation for more information
    """

    def __init__(self, addr: Tuple[str, int], method: str, path: str, params: Dict[str, str], fragment: str, headers: Dict[bytes, bytes], stream: IO[bytes]):
        """

        :param addr: A 2-tuple (host: str, port: int)
        :param method:
        :param path: the absolute path + query + fragment
        :param stream: a file like object for reading the request body
        :param headers:

        """
        super(Request, self).__init__()

        self.client_address = addr
        self.method = method
        self.path = path
        self.params = params
        self.fragment = fragment
        self.headers = headers
        self.stream = stream
        self.matches = {}

    def json(self):
        """ deserialize the request content as a JSON
        """
        # self.requestHeaders['Content-Type']
        return json.loads(self.stream.read().decode("utf-8"))

    def message(self):
        """ deserialize the request content as a Serializable instance
        """
        return Serializable.loadb(self.stream.read())

    def __repr__(self):

        return "<Request %s %s>" % (self.method, self.path)

class RequestFactory(http.Request):
    BUFFER_TX_SIZE = 2048

    def process(self):
        """ private method

        decode the request, call the user callback, encode the response
        """
        t0 = time.perf_counter()
        router = self.channel.requestRouter

        addr = self.getClientAddress()

        headers = CaseInsensitiveDict()
        for key, value in self.requestHeaders.getAllRawHeaders():
            headers[key] = value

        hostport = (addr.host, addr.port)

        path, query, fragment = parse_url(self.uri)

        req = Request(
                hostport,
                self.method.decode(),
                path.decode("utf-8"),
                query,
                fragment,
                headers,
                self.content)

        response = router.dispatch(req)

        content_length = None

        # this may mutate the headers
        payload = response._get_payload(req)

        try:

            self.setResponseCode(response.status_code)
            self.sendResponseHeaders(response.headers)

            if hasattr(payload, "read"):
                content_length = 0
                buf = payload.read(RequestFactory.BUFFER_TX_SIZE)
                while buf:
                    self.write(buf)
                    content_length += len(buf)
                    buf = payload.read(RequestFactory.BUFFER_TX_SIZE)
            else:
                if content_length is None:
                    # content length has not been set
                    content_length = str(len(payload))
                    self.setHeader("Content-Length", content_length)
                self.write(payload)

        except ConnectionAbortedError as e:
            sys.stderr.write("%s aborted\n" % url.path)
        except BrokenPipeError as e:
            sys.stderr.write("%s aborted\n" % url.path)
        except Exception as e: # TODO: remove this error handler after testing ws
            logging.error("handled error", e)
        finally:
            if hasattr(payload, "close"):
                payload.close()

            elapsed = int((time.perf_counter() - t0) * 1000)
            mplogger.info("%016X %s:%s %s %3s t=%6d %-8s %s [%s] %s" % (
                threading.get_ident(),
                self.getClientAddress().host,
                self.getClientAddress().port,
                self.clientproto.decode(),
                response.status_code,
                elapsed,
                req.method,
                req.path,
                content_length,
                "z" if response.compress else ""))

            if not response.upgrade:
                self.finish()
            else:
                print("ws set raw mode")
                self.channel.setRawMode()
                buffer = WebSocketTemporaryRingBuffer(self)
                handler = WebSocketTemporaryHandler(hostport, query, headers, buffer, response.endpt)
                self.channel.websocket_callback = handler
                try:
                    handler.open()
                except Exception as e:
                    mplogger.exception("failed to install websocket")



    def sendResponseHeaders(self, headers):
        for k, v in headers.items():
            if k.lower() == "content-length":
                content_length = v
            if not isinstance(v, str):
                mplogger.warning("header value is not a string. %s=%s", k, v)
                v = str(v)
            self.setHeader(k, v)

class HTTPFactory(http.HTTPFactory):

    def __init__(self, *args, router=None, **kwargs):
        super().__init__(*args, **kwargs)

        class Channel(http.HTTPChannel):
            requestFactory = RequestFactory
            requestRouter = router
            websocket_callback = None

            def dataReceived(self, data):
                if self.websocket_callback:
                    self.websocket_callback(data)
                else:
                    super().dataReceived(data)
                return

            def requestDone(self, request):
                print("on requestDone")
                self.websocket_callback = None
                super().requestDone(request)

            def connectionLost(self, reason):
                uid = -1
                closed = None
                if self.websocket_callback:
                    uid = self.websocket_callback.uid
                    closed = self.websocket_callback.closed
                print("on connectionLost", uid, closed, reason)
                self.websocket_callback = None
                super().connectionLost(reason)

            def loseConnection(self):
                print("on loseConnection")
                super().loseConnection()

        self._channel = Channel

    def buildProtocol(self, addr):
        return self._channel()

class HTTPServer(object):
    def __init__(self, addr, privkey=None, cert=None):
        super(HTTPServer, self).__init__()

        self.addr = addr
        self.router = Router()

        self.privatekey_path = privkey
        self.certificate_path = cert

    def run(self):

        cert = None
        if self.privatekey_path is not None:
            keyAndCert = ""
            with open(self.privatekey_path) as key:
                keyAndCert += key.read()
            with open(self.certificate_path) as cert:
                keyAndCert += cert.read()

            cert = ssl.PrivateCertificate.loadPEM(keyAndCert)

        if cert:
            # https://stackoverflow.com/questions/57812501/python-twisted-is-it-possible-to-reload-certificates-on-the-fly
            opts = cert.options()
            # TODO: setting opts._context = None should force a reload of the cert file
            port = reactor.listenSSL(self.addr[1],
                HTTPFactory(router=self.router),
                opts,
                interface=self.addr[0])
            mplogger.info("tls server listening on %s:%d" % (self.addr))
        else:
            reactor.listenTCP(self.addr[1],
                HTTPFactory(router=self.router),
                interface=self.addr[0])
            mplogger.info("tcp server listening on %s:%d" % (self.addr))

        for route in self.router.routes:
            print("%-7s %s" % (route.method, route.pattern))

        reactor.run()

    def registerRoutes(self, routes):
        self.router.registerRoutes(routes)

    def routes(self):
        return self.router.routes
