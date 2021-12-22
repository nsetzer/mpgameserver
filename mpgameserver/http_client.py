#! cd .. && python -m mpgameserver.http_client

import time
import asyncio
import threading
import urllib.request
import ssl
# import requests
import json
import sys

from .serializable import Serializable, serialize_registry
from .http_server import Response, ErrorResponse, JsonResponse, SerializableResponse

from urllib.parse import quote
from urllib.error import URLError, HTTPError
from concurrent.futures import ThreadPoolExecutor
from http.client import RemoteDisconnected
from .logger import mplogger

def asyncio_thread(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def make_request(method, url, payload, query, headers):
    """

    :param  method:  one of GET, POST, PUT, DELETE
    :param  url:     the url including the protocol, host, port and path
    :param payload:  None, a file like object or a bytes array containing
                     data to upload
    :param  query:   dictionary of query parameters to append to the url
                     this function will safely encode the parameters
    :param  headers: dictionary of request headers to send

    """

    if query:
        parts = []
        for key, value in query.items():
            if isinstance(value, str):
                parts.append(quote(key) + "=" + quote(value))
            elif isinstance(value, bytes):
                raise TypeError("unexpected bytes in query")
            else:
                for v in value:
                    parts.append(quote(key) + "=" + quote(v))
        url += "?" + "&".join(parts)

    if headers is None:
        headers = {}

    #args = ["curl", "-k"]
    #args.extend([("-H%s=\"%s\"" % (k, v)) for k, v in headers.items()])
    #args.append("\"%s\"" % url)
    #print(" ".join(args))

    # if the payload is a file like object, read the content inside
    # this thread and prepare for sending.
    if hasattr(payload, "read"):
        tmp = payload.read()
        if hasattr(payload, "close"):
            payload.close()
        payload = tmp

    # if isinstance(payload, ...):
    #     payload = payload.dumpb()
    #      headers['Content-Type'] = "application/json"

    if isinstance(payload, dict):
        payload = json.dumps(payload).encode("utf-8")

    if isinstance(payload, Serializable):
        payload = payload.dumpb()
        headers['Content-Type'] = "application/x-serializable"

    if payload is not None and isinstance(payload, bytes):
        if 'Content-Length' not in headers:
            headers['Content-Length'] = len(payload)

    req = urllib.request.Request(url, data=payload, headers=headers, method=method)

    # TODO: the creation of this context needs to be exposed at a higher level
    # users of mpgameserver will need to decide on the parameters, if any
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        response = urllib.request.urlopen(req, context=ctx)
    except RemoteDisconnected as e:
        return ErrorResponse(str(e), 408, {})
    except HTTPError as e:
        # http_error.reason
        body = e.read()
        if e.headers.get('Content-Type', None) == "application/json":
            try:
                body = json.loads(body)
            except Exception:
                mplogger.exception("unable to parse json response")
                pass
        return ErrorResponse(body, e.code, e.headers)
    except URLError as e:
        return ErrorResponse(str(e), 408, {})

    data = response.read()

    content_type = None
    if 'Content-Type' in response.headers:
        content_type = response.headers['Content-Type']

    T = Response
    if content_type == "application/json":
        T = JsonResponse
        data = json.loads(data.decode("utf-8"))

    elif content_type == "application/x-serializable":
        T = SerializableResponse
        data = Serializable.loadb(data)

    return T(data, status_code=response.status, headers=response.headers)

def execute_async_function(handle, fn, args, kwargs):

    try:
        handle.response = fn(*args, **kwargs)
    finally:
        handle.ready = True

handle_id = 1
class RequestHandle(object):
    """docstring for RequestHandle"""
    def __init__(self):
        super(RequestHandle, self).__init__()
        global handle_id

        self.hid = handle_id
        handle_id += 1
        self.async_handle = None
        self.callback = None
        self.response = None
        self.ready = False

    def cancel(self):
        return self.async_handle.cancel()

    def cancelled(self):
        return self.async_handle.cancelled()

class AsyncHTTPClientImpl(object):
    def __init__(self, loop=None):
        super(AsyncHTTPClientImpl, self).__init__()

        if loop:
            self.loop = loop
        else:
            self.loop = asyncio.new_event_loop()
            self.executor = ThreadPoolExecutor(max_workers = 1)
            self.loop.set_default_executor(self.executor)

        self.handles = []

    def start(self):
        if self.loop is None:
            raise RuntimeError("start after stop not supported")

        self.thread = threading.Thread(target=asyncio_thread, args=(self.loop,))
        self.thread.start()

    def stop(self):

        if self.thread:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join()
            self.loop = None
            self.thread = None

    def call_soon_threadsafe(self, callback, *args):

        self.loop.call_soon_threadsafe(callback, *args)

    def get(self, url, query=None, headers=None, callback=None):
        handle = RequestHandle()
        handle.callback = callback
        async_handle = self.loop.call_soon_threadsafe(execute_async_function,
            handle, make_request, ("GET", url, None, query, headers), {})
        handle.async_handle = async_handle
        self.handles.append(handle)
        return handle

    def put(self, url, payload, query=None, headers=None, callback=None):
        handle = RequestHandle()
        handle.callback = callback
        async_handle = self.loop.call_soon_threadsafe(execute_async_function,
            handle, make_request, ("PUT", url, payload, query, headers), {})
        handle.async_handle = async_handle
        self.handles.append(handle)
        return handle

    def post(self, url, payload, query=None, headers=None, callback=None):
        handle = RequestHandle()
        handle.callback = callback
        async_handle = self.loop.call_soon_threadsafe(execute_async_function,
            handle, make_request, ("POST", url, payload, query, headers), {})
        handle.async_handle = async_handle
        self.handles.append(handle)
        return handle

    def delete(self, url, query=None, headers=None, callback=None):
        handle = RequestHandle()
        handle.callback = callback
        async_handle = self.loop.call_soon_threadsafe(execute_async_function,
            handle, make_request, ("DELETE", url, None, query, headers), {})
        handle.async_handle = async_handle
        self.handles.append(handle)
        return handle

    def pending(self):
        return len(self.handles)

    def getResponses(self):
        i = 0
        while i < len(self.handles):
            handle = self.handles[i]
            if handle.ready:
                if handle.callback:
                    handle.callback(handle.response)
                yield handle
                self.handles.pop(i)
            else:
                i += 1

class HTTPClient(object):
    """docstring for HTTPClient"""
    def __init__(self, addr, protocol="http"):
        super(HTTPClient, self).__init__()

        self.addr = addr
        self.protocol = protocol

        self.client = AsyncHTTPClientImpl()

        if addr[0] == "localhost":
            sys.stderr.write("HTTP Client warning: use 127.0.0.1 instead of localhost for best performance\n")

    def get(self, path, query=None, headers=None, callback=None):
        url = "%s://%s:%d%s" % (self.protocol, *self.addr, path)
        return self.client.get(url, query, headers, callback)

    def put(self, path, payload, query=None, headers=None, callback=None):
        url = "%s://%s:%d%s" % (self.protocol, *self.addr, path)
        return self.client.put(url, payload, query, headers, callback)

    def post(self, path, payload, query=None, headers=None, callback=None):
        url = "%s://%s:%d%s" % (self.protocol, *self.addr, path)
        return self.client.post(url, payload, query, headers, callback)

    def delete(self, path, query=None, headers=None, callback=None):
        url = "%s://%s:%d%s" % (self.protocol, *self.addr, path)
        return self.client.delete(url, payload, query, headers, callback)

    def pending(self):
        """ get the number of pending requests

        :returns: the count of pending requests
        """
        return self.client.pending()

    def getResponses(self):
        """ yield from the pending set of requests.
        return a handle containing information for each completed request.

        :returns: a generator of completed RequestHandle instances
        """
        return self.client.getResponses()

    def start(self):
        self.client.start()

    def stop(self):
        self.client.stop()

