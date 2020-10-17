#! cd .. && python -m demo.echoclient

from mpgameserver import UdpClient, Timer
import time
import sys

def main():  # pragma: no cover

    addr = ('localhost', 1474)

    # the duration of each 'frame'
    interval = 1/30

    def send_message():
        if client.connected():
            client.conn.send(b"hello")

    def onConnect(connected):
        if not connected:
            print("unable to connect to server")
            sys.exit(1)


    client = UdpClient()
    client.connect(addr, callback=onConnect)
    timer = Timer(.5, send_message)

    try:
        while True:
            timer.update(interval)
            client.update()

            for seqnum, msg in client.getMessages():
                print("received: %r" % msg, "Latency: %dms" % int(1000*client.latency()))
            time.sleep(interval)
    except KeyboardInterrupt as e:
        pass

    client.disconnect()
    client.waitForDisconnect()

if __name__ == '__main__':
    main()

