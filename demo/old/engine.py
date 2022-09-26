
class Namespace(object):
    def __init__(self):
        super(Namespace, self).__init__()
        self.FPS = 60
        self.host = 'localhost'
        #self.host = "104.248.122.206"
        self.port = 1474
        self.screen_width = 960
        self.screen_height = 540
        self.screen = None
        self.default_font = None
        self.frame_counter = 1

        self.next_state = None

        self.update_interval = 0.1

g = Namespace()


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

class GameStates(Enum):
    ERROR = 1
    CONNECTING = 2

class ConnectingState(GameState):
    def __init__(self):
        super(GameState, self).__init__()

        g.client.connect((g.host, g.port))
        self.timer = Timer(1.0, self.fail)

        self.font = pygame.font.SysFont('arial', 72)
        self.text = self.font.render("Connecting...", True, (255, 255, 255))

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
            g.next_state = GameStates.MAIN

        else:
            self.timer.update(delta_t)

    def fail(self):
        self.text = self.font.render("Unable to Connect", True, (255, 255, 255))

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

class Engine(object):
    def __init__(self):
        super(Engine, self).__init__()

        self.active = False
        self.state = None

    def init(self):

        pygame.init()
        pygame.font.init()
        g.next_state = GameStates.CONNECTING

        g.screen = pygame.display.set_mode((g.screen_width, g.screen_height))

    def _getState(self, state):
        if state is GameStates.ERROR:
            return ExceptionState()

        elif state is GameStates.CONNECTING:
            return ConnectingState()

        return self.getState(state)

    def getState(self, state):
        raise NotImplementedError()

    def setActive(self, active):
        self.active = active

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.setActive(False)

        if event.type == pygame.KEYUP:
            if event.key == pygame.K_ESCAPE:
                self.setActive(False)

        self.state.handle_event(event)

    def run(self):

        g.clock = pygame.time.Clock()

        self.active = True

        g.default_font = pygame.font.SysFont('Comic Sans MS', 16)

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
                g.client.update(dt)
                for msg in g.client.getMessages():
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
                g.next_state = GameStates.ERROR

        pygame.quit()

        if g.client:
            print("disconnecting client")
            g.client.disconnect()