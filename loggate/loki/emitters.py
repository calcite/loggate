import asyncio
import time

import random
from threading import Thread, Event

import sys
from typing import List

from loggate.http import HttpApiCallInterface
from loggate.logger import LoggingException, LogRecord
from loggate.loki.confirmation_queue import ConfirmatrionQueue

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

    def __get_new_generator(self):
        def generator():
            for value in self.send_retry:
                yield value

            while True:
                yield self.send_retry[-1]
        return generator()

    def __init__(self, handler, urls, api: HttpApiCallInterface,
                 queue: ConfirmatrionQueue, strategy: str = None,
                 send_retry=None):
        """
        Loki Handler
        :param handler: LokiHandler
        :param urls: [str]|str loki entrypoints
                     (e.g. [http://127.0.0.1/loki/api/v1/push])
        :param strategy: str ('random', 'fallback', 'all')
        :param send_retry: list|str interval of send retry (in seconds)
        """
        if isinstance(urls, str):
            urls = [urls]
        if not strategy:
            strategy = LOKI_DEPLOY_STRATEGY_RANDOM
        strategy = strategy.lower()
        if strategy not in LOKI_DEPLOY_STRATEGIES:
            raise
        self.urls = urls
        if strategy == LOKI_DEPLOY_STRATEGY_RANDOM:
            random.shuffle(self.urls)
        self.strategy = strategy
        self.handler = handler
        self.queue: ConfirmatrionQueue = queue
        self.api = api
        if send_retry is None:
            self.send_retry = [5, 5, 10, 10, 30, 30, 60, 60, 120]
        elif isinstance(send_retry, str):
            self.send_retry = [int(it) for it in send_retry.split(',')]
        else:
            self.send_retry = send_retry
        self.thread = None
        self.thread_stop = Event()

    @property
    def entrypoint(self):
        return self.urls[0]

    def rotate_entrypoints(self):
        self.urls.append(self.urls.pop(0))

    def prepare_payload(self, records: List[LogRecord]):
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
        res = False
        for entrypoint in self.urls:
            status_code, msg = self.api.send_json(entrypoint, payload)
            if status_code == self.success_response_code:
                res |= True
                if self.strategy != LOKI_DEPLOY_STRATEGY_ALL:
                    break
        if not res:
            raise LokiServerError(f'Loki API response status code: {status_code} "{msg}"')

    async def emit_async(self, records):
        """
        Asyncio send log record to Loki.
        :param records: List[LogRecord]
        """
        payload = self.prepare_payload(records)
        res = False
        for entrypoint in self.urls:
            status_code, msg = await self.api.send_json(entrypoint, payload)
            if status_code == self.success_response_code:
                res |= True
                if self.strategy != LOKI_DEPLOY_STRATEGY_ALL:
                    break
        if not res:
            raise LokiServerError(f'Loki API response status code: {status_code} "{msg}"')

    def close(self):
        """Close HTTP session."""
        self.thread_stop.set()
        if self.thread:
            self.thread.join()

    def start(self):
        def process():
            wait_gen = None
            while not self.thread_stop.is_set():
                records = self.queue.gets(
                    number=self.handler.max_records_in_one_request,
                    block=True,
                    timeout=self.handler.send_interval
                )
                if records:
                    try:
                        self.emit(records)
                        self.queue.confirm()
                        wait_gen = None
                    except LokiServerError:
                        if not wait_gen:
                            wait_gen = self.__get_new_generator()
                        wait_sec = next(wait_gen)
                        # from loggate.logger import getLogger
                        # getLogger('loggate.loki').warning(
                        #     "Sending of the log messages failed.",
                        #     meta={
                        #         'privileged': True,
                        #         'max_size': self.queue.max_size,
                        #         'queue_size': self.queue.qsize()
                        #     }
                        # )
                        time.sleep(wait_sec)
                    except Exception as ex:
                        from loggate.logger import getLogger
                        getLogger('loggate.loki').exception(
                            ex,
                            meta={'privileged': True}
                        )
                        if sys.stderr:
                            sys.stderr.write(f"[LOKI ERROR]\n{ex}\n")
                        # If there are problematic message we drop it.
                        self.queue.confirm()

        self.thread = Thread(target=process, name="loggate", daemon=True)
        self.thread.start()

    def asyncio_start(self):
        async def process(is_full_asyncio):
            wait_gen = None
            while not self.thread_stop.is_set():
                records = self.queue.gets(
                    self.handler.max_records_in_one_request,
                    block=False,
                )
                if records:
                    try:
                        if is_full_asyncio:
                            await self.emit_async(records)
                        else:
                            self.emit(records)
                        self.queue.confirm()
                    except LokiServerError:
                        if not wait_gen:
                            wait_gen = self.__get_new_generator()
                        wait_sec = next(wait_gen)
                        # from loggate.logger import getLogger
                        # getLogger('loggate.loki').warning(
                        #     "Sending of the log messages failed.",
                        #     meta={
                        #         'privileged': True,
                        #         'max_size': self.queue.max_size,
                        #         'queue_size': self.queue.qsize()
                        #     }
                        # )
                        await asyncio.sleep(wait_sec)
                    except Exception as ex:
                        if sys.stderr:
                            sys.stderr.write(f"[LOKI ERROR]\n{ex}\n")
                        # If there are problematic message we drop it.
                        self.queue.confirm()
                else:
                    await asyncio.sleep(self.handler.send_interval)
        is_full_asyncio = asyncio.iscoroutinefunction(self.api.send_json)
        asyncio.get_event_loop().create_task(process(is_full_asyncio))
