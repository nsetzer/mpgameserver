#! cd .. && python -m demo.http
import os
import sys
import json
import time
import gzip
import io
import threading
from threading import Thread

from collections import defaultdict, OrderedDict

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from twisted.web import http

from urllib.parse import urlparse, unquote
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

def put(path, max_content_length=5*1024*1024):
    """decorator which registers a class method as a PUT handler"""
    def decorator(f):
        f._options = {'max_content_length': max_content_length}
        f._endpoint = path
        f._methods = ['PUT']
        return f
    return decorator

def post(path, max_content_length=5*1024*1024):
    """decorator which registers a class method as a POST handler"""
    def decorator(f):
        f._options = {'max_content_length': max_content_length}
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

class Endpoint(object):

    def __init__(self, method, pattern, callback):
        super(Endpoint, self).__init__()
        self.method = method
        self.pattern = pattern
        self.callback = callback

        self.ratelimit = None
        self.options = {}

class Resource(object, metaclass=OrderedClass):
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
    /:abc       - match a path component exactly once. e.g. '/one' or '/two'
    /:abc?      - match a path component 0 or 1 times. e.g. '/' or '/one'
    /:abc+      - match a path component 1 or more times. e.g. '/one' or '/one/two'
    /:abc*      - match a path component 0 or more times. e.g. '/' or '/one' or '/one/two'
    ```

    When the router is attempting to match a path to a registered endpoint,
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

        for name in self.member_names:
            if name.startswith("_"):
                continue
            attr = getattr(self, name)
            if hasattr(attr, '_endpoint'):
                func = attr
                # fname = self.__class__.__name__ + "." + func.__name__
                path = func._endpoint
                methods = func._methods

                endpt = Endpoint(methods[0], path, attr)
                endpt.ratelimit = getattr(func, '_ratelimit', (1, "second"))
                endpt.options = getattr(func, '_options', {})
                self._endpoints.append(endpt)

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

        # a rate limiter which limits requests per IP
        # to 100 requests per minute, for up to 1024 clients
        self.limiter = RateLimiter(5, 60*1000, 1024)

    def registerEndpoints(self, endpoints):
        """ register endpoints with the router


        :param endpoints: either a Resource instance,
            or a list-of-3-tuples: [(http_method, url_pattern, callback)]
        """

        if isinstance(endpoints, Resource):
            endpoints = endpoints.endpoints()

        for endpt in endpoints:
            regex, tokens = self.patternToRegex(endpt.pattern)
            self.route_table[endpt.method].append((regex, tokens, endpt))
            self.endpoints.append(endpt)

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
    """ A Request contains the information received from a client


    :attr client_address: the clients IP and port
    :attr method: a bytes string containing the HTTP method
    :attr url: the raw request uri
    :attr location: the path component of the uri
    :attr stream: a File-like object containig the request content
    :attr headers: a dictionary bytes=>List[bytes] of HTTP headers
    :attr matches: dictionary of matched path components. See the Resource documentation for more information
    :attr query: dictionary str=>List[str] of decoded query parameters
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

        req = Request(
                hostport,
                self.method.decode("utf-8"),
                self.uri.decode("utf-8"),
                self.content,
                headers)

        response = None
        if router.limiter.insert(addr.host):

            response = JsonResponse({'error': 'Too Many Requests'}, 429)

        else:

            result = router.getRoute(req.method, req.location)

            if result:
                endpt, matches = result

                req.matches = matches

                # check the put/post options and validate the incoming request.
                # ensure that the input is not too large
                max_content_length = endpt.options.get('max_content_length', None)
                if max_content_length is not None:
                    request_content_length = 0

                    if b'Content-Length' not in headers:
                        response = JsonResponse({'error': 'Content-Length not specified'}, 411)
                    else:
                        try:
                            request_content_length = int(headers[b'Content-Length'][0])
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
                        response = endpt.callback(req)
                    except Exception as e:
                        mplogger.exception("user callback failed")
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
                    mplogger.warning("header value is not a string. %s=%s", k, v)
                    v = str(v)
                self.setHeader(k, v)

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

        for endpt in self.router.endpoints:
            print("%-7s %s" % (endpt.method, endpt.pattern))

        reactor.run()

    def registerEndpoints(self, endpoints):
        self.router.registerEndpoints(endpoints)

    def endpoints(self):
        return self.router.endpoints
