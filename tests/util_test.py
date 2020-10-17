
import unittest
from mpgameserver import util


class UtilTestCase(unittest.TestCase):

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

    def test_ipv6(self):

        self.assertFalse(util.is_valid_ipv6_address("0.0.0.0"))

        self.assertTrue(util.is_valid_ipv6_address("::"))
        self.assertTrue(util.is_valid_ipv6_address("::1"))

        self.assertTrue(util.is_valid_ipv6_address("2001:0db8:0000:0000:0000:ff00:0042:8329"))
        self.assertTrue(util.is_valid_ipv6_address("2001:db8::ff00:42:8329"))


def main():
    unittest.main()


if __name__ == '__main__':
    main()
