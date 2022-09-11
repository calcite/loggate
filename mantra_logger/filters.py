import logging

from mantra_logger.helper import get_level


class LogLevelFilter(logging.Filter):
    def __init__(self, level):
        self.level = get_level(level)

    def filter(self, record):
        return record.levelno < self.level
