
import unittest
from mpgameserver import Serializable, SeqNum, \
    ServerMessageDispatcher, ClientMessageDispatcher, \
    server_event, client_event

class Event1(Serializable):
    value: int = 0

class Event2(Serializable):
    value: int = 0

class ServerResource(object):
    def __init__(self):
        super(ServerResource, self).__init__()

        self.event1 = None
        self.event2 = None

    @server_event
    def onEvent1(self, client, seq: SeqNum, msg: Event1):
        self.event1 = msg

    @server_event
    def onEvent2(self, client, seq: SeqNum, msg: Event2):
        self.event2 = msg

class ClientResource(object):
    def __init__(self):
        super(ClientResource, self).__init__()

        self.event1 = None
        self.event2 = None

    @client_event
    def onEvent1(self, seq: SeqNum, msg: Event1):
        self.event1 = msg

    @client_event
    def onEvent2(self, seq: SeqNum, msg: Event2):
        self.event2 = msg

class DispatchTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_server_dispatch(self):

        resource = ServerResource()
        dispatcher = ServerMessageDispatcher()
        dispatcher.register(resource)

        msg1 = Event1(value=1)
        dispatcher.dispatch(None, SeqNum(), msg1)

        msg2 = Event2(value=2)
        dispatcher.dispatch(None, SeqNum(), msg2)

        self.assertEqual(resource.event1.value, msg1.value)
        self.assertEqual(resource.event2.value, msg2.value)

    def test_client_dispatch(self):

        resource = ClientResource()
        dispatcher = ClientMessageDispatcher()
        dispatcher.register(resource)

        msg1 = Event1(value=1)
        dispatcher.dispatch(SeqNum(), msg1)

        msg2 = Event2(value=2)
        dispatcher.dispatch(SeqNum(), msg2)

        self.assertEqual(resource.event1.value, msg1.value)
        self.assertEqual(resource.event2.value, msg2.value)

def main():
    unittest.main()

if __name__ == '__main__':
    main()
