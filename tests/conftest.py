import threading

import pytest
import requests


@pytest.fixture(autouse=True)
def no_requests(monkeypatch):
    """Remove requests.sessions.Session.request for all tests."""
    monkeypatch.delattr("requests.sessions.Session.request")


@pytest.fixture
def make_profile():
    def _make_profile(update: dict = None):
        profiles = {
            'default': {
                'formatters': {
                    'loki': {
                        'class': 'logate.loki.LokiLogFormatter'
                    }
                },
                'handlers': {
                    'loki': {
                        'class': 'logate.loki.LokiQueueHandler',
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
        def __init__(self, status_code, content='XXX'):
            self.status_code = status_code
            self.content = content

    def __init__(self, *args, **kwargs):
        self.calls = []
        self.closed = threading.Event()
        self.response_code = 204

    def post(self, *args, **kwargs):
        self.calls.append(('post', args, kwargs))
        if isinstance(self.response_code, list):
            return MockSession.MockResponse(self.response_code.pop(0))
        return MockSession.MockResponse(self.response_code)

    def close(self):
        self.closed.clear()


@pytest.fixture
def session(monkeypatch):
    _session = MockSession()
    monkeypatch.setitem(requests.__dict__, 'Session', lambda: _session)
    return _session
