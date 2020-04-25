'''
Utilities for data handling
Created on 25 Apr 2020

@author: simon
'''

import logging


def make_ints(values, keys):
    for key in keys:
        values[key] = [int(v) if v else 0 for v in values[key]]


def get_int(value):
    return int(value) if value else 0


def list_to_str(l: list):
    """ return a string version with str(item) for items in list """
    return [str(item) for item in l]


class TempLogLevel():
    """ context manager for temporary log level override """
    def __init__(self, level, logger='__name__'):
        self.handler = logging.getLogger(logger)
        self.saved_level = self.handler.getLevel()
        self.handler.setLevel(level)

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _exc_traceback):
        self.handler.setLevel(self.saved_level)
