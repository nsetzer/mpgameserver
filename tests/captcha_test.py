
import unittest

try:
    from mpgameserver.captcha import Captcha


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

        def test_captcha(self):

            captcha = Captcha.create()

            self.assertTrue(len(captcha.getBytes()) < 1500)
            self.assertTrue(len(captcha.code) == 5)

            self.assertTrue(captcha.validate(captcha.code))



except ImportError as e:
    pass

def main():
    unittest.main()


if __name__ == '__main__':
    main()
