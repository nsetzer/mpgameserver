#! cd .. && python -m demo.headlessclient -n 100

import os
import sys
import time
import random
import argparse
sys.path.insert(0, os.getcwd())

from mpgameserver import UdpClient, Timer, Serializable, EllipticCurvePublicKey
from mpgameserver.connection import ConnectionStats
from .shipcommon import ShipPhase, ShipState, ShipUpdate, ShipCreateBullet

def getState():
    state = ShipState()
    state.phase = ShipPhase.DEFAULT
    state.angle = 0
    state.xpos = 0
    state.ypos = 0
    state.charge = 0.0
    return state

def main():

    parser = argparse.ArgumentParser(description='Client Simulator')

    parser.add_argument('-n', '--n_clients', type=int, default=25)

    args = parser.parse_args()

    host = "localhost"
    port = 1474
    n_clients = args.n_clients
    clients = []
    dt = 1/60

    counter = 0
    while True:

        for client in clients:
            client.update(dt)

        if counter%20 == 0 and len(clients) < n_clients:
            client = UdpClient()
            client.remote_players = {}
            client.connect((host, port))
            clients.append(client)
            print("adding client %d" % len(clients))

        if len(clients) == n_clients:
            if all([client.connected() for client in clients]):
                break;
            else:
                if counter%20 == 0:
                    print("waiting for clients to connect...")

        time.sleep(1/128)
        counter += 1

    print("clients to connected")

    def print_stats():

        lat = [int(client.conn.latency*1000) for client in clients]
        lat = (min(lat), sum(lat)/len(lat), max(lat))

        stats = ConnectionStats()
        pending = 0
        bytes_sent = 0
        bytes_recv = 0
        delay = 0
        t0 = time.time()
        for client in clients:
            stats.assembled += client.conn.stats.assembled
            stats.acked += client.conn.stats.acked
            stats.timeouts += client.conn.stats.timeouts
            stats.sent += client.conn.stats.sent
            bytes_sent += sum(client.conn.stats.bytes_sent[-10:]) / 10
            bytes_recv += sum(client.conn.stats.bytes_recv[-10:]) / 10
            pending += len(client.conn.pending_acks)

            # delay is a measure of worst case, how far behind a remote player
            # is from reality.higher values are a symptom of packet loss
            # from the server
            if client.remote_players:
                delay = max(delay, max(t0 - t1 for t1 in client.remote_players.values()))

        text = "asm: %5d acked: %5d timeouts: %5d pending: %5d s: %.2f r: %.2f" % (
            stats.assembled,
            stats.acked,
            stats.timeouts,
            pending,
            # the average number of bytes sent/revceived by a single client
            # over a 10 second window
            bytes_sent/n_clients,
            bytes_recv/n_clients,
        )
        print(text, lat, "%.6f" % delay)

    def ship_update():

        for client in clients:
            state = ShipState()
            state.token = client.token()
            client.send(state.dumpb(), retry=0)
            client.update(dt)

    stat_timer = Timer(1, print_stats)
    update_timer = Timer(.1, ship_update)


    try:
        while True:

            t0 = time.time()
            for client in clients:
                # process messages received from the server
                for msg in client.getMessages():
                    msg = Serializable.loadb(msg)

                    if msg.type_id == ShipUpdate.type_id:
                        for state in msg.states:
                            if state.token == client.token():
                                continue
                            client.remote_players[state.token] = t0
                    if msg.type_id == ShipState.type_id:
                        if msg.token == client.token():
                                continue
                        client.remote_players[msg.token] = t0

                # randomly fire a bullet, approximately once every 2 seconds
                if random.randint(0,120)==0:
                    msg = ShipCreateBullet()
                    client.send(msg.dumpb(), retry=0)

                client.update(dt)

            stat_timer.update(dt)
            update_timer.update(dt)
            time.sleep(dt)
    except BaseException as e:
        for client in clients:
            client.disconnect()
        raise


if __name__ == '__main__':
        main()