import asyncio

import random
from multiprocessing import SimpleQueue
from queue import Empty
from threading import Thread, Event

import sys

from loggate.http import HttpApiCallInterface
from loggate.logger import LoggingException, LogRecord

LOKI_DEPLOY_STRATEGY_ALL = 'all'
LOKI_DEPLOY_STRATEGY_RANDOM = 'random'
LOKI_DEPLOY_STRATEGY_FALLBACK = 'fallback'

LOKI_DEPLOY_STRATEGIES = [
    LOKI_DEPLOY_STRATEGY_ALL,
    LOKI_DEPLOY_STRATEGY_RANDOM,
    LOKI_DEPLOY_STRATEGY_FALLBACK
]


class LokiWrongDeployStrategy(LoggingException): pass       # noqa: E701
class LokiServerError(LoggingException): pass  # noqa: E701


class LokiEmitterV1:
    """
    Base Loki emitter class.
    see https://github.com/grafana/loki/blob/main/docs/sources/api/_index.md#push-log-entries-to-loki       # noqa: E501
    """

    success_response_code = 204
    timeout_response_code = 1000

    def __init__(self, handler, urls, api: HttpApiCallInterface, queue,
                 strategy: str = None):
        """
        Loki Handler
        :param handler: LokiHandler
        :param urls: [str]|str loki entrypoints
                     (e.g. [http://127.0.0.1/loki/api/v1/push])
        :param strategy: str ('random', 'fallback', 'all')
        """
        if isinstance(urls, str):
            urls = [urls]
        if not strategy:
            strategy = LOKI_DEPLOY_STRATEGY_RANDOM
        strategy = strategy.lower()
        if strategy not in LOKI_DEPLOY_STRATEGIES:
            raise

        self.urls = urls
        self.strategy = strategy
        self._url_indexes = list(range(len(urls)))
        if strategy == LOKI_DEPLOY_STRATEGY_RANDOM:
            random.shuffle(self._url_indexes)

        self.handler = handler
        self.queue: SimpleQueue = queue
        self.api = api
        self.thread = None
        self.thread_stop = Event()

    def prepare_payload(self, records: [LogRecord]):
        data = []
        for record in records:
            data.append({
                'stream': self.handler.build_tags(record),
                'values': [(str(int(record.created * 1e9)),
                            self.handler.format(record))]
            })
        return {'streams': data}

    def emit(self, records):
        """
        Send log records to Loki.
        :param records: List[LogRecord]
        """
        payload = self.prepare_payload(records)
        for ix in self._url_indexes:
            status_code, msg = self.api.send_json(self.urls[ix], payload)
            if status_code == self.success_response_code:
                if self.strategy != LOKI_DEPLOY_STRATEGY_ALL:
                    return
            elif status_code == self.timeout_response_code:
                sys.stderr.write(f'loggate: The delivery logs to '
                                 f'"{self.urls[ix]}" failed.\n')

        if status_code in [self.success_response_code,
                           self.timeout_response_code]:
            return
        # TODO: make recovery strategy
        raise LokiServerError(
            f"Unexpected Loki API response status code: "
            f"{status_code} \"{msg}\"")

    async def emit_async(self, records):
        """
        Asyncio send log record to Loki.
        :param records: List[LogRecord]
        """
        payload = self.prepare_payload(records)
        for ix in self._url_indexes:
            status_code, msg = await self.api.send_json(
                self.urls[ix], payload
            )
            if status_code == self.success_response_code:
                if self.strategy != LOKI_DEPLOY_STRATEGY_ALL:
                    return
            elif status_code == self.timeout_response_code:
                sys.stderr.write(f'loggate: The delivery logs to '
                                 f'"{self.urls[ix]}" failed.\n')

        if status_code in [self.success_response_code,
                           self.timeout_response_code]:
            return
        # TODO: make recovery strategy
        raise LokiServerError(
            f"Unexpected Loki API response status code: "
            f"{status_code} \"{msg}\"")

    def close(self):
        """Close HTTP session."""
        self.thread_stop.set()
        if self.thread:
            self.thread.join()

    def start(self):
        def process():
            while not self.thread_stop.is_set():
                records = []
                try:
                    for _ in range(self.handler.max_records_in_one_request):
                        try:
                            records.append(
                                self.queue.get(
                                    block=True,
                                    timeout=self.handler.send_interval))
                        except Empty:
                            break
                    if records:
                        try:
                            self.emit(records)
                        except LokiServerError:
                            self.handler.handleError(records[0])
                except Exception as ex:
                    if sys.stderr:
                        sys.stderr.write(f"[CRITICAL LOKI ERROR]\n{ex}\n")

        self.thread = Thread(target=process, name="loggate", daemon=True)
        self.thread.start()

    def asyncio_start(self):
        async def process(is_full_asyncio):
            while not self.thread_stop.is_set():
                try:
                    records = []
                    for _ in range(self.handler.max_records_in_one_request):
                        try:
                            records.append(self.queue.get(block=False))
                        except Empty:
                            break
                    if records:
                        try:
                            if is_full_asyncio:
                                await self.emit_async(records)
                            else:
                                self.emit(records)
                        except LokiServerError:
                            self.handler.handleError(records[0])
                    else:
                        await asyncio.sleep(self.handler.send_interval)
                except Exception as ex:
                    if sys.stderr:
                        sys.stderr.write(f"[CRITICAL LOKI ERROR]\n{ex}\n")
        is_full_asyncio = asyncio.iscoroutinefunction(self.api.send_json)
        asyncio.get_event_loop().create_task(process(is_full_asyncio))
