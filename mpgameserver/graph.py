
import pygame
from .timer import Timer

class LineGraph(object):
    def __init__(self, rect, samples, title, callback, text_transform):
        super(LineGraph, self).__init__()

        self.xpos = rect.x
        self.ypos = rect.y
        self.callback = callback

        self.timer_update = Timer(.5, self._onUpdateTimeout)

        self.lines = []

        self.width = rect.width
        self.height = rect.height
        self.samples = samples

        self.xscale = self.width//self.samples
        self.yscale = self.height

        self.colors = [(255,0,0), (0,255,0), (0,0,255)]

        self.text_transform = text_transform

        self.vmin = None
        self.vmax = None

        self.font = pygame.font.SysFont('arial', 16)

        self.txt_title = self.font.render(title, True, (255,255,255))

        self.line_titles = []

        self.show_labels = True

    def setRange(self, vmin, vmax):
        self.vmin = vmin
        self.vmax = vmax

    def setLineTitle(self, titles):

        self.line_titles = []
        for col, txt in zip(self.colors, titles):
            self.line_titles.append(self.font.render(txt, True, col))

    def setShowLabels(self, show):
        self.show_labels = show

    def handle_event(self, evt):
        pass

    def handle_message(self, msg):
        pass

    def update(self, delta_t):

        self.timer_update.update(delta_t)

    def paint(self, surface):

        for x in range(0, self.samples + 1, 30):
            c = (72,72,72) if x%60 == 0 else (32,32,32)
            x0 = self.xpos + x * self.xscale
            y0 = self.ypos
            y1 = self.ypos + self.height
            pygame.draw.line(surface, c, (x0, y0), (x0, y1))
        w = self.samples*self.xscale

        pygame.draw.line(surface, (128,128,128), (self.xpos,self.ypos), (self.xpos+w, self.ypos))
        pygame.draw.line(surface, (128,128,128), (self.xpos,self.ypos+self.height), (self.xpos+w, self.ypos+self.height))
        pygame.draw.line(surface, (64,64,64), (self.xpos,self.ypos+self.height//2), (self.xpos+w, self.ypos+self.height//2))
        pygame.draw.line(surface, (32,32,32), (self.xpos,self.ypos+self.height//4), (self.xpos+w, self.ypos+self.height//4))
        pygame.draw.line(surface, (32,32,32), (self.xpos,self.ypos+self.height*3//4), (self.xpos+w, self.ypos+self.height*3//4))

        fh = self.font.get_linesize()

        for idx, line in enumerate(self.lines):
            if not line:
                continue
            vmax, points, txt_max, txt_val = line
            pygame.draw.lines(surface, self.colors[idx], False, points, width=2)

            if self.show_labels:
                surface.blit(txt_max, (self.xpos + w + 8, self.ypos + 3*fh*idx))
                surface.blit(txt_val, (self.xpos + w + 8, self.ypos + 3*fh*idx + fh))

        surface.blit(self.txt_title, (self.xpos, self.ypos + self.height - self.txt_title.get_height()))

    def _construct(self, values, color, dmax):

        if len(values) < 2:
            return

        values = values[-self.samples:]

        tmax = max(values)
        vmax = self.vmax if self.vmax is not None else dmax
        vmin = self.vmin if self.vmin is not None else 0
        vrng = vmax - vmin

        if vrng == 0:
            return

        points = [(i*self.xscale, self.ypos + self.yscale - (self.yscale*(max(min(v,vmax),vmin)-vmin)/vrng)) for i,v in enumerate(values)]

        txt_max = self.font.render(self.text_transform(tmax), True, color)
        txt_val = self.font.render("(%s)" % self.text_transform(values[-1]), True, color)

        return (vmax, points, txt_max, txt_val)

    def _onUpdateTimeout(self):

        x = -self.samples
        data = self.callback()
        dmax = max([max(values[x:]) if len(values)>2 else 0 for values in data])
        self.lines = [self._construct(data, color, dmax) for data, color in zip(data, self.colors)]

class AreaGraph(object):
    def __init__(self, rect, samples, callback):
        super(AreaGraph, self).__init__()

        self.xpos = rect.x
        self.ypos = rect.y
        self.width = rect.width
        self.height = rect.height
        self.callback = callback

        self.samples = samples
        self.xscale = self.width//self.samples
        self.yscale = self.height


        self.plot_width = int(self.samples * self.xscale)

        self.timer_update = Timer(.5, self._onUpdateTimeout)


        self.colors = [
            (0,50,200),
            (20,128,20),
            (128,20,20),
            (128,128,128),
        ]

        self.perf_data = []

            # 1 - 2 : message handler
            # 2 - 3 : update
            # 3 - 4 : network send
            # 4 - 5 : idle time

        self.font = pygame.font.SysFont('arial', 16)
        self.labels = []
        for col, txt in zip(self.colors, ['Msg. Handler', 'Update', 'Network', 'Idle']):
            surf = self.font.render(txt, True, col)
            self.labels.append(surf)

    def handle_event(self, evt):
        pass

    def handle_message(self, msg):
        pass

    def update(self, delta_t):
        self.timer_update.update(delta_t)

    def paint(self, surface):

        x = self.xpos
        y = self.ypos + self.height

        pygame.draw.line(surface, (32,32,32), (x,y), (x+self.plot_width, y))

        for i, data in enumerate(self.perf_data):

            x = self.xscale * i
            sum_total = 1.0 # data[0]
            percents = [round(self.yscale * data[x]/sum_total) for x in [1,2,3,4]]

            y = self.ypos

            # time spent in user code, processing messages
            v = percents[0]
            if v > 0:
                pygame.draw.rect(surface, self.colors[0], (x, y, self.xscale, v))
                y += v

            # time spent in user code, processing update
            v = percents[1]
            if v > 0:
                pygame.draw.rect(surface, self.colors[1], (x, y, self.xscale, v))
                y += v

            # time spent sending datagrams
            v = percents[2]
            if v > 0:
                pygame.draw.rect(surface, self.colors[2], (x, y, self.xscale, v))
                y += v

            # time spent idle
            v = percents[3]
            if v > 0:
                if y + v > y + self.height + 10:
                    v = self.height + 10
                pygame.draw.rect(surface, self.colors[3], (x, y, self.xscale, v))
                y += v



        y = self.ypos + self.height
        x = self.xpos + 8
        for lbl in self.labels:
            surface.blit(lbl, (x, y))
            x += lbl.get_width() + 8

    def _onUpdateTimeout(self):
        self.perf_data = self.callback()

