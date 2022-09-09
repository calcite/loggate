import json
import logging


class LokiLogFormatter(logging.Formatter):
    """
    Loki formatter
    """

    def format(self, record: logging.LogRecord) -> str:
        res = {}
        if isinstance(record.msg, dict):
            # overwriting whole record
            res = record.msg
        elif isinstance(record.msg, bytes):
            # convert bytes to string
            record.msg = record.msg.decode('utf-8').strip()
        res['msg'] = record.getMessage()
        # res.update(self.get_extra_attributes(record))
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            res['exception'] = record.exc_text
        if record.stack_info:
            res['stack'] = self.formatStack(record.stack_info)
        return json.dumps(res)
