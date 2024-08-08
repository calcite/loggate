import json
from urllib.request import Request

from loggate import setup_logging, get_logger


def check_call(request: Request, *args, headers=None, url='http://loki'):
    # check loki url address
    assert request.full_url == url, \
        f"Wrong loki url {request.full_url} != {url}"
    data = json.loads(request.data)
    assert len(data['streams']) > 0
    # headers
    if not headers:
        headers = {'Content-type': 'application/json; charset=utf-8'}
    for k, val in headers.items():
        request.headers[k]
    # check message
    for row in args:
        rec = data['streams'].pop(0)
        assert rec.get('stream', {}) == row[0]
        _msg = rec.get('values')[0][1]
        if not isinstance(_msg, dict):
            _msg = json.loads(_msg)
        assert _msg == row[1]


def test_simple(make_profile, session):
    """
    This is a simple test without any metadata
    """
    profiles = make_profile()
    setup_logging(profiles=profiles)

    logger = get_logger('component')
    logger.debug('Debug')
    logger.warning('Warning')
    logger.error('Error')
    logger.critical('Critical')

    session.closed.wait(.2)
    check_call(
        session.requests.pop(0),
        ({'logger': 'component', 'level': 'debug'}, {"msg": "Debug"}),
        ({'logger': 'component', 'level': 'warning'}, {"msg": "Warning"}),
        ({'logger': 'component', 'level': 'error'}, {"msg": "Error"}),
        ({'logger': 'component', 'level': 'critical'}, {"msg": "Critical"})
    )


def test_metadata(make_profile, session):
    """
    This is a test with metadata and metadata overwriting
    """
    profiles = make_profile({
        'default.handlers.loki.meta': {
            'handler_meta': '000',
            'overwriteH': 'Z'
        },
        'default.handlers.loki.loki_tags': ['logger', 'level', 'meta']
    })
    setup_logging(profiles=profiles)

    logger = get_logger('component',
                        meta={'logger_meta': 'ABC', 'overwriteL': 'X'})
    logger.debug('Debug',
                 meta={'meta': 'DEF',
                       'overwriteL': 'Y',
                       'overwriteH': '111'})
    logger.warning('Warning',
                   meta={'meta': 'GHI',
                         'overwriteL': 'Y',
                         'overwriteH': '111'})
    logger.error('Error',
                 meta={'meta': 'JKL',
                       'overwriteL': 'Y',
                       'overwriteH': '111'})
    logger.critical('Critical',
                    meta={'meta': 'MNO',
                          'overwriteL': 'Y',
                          'overwriteH': '111'})

    session.closed.wait(.2)
    check_call(session.requests.pop(0),
               ({'logger': 'component', 'level': 'debug', 'meta': 'DEF'},
                {"msg": "Debug",
                 'handler_meta': '000',
                 'logger_meta': 'ABC',
                 'overwriteH': '111',
                 'overwriteL': 'Y'}),
               ({'logger': 'component', 'level': 'warning', 'meta': 'GHI'},
                {"msg": "Warning",
                 'handler_meta': '000',
                 'logger_meta': 'ABC',
                 'overwriteH': '111',
                 'overwriteL': 'Y'
                 }),
               ({'logger': 'component', 'level': 'error', 'meta': 'JKL'},
                {"msg": "Error",
                 'handler_meta': '000',
                 'logger_meta': 'ABC',
                 'overwriteH': '111',
                 'overwriteL': 'Y'
                 }),
               ({'logger': 'component', 'level': 'critical', 'meta': 'MNO'},
                {"msg": "Critical",
                 'handler_meta': '000',
                 'logger_meta': 'ABC',
                 'overwriteH': '111',
                 'overwriteL': 'Y'
                 }))


def test_loki_all_strategy(make_profile, session):
    """
    Test strategy all. The log message is send to all servers.
    """
    servers = ['http://loki1', 'http://loki2', 'http://loki3']
    profiles = make_profile({
        'default.handlers.loki.strategy': 'all',
        'default.handlers.loki.urls': servers
    })
    setup_logging(profiles=profiles)
    logger = get_logger('component')
    logger.critical('Critical')

    session.closed.wait(.2)
    rec = ({'logger': 'component', 'level': 'critical'}, {"msg": "Critical"})
    check_call(session.requests.pop(0), rec, url=servers.pop(0))
    check_call(session.requests.pop(0), rec, url=servers.pop(0))
    check_call(session.requests.pop(0), rec, url=servers.pop(0))


def test_loki_fallback_strategy(make_profile, session, capsys):
    """
    Test strategy fallback. The log message is send to first server,
    if it failed we try to send it to others.
    """
    servers = ['http://loki1', 'http://loki2', 'http://loki3']
    profiles = make_profile({
        'default.handlers.loki.strategy': 'fallback',
        'default.handlers.loki.timeout': 3,
        'default.handlers.loki.urls': servers
    })
    session.response_code = [400, 400, 400]
    setup_logging(profiles=profiles)
    logger = get_logger('component')
    logger.critical('Critical')

    session.closed.wait(.2)
    rec = ({'logger': 'component', 'level': 'critical'}, {"msg": "Critical"})
    assert session.requests[0].kwargs['timeout'] == 3
    check_call(session.requests.pop(0), rec, url=servers.pop(0))
    check_call(session.requests.pop(0), rec, url=servers.pop(0))
    check_call(session.requests.pop(0), rec, url=servers.pop(0))
    # captured = capsys.readouterr()
    # assert '--- Logging error ---' in captured.err


def test_loki_with_auth(make_profile, session, capsys):
    """
    Test strategy fallback. The log message is send to first server,
    if it failed we try to send it to others.
    """
    profiles = make_profile({
        'default.handlers.loki.auth': ['username', 'password']
    })
    setup_logging(profiles=profiles)
    logger = get_logger('component')
    logger.critical('Critical')

    session.closed.wait(.2)

    check_call(session.requests.pop(0),
               ({'logger': 'component', 'level': 'critical'},
                {"msg": "Critical"}))
