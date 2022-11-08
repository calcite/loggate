import logging
import sys


class LogColorFormatter(logging.Formatter):
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

    COLORS = {
        'COLOR_RED': RED,
        'COLOR_GREEN': GREEN,
        'COLOR_YELLOW': YELLOW,
        'COLOR_BLUE': BLUE,
        'COLOR_PURPLE': PURPLE,
        'COLOR_GRAY': GRAY,
        'COLOR_RESET': RESET,
        'COLOR_DEBUG': BLUE,
        'COLOR_INFO': GREEN,
        'COLOR_WARNING': YELLOW,
        'COLOR_ERROR': RED,
        'COLOR_CRITICAL': PURPLE,
        'COLOR_METADATA': GRAY,
        'COLOR_TRACEBACK': None
    }

    INDENTATION_TRACEBACK = '    '
    INDENTATION_METADATA = '\t\t\t\t'

    def __init__(self, fmt=None, datefmt=None, style='%', validate=True,
                 **kwargs):
        """
        This is stdout/sterr formatter.

        :param fmt: str - standard log formatter template + we can use colors.
                        %(COLOR_RED)s Red Text %(COLOR_RESET)s
                        %(LEVEL_COLOR)s Color by log level %(COLOR_RESET)s
        :param datefmt: str
        :param style: str
        :param validate: bool
        :param kwargs: we can overwrite COLORS_* by this.
        """
        if not fmt:
            fmt = "%(LEVEL_COLOR)s%(asctime)s\t [%(levelname)s] " \
                  "%(name)s:%(COLOR_RESET)s %(message)s"
        if sys.version_info.minor < 8:
            super(LogColorFormatter, self).__init__(fmt, datefmt, style)
        else:
            super(LogColorFormatter, self).__init__(fmt, datefmt, style,
                                                    validate)
        if 'TRACEBACK_INDENTATION' in kwargs:
            self.TRACEBACK_INDENTATION = kwargs.get('TRACEBACK_INDENTATION')
        if 'METADATA_INDENTATION' in kwargs:
            self.METADATA_INDENTATION = kwargs.get('METADATA_INDENTATION')
        for key, val in kwargs.items():
            if key.startswith('COLOR_'):
                if val.startswith('#'):
                    val = self.COLORS.get(val[1:], val)
                self.COLORS[key] = val

    def format(self, record: logging.LogRecord) -> str:
        if isinstance(record.msg, bytes):
            # convert bytes to string
            record.msg = record.msg.decode('utf-8').strip()
        record.__dict__.update(self.COLORS)
        record.LEVEL_COLOR = \
            self.COLORS.get(f'COLOR_{record.levelname.upper()}', '')

        record.message = record.getMessage()
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)
        s = self.formatMessage(record)
        if hasattr(record, 'meta') and record.meta:
            s += f'{self.COLORS["COLOR_METADATA"]}\n' \
                 f'{self.INDENTATION_METADATA}' \
                 f'{record.meta}{self.COLORS["COLOR_RESET"]}'
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if s[-1:] != "\n":
                s = s + "\n"
            _trace_color = record.LEVEL_COLOR
            if self.COLORS['COLOR_TRACEBACK']:
                _trace_color = self.COLORS['COLOR_TRACEBACK']

            trace = record.exc_text.replace('\n',
                                            f'\n{self.INDENTATION_TRACEBACK}')
            s += f'{self.INDENTATION_TRACEBACK}{_trace_color}' \
                 f'{trace}{self.COLORS["COLOR_RESET"]}'
        if record.stack_info:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + self.formatStack(record.stack_info)
        return s
