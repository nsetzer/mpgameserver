#! cd .. && python -m demo.simadventure

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

        self.physics = pylon.AdventurePhysics2dComponent(self,
            map_rect=pygame.Rect(0, 0, g.screen_width, g.screen_height),
            collision_group=collision_group)
        self.physics.floor = g.screen_height - 32

        self.color = (0,0,200)

        self.solid = False

    def update(self, delta_t):

        self.physics.update(delta_t)

    def paint(self, surface):

        pygame.draw.rect(surface, self.color, self.rect)

    def onUserInput(self, event):

        if event.kind == pylon.InputEventType.DIRECTION:
            self.physics.setDirection(event.direction.vector())

        if event.kind == pylon.InputEventType.BUTTON_PRESS:
            if event.button == 0:
                pass

        if event.kind == pylon.InputEventType.BUTTON_RELEASE:
            if event.button == 0:
                pass

    def onCollide(self, ent, normal=None):
        print(ent)

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

        self.rect2 = pygame.Rect(self.rect.x+4, self.rect.y+4, self.rect.width-8+1, self.rect.height-12+1)
        self.rect3 = pygame.Rect(self.rect.x, self.rect.y, self.rect.width+1, self.rect.height+1)

    def update(self, delta_t):
        pass

    def paint(self, viewport):

        pygame.draw.rect(viewport, (60,60,60), self.rect)
        pygame.draw.rect(viewport, (120,120,120), self.rect2, border_radius=2)
        pygame.draw.line(viewport, (120,120,120), self.rect.bottomleft, self.rect2.bottomleft)
        pygame.draw.line(viewport, (120,120,120), self.rect.bottomright, self.rect2.bottomright)
        pygame.draw.line(viewport, (120,120,120), self.rect.topleft, self.rect2.topleft)
        pygame.draw.line(viewport, (120,120,120), self.rect.topright, self.rect2.topright)
        pygame.draw.rect(viewport, (120,120,120), self.rect3, width=1)

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

        self.floor = pygame.Rect(0, g.screen_height - 32, g.screen_width, 32)

        self.ecs = pylon.EntityStore()

        self.group_solid = pylon.EntityGroup(self.ecs, pylon.EntityStore.SOLID)

        px = g.screen_width/2 - 16
        py = g.screen_height/2 - 16
        self.player = Player((px, py), collision_group=self.group_solid)
        self.ghost = Player((px, py), collision_group=self.group_solid)
        self.ghost.color = (100,0,0)

        self.ecs.addEntity(self.ghost)
        self.ecs.addEntity(self.player)

        self.ecs.addEntity(Wall(pygame.Rect(32,32,128,32)))
        self.ecs.addEntity(Wall(pygame.Rect(g.screen_width-32-128,32,128,32)))
        self.ecs.addEntity(Wall(pygame.Rect(32,g.screen_height-64,128,32)))
        self.ecs.addEntity(Wall(pygame.Rect(g.screen_width-32-128,g.screen_height-64,128,32)))

        cx = g.screen_width/2
        cy = g.screen_height/2

        self.ecs.addEntity(Wall(pygame.Rect(cx - 32 - 128, cy - 32 -32, 128,32)))
        self.ecs.addEntity(Wall(pygame.Rect(cx - 32 - 32, cy - 32 - 128, 32, 96)))
        self.ecs.addEntity(Wall(pygame.Rect(cx - 32 - 128, cy - 32 - 128, 32, 32)))

        self.ecs.addEntity(Wall(pygame.Rect(cx + 32, cy - 32 - 32, 128,32)))
        self.ecs.addEntity(Wall(pygame.Rect(cx + 32, cy - 32 - 128, 32, 96)))
        self.ecs.addEntity(Wall(pygame.Rect(cx + 32 + 96, cy - 32 - 128, 32, 32)))

        self.ecs.addEntity(Wall(pygame.Rect(cx - 32 - 128, cy + 32, 128,32)))
        self.ecs.addEntity(Wall(pygame.Rect(cx - 32 - 32, cy + 32 + 32, 32, 96)))
        self.ecs.addEntity(Wall(pygame.Rect(cx + 32 + 96, cy + 32 + 96, 32, 32)))

        self.ecs.addEntity(Wall(pygame.Rect(cx + 32, cy + 32 , 128,32)))
        self.ecs.addEntity(Wall(pygame.Rect(cx + 32, cy + 32 + 32, 32, 96)))
        self.ecs.addEntity(Wall(pygame.Rect(cx - 32 -128, cy + 32 + 96, 32, 32)))

        self.remote_ctrl = pylon.RemoteInputController(self.ghost)
        self.client = pylon.DummyClient(self.remote_ctrl)
        self.ctrl = pylon.InputController(getInputDevice(), self.player, self.client)

    def handle_event(self, evt):
        self.ctrl.handle_event(evt)

    def update(self, delta_t):

        self.group_solid.clear()

        self.ctrl.update(delta_t)
        self.client.update(delta_t)
        self.remote_ctrl.update(delta_t)

        for ent in self.ecs.getEntitiesByComponent(pylon.EntityStore.UPDATE):
            ent.update(delta_t)

    def paint(self, surface):
        surface.fill((30,30,30))

        for ent in self.ecs.getEntitiesByComponent(pylon.EntityStore.VISIBLE):
            ent.paint(surface)

def main():

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)-15s %(levelname)s %(filename)s:%(funcName)s():%(lineno)d:%(message)s')
    engine = pylon.Engine()
    engine.init()

    g.update_interval = 0.1
    engine.setScene(MainScene())
    engine.run()

if __name__ == '__main__':
    main()