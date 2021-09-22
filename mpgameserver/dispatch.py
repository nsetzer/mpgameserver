
import inspect
from mpgameserver import Serializable, SeqNum


class DispatchError(Exception):
    pass

def server_event(method):
    """
    method decorator for server events

    :param method: a class method to be decorated

    Use this decorator to mark methods of a class that can
    be registered as server events with ServerMessageDispatcher

    the annotated method must have the signature: (client, seqnum, msg).
    Type annotations

    The following is an example on how to use the dispatch api.
    First create a 'Resource' class which handles events of a given type
    annotate the msg type and decorate the method handlers.

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

    """

    sig = inspect.signature(method)
    args = list(sig.parameters.items())

    if len(args) != 4:
        raise Exception()

    # the third argument is the message
    parameter = args[3][1]

    if parameter.annotation is inspect._empty:
        raise Exception()
    else:
        method._event = parameter.annotation
    return method

def client_event(method):
    """
    method decorator for client events

    :param method: a class method to be decorated

    Use this decorator to mark methods of a class that can
    be registered as client events with ClientMessageDispatcher

    The following is an example on how to use the dispatch api.
    First create a 'Resource' class which handles events of a given type
    annotate the msg type and decorate the method handlers.

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

    """

    sig = inspect.signature(method)
    args = list(sig.parameters.items())

    if len(args) != 3:
        raise Exception()

    # the second argument is the message
    parameter = args[2][1]

    if parameter.annotation is inspect._empty:
        raise Exception()
    else:
        method._event = parameter.annotation
    return method

class MessageDispatcher(object):
    def __init__(self):
        super(MessageDispatcher, self).__init__()
        # a map of event type to callable
        self.registered_events = {}

    def register(self, resource):
        """ register all methods of a given resource
        """

        for name in dir(resource):
            attr = getattr(resource, name)
            if inspect.isroutine(attr) and hasattr(attr, "_event"):
                self.register_function(attr._event, attr)

    def unregister(self, resource):
        """ unregister all methods of a given resource
        """
        for name in dir(resource):
            attr = getattr(resource, name)
            if inspect.isroutine(attr) and hasattr(attr, "_event"):
                if attr._event in self.registered_events:
                    self.unregister_function(attr._event)

    def register_function(self, event_type, fn):
        """ register an event handler for a given type

        Normally you will not need to call this method directly
        """
        self.registered_events[event_type] = fn

    def unregister_function(self, event_type):
        """
        unregister the event handler for a given type

        Normally you will not need to call this method directly
        """
        del self.registered_events[event_type]

    def dispatch(self):

        raise NotImplementedError()

class ServerMessageDispatcher(MessageDispatcher):
    """ An Event Dispatcher for server events

    server events are messages with an associate client and seqnum.

    register functions to process events with this class. When
    an event is received (using dispath()) the type of the msg
    is used to determine which of the registered functions to call

    """

    def __init__(self):
        super().__init__()

    def dispatch(self, client, seqnum, msg):
        """ call the registered method handler for an event of type msg

        :param client: the client that sent the message
        :param seqnum: the seqnum for the received message
        :param msg: the message received from the server

        """

        T = type(msg)
        if T not in self.registered_events:
            raise DispatchError(T.__name__)
        self.registered_events[T](client, seqnum, msg)

class ClientMessageDispatcher(MessageDispatcher):
    """ An Event Dispatcher for server events

    client events are messages with an associate seqnum.

    register functions to process events with this class. When
    an event is received (using dispath()) the type of the msg
    is used to determine which of the registered functions to call

    """

    def __init__(self):
        super().__init__()

    def dispatch(self, seqnum, msg):
        """ call the registered method handler for an event of type msg

        :param seqnum: the seqnum for the received message
        :param msg: the message received from the server
        """
        T = type(msg)
        if T not in self.registered_events:
            raise DispatchError(T.__name__)
        self.registered_events[T](seqnum, msg)

