import json
import logging

LOKI_LABELS = {}

class BaseLogFormatter(logging.Formatter):
    REGULAR_ATTRIBUTES = None

    def __init__(self, fmt=None, datefmt=None, style='%', validate=True):
        super().__init__(fmt, datefmt, style, validate)
        if not self.REGULAR_ATTRIBUTES:
            pattern = logging.LogRecord('', 10, '', 0, '', None, None)
            self.REGULAR_ATTRIBUTES = set(pattern.__dict__.keys())
            self.REGULAR_ATTRIBUTES.add('tags')

    def get_extra_attributes(self, record, ignore=None):
        res = {}
        attrs = set(ignore if ignore else [])\
            .union(self.REGULAR_ATTRIBUTES, LOKI_LABELS)
        try:
            for key in record.__dict__.keys():
                if key not in attrs:
                    val = getattr(record, key)
                    if isinstance(val, bytes):
                        val = val.decode('utf-8')
                    res[key] = val
        finally:
            pass
        return res


class LogFormatter(BaseLogFormatter):
    """
    Logger for stdout/stderr
    """
    RED = "\x1b[1;31m"
    GREEN = "\x1b[1;32m"
    YELLOW = "\x1b[1;33m"
    BLUE = "\x1b[1;34m"
    PURPLE = '\x1b[1;35m'
    GRAY = "\x1b[1;36m"
    RESET = "\x1b[0m"

    FORMATS = {
        'DEBUG': BLUE,
        'INFO': GREEN,
        'WARNING': YELLOW,
        'ERROR': RED,
        'CRITICAL': PURPLE
    }

    def format(self, record: logging.LogRecord) -> str:
        if isinstance(record.msg, bytes):
            record.msg = record.msg.decode('utf-8').strip()
        if record.levelname in self.FORMATS:
            formatter = logging.Formatter(
                    f"{self.FORMATS[record.levelname]}"
                    "%(asctime)s\t [%(levelname)s] %(name)s"
                    f":{self.RESET} %(message)s")
            msg = formatter.format(record)
        else:
            msg = super().format(record)
        if record.tags:
            try:
                extra = json.dumps(record.tags)
                return f'{msg}\n\t\t\t\t{self.GRAY}{extra}{self.RESET}'
            finally:
                pass
        return msg


class LokiLogFormatter(BaseLogFormatter):
    """
    Loki formatter
    """
    def format(self, record: logging.LogRecord) -> str:
        res = {}
        if isinstance(record.msg, dict):
            res = record.msg
        elif isinstance(record.msg, bytes):
            record.msg = record.msg.decode('utf-8').strip()
        res.update({
            'msg': record.getMessage(),
            'thread_name': record.threadName,
            'fw_version': FIRMWARE_VERSION,
            'mbox_version': MBOXOS_VERSION
        })
        res.update(self.get_extra_attributes(record))
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            res['exception'] = record.exc_text
        if record.stack_info:
            res['stack'] = self.formatStack(record.stack_info)
        return json.dumps(res)
