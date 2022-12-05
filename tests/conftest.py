import threading
import urllib

import aiohttp
import pytest


@pytest.fixture
def make_profile():
    def _make_profile(update: dict = None):
        profiles = {
            'default': {
                'disable_existing_loggers': True,
                'formatters': {
                    'loki': {
                        'class': 'loggate.loki.LokiLogFormatter'
                    }
                },
                'handlers': {
                    'loki': {
                        'class': 'loggate.loki.LokiThreadHandler',
                        'formatter': 'loki',
                        'urls': ['http://loki'],
                        'send_interval': 0.1
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

        def read(self):
            return b''

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


class MockAsyncSession:
    class MockResponse:
        def __init__(self, status):
            self.status = status

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def text(self):
            return ''

    def __init__(self, *args, **kwargs):
        self.requests = []
        self.closed = threading.Event()
        self.response_code = 204
        self.client = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def post(self, url, **kwargs):
        request = {'url': url}
        request.update(kwargs)
        request.update(self.client)
        # print(request)
        self.requests.append(request)
        if isinstance(self.response_code, list):
            return MockAsyncSession.MockResponse(self.response_code.pop(0))
        return MockAsyncSession.MockResponse(self.response_code)

    def get_client(self, **kwargs):
        self.client = {}
        self.client.update(kwargs)
        return self


@pytest.fixture
def async_session(monkeypatch):
    __session = MockAsyncSession()
    monkeypatch.setattr(aiohttp, 'ClientSession', __session.get_client)
    return __session
