import random
import sys
from typing import Any, Dict

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


class LokiEmitterV1:
    """
    Base Loki emitter class.
    see https://github.com/grafana/loki/blob/main/docs/sources/api/_index.md#push-log-entries-to-loki       # noqa: E501
    """

    success_response_code = 204
    timeout_response_code = 1000

    def __init__(self, handler, urls, api: HttpApiCallInterface,
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

        self.__handler = handler
        self.api = api

    def prepare_payload(self, record: LogRecord, line):
        return {
            'streams': [{
                'stream': self.build_tags(record),
                'values': [(str(int(record.created * 1e9)), line)]
            }]
        }

    def emit(self, record, line):
        """
        Send log record to Loki.
        :param record: LogRecord
        """
        for ix in self._url_indexes:
            status_code, msg = self.api.send_json(
                self.urls[ix],
                self.prepare_payload(record, line)
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
        raise ValueError(
            f"Unexpected Loki API response status code: "
            f"{status_code} \"{msg}\"")

    def close(self):
        """Close HTTP session."""
        pass

    def build_tags(self, record) -> Dict[str, Any]:
        """
        Prepare tags
        :param record: LogRecord
        :return:  Dict[str, Any]
        """
        meta = {}
        if hasattr(self.__handler, 'meta') and self.__handler.meta:
            meta = self.__handler.meta.copy()
        meta[self.__handler.level_tag] = record.levelname.lower()
        meta[self.__handler.logger_tag] = record.name
        meta.update(getattr(record, "meta", {}))

        return {key: val for key, val in meta.items()
                if key in self.__handler.loki_tags}


class LokiAsyncEmitterV1(LokiEmitterV1):

    async def emit(self, record, line):
        """
        Send log record to Loki.
        :param record: LogRecord
        """
        for ix in self._url_indexes:
            status_code, msg = await self.api.send_json(
                self.urls[ix],
                self.prepare_payload(record, line)
            )
            if self.strategy != LOKI_DEPLOY_STRATEGY_ALL \
                    and status_code == self.success_response_code:
                return
        if status_code == self.success_response_code:
            return
        # TODO: make recovery strategy
        raise ValueError(
            f"Unexpected Loki API response status code: "
            f"{status_code} \"{msg}\"")
