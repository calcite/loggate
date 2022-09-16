import logging

from loggate.helper import get_level


class LowerLogLevelFilter(logging.Filter):
    """
    This filter accepts only logs with the declared or lower levels.
    """
    def __init__(self, level):
        self.level = get_level(level)

    def filter(self, record):
        return record.levelno < self.level
