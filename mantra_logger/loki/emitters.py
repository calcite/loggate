from typing import Any, Dict, Optional, Tuple, List

import requests


class LokiEmitterV1:
    """
    Base Loki emitter class.
    see https://github.com/grafana/loki/blob/main/docs/sources/api/_index.md#push-log-entries-to-loki
    """

    DEFAULT_TAGS = ['logger', 'level']

    level_tag = 'level'
    logger_tag = 'logger'
    timeout = 30            # seconds
    success_response_code = 204

    def __init__(self, urls: [str],
                 meta: Optional[dict] = None,
                 auth: Optional[Tuple[str, str]] = None,
                 tags: Optional[List[str]] = None) -> None:
        """
        Loki Handler
        :param urls: str loki url (e.g. [http://127.0.0.1/loki/api/v1/push])
        :param meta: dict metadata that will be added to all records handled
        by this handler.
        :param auth: Touple[str, str] tuple with username and password.
        """

        self.meta = meta or {}
        self.url = urls[0]
        self.auth = auth
        self._session = None
        self.tags = tags if tags else self.DEFAULT_TAGS

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
        resp = self.session.post(self.url, json=payload, timeout=self.timeout)
        if resp.status_code != self.success_response_code:
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
        meta = self.meta.copy()
        meta[self.level_tag] = record.levelname.lower()
        meta[self.logger_tag] = record.name
        meta.update(getattr(record, "meta", {}))

        return {key: val for key, val in meta.items()
                if key in self.tags}

