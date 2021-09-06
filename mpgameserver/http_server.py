#! cd .. && python -m demo.http
import sys
import json
import time
import gzip
import io
import logging

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

class JsonResponse(Response):
    def __init__(self, obj, status_code=200, headers=None):
        super(JsonResponse, self).__init__(obj, status_code, headers)

    def _get_payload(self, request):

        payload = super()._get_payload(request)
        encoded = json.dumps(payload).encode('utf-8') + b"\n"
        self.headers['Content-Type'] = "application/json"
        self.headers['Content-Length'] = str(len(encoded))
        return encoded

class SerializableResponse(Response):
    def __init__(self, obj, status_code=200, headers=None):
        super(SerializableResponse, self).__init__(obj, status_code, headers)

    def _get_payload(self, request):

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
        return self._endpoints

class Router(object):
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
        for method, pattern, callback in endpoints:
            regex, tokens = self.patternToRegex(pattern)
            self.route_table[method].append((regex, tokens, callback))
            self.endpoints.append((method, pattern))

    def getRoute(self, method, path):
        if method not in self.route_table:
            logging.error("unsupported method: %s", method)
            return None

        for re_ptn, tokens, callback in self.route_table[method]:
            m = re_ptn.match(path)
            if m:
                return callback, {k: v for k, v in zip(tokens, m.groups())}
        return None

    def patternToRegex(self, pattern):
        # convert a url pattern into a regular expression
        #
        #   /abc        - match exactly
        #   /:abc       - match a path compenent exactly once
        #   /:abc?      - match a path component 0 or 1 times
        #   /:abc+      - match a path component 1 or more times
        #   /:abc*      - match a path component 0 or more times
        #
        # /:abc will match '/foo' with
        #  {'abc': foo}
        # /:bucket/:key* will match '/mybucket/dir1/dir2/fname' with
        #  {'bucket': 'mybucket', key: 'dir1/dir2/fname'}

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

class RequestFactory(http.Request):
    """

    member variables:

    location: the decoded path component of the url
    query: dictionary of decoded query parameters
    """

    def process(self):
        router = self.channel.requestRouter
        url = urlparse(unquote(self.uri.decode()))
        result = router.getRoute(self.method.decode(), url.path)

        if result:
            callback, matches = result

            self.query = defaultdict(list)
            parts = url.query.split("&")
            for part in parts:
                if '=' in part:
                    key, value = part.split("=", 1)
                    self.query[key].append(value)
                else:
                    self.query[part].append(None)

            self.location = url.path
            self.matches = matches

            # TODO: self.content is a file like object
            #       for json: replace with json?
            #       for serializeable replace?
            response = callback(self)

            if response is None:
                response = JsonResponse({'error':
                    'endpoint failed to return a response'}, 500)

            if not isinstance(response, Response):
                raise TypeError(type(response))
        else:
            response = JsonResponse({'error': 'path not found'}, 404)

        # this may mutate the headers
        print(response)
        payload = response._get_payload(self)

        try:

            self.setResponseCode(response.status_code)

            content_length_set = False
            for k, v in response.headers.items():
                if k.lower() == "content-length":
                    content_length_set = True
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
                if not content_length_set:
                    self.setHeader("Content-Length", str(len(payload)))
                self.write(payload)

        except ConnectionAbortedError as e:
            sys.stderr.write("%s aborted\n" % url.path)
        except BrokenPipeError as e:
            sys.stderr.write("%s aborted\n" % url.path)
        finally:
            if hasattr(payload, "close"):
                payload.close()

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
