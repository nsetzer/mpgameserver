
import unittest
import logging
import os
from fnmatch import fnmatch
import argparse

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

def matcher(patterns):
    def match(test):
        # qualname example: ConnectionTestCase.test_conn_fragment
        s = getattr(test, test._testMethodName).__qualname__
        for p in patterns:
            if fnmatch(s, p):
                return True
        return False
    return match

def main():

    parser = argparse.ArgumentParser(description='Process some integers.')

    parser.add_argument('-v', '--verbose', action='count', default=0,
                    help='set verbosity')

    parser.add_argument('-f', '--filter', action='append',
                    help='test filter')

    args = parser.parse_args()

    if args.verbose >= 3:
        logging.basicConfig(level=logging.ERROR) # disable logging
        verbose = 2
    else:
        logging.basicConfig(level=100) # disable logging
        verbose = args.verbose


    pattern = '*_test.py'
    test_loader = unittest.defaultTestLoader
    test_runner = unittest.TextTestRunner(verbosity=verbose)
    test_suite = test_loader.discover("./tests", pattern=pattern)

    if args.filter:
        match = matcher(args.filter)
        for lvl0 in test_suite._tests:
            for lvl1 in lvl0._tests:
                if hasattr(lvl1, '_tests'):
                    lvl1._tests = [test for test in lvl1._tests if match(test)]

                #for test in lvl1._tests:
                #    print(getattr(test, test._testMethodName).__qualname__)

    return test_runner.run(test_suite)

if __name__ == '__main__':
    main()
