
import pygame
import math
from typing import List
from mpgameserver.serializable import Serializable, SerializableEnum

from mpgameserver import pylon

class GameStart(Serializable):
    player0: int = 0
    player1: int = 0

class BallRelease(Serializable):
    position: int = 0 # 0: player0, 1: player1

class PaddlePhysics(pylon.Physics2dComponent):

    def __init__(self, entity, map_rect=None, collision_group=None):
        super(PaddlePhysics, self).__init__(entity, map_rect, collision_group)

    def update(self, delta_t):

        super().update(delta_t)

        if self.map_rect:

            if self.entity.rect.y < self.map_rect.top:
                if self.yspeed < 0:
                    self.yspeed = 0
                    self.entity.rect.y = self.map_rect.top

            if self.entity.rect.y > self.map_rect.bottom - self.entity.rect.height:
                if self.yspeed > 0:
                    self.yspeed = 0
                    self.entity.rect.y = self.map_rect.bottom - self.entity.rect.height

class Paddle(pylon.Entity):
    def __init__(self, player_id, map_rect, collision_group=None):

        width = 8
        height = map_rect.height / 4
        if player_id==0:
            x = map_rect.width/2 - map_rect.height/2
        else:
            x = map_rect.width/2 + map_rect.height/2 - width
        y = map_rect.width/2 - height/8
        super(Paddle, self).__init__(pygame.Rect(x,y,width,height))
        self.token = 0

        self.physics = PaddlePhysics(self,
                map_rect=map_rect)

        self.color = (0,0,200)

    def update(self, delta_t):
        self.physics.update(delta_t)

    def paint(self, surface):

        pygame.draw.rect(surface, self.color, self.rect)

    def onUserInput(self, event):

        if event.kind == pylon.InputEventType.DIRECTION:

            dx, dy = event.direction.vector()
            self.physics.yspeed = self.physics.map_rect.height/2*dy

        if event.kind == pylon.InputEventType.BUTTON_PRESS:
            if event.button == 0:
                pass

        if event.kind == pylon.InputEventType.BUTTON_RELEASE:
            if event.button == 0:
                self.callback()

    def getState(self):
        return self.physics.getState()

    def setState(self, state):
        self.physics.setState(state)

    def interpolateState(self, state1, state2, p):

        return self.physics.interpolateState(state1, state2, p)

class BallPhysics(pylon.Physics2dComponent):

    def __init__(self, entity, map_rect=None, collision_group=None):
        super(BallPhysics, self).__init__(entity, map_rect, collision_group)

    def update(self, delta_t):

        super().update(delta_t)

        if self.map_rect:

            if self.entity.rect.x < self.map_rect.left:
                if self.xspeed < 0:
                    self.xspeed = -self.xspeed
                    self.entity.rect.x = self.map_rect.left

            if self.entity.rect.x > self.map_rect.right - self.entity.rect.width:
                if self.xspeed > 0:
                    self.xspeed = -self.xspeed
                    self.entity.rect.x = self.map_rect.right - self.entity.rect.width

            if self.entity.rect.y < self.map_rect.top:
                if self.yspeed < 0:
                    self.yspeed = -self.yspeed
                    self.entity.rect.y = self.map_rect.top

            if self.entity.rect.y > self.map_rect.bottom - self.entity.rect.height:
                if self.yspeed > 0:
                    self.yspeed = -self.yspeed
                    self.entity.rect.y = self.map_rect.bottom - self.entity.rect.height

class Ball(pylon.Entity):
    def __init__(self, pos, map_rect, collision_group=None):
        super(Ball, self).__init__(pygame.Rect(*pos, 8, 8))

        self.physics = BallPhysics(self,
            map_rect=map_rect,
            collision_group=collision_group)

        self.history = []

        self.callback = None

        self.captured_by = None

    def onCollide(self, ent, normal=None):
        print(ent, normal)

        speed = (self.physics.xspeed**2 + self.physics.yspeed**2)**0.5
        direction = pygame.math.Vector2(self.physics.xspeed, self.physics.yspeed)

        print(ent, normal, speed, direction)
        self.physics.xspeed, self.physics.yspeed = direction.reflect(normal)

        if self.callback:
            self.callback()

    def update(self, delta_t):

        if self.captured_by:

            self.rect.centery = self.captured_by.rect.centery
            self.rect.centerx = self.captured_by.rect.centerx + 32

        else:
            self.physics.update(delta_t)

    def paint(self, surface):

        self.history.append(self.rect.copy())
        while len(self.history) > 20:
            self.history.pop(0)

        for i, rect in enumerate(reversed(self.history)):
            pygame.draw.rect(surface, ((200 - i*5),0,0), rect)

        pygame.draw.rect(surface, (200,0,0), self.rect)

    def getState(self):

        return self.physics.getState()

    def setState(self, state):
        self.physics.setState(state)

    def interpolateState(self, state1, state2, p):

        return self.physics.interpolateState(state1, state2, p)
