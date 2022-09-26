#! cd .. && python -m demo.pong2_server

import os
import sys
import select
import logging
import math
import time

import pygame

from mpgameserver import EventHandler, TwistedServer, GuiServer, ServerContext, \
    Timer, Serializable, RetryMode, \
    ServerMessageDispatcher, server_event, \
    get, put, delete, post, Router, Resource, \
    Response, JsonResponse

from mpgameserver import pylon
from mpgameserver.pylon import g

from . import pong2_common as common

class Room(object):
    def __init__(self, uid, player0, player1):
        super(Room, self).__init__()

        self.uid = uid
        self.player0 = player0
        self.player1 = player1

        map_rect = pygame.Rect(0, 0, g.screen_width, g.screen_height)
        self.paddle0 = common.Paddle(0, map_rect)
        self.paddle1 = common.Paddle(1, map_rect)

        # TODO: create an NPC controller for the ball
        #       InputController and NpcController need an api for sending
        #       states that are keyframe states
        self.update_timer = Timer(0.1, self.onUpdateTimeout)
        self.clock = 0

        self.ball = common.Ball((32,32), map_rect, [self.paddle0, self.paddle1])
        self.ball.callback = self.onUpdateTimeout
        self.ball.captured_by = self.paddle0

        self.ctrl0 = pylon.RemoteInputController(self.paddle0)
        self.ctrl1 = pylon.RemoteInputController(self.paddle1)

        self.ball.rect.x = g.screen_width/2
        self.ball.rect.x = g.screen_height/2
        self.ball.physics.xspeed = -100
        self.ball.physics.yspeed = -100

    def update(self, delta_t):
        self.clock += delta_t
        self.update_timer.update(delta_t)

        self.ctrl0.update(delta_t)
        self.ctrl1.update(delta_t)
        self.ball.update(delta_t)

    def onUpdateTimeout(self):

        state = self.ball.getState()
        state = pylon.NetworkPlayerState(token=1, clock=self.clock, state=state)
        data = state.dumpb()

        if self.player0:
            self.player0.send(data, retry=RetryMode.NONE)

        if self.player1:
            self.player1.send(data, retry=RetryMode.NONE)

    def onBallRelease(self, msg):

        if  self.ball.captured_by and self.player0 and self.player1:

            data = msg.dumpb()
            self.player0.send(data, retry=RetryMode.BEST_EFFORT)
            self.player1.send(data, retry=RetryMode.BEST_EFFORT)

            self.ball.captured_by = None
            self.ball.physics.xspeed = 100
            self.ball.physics.yspeed = 100

    def onNetworkPlayerState(self, msg):

        if self.player0.token == msg.token:
            self.ctrl0.receiveState(msg)
            self.player1.send(msg.dumpb(), retry=RetryMode.NONE)

        if self.player1.token == msg.token:
            self.ctrl1.receiveState(msg)
            self.player0.send(msg.dumpb(), retry=RetryMode.NONE)

class GameResource(object):
    def __init__(self):
        super(GameResource, self).__init__()

        self.lobby = []
        self.player2room = {}
        self.rooms = {}

        self.nextid = 1

    def connect(self, client):

        self.lobby.append(client)

        if len(self.lobby) >= 2:

            player0 = self.lobby.pop()
            player1 = self.lobby.pop()

            room = Room(self.nextid, player0, player1)
            self.nextid += 1

            self.rooms[room.uid] = room
            self.player2room[player0.token] = room
            self.player2room[player1.token] = room

            msg = common.GameStart(
                player0=player0.token,
                player1=player1.token)

            player0.send(msg.dumpb(), retry=RetryMode.BEST_EFFORT)
            player1.send(msg.dumpb(), retry=RetryMode.BEST_EFFORT)
            print("start room", room.uid)

    def disconnect(self, client):

        if client.token in self.player2room:
            room = self.player2room[client.token]
            del self.player2room[room.player0.token]
            del self.player2room[room.player1.token]
            del self.rooms[room.uid]

            if room.player0 is not client:
                self.lobby.append(room.player0)

            if room.player1 is not client:
                self.lobby.append(room.player1)

        if client in self.lobby:
            self.lobby.remove(client)

        print("disconnect", client)

    def update(self, delta_t):

        for room in self.rooms.values():
            room.update(delta_t)

    @server_event
    def onBallRelease(self, client, seqnum, msg: common.BallRelease):

        if client.token in self.player2room:
            room = self.player2room[client.token]
            room.onBallRelease(msg)

    @server_event
    def onNetworkPlayerState(self, client, seqnum, msg: pylon.NetworkPlayerState):

        if client.token in self.player2room:
            room = self.player2room[client.token]
            room.onNetworkPlayerState(msg)

class GameHandler(EventHandler):
    def __init__(self):
        super(GameHandler, self).__init__()

        self.resource_game = GameResource()
        self.dispatcher = ServerMessageDispatcher()
        self.dispatcher.register(self.resource_game)

    def connect(self, client):
        self.resource_game.connect(client)

    def disconnect(self, client):
        self.resource_game.disconnect(client)

    def update(self, delta_t):
        self.resource_game.update(delta_t)

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

    handler = GameHandler()

    ctxt = ServerContext(handler)

    if '--gui' in sys.argv:
        server = GuiServer(ctxt, (host, port))
    else:
        server = TwistedServer(ctxt, (host, port))

    router = Router()
    router.registerRoutes(SampleResource().routes())
    server.listenTCP(router, (host, port+1))

    server.run()

if __name__ == '__main__':
    main()