#! cd .. && python -m demo.shipclient

import os
import sys
import logging
import math
import random
import time

from PIL import Image

from enum import Enum

import pygame
sys.path.insert(0, os.getcwd())

from .shipcommon import ShipPhase, ShipState, ShipUpdate, ShipDestroy, \
    ShipRemove, ShipCreateBullet, collide_triangle_point, Bullet, \
    ShipPolygon, ShipTriangle, g, lerp, lerp_wrap, wrap
from mpgameserver import Serializable, EllipticCurvePublicKey, UdpClient, \
    Timer, LineGraph, RetryMode

colors = [(255,0,0), (0,0,255), (160, 75, 160), (255, 130, 0)]

class GameScenes(Enum):
    ERROR = 1
    CONNECTING = 2
    MAIN = 3

class GameScene(object):
    def __init__(self):
        super(GameScene, self).__init__()

    def handle_message(self, msg):
        pass

    def handle_event(self, evt):
        pass

    def paint(self):
        pass

    def update(self, delta_t):
        pass

class SmokeParticle(object):
    max_time = 3
    def __init__(self, pos):
        self.time = 0
        xr = random.randint(0,32) - 16
        yr = random.randint(0,32) - 16
        self.pos = pygame.Vector2(pos) - pygame.Vector2(xr, yr)
        v = random.randint(100, 200)
        a = random.randint(0, 360)
        self.vec = pygame.Vector2(v, 0).rotate(a)

class Ship(object):
    def __init__(self, color):
        super(Ship, self).__init__()

        self.phase = ShipPhase.DEFAULT

        self.pos = pygame.math.Vector2(32,32)
        self.direction = (0,0)
        self.angle = 45
        self.thrust = pygame.math.Vector2(0,0)

        # the thrust vector is added to the ship's thrust every update step
        # the vector will be rotated by the ships angle
        # the magnitude was chosen based on what felt right
        self.thrust_vector = pygame.Vector2(320, 0)
        self.drag_coeff = .99
        self.charge = 0

        self.charge_rate = 3

        self.recv_time = 0

        self.color = color

        self.recv_timeout = .1

        self.timer_dead = 0
        self.particles = []
        self.counter = 0

    def setDirection(self, vector):
        self.direction = vector

    def update(self, delta_t):

        if self.phase == ShipPhase.DEAD:

            self.particles = [p for p in self.particles if p.time < SmokeParticle.max_time]

            for p in self.particles:
                p.time += delta_t
                p.pos += p.vec * delta_t

            # every other frame create a bunch or particles until the counter reaches zero
            # this has an added bonus that if the player is moving the explosion source
            # roughly tracts their last trajectory.
            if self.counter > 0:
                self.counter -= 1
                if self.counter%2 == 0:
                    for i in range(15):
                        self.particles.append(SmokeParticle(self.pos))

    def paint(self, surface):

        poly = ShipPolygon(self.pos, self.angle)

        if self.phase == ShipPhase.CHARGING:

            p = self.charge*self.charge
            if p > 1.0:
                color = self.color
            else:
                color = pygame.Color(0,0,0).lerp(self.color, p)
            pygame.draw.polygon(surface, color, poly, width=0)

            pygame.draw.polygon(surface, self.color, poly, width=2)

        elif self.phase == ShipPhase.DEAD:
            for p in self.particles:
                size = 1.0 - (p.time / SmokeParticle.max_time)
                pygame.draw.circle(surface, (255,255,255), p.pos, 5 * size)

        else:
            pygame.draw.polygon(surface, self.color, poly, width=2)

    def getState(self):

        state = ShipState()
        state.token = g.client.token()
        state.time = time.time()
        state.phase = self.phase
        state.angle = int(self.angle)
        state.xpos = int(self.pos[0])
        state.ypos = int(self.pos[1])
        state.charge = self.charge

        return state

    def setState(self, state):

        raise NotImplementedError()

    def destroy(self):

        self.phase = ShipPhase.DEAD
        self.counter = 15
        self.timer_dead = 0
        self.particles = []

    def revive(self):

        self.particles = []
        self.counter = 0
        self.phase = ShipPhase.DEFAULT
        self.pos[0] = g.screen_width//2
        self.pos[1] = g.screen_height//2
        self.angle = 90
        self.thrust = pygame.math.Vector2(0,0)

class LocalShip(Ship):
    def __init__(self):
        color = (0,255,0)
        super(LocalShip, self).__init__(color)

        self.particles = []
        self.counter = 0
        self.phase = ShipPhase.DEFAULT
        self.pos[0] = g.screen_width//2
        self.pos[1] = g.screen_height//2
        self.angle = 90
        self.thrust = pygame.math.Vector2(0,0)

    def update(self, delta_t):
        super().update(delta_t)

        # for a local player, apply the effects of keyboard input
        # to move the player's ship. The player can directly change
        # the phase of the ship (default to charging) and the direction
        # which is used to determine rotation and thrust.

        r, v = self.direction
        if r:
            # rotate the ship
            self.angle = wrap(self.angle + (180 * r) * delta_t, 0, 360)

        # apply drag
        self.thrust = self.thrust * self.drag_coeff

        if v != 0:
            # apply thrust in the direction the ship is facing
            self.thrust += self.thrust_vector.rotate(self.angle) * delta_t * v * -1

        # increase the charge counter while in the charging state
        if self.phase == ShipPhase.CHARGING:
            self.charge = min(self.charge + self.charge_rate * delta_t, 1.0)

        # move the ship N pixels per second using the calculated thrust
        self.pos += self.thrust * delta_t
        self.pos[0] = wrap(self.pos[0], 0, g.screen_width)
        self.pos[1] = wrap(self.pos[1], 0, g.screen_height)

class RemoteShip(Ship):
    """ The ship controlled by remote players

    Remote players send updates every 100ms. This class
    caches the last two updates received and interpolates over time the
    state of the player. This means that remote players are delayed by 100ms,
    but appears to play smoothly.

    """
    def __init__(self):
        color = random.choice(colors)
        super(RemoteShip, self).__init__(color)
        self.states = []

    def update(self, delta_t):
        super().update(delta_t)

        self.recv_time += delta_t

        if len(self.states) < 2:
            return

        s1 = self.states[-2]
        s2 = self.states[-1]

        p = self.recv_time/g.update_interval

        # interpolate the state

        # angle and position are linearly interpolated but can wrap
        # around some maximum value
        self.angle = lerp_wrap(s1.angle, s2.angle, p, 360)
        self.pos[0] = lerp_wrap(s1.xpos, s2.xpos, p, g.screen_width)
        self.pos[1] = lerp_wrap(s1.ypos, s2.ypos, p, g.screen_height)
        # charge is a value from 0 to 1, linearly interpolate
        self.charge = lerp(s1.charge, s2.charge, p)
        # the phase is a discrete value, use the oldest value
        self.phase = s1.phase

    def setState(self, state):

        # always keep the last two received states
        if len(self.states) > 0:
            self.states = [self.states[-1], state]
        else:
            self.states.append(state)
        self.recv_time = 0

    def destroy(self):
        super().destroy()
        self.states = []

    def revive(self):
        super().revive()
        self.states = []

class KeyMap(object):

    UP    = 0x01
    RIGHT = 0x02
    DOWN  = 0x04
    LEFT  = 0x08

    HORIZONTAL = LEFT|RIGHT
    VERTICAL = UP|DOWN
    DIR_MASK = UP|LEFT|DOWN|RIGHT

    BTN_0 = 0x10

    KEY_UP = (pygame.K_w, pygame.K_UP)
    KEY_RIGHT = (pygame.K_d, pygame.K_RIGHT)
    KEY_DOWN = (pygame.K_s, pygame.K_DOWN)
    KEY_LEFT = (pygame.K_a, pygame.K_LEFT)
    KEY_BTN_0 = (pygame.K_TAB, pygame.K_SPACE, pygame.K_q)

    @staticmethod
    def getCode(key):
        if key in KeyMap.KEY_UP:
            return KeyMap.UP
        elif key in KeyMap.KEY_RIGHT:
            return KeyMap.RIGHT
        elif key in KeyMap.KEY_DOWN:
            return KeyMap.DOWN
        elif key in KeyMap.KEY_LEFT:
            return KeyMap.LEFT
        elif key in KeyMap.KEY_BTN_0:
            return KeyMap.BTN_0

        return 0

class InputController(object):
    def __init__(self, parent):
        super(InputController, self).__init__()

        self.parent = parent

        # an ordered list of direction inputs that have been pressed
        # maintain the order of opposite keys, so that when released
        # the direction can be updated correctly
        self.ord_dir = []
        self.buttons = {
            0:False,
            1:False,
            2:False
        }
        self.current_vector = (-1, -1)

    def handle_event(self, evt):

        if evt.type == pygame.KEYDOWN:
            code = KeyMap.getCode(evt.key)
            if code&KeyMap.DIR_MASK:
                if code not in self.ord_dir:
                    self.ord_dir.append(code)
                    self._setDirection(self._getDirVector())
            elif code:
                self._onPress((code >> 4)-1)

        elif evt.type == pygame.KEYUP:
            code = KeyMap.getCode(evt.key)
            if code&KeyMap.DIR_MASK:
                if code in self.ord_dir:
                    self.ord_dir.remove(code)
                self._setDirection(self._getDirVector())
            elif code:
                self._onRelease((code >> 4)-1)

    def _getDirVector(self):
        dx = 0
        dy = 0
        for ord in self.ord_dir:
            if ord&KeyMap.VERTICAL and dy == 0:
                dy = -1 if ord&KeyMap.UP else 1
            if ord&KeyMap.HORIZONTAL and dx == 0:
                dx = -1 if ord&KeyMap.LEFT else 1
        return (dx, dy)

    def _setDirection(self, vector):
        if vector == self.current_vector:
            return

        self.setDirection(vector)
        self.current_vector = vector

    def _onPress(self, index):
        if not self.buttons[index]:
            self.onPress(index)
            self.buttons[index] = True

    def _onRelease(self, index):
        if self.buttons[index]:
            self.onRelease(index)
            self.buttons[index] = False

    def setDirection(self, vector):

        self.parent.local_player.setDirection(vector)

    def onPress(self, index):

        if index == 0:

            if self.parent.local_player.phase == ShipPhase.DEFAULT:
                self.parent.local_player.phase = ShipPhase.CHARGING

    def onRelease(self, index):

        if index == 0:
            if self.parent.local_player.phase == ShipPhase.CHARGING:

                pos = self.parent.local_player.pos
                angle = self.parent.local_player.angle
                charge = self.parent.local_player.charge

                # send a request to create a bullet for the user

                msg = ShipCreateBullet(xpos=pos[0], ypos=pos[1],
                    angle=angle, charge=charge)

                g.client.send(msg.dumpb(), retry=RetryMode.BEST_EFFORT)

                self.parent.local_player.phase = ShipPhase.DEFAULT
                self.parent.local_player.charge = 0

class ConnectingScene(GameScene):
    def __init__(self):
        super(ConnectingScene, self).__init__()

        g.client.connect((g.host, g.port), callback=self.onConnect)

        self.font = pygame.font.SysFont('arial', 72)
        self.text = self.font.render("Connecting...", True, (255, 255, 255))

    def onConnect(self, connected):
        print("client connected: %s" % connected)

        if not connected:
            self.text = self.font.render("Unable to Connect", True, (255, 255, 255))

    def handle_message(self, msg):
        pass

    def handle_event(self, evt):
        pass

    def paint(self):
        g.screen.fill((0,0,0))
        x = g.screen_width//2 - self.text.get_width()//2
        y = g.screen_height//2 - self.text.get_height()//2
        g.screen.blit(self.text, (x,y))

    def update(self, delta_t):

        if g.client.connected():
            g.next_state = GameScenes.MAIN

class MainScene(GameScene):
    def __init__(self):
        super(MainScene, self).__init__()
        self.font = pygame.font.SysFont('arial', 16)

        self.local_player = LocalShip()
        self.remote_players = {}
        self.bullets = []
        self.widgets = []

        self.ctrl = InputController(self)

        self.update_timer = Timer(g.update_interval, self.onUpdateTimeout)
        self.update_timeout = 0

        self.line_bytes_sent = []
        self.line_bytes_recv = []
        self.max_bytes_sent = self.font.render("????", True, (0, 200, 0))
        self.max_bytes_recv = self.font.render("????", True, (200, 0, 0))

        self.line_pkts_sent = []
        self.line_pkts_recv = []
        self.max_pkts_sent = self.font.render("????", True, (0, 200, 0))
        self.max_pkts_recv = self.font.render("????", True, (200, 0, 0))

        self.extra_points = []

        self.paint_widgets = False
        self._init_stats()

    def _init_stats(self):
        size = 100

        rect = pygame.Rect(0, g.screen_height-3*size-17,g.screen_width//2, size)
        self.widgets.append(LineGraph(rect, 2*60, "Latency (ms)",
            lambda: [g.client.stats().latency[:-1]],
            lambda v: "%d"%(1000*v)))
        self.widgets[-1].setShowLabels(True)
        self.graph_fps = self.widgets[-1]

        rect = pygame.Rect(0, g.screen_height-2*size-9,g.screen_width//2, size)
        self.widgets.append(LineGraph(rect, 2*60, "Packets Sent (G) Recv (R)",
            lambda: [g.client.stats().pkts_recv[:-1], g.client.stats().pkts_sent[:-1]],
            lambda v: "%d"%v))
        self.widgets[-1].setShowLabels(True)
        self.graph_pkts = self.widgets[-1]

        rect = pygame.Rect(0, g.screen_height-1*size-1,g.screen_width//2, size)
        self.widgets.append(LineGraph(rect, 2*60, "Bytes Sent (G) Recv (R)",
            lambda: [g.client.stats().bytes_recv[:-1], g.client.stats().bytes_sent[:-1]],
            lambda v: "%d"%v))
        self.widgets[-1].setShowLabels(True)
        self.graph_bytes = self.widgets[-1]

    def onUpdateTimeout(self):

        t0 = time.time()
        delta_t = t0 - self.update_timeout
        self.update_timeout = t0
        state = self.local_player.getState()

        # send the message with retry disabled
        # if the update is not received, there will be a new message
        # to take its place.
        g.client.send(state.dumpb(), retry=RetryMode.NONE)

    def handle_message(self, msg):

        if msg.type_id == ShipUpdate.type_id:
            for state in msg.states:

                # drop updates for the local player
                if state.token == g.client.token():
                    continue

                # create a new remote player
                if state.token not in self.remote_players:
                    self.remote_players[state.token] = RemoteShip()

                # update the remote player
                self.remote_players[state.token].setState(state)

        elif msg.type_id == ShipRemove.type_id:
            if msg.token in self.remote_players:
                del self.remote_players[msg.token]

        elif msg.type_id == ShipCreateBullet.type_id:

            self.bullets.append(Bullet((msg.xpos, msg.ypos), msg.angle, msg.charge))

        elif msg.type_id == ShipDestroy.type_id:

            if msg.token == g.client.token():
                if msg.destroy:
                    self.local_player.destroy()
                else:
                    self.local_player.revive()
            elif msg.token in self.remote_players:
                if msg.destroy:
                    self.remote_players[msg.token].destroy()
                else:
                    self.remote_players[msg.token].revive()
            else:
                print("error: unkown ship %s" % msg.token)

    def handle_event(self, evt):
        self.ctrl.handle_event(evt)

        # mouse events trigger a test of the triangle-point collision detection
        # press the button to draw the test triangles
        # release the button to clear the test
        if evt.type == pygame.MOUSEBUTTONDOWN:
            if evt.button == 1:

                t1, t2, t3 = ShipTriangle(self.local_player.pos, self.local_player.angle)
                distance_squared = self.local_player.pos.distance_squared_to(evt.pos)

                is_close = distance_squared < 32*32
                does_collide = collide_triangle_point(t1, t2, t3, evt.pos)

                print("Is Close: %s, Does collide: %s" % (is_close, does_collide))

                self.extra_points = [
                    (t1, t2, evt.pos),
                    (t1, t3, evt.pos),
                    (t2, t3, evt.pos)
                ]

        elif evt.type == pygame.MOUSEBUTTONUP:
            self.extra_points = []

        if evt.type == pygame.KEYDOWN:
            if evt.key == pygame.K_z:
                self.paint_widgets = not self.paint_widgets

    def paint(self):
        g.screen.fill((0,0,0))

        self.local_player.paint(g.screen)

        for ship in self.remote_players.values():
            ship.paint(g.screen)

        for bullet in self.bullets:
            bullet.paint(g.screen)

        if self.extra_points:
            for color, poly in zip(colors, self.extra_points):
                pygame.draw.polygon(g.screen, color, poly, width=0)
            pygame.draw.circle(g.screen, (0,255,0), (self.local_player.pos), 32, width=1)

        if self.paint_widgets:
            for wgt in self.widgets:
                wgt.paint(g.screen)

    def update(self, delta_t):

        self.update_timer.update(delta_t)

        self.local_player.update(delta_t)

        for ship in self.remote_players.values():
            ship.update(delta_t)

        for bullet in self.bullets:
            bullet.update(delta_t)

        self.bullets = [b for b in self.bullets if b.alive()]

        for wgt in self.widgets:
            wgt.update(delta_t)


class ExceptionScene(GameScene):
    def __init__(self):
        super(ExceptionScene, self).__init__()
        self.exec_info = sys.exc_info()
        font = pygame.font.SysFont('arial', 72)
        self.text = font.render("Error", True, (255, 255, 255))

    def paint(self):

        g.screen.fill((0,0,170))
        x = g.screen_width//2 - self.text.get_width()//2
        y = g.screen_height//2 - self.text.get_height()//2
        g.screen.blit(self.text, (x,y))

class Engine(object):
    def __init__(self):
        super(Engine, self).__init__()

        self.active = False
        self.state = None
        self.screenshot_index = 0

    def init(self):

        pygame.init()
        pygame.font.init()
        g.next_state = GameScenes.CONNECTING

        g.screen = pygame.display.set_mode((g.screen_width, g.screen_height))

    def getState(self, state):
        if state == GameScenes.ERROR:
            return ExceptionScene()

        elif state == GameScenes.CONNECTING:
            return ConnectingScene()
        else:
            return MainScene()

    def setActive(self, active):
        self.active = active

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.setActive(False)

        if event.type == pygame.KEYUP:
            if event.key == pygame.K_ESCAPE:
                self.setActive(False)

            elif event.key == pygame.K_p:
                imgs = []

                raw = pygame.image.tostring(g.screen, "RGBA", False)
                image = Image.frombytes("RGBA", g.screen.get_size(), raw)
                filename = 'screenshot-%d.png' % self.screenshot_index
                image.save(filename)
                self.screenshot_index += 1
                print("saved " + filename)

        self.state.handle_event(event)

    def run(self):

        g.clock = pygame.time.Clock()

        self.active = True

        accumulator = 0.0
        update_step = 1 / g.FPS

        g.client = UdpClient(EllipticCurvePublicKey.unsafeTestKey())

        while self.active:

            try:
                if g.next_state:
                    self.state = self.getState(g.next_state)
                    g.next_state = None

                dt = g.clock.tick(g.FPS) / 1000
                accumulator += dt
                g.frame_counter += 1

                # handle events
                for event in pygame.event.get():
                    if self.handle_event(event):
                        continue

                # send/recv network data
                g.client.update()
                for seqnum, msg in g.client.getMessages():
                    self.state.handle_message(Serializable.loadb(msg))

                # update game state
                # use a constant delta
                while accumulator > update_step:
                    self.state.update(update_step)
                    accumulator -= update_step

                # paint
                self.state.paint()

                pygame.display.flip()
            except Exception as e:
                logging.exception("error")
                g.next_state = GameScenes.ERROR

        pygame.quit()

        if g.client and g.client.connected():
            g.client.disconnect()
            g.client.waitForDisconnect()

def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)-15s %(levelname)s %(filename)s:%(funcName)s():%(lineno)d:%(message)s')
    engine = Engine()
    engine.init()
    engine.run()

if __name__ == '__main__':
    main()