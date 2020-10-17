#! cd .. && python demo/tankguiserver.py


import os
import sys
import logging
import time

import pygame

from threading import Thread

from mpgameserver.connection import ServerContext, ConnectionStats
from mpgameserver.twisted import ThreadedServer
from mpgameserver.timer import Timer
from mpgameserver import crypto

from mpgameserver.util import is_valid_ipv6_address
from mpgameserver.graph import LineGraph, AreaGraph

try:
    from PIL import Image
    has_pillow = True
except ImportError as e:
    has_pillow = False


class Namespace(object):
    def __init__(self):
        super(Namespace, self).__init__()
        self.FPS = 10
        self.screen_width = 960
        self.screen_height = 540
        self.screen = None
        self.frame_counter = 1

        self.next_state = None

        self.update_interval = 0.1

g = Namespace()

class GameStates(object):
    ERROR = 1
    MAIN = 2

class GameState(object):
    def __init__(self):
        super(GameState, self).__init__()

    def handle_message(self, msg):
        pass

    def handle_event(self, evt):
        pass

    def paint(self):
        pass

    def update(self, delta_t):
        pass

class ExceptionState(GameState):
    def __init__(self):
        super(ExceptionState, self).__init__()
        self.exec_info = sys.exc_info()
        font = pygame.font.SysFont('arial', 72)
        self.text = font.render("Error", True, (255, 255, 255))

    def paint(self):

        g.screen.fill((0,0,170))
        x = g.screen_width//2 - self.text.get_width()//2
        y = g.screen_height//2 - self.text.get_height()//2
        g.screen.blit(self.text, (x,y))

class MainState(GameState):
    def __init__(self):
        super(MainState, self).__init__()
        self.widgets = []

        self.font = pygame.font.SysFont('arial', 16)
        self.text_summary = self.font.render("????", True, (255, 255, 255))

        self.max_bytes_sent = self.font.render("????", True, (0, 200, 0))
        self.max_bytes_recv = self.font.render("????", True, (200, 0, 0))

        self.max_pkts_sent = self.font.render("????", True, (0, 200, 0))
        self.max_pkts_recv = self.font.render("????", True, (200, 0, 0))

        w = max(self.max_bytes_sent.get_width(), self.max_bytes_recv.get_width())
        h = self.font.get_linesize()*2

        self.max_bytes_mask = pygame.Surface((w,h)).convert_alpha()
        self.max_bytes_mask.fill((0,0,0,192))

        self.max_pkts_mask = pygame.Surface((w,h)).convert_alpha()
        self.max_pkts_mask.fill((0,0,0,192))

        self.stats_timer = Timer(2*g.update_interval, self.onStatsTimeout)

        host,port = g.server.server.addr
        proto = "IPv6" if is_valid_ipv6_address(host) else "IPV4"
        if host == '0.0.0.0':
            host = 'localhost'
        self.txt_listen = self.font.render("Listening on %s %s port %d" % (proto, host, port), True, (255,255,255))

        size = 100

        rect = pygame.Rect(0, g.screen_height-3*size-17,g.screen_width, size)
        self.widgets.append(LineGraph(rect, 5*60, "FPS",
            lambda: [g.server.server.thread.frame_rate],
            lambda v: "%d"%v))
        self.widgets[-1].setRange(45,75)
        self.widgets[-1].setLineTitle(["FPS"])
        self.graph_fps = self.widgets[-1]

        rect = pygame.Rect(0, g.screen_height-2*size-9,g.screen_width, size)
        self.widgets.append(LineGraph(rect, 5*60, "Packets Sent/Recv",
            lambda: [self.stats.pkts_recv, self.stats.pkts_sent],
            lambda v: "%d"%v))
        self.widgets[-1].setShowLabels(False)
        self.graph_pkts = self.widgets[-1]

        rect = pygame.Rect(0, g.screen_height-1*size-1,g.screen_width, size)
        self.widgets.append(LineGraph(rect, 5*60, "Bytes Sent/Recv",
            lambda: [self.stats.bytes_recv, self.stats.bytes_sent],
            lambda v: "%d"%v))
        self.widgets[-1].setShowLabels(False)
        self.graph_bytes = self.widgets[-1]

        size = 150
        y = self.widgets[0].ypos - size - 24
        rect = pygame.Rect(0, y, g.screen_width, size)
        self.widgets.append(AreaGraph(rect, 5*60,
            lambda: g.server.server.thread.perf_data))

    def getServerStats(self):

        stats = ConnectionStats()
        stats.assembled = 0
        stats.acked = 0
        stats.timeouts = 0
        stats.sent = 0

        N = (5 * 60)

        stats.pkts_sent = [0] * N
        stats.pkts_recv = [0] * N

        stats.bytes_sent = [0] * N
        stats.bytes_recv = [0] * N

        stats.pending_acks = 0

        seq = list(g.server.server.ctxt.connections.items())
        stats.connected = len(seq)
        for addr, client in seq:

            stats.assembled += client.stats.assembled
            stats.acked += client.stats.acked
            stats.timeouts += client.stats.timeouts
            stats.sent += client.stats.sent
            stats.pending_acks += len(client.pending_acks)

            for i, v in enumerate(reversed(client.stats.pkts_sent)):
                stats.pkts_sent[N - i - 1] += v

            for i, v in enumerate(reversed(client.stats.pkts_recv)):
                stats.pkts_recv[N - i - 1] += v

            for i, v in enumerate(reversed(client.stats.bytes_sent)):
                stats.bytes_sent[N - i - 1] += v

            for i, v in enumerate(reversed(client.stats.bytes_recv)):
                stats.bytes_recv[N - i - 1] += v


        return stats

    def onStatsTimeout(self):

        stats = self.getServerStats()

        statv = (
            stats.connected,
            stats.assembled,
            #stats.sent,
            stats.acked,
            int(100*stats.acked/max(1,stats.acked+stats.timeouts+stats.pending_acks)),
            stats.timeouts,
            stats.pending_acks
        )
        text = 'connections: %d assembled: %6d acked: %6d (%3d%%) timed_out: %6d pending_ack: %6d' % statv
        self.text_summary = self.font.render(text, True, (255, 255, 255))

        self.stats = stats

        # -----------

        if not stats.bytes_sent:
            return

        smax = max(stats.bytes_sent[:-1])
        rmax = max(stats.bytes_recv[:-1])
        tmax = max(smax, rmax)
        xscale = g.screen_width//(5*60)
        yscale = 100

        if tmax < 1:
            return

        # compute bytes per second over the last 10 seconds
        d = stats.bytes_sent[-10:]
        sbps = sum(d) / len(d)

        d = stats.bytes_recv[-10:]
        rbps = sum(d) / len(d)

        self.max_bytes_sent = self.font.render("sent: %6d bytes (%.3f bps)" % (smax, sbps), True, (0, 200, 0))
        self.max_bytes_recv = self.font.render("recv: %6d bytes (%.3f bps)" % (rmax, rbps), True, (200, 0, 0))
        w = max(self.max_bytes_sent.get_width(), self.max_bytes_recv.get_width())
        h = self.font.get_linesize()*2
        self.max_bytes_mask = pygame.Surface((w,h)).convert_alpha()
        self.max_bytes_mask.fill((0,0,0,128))
        # -----------

        smax = max(stats.pkts_sent[:-1])
        rmax = max(stats.pkts_recv[:-1])
        tmax = max(smax, rmax)
        xscale = g.screen_width//(5*60)
        yscale = 100

        # compute packets per second over the last 10 seconds
        d = stats.pkts_sent[-10:-1]
        spps = sum(d) / len(d)

        d = stats.pkts_recv[-10:-1]
        rpps = sum(d) / len(d)

        self.max_pkts_sent = self.font.render("sent: %6d packets (%.3f pps)" % (smax, spps), True, (0, 200, 0))
        self.max_pkts_recv = self.font.render("recv: %6d packets (%.3f pps)" % (rmax, rpps), True, (200, 0, 0))

        w = max(self.max_pkts_sent.get_width(), self.max_pkts_recv.get_width())
        h = self.font.get_linesize()*2
        self.max_pkts_mask = pygame.Surface((w,h)).convert_alpha()
        self.max_pkts_mask.fill((0,0,0,128))

    def paint(self):
        g.screen.fill((0,0,0))

        g.screen.blit(self.txt_listen, (8, 8))
        g.screen.blit(self.text_summary, (8, 8 + self.font.get_linesize()))

        for wgt in self.widgets:
            wgt.paint(g.screen)

        y = self.graph_pkts.ypos
        g.screen.blit(self.max_pkts_mask, (4, y+4))
        g.screen.blit(self.max_pkts_sent, (4, y+4))
        g.screen.blit(self.max_pkts_recv, (4, y+4+self.font.get_linesize()))

        y = self.graph_bytes.ypos
        g.screen.blit(self.max_bytes_mask, (4, y+4))
        g.screen.blit(self.max_bytes_sent, (4, y+4))
        g.screen.blit(self.max_bytes_recv, (4, y+4+self.font.get_linesize()))

        xscale = g.screen_width//(5*60)
        w = xscale * (5*60)


    def update(self, delta_t):

        self.stats_timer.update(delta_t)

        for wgt in self.widgets:
            wgt.update(delta_t)



class GuiServer(object):
    """ A server implementation which displays run time metrics in a pygame interface

    1. A summary of lifetime packets assembled, acked, timed out and pending

    2. Time Profiling: An area plot showing where the server is spending it's time, split into 4 categories.
        `Message Handling` is the time spent decrypting and processing datagrams.
        `Update` is the time spent in the update method of the event handler
        `Network` is the time spent encrypting and sending datagrams
        `Idle` is the time spent sleeping to maintain a steady tick rate

    3. Frames Per Scond / Ticks Per Second - the number of times the main loop is run during a given second.
        Ideally this would be a constant value determined from the [ServerContext](#servercontext) interval.
        But can fluctuate due to the accuracy of the sleep timer and server workload

    4. Packets Per Second - the Number of packets sent or received each second

    5. Bytes Per Second - the total number of bytes in each packet sent or received.

    ![Server](server.png)
    """
    def __init__(self, ctxt, addr):
        """ a server which displays metrics in a pygame window

        :param ctxt: A [ServerContext](#servercontext) instance
        :param addr: The address to bind to. A 2-tuple (host, port).
            host can be "::" to bind to an ipv6 address

        """
        super(GuiServer, self).__init__()

        self.ctxt = ctxt
        self.addr = addr
        self._active = False
        self._state = None

        self._init = False

        self.screenshot_index = 0

    def init(self):
        """ init pygame
        """
        pygame.init()
        pygame.font.init()
        g.next_state = GameStates.MAIN

        g.screen = pygame.display.set_mode((g.screen_width, g.screen_height))

        self._init = True

    def getState(self, state):
        """ private return a state instance
        """

        if state == GameStates.ERROR:
            return ExceptionState()
        else:
            return MainState()

    def _setActive(self, active):

        self._active = active

    def handle_event(self, event):
        """ private default event handler
        """

        if event.type == pygame.QUIT:
            self._setActive(False)

        if event.type == pygame.KEYUP:
            if event.key == pygame.K_ESCAPE:
                self._setActive(False)

            elif event.key == pygame.K_p and has_pillow:
                imgs = []

                raw = pygame.image.tostring(g.screen, "RGBA", False)
                image = Image.frombytes("RGBA", g.screen.get_size(), raw)
                filename = 'screenshot-%d.png' % self.screenshot_index
                image.save(filename)
                self.screenshot_index += 1
                print("saved " + filename)

        self._state.handle_event(event)

    def run(self):
        """ run the server.

        calls `init()` if it has not yet been run
        """

        if not self._init:
            self.init()

        g.clock = pygame.time.Clock()

        self._active = True

        accumulator = 0.0
        update_step = 1 / g.FPS

        g.server = ThreadedServer(self.ctxt, self.addr)
        g.server.start()

        while self._active:

            try:
                if g.next_state:
                    self._state = self.getState(g.next_state)
                    g.next_state = None

                dt = g.clock.tick(g.FPS) / 1000
                accumulator += dt
                g.frame_counter += 1

                # handle events
                for event in pygame.event.get():
                    if self.handle_event(event):
                        continue

                # update game state
                # use a constant delta
                while accumulator > update_step:
                    self._state.update(update_step)
                    accumulator -= update_step

                # paint
                self._state.paint()

                pygame.display.flip()
            except Exception as e:
                logging.exception("unhandled exception")
                g.next_state = GameStates.ERROR

        pygame.quit()
