#! cd .. && python -m demo.pong_server

import pygame
import math
from typing import List, Dict
from mpgameserver.serializable import Serializable, SerializableEnum

##############################################################################
# Globals
#

class Namespace(object):
    """ shared global config

    """
    def __init__(self):
        super(Namespace, self).__init__()

        # shared state
        self.screen_width = 960
        self.screen_height = 540

        self.username = "name"
        self.roomname = "my room"
        self.auto_join = False

        # client state:
        self.FPS = 60
        self.screen = None
        self.frame_counter = 1
        self.next_state = None
        self.update_interval = 0.1
        self.host = "localhost"
        self.port = 1474

        self.c_paddle = (0, 255, 0)
        self.c_ball = (0, 255, 0)
        self.c_text = (0, 255, 0)
        self.c_input_bg_inactive = (72, 72, 72)
        self.c_input_bg_active = (128, 128, 128)

        self.waiting_on_player2 = True
        self.score_left = 0
        self.score_right = 0
        self.player_id = 0

# import the global config as 'g'
g = Namespace()

##############################################################################
# Messages
#

class PlayerSide(SerializableEnum):
    UNKNOWN = 0
    LEFT = 1
    RIGHT = 2

class PlayerDirection(SerializableEnum):
    NONE = 0
    UP   = 1
    DOWN = 2


class PlayerPosition(Serializable):
    direction: PlayerDirection = PlayerDirection.NONE
    x: int = 0
    y: int = 0

class RoomList(Serializable):
    pass

class RoomListReply(Serializable):
    rooms: Dict[int, str] = {} # room_id to room_name

class RoomCreate(Serializable):
    name: str = ""

class RoomCreateReply(Serializable):
    room_id: int = 0

class RoomJoin(Serializable):
    room_id: int = 0

class RoomJoinStatus(SerializableEnum):
    OK=0
    ERROR_FULL=1
    ERROR_DNE=2

class RoomJoinReply(Serializable):
    room_id: int = 0
    status: RoomJoinStatus = RoomJoinStatus.OK
    opponent_name: str = ""
    side: PlayerSide = PlayerSide.UNKNOWN

class RoomDestroy(Serializable):
    room_id: int = 0

class BallPosition(Serializable):
    x: int = 0
    y: int = 0
    dx: int = 0
    dy: int = 0

class BallRelease(Serializable):
    pass

class ScoreUpdate(Serializable):
    score1: int = 0
    score2: int = 0