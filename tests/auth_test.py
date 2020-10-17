
import unittest
from mpgameserver.auth import Auth


class AuthTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_auth_success(self):

        password = b"password"
        hash = Auth.hash_password(password)

        self.assertTrue(hash.startswith("scrypt:1:"))

        self.assertTrue(Auth.verify_password(password, hash))



def main():
    unittest.main()


if __name__ == '__main__':
    main()
