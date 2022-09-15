from logging import Handler
from logging.handlers import QueueHandler, QueueListener
from queue import Queue

from .formatters import LokiLogFormatter
from .emitters import LokiEmitterV1

_defaultFormatter = LokiLogFormatter()


class LokiHandler(Handler):
    """
    Log handler that sends log records to Loki.

    `Loki API <https://github.com/grafana/loki/blob/master/docs/api.md>`_
    """

    DEFAULT_LOKI_TAGS = ['logger', 'level']
    level_tag = 'level'
    logger_tag = 'logger'

    def __init__(self, urls: [str], strategy: str = None, meta: dict = None,
                 auth: (str, str) = None, loki_tags: list[str] = None,
                 timeout: int = None, ssl_verify=True):
        """
        Create new Loki logging handler.

        :param urls: Endpoints used to send log entries to Loki
                  (e.g. [`https://my-loki-instance/loki/api/v1/push`]).
        :param strategy: to choose loki server
                  (e.g. 'all', 'random', 'fallback')
        :param meta: Default metadata added to every log record.
        :param auth: Optional tuple with username and password for
                  basic HTTP authentication.
        :param loki_tags: The list of names metadata, which will be converted to
                  loki tags.
        :param timeout: connection timeout to loki server

        """
        super(LokiHandler, self).__init__()
        self.emitter = LokiEmitterV1(self,
                                     urls=urls,
                                     strategy=strategy,
                                     auth=auth,
                                     timeout=timeout,
                                     ssl_verify=ssl_verify)
        self.meta = meta
        self.loki_tags = loki_tags if loki_tags else self.DEFAULT_LOKI_TAGS

    def handleError(self, record):
        """
        Close emitter and let default handler take actions on error.
        """
        self.emitter.close()
        super(LokiHandler, self).handleError(record)

    def format(self, record):
        fmt = self.formatter if self.formatter else _defaultFormatter
        if isinstance(fmt, LokiLogFormatter):
            return fmt.format(record, handler=self)
        return fmt.format(record)

    def emit(self, record):
        """
        Send log record to Loki.
        :param record: LogRecord
        """
        # noinspection PyBroadException
        try:
            self.emitter.emit(record, self.format(record))
        except Exception:
            self.handleError(record)


class LokiQueueHandler(QueueHandler):
    """
    This handler automatically creates listener and `LokiHandler`
    to handle logs queue.
    """

    def __init__(self, **kwargs):
        """
        Create new logger handler with the specified queue
        and kwargs for the `LokiHandler`.
        """
        super(LokiQueueHandler, self).__init__(Queue())
        self.handler = LokiHandler(**kwargs)
        self.listener = QueueListener(self.queue, self.handler)
        self.listener.start()

    def close(self) -> None:
        if hasattr(self, 'listener'):
            self.listener.stop()
            self.handler.close()

    def setFormatter(self, fmt):
        self.handler.setFormatter(fmt)

    def setLevel(self, level):
        self.handler.setLevel(level)

    def handleError(self, record):
        self.handler.handleError(record)

    def emit(self, record):
        """
        Emit a record.

        Writes the LogRecord to the queue, preparing it for pickling first.
        """
        try:
            self.enqueue(record)
        except Exception:
            self.handleError(record)
