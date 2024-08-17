#! cd .. && python -m demo.pong2_launcher
#! cd .. && python -m demo.pong2_client

import os
import sys
import logging
import math
import random
import time
import struct

import pygame

from mpgameserver import Timer, RetryMode, Serializable

from mpgameserver import pylon
from mpgameserver.pylon import g

from . import pong2_common as common

if '--id=1' in sys.argv:
    CLIENT_ID=1
if '--id=2' in sys.argv:
    CLIENT_ID=2

def getInputDevice():

    direction_config = {
        pylon.Direction.UP   : (pygame.K_UP,),
        pylon.Direction.RIGHT: (pygame.K_RIGHT,),
        pylon.Direction.DOWN : (pygame.K_DOWN,),
        pylon.Direction.LEFT : (pygame.K_LEFT,),
    }

    button_config = {
        0: (pygame.K_SPACE,),
    }

    device = pylon.KeyboardInputDevice(direction_config, button_config)

    return device

class MainScene(pylon.GameScene):
    def __init__(self):
        super(MainScene, self).__init__()

        self.ecs = pylon.EntityStore()

        map_rect = pygame.Rect(0, 0, g.screen_width, g.screen_height)

        self.player0 = common.Paddle(0, map_rect)
        self.player1 = common.Paddle(1, map_rect)
        self.player0.callback = self.doBallRelease
        self.player1.callback = self.doBallRelease

        self.ctrl_local = None
        self.ctrl_remote = None
        self.ctrls = []

        self.ecs.addEntity(self.player0)
        self.ecs.addEntity(self.player1)

        self.handle_message(common.GameStart(player0=g.client.token(), player1=0))

        # The Ball is an 'NPC' controlled by  the server.
        self.ball = common.Ball((0,0), map_rect, [self.player0, self.player1])
        self.ball_ctrl = pylon.RemoteInputController(self.ball)
        self.ecs.addEntity(self.ball)

    def handle_message(self, msg):

        if msg.type_id == common.GameStart.type_id:

            self.onGameStart(msg)

        elif msg.type_id == pylon.NetworkPlayerState.type_id and self.ctrl_remote:
            if msg.token == 1:
                self.ball_ctrl.receiveState(msg)

            if msg.token == self.ctrl_remote.token:
                self.ctrl_remote.receiveState(msg)

    def handle_event(self, evt):

        if self.ctrl_local:
            self.ctrl_local.handle_event(evt)

    def update(self, delta_t):

        for ctrl in self.ctrls:
            ctrl.update(delta_t)

        self.ball_ctrl.update(delta_t)

        for ent in self.ecs.getEntitiesByComponent(pylon.EntityStore.UPDATE):
            ent.update(delta_t)

    def paint(self, surface):
        surface.fill((0,0,0))

        for ent in self.ecs.getEntitiesByComponent(pylon.EntityStore.VISIBLE):
            ent.paint(surface)

    def onGameStart(self, msg):

        if msg.player0 == g.client.token():
            # this user is the first player
            # give them control of the left hand side
            ent0 = self.player0
            ent1 = self.player1

            ent0.token = msg.player0
            ent1.token = msg.player1

        elif msg.player1 == g.client.token():
            # this user is the second player
            # give them control of the right hand side
            ent0 = self.player1
            ent1 = self.player0

            ent0.token = msg.player1
            ent1.token = msg.player0
        else:
            print(msg)
            raise RuntimeError()

        ent0.requires_update = True
        ent1.requires_update = True # reset by input controller

        self.ctrl_local = pylon.InputController(getInputDevice(), ent0, g.client)
        self.ctrl_remote = pylon.RemoteInputController(ent1)

        self.ctrl_remote.token = ent1.token

        self.ctrls = [self.ctrl_local, self.ctrl_remote]

    def doBallRelease(self):

        g.client.send(common.BallRelease(position=0).dumpb(), retry=RetryMode.BEST_EFFORT)

def main():

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)-15s %(levelname)s %(filename)s:%(funcName)s():%(lineno)d:%(message)s')
    engine = pylon.Engine()
    engine.init()


    count = pygame.joystick.get_count()
    print(count)
    joy = [pygame.joystick.Joystick(x) for x in range(count)]
    print(joy[0].get_numbuttons())

    g.update_interval = 0.1
    def transition(success):
        if success:
            engine.setScene(MainScene())

    engine.setScene(pylon.ConnectingScene(transition))
    engine.run()

if __name__ == '__main__':
    main()