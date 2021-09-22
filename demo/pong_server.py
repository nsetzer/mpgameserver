#! cd .. && python -m demo.pong_server


import os
import sys
import select
import logging
import math
import time

from mpgameserver import EventHandler, TwistedServer, GuiServer, ServerContext, \
    Timer, Serializable, EllipticCurvePrivateKey, RetryMode, \
    ServerMessageDispatcher, server_event, \
    get, put, delete, post, Router, Resource, \
    Response, JsonResponse

from . import pong_common as common

class Room(object):
    def __init__(self, room_id, name):
        super(Room, self).__init__()
        self.room_id = room_id
        self.name = name

        self.player0 = None
        self.player1 = None

class GameService(object):
    def __init__(self):
        super(GameService, self).__init__()

        self.players = {}      # addr to client
        self.rooms = {}        # room_id to Room
        self.player_room = {}  # addr to Room

        self.next_id = 1
        self.rooms[0] = Room(0, "abc")

    def connect(self, client):
        self.players[client.addr] = client

        self.rooms[0].player0 = client
        self.player_room[client.addr] = self.rooms[0]

    def disconnect(self, client):
        if client.addr in self.players:
            del self.players[client.addr]

    def getRoomList(self):
        return {rid: room.name for rid, room in self.rooms.items()}

    def createRoom(self, client, name):

        room = Room(self.next_id, name)
        room.player0 = client

        self.rooms[self.next_id] = room
        self.player_room[client.addr] = room

        self.next_id += 1

        return room

class LobbyResource(object):
    def __init__(self, service):
        super(LobbyResource, self).__init__()

        self.service = service

    def connect(self, client):
        self.service.connect(client)



    def disconnect(self, client):
        self.service.disconnect(client)

    @server_event
    def onRoomList(self, client, seqnum, msg: common.RoomList):
        msg = common.RoomListReply(rooms=self.service.getRoomList())
        client.send(msg.dumpb())

    @server_event
    def onRoomCreate(self, client, seqnum, msg: common.RoomCreate):

        room = self.service.createRoom(msg.name)
        msg = RoomCreateReply(room_id=room.room_id)
        client.send(msg.dumpb())

    @server_event
    def onRoomJoin(self, client, seqnum, msg: common.RoomJoin):
        pass

class GameResource(object):
    def __init__(self, service):
        super(GameResource, self).__init__()
        self.service = service

    @server_event
    def onBallRelease(self, client, seqnum, msg: common.BallRelease):

        if client.addr in self.service.player_room:
            room = self.service.player_room[client.addr]

            payload = msg.dumpb()

            if room.player0:
                room.player0.send(payload)

            if room.player1:
                room.player1.send(payload)
        else:
            print("error not in room")

    @server_event
    def onPlayerPosition(self, client, seqnum, msg: common.PlayerPosition):
        pass

class PongHandler(EventHandler):
    def __init__(self):
        super(PongHandler, self).__init__()

        self.dispatcher = ServerMessageDispatcher()

        self.service = GameService()

        self.resource_lobby = LobbyResource(self.service)
        self.resource_game = GameResource(self.service)

        self.dispatcher.register(self.resource_lobby)
        self.dispatcher.register(self.resource_game)

    def connect(self, client):

        self.resource_lobby.connect(client)

    def disconnect(self, client):

        self.resource_lobby.disconnect(client)

    def update(self, delta_t):

       pass

    def handle_message(self, client, seqnum, payload):

        msg = Serializable.loadb(payload)

        self.dispatcher.dispatch(client, seqnum, msg)

class SampleResource(Resource):

    @get("/health")
    def get_health(self, request):
        return JsonResponse({"status": "ok"}, status_code=200)

def main():

    host = "0.0.0.0"
    port = 1474

    format = '%(asctime)-15s %(levelname)s %(filename)s:%(funcName)s():%(lineno)d:%(message)s'
    logging.basicConfig(level=logging.DEBUG, format=format)

    # read the root key from stdin or use a default development key
    key = None
    if not sys.stdin.isatty():
        r, _, _ = select.select([sys.stdin], [], [], 0)
        if r:
            key = EllipticCurvePrivateKey.fromPEM(sys.stdin.read())
    if key is None:
        sys.stderr.write("MpGameServer using unsafe test key\n")
        key = EllipticCurvePrivateKey.unsafeTestKey()

    handler = PongHandler()

    ctxt = ServerContext(handler, key)

    if '--gui' in sys.argv:
        server = GuiServer(ctxt, (host, port))
    else:
        server = TwistedServer(ctxt, (host, port))

    router = Router()
    router.registerEndpoints(SampleResource().endpoints())
    server.listenTCP(router, (host, port+1))

    server.run()

if __name__ == '__main__':
    main()