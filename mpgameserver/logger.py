
import os
import logging
from logging.handlers import RotatingFileHandler

LOGLEVEL_TRACE = 9
logging.addLevelName(LOGLEVEL_TRACE, "TRACE")
def trace(self, message, *args, **kws):
    if self.isEnabledFor(LOGLEVEL_TRACE):
        self._log(LOGLEVEL_TRACE, message, args, **kws)
logging.Logger.trace = trace


def basicConfig():

    logging.basicConfig(format='%(asctime)-15s %(levelname)s %(filename)s:%(funcName)s():%(lineno)d:%(message)s')

log = logging.getLogger("mpgameserver")

class PeerLogger(object):
    def __init__(self, addr):
        super(PeerLogger, self).__init__()
        if addr:
            self.peer = "%s:%d " % addr
        else:
            self.peer = ""

    def trace(self, *args, **kwargs):
        # stacklevel is new in 3.8
        s, *args = args
        log.trace(self.peer + s, *args, stacklevel=2, **kwargs)

    def debug(self, *args, **kwargs):
        s, *args = args
        log.debug(self.peer + s, *args, stacklevel=2, **kwargs)

    def info(self, *args, **kwargs):
        s, *args = args
        log.info(self.peer + s, *args, stacklevel=2, **kwargs)

    def warning(self, *args, **kwargs):
        s, *args = args
        log.warning(self.peer + s, *args, stacklevel=2, **kwargs)

    def error(self, *args, **kwargs):
        s, *args = args
        log.error(self.peer + s, *args, stacklevel=2, **kwargs)

    def exception(self, *args, **kwargs):
        s, *args = args
        log.error(self.peer + s, *args, stacklevel=2, exc_info=True, **kwargs)

def setupLogger(logger_name, log_file):
    parent, _ = os.path.split(log_file)

    if not os.path.exists(parent):
        os.makedirs(parent)

    l = logging.getLogger(logger_name)
    formatter = logging.Formatter('%(asctime)-15s %(levelname)s %(pathname)s:%(funcName)s:%(lineno)d: %(message)s')

    size = 1024 * 1024
    backupCount = 5
    fileHandler = RotatingFileHandler(
        log_file, maxBytes=size, backupCount=backupCount)
    fileHandler.setFormatter(formatter)
    l.addHandler(fileHandler)
    #if logger_name is not None:
    #    streamHandler = logging.StreamHandler()
    #    streamHandler.setFormatter(formatter)
    #    l.addHandler(streamHandler)

    return l