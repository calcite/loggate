import json
import logging


class StdLogFormatter(logging.Formatter):
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
            # convert bytes to string
            record.msg = record.msg.decode('utf-8').strip()
        if record.levelname in self.FORMATS:
            # colorize output
            formatter = logging.Formatter(
                    f"{self.FORMATS[record.levelname]}"
                    "%(asctime)s\t [%(levelname)s] %(name)s"
                    f":{self.RESET} %(message)s")
            msg = formatter.format(record)
        else:
            msg = super().format(record)
        if record.tags:
            # show tags
            try:
                extra = json.dumps(record.tags)
                return f'{msg}\n\t\t\t\t{self.GRAY}{extra}{self.RESET}'
            finally:
                pass
        return msg
