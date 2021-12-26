#! cd .. && python -m demo.pong_client

import os
import sys
import logging
import math
import random
import time

from PIL import Image

from enum import Enum

import pygame

from . import pong_common as common
from .pong_common import g

from mpgameserver import Serializable, EllipticCurvePublicKey, UdpClient, \
    Timer, LineGraph, RetryMode

class Scenes(Enum):
    ERROR = 1
    HOME = 2
    CONNECTING = 3
    LOBBY = 4
    GAME = 5

class Scene(object):
    def __init__(self):
        super(Scene, self).__init__()

    def handle_message(self, msg):
        pass

    def handle_event(self, evt):
        pass

    def paint(self):
        pass

    def update(self, delta_t):
        pass

class ConnectingScene(Scene):
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
            g.next_state = Scenes.LOBBY

class ExceptionScene(Scene):
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

class HomeScene(Scene):
    def __init__(self):
        super(HomeScene, self).__init__()

        self.surface_title = g.font_title.render('Pong', True, g.c_text)
        self.surface_name = g.font_score.render('User Name:', True, g.c_text)
        self.surface_host = g.font_score.render('Server:', True, g.c_text)
        self.surface_port = g.font_score.render('Port:', True, g.c_text)
        self.surface_connect = g.font_score.render('Connect', True, g.c_text)

        self.init_coords()

        self.active_ctrl = 1
        self.active_btn = False

        self.text_name = g.username
        self.text_addr = g.host
        self.text_port = str(g.port)

        self.timer_cursor = 0
        self.cursor_delta = 0.5
        self.cursor_display = False

    def init_coords(self):
        top = 48
        w = self.surface_title.get_width()
        h = self.surface_title.get_height()
        self.pt_title = (g.screen_width//2 - w//2, top)

        top += h + 32

        w = self.surface_name.get_width()
        h = self.surface_name.get_height()
        self.pt_name = (32, top)

        left = 32 + w + 16
        width = g.screen_width - 32 - left
        self.rect_input_name = pygame.Rect(left, top, width, h)

        top += h + 32
        w = self.surface_host.get_width()
        h = self.surface_host.get_height()
        self.pt_host = (32, top)

        left = 32 + w + 16
        width = 3*g.screen_width//4 - 32 - 48 - left
        self.rect_input_addr = pygame.Rect(left, top, width, h)

        self.pt_addr = (left, top)

        w = self.surface_port.get_width()
        h = self.surface_port.get_height()
        self.pt_port = (3*g.screen_width//4 - 48, top)

        left = 3*g.screen_width//4 + w - 48 + 16
        width = g.screen_width - 32 - left
        self.rect_input_port = pygame.Rect(left, top, width, h)

        top += h + 64

        w = self.surface_connect.get_width()
        h = self.surface_connect.get_height()
        left = g.screen_width//2 - w//2
        self.rect_btn = pygame.Rect(left-32, top-16, w+64, h+32)
        self.lines_btn_0 = [(left-32, top-16 + h+32), (left-32, top-16), (left-32 + w+64, top-16)]
        self.lines_btn_1 = [(left-32, top-16 + h+32), (left-32 + w+64, top-16 + h+32), (left-32 + w+64, top-16)]
        self.pt_btn = (left, top)

    def handle_event(self, evt):

        if evt.type == pygame.MOUSEBUTTONDOWN:
            pos = pygame.mouse.get_pos()

            if self.rect_input_name.collidepoint(pos):
                self.active_ctrl = 1

            if self.rect_input_addr.collidepoint(pos):
                self.active_ctrl = 2

            if self.rect_input_port.collidepoint(pos):
                self.active_ctrl = 3

            if self.rect_btn.collidepoint(pos):
                self.active_btn = True

        if evt.type == pygame.MOUSEBUTTONUP:
            pos = pygame.mouse.get_pos()

            if self.rect_btn.collidepoint(pos):
                g.host = self.text_addr
                g.port = int(self.text_port)
                g.username = self.text_name

                g.next_state = Scenes.CONNECTING

            self.active_btn = False

        elif evt.type == pygame.KEYDOWN:
            self.onKeyDown(evt)

    def onKeyDown(self, evt):
        keys = pygame.key.get_pressed()
        if evt.key == pygame.K_BACKSPACE:
            self.onKeyBackspace()
        elif evt.unicode:
            self.onKeyAppend(evt)

    def onKeyBackspace(self):
        if self.active_ctrl == 1:
            self.text_name = self.text_name[:-1]
        elif self.active_ctrl == 2:
            self.text_addr = self.text_addr[:-1]
        elif self.active_ctrl == 3:
            self.text_port = self.text_port[:-1]

    def onKeyAppend(self, evt):

        if self.active_ctrl == 1:
            if len(self.text_name) < 25:
                self.text_name += evt.unicode
        elif self.active_ctrl == 2:
            if len(self.text_addr) < 15:
                self.text_addr += evt.unicode
        elif self.active_ctrl == 3:
            if len(self.text_port) < 5 and len(evt.unicode) == 1:
                if 0x30 <= ord(evt.unicode) <= 0x39:
                    self.text_port += evt.unicode

    def paint(self):
        g.screen.fill((0, 0, 0))

        g.screen.blit(self.surface_title, self.pt_title)

        # paint the text input for user name

        g.screen.blit(self.surface_name, self.pt_name)
        c = g.c_input_bg_active if self.active_ctrl==1 else g.c_input_bg_inactive
        pygame.draw.rect(g.screen, c, self.rect_input_name)

        surface = g.font_score.render(self.text_name, True, g.c_text)
        g.screen.blit(surface, self.rect_input_name)

        if self.active_ctrl==1 and self.cursor_display:
            l, t, _, _ = self.rect_input_name
            pygame.draw.rect(g.screen, g.c_text, (l + surface.get_width()+4, t+8, 4, surface.get_height() - 16))

        # paint the text input for host

        g.screen.blit(self.surface_host, self.pt_host)
        c = g.c_input_bg_active if self.active_ctrl==2 else g.c_input_bg_inactive
        pygame.draw.rect(g.screen, c, self.rect_input_addr)

        surface = g.font_score.render(self.text_addr, True, g.c_text)
        g.screen.blit(surface, self.rect_input_addr)

        if self.active_ctrl==2 and self.cursor_display:
            l, t, _, _ = self.rect_input_addr
            pygame.draw.rect(g.screen, g.c_text, (l + surface.get_width()+4, t+8, 4, surface.get_height() - 16))

        # paint the text input for port
        g.screen.blit(self.surface_port, self.pt_port)
        c = g.c_input_bg_active if self.active_ctrl==3 else g.c_input_bg_inactive
        pygame.draw.rect(g.screen, c, self.rect_input_port)

        surface = g.font_score.render(self.text_port, True, g.c_text)
        g.screen.blit(surface, self.rect_input_port)

        if self.active_ctrl==3 and self.cursor_display:
            l, t, _, _ = self.rect_input_port
            pygame.draw.rect(g.screen, g.c_text, (l + surface.get_width()+4, t+8, 4, surface.get_height() - 16))

        # paint the connect button
        c2 = (200,200,200) if self.active_btn else ( 32, 32, 32)
        c1 = ( 32, 32, 32) if self.active_btn else (200,200,200)
        pygame.draw.rect(g.screen, g.c_input_bg_inactive, self.rect_btn, width=0)
        pygame.draw.lines(g.screen, c1, False, self.lines_btn_0, width=8)
        pygame.draw.lines(g.screen, c2, False, self.lines_btn_1, width=8)
        g.screen.blit(self.surface_connect, self.pt_btn)

    def update(self, delta_t):

        self.timer_cursor += delta_t

        if self.timer_cursor > self.cursor_delta:
            self.timer_cursor -= self.cursor_delta
            self.cursor_display = not self.cursor_display

class LobbyScene(object):

    def __init__(self):
        super(LobbyScene, self).__init__()

        font1 = pygame.font.SysFont('arial', 42)
        font2 = pygame.font.SysFont('arial', 16)

        self.surface_title  = font1.render('Lobby', True, g.c_text)
        self.surface_name   = font1.render('Room Name:', True, g.c_text)
        self.surface_create = font1.render('Create', True, g.c_text)
        self.surface_join   = font1.render('Join', True, g.c_text)
        self.surface_logout = font2.render('Log Out', True, g.c_text)

        self.surface_uparrow = pygame.Surface((32,32))
        self.surface_uparrow.fill(g.c_input_bg_inactive)
        points = [(0,32),(16,0),(32,32)]
        pygame.draw.lines(self.surface_uparrow, g.c_text, False, points, width=3)

        self.surface_dnarrow = pygame.Surface((32,32))
        self.surface_dnarrow.fill(g.c_input_bg_inactive)
        points = [(0,0),(16,32),(32,0)]
        pygame.draw.lines(self.surface_dnarrow, g.c_text, False, points, width=3)

        self.surface_mask = pygame.Surface((g.screen_width, g.screen_height))
        self.surface_mask.set_alpha(192)
        self.surface_mask.fill((0,0,0))

        self.init_coords()

        self.active_ctrl = 1
        self.active_btn = -1
        self.text_name = g.roomname

        self.timer_cursor = 0
        self.cursor_delta = 0.5
        self.cursor_display = False

        self.display_start_index = 0

        self.block_input = False
        self.block_message = ""
        self.block_message_count = 0
        self.timer_block = 0
        self.timer_block_anim = 0

        self.rooms = []

        msg = common.RoomList()
        g.client.send(msg.dumpb())

    def init_coords(self):

        top = 16
        w = self.surface_title.get_width()
        h = self.surface_title.get_height()
        self.pt_title = (g.screen_width//2 - w//2, top)

        top += h + 16

        w = self.surface_name.get_width()
        h = self.surface_name.get_height()
        self.pt_name = (32, top)

        left = 32 + w + 16
        width = g.screen_width - 32 - left - self.surface_create.get_width() - 32 - 16 - 32
        self.rect_input_name = pygame.Rect(left, top, width, h)

        left += width + 16 + 32
        w = self.surface_create.get_width()
        h = self.surface_create.get_height()
        self.rect_btn_create = pygame.Rect(left-16, top, w+32, h)
        self.lines_btn_create_0 = [(left-16, top + h), (left-16, top), (left-16 + w+32, top)]
        self.lines_btn_create_1 = [(left-16, top + h), (left-16 + w+32, top + h), (left-16 + w+32, top)]
        self.pt_btn_create = (left, top)

        top += h + 12

        self.lines_divider = [(64, top), (left-16, top), (g.screen_width - 64, top)]
        self.divider_width = 4

        left = 128
        top += self.divider_width + 12
        self.pt_room_list_start = (left, top)

        self.lst_join_buttons = []

        # the up arrow button
        l=32
        w = self.surface_uparrow.get_width()
        h = self.surface_uparrow.get_height()
        t = top + (self.surface_title.get_height() - h)//2
        self.btn_uparrow_rect = pygame.Rect(l, t, w, h)
        self.btn_uparrow_lines_0 = [(l, t + h), (l, t), (l + w, t)]
        self.btn_uparrow_lines_1 = [(l, t + h), (l + w, t + h), (l + w, t)]
        self.btn_uparrow_pt = (l, t)

        for i in range(4):

            attrs = lambda: None
            self.lst_join_buttons.append(attrs)

            w = self.surface_join.get_width()
            h = self.surface_join.get_height()
            l = g.screen_width - 96 - w - 32

            attrs.rect = pygame.Rect(l-16, top, w+32, h)
            attrs.lines_0 = [(l-16, top + h), (l-16, top), (l-16 + w+32, top)]
            attrs.lines_1 = [(l-16, top + h), (l-16 + w+32, top + h), (l-16 + w+32, top)]
            attrs.pt_name = (left, top)
            attrs.pt_button = (l, top)

            top += self.surface_join.get_height() + 16

        l=32
        top -= self.surface_join.get_height() + 16
        w = self.surface_uparrow.get_width()
        h = self.surface_uparrow.get_height()
        t = top + (self.surface_title.get_height() - h)//2
        self.btn_dnarrow_rect = pygame.Rect(l, t, w, h)
        self.btn_dnarrow_lines_0 = [(l, t + h), (l, t), (l + w, t)]
        self.btn_dnarrow_lines_1 = [(l, t + h), (l + w, t + h), (l + w, t)]
        self.btn_dnarrow_pt = (l, t)

        left = 32
        top = 32
        w = self.surface_logout.get_width()
        h = self.surface_logout.get_height()
        self.btn_logout_rect = pygame.Rect(left-16, top, w+32, h)
        self.btn_logout_lines_0 = [(left-16, top + h), (left-16, top), (left-16 + w+32, top)]
        self.btn_logout_lines_1 = [(left-16, top + h), (left-16 + w+32, top + h), (left-16 + w+32, top)]
        self.btn_logout_pt = (left, top)

    def handle_message(self, msg):

        if msg.type_id == common.RoomListReply.type_id:
            self.rooms = list(sorted(msg.rooms.items(), key=lambda x: x[1]))

            # TODO: fixme enqueue
            #if g.auto_join:
            #    for uid, name in self.rooms:
            #        if name == g.auto_join:
            #            g.client.enqueue(message.RoomJoinMessage(uid, g.username))

        if msg.type_id == common.RoomCreateReply.type_id:
            self.block_input = False
            g.player_id = 0
            g.next_state = Scenes.GAME

        if msg.type_id == common.RoomJoinReply.type_id:
            self.block_input = False
            if msg.room_id:
                g.player_id = 1
                g.next_state = Scenes.GAME

    def handle_event(self, evt):

        if self.block_input:
            return

        if evt.type == pygame.MOUSEBUTTONDOWN:
            self.onMouseButtonDown(evt)

        if evt.type == pygame.MOUSEBUTTONUP:
            self.onMouseButtonUp(evt)

        elif evt.type == pygame.KEYDOWN:
            self.onKeyDown(evt)

    def onKeyDown(self, evt):
        keys = pygame.key.get_pressed()
        if evt.key == pygame.K_BACKSPACE:
            self.onKeyBackspace()
        elif evt.unicode:
            self.onKeyAppend(evt)

    def onKeyBackspace(self):
        if self.active_ctrl == 1:
            self.text_name = self.text_name[:-1]

    def onKeyAppend(self, evt):

        if self.active_ctrl == 1:
            if len(self.text_name) < 12:
                self.text_name += evt.unicode

    def onMouseButtonDown(self, evt):
        pos = pygame.mouse.get_pos()

        if self.rect_input_name.collidepoint(pos):
            self.active_ctrl = 1

        if self.rect_btn_create.collidepoint(pos):
            self.active_btn = 0

        if self.btn_logout_rect.collidepoint(pos):
            self.active_btn = 1

        if self.btn_uparrow_rect.collidepoint(pos):
            self.active_btn = 2

        if self.btn_dnarrow_rect.collidepoint(pos):
            self.active_btn = 3

        for i, attr in enumerate(self.lst_join_buttons):
            if attr.rect.collidepoint(pos):
                self.active_btn = 3 + i
                break;

    def onMouseButtonUp(self, evt):
        pos = pygame.mouse.get_pos()

        if self.rect_btn_create.collidepoint(pos):
            self.block_input = True
            self.block_message = "Creating Room"
            self.timer_block = 0
            self.timer_block_anim = 0
            self.block_message_count = 0
            g.roomname = self.text_name
            # TODO: fixme enqueue
            g.client.send(common.RoomCreate(name=g.roomname).dumpb())

        if self.btn_logout_rect.collidepoint(pos):
            g.client.disconnect()
            g.next_state = Scenes.HOME

        for i, attr in enumerate(self.lst_join_buttons):

            index = self.display_start_index + i
            if index >= len(self.rooms):
                break;

            if attr.rect.collidepoint(pos):

                uid, _ = self.rooms[index]
                self.block_input = True
                self.block_message = "Joining Room"
                self.timer_block = 0
                self.timer_block_anim = 0
                self.block_message_count = 0

                # TODO: fixme enqueue
                g.client.send(common.RoomJoin(room_id=uid).dumpb())

        self.active_btn = -1

    def paint(self):
        g.screen.fill((0, 0, 0))

        g.screen.blit(self.surface_title, self.pt_title)

        # paint the input text box for room name
        g.screen.blit(self.surface_name, self.pt_name)
        c = g.c_input_bg_active if self.active_ctrl==1 else g.c_input_bg_inactive
        pygame.draw.rect(g.screen, c, self.rect_input_name)

        surface = g.font_score.render(self.text_name, True, g.c_text)
        g.screen.blit(surface, self.rect_input_name)

        if self.active_ctrl==1 and self.cursor_display:
            l, t, _, _ = self.rect_input_name
            pygame.draw.rect(g.screen, g.c_text, (l + surface.get_width()+4, t+8, 4, surface.get_height() - 16))

        # paint the create button
        c2 = (200,200,200) if self.active_btn==0 else ( 32, 32, 32)
        c1 = ( 32, 32, 32) if self.active_btn==0 else (200,200,200)
        pygame.draw.rect(g.screen, g.c_input_bg_inactive, self.rect_btn_create, width=0)
        pygame.draw.lines(g.screen, c1, False, self.lines_btn_create_0, width=8)
        pygame.draw.lines(g.screen, c2, False, self.lines_btn_create_1, width=8)
        g.screen.blit(self.surface_create, self.pt_btn_create)

        # paint the logout button
        c2 = (200,200,200) if self.active_btn==1 else ( 32, 32, 32)
        c1 = ( 32, 32, 32) if self.active_btn==1 else (200,200,200)
        pygame.draw.rect(g.screen, g.c_input_bg_inactive, self.btn_logout_rect, width=0)
        pygame.draw.lines(g.screen, c1, False, self.btn_logout_lines_0, width=8)
        pygame.draw.lines(g.screen, c2, False, self.btn_logout_lines_1, width=8)
        g.screen.blit(self.surface_logout, self.btn_logout_pt)

        # paint the up button
        c2 = (200,200,200) if self.active_btn==2 else ( 32, 32, 32)
        c1 = ( 32, 32, 32) if self.active_btn==2 else (200,200,200)
        pygame.draw.lines(g.screen, c1, False, self.btn_uparrow_lines_0, width=8)
        pygame.draw.lines(g.screen, c2, False, self.btn_uparrow_lines_1, width=8)
        g.screen.blit(self.surface_uparrow, self.btn_uparrow_pt)

        # paint the dn button
        c2 = (200,200,200) if self.active_btn==3 else ( 32, 32, 32)
        c1 = ( 32, 32, 32) if self.active_btn==3 else (200,200,200)
        pygame.draw.lines(g.screen, c1, False, self.btn_dnarrow_lines_0, width=8)
        pygame.draw.lines(g.screen, c2, False, self.btn_dnarrow_lines_1, width=8)
        g.screen.blit(self.surface_dnarrow, self.btn_dnarrow_pt)

        # paint a separator between create room and select room
        pygame.draw.lines(g.screen, g.c_input_bg_inactive, False, self.lines_divider, width=self.divider_width)

        # paint the rooms that can be joined:

        left, top = self.pt_room_list_start

        for i, attr in enumerate(self.lst_join_buttons):

            index = self.display_start_index + i
            if index >= len(self.rooms):
                left, top = attr.pt_name
                surface = g.font_score.render("--", True, g.c_text)
                g.screen.blit(surface, (left, top))
                continue;

            # print the number of the index
            left, top = attr.pt_name
            surface = g.font_score.render("%2d." % (1 + index), True, g.c_text)
            g.screen.blit(surface, (left, top))

            left += 64 + 16
            surface = g.font_score.render(self.rooms[index][1], True, g.c_text)
            g.screen.blit(surface, (left, top))

            c2 = (200,200,200) if self.active_btn==4+i else ( 32, 32, 32)
            c1 = ( 32, 32, 32) if self.active_btn==4+i else (200,200,200)
            pygame.draw.rect(g.screen, g.c_input_bg_inactive, attr.rect, width=0)
            pygame.draw.lines(g.screen, c1, False, attr.lines_0, width=8)
            pygame.draw.lines(g.screen, c2, False, attr.lines_1, width=8)
            g.screen.blit(self.surface_join, attr.pt_button)


            top += surface.get_height() + 16

        if self.block_input:
            g.screen.blit(self.surface_mask, (0, 0))

            if self.block_message:
                s1 = g.font_score.render(self.block_message, True, g.c_text)
                s2 = g.font_score.render("." * self.block_message_count, True, g.c_text)
                w = s1.get_width()//2
                h = s1.get_height()//2
                g.screen.blit(s1, (g.screen_width//2 - w, g.screen_height//2 - h))
                g.screen.blit(s2, (g.screen_width//2 + w, g.screen_height//2 - h))

    def update(self, delta_t):

        if self.block_input:

            # 5 second timeout before re-enabling the screen
            self.timer_block += delta_t
            if self.timer_block > 5.0:
                self.block_input = False

            self.timer_block_anim += delta_t
            if self.timer_block_anim > .33:
                self.timer_block_anim -= .33
                self.block_message_count = (self.block_message_count + 1) % 4

            return

        self.timer_cursor += delta_t

        if self.timer_cursor > self.cursor_delta:
            self.timer_cursor -= self.cursor_delta
            self.cursor_display = not self.cursor_display

class Entity(object):
    def __init__(self):
        super(Entity, self).__init__()
        self.px = 0
        self.py = 0

    def paint(self):
        pass

    def update(self, delta_t):
        pass

class Paddle(Entity):
    def __init__(self, px, py, ball):
        super(Paddle, self).__init__()

        self.px = px
        self.py = py
        self.height = 100
        self.width = 10

        self.ball = ball

    def paint(self):
        x = int(self.px - self.width / 2)
        y = int(self.py - self.height / 2)
        pygame.draw.rect(g.screen, g.c_paddle, (x, y, self.width, self.height))

    def update(self, delta_t):

        pass

    def check_collision(self):

        if self.px < g.screen_width/2:
            # lhs
            if self.ball.px - self.ball.radius < self.px + self.width/2:
                if self.ball.py > self.py - self.height/2 and \
                   self.ball.py < self.py + self.height/2:
                    if self.ball.dx < 0:
                        self.ball.dx = abs(self.ball.dx)
                else:
                    self.ball.attach(self)
                    if g.player_id == 0:
                        g.score_right += 1
                        # TODO: fixme enqueue
                        #g.client.enqueue(message.UpdateScoreMessage(g.score_left, g.score_right))
        else:
            # rhs
            if self.ball.px + self.ball.radius > self.px - self.width/2:
                if self.ball.py > self.py - self.height/2 and \
                   self.ball.py < self.py + self.height/2:
                    if self.ball.dx > 0:
                        self.ball.dx = -abs(self.ball.dx)
                else:
                    self.ball.attach(self)
                    if g.player_id == 0:
                        g.score_left += 1
                        # TODO: fixme enqueue
                        #g.client.enqueue(message.UpdateScoreMessage(g.score_left, g.score_right))

class PlayerLocal(Paddle):
    def __init__(self, px, py, ball):
        super(PlayerLocal, self).__init__(px, py, ball)

        self.direction = common.PlayerDirection.NONE

        self.elapsed_t = 0

    def update(self, delta_t):

        self.elapsed_t += delta_t

        keys = pygame.key.get_pressed()

        y1 = self.height//2
        y2 = g.screen_height - self.height//2

        if keys[pygame.K_z] or keys[pygame.K_DOWN]:
            # top to bottom takes 2 seconds
            self.py += g.screen_height / 2 * delta_t
            new_direction = common.PlayerDirection.DOWN

        elif keys[pygame.K_a] or keys[pygame.K_UP]:
            # top to bottom takes 2 seconds
            self.py -= g.screen_height / 2 * delta_t
            new_direction = common.PlayerDirection.UP
        else:
            new_direction = common.PlayerDirection.NONE

        # send position every time the direction changes or every .1 seconds
        if new_direction != self.direction or self.elapsed_t > 0.1:
            self.direction = new_direction
            msg = common.PlayerPosition(direction=self.direction, x=int(self.px), y=int(self.py))
            g.client.send(msg.dumpb(), retry=RetryMode.NONE)
            self.elapsed_t = 0

        if self.py < y1:
            self.py = y1

        elif self.py > y2:
            self.py = y2

        self.check_collision()

class PlayerRemote(Paddle):
    def __init__(self, px, py, ball):
        super(PlayerRemote, self).__init__(px, py, ball)
        self.direction = common.PlayerDirection.NONE

        self.py_shadow = py
        self.py_error = 0

    def updateState(self, state: common.PlayerPosition):

        self.py_error = 0
        self.py_shadow = state.y
        self.direction = state.direction

    def update(self, delta_t):

        y1 = self.height//2
        y2 = g.screen_height - self.height//2

        if self.direction == common.PlayerDirection.DOWN:
            # top to bottom takes 2 seconds
            self.py_shadow += g.screen_height / 2 * delta_t

        elif self.direction == common.PlayerDirection.UP:
            # top to bottom takes 2 seconds
            self.py_shadow -= g.screen_height / 2 * delta_t
            new_direction = common.PlayerDirection.UP

        self.py = self.py_shadow + self.py_error

        if abs(self.py_error) > 1e-5:
            self.py_error = self.py_error * .9

        if self.py < y1:
            self.py = y1

        elif self.py > y2:
            self.py = y2

        self.check_collision()

class Ball(Entity):
    def __init__(self):
        super(Ball, self).__init__()
        self.attached = None
        self.radius = 5

        self.speed = 300

        self.px = g.screen_width / 2
        self.py = g.screen_height / 2

        self.dx = self.speed * .7071
        self.dy = self.speed * .7071

        self.elapsed_t = 0

    def paint(self):
        pygame.draw.circle(g.screen, g.c_ball, (int(self.px), int(self.py)), self.radius)

    def update(self, delta_t):

        if g.player_id == 0:

            self.elapsed_t += delta_t
            if self.elapsed_t > .1:
                t = time.time()
                self.elapsed_t -= .1
                # TODO: fixme enqueue
                #g.client.enqueue(self.getState())

        if self.attached is not None:
            self.py = self.attached.py
            if self.attached.px < g.screen_width//2:
                self.px = self.attached.px + self.radius*2
            else:
                self.px = self.attached.px - self.radius*2
        else:
            self.px += self.dx * delta_t
            self.py += self.dy * delta_t

        y1 = self.radius
        y2 = g.screen_height - self.radius
        if self.py < y1:
            self.py = y1
            self.dy = abs(self.dy)
        elif self.py > y2:
            self.py = y2
            self.dy = -abs(self.dy)

        x1 = self.radius
        x2 = g.screen_width - self.radius
        if self.px < x1:
            self.px = x1
            self.dx = abs(self.dx)
        elif self.px > x2:
            self.px = x2
            self.dx = -abs(self.dx)

    def attach(self, other):
        self.attached = other

    def detach(self):
        if self.attached is not None:
            self.attached = None

            xdir = 1 if (self.px < g.screen_width//2) else -1
            ydir = 1 if (self.py < g.screen_height//2) else -1
            self.dx = xdir * self.speed * .7071
            self.dy = ydir * self.speed * .7071

    def getState(self):

        attached_to = 0
        if self.attached is not None:
            attached_to = 1 if self.attached.px < g.screen_width//2 else 2

        return message.UpdateBallMessage(time.time(), attached_to, self.px, self.py, self.dx, self.dy)

    def updateState(self, send_time, attached_obj, px, py, dx, dy):
        recv_time = time.time()
        current = self.getState()

        self.attached = attached_obj
        self.px = px
        self.py = py
        self.dx = dx
        self.dy = dy
        delta_t = recv_time - send_time
        frame_rate = 1 / g.FPS
        while delta_t > 0:
            self.update(frame_rate)
            delta_t -= frame_rate

class GameScene(Scene):
    def __init__(self):
        super(GameScene, self).__init__()

        self.entities = []

        left = (10, g.screen_height//2)
        right = (g.screen_width - 10, g.screen_height//2)

        if g.player_id == 0:
            s1 = left
            s2 = right
        elif g.player_id == 1:
            s1 = right
            s2 = left
        else:
            raise ValueError(g.player_id)

        self.ball = Ball()

        self.player_local = PlayerLocal(*s1, self.ball)
        self.player_remote = PlayerRemote(*s2, self.ball)

        if g.player_id == 0:
            self.player_left = self.player_local
            self.player_right = self.player_remote
        elif g.player_id == 1:
            self.player_left = self.player_remote
            self.player_right = self.player_local

        if g.player_id == 0:
            self.ball.attached = self.player_local
        else:
            self.ball.attached = self.player_remote

        self.entities.append(self.player_local)
        self.entities.append(self.player_remote)
        self.entities.append(self.ball)

        self.score_1 = 0
        self.score_2 = 0

    def handle_message(self, msg):

        if msg.type_id == common.PlayerPosition.type_id:
            self.player_remote.updateState(msg)

        #elif pkt.type == common.UpdateBallMessage.type_id:
        #    obj = None
        #    if pkt.attached_to:
        #        if pkt.attached_to == 1:
        #            obj = self.player_left
        #        else:
        #            obj = self.player_right
        #    self.ball.updateState(pkt.time, obj, pkt.px, pkt.py, pkt.dx, pkt.dy)

        elif msg.type_id == common.BallRelease.type_id:
            if self.ball.attached is not None:
                self.ball.detach()

        elif msg.type_id == common.ScoreUpdate.type_id:
            g.score_left = msg.score1
            g.score_right = msg.score2

        elif msg.type_id == common.RoomJoinReply.type_id:
            if msg.status == common.RoomJoinStatus.OK:
                g.waiting_on_player2 = False

        elif msg.type_id == common.RoomDestroy.type_id:
            g.next_state = Scenes.LOBBY

        else:
            print(msg)

    def handle_event(self, evt):

        if evt.type == pygame.KEYUP:
            if evt.key == pygame.K_SPACE:
                if self.ball.attached is self.player_local:
                    g.client.send(common.BallRelease().dumpb())

    def paint(self):

        g.screen.fill((0, 0, 0))

        for ent in self.entities:
            ent.paint()

        surface = g.font_score.render('%d - %d' % (g.score_left, g.score_right), True, g.c_text)
        w = surface.get_width()
        h = surface.get_height()
        #pygame.draw.rect(g.screen, (127,127,127), (g.screen_width//2 - w//2, 0, w, h))
        g.screen.blit(surface, (g.screen_width//2 - w//2, 0))

        surface = g.font_score.render('%d' % (g.player_id), True, g.c_text)
        w = surface.get_width()
        h = surface.get_height()
        g.screen.blit(surface, (g.screen_width//2 - w//2, g.screen_height - h))

        lat = int(g.client.latency() * 1000)
        surface = g.font_sys.render('latency: %dms' % lat, True, g.c_text)
        w = surface.get_width()
        h = surface.get_height()
        g.screen.blit(surface, (0, g.screen_height - h))

        s = "dir: %s" % self.player_remote.direction
        surface = g.font_sys.render(s, True, g.c_text)
        w = surface.get_width()
        h = surface.get_height()
        g.screen.blit(surface, (g.screen_width - w, g.screen_height - h))

        if g.player_id == 0 and g.waiting_on_player2:
            surface = g.font_score.render('Waiting on Player 2', True, g.c_text)
            w = surface.get_width()
            h = surface.get_height()
            g.screen.blit(surface, (g.screen_width//2 - w//2, g.screen_height//2 - h//2))
        elif self.ball.attached is self.player_local:
            surface = g.font_score.render('Press Space', True, g.c_text)
            w = surface.get_width()
            h = surface.get_height()
            g.screen.blit(surface, (g.screen_width//2 - w//2, g.screen_height//2 - h//2))

    def update(self, delta_t):

        for ent in self.entities:
            ent.update(delta_t)

class Engine(object):
    def __init__(self):
        super(Engine, self).__init__()

        self.active = False
        self.state = None
        self.screenshot_index = 0

    def init(self):

        pygame.init()
        pygame.font.init()
        g.next_state = Scenes.HOME
        # g.next_state = Scenes.CONNECTING

        g.screen = pygame.display.set_mode((g.screen_width, g.screen_height))

        g.font_title = pygame.font.SysFont('Comic Sans MS', 72)
        g.font_score = pygame.font.SysFont('Comic Sans MS', 42)
        g.font_sys = pygame.font.SysFont('Comic Sans MS', 16)

    def getState(self, state):
        if state == Scenes.ERROR:
            return ExceptionScene()
        elif state == Scenes.CONNECTING:
            return ConnectingScene()
        elif state == Scenes.HOME:
            return HomeScene()
        elif state == Scenes.LOBBY:
            return LobbyScene()
        elif state == Scenes.GAME:
            return GameScene()

        raise ValueError(state)

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

        g.client = UdpClient()

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
                g.next_state = Scenes.ERROR

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