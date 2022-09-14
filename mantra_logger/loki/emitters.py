import random
from typing import Any, Dict, Optional, Tuple
import requests

from mantra_logger.logger import LoggingException

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

    def __init__(self, handler, urls, strategy: str = None,
                 auth: Optional[Tuple[str, str]] = None,
                 timeout: int = None):
        """
        Loki Handler
        :param urls: [str]|str loki url
                     (e.g. [http://127.0.0.1/loki/api/v1/push])
        :param auth: Tuple[str, str] tuple with username and password.
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
        self.__url_indexes = list(range(len(urls)))
        if strategy == LOKI_DEPLOY_STRATEGY_RANDOM:
            random.shuffle(self.__url_indexes)
        self.timeout = int(timeout) if timeout else 30
        self.auth = auth
        self._session = None
        self.__handler = handler

    def emit(self, record, line):
        """
        Send log record to Loki.
        :param record: LogRecord
        """
        payload = {
            "streams": [{
                "stream": self.build_tags(record),
                "values": [(int(record.created * 1e9), line)]
            }]
        }
        for ix in self.__url_indexes:
            resp = self.session.post(self.urls[ix],
                                     json=payload, timeout=self.timeout)
            # print(f'{self.urls[ix]} - {resp.status_code}')
            if self.strategy != LOKI_DEPLOY_STRATEGY_ALL \
                    and resp.status_code == self.success_response_code:
                return
        if resp.status_code == self.success_response_code:
            return
        raise ValueError(
            f"Unexpected Loki API response status code: {resp.status_code}",
            resp.content)

    @property
    def session(self) -> requests.Session:
        """Create HTTP session."""
        if self._session is None:
            self._session = requests.Session()
            self._session.auth = self.auth or None
        return self._session

    def close(self):
        """Close HTTP session."""
        if self._session is not None:
            self._session.close()
            self._session = None

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
