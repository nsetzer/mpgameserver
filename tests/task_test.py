
import unittest
import time
from mpgameserver.task import TaskPool


def task1(x, y):
    return x * y

def task2(x, y):
    raise ValueError()

class TaskTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        self.pool = TaskPool()

    def tearDown(self):
        self.pool.shutdown()

    def test_task_success(self):

        result = None
        def callback(res):
            nonlocal result
            result = res

        self.pool.submit(task1, (6, 7),
            callback=callback, error_callback=callback)

        for i in range(30):
            self.pool.update()
            if result is not None:
                return
            time.sleep(1/120)

        self.assertEqual(42, result, str(result))

    def test_task_failure(self):

        result = None
        def callback(res):
            nonlocal result
            result = res

        self.pool.submit(task2, (6, 7),
            callback=callback, error_callback=callback)

        for i in range(30):
            self.pool.update()
            if result is not None:
                return
            time.sleep(1/120)

        self.assertTrue(isinstance(result, ValueError))

    def test_task_user_fail(self):

        result = None
        def callback(res):
            raise ValueError()

        self.pool.submit(task2, (6, 7),
            callback=callback, error_callback=callback)

        for i in range(30):
            self.pool.update()
            if result is not None:
                return
            time.sleep(1/120)

        self.assertEqual(None, result)

def main():
    unittest.main()


if __name__ == '__main__':
    main()
