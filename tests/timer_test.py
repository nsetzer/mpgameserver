
import unittest
from mpgameserver.timer import Timer


class TimerTestCase(unittest.TestCase):

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

    def test_timer_1(self):

        success = False
        def callback():
            nonlocal success
            success = True

        timer = Timer(.5, callback)
        self.assertFalse(success)

        timer.update(.3)
        self.assertFalse(success)

        timer.update(.3)
        self.assertTrue(success)

    def test_timer_2(self):

        success = 0
        def callback():
            nonlocal success
            success += 1

        timer = Timer(.5, callback)
        self.assertEqual(success, 0)

        timer.update(10)
        self.assertEqual(success, 1)

    def test_timer_3(self):

        success = False
        def callback():
            nonlocal success
            success = True

        timer = Timer(.5, callback)

        timer.setInterval(1.0, callback)

        self.assertFalse(success)

        timer.update(.3)
        self.assertFalse(success)

        timer.update(.3)
        self.assertFalse(success)

        timer.update(.3)
        self.assertFalse(success)

        timer.update(.3)
        self.assertTrue(success)


def main():
    unittest.main()


if __name__ == '__main__':
    main()
