from logging import Handler
from logging.handlers import QueueHandler, QueueListener
from queue import Queue


from .emitters import LokiEmitterV1


class LokiHandler(Handler):
    """
    Log handler that sends log records to Loki.

    `Loki API <https://github.com/grafana/loki/blob/master/docs/api.md>`_
    """

    def __init__(self, urls: [str], tags: dict = None, auth: (str, str) = None):
        """
        Create new Loki logging handler.

        Arguments:
            urls: Endpoints used to send log entries to Loki
                  (e.g. [`https://my-loki-instance/loki/api/v1/push`]).
            tags: Default tags added to every log record.
            auth: Optional tuple with username and password for
                  basic HTTP authentication.

        """
        super(LokiHandler, self).__init__()
        self.emitter = LokiEmitterV1(urls, tags, auth)

    def handleError(self, record):
        """
        Close emitter and let default handler take actions on error.
        """
        self.emitter.close()
        super(LokiHandler, self).handleError(record)

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

