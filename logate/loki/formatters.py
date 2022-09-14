import json
import logging


class LokiLogFormatter(logging.Formatter):
    """
    Loki formatter
    """

    def format(self, record: logging.LogRecord, handler=None) -> str:
        res = {}
        if isinstance(record.msg, dict):
            # overwriting whole record
            res = record.msg
            record.msg = record.msg.get('msg', '')
        if isinstance(record.msg, bytes):
            # convert bytes to string
            record.msg = record.msg.decode('utf-8').strip()
        res['msg'] = record.getMessage()
        loki_tags = []
        if handler:
            if hasattr(handler, 'loki_tags'):
                loki_tags = handler.loki_tags
            if hasattr(handler, 'meta') and handler.meta:
                res.update({key: val for key, val in handler.meta.items()
                            if key not in loki_tags})
        if hasattr(record, 'meta') and record.meta:
            res.update({key: val for key, val in record.meta.items()
                       if key not in loki_tags})
        if record.exc_info:
            res['exception'] = "\n" + self.formatException(record.exc_info)
        if record.stack_info:
            res['stack'] = self.formatStack(record.stack_info)
        return json.dumps(res)
