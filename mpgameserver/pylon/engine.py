
import os
import sys
import logging
import math
import random
import time
import struct
import heapq

import pygame
from pygame._sdl2.video import Window

from ..client import UdpClient
from ..timer import Timer
from ..connection import RetryMode
from ..serializable import Serializable, SerializableEnum

# pylon

def sign(x):
    return -1 if x < 0 else 1

## PyGame Engine

class Namespace(object):
    def __init__(self):
        super(Namespace, self).__init__()

        self.screen_width = 960
        self.screen_height = 540

        # client state:
        self.client = None
        self.FPS = 60
        self.screen = None
        self.window_mode = "windowed"
        self.window_size = (0,0)
        self.window = None
        self.screen = None

        self.frame_counter = 1
        self.global_timer = 0
        self.host = "localhost"
        self.port = 1474

g = Namespace()

class GameScene(object):
    def __init__(self):
        super(GameScene, self).__init__()

    def handle_message(self, msg):
        pass

    def handle_event(self, evt):
        pass

    def paint(self, surface):
        """ called once for every frame to paint the game state to the given surface

        """
        pass

    def paintOverlay(self, window, scale):
        """ called once for every frame for painting after the game surface has been
        resized to the display size.

        This can be used for drawing smooth fonts by drawing the fonts to the game
        surface after resizing the surface for full screen mode.

        :param window: the surface to paint
        :param scale: the scale factor relative the the surface passed in to paint()
        """
        pass

    def update(self, delta_t):
        """ called once for every frame to update the game state

        :param delta_t: the amount of time that has elapsed since the last call.
        This value is stable and will be 1/FPS.
        """

    def resizeEvent(self, surface, scale):
        """ called when the window is resized

        :param surface:
        """
        pass

class NoScene(GameScene):
    def __init__(self):
        super(NoScene, self).__init__()
        self.exec_info = sys.exc_info()
        font = pygame.font.SysFont('arial', 72)
        self.text = font.render("No Scene", True, (255, 255, 255))

        if g.client and g.client.connected():
            g.client.disconnect()

    def paint(self, surface):

        surface.fill((0,100,0))
        x = g.screen_width//2 - self.text.get_width()//2
        y = g.screen_height//2 - self.text.get_height()//2
        surface.blit(self.text, (x,y))

class ExceptionScene(GameScene):
    def __init__(self):
        super(ExceptionScene, self).__init__()
        self.exec_info = sys.exc_info()
        font = pygame.font.SysFont('arial', 72)
        self.text = font.render("Error", True, (255, 255, 255))

        if g.client and g.client.connected():
            g.client.disconnect()

    def paint(self, surface):

        surface.fill((0,0,170))
        x = g.screen_width//2 - self.text.get_width()//2
        y = g.screen_height//2 - self.text.get_height()//2
        surface.blit(self.text, (x,y))

class ConnectingScene(GameScene):
    def __init__(self, callback=None):
        """
        :param callback: A function that is called after successfully connecting
            or timing out. It should accept a single boolean indicating whether
            connection was successful.

        """
        super(ConnectingScene, self).__init__()

        g.client.connect((g.host, g.port), callback=self.onConnect)

        self.font = pygame.font.SysFont('arial', 72)
        self.text = self.font.render("Connecting...", True, (255, 255, 255))

        self.callback = callback

    def onConnect(self, connected):
        print("client connected: %s" % connected)

        # TODO: need to route back to previous scene
        if not connected:
            self.text = self.font.render("Unable to Connect", True, (255, 255, 255))

        if self.callback:
            self.callback(connected)

    def handle_message(self, msg):
        pass

    def handle_event(self, evt):
        pass

    def paint(self, surface):
        surface.fill((0,0,0))
        x = g.screen_width//2 - self.text.get_width()//2
        y = g.screen_height//2 - self.text.get_height()//2
        surface.blit(self.text, (x,y))

    def update(self, delta_t):

        if g.client.connected():
            g.next_scene = GameScenes.LOBBY

## Camera

class Surface(object):
    def __init__(self, surface):
        super(Surface, self).__init__()
        self.surface = surface

        self.fill = surface.fill
        self.blit = surface.blit
        self.get_width = surface.get_width
        self.get_height = surface.get_height

        setattr(self, "draw_rect"   , lambda *args, **kwargs: pygame.draw.rect(surface, *args, **kwargs))
        setattr(self, "draw_polygon", lambda *args, **kwargs: pygame.draw.polygon(surface, *args, **kwargs))
        setattr(self, "draw_circle" , lambda *args, **kwargs: pygame.draw.circle(surface, *args, **kwargs))
        setattr(self, "draw_ellipse", lambda *args, **kwargs: pygame.draw.ellipse(surface, *args, **kwargs))
        setattr(self, "draw_arc"    , lambda *args, **kwargs: pygame.draw.arc(surface, *args, **kwargs))
        setattr(self, "draw_line"   , lambda *args, **kwargs: pygame.draw.line(surface, *args, **kwargs))
        setattr(self, "draw_lines"  , lambda *args, **kwargs: pygame.draw.lines(surface, *args, **kwargs))
        setattr(self, "draw_aaline" , lambda *args, **kwargs: pygame.draw.aaline(surface, *args, **kwargs))
        setattr(self, "draw_aalines", lambda *args, **kwargs: pygame.draw.aalines(surface, *args, **kwargs))

class Camera(object):
    def __init__(self, surface, entity, map_rect, xmargin=None, ymargin=None):
        super(Camera, self).__init__()
        self.surface = surface
        self.entity = entity

        self.map_rect = map_rect

        self.x = 0 # camera top left corner within the map_rect
        self.y = 0

        if isinstance(xmargin, tuple):
            self.xmargin_left, self.xmargin_right = xmargin
        elif isinstance(xmargin, int):
            self.xmargin_left = self.xmargin_right = xmargin
        elif xmargin is None:
            self.xmargin_left = self.xmargin_right = None
        else:
            raise TypeError("unexpected type for xmargin %s(%s)" % (type(xmargin), xmargin))

        if isinstance(ymargin, tuple):
            self.ymargin_top, self.ymargin_bot = ymargin
        elif isinstance(ymargin, int):
            self.ymargin_top = self.ymargin_bot = ymargin
        elif ymargin is None:
            self.ymargin_top = self.ymargin_bot = None
        else:
            raise TypeError("unexpected type for ymargin %s(%s)" % (type(ymargin), ymargin))

    def get_width(self):
        return self.surface.get_width()

    def get_height(self):
        return self.surface.get_height()

    def blit(self, image, pt, area=None, special_flags=0):

        if isinstance(pt, pygame.Rect):
            x1, y1 = pt.topleft
        else:
            x1, y1 = pt

        x1 -= self.x
        y1 -= self.y

        self.surface.blit(image, (x1,y1), area=area, special_flags=special_flags)

    def draw_rect(self, color, rect, width=0, alpha=255, **kwargs):

        rect = rect.move(-self.x, -self.y)

        if alpha < 255:
            surf = pygame.Surface((rect.width, rect.height))
            surf.fill(color)
            surf.set_alpha(alpha)

            self.surface.blit(surf, rect.topleft)
        else:
            pygame.draw.rect(self.surface, color, rect, width, **kwargs)

    def draw_polygon(self, color, points, width=0):
        points = [(x-self.x, y-self.y) for x,y in points]
        pygame.draw.polygon(self.surface, color, points, width)

    def draw_circle(self, color, center, radius, *args, **kwargs):

        x1,y1 = center

        x1 -= self.x
        y1 -= self.y

        pygame.draw.circle(self.surface, color, (x1, y1), radius, *args, **kwargs)

    def draw_ellipse(self, color, rect, width=0):
        rect = rect.move(-self.x, -self.y)
        pygame.draw.circle(self.surface, color, rect, width)

    def draw_arc(self, color, rect, start_angle, stop_angle, width=1):
        rect = rect.move(-self.x, -self.y)
        pygame.draw.circle(self.surface, color, start_angle, stop_angle, width)

    def draw_line(self, color, p1, p2, width=1):

        x1, y1 = p1
        x2, y2 = p2

        x1 -= self.x
        y1 -= self.y

        x2 -= self.x
        y2 -= self.y

        pygame.draw.line(self.surface, color, (x1,y1), (x2,y2), width)

    def draw_lines(self, color, clsoed, points, width=1):
        points = [(x-self.x, y-self.y) for x,y in points]
        pygame.draw.lines(self.surface, color, closed, points, width)

    def draw_aaline(self, color, p1, p2, blend=1):

        x1, y1 = p1
        x2, y2 = p2

        x1 -= self.x
        y1 -= self.y

        x2 -= self.x
        y2 -= self.y

        pygame.draw.aaline(self.surface, color, (x1,y1), (x2,y2), blend)

    def draw_aalines(self, color, clsoed, points, blend=1):
        points = [(x-self.x, y-self.y) for x,y in points]
        pygame.draw.aalines(self.surface, color, closed, points, blend)

    def update(self, delta_t):

        if self.entity is not None:

            # update camera x
            x,y = self.entity.rect.center

            if self.xmargin_left is not None:
                tgt = self.x
                r1 = self.xmargin_left
                if x <= self.x + r1:
                    tgt = x - r1
                r2 = g.screen_width - self.xmargin_right
                if x >= self.x + r2:
                    tgt = x - r2
            else:
                tgt = x - self.map_rect.width//2

            self.x = min(max(0, tgt), self.map_rect.width - self.surface.get_width())

            # update camera y
            if self.ymargin_top is not None:
                tgt = self.y
                r1 = self.ymargin_top
                if y <= self.y + r1:
                    tgt = y - r1

                r2 = g.screen_height - self.ymargin_bot
                if y >= self.y + r2:
                    tgt = y - r2
            else:
                tgt = y - self.map_rect.height//2

            self.y = min(max(0, tgt), self.map_rect.height - self.surface.get_height())

    def paint(self, surface=None):

        if self.xmargin_left is not None:
            x1 = self.x + self.xmargin_left
            x2 = self.x + g.screen_width - self.xmargin_right

            self.draw_line((32,32,32), (x1, 0), (x1, g.map_height))
            self.draw_line((32,32,32), (x2, 0), (x2, g.map_height))

        if self.ymargin_top is not None:
            y1 = self.y + self.ymargin_top
            y2 = self.y + g.screen_height - self.ymargin_bot

            self.draw_line((32,32,32), (0, y1), (g.map_width, y1))
            self.draw_line((32,32,32), (0, y2), (g.map_width, y2))

## Engine

class Engine(object):
    def __init__(self):
        super(Engine, self).__init__()

        self.active = False
        self.scene = None
        self.screenshot_index = 0
        self.sdl_window = None

    def init(self, scene=None):

        pygame.init()
        pygame.font.init()
        pygame.display.init()
        pygame.joystick.init()

        if scene:
            self.scene = scene
        if not self.scene:
            self.scene = NoScene()

        infoObject = pygame.display.Info()
        w = infoObject.current_w
        h =infoObject.current_h
        self.resolution = (w, h)

        self.setWindowMode()

        g.client = UdpClient()

    def setScene(self, scene):
        self.scene = scene

    def setActive(self, active):
        self.active = active

    def setWindowMode(self):
        """
        the first time this is called the environment variables are
        used to suggest  how to display the window

        subsequent calls require changing the window to a bogus value
        before updating the sdl_window and changing the mode to the
        new correct value

        """

        if g.window_mode == "borderless":
            if self.sdl_window:
                g.window = pygame.display.set_mode((100, 100))
            os.environ['SDL_VIDEO_CENTERED'] = '1'
            os.environ['SDL_VIDEO_WINDOW_POS']='0, 0'
            if self.sdl_window:
                self.sdl_window.position = (0,0)
            g.window = pygame.display.set_mode(self.resolution, pygame.NOFRAME)
            g.window_size = self.resolution
            g.screen = pygame.Surface((g.screen_width, g.screen_height)).convert()

        elif g.window_mode == "fullscreen":
            if self.sdl_window:
                g.window = pygame.display.set_mode((100, 100))
            g.window = pygame.display.set_mode((0,0), pygame.FULLSCREEN|pygame.HWSURFACE|pygame.DOUBLEBUF)
            g.window_size = (g.window.get_width(), g.window.get_height())
            g.screen = pygame.Surface((g.screen_width, g.screen_height)).convert()
        else:
            scale = 1
            if g.window_mode == "windowed_2x":
                scale = 2
            if g.window_mode == "windowed_3x":
                scale = 3
            if self.sdl_window:
                g.window = pygame.display.set_mode((100, 100))
            x=self.resolution[0]//2 - scale*g.screen_width//2
            y=self.resolution[1]//2 - scale*g.screen_height//2
            os.environ['SDL_VIDEO_WINDOW_POS']='%d, %d' % (x,y)
            if self.sdl_window:
                self.sdl_window.position = (x, y)
            g.window = pygame.display.set_mode((scale*g.screen_width, scale*g.screen_height))
            g.window_size = None
            if scale != 1:
                g.screen = pygame.Surface((g.screen_width, g.screen_height)).convert()
                g.window_size = (g.window.get_width(), g.window.get_height())
            else:
                g.screen = g.window

        print(g.window, g.screen)

        #if g.window is not g.screen:
        #    g.screen = Surface(g.screen)
        #    g.window = Surface(g.window)
        #else:
        #    g.window = g.screen = Surface(g.screen)

        g.window_scale = (g.window.get_width()/g.screen.get_width(),
                          g.window.get_height()/g.screen.get_height())

        if self.sdl_window is None:
            self.sdl_window = Window.from_display_module()

        print("SDL_VIDEO_WINDOW_POS: %s" % os.environ.get('SDL_VIDEO_WINDOW_POS'))
        print("SDL_VIDEO_CENTERED: %s" % os.environ.get('SDL_VIDEO_CENTERED'))
        print(g.window_scale)

        self.scene.resizeEvent(g.screen, g.window_scale)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.setActive(False)

        if event.type == pygame.KEYUP:
            if event.key == pygame.K_ESCAPE:
                self.setActive(False)

            if event.key == pygame.K_F1:
                g.window_mode = "borderless"
                self.setWindowMode()

            if event.key == pygame.K_F2:
                g.window_mode = "fullscreen"
                self.setWindowMode()

            if event.key == pygame.K_F3:
                g.window_mode = "windowed"
                self.setWindowMode()

            if event.key == pygame.K_F4:
                g.window_mode = "windowed_2x"
                self.setWindowMode()

            if event.key == pygame.K_F5:
                g.window_mode = "windowed_3x"
                self.setWindowMode()

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

        self.scene.handle_event(event)

    def run(self):

        g.clock = pygame.time.Clock()

        self.active = True

        accumulator = 0.0
        update_step = 1 / g.FPS

        error = False

        while self.active:

            try:

                if not error:
                    self.beforeFrame()

                if self.scene is None:
                    self.scene = NoScene()

                dt = g.clock.tick(g.FPS) / 1000
                accumulator += dt
                g.frame_counter += 1
                g.global_timer += dt

                # handle events
                for event in pygame.event.get():
                    if self.handle_event(event):
                        continue

                # send/recv network data
                g.client.update()
                for seqnum, msg in g.client.getMessages():
                    self.scene.handle_message(Serializable.loadb(msg))

                # update game state
                # use a constant delta
                while accumulator > update_step:
                    self.scene.update(update_step)
                    accumulator -= update_step

                # paint
                self.scene.paint(g.screen)

                if g.screen is not g.window:
                    s = g.screen.surface if isinstance(g.screen, Surface) else g.screen
                    g.window.blit(pygame.transform.smoothscale(s, g.window_size), (0,0))

                self.scene.paintOverlay(g.window, g.window_scale)

                pygame.display.flip()

                if not error:
                    self.afterFrame()

            except Exception as e:
                logging.exception("error")
                self.setScene(ExceptionScene())
                error = True

        pygame.quit()

        if g.client and g.client.connected():
            g.client.disconnect()
            g.client.waitForDisconnect()

    def beforeFrame(self):
        pass

    def afterFrame(self):
        pass

## Network Entities

class PhysicsState(Serializable):
    xpos: int = 0
    ypos: int = 0
    xdir: float = 0
    ydir: float = 0
    xaccum: int = 0
    xspeed: float = 0
    xaccel: float = 0
    yaccum: int = 0
    yspeed: float = 0
    yaccel: float = 0

class AnimationState(Serializable):
    aid: int = 0
    index: int = 0
    timer: float = 0

class EntityState(Serializable):


    physics: PhysicsState = None
    animation: AnimationState = None

class Physics2dComponent(object):
    def __init__(self, entity, map_rect=None, collision_group=None):
        super(Physics2dComponent, self).__init__()

        self.entity = entity
        self.group = collision_group or []

        self.xaccum = 0
        self.yaccum = 0
        self.xspeed = 0
        self.yspeed = 0
        self.xaccel = 0
        self.yaccel = 0

        self.direction = (0.0, 0.0)

        self.map_rect = map_rect

        self.on_collision_stop = False


        # allow moving along 45 degree slopes
        # requires collision masks two be set for both entities
        self.allow_diagonal = False

    def reset(self):
        self.xaccum = 0
        self.yaccum = 0
        self.xspeed = 0
        self.yspeed = 0
        self.xaccel = 0
        self.yaccel = 0

    def speed(self):
        return (self.xspeed**2 + self.yspeed**2)**0.5

    def paint(self, surface):
        pass

    def update(self, delta_t):

        self._move(delta_t, self.group)

    def _move(self, delta_t, entities):
        if self.entity.solid or self.entity.collide:
            tx = abs(self.xspeed) > 1e-3
            ty = abs(self.yspeed) > 1e-3

            if tx or ty:

                xcol = set()
                ycol = set()
                collisions = set()

                dx = self.xspeed*delta_t
                dy = self.yspeed*delta_t



                if tx:
                    xcol = self._move_x(entities, dx)
                    if xcol and self.on_collision_stop:
                        self.xspeed = 0
                        self.xaccum = 0
                    collisions |= xcol

                if ty:
                    ycol = self._move_y(entities, dy)
                    if ycol and self.on_collision_stop:
                        self.yspeed = 0
                        self.yaccum = 0
                    collisions |= ycol

                for ent in xcol|ycol:
                    nx = 0
                    if ent in xcol:
                        nx = -dx
                    ny = 0
                    if ent in ycol:
                        ny = -dy

                    s = (nx**2 + ny**2)**0.5
                    nx /= s
                    ny /= s

                    normal = pygame.math.Vector2(nx, ny)

                    self.entity.onCollide(ent, normal=normal)
        else:
            tx = abs(self.xspeed) > 1e-3
            ty = abs(self.yspeed) > 1e-3
            if tx or ty:
                self.xaccum += self.xspeed*delta_t
                self.xaccum, intg = math.modf(self.xaccum)
                self.entity.rect.x += intg

                self.yaccum += self.yspeed*delta_t
                self.yaccum, intg = math.modf(self.yaccum)
                self.entity.rect.y += intg

    def _move_norm(self, delta, edge1, edge2, other1, other2):

        #                 1         2
        #                 |<-self_->|
        #    |<-other->|       <-------
        #    1         2

        #            1         2
        #            |<-self_->|
        #    |<-other->|       <-----
        #    1         2
        #print((delta), edge1 ,other2, "|", edge2, other1)

        if delta < 0 and edge1 >= other2:
            delta = max(delta, other2 - edge1)
        elif delta < 0 and edge1 < other2:
            delta = edge1 - other2

        #    1         2
        #    |<-self_->|
        #                 |<-other->|
        #                 1         2

        #    1         2
        #    |<-self_->|
        #          |<-other->|
        #          1         2

        if delta > 0  and edge2 <= other1:
            delta = min(delta, other1 - edge2)
        elif delta > 0 and edge2 > other1:
            delta =  edge2 - other1

        return delta

    def _check_solid(self, collide_rect, entity):

        if entity.rect.colliderect(collide_rect):
            if self.entity.collision_mask and entity.collision_mask:
                p1 = collide_rect.topleft
                p2 = entity.rect.topleft
                offset_x = p1[0] - p2[0]
                offset_y = p1[1] - p2[1]
                overlap = entity.collision_mask.overlap(self.entity.collision_mask, (offset_x, offset_y))
                return bool(overlap)
            return True
        return False

    def _move_test(self, rect, collide_rect, collisions, intg, east_west, entity):
        """
        test the current and next position
        don't collide if the entity already overlaps with the solid object
        this allows the entity to move out to a non solid area near by
        without further walking through other solid objects
        """

        #if not self.entity.solid:
        #    return intg

        other_rect = entity.rect

        if self.entity.collision_mask and entity.collision_mask:

            if other_rect.colliderect(collide_rect):

                # if the new position collides
                p1 = collide_rect.topleft
                p2 = entity.rect.topleft
                offset_x = p1[0] - p2[0]
                offset_y = p1[1] - p2[1]
                overlap1 = entity.collision_mask.overlap(self.entity.collision_mask, (offset_x, offset_y))

                # if the current position does not collide
                p1 = rect.topleft
                p2 = entity.rect.topleft
                offset_x = p1[0] - p2[0]
                offset_y = p1[1] - p2[1]
                overlap2 = entity.collision_mask.overlap(self.entity.collision_mask, (offset_x, offset_y))

                if overlap1 and not overlap2:
                    #self.overlap_mask = entity.collision_mask.overlap_mask(self.collision_mask, (offset_x, offset_y))
                    #self.overlap_overlap = (offset_x, offset_y)
                    collisions.add(entity)
                    intg = 0
        else:

            overlap1 = other_rect.colliderect(collide_rect)
            overlap2 = other_rect.colliderect(rect)
            if overlap1 and not overlap2:

                collisions.add(entity)

                if east_west:
                    intg = self._move_norm(intg, rect.left, rect.right, other_rect.left, other_rect.right)
                else:
                    intg = self._move_norm(intg, rect.top, rect.bottom, other_rect.top, other_rect.bottom)

        return intg

    def _move_x(self, entities, dx):
        """
            returns true if a collision occurred, using self.xspeed the direction
            of the collision can be determined. e.g. for calculating a bounce
        """

        self.xaccum += dx
        self.xaccum, intg = math.modf(self.xaccum)
        rect = self.entity.rect
        collide_rect = rect.move(intg, 0)

        if self.allow_diagonal:
            intg2 = round(intg*.7071)
            collide_rectR = rect.move(intg2, +abs(intg2))
            collide_rectL = rect.move(intg2, -abs(intg2))
        dy = 0

        collisions = set()

        if intg == 0:
            return collisions

        for entity in entities:
            if entity is self.entity:
                continue

            if  entity.solid or (self.entity.collide and entity.collide):

                intg = self._move_test(rect, collide_rect, collisions, intg, True, entity)

        if self.allow_diagonal and intg == 0 and intg2 != 0:

            cR = None
            for entity in entities:
                cR = self._check_solid(collide_rectR, entity)
                if cR:
                    break

            cL = None
            for entity in entities:
                cL = self._check_solid(collide_rectL, entity)
                if cL:
                    break

            if not cR and cL:
                dy = +abs(intg2)
                intg = intg2
            elif not cL and cR:
                dy = -abs(intg2)
                intg = intg2


        if collisions:
            self.overlap_mask=None

        self.entity.rect.x += intg
        self.entity.rect.y += dy

        return collisions

    def _move_y(self, entities, dy):
        """
            returns true if a collision occurred, using self.xspeed the direction
            of the collision can be determined. e.g. for calculating a bounce
        """

        self.yaccum += dy
        self.yaccum, intg = math.modf(self.yaccum)
        intg = int(intg)
        rect = self.entity.rect
        collide_rect = rect.move(0, intg)


        if self.allow_diagonal:
            intg2 = round(intg*.7071)
            collide_rectR = rect.move(+abs(intg2), intg2)
            collide_rectL = rect.move(-abs(intg2), intg2)
        dx = 0

        collisions = set()

        if intg == 0:
            return collisions

        for entity in entities:
            if entity is self:
                continue

            if entity.solid or (self.entity.collide and entity.collide):

                intg = self._move_test(rect, collide_rect, collisions, intg, False, entity)


        if self.allow_diagonal and intg == 0 and intg2 != 0:

            cR = None
            for entity in entities:
                cR = self._check_solid(collide_rectR, entity)
                if cR:
                    break

            cL = None
            for entity in entities:
                cL = self._check_solid(collide_rectL, entity)
                if cL:
                    break

            if not cR and cL:
                dx = +abs(intg2)
                intg = intg2
            elif not cL and cR:
                dx = -abs(intg2)
                intg = intg2

        if collisions:
            self.overlap_mask=None

        self.entity.rect.y += intg
        self.entity.rect.x += dx


        return collisions

    def getState(self):

        return PhysicsState(
            xpos=self.entity.rect.x,
            ypos=self.entity.rect.y,
            xdir=self.direction[0],
            ydir=self.direction[1],
            xspeed=self.xspeed,
            xaccum=self.xaccum,
            xaccel=self.xaccel,
            yspeed=self.yspeed,
            yaccum=self.yaccum,
            yaccel=self.yaccel,
        )

    def setState(self, state):

        # TODO: add a tolerance check to setting the x/y position
        #       if the new position is off by a few pixels don't
        #       bother updating. this may need to be implemented in
        #       in the remote controller?

        self.entity.rect.x = state.xpos
        self.entity.rect.y = state.ypos

        self.direction = (state.xdir, state.ydir)

        self.xspeed = state.xspeed
        self.yspeed = state.yspeed

        self.xaccel = state.xaccel
        self.yaccel = state.yaccel

        self.xaccum= state.xaccum
        self.yaccum= state.yaccum

    def interpolateState(self, state1, state2, p):

        state = PhysicsState()

        # TODO: round to nearest instead of rounding down
        state.xpos   = state1.xpos * (1-p) + state2.xpos * p
        state.ypos   = state1.ypos * (1-p) + state2.ypos * p
        state.xspeed = state1.xspeed * (1-p) + state2.xspeed * p
        state.yspeed = state1.yspeed * (1-p) + state2.yspeed * p
        state.xaccel = state1.xaccel * (1-p) + state2.xaccel * p
        state.yaccel = state1.yaccel * (1-p) + state2.yaccel * p

        return state

    def setDirection(self, vector):
        self.direction = vector

    def addImpulse(self, dx, dy):

        self.xspeed += dx
        self.yspeed += dy

class PlatformPhysics2dComponent(Physics2dComponent):
    def __init__(self, entity, map_rect=None, collision_group=None):
        super(PlatformPhysics2dComponent, self).__init__(entity, map_rect, collision_group)

        self.acceleration = 256
        self.max_hor_speed = 192
        self.max_ver_speed = 256
        self.friction = 0
        self.gravity = 512
        self.floor = g.screen_height

    def update(self, delta_t):
        # gravity = 512
        # yaccel = gravity
        # y = t*t*yaccel + t*y_speed_initial + y_initial
        # y_speed = 2*t*yaccel + y_speed_initial

        # apply acceleration to change the speed
        self.xspeed += delta_t * self.xaccel

        # include gravity with yaccel
        yaccel = self.yaccel
        if self.entity.rect.y < self.floor:
            yaccel += self.gravity
        self.yspeed += delta_t * yaccel

        # clamp the maximum horizontal speed
        if self.xspeed > self.max_hor_speed:
            self.xspeed = self.max_hor_speed
        elif self.xspeed < -self.max_hor_speed:
            self.xspeed = -self.max_hor_speed

        # clamp the maximum vertical speed
        if self.yspeed > self.max_ver_speed:
            self.yspeed = self.max_ver_speed
        elif self.yspeed < -self.max_ver_speed:
            self.yspeed = -self.max_ver_speed

        #if self.yspeed < 1e-3 and self.yspeed > -1e-3:
        #    self.yspeed = 0

        # apply friction to horizontal speed

        if self.xspeed > 1e-3:
            self.xspeed -= delta_t * self.friction
            if self.xspeed < 0:
                self.xspeed = 0
        elif self.xspeed < -1e-3:
            self.xspeed += delta_t * self.friction
            if self.xspeed > 0:
                self.xspeed = 0

        super().update(delta_t)

        # check the bounds of the room

        if self.map_rect:

            if self.entity.rect.x < self.map_rect.left:
                if self.xspeed < 0:
                    self.xspeed = 0
                    self.entity.rect.x = self.map_rect.left

            if self.entity.rect.x > self.map_rect.right - self.entity.rect.width:
                if self.xspeed > 0:
                    self.xspeed = 0
                    self.entity.rect.x = self.map_rect.right - self.entity.rect.width

            if self.entity.rect.y < self.map_rect.top:
                if self.yspeed < 0:
                    self.yspeed = 0
                    self.entity.rect.y = self.map_rect.top

            if self.entity.rect.y > self.map_rect.bottom - self.entity.rect.height:
                if self.yspeed > 0:
                    self.yspeed = 0
                    self.entity.rect.y = self.map_rect.bottom - self.entity.rect.height

    def setDirection(self, vector):

        self.xaccel = self.acceleration * vector[0]
        if vector[0] == 0:
            self.friction = 3 * self.max_hor_speed
        else:
            self.friction = 0

class AdventurePhysics2dComponent(Physics2dComponent):
    def __init__(self, entity, map_rect=None, collision_group=None):
        super(AdventurePhysics2dComponent, self).__init__(entity, map_rect, collision_group)

        self.max_speed = 192

    def update(self, delta_t):

        # apply acceleration to change the speed
        self.xspeed += delta_t * self.xaccel
        self.yspeed += delta_t * self.yaccel

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
                if self.xspeed < 0:
                    self.xspeed = 0
                    self.entity.rect.x = self.map_rect.left

            if self.entity.rect.x > self.map_rect.right - self.entity.rect.width:
                if self.xspeed > 0:
                    self.xspeed = 0
                    self.entity.rect.x = self.map_rect.right - self.entity.rect.width

            if self.entity.rect.y < self.map_rect.top:
                if self.yspeed < 0:
                    self.yspeed = 0
                    self.entity.rect.y = self.map_rect.top

            if self.entity.rect.y > self.map_rect.bottom - self.entity.rect.height:
                if self.yspeed > 0:
                    self.yspeed = 0
                    self.entity.rect.y = self.map_rect.bottom - self.entity.rect.height

    def setDirection(self, vector):

        self.xspeed = self.max_speed * vector[0]
        self.yspeed = self.max_speed * vector[1]

class AnimationComponent(object):
    def __init__(self, entity):
        super(AnimationComponent, self).__init__()

        # managed object
        self.entity = entity

        # user config
        self.images = []
        self.animated = False
        self.offset = None
        self.fps = 4 # frames per second to play the animation
        self.loop = True # whether to loop the animation
        self.onend = None # callback for the end of the final frame in the animation sequence
        self.onframe = None # callback for the start of each frame. fn(i) => None
        self.interuptable = True
        self.transform = None # callback to transform frame before painting. fn(i, img) => img

        # animation state
        self.index = 0
        self.timer = 0
        self._unit = 1.0/self.fps

        # network config
        self.registry = {}
        self._nextid = 1
        self._current_aid = -1

        self.debug = False

    def register(self, images=None, animated=None, offset=None, fps=4, loop=True, onend=None, onframe=None, interuptable=True, transform=None):

        aid = self._nextid
        self._nextid += 1

        self.registry[aid] = {
            "images": images,
            "animated": animated,
            "offset": offset,
            "fps": fps,
            "loop": loop,
            "onend": onend,
            "onframe": onframe,
            "interuptable": interuptable,
            "transform": transform
        }

        return aid

    @property
    def finished(self):
        """ return true if a non looping animation has completed """
        return not self.loop and self.index == len(self.images)

    def setAnimationById(self, aid):

        if self._current_aid != aid:
            if not self.interuptable and not self.finished:
                return False
            self.setAnimation(**self.registry[aid])
            self._current_aid = aid
            return True
        return False

    def clear(self):
        self.images = []
        self.animated = False
        self.offset = None

    def setAnimation(self, images=None, animated=None, offset=None, fps=4, loop=True, onend=None, onframe=None, interuptable=True, transform=None):

        self.images = images or []

        if animated is None:
            self.animated = len(self.images) > 1
        else:
            self.animated = animated

        self.offset = offset
        self.loop = loop
        self.index = 0
        self.timer = 0
        self.onend = onend
        self.onframe = onframe
        self.fps = fps
        self._unit = 1.0/fps
        self.interuptable = interuptable
        self.transform = transform

        if self.onframe:
            self.onframe(self.index)

    def paint(self, surface):
        """
        paint the current animation

        if the entities visible flag is false, nothing will be drawn

        if a transform is set, the transform function can change the
        image that will be drawn

        the image is drawn at the entities top left corver with an
        optional offset
        """

        if self.entity.visible and self.index < len(self.images):
            image = self.images[self.index]

            if self.transform:
                image = self.transform(self.index, image)

            x, y = self.entity.rect.topleft
            if self.offset:
                x += self.offset[0]
                y += self.offset[1]

            surface.blit(image, (x, y))

    def update(self, delta_t):
        if self.animated and self.images:
            self.timer += delta_t
            if self.timer > self._unit:

                N = len(self.images)

                if self.index < N:
                    self.index += 1

                if self.index < N and self.onframe:
                    self.onframe(self.index)

                if self.index == N:
                    if self.onend:
                        self.onend()
                    if self.loop:
                        self.index = 0
                    else:
                        self.index = N - 1

                self.timer -= self._unit

    def getState(self):
        return AnimationState(
            aid=self._current_aid,
            index=self.index,
            timer=self.timer
        )

    def setState(self, state):
        if state.aid in self.registry:

            x = self.setAnimationById(state.aid)
            if self.debug:
                print(x, self.index)

    def interpolateState(self, state1, state2, p):

        return state1

class Entity(object):
    def __init__(self, rect=None):
        super(Entity, self).__init__()

        if rect is None:
            rect = pygame.Rect(0,0,0,0)

        self.rect = rect
        self.collision_mask = None

        # ECS properties
        self.layer=0
        self.destroy = False
        self.solid = True
        self.collide = True
        self.visible = True
        self.requires_update = True

        self.netid = 0 # unique network id
        self.controller = None # Input Controller owning this entity

        # components:
        self.physics = None
        self.animation = None

    def onCollide(self, ent, normal=None):
        """ called by the physics component on a collision with an entity
        """
        pass

    def getState(self):
        """ get the current state of this entity

        reimplement this method to support network synchronization.

        At a minimum the state must have a 'clock' member variable. The
        clock must be monotonic (strictly increasing) count of frames.

        """
        return None

    def setState(self, state):
        """ set the current state of this entity

        reimplement this method to support network synchronization.
        """
        raise NotImplementedError()

    def interpolateState(self, state1, state2, p):
        """ blend two states together

        reimplement this method to support network synchronization.

        :param state1: the initial state, acting as the starting point
        :param state2: the target state
        :param p: value between zero and one representing the amount of blending.

        a value of p=0 means to return state1, while a value of p=1 means
        to returns state2.  values between 0 and 1 should blend the states
        together.

        Note: the clock value, if set, will be ignored.

        """
        raise NotImplementedError()

    def update(self, delta_t):
        pass

    def paint(self, surface):
        pass

## User Input

class Direction(SerializableEnum):
    NONE   = 0

    UP     = 1
    RIGHT  = 2
    DOWN   = 4
    LEFT   = 8

    # unions for direction combinations
    UPRIGHT  = UP|RIGHT
    DOWNRIGHT  = DOWN|RIGHT
    UPLEFT  = UP|LEFT
    DOWNLEFT  = DOWN|LEFT

    RDL = RIGHT|DOWN|LEFT
    UDL = UP|DOWN|LEFT
    URL = UP|RIGHT|LEFT
    URD = UP|RIGHT|DOWN

    # masks for checking directions
    UPDOWN = UP|DOWN
    LEFTRIGHT = LEFT|RIGHT
    ALL = UP|DOWN|LEFT|RIGHT

    def __and__(self, other):
        return Direction(self.value&other.value)

    def __or__(self, other):
        return Direction(self.value|other.value)

    def __xor__(self, other):
        return Direction(self.value^other.value)

    def vector(self):

        x = 0
        y = 0

        if self.value&0x1:
            y = -1

        if self.value&0x4:
            if y != 0:
                raise ValueError("%s" % self)
            y = 1

        if self.value&0x2:
            x = 1

        if self.value&0x8:
            if x != 0:
                raise ValueError("%s" % self)
            x = -1

        return (x, y)

    @staticmethod
    def fromVector(vector):

        value = 0

        if vector[0] > 0:
            value |= 0x2
        elif vector[0] < 0:
            value |= 0x8

        if vector[1] > 0:
            value |= 0x4
        elif vector[1] < 0:
            value |= 0x1

        return Direction(value)

class NetworkPlayerState(Serializable):
    token: int = 0
    clock: float = 0
    state: Serializable = None

class InputEventType(SerializableEnum):
    JOYSTICK1=1
    JOYSTICK2=2
    DIRECTION=3
    BUTTON_PRESS=4
    BUTTON_RELEASE=5

class InputEvent(Serializable):
    """
    kind specifies the type of event
    AXIS events have an angle
    DIRECTION events have a direction
    BUTTON events have a button index
    """
    kind : InputEventType = None
    dx: float = 0
    dy: float = 0
    direction: Direction = None
    button : int = 0

class KeyboardInputDevice(object):
    """

    TODO: add an option to repeat sending direction or button press events
    """

    def __init__(self, direction_config, button_config, callback=None):
        super(KeyboardInputDevice, self).__init__()

        self.direction_config = direction_config
        self.button_config = button_config

        self.callback = callback or (lambda event: None)

        # remember the order that direction keys are pressed and released
        # this fixes an issue where the user can press left and right
        # then release one of the directions. the result will be to
        # remember the button press in the other direction
        self.order = []
        self.buttons = {btn:False for btn in self.button_config.keys()}

        self.previous = None
        self.current = None

    def setCallback(self, callback):
        self.callback = callback

    def handle_event(self, evt):

        if evt.type == pygame.KEYDOWN:
            for direction, keys in self.direction_config.items():
                if evt.key in keys:
                    if direction not in self.order:
                        self.order.append(direction)

                        self.callback(InputEvent(
                            kind=InputEventType.DIRECTION,
                            direction=self._getDirection()))

            for btn, keys in self.button_config.items():
                if evt.key in keys:
                    self.buttons[btn] = True

                    self.callback(InputEvent(
                            kind=InputEventType.BUTTON_PRESS,
                            button=btn))

        if evt.type == pygame.KEYUP:
            for direction, keys in self.direction_config.items():
                if evt.key in keys:
                    if direction in self.order:
                        self.order.remove(direction)

                        self.callback(InputEvent(
                            kind=InputEventType.DIRECTION,
                            direction=self._getDirection()))

            for btn, keys in self.button_config.items():
                if evt.key in keys:
                    self.buttons[btn] = False

                    self.callback(InputEvent(
                            kind=InputEventType.BUTTON_RELEASE,
                            button=btn))

    def _getDirection(self):
        output = Direction.NONE
        for direction in self.order:
            if direction&Direction.UPDOWN and output&Direction.UPDOWN == Direction.NONE:
                output |= direction
            if direction&Direction.LEFTRIGHT and output&Direction.LEFTRIGHT == Direction.NONE:
                output |= direction

        return output

    def _getDirectionVector(self):
        dx = 0
        dy = 0
        for direction in self.order:
            if direction&Direction.UPDOWN and dy == 0:
                dy = -1 if direction&Direction.UP else 1
            if direction&Direction.LEFTRIGHT and dx == 0:
                dx = -1 if direction&Direction.LEFT else 1
        return (dx, dy)

class JoystickInputDevice(object):

    def __init__(self, instance_id, joy_config, button_config, callback=None):
        super(JoystickInputDevice, self).__init__()

        self.instance_id = instance_id
        self.joy_config = joy_config
        self.button_config = button_config

        self.callback = callback or (lambda event: None)

        # remember the order that direction keys are pressed and released
        # this fixes an issue where the user can press left and right
        # then release one of the directions. the result will be to
        # remember the button press in the other direction
        self.order = []
        self.buttons = {btn:False for btn in self.button_config.keys()}

        self.previous = None
        self.current = None

        self.deadzone = 0.2
        self.minimum_change = 1 # in degrees

        joy0 = [0,0]
        joy1 = [0,0]
        self.joysticks = {0: joy0, 1: joy0, 2: joy1, 3: joy1} # axis -> vector
        self.joyindex = {0:0, 1:1, 2:0, 3:1} # axis -> vector index
        self.joykind = {
            0:InputEventType.JOYSTICK1,
            1:InputEventType.JOYSTICK1,
            2:InputEventType.JOYSTICK2,
            3:InputEventType.JOYSTICK2
        }


        self.joy0_nomotion = False

        self.throttles = {5:0, 6:0}

    def setCallback(self, callback):
        self.callback = callback

    def handle_event(self, evt):
        if evt.type == pygame.JOYAXISMOTION:
            if evt.instance_id != self.instance_id:
                return

            if evt.axis in self.joysticks:

                idx = self.joyindex[evt.axis]
                vec1 = pygame.math.Vector2(*self.joysticks[evt.axis])
                tmp = list(self.joysticks[evt.axis])
                tmp[idx] = evt.value
                vec2 = pygame.math.Vector2(*tmp)

                if vec2.magnitude() > self.deadzone:

                    d_angle = abs(vec1.angle_to(vec2))
                    if d_angle > self.minimum_change:
                        #print(vec2.x-vec1.x, vec2.y-vec1.y)
                        #print(self.joykind[evt.axis], vec2.magnitude(), "angle", vec1.angle_to(vec2), vec2.angle_to(pygame.math.Vector2(1,0)))
                        self.joysticks[evt.axis][idx] = evt.value
                        dx, dy = self.joysticks[evt.axis]
                        self.callback(InputEvent(
                            kind=self.joykind[evt.axis],
                            dx=dx,
                            dy=dy))

                        self.joy0_nomotion = True
                elif self.joy0_nomotion:
                    #print(self.joykind[evt.axis], "dead")
                    self.joysticks[evt.axis][idx] = evt.value
                    self.callback(InputEvent(
                        kind=self.joykind[evt.axis],
                        dx=0,
                        dy=0))
                    self.joy0_nomotion = False

            elif evt.axis in self.throttles:
                if evt.value > 0 :
                    self.callback(InputEvent(
                        kind=InputEventType.BUTTON_PRESS,
                        button=-1))
                else:
                    self.callback(InputEvent(
                        kind=InputEventType.BUTTON_RELEASE,
                        button=-1))

        elif evt.type == pygame.JOYBALLMOTION:
            if evt.instance_id != self.instance_id:
                return
            # not supported
        elif evt.type == pygame.JOYBUTTONDOWN:

            if evt.instance_id != self.instance_id:
                return
            self.callback(InputEvent(
                kind=InputEventType.BUTTON_PRESS,
                button=evt.button))
        elif evt.type == pygame.JOYBUTTONUP:
            if evt.instance_id != self.instance_id:
                return
            self.callback(InputEvent(
                kind=InputEventType.BUTTON_RELEASE,
                button=evt.button))

        elif evt.type == pygame.JOYHATMOTION:
            if evt.instance_id != self.instance_id:
                return
            if evt.hat == 0:
                dx, dy = evt.value
                self.callback(InputEvent(
                kind=InputEventType.DIRECTION,
                direction=Direction.fromVector((dx, -dy))))

class MultiInputDevice(object):
    def __init__(self, *devices, callback=None):
        super(MultiInputDevice, self).__init__()
        self.devices = devices

        self.callback = callback

        for dev in self.devices:
            dev.callback = self.onUserInput

    def handle_event(self, evt):
        for dev in self.devices:
            dev.handle_event(evt)

    def onUserInput(self, evt):

        if self.callback:
            self.callback(evt)

class InputController(object):
    """
    The update interval controls how often a [NetworkPlayerState](#large_blue_diamond-networkplayerstate) event
    is sent to the server. The server should send this event back to all other clients, so that
    it can be processed by the [RemoteInputController](#large_blue_diamond-remoteinputcontroller)

    TODO: add an option to send input events to the server
    """
    def __init__(self, input_device, entity, client=None, input_delay=5, update_interval=0.1):
        """
        :param input_device: A keyboard or joystick input device
        :param entity: The entity to pass input events to
        :param client: the UdP client to use for sending information to the server
        :param input_delay: The number of frames to delay user input before applying to the entity
        :param update_interval: send the entity state to the serveral at this interval, default 100ms
        """
        super(InputController, self).__init__()

        self.entity = entity
        self.client = client
        if self.client:
            self.token = self.client.token()
        else:
            self.token = 0

        if input_device:
            self.input_device = input_device
            self.input_device.callback = self.onUserInput

        self.input_delay = input_delay
        self.event_queue = [[] for i in range(self.input_delay+1)]

        self.update_timer = Timer(update_interval, self.onUpdateTimeout)

        self.entity.requires_update = True
        self.entity.controller = self

    def onUserInput(self, event):
        self.event_queue[self.input_delay].append(event)
        #if self.client and self.client.connected():
        #    self.client.send(event.dumpb(), retry=RetryMode.NONE)
        return

    def handle_event(self, evt):
        self.input_device.handle_event(evt)

    def onUpdateTimeout(self):

        self.sendState()

    def update(self, delta_t):

        #if self.client:
        self.update_timer.update(delta_t)

        # process inputs after a delay of 100 ms
        if self.event_queue[0]:
            for event in self.event_queue[0]:
                self.entity.onUserInput(event)
        self.event_queue.pop(0)
        self.event_queue.append([])

    def sendState(self):
        state = self.entity.getState()

        netstate = NetworkPlayerState(
            token=self.token, clock=g.global_timer, state=state)

        # send the message with retry disabled
        # if the update is not received, there will be a new message
        # to take its place.
        if self.client and self.client.connected():
            self.client.send(netstate.dumpb(), retry=RetryMode.NONE)

class PriorityQueue(object):
    """ A priority queue which sorts items in ascending order
    """
    def __init__(self):
        super(PriorityQueue, self).__init__()
        self._heap = []
        self._index = 0

    def push(self, priority, entry):
        heapq.heappush(self._heap, (priority, self._index, entry))
        self._index += 1

    def peak(self):
        return self._heap[0][-1]

    def pop(self):
        return heapq.heappop(self._heap)[-1]

    def __len__(self):
        return len(self._heap)

class RemoteInputController(object):
    def __init__(self, entity, input_delay=0.1):
        """
        """
        super(RemoteInputController, self).__init__()
        self.entity = entity
        self.tlast = 0

        self.input_clock = 0
        self.input_error = 0
        self.input_delay = input_delay # delay in seconds between receiving a message and applying it
        self.input_delay_max = 60
        self.state_queue = PriorityQueue()

        self.first_receive = False
        self.first_event = False

        self.previous_state = None
        self.previous_clock = 0

        self.entity.requires_update = False
        self.entity.controller = self

        self.clock_error_count = 0
        self.clock_error_count_max = 1

        self.timer = 0

    def receiveState(self, msg):

        if not self.first_receive:
            self.input_clock = msg.clock
            self.first_receive = True

        msg._r = time.time()
        msg._t = 0

        t = self.input_clock - self.input_delay
        if msg.clock >= t:
            self.state_queue.push(msg.clock, msg)
        else:
            # TODO: one dropped packet is not worth correcting
            # multiple in a row should increase the amount of correction
            print("drop", msg.clock, t, "error", t - msg.clock)
            self.input_clock += (t - msg.clock)/4

    def update(self, delta_t):

        self.input_clock += delta_t #  + self.input_error/g.FPS

        if len(self.state_queue):
            state = self.state_queue.peak()
            t = state.clock

            clock = self.input_clock - self.input_delay

            if t < clock:
                # TODO: fix clock drift by taking a small error correcting step
                #self.input_error = (clock - state.clock)
                # self.input_clock -= self.input_error/g.FPS
                #self.input_error = (clock - state.clock)
                #print("%9.6f %9.6f %.6f" % (clock, state.clock, self.input_error))

                self.state_queue.pop()
                # set state here may be causing a stutter?
                self.entity.setState(state.state)
                self.previous_state = state
                self.previous_clock = state.clock

            elif self.previous_state:
                # interpolate from the previous state to the next state
                t0 = self.previous_clock
                t1 = state.clock
                p = (clock - t0) / (t1 - t0)

                x1 = self.entity.rect.x

                self.entity.update(delta_t)
                current_state = self.entity.getState()
                state = self.entity.interpolateState(current_state, state.state, p)
                self.entity.setState(state)

        else:
            # predict from the previous state
            self.entity.update(delta_t)

class DummyClient(object):
    def __init__(self, ctrl, delay=6):
        super(DummyClient, self).__init__()

        self.ctrl = ctrl

        self.input_delay = delay
        self.input_queue = [[] for i in range(self.input_delay)]

        self.log = None

    def beginLogging(self, fpath):
        """ begin logging sent messages to a file
        """
        self.log = open(fpath, "wb")

    def stopLogging(self):
        """ end logging to a file
        """
        if self.log:
            self.log.close()
            self.log = None

    def connected(self):
        return True

    def disconnect(self):
        pass

    def token(self):
        return 0

    def send(self, msgdata, retry=RetryMode.NONE):
        self.input_queue[self.input_delay-1].append(msgdata)

        if self.log:
            self.log.write(struct.pack("<bLL", 1, len(msgdata), g.frame_counter))
            self.log.write(msgdata)
            self.log.flush()


    def update(self, delta_t):

        for msg in self.input_queue[0]:
            self.ctrl.receiveState(Serializable.loadb(msg))

        self.input_queue.pop(0)
        self.input_queue.append([])

    def getMessages(self):
        return []

## ECS

class EntityStore(object):
    ALL="idx_all"
    VISIBLE="idx_visible"
    SOLID="idx_solid"
    UPDATE="idx_update"
    DESTROY="idx_destroy"

    def __init__(self):
        super(EntityStore, self).__init__()
        self.entities = {} # eid => entity
        self.indicies = {}

        self.createIndex(EntityStore.ALL, lambda ent: True)
        self.createIndex(EntityStore.VISIBLE, lambda ent: getattr(ent, "visible", False))
        self.createIndex(EntityStore.SOLID, lambda ent: getattr(ent, "solid", False))
        self.createIndex(EntityStore.UPDATE, lambda ent: getattr(ent, "requires_update", False))
        self.createIndex(EntityStore.DESTROY, lambda ent: getattr(ent, "destroy", False))

        self._nextid = 0x40000000

        self._mutated = 0


    def addEntity(self, ent, eid=None):

        if eid is None:
            eid = self._nextid
            self._nextid += 1

        self.entities[eid] = ent

        self._mutated += 1

    def createIndex(self, index_name, index_fn):
        self.indicies[index_name] = index_fn

    def getEntityById(self, eid):
        return self.entities.get(eid, None)

    def getEntitiesByComponent(self, index_name):

        if index_name not in self.indicies:
            raise KeyError("component `%s` not found" % index_name)

        fn = self.indicies[index_name]

        return [ent for ent in self.entities.values() if fn(ent)]

    def removeEntitiesByComponent(self, index_name):
        if index_name not in self.indicies:
            raise KeyError("component `%s` not found" % index_name)

        fn = self.indicies[index_name]

        result = []

        for eid in list(self.entities.keys()):
            ent = self.entities[eid]
            if fn(ent):
                result.append(ent)
                del self.entities[eid]

        self._mutated += 1

        return result

class EntityGroup(object):
    """

    TODO: provide an api to get entities that are *near* a given entity
          preferably building a cache once per frame for fast querying
    """
    def __init__(self, store, component):
        super(EntityGroup, self).__init__()
        self.store = store
        self.component = component
        self.cache = None

        self._mutated = store._mutated
        self._last_frame = -1

    def getEntities(self):

        # clear the cache only once per frame, on first access
        if self._last_frame < g.frame_counter:
            # clear cache only if the store was mutated
            if self._mutated != self.store._mutated:
                self.cache = None

        if self.cache is None:
            self.cache = self.store.getEntitiesByComponent(self.component)
            self._mutated = self.store._mutated
            self._last_frame = g.frame_counter

        return self.cache

    def __iter__(self):
        yield from self.getEntities()

# Events

class _EventSuppressor(object):
    def __init__(self, parent):
        super(_EventSuppressor, self).__init__()
        self.parent = parent

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.parent.suppress_events = set()

class EventQueue(object):
    def __init__(self):
        super(EventQueue, self).__init__()

        self.events = []
        self.suppress_events = set()

    def push(self, event):

        if event.type_id in self.suppress_events:
            print("drop event")
            return
        self.events.append(event)

    def getEvent(self):
        return self.events.pop(0)

    def __bool__(self):
        return bool(self.events)

    def suppress(self, *args):

        self.suppress_events = set()
        for arg in args:
            if isinstance(arg, (Event, EventType)):
                self.suppress_events.add(arg.type_id)
            elif isinstance(arg, int):
                self.suppress_events.add(arg)
            else:
                raise TypeError(str(type(arg)))


        return _EventSuppressor(self)

class EventType(type):
    next_type_id = 128
    types_by_name = {}
    types_by_id = {}
    def __new__(metacls, name, bases, namespace):
        if name in EventType.types_by_name:
            raise ValueError(name)

        cls = super().__new__(metacls, name, bases, namespace)

        cls.type_id = EventType.next_type_id
        EventType.next_type_id += 1

        EventType.types_by_name[name] = cls
        EventType.types_by_id[cls.type_id] = cls

        return cls

class Event(object, metaclass=EventType):
    pass