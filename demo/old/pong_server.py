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

    def joinRoom(self, client, room_id):

        if room_id not in self.rooms:
            return None, common.RoomJoinStatus.ERROR_DNE

        room = self.rooms[room_id]

        if room.player1:
            return None, common.RoomJoinStatus.ERROR_FULL

        room.player1 = client

        self.player_room[client.addr] = room

        return room, common.RoomJoinStatus.OK


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

        room = self.service.createRoom(client, msg.name)
        msg = common.RoomCreateReply(room_id=room.room_id)
        client.send(msg.dumpb())

    @server_event
    def onRoomJoin(self, client, seqnum, msg: common.RoomJoin):

        room, status = self.service.joinRoom(client, msg.room_id)
        if room:

            msg = common.RoomJoinReply(
                room_id=room.room_id,
                status=status,
                opponent_name="alice",
                side=common.PlayerSide.LEFT
                )
            room.player0.send(msg.dumpb())

            msg = common.RoomJoinReply(
                room_id=room.room_id,
                status=status,
                opponent_name="bob",
                side=common.PlayerSide.RIGHT
                )
            room.player1.send(msg.dumpb())

        else:

            msg = common.RoomJoinReply(
                room_id=0,
                status=status,
                opponent_name="",
                side=common.PlayerSide.UNKNOWN
                )
            client.send(msg.dumpb())

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

        # just send player position updates to the other player in the room
        room = self.service.player_room[client.addr]

        if room.player0 is client and room.player1:
            room.player1.send(msg.dumpb())

        if room.player1 is client and room.player0:
            room.player0.send(msg.dumpb())

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

    handler = PongHandler()

    ctxt = ServerContext(handler)

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