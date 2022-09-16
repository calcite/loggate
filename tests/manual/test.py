import os
import sys

import yaml

sys.path.insert(0,
                os.path.abspath(os.path.join(os.path.dirname(__file__),
                                             '../..')))

from loggate import setup_logging, get_logger   # noqa: E402


def get_yaml(filename):
    with open(filename, 'r+') as fd:
        return yaml.safe_load(fd)


schema = get_yaml('test.yaml')
setup_logging(profiles=schema.get('profiles'))

logger = get_logger('component', meta={'version': '1.0.0'})
logger2 = get_logger('component.aaa')


# logger.debug('Loading resources for the component')
logger2.info('Initialize of the component')
# logger.warning('The component is not ready')
# logger.error('The component failed.', meta={'inputs': {'A': 1, 'B': 2}})
# logger.critical('The component unexpected failed.',
#                 meta={'attrs': {'A': 1, 'B': 2}})
