[Home](../README.md)


# HTTP/TCP Protocol



* [Resource](#resource)
* [Request](#request)
* [Router](#router)
* [Response](#response)
* [ErrorResponse](#errorresponse)
* [JsonResponse](#jsonresponse)
* [SerializableResponse](#serializableresponse)
* [HTTPServer](#httpserver)
* [HTTPClient](#httpclient)
* [WebSocketOpCode](#websocketopcode)
* [path_join_safe](#path_join_safe)
* [get](#get)
* [put](#put)
* [post](#post)
* [delete](#delete)
* [websocket](#websocket)
* [header](#header)
* [param](#param)
---
## Resource
A Resource is a collection of related routes that can be registered with a Router.

Subclass this class and define methods with the annotations: get, put, post, delete to automatically register routes. Each method takes a single argument, the request. Then register the resource with a Router. When the server receives an HTTP request the url path will be matched with a route and the corresponding function will be called.

When using HTTP verb annotations, the path may include named wildcards using a colon prefix. The special characters ?, +, * allow for changing how the wildcard matching is performed.



    ```
    /abc        - match exactly. e.g. '/abc'
    /:abc       - match a path component exactly once. e.g. '/one' or '/two'
    /:abc?      - match a path component 0 or 1 times. e.g. '/' or '/one'
    /:abc+      - match a path component 1 or more times. e.g. '/one' or '/one/two'
    /:abc*      - match a path component 0 or more times. e.g. '/' or '/one' or '/one/two'
    ```

When the router is attempting to match a path to a registered route, the first successful match is used.

Websockets are handled as a special case to a normal request. The websocket connection lifecycle is handled by the framework. The registered function will be called when the socket is successfully opened and again when it is closed, with an empty payload. The function will also be called each time a user message is received. Check the opcode to determine if the payload is text or binary.

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

        @put("/file/:name"):
        def put_file(self, request):
            pass

        @websocket("/ws"):
        def websocket(self, request, opcode, payload):
            pass

    ```




#### Constructor:

* :small_blue_diamond: **`Resource`**`(self)` - 

#### Methods:

* :small_blue_diamond: **`routes`**`(self)` - 

  * **:leftwards_arrow_with_hook: `returns:`** a list-of-3-tuples: [(http_method, url_pattern, callback)]

  

---
## Request
A Request contains the information received from a client




#### Constructor:

* :small_blue_diamond: **`Request`**`(self, addr: Tuple[str, int], method: str, path: str, params: Dict[str, str], fragment: str, headers: Dict[bytes, bytes], stream: IO[bytes])` - 

  * **:arrow_forward: `addr:`** A 2-tuple (host: str, port: int)

  * **:arrow_forward: `method:`** 

  * **:arrow_forward: `path:`** the absolute path + query + fragment

  * **:arrow_forward: `params:`** 

  * **:arrow_forward: `fragment:`** 

  * **:arrow_forward: `headers:`** 

  * **:arrow_forward: `stream:`** a file like object for reading the request body

  


#### Public Attributes:

**`client_address`**: the clients IP and port

**`fragment`**: a string the request fragment

**`headers`**: a dictionary bytes=>List[bytes] of HTTP headers

**`matches`**: dictionary of matched path components. See the Resource documentation for more information

**`method`**: a string containing the HTTP method

**`params`**: dictionary str=>List[str] of decoded query parameters

**`path`**: a string containing the resource path

**`stream`**: a File-like object containig the request content


#### Methods:

* :small_blue_diamond: **`json`**`(self)` - deserialize the request content as a JSON

  

* :small_blue_diamond: **`message`**`(self)` - deserialize the request content as a Serializable instance

  

---
## Router





#### Constructor:

* :small_blue_diamond: **`Router`**`(self)` - 

#### Methods:

* :small_blue_diamond: **`dispatch`**`(self, request)` - 

  * **:arrow_forward: `request:`** 
* :small_blue_diamond: **`registerRoutes`**`(self, routes)` - register routes with the router

  * **:arrow_forward: `routes:`** either a Resource instance, or a list-of-3-tuples: [(http_method, url_pattern, callback)]

  

---
## Response



#### Constructor:

* :small_blue_diamond: **`Response`**`(self, payload=None, status_code=200, headers=None, compress=False)` - 

  * **:arrow_forward: `payload:`** 

  * **:arrow_forward: `status_code:`** 

  * **:arrow_forward: `headers:`** 

  * **:arrow_forward: `compress:`** 
---
## ErrorResponse
Represents an http error response returned from the server

Clients will use this class to hold the original exception raised by urllib.




#### Constructor:

* :small_blue_diamond: **`ErrorResponse`**`(self, obj, status_code=400, headers=None)` - 

  * **:arrow_forward: `obj:`** 

  * **:arrow_forward: `status_code:`** 

  * **:arrow_forward: `headers:`** 
---
## JsonResponse



#### Constructor:

* :small_blue_diamond: **`JsonResponse`**`(self, obj, status_code=200, headers=None)` - 

  * **:arrow_forward: `obj:`** 

  * **:arrow_forward: `status_code:`** 

  * **:arrow_forward: `headers:`** 
---
## SerializableResponse



#### Constructor:

* :small_blue_diamond: **`SerializableResponse`**`(self, obj, status_code=200, headers=None)` - 

  * **:arrow_forward: `obj:`** 

  * **:arrow_forward: `status_code:`** 

  * **:arrow_forward: `headers:`** 
---
## HTTPServer



#### Constructor:

* :small_blue_diamond: **`HTTPServer`**`(self, addr, privkey=None, cert=None)` - 

  * **:arrow_forward: `addr:`** 

  * **:arrow_forward: `privkey:`** 

  * **:arrow_forward: `cert:`** 

#### Methods:

* :small_blue_diamond: **`registerRoutes`**`(self, routes)` - 

  * **:arrow_forward: `routes:`** 
* :small_blue_diamond: **`routes`**`(self)` - 
* :small_blue_diamond: **`run`**`(self)` - 
---
## HTTPClient
docstring for HTTPClient


#### Constructor:

* :small_blue_diamond: **`HTTPClient`**`(self, addr, protocol='http')` - 

  * **:arrow_forward: `addr:`** 

  * **:arrow_forward: `protocol:`** 

#### Methods:

* :small_blue_diamond: **`delete`**`(self, path, query=None, headers=None, callback=None)` - 

  * **:arrow_forward: `path:`** 

  * **:arrow_forward: `query:`** 

  * **:arrow_forward: `headers:`** 

  * **:arrow_forward: `callback:`** 
* :small_blue_diamond: **`get`**`(self, path, query=None, headers=None, callback=None)` - 

  * **:arrow_forward: `path:`** 

  * **:arrow_forward: `query:`** 

  * **:arrow_forward: `headers:`** 

  * **:arrow_forward: `callback:`** 
* :small_blue_diamond: **`getResponses`**`(self)` - yield from the pending set of requests. return a handle containing information for each completed request.

  * **:leftwards_arrow_with_hook: `returns:`** a generator of completed RequestHandle instances

  

* :small_blue_diamond: **`pending`**`(self)` - get the number of pending requests

  * **:leftwards_arrow_with_hook: `returns:`** the count of pending requests

  

* :small_blue_diamond: **`post`**`(self, path, payload, query=None, headers=None, callback=None)` - 

  * **:arrow_forward: `path:`** 

  * **:arrow_forward: `payload:`** 

  * **:arrow_forward: `query:`** 

  * **:arrow_forward: `headers:`** 

  * **:arrow_forward: `callback:`** 
* :small_blue_diamond: **`put`**`(self, path, payload, query=None, headers=None, callback=None)` - 

  * **:arrow_forward: `path:`** 

  * **:arrow_forward: `payload:`** 

  * **:arrow_forward: `query:`** 

  * **:arrow_forward: `headers:`** 

  * **:arrow_forward: `callback:`** 
* :small_blue_diamond: **`start`**`(self)` - 
* :small_blue_diamond: **`stop`**`(self)` - 
* :small_blue_diamond: **`update`**`(self)` - 
---
## :large_orange_diamond: WebSocketOpCode
opcodes indicating the kind of message sent or received over a websocket connection



| Attribute | Enum Value | Description |
| :-------- | ---------: | :---------- |
| Text | 1 | Message Payload is Text data |
| Binary | 2 | Message Payload is binary data |
| Close | 8 | Opcode indicating the connection was closed |
| Ping | 9 | Opcode sent by the server expecting a Pong response from the client |
| Pong | 10 | Opcode sent by the client after receiving a Ping |
| Open | 255 | Non-Standard opcode indicating the connection was successfully opened |

## :cherry_blossom: Functions:

* :small_blue_diamond: **`path_join_safe`**`(root_directory: str, filename: str)` - join the two path components ensuring that the returned value exists with root_directory as prefix.

  * **:arrow_forward: `root_directory:`** the root directory. This must allways be provided by a trusted source.

  * **:arrow_forward: `filename:`** a relative path to a file. This may be provided from untrusted input

  Using this function can prevent files not intended to be exposed by a webserver from being served, by making sure the returned path exists in a directory under the root directory.

  

* :small_blue_diamond: **`get`**`(path)` - decorator which registers a class method as a GET handler

  * **:arrow_forward: `path:`** 

  The decorated function should have the signature:

  

    ```
    def myhandler(self, request: Request)
    ```

  

* :small_blue_diamond: **`put`**`(path, max_content_length=5242880)` - decorator which registers a class method as a PUT handler

  * **:arrow_forward: `path:`** 

  * **:arrow_forward: `max_content_length:`** 

  The decorated function should have the signature:

  

    ```
    def myhandler(self, request: Request)
    ```

  

* :small_blue_diamond: **`post`**`(path, max_content_length=5242880)` - decorator which registers a class method as a POST handler

  * **:arrow_forward: `path:`** 

  * **:arrow_forward: `max_content_length:`** 

  The decorated function should have the signature:

  

    ```
    def myhandler(self, request: Request)
    ```

  

* :small_blue_diamond: **`delete`**`(path)` - decorator which registers a class method as a DELETE handler

  * **:arrow_forward: `path:`** 

  The decorated function should have the signature:

  

    ```
    def myhandler(self, request: Request)
    ```

  

* :small_blue_diamond: **`websocket`**`(path)` - decorator which registers a class method as a websocket handler

  * **:arrow_forward: `path:`** 

  The decorated function should have the signature:

  

    ```
    def mysocket(self, request: Request, opcode: WebSocketOpCode, payload: str|bytes)
    ```

  

* :small_blue_diamond: **`header`**`(header)` - decorator for documenting expected headers

  * **:arrow_forward: `header:`** 
* :small_blue_diamond: **`param`**`(param)` - decorator for documenting expected query parameters

  * **:arrow_forward: `param:`** 
