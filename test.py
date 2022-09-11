import yaml

from mantra_logger import setup_logging, get_logger
from mantra_logger.logger import Logger


def get_yaml(filename):
    with open(filename, 'r+') as fd:
        return yaml.safe_load(fd)


schema = get_yaml('test.yaml')
setup_logging(profiles=schema.get('profiles'))

Logger.manager.activate_profile('debug')

test = get_logger('AAA')
test.debug('Pokus')
test.error('Pokus')

