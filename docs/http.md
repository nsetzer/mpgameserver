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

 **Resource**`(self)` - 

#### Methods:

 **routes**`(self)` - 

  * **returns:** a list-of-3-tuples: [(http_method, url_pattern, callback)]

  

---
## Request
A Request contains the information received from a client




#### Constructor:

 **Request**`(self, addr: Tuple[str, int], method: str, path: str, params: Dict[str, str], fragment: str, headers: Dict[bytes, bytes], stream: IO[bytes])` - 

  * **addr:** A 2-tuple (host: str, port: int)

  * **method:** 

  * **path:** the absolute path + query + fragment

  * **params:** 

  * **fragment:** 

  * **headers:** 

  * **stream:** a file like object for reading the request body

  


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

 **json**`(self)` - deserialize the request content as a JSON

  

 **message**`(self)` - deserialize the request content as a Serializable instance

  

---
## Router





#### Constructor:

 **Router**`(self)` - 

#### Methods:

 **dispatch**`(self, request)` - 

  * **request:** 
 **registerRoutes**`(self, routes)` - register routes with the router

  * **routes:** either a Resource instance, or a list-of-3-tuples: [(http_method, url_pattern, callback)]

  

---
## Response



#### Constructor:

 **Response**`(self, payload=None, status_code=200, headers=None, compress=False)` - 

  * **payload:** 

  * **status_code:** 

  * **headers:** 

  * **compress:** 
---
## ErrorResponse
Represents an http error response returned from the server

Clients will use this class to hold the original exception raised by urllib.




#### Constructor:

 **ErrorResponse**`(self, obj, status_code=400, headers=None)` - 

  * **obj:** 

  * **status_code:** 

  * **headers:** 
---
## JsonResponse



#### Constructor:

 **JsonResponse**`(self, obj, status_code=200, headers=None)` - 

  * **obj:** 

  * **status_code:** 

  * **headers:** 
---
## SerializableResponse



#### Constructor:

 **SerializableResponse**`(self, obj, status_code=200, headers=None)` - 

  * **obj:** 

  * **status_code:** 

  * **headers:** 
---
## HTTPServer



#### Constructor:

 **HTTPServer**`(self, addr, privkey=None, cert=None)` - 

  * **addr:** 

  * **privkey:** 

  * **cert:** 

#### Methods:

 **registerRoutes**`(self, routes)` - 

  * **routes:** 
 **routes**`(self)` - 
 **run**`(self)` - 
---
## HTTPClient
docstring for HTTPClient


#### Constructor:

 **HTTPClient**`(self, addr, protocol='http')` - 

  * **addr:** 

  * **protocol:** 

#### Methods:

 **delete**`(self, path, query=None, headers=None, callback=None)` - 

  * **path:** 

  * **query:** 

  * **headers:** 

  * **callback:** 
 **get**`(self, path, query=None, headers=None, callback=None)` - 

  * **path:** 

  * **query:** 

  * **headers:** 

  * **callback:** 
 **getResponses**`(self)` - yield from the pending set of requests. return a handle containing information for each completed request.

  * **returns:** a generator of completed RequestHandle instances

  

 **pending**`(self)` - get the number of pending requests

  * **returns:** the count of pending requests

  

 **post**`(self, path, payload, query=None, headers=None, callback=None)` - 

  * **path:** 

  * **payload:** 

  * **query:** 

  * **headers:** 

  * **callback:** 
 **put**`(self, path, payload, query=None, headers=None, callback=None)` - 

  * **path:** 

  * **payload:** 

  * **query:** 

  * **headers:** 

  * **callback:** 
 **start**`(self)` - 
 **stop**`(self)` - 
 **update**`(self)` - 
---
##  WebSocketOpCode
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

 **path_join_safe**`(root_directory: str, filename: str)` - join the two path components ensuring that the returned value exists with root_directory as prefix.

  * **root_directory:** the root directory. This must allways be provided by a trusted source.

  * **filename:** a relative path to a file. This may be provided from untrusted input

  Using this function can prevent files not intended to be exposed by a webserver from being served, by making sure the returned path exists in a directory under the root directory.

  

 **get**`(path)` - decorator which registers a class method as a GET handler

  * **path:** 

  The decorated function should have the signature:

  

    ```
    def myhandler(self, request: Request)
    ```

  

 **put**`(path, max_content_length=5242880)` - decorator which registers a class method as a PUT handler

  * **path:** 

  * **max_content_length:** 

  The decorated function should have the signature:

  

    ```
    def myhandler(self, request: Request)
    ```

  

 **post**`(path, max_content_length=5242880)` - decorator which registers a class method as a POST handler

  * **path:** 

  * **max_content_length:** 

  The decorated function should have the signature:

  

    ```
    def myhandler(self, request: Request)
    ```

  

 **delete**`(path)` - decorator which registers a class method as a DELETE handler

  * **path:** 

  The decorated function should have the signature:

  

    ```
    def myhandler(self, request: Request)
    ```

  

 **websocket**`(path)` - decorator which registers a class method as a websocket handler

  * **path:** 

  The decorated function should have the signature:

  

    ```
    def mysocket(self, request: Request, opcode: WebSocketOpCode, payload: str|bytes)
    ```

  

 **header**`(header)` - decorator for documenting expected headers

  * **header:** 
 **param**`(param)` - decorator for documenting expected query parameters

  * **param:** 
