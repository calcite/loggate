from logging import critical, error, exception, warning, warn, info, debug, log
from logging import DEBUG, INFO, WARNING, ERROR, FATAL, CRITICAL, NOTSET

nameToLevel = {
    'CRITICAL': CRITICAL,
    'FATAL': FATAL,
    'ERROR': ERROR,
    'WARN': WARNING,
    'WARNING': WARNING,
    'INFO': INFO,
    'DEBUG': DEBUG,
    'NOTSET': NOTSET,
}


def get_level(level):
    if isinstance(level, str):
        return nameToLevel.get(level)
    return level


from .logger import getLogger, get_logger, setup_logging, Logger
from .filters import LowerLogLevelFilter
from .formatters import LogColorFormatter
