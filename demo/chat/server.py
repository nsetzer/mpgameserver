#! cd .. && python -m demo.http
#! cd .. && python -m demo.http --client

# https://github.com/rlotun/txWebSocket/blob/master/simple_server.py


# server response is serializeable : client decodes
# client request  is serializeable : server decodes

import sys
import logging
import time
import json

from mpgameserver import Serializable, HTTPServer, Router, Resource, \
    get, post, \
    HTTPClient, Response, JsonResponse, \
    websocket, WebSocketOpCodes

class SampleResource(Resource):

    def __init__(self):
        super().__init__()

        self.connections = {}

    @get("/")
    def get_html(self, request):
        return Response(open("demo/chat/index.html").read())

    @get("/static/index.js")
    def get_script(self, request):
        return Response(open("demo/chat/index.js").read())

    @websocket("/ws")
    def socket(self, request, opcode, payload):

        if opcode == WebSocketOpCodes.Open:
            print("socket open")

            username = "user-%s" % request.uid
            request.send(json.dumps({
                "type": "setusername",
                "username": username
            }))

            for client in self.connections.values():
                client.send(json.dumps({
                    "type": "message",
                    "message": "%s joined the chat" % username,
                    "username": "system"
                }))
            self.connections[request.uid] = request

        elif opcode == WebSocketOpCodes.Close:

            username = "user-%s" % request.uid
            del self.connections[request.uid]
            for client in self.connections.values():
                client.send(json.dumps({
                    "type": "message",
                    "message": "%s left the chat" % username,
                    "username": "system"
                }))


        else:
            obj = json.loads(payload)

            # TODO: fill in username based on request.uid
            #       dont trust the user
            if obj['type'] == "message":
                for client in self.connections.values():
                    client.send(payload)





def main_server():
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)

    server = HTTPServer(("0.0.0.0", 4100))
    server.registerRoutes(SampleResource())
    server.run()


if __name__ == '__main__':

    main_server()
