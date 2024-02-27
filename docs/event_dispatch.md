[Home](../README.md)
* [ServerMessageDispatcher](#servermessagedispatcher)
* [ClientMessageDispatcher](#clientmessagedispatcher)

 # Event Dispatch API
 The Event Dispatch API is a collection of classes designed to work with the serialization library. It allows for message dispatch based on the type of the message. It can be used in both the server or client.
 
---
## ServerMessageDispatcher
An Event Dispatcher for server events

server events are messages with an associate client and seqnum.

register functions to process events with this class. When an event is received (using dispath()) the type of the msg is used to determine which of the registered functions to call




#### Constructor:

 **ServerMessageDispatcher**`(self)` - 

#### Methods:

 **dispatch**`(self, client, seqnum, msg)` - call the registered method handler for an event of type msg

  * **client:** the client that sent the message

  * **seqnum:** the seqnum for the received message

  * **msg:** the message received from the server

  

 **register**`(self, resource)` - register all methods of a given resource

  * **resource:** 

  

 **register_function**`(self, event_type, fn)` - register an event handler for a given type

  * **event_type:** 

  * **fn:** 

  Normally you will not need to call this method directly

  

 **unregister**`(self, resource)` - unregister all methods of a given resource

  * **resource:** 

  

 **unregister_function**`(self, event_type)` - unregister the event handler for a given type

  * **event_type:** 

  Normally you will not need to call this method directly

  

---
## ClientMessageDispatcher
An Event Dispatcher for server events

client events are messages with an associate seqnum.

register functions to process events with this class. When an event is received (using dispath()) the type of the msg is used to determine which of the registered functions to call




#### Constructor:

 **ClientMessageDispatcher**`(self)` - 

#### Methods:

 **dispatch**`(self, seqnum, msg)` - call the registered method handler for an event of type msg

  * **seqnum:** the seqnum for the received message

  * **msg:** the message received from the server

  

 **register**`(self, resource)` - register all methods of a given resource

  * **resource:** 

  

 **register_function**`(self, event_type, fn)` - register an event handler for a given type

  * **event_type:** 

  * **fn:** 

  Normally you will not need to call this method directly

  

 **unregister**`(self, resource)` - unregister all methods of a given resource

  * **resource:** 

  

 **unregister_function**`(self, event_type)` - unregister the event handler for a given type

  * **event_type:** 

  Normally you will not need to call this method directly

  


## :cherry_blossom: Functions:

 **server_event**`(method)` - method decorator for server events

  * **method:** a class method to be decorated

  Use this decorator to mark methods of a class that can be registered as server events with ServerMessageDispatcher

  the annotated method must have the signature: (client, seqnum, msg). Type annotations

  The following is an example on how to use the dispatch api. First create a 'Resource' class which handles events of a given type annotate the msg type and decorate the method handlers.

  

    ```python

    class Event(Serializable):
        value: int = 0

    class ServerResource

        @server_event
        def handle_event(self, client: EventHandler.Client, seqnum: SeqNum, msg: Event)
            print(msg)

    dispatcher = ServerMessageDispatcher()
    resource = ServerResource()

    dispatcher.register(resource)

    # calls ClientResource.handle_event
    dispatcher.dispatch(client, seqnum, Event(value=0))

    ```

  

 **client_event**`(method)` - method decorator for client events

  * **method:** a class method to be decorated

  Use this decorator to mark methods of a class that can be registered as client events with ClientMessageDispatcher

  The following is an example on how to use the dispatch api. First create a 'Resource' class which handles events of a given type annotate the msg type and decorate the method handlers.

  

    ```python

    class Event(Serializable):
        value: int = 0

    class ClientResource

        @server_event
        def handle_event(self, seqnum: SeqNum, msg: Event)
            print(msg)

    dispatcher = ClientMessageDispatcher()
    resource = ClientResource()

    dispatcher.register(resource)

    # calls ClientResource.handle_event
    dispatcher.dispatch(seqnum, Event(value=0))

    ```

  

