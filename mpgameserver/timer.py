

class Timer(object):
    INTERVAL = 1/60

    def __init__(self, duration=0, callback=None):
        super(Timer, self).__init__()
        self.elapsed_t = 0
        self.expires_t = duration
        self.expires_t2 = duration - Timer.INTERVAL/2
        self.callback = callback

    def update(self, delta_t):
        self.elapsed_t += delta_t
        if self.elapsed_t >= self.expires_t2:

            if self.elapsed_t > 2*self.expires_t:
                self.elapsed_t = 0
            else:
                self.elapsed_t -= self.expires_t

            self.callback()

    def setInterval(self, duration, callback):

        self.expires_t = duration
        self.expires_t2 = duration - Timer.INTERVAL/2
        self.callback = callback
