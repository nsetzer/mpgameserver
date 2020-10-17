
class EventHandler(object):
    """ Base class for user defined game logic.

    In your game, create a subclass from `EventHandler` and then implement the event handler methods.
    Pass an instance of EventHandler to a [ServerContext](#servercontext) instance

    The EventHandler events are guaranted to always be run from the same thread.


    """


    def starting(self):  # pragma: no cover
        """ server starting event

        This event is raised when the server first starts
        """
        pass

    def shutdown(self):  # pragma: no cover
        """ server shutdown event

        This event is raised when the server is shutting down gracefully.
        It is the last event that will be called before the process exits

        > :x: Do not depend on this event being raised. The server does not guarantee
        that this method will be called in the event of a crash or SIGKILL.
        """
        pass

    def connect(self, client):  # pragma: no cover
        """ client connection event

        :param client: the client instance that connected

        This event is raised when a client successfully completes the handshake

        > :bulb: In order to send a message to all connected clients, record
        connections in a map client.token => client. Remove clients when they disconnect.
        Then you can use the map to get all connected clients and call send on each one with
        the message.
        """
        pass

    def disconnect(self, client):  # pragma: no cover
        """ client disconnect event

        :param client: the client instance that disconnected

        This event is raised when a client disconnects or timeouts
        """
        pass

    def update(self, delta_t: float):  # pragma: no cover
        """ server tick event

        :param delta_t: elapsed time in seconds since the last update

        This event is raised once per server tick
        """
        pass

    def handle_message(self, client, seqnum, msg: bytes = b''):  # pragma: no cover
        """ receive client message event

        :param client: the client that sent the message
        :param msg: the message

        This event is raised whenever a message is received from a remote client.
        If a datagram contained multiple messages, then this event will be
        raised once for each message.
        """
        pass

