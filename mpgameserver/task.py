
import sys
import time
import logging

from threading import Thread, Lock, Condition
from multiprocessing import Pool

class TaskPool(object):
    """ A Task Pool provides a thread safe mechanism for running long lived operations
    inside a separate process to avoid blocking the main game loop.

    The event handler can submit a task at any time. When the task completes the task pool update
    will process the callbacks.

    The event handler events Update and Shutdown should call the appropriate task pool method.
    """
    def __init__(self, processes=1, maxtasksperchild=None):
        super(TaskPool, self).__init__()
        self.pool = Pool(processes, maxtasksperchild=maxtasksperchild)

        self._lk_result = Lock()
        self._results = []

    def submit(self, fn, args=(), kwargs={}, callback=None, error_callback=None):
        """ submit a task to be run in a background process

        :param fn: a function to be run in a background process
        :param args: the positional arguments to fn, if any
        :param kwargs: the keyword arguments to fn, if any
        :param callback: a callback function which accepts a single argument, the return value from fn.
        The callback is called if the function exits without an exception.
        :param error_callback: a callback function which accepts a single argument, the exception value from fn.
        The callback is called if the function exits because of an unhandled exception.
        """

        self.pool.apply_async(fn, args, kwargs,
            lambda result: self._onSuccess(result, callback),
            lambda ex: self._onFailure(ex, error_callback))

    def _onSuccess(self, result, callback):
        with self._lk_result:
            self._results.append( (result, callback) )

    def _onFailure(self, ex, callback):
        with self._lk_result:
            self._results.append( (ex, callback) )

    def update(self):
        """ check for completed tasks and process the callbacks.
        """

        results = []
        if self._results:
            with self._lk_result:
                results = self._results
                self._results = []

            for result, callback in results:
                if callback:
                    try:
                        callback(result)
                    except Exception as e:
                        logging.exception("task callback failed")

    def shutdown(self):
        """ cancel running tasks and stop the task pool """

        self.pool.terminate()
        self.pool.join()

