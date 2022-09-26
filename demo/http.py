#! cd .. && python -m demo.http
#! cd .. && python -m demo.http --client


# server response is serializeable : client decodes
# client request  is serializeable : server decodes

import sys
import logging
import time

from mpgameserver import Serializable, HTTPServer, Router, Resource, get, post, HTTPClient, Response, JsonResponse, SerializableResponse
from mpgameserver.http_server import Request, TestClient

class SampleMessage(Serializable):
    x: int = 0
    y: int = 0

class WebResource(Resource):
    @get("/health")
    def health(self, request):
        return JsonResponse({}, status_code=200)

class SampleResource(Resource):

    @get("/hello")
    def get_hello(self, request):

        name = request.params.get("name", ['World'])[0]
        obj = {
            "message": "Hello, " + name,
        }
        return JsonResponse(obj, status_code=200)

    @get("/json")
    def get_json(self, request):

        obj = {
            "location": request.location,
            "matches": request.matches,
            "query": request.query,
        }
        return JsonResponse(obj, status_code=200)

    @get("/message")
    def get_message(self, request):
        return SerializableResponse(SampleMessage(), status_code=200)

    @post("/message")
    def post_message(self, request):
        print(request.message())
        return Response()

    @get("/:path*")
    def root(self, request):
        # return SerializableResponse(SampleMessage(), status_code=200)
        print(request.headers)
        print(request.params)
        return JsonResponse({}, status_code=200)

def main_server():
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)

    router = Router()
    router.registerRoutes(WebResource())
    router.registerRoutes(SampleResource())


    client = TestClient(router)
    print(dir(client))
    response = client.sample_root("x")
    print(response)
    print(response.payload)

    #req = Request(("127.0.0.1", 1234), "GET", "/foo?a=%26&x=y;a=c", None, {})
    #print(req.query)
    #print(req.location)


    server = HTTPServer(("0.0.0.0", 1475))
    server.registerRoutes(SampleResource())
    server.run()


def main_client():

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)

    #requests_log = logging.getLogger("requests.packages.urllib3")
    #requests_log.setLevel(logging.DEBUG)
    #requests_log.propagate = True

    #t0 = time.time()
    #requests.get("http://127.0.0.1:1475/hello")
    #print(time.time() - t0)

    client = HTTPClient(("127.0.0.1", 1475))
    client.start()

    client.get("/hello", query={"name": "john"})
    client.get("/message")
    client.post("/message", SampleMessage())

    while client.pending():
        for h in client.getResponses():
            print()
            print(h.hid, h.response, h.response.payload)
        time.sleep(.2)

    client.stop()

if __name__ == '__main__':

    if '--client' in sys.argv:
        main_client()
    else:
        main_server()
