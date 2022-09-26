#! cd .. && python -m demo.simplatform

# TODO:
#  - resolve issue with ECS and calling update on remote controlled instances
#     ecs.getUpdateableInstances()
#     remote control disables flag?
#  - Test failure modes for de-sync

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

class Player(pylon.Entity):
    def __init__(self, pos, collision_group=None):
        super(Player, self).__init__(pygame.Rect(*pos, 32, 32))

        self.alive = True

        self.physics = pylon.PlatformPhysics2dComponent(self,
                map_rect=pygame.Rect(0, 0, g.screen_width, g.screen_height),
                collision_group=collision_group)
        self.physics.floor = g.screen_height - 32

        self.gravity_counter = 0

        self.color = (0,0,200)

        self.log = None

        if False:
            self.log = open("./output.bin", "wb")

        self.update_timer = Timer(g.update_interval, self.onUpdateTimeout)

        #self.history = []

    def update(self, delta_t):

        self.physics.update(delta_t)

        if self.gravity_counter > 0:
             self.gravity_counter -= 1
             if  self.gravity_counter <= 0:
                self.physics.gravity = 512

        if self.log:
            self.log.write(struct.pack("<bLL", 2, 8, g.frame_counter))
            self.log.write(struct.pack("<ll", self.entity.rect.x, self.entity.rect.y))
            self.log.flush()

        #if g.frame_counter%5 ==0:
        #    self.history.append(self.rect.copy())
        #    if len(self.history) > 12:
        #        self.history.pop(0)

    def paint(self, surface):

        pygame.draw.rect(surface, self.color, self.rect)

        #for i, rect in enumerate(self.history):
        #    r,g,b = self.color
        #    p = (i+1)/len(self.history)
        #    r = int(r*p)
        #    g = int(g*p)
        #    b = int(b*p)
        #    s = pygame.Surface((rect.width, rect.height))
        #    s.set_alpha(64)
        #    s.fill((r,g,b))
        #    surface.blit(s, rect.topleft)


    def onUpdateTimeout(self):

        if self.log:
            data = self.getState().dumpb()
            self.log.write(struct.pack("<bLL", 1, len(data), g.frame_counter))
            self.log.write(data)
            self.log.flush()

    def onUserInput(self, event):

        if event.kind == pylon.InputEventType.DIRECTION:
            self.physics.setDirection(event.direction.vector())

        if event.kind == pylon.InputEventType.BUTTON_PRESS:
            if event.button == 0:
                self.physics.yspeed = - 256
                self.physics.yaccum = 0
                # reduce gravity while the button is pressed for
                # up to 1/2 of a second
                self.physics.gravity = 512/3
                self.gravity_counter = 30

        if event.kind == pylon.InputEventType.BUTTON_RELEASE:
            if event.button == 0:
                self.physics.gravity = 512

    def getState(self):
        physics = self.physics.getState()

        return physics

    def setState(self, state):
        self.physics.setState(state)

    def interpolateState(self, state1, state2, p):

        physics = self.physics.interpolateState(state1, state2, p)
        return physics

class Wall(pylon.Entity):
    def __init__(self, rect=None):
        if rect is None:
            rect = pygame.Rect(0,0,0,0)
        super(Wall, self).__init__(rect)

    def update(self, delta_t):
        pass

    def paint(self, viewport):

        pygame.draw.rect(viewport, (60,60,60), self.rect)

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

        self.group_solid = pylon.EntityGroup(self.ecs, pylon.EntityStore.SOLID)

        self.player = Player((32, g.screen_height - 64), collision_group=self.group_solid)
        self.ghost = Player((32, g.screen_height - 64), collision_group=self.group_solid)
        self.ghost.color = (100,0,0)

        self.ecs.addEntity(self.ghost)
        self.ecs.addEntity(self.player)

        self.ecs.addEntity(Wall(pygame.Rect(g.screen_width/2-96,g.screen_height-96,192,16)))
        self.ecs.addEntity(Wall(pygame.Rect(g.screen_width/4-96,g.screen_height-192,192,16)))
        self.ecs.addEntity(Wall(pygame.Rect(3*g.screen_width/4-96,g.screen_height-192,192,16)))

        self.remote_ctrl = pylon.RemoteInputController(self.ghost)
        self.client = pylon.DummyClient(self.remote_ctrl)
        self.ctrl = pylon.InputController(getInputDevice(), self.player, self.client)

    def handle_event(self, evt):
        self.ctrl.handle_event(evt)

    def update(self, delta_t):

        self.ctrl.update(delta_t)
        self.client.update(delta_t)
        self.remote_ctrl.update(delta_t)

        for ent in self.ecs.getEntitiesByComponent(pylon.EntityStore.UPDATE):
            ent.update(delta_t)

    def paint(self, surface):
        surface.fill((0,0,0))

        for ent in self.ecs.getEntitiesByComponent(pylon.EntityStore.VISIBLE):
            ent.paint(surface)

def main():

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)-15s %(levelname)s %(filename)s:%(funcName)s():%(lineno)d:%(message)s')
    engine = pylon.Engine()
    engine.init()


    count = pygame.joystick.get_count()
    print(count)
    joy = [pygame.joystick.Joystick(x) for x in range(count)]
    print(joy[0].get_numbuttons())

    g.update_interval = 0.1
    engine.setScene(MainScene())
    engine.run()

if __name__ == '__main__':
    main()