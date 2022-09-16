import threading
import urllib

import pytest


@pytest.fixture
def make_profile():
    def _make_profile(update: dict = None):
        profiles = {
            'default': {
                'formatters': {
                    'loki': {
                        'class': 'loggate.loki.LokiLogFormatter'
                    }
                },
                'handlers': {
                    'loki': {
                        'class': 'loggate.loki.LokiQueueHandler',
                        'formatter': 'loki',
                        'urls': ['http://loki'],
                    }
                },
                'loggers': {
                    'root': {
                        'handlers': ['loki'],
                        'level': 'DEBUG'
                    }
                }
            }
        }
        if update:
            for key, val in update.items():
                keys = key.split('.')
                attr = keys.pop()
                item = profiles
                while keys:
                    _k = keys.pop(0)
                    if _k not in item:
                        item[_k] = {}
                    item = item[_k]
                item[attr] = val
        return profiles
    return _make_profile


class MockSession:

    class MockResponse:
        def __init__(self, status):
            self.status = status

    def __init__(self, *args, **kwargs):
        self.requests = []
        self.closed = threading.Event()
        self.response_code = 204

    def send(self, request, **kwargs):
        request.kwargs = kwargs
        self.requests.append(request)
        if isinstance(self.response_code, list):
            return MockSession.MockResponse(self.response_code.pop(0))
        return MockSession.MockResponse(self.response_code)


@pytest.fixture
def session(monkeypatch):
    _session = MockSession()
    monkeypatch.setattr(urllib.request, 'urlopen', _session.send)
    return _session
