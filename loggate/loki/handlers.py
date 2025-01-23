from logging import Handler
from loggate.loki.confirmation_queue import ConfirmatrionQueue
from typing import Dict, Any, List

from .formatters import LokiLogFormatter
from .emitters import LokiEmitterV1
from ..http.simple_api_call import SimpleApiCall

_defaultFormatter = LokiLogFormatter()


class LokiHandlerBase(Handler):
    """
    `Loki API <https://github.com/grafana/loki/blob/master/docs/api.md>`_
    """

    DEFAULT_LOKI_TAGS = ['logger', 'level']
    level_tag = 'level'
    logger_tag = 'logger'

    def __init__(self, meta: dict = None, loki_tags=None, send_interval=1,
                 max_records_in_one_request=0, max_queue_size=0):
        """
        Create new Loki logging handler.

        :param meta: Default metadata added to every log record.
        :param loki_tags: The list of names metadata, which will be converted to
                  loki tags.
        """
        super().__init__()
        self.queue = ConfirmatrionQueue(max_queue_size)
        self.meta = meta
        self.loki_tags = loki_tags if loki_tags else self.DEFAULT_LOKI_TAGS
        self.send_interval = send_interval
        self.max_records_in_one_request = 100
        if max_records_in_one_request > 0:
            self.max_records_in_one_request = max_records_in_one_request
        if max_queue_size > 0 and\
                max_queue_size <= self.max_records_in_one_request:
            self.max_records_in_one_request = max(1, max_queue_size - 1)
        self.shown_message_about_full_queue = 0

    def format(self, record):
        fmt = self.formatter if self.formatter else _defaultFormatter
        if isinstance(fmt, LokiLogFormatter):
            return fmt.format(record, handler=self)
        return fmt.format(record)

    def build_tags(self, record) -> Dict[str, Any]:
        """
        Prepare tags
        :param record: LogRecord
        :return:  Dict[str, Any]
        """
        meta = {}
        if hasattr(self, 'meta') and self.meta:
            meta = self.meta.copy()
        meta[self.level_tag] = record.levelname.lower()
        meta[self.logger_tag] = record.name
        meta.update(getattr(record, "meta", {}))
        return {key: val for key, val in meta.items() if key in self.loki_tags}

    def emit(self, record):
        """
        Save record to the queue.
        """
        try:
            privileged = getattr(record, 'meta', {}).get('privileged', False)
            res = self.queue.put_nowait(record, privileged=privileged)
            if res and not privileged:
                # The queue is not full
                self.shown_message_about_full_queue = 0
            elif not res:
                from loggate.logger import getLogger
                if not privileged and self.shown_message_about_full_queue == 0:
                    # The queue is full, but still accept privileged messages
                    self.shown_message_about_full_queue = 1
                    getLogger('loggate.loki').error(
                        "Loki Queue is full. All next non-privileged log "
                        "records will be dropped.",
                        meta={
                            'privileged': True,
                            'max_size': self.queue.max_size,
                            'queue_size': self.queue.qsize()
                        }
                    )
                elif privileged and self.shown_message_about_full_queue != 2:
                    # The queue is really full, we don't accept any messages.
                    self.shown_message_about_full_queue = 2
                    getLogger('loggate.loki').critical(
                        "Loki Queue is full. Any next log records will be "
                        "dropped.",
                        meta={
                            'privileged': True,
                            'max_size': self.queue.max_size,
                            'queue_size': self.queue.qsize()
                        }
                    )
        except Exception:
            self.handleError(record)


class LokiHandler(LokiHandlerBase):
    """
    Log handler that sends log records to Loki.
    This type of Loki handler is blocking. It means, when we call log method
    (debug, ... critical) the message is sent in the same thread. We should use
     this only for tiny scripts where other ways have a big overhead.
    """

    def __init__(self, urls: List[str], strategy: str = None,
                 meta: dict = None, auth=None, loki_tags=None,
                 timeout=None, ssl_verify=True, send_retry=None,
                 max_queue_size=0):
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
        :param send_retry: list of waiting seconds
               to retry sending loki messages
        :param max_queue_size: max queue size

        """
        super().__init__(
            meta,
            loki_tags,
            max_queue_size=max_queue_size
        )
        api = SimpleApiCall(auth=auth, timeout=timeout, ssl_verify=ssl_verify)
        self.emitter = LokiEmitterV1(
            self,
            urls=urls,
            api=api,
            queue=self.queue,
            strategy=strategy,
            send_retry=send_retry
        )

    def emit(self, record):
        """
        Send record.
        """
        try:
            self.emitter.emit([record])
        except Exception:
            self.handleError(record)


class LokiThreadHandler(LokiHandlerBase):
    """
    This type of Loki handler is non-blocking.
    The sending of messages is done in separate thread.
    This type of handler we should use as default.
    """

    def __init__(self, urls: List[str], strategy: str = None,
                 meta: dict = None, auth=None, loki_tags=None,
                 timeout=None, ssl_verify=True, send_interval=1,
                 max_records_in_one_request=0, send_retry=None,
                 max_queue_size=0):
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
        :param send_interval: max period (in second) for send logs,
               how long we should wait, if the queue is empty and
               number messages is less than max_records_in_one_request
        :param max_records_in_one_request: maximal number of log messages
               in the one send
        :param send_retry: list of waiting seconds
               to retry sending loki messages
        :param max_queue_size: max queue size
        """
        super().__init__(
            meta=meta,
            loki_tags=loki_tags,
            send_interval=send_interval,
            max_records_in_one_request=max_records_in_one_request,
            max_queue_size=max_queue_size
        )
        api = SimpleApiCall(auth=auth, timeout=timeout, ssl_verify=ssl_verify)
        self.emitter = LokiEmitterV1(
            self,
            urls=urls,
            api=api,
            queue=self.queue,
            strategy=strategy,
            send_retry=send_retry
        )
        self.emitter.start()

    def close(self) -> None:
        self.emitter.close()
        super().close()


class LokiAsyncioHandler(LokiHandlerBase):
    def __init__(self, urls: List[str], strategy: str = None,
                 meta: dict = None, auth=None, loki_tags=None,
                 timeout=None, ssl_verify=True, send_interval=1,
                 max_records_in_one_request=0, send_retry=None,
                 max_queue_size=0):
        """
            Create new Loki logging handler.

            :param urls: Endpoints used to send log entries to Loki
                      (e.g. [`https://my-loki-instance/loki/api/v1/push`]).
            :param strategy: to choose loki server
                      (e.g. 'all', 'random', 'fallback')
            :param meta: Default metadata added to every log record.
            :param auth: Optional tuple with username and password for
                      basic HTTP authentication.
            :param loki_tags: The list of names metadata, which will
                              be converted to loki tags.
            :param timeout: connection timeout to loki server
            :param send_interval: max period (in second) for send logs,
                   how long we should wait, if the queue is empty and
                   number messages is less than max_records_in_one_request
            :param max_records_in_one_request: maximal number of log messages
                   in the one send
            :param send_retry: list of waiting seconds
                to retry sending loki messages
            :param max_queue_size: max queue size
        """
        super().__init__(
            meta=meta,
            loki_tags=loki_tags,
            send_interval=send_interval,
            max_records_in_one_request=max_records_in_one_request,
            max_queue_size=max_queue_size,
        )
        try:
            from ..http.aio_api_call import AIOApiCall
            api = AIOApiCall(auth=auth, timeout=timeout, ssl_verify=ssl_verify)
        except ImportError:
            api = SimpleApiCall(auth=auth, timeout=timeout,
                                ssl_verify=ssl_verify)
        self.emitter = LokiEmitterV1(
            self,
            urls=urls,
            api=api,
            queue=self.queue,
            strategy=strategy,
            send_retry=send_retry
        )
        self.emitter.asyncio_start()

    def close(self) -> None:
        self.emitter.close()
        super().close()
