#! cd .. && python -m demo.http
import sys
import json
import time
import gzip
import io
import logging
import threading

from collections import defaultdict

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from twisted.web import http

from urllib.parse import urlparse, unquote
import re

from . import crypto
from .serializable import Serializable

from threading import Thread

# https://twistedmatrix.com/documents/21.2.0/api/twisted.web.http.Request.html

class Response(object):
    def __init__(self, payload=None, status_code=200, headers=None, compress=False):
        super(Response, self).__init__()
        self.status_code = status_code
        self.headers = {} if headers is None else headers
        self.payload = b"" if payload is None else payload
        self.compress = compress

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

def get(path):
    """decorator which registers a class method as a GET handler"""
    def decorator(f):
        f._endpoint = path
        f._methods = ['GET']
        return f
    return decorator

def put(path):
    """decorator which registers a class method as a PUT handler"""
    def decorator(f):
        f._endpoint = path
        f._methods = ['PUT']
        return f
    return decorator

def post(path):
    """decorator which registers a class method as a POST handler"""
    def decorator(f):
        f._endpoint = path
        f._methods = ['POST']
        return f
    return decorator

def delete(path):
    """decorator which registers a class method as a DELETE handler"""
    def decorator(f):
        f._endpoint = path
        f._methods = ['DELETE']
        return f
    return decorator

class Resource(object):
    """ A Resource is a collection of related endpoints that can be
    registered with a Router.

    Subclass this class and define methods with the annotations: get, put, post, delete
    to automatically register endpoints. Each method takes a single argument, the request.
    Then register the resource with a Router. When the server receives an HTTP
    request the url path will be matched with an endpoint and the corresponding function
    will be called.


    When using HTTP verb annotations, the path may include named wildcards using
    a colon prefix. The special characters ?, +, * allow for changing how the
    wildcard matching is performed.

    ```
    /abc        - match exactly. e.g. '/abc'
    /:abc       - match a path compenent exactly once. e.g. '/one' or '/two'
    /:abc?      - match a path component 0 or 1 times. e.g. '/' or '/one'
    /:abc+      - match a path component 1 or more times. e.g. '/one' or '/one/two'
    /:abc*      - match a path component 0 or more times. e.g. '/' or '/one' or '/one/two'
    ```

    When the router is attempting to match a path to a registerd endpoint,
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

        self._endpoints = []

        for name in dir(self):
            attr = getattr(self, name)
            if hasattr(attr, '_endpoint'):
                func = attr
                # fname = self.__class__.__name__ + "." + func.__name__
                path = func._endpoint
                methods = func._methods

                self._endpoints.append((methods[0], path, attr))

    def endpoints(self):
        """

        :returns: a list-of-3-tuples: [(http_method, url_pattern, callback)]
        """
        return self._endpoints

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
        self.endpoints = []

    def registerEndpoints(self, endpoints):
        """ register endpoints with the router


        :param endpoints: either a Resource instance,
            or a list-of-3-tuples: [(http_method, url_pattern, callback)]
        """

        if isinstance(endpoints, Resource):
            endpoints = endpoints.endpoints()

        for method, pattern, callback in endpoints:
            regex, tokens = self.patternToRegex(pattern)
            self.route_table[method].append((regex, tokens, callback))
            self.endpoints.append((method, pattern))

    def getRoute(self, method, path):
        """ private method

        Get the route for a given method and path
        """
        if method not in self.route_table:
            logging.error("unsupported method: %s", method)
            return None

        for re_ptn, tokens, callback in self.route_table[method]:
            m = re_ptn.match(path)
            if m:
                return callback, {k: v for k, v in zip(tokens, m.groups())}
        return None

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
        for part in parts:
            if (part.startswith(':')):
                c = part[-1]
                if c == '?':
                    tokens.append(part[1: -1])
                    re_str += "(?:\\/([^\\/]*)|\\/)?"
                elif c == '*':
                    # match the first forward slash but do not include
                    # match everything after a slash
                    # and store in a capture group
                    tokens.append(part[1: -1])
                    re_str += "(?:\\/(.*)|\\/)?"
                elif c == '+':
                    tokens.append(part[1: -1])
                    re_str += "\\/?(.+)"
                else:
                    tokens.append(part[1:])
                    re_str += "\\/([^\\/]+)"
            else:
                re_str += '\\/' + part

        if re_str != "^\\/":
            re_str += "\\/?"

        re_str += '$'
        return (re.compile(re_str), tokens)

class Request(object):
    """ A Request contains information received from a client


    :attr client_address: the clients IP and port
    :attr headers: a dictionary of HTTP headers
    :attr location: the path component of the uri
    :attr matches: dictionary of matched path components. See the Resource documentation for mor information
    :attr method: a bytes string containing the HTTP method
    :attr query: dictionary of decoded query parameters
    :attr stream: a File-like object containig the request content
    :attr uri: the raw request uri
    """

    def __init__(self, addr, method, uri, stream, headers):
        super(Request, self).__init__()

        parsed = urlparse(unquote(uri))

        self.client_address = addr
        self.method = method
        self.url = uri
        self.location = parsed.path
        self.stream = stream
        self.headers = headers
        self.matches = {}

        self.query = defaultdict(list)
        parts = parsed.query.split("&")
        for part in parts:
            if '=' in part:
                key, value = part.split("=", 1)
                self.query[key].append(value)
            else:
                self.query[part].append(None)

    def json(self):
        """ deserialize the request content as a JSON
        """
        # self.requestHeaders['Content-Type']
        return json.loads(self.stream.read().decode("utf-8"))

    def message(self):
        """ deserialize the request content as a Serializable instance
        """
        return Serializable.loadb(self.stream.read())

class RequestFactory(http.Request):

    def process(self):
        """ private method

        decode the request, call the user callback, encode the response
        """
        t0 = time.perf_counter()
        router = self.channel.requestRouter

        addr = self.getClientAddress()

        req = Request(
            (addr.host, addr.port),
            self.method.decode("utf-8"),
            self.uri.decode("utf-8"),
            self.content,
            self.requestHeaders)

        result = router.getRoute(req.method, req.location)

        if result:
            callback, matches = result

            req.matches = matches

            # TODO: self.content is a file like object
            #       for json: replace with json?
            #       for serializeable replace?

            try:
                response = callback(req)
            except Exception as e:
                logging.exception("user callback failed")
                response = None

            if response is None:
                response = JsonResponse({'error':
                    'endpoint failed to return a response'}, 500)

            if not isinstance(response, Response):
                raise TypeError(type(response))
        else:
            response = JsonResponse({'error': 'path not found'}, 404)

        # this may mutate the headers
        payload = response._get_payload(req)

        content_length = None

        try:

            self.setResponseCode(response.status_code)

            for k, v in response.headers.items():
                if k.lower() == "content-length":
                    content_length = v
                if not isinstance(v, str):
                    logging.warning("header value is not a string. %s=%s", k, v)
                    v = str(v)
                self.setHeader(k, v)

            if hasattr(payload, "read"):
                buf = payload.read(RequestHandler.BUFFER_TX_SIZE)
                while buf:
                    self.write(buf)
                    buf = payload.read(RequestHandler.BUFFER_TX_SIZE)
            else:
                if content_length is None:
                    content_length = str(len(payload))
                    self.setHeader("Content-Length", content_length)
                self.write(payload)

        except ConnectionAbortedError as e:
            sys.stderr.write("%s aborted\n" % url.path)
        except BrokenPipeError as e:
            sys.stderr.write("%s aborted\n" % url.path)
        finally:
            if hasattr(payload, "close"):
                payload.close()

            elapsed = int((time.perf_counter() - t0) * 1000)
            logging.info("%016X %s:%s %s %3s t=%6d %-8s %s [%s] %s" % (
                threading.get_ident(),
                self.getClientAddress().host,
                self.getClientAddress().port,
                self.clientproto.decode(),
                response.status_code,
                elapsed,
                req.method,
                req.location,
                content_length,
                "z" if response.compress else ""))

            self.finish()

class HTTPFactory(http.HTTPFactory):

    def __init__(self, *args, router=None, **kwargs):
        super().__init__(*args, **kwargs)

        class Channel(http.HTTPChannel):
            requestFactory = RequestFactory
            requestRouter = router

        self._channel = Channel

    def buildProtocol(self, addr):
        return self._channel()

class HTTPServer(object):
    """docstring for TwistedTCPServer"""
    def __init__(self, addr):
        super(HTTPServer, self).__init__()

        self.addr = addr
        self.router = Router()

    def run(self):
        reactor.listenTCP(self.addr[1],
            HTTPFactory(router=self.router),
            interface=self.addr[0])
        reactor.run()

    def registerEndpoints(self, endpoints):
        self.router.registerEndpoints(endpoints)
