#! cd .. && python -m tests.http_test
import unittest

import io

from mpgameserver import Serializable, HTTPServer, Router, Resource, \
    get, put, post, delete, \
    Response, JsonResponse, SerializableResponse

from mpgameserver.http_server import Request, TestClient


class SampleResource(Resource):

    @get("/simple")
    def get_simple(self, request):
        return JsonResponse({}, status_code=200)

    @put("/simple")
    def put_simple(self, request):
        #print("headers %r" % request.headers)
        #print('len', int(request.headers[b'Content-Length'][0]))
        return JsonResponse({}, status_code=200)

    @post("/simple")
    def post_simple(self, request):
        #print("headers %r" % request.headers)
        #print('len', int(request.headers[b'Content-Length'][0]))
        return JsonResponse({}, status_code=200)

    @delete("/simple")
    def delete_simple(self, request):
        return JsonResponse({}, status_code=200)

    @get("/path/optone/:arg1?")
    def get_path_optone(self, request):
        return JsonResponse({}, status_code=200)

    @get("/path/optplus/:arg1+")
    def get_path_optplus(self, request):
        return JsonResponse({}, status_code=200)

    @get("/path/optmany/:arg1*")
    def get_path_optmany(self, request):
        return JsonResponse({}, status_code=200)

    @get("/params")
    def get_params(self, request):
        #print("params", request.params)
        return JsonResponse({}, status_code=200)

class HttpServerTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.router = Router()
        cls.router.registerRoutes(SampleResource())
        cls.client = TestClient(cls.router)

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_simple(self):

        response = self.client.sample_get_simple()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request.path, "/simple")

        response = self.client.sample_put_simple(headers={"Content-Length": 0}, body=io.BytesIO())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request.path, "/simple")

        response = self.client.sample_post_simple(headers={"Content-Length": 0}, body=io.BytesIO())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request.path, "/simple")

        response = self.client.sample_delete_simple()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request.path, "/simple")

    def test_optone(self):

        response = self.client.sample_get_path_optone()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request.path, "/path/optone/")

        response = self.client.sample_get_path_optone("1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request.path, "/path/optone/1")

    def test_optplus(self):

        response = self.client.sample_get_path_optplus("1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request.path, "/path/optplus/1")

        response = self.client.sample_get_path_optplus("1", "2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request.path, "/path/optplus/1/2")

    def test_optmany(self):

        response = self.client.sample_get_path_optmany()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request.path, "/path/optmany/")

        response = self.client.sample_get_path_optmany("1", "2", "3")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request.path, "/path/optmany/1/2/3")

    def test_params(self):
        response = self.client.sample_get_params(params={"foo":"bar"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request.path, "/params")

def main():
    unittest.main()

if __name__ == '__main__':
    main()
