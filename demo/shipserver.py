#! cd .. && python -m demo.shipserver --gui

import os
import sys
import select
import logging
import math
import time

from mpgameserver import EventHandler, TwistedServer, GuiServer, Timer, Serializable, \
    ServerContext, EllipticCurvePrivateKey, RetryMode

from .shipcommon import ShipPhase, ShipState, ShipRemove, ShipUpdate, ShipDestroy, \
    ShipCreateBullet, Bullet, collide_triangle_point, ShipTriangle

class ShipHandler(EventHandler):
    def __init__(self):
        super(ShipHandler, self).__init__()

        self.players = {} # addr -> client
        self.player_state = {} # addr -> state
        self.players_dead = {} # addr -> time

        self.bullets = []

        # ships are 48 pixels on the longest axis
        # collision detection uses the distance squared metric
        self.ship_radius_squared = 32 * 32

        # seconds a player is dead until their ship is revived
        self.time_to_revive = 3.0

    def connect(self, client):

        self.players[client.addr] = client

    def disconnect(self, client):
        """ remove the client from the game state
        """

        if client.addr in self.player_state:

            for other in self.players.values():
                other.send(ShipRemove(token=client.token).dumpb(),
                    retry=RetryMode.RETRY_ON_TIMEOUT)

            del self.player_state[client.addr]

        if client.addr in self.players:
            del self.players[client.addr]

        if client.addr in self.players_dead:
            del self.players_dead[client.addr]

    def update(self, delta_t):

        """

        There is a bug here left as an exercise to the reader.
        If the bullet is moving fast enough it could teleport through
        the ship and not trigger a collision event.

        note how the bullet trails in the client don't overlap when
        the bullet speed is increased.

        The solution would be to call update multiple times per tick
        such that the value passed in to update() is a function of the
        radius and speed of the bullet. And to check for collisions
        after every update. Finally, work out the trade off between
        collision resolution, number of updates, and bullet speed
        to optimize for a large number of concurrent players.

        """

        self.updateBullets(delta_t)

        self.checkCollide()

        self.checkRevive()

    def handle_message(self, client, seqnum, payload):

        msg = Serializable.loadb(payload)

        if msg.type_id == ShipState.type_id:

            if client.addr in self.player_state:
                curseq, curstate = self.player_state[client.addr]
                if seqnum.newer_than(curseq):
                    self.player_state[client.addr] = (seqnum, msg)
                else:
                    client.log.info("dropping out of order message received: %d current: %d", seqnum, curseq)

            else:
                self.player_state[client.addr] = (seqnum, msg)

            for other in self.players.values():
                if other is client:
                    continue
                other.send(ShipUpdate(states=[msg]).dumpb(), retry=RetryMode.NONE)

        elif msg.type_id == ShipCreateBullet.type_id:
            # received a request from a client to create a bullet
            # validate the request, and if valid send a reply to all clients
            # to create the bullet.
            bullet = Bullet((msg.xpos, msg.ypos), msg.angle, msg.charge)
            bullet.collisions = set([client.token])
            self.bullets.append(bullet)

            for other in self.players.values():
                other.send(payload, retry=RetryMode.BEST_EFFORT)

    def updateBullets(self, delta_t):

        for bullet in self.bullets:
            # move the bullet
            bullet.update(delta_t)

        # remove bullets that have timed out
        self.bullets = [b for b in self.bullets if b.alive()]

    def checkCollide(self):
        """ check for a collision between any bullet and player
        """

        for bullet in self.bullets:
            # check for collisions
            for addr, (_, state) in self.player_state.items():

                # skip players that are already dead
                if state.phase == ShipPhase.DEAD:
                    continue

                # skip a collision test if a collision has already occurred between this bullet and this player
                client = self.players[addr]
                if client.token in bullet.collisions:
                    continue

                # perform a quick, course grain test to see if the bullet is near the ship
                distance_squared = bullet.pos.distance_squared_to((state.xpos, state.ypos))
                if distance_squared < self.ship_radius_squared:
                    # get the shape of the ship
                    t1,t2,t3 = ShipTriangle((state.xpos, state.ypos), state.angle)
                    # perform a slower, fine grain test to see if the bullet is within the ship
                    if collide_triangle_point(t1,t2,t3, bullet.pos):
                        self.doCollide(addr, state, bullet)

    def doCollide(self, addr, state, bullet):
        """ process the collision between a bullet and a player

        * record that this bullet collided with this player
        * send a message to all clients that the player is dead
        """

        client = self.players[addr]
        bullet.collisions.add(client.token)
        self.players_dead[addr] = time.time()

        msg = ShipDestroy(token=client.token, destroy=True).dumpb()
        for other in self.players.values():
            other.send(msg, retry=RetryMode.BEST_EFFORT)

    def checkRevive(self):
        """ check to see if it is time to revive a player


        """
        ct = time.time()

        revive = []
        for addr, t in self.players_dead.items():
            if ct - t > self.time_to_revive:
                revive.append(addr)

        for addr in revive:
            client = self.players[addr]
            msg = ShipDestroy(token=client.token, destroy=False).dumpb()
            for other in self.players.values():
                other.send(msg, retry=RetryMode.RETRY_ON_TIMEOUT)

            del self.players_dead[addr]


def main():

    host = "0.0.0.0"
    port = 1474

    format = '%(asctime)-15s %(levelname)s %(filename)s:%(funcName)s():%(lineno)d:%(message)s'
    logging.basicConfig(level=logging.DEBUG, format=format)

    # read the root key from stdin or use a default development key
    key = None
    if not sys.stdin.isatty():
        r, _, _ = select.select([sys.stdin], [], [], 0)
        if r:
            key = EllipticCurvePrivateKey.fromPEM(sys.stdin.read())
    if key is None:
        sys.stderr.write("MpGameServer using unsafe test key\n")
        key = EllipticCurvePrivateKey.unsafeTestKey()

    handler = ShipHandler()

    ctxt = ServerContext(handler, key)

    if '--gui' in sys.argv:
        server = GuiServer(ctxt, (host, port))
    else:
        server = TwistedServer(ctxt, (host, port))

    server.run()

if __name__ == '__main__':
    main()