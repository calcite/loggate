import json

from logate import setup_logging, get_logger


def check_call(call, labels, msg, server='http://loki'):
    _, args, kwargs = call
    # check server
    assert len(args) == 1,  f"Wrong number args params {args}"
    assert args[0] == server, f"Wrong loki server {args[0]} != {server}"
    # check labels
    assert 'json' in kwargs
    assert 'streams' in kwargs['json']
    assert 'stream' in kwargs['json']['streams'][0]
    assert labels == kwargs['json']['streams'][0]['stream']
    # check message
    assert len(kwargs['json']['streams'][0]['values']) > 0
    _msg = kwargs['json']['streams'][0]['values'][0][1]
    if isinstance(msg, dict):
        _msg = json.loads(_msg)
    assert msg == _msg


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

    session.closed.wait(.1)
    check_call(session.calls.pop(0),
               {'logger': 'component', 'level': 'debug'},
               {"msg": "Debug"})
    check_call(session.calls.pop(0),
               {'logger': 'component', 'level': 'warning'},
               {"msg": "Warning"})
    check_call(session.calls.pop(0),
               {'logger': 'component', 'level': 'error'},
               {"msg": "Error"})
    check_call(session.calls.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"})


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
                       'overwriteH': '111'
                })
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

    session.closed.wait(.1)
    check_call(session.calls.pop(0),
               {'logger': 'component', 'level': 'debug', 'meta': 'DEF'},
               {"msg": "Debug",
                'handler_meta': '000',
                'logger_meta': 'ABC',
                'overwriteH': '111',
                'overwriteL': 'Y'})
    check_call(session.calls.pop(0),
               {'logger': 'component', 'level': 'warning', 'meta': 'GHI'},
               {"msg": "Warning",
                'handler_meta': '000',
                'logger_meta': 'ABC',
                'overwriteH': '111',
                'overwriteL': 'Y'
                })
    check_call(session.calls.pop(0),
               {'logger': 'component', 'level': 'error', 'meta': 'JKL'},
               {"msg": "Error",
                'handler_meta': '000',
                'logger_meta': 'ABC',
                'overwriteH': '111',
                'overwriteL': 'Y'
                })
    check_call(session.calls.pop(0),
               {'logger': 'component', 'level': 'critical', 'meta': 'MNO'},
               {"msg": "Critical",
                'handler_meta': '000',
                'logger_meta': 'ABC',
                'overwriteH': '111',
                'overwriteL': 'Y'
                })


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

    session.closed.wait(.1)
    check_call(session.calls.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"},
               server='http://loki1')
    check_call(session.calls.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"},
               server='http://loki2')
    check_call(session.calls.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"},
               server='http://loki3')


def test_loki_fallback_strategy(make_profile, session, capsys):
    """
    Test strategy fallback. The log message is send to first server,
    if it failed we try to send it to others.
    """
    servers = ['http://loki1', 'http://loki2', 'http://loki3']
    profiles = make_profile({
        'default.handlers.loki.strategy': 'fallback',
        'default.handlers.loki.urls': servers
    })
    session.response_code = [400, 400, 400]
    setup_logging(profiles=profiles)
    logger = get_logger('component')
    logger.critical('Critical')

    session.closed.wait(.1)
    check_call(session.calls.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"},
               server='http://loki1')
    check_call(session.calls.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"},
               server='http://loki2')
    check_call(session.calls.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"},
               server='http://loki3')
    captured = capsys.readouterr()
    assert 'Unexpected Loki API response status code: 400' in captured.err
