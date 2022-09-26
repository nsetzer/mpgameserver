#! cd .. && python -m demo.simspace


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

def lerp_wrap(a, b, p, size):
    """ linearly interpolate between two value a and b given percent p
    wrap arround back to 0 if the resulting value is greater than size/2
    and wrap around back to m if the resulting value is less than size/2

    """
    if p > 1.0:
        return b
    if p < 0.0:
        return a

    c = b - a
    if c < -size/2:
        c += size
    elif c > size/2:
        c -= size

    c = a + p * c

    if c > size:
        c -= size
    if c < 0:
        c += size

    return c

class ShipPhysics2dComponent(pylon.Physics2dComponent):
    def __init__(self, entity, map_rect=None, collision_group=None):
        super(ShipPhysics2dComponent, self).__init__(entity, collision_group)

        self.max_speed = 192
        self.friction = 0

        self.map_rect = map_rect

    def update(self, delta_t):

        # apply acceleration to change the speed
        self.xspeed += delta_t * self.xaccel
        self.yspeed += delta_t * self.yaccel

        self.xspeed += -self.xspeed * self.friction * delta_t
        self.yspeed += -self.yspeed * self.friction * delta_t

        # clamp the maximum horizontal speed
        if self.xspeed > self.max_speed:
            self.xspeed = self.max_speed
        elif self.xspeed < -self.max_speed:
            self.xspeed = -self.max_speed

        # clamp the maximum vertical speed
        if self.yspeed > self.max_speed:
            self.yspeed = self.max_speed
        elif self.yspeed < -self.max_speed:
            self.yspeed = -self.max_speed

        if abs(delta_t*self.xspeed) < 0.01:
            self.xspeed = 0

        if abs(delta_t*self.yspeed) < 0.01:
            self.yspeed = 0

        super().update(delta_t)

        # check the bounds of the room

        if self.map_rect:

            if self.entity.rect.x < self.map_rect.left:
                self.entity.rect.x += self.map_rect.width

            if self.entity.rect.x > self.map_rect.right:
                self.entity.rect.x -= self.map_rect.width

            if self.entity.rect.y < self.map_rect.top:
                self.entity.rect.y += self.map_rect.height

            if self.entity.rect.y > self.map_rect.bottom:
                self.entity.rect.y -= self.map_rect.height

def ShipPolygon(pos, angle):
    """
    the default polygon is centered at (0,0) and facing EAST
    the polygon is rotated around the center point then translated
    to final position

    this is used for rendering the ship to the screen
    """
    polygon = [
        pygame.math.Vector2(0,0).rotate(angle) + pos,
        pygame.math.Vector2(-16,-16).rotate(angle) + pos,
        pygame.math.Vector2(32, 0).rotate(angle) + pos,
        pygame.math.Vector2(-16, 16).rotate(angle) + pos,
    ]
    return polygon

def ThrustPolygon(pos, angle):
    """
    the default polygon is centered at (0,0) and facing EAST
    the polygon is rotated around the center point then translated
    to final position

    this is used for rendering the ship to the screen
    """
    polygon = [
        pygame.math.Vector2(0, 0).rotate(angle) + pos,
        pygame.math.Vector2(-8, -4).rotate(angle) + pos,
        pygame.math.Vector2(-16, 0).rotate(angle) + pos,
        pygame.math.Vector2(-8, 4).rotate(angle) + pos,
    ]
    return polygon

def ThrustReverse1Polygon(pos, angle):
    """
    the default polygon is centered at (0,0) and facing EAST
    the polygon is rotated around the center point then translated
    to final position

    this is used for rendering the ship to the screen
    """
    polygon = [
        pygame.math.Vector2(-16, -16).rotate(angle) + pos,
        pygame.math.Vector2(-8, -12).rotate(angle) + pos,
        pygame.math.Vector2(-0, -16).rotate(angle) + pos,
        pygame.math.Vector2(-8, -20).rotate(angle) + pos,
    ]
    return polygon

def ThrustReverse2Polygon(pos, angle):
    """
    the default polygon is centered at (0,0) and facing EAST
    the polygon is rotated around the center point then translated
    to final position

    this is used for rendering the ship to the screen
    """
    polygon = [
        pygame.math.Vector2(-16, 16).rotate(angle) + pos,
        pygame.math.Vector2(-8, 12).rotate(angle) + pos,
        pygame.math.Vector2(-0, 16).rotate(angle) + pos,
        pygame.math.Vector2(-8, 20).rotate(angle) + pos,
    ]
    return polygon

class ShipState(Serializable):

    token: int = 0
    clock: int = 0
    physics: pylon.PhysicsState = None
    angle: float = 0
    thrust: int = 0

class Player(pylon.Entity):
    def __init__(self, pos):
        super(Player, self).__init__(pygame.Rect(*pos, 32, 32))

        self.alive = True

        self.angle = 0
        self.rotate = 0
        self.thrust = 0

        self.physics = ShipPhysics2dComponent(self,
            map_rect=pygame.Rect(0,0,g.screen_width,g.screen_height))
        self.physics.floor = g.screen_height - 32

        self.color = (0,0,200)

        self.log = None

        if False:
            self.log = open("./output.bin", "wb")

        self.update_timer = Timer(g.update_interval, self.onUpdateTimeout)

        #self.history = []

    def update(self, delta_t):

        self.angle += self.rotate * delta_t

        if self.angle > 360:
            self.angle -= 360
        if self.angle < 0:
            self.angle += 360


        self.physics.update(delta_t)

        if self.log:
            self.log.write(struct.pack("<bLL", 2, 8, g.frame_counter))
            self.log.write(struct.pack("<ll", self.entity.rect.x, self.entity.rect.y))
            self.log.flush()

    def paint(self, surface):

        #pygame.draw.rect(surface, self.color, self.rect)

        poly = ShipPolygon(self.rect.center, self.angle)
        pygame.draw.polygon(surface, self.color, poly, width=3)

        if self.thrust < 0 or self.physics.friction != 0:
            poly = ThrustPolygon(self.rect.center, self.angle)
            pygame.draw.polygon(surface, (255,128,0), poly, width=2)

        if self.thrust > 0 or self.physics.friction != 0:
            poly = ThrustReverse1Polygon(self.rect.center, self.angle)
            pygame.draw.polygon(surface, (255,128,0), poly, width=2)

            poly = ThrustReverse2Polygon(self.rect.center, self.angle)
            pygame.draw.polygon(surface, (255,128,0), poly, width=2)

    def onUpdateTimeout(self):

        if self.log:
            data = self.getState().dumpb()
            self.log.write(struct.pack("<bLL", 1, len(data), g.frame_counter))
            self.log.write(data)
            self.log.flush()

    def onUserInput(self, event):

        if event.kind == pylon.InputEventType.DIRECTION:

            dx, dy = event.direction.vector()
            self.rotate = 180 * dx

            self.physics.xaccel = -dy * self.physics.max_speed * math.cos(self.angle*math.pi/180)
            self.physics.yaccel = -dy * self.physics.max_speed * math.sin(self.angle*math.pi/180)
            self.thrust = dy

        if event.kind == pylon.InputEventType.BUTTON_PRESS:
            if event.button == 0:
                self.physics.friction = 1

        if event.kind == pylon.InputEventType.BUTTON_RELEASE:
            if event.button == 0:
                self.physics.friction = 0

    def getState(self):

        state = ShipState()

        state.physics = self.physics.getState()
        state.angle = self.angle
        state.thrust = self.thrust

        return state

    def setState(self, state):

        self.physics.setState(state.physics)
        self.angle = state.angle
        self.thrust = state.thrust

    def interpolateState(self, state1, state2, p):

        phys = pylon.PhysicsState()
        # custom interpolation
        phys.xpos   = lerp_wrap(state1.physics.xpos, state2.physics.xpos, p, g.screen_width)
        phys.ypos   = lerp_wrap(state1.physics.ypos, state2.physics.ypos, p, g.screen_height)
        phys.xspeed = state1.physics.xspeed * (1-p) + state2.physics.xspeed * p
        phys.yspeed = state1.physics.yspeed * (1-p) + state2.physics.yspeed * p
        phys.xaccel = state1.physics.xaccel * (1-p) + state2.physics.xaccel * p
        phys.yaccel = state1.physics.yaccel * (1-p) + state2.physics.yaccel * p
        # print(state1.physics.xpos, phys.xpos, state2.physics.xpos, p)

        state = ShipState()
        state.physics = phys
        state.angle = lerp_wrap(state1.angle, state2.angle, p, 360)
        state.thrust = round(state1.thrust * (1-p) + state2.thrust * p)
        #print(">", p, state1.angle, state.angle, state2.angle)

        return state


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

        self.player = Player((g.screen_width/2, g.screen_height/2))
        self.ghost = Player((g.screen_width/2, g.screen_height/2))
        self.ghost.color = (100,0,0)

        self.remote_ctrl = pylon.RemoteInputController(self.ghost)
        self.client = pylon.DummyClient(self.remote_ctrl, delay=int(.1*g.FPS))
        self.ctrl = pylon.InputController(getInputDevice(), self.player, self.client)

        self.ecs = pylon.EntityStore()

        self.ecs.addEntity(self.ghost)
        self.ecs.addEntity(self.player)

        self.device = pylon.JoystickInputDevice(0, {}, {}, print)

    def handle_event(self, evt):
        self.ctrl.handle_event(evt)
        self.device.handle_event(evt)

    def update(self, delta_t):

        self.ctrl.update(delta_t)
        self.client.update(delta_t)
        self.remote_ctrl.update(delta_t)

        for ent in self.ecs.getEntitiesByComponent(pylon.EntityStore.UPDATE):
            ent.update(delta_t)

    def paint(self, surface):
        surface.fill((0,0,0))

        self.ghost.paint(g.screen)
        self.player.paint(g.screen)

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

    print(g.screen.x)
    engine.run()

if __name__ == '__main__':
    main()