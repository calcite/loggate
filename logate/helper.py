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
