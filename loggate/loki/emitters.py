import base64
import json
import random
import ssl
import urllib.request
from typing import Any, Dict, Optional, Tuple

from loggate.logger import LoggingException

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
                 timeout: int = None, ssl_verify=True):
        """
        Loki Handler
        :param handler: LokiHandler
        :param urls: [str]|str loki entrypoints
                     (e.g. [http://127.0.0.1/loki/api/v1/push])
        :param strategy: str ('random', 'fallback', 'all')
        :param auth: (str, str) - username, password
        :param timeout int - timeout in seconds
        :param ssl_verify bool - check ssl server certificate
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
        self.timeout = int(timeout) if timeout else 5
        # auth
        self.__auth = None
        if auth:
            self.__auth = base64.b64encode(f'{auth[0]}:{auth[1]}'
                                           .encode('utf8')).decode()
        self.ctx = ssl.create_default_context()
        if not ssl_verify:
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE
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
            jsondata = json.dumps(payload).encode('utf-8')
            request = urllib.request.Request(self.urls[ix],
                                             data=jsondata,
                                             method='POST')
            request.add_header('Content-Type',
                               'application/json; charset=utf-8')
            request.add_header('Content-Length',
                               len(jsondata))
            if self.__auth:
                request.add_header("Authorization", "Basic %s" % self.__auth)
            resp = urllib.request.urlopen(
                request,
                timeout=self.timeout,
                context=self.ctx
            )
            if self.strategy != LOKI_DEPLOY_STRATEGY_ALL \
                    and resp.status == self.success_response_code:
                return
        if resp.status == self.success_response_code:
            return

        # TODO: make recovery strategy
        raise ValueError(
            f"Unexpected Loki API response status code: {resp.status}")

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
