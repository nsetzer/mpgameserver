
import pygame
import math
from typing import List
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

        # client state:
        self.FPS = 60
        self.screen = None
        self.frame_counter = 1
        self.next_state = None
        self.update_interval = 0.1
        self.host = "localhost"
        self.port = 1474

# import the global config as 'g'
g = Namespace()

##############################################################################
# Messages
#

class ShipPhase(SerializableEnum):
    DEAD = 1
    DEFAULT = 2
    CHARGING = 3

class ShipState(Serializable):
    """ The current status of a ship
    """
    token: int = 0
    time: float = 0.0
    phase: ShipPhase = ShipPhase.DEAD
    angle: int = 0
    xpos: int = 0
    ypos: int = 0
    charge: float = 0

class ShipRemove(Serializable):
    """ Remove a player (indicated by the token) from the game
    """
    token: int = 0

class ShipDestroy(Serializable):
    """ Notify a client that a player (indicated by the token) should be destroyed
    """
    token: int = 0
    destroy: bool = False

class ShipUpdate(Serializable):
    """ multiple ShipState update messages

    """
    states: List[ShipState] = None

class ShipCreateBullet(Serializable):
    """ request a bullet to be spawned

    This message has a dual purpose:

    * A client can send this message to request that a bullet be spawned
    * The server will send this message to all clients to spawn the bullet.


    """
    xpos: int = 0
    ypos: int = 0
    angle: int = 0
    charge: float = 0

##############################################################################
# Shapes
#

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

def ShipTriangle(pos, angle):
    """
    the default polygon is centered at (0,0) and facing EAST
    the polygon is rotated around the center point then translated
    to final position

    this is used as the collision mask for the ship
    """
    polygon = [
        pygame.math.Vector2(-16,-16).rotate(angle) + pos,
        pygame.math.Vector2(32, 0).rotate(angle) + pos,
        pygame.math.Vector2(-16, 16).rotate(angle) + pos,
    ]
    return polygon

##############################################################################
# Interpolation
#


def lerp(a, b, p):
    """ linearly interpolate between two value a and b given percent p
    """
    return (b - a) * p + a

def lerp_wrap(a, b, p, m):
    """ linearly interpolate between two value a and b given percent p
    wrap arround back to 0 if the resulting value is greater than m
    and wrap around back to m if the resulting value is less than 0

    """
    if p > 1.0:
        return b
    if p < 0.0:
        return a

    c = b - a
    if c < -m/2:
        c += m
    elif c > m/2:
        c -= m

    c = a + p * c

    if c > m:
        c -= m
    if c < 0:
        c += m

    return c

def wrap(v, minv, maxv):
    """ wrap a value v between some minimum and maximum value

    e.g. wrap(7, 3, 6) => 7 - (6 - 3) => 7 - 3 => 4
    """
    if v > maxv:
        return v - (maxv - minv)
    elif v < minv:
        return v + (maxv - minv)
    return v

##############################################################################
# Collision Detection
#

def triangle_area(p1,p2,p3):
    """ calculate the area of a triangle using Heron's formula

    return s*(s-a)*(s-b)*(s-c)

    Heron's formula
        a,b,c := the length of each side
        s := semi-perimeter := (a + b + c) / 2
        area := sqrt(s*(s-a)*(s-b)*(s-c))

    """
    x1,y1 = p1
    x2,y2 = p2
    x3,y3 = p3
    # compute the square of the length of each side
    a = math.sqrt((x1-x2) ** 2 + (y1-y2) ** 2)
    b = math.sqrt((x1-x3) ** 2 + (y1-y3) ** 2)
    c = math.sqrt((x2-x3) ** 2 + (y2-y3) ** 2)
    # find the semi-perimeter
    s = (a + b + c) / 2
    # compute the area
    return math.sqrt(s * (s-a) * (s-b) * (s-c))

def collide_triangle_point(t1, t2, t3, p, tolerance=1e-3):
    """ return true if a point collides with a triangle
    """

    # compute the area of the triangle
    area0 = triangle_area(t1, t2, t3)

    # compute the area of each triangle made from 2 points and the given point
    area1 = triangle_area(t1, t2, p)
    area2 = triangle_area(t1, t3, p)
    area3 = triangle_area(t2, t3, p)

    # the sum of the three areas will equal the original area if the point
    # is fully contained within the triangle, or be much greater if the
    # point is outside the triangle.
    areas = area1 + area2 + area3

    # compute the error between the expected and actual area
    # typically the calculation is off by +/- 1e-15
    # use a tolerance instead of directly comparing the sizes
    error = abs(area0 - areas) / area0
    return error < tolerance


##############################################################################
# Shared Entities
#

class Bullet(object):
    """
    """

    def __init__(self, pos, angle, charge):
        super(Bullet, self).__init__()
        self.pos = pygame.Vector2(pos)
        self.charge = charge

        # a countdown timer: the number of seconds before destroying the bullet
        self.countdown = 1.25

        self.angle = angle
        self.velocity = pygame.Vector2(640,0).rotate(angle)
        self.radius = 3 + 4 * charge

        self.chain = [pygame.Vector2(self.pos)]

        # for the client
        self.sprite = None

        # for the server, collision detection
        # the set of clients this bullet has already collided with
        self.collisions = set()

    def alive(self):
        return self.countdown > 0

    def update(self, delta_t):

        if self.countdown > 0:
            self.countdown -= delta_t

            # fix the rounding error
            # ensure that the bullet on all clients and the server
            # end at exactly the same position
            if self.countdown < 0:
                delta_t += self.countdown

            self.pos += self.velocity * delta_t

            if self.pos[0] < 0:
                self.pos[0] += g.screen_width

            if self.pos[0] > g.screen_width:
                self.pos[0] -= g.screen_width

            if self.pos[1] < 0:
                self.pos[1] += g.screen_height

            if self.pos[1] > g.screen_height:
                self.pos[1] -= g.screen_height

            self.chain.append(pygame.Vector2(self.pos))
            while len(self.chain) > 10:
                self.chain.pop(0)

    def paint(self, surface):

        if not self.sprite:
            w = self.radius * 2 + 1
            self.sprite = pygame.Surface((w,w))
            self.sprite.fill((0,255,0))
            self.sprite.set_colorkey((0,255,0))

            pygame.draw.circle(self.sprite, (255,0,0), (self.radius,self.radius), self.radius)

        for i, pos in enumerate(self.chain):
            self.sprite.set_alpha(int(i * (255 / len(self.chain))))
            surface.blit(self.sprite, pos - (self.radius, self.radius))