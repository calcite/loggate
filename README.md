# Loggate
[![PyPI](https://img.shields.io/pypi/v/loggate?color=green&style=plastic)](https://pypi.org/project/loggate/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/loggate?style=plastic)
![License](https://img.shields.io/github/license/calcite/loggate?style=plastic)

The complex logging system with support of log metadata and delivery to [Grafana Loki](https://grafana.com/oss/loki/). 
This library supports threading & asyncio modules.  

## Simple stdout/stderr colorized output
One example is more than a thousand words.

```python
from loggate import setup_logging, get_logger

setup_logging(level='DEBUG')
logger = get_logger('component', meta={'version': '1.0.0'})

logger.debug('Loading resources for the component')
logger.info('Initialize of the component')
logger.warning('The component is not ready')
logger.error('The component failed.',
             meta={'inputs': {'A': 1, 'B': 2}})
logger.critical('The component unexpected failed.',
                meta={'attrs': {'A': 1, 'B': 2}})
```
*Console output:*

![Console output](https://github.com/calcite/loggate/raw/master/img/console.png)


### Exceptions

```python
from loggate import setup_logging, get_logger

setup_logging()
logger = get_logger('component', meta={'version': '1.0.0'})

try:
    raise Exception('Some error')
except Exception as ex:
    logger.error('The component failed.', exc_info=True)
```
*Console output:*

![Console output](https://github.com/calcite/loggate/raw/master/img/exception.png)


## Advanced configuration
The Loggate supports a declarative configuration alike as [logging.config](https://docs.python.org/3/library/logging.config.html).
But this support profiles as well. It's mean we can declare many logging profiles and switch between them. Default profile is called `default`.

We can use yaml file as configuration file (see next):
```yaml
profiles:
  default:                             
    # Default profile
    filters:
      warning:                          
        # This is a filter for stdout logger, that enable only logs with level lower than WARNING. 
        # For logs with WARNING and higher we use stderr logger. 
        class: loggate.LowerLogLevelFilter
        level: WARNING

    formatters:
      colored:
        # This is stdout/sterr formatter. 
        class: loggate.LogColorFormatter
      loki:
        # This is formatter of loki messages.
        class: loggate.loki.LokiLogFormatter

    handlers:
      stdout:
        # This is a stdout handler
        class: logging.StreamHandler
        stream: ext://sys.stdout
        formatter: colored
        filters:
          - warning
      stderr:
        # This is a stderr handler
        class: logging.StreamHandler
        stream: ext://sys.stderr
        formatter: colored
        level: WARNING        
      loki:
        # This is a loki handler
        class: loggate.loki.LokiThreadHandler  # for asyncio use loggate.loki.LokiHandler       
        formatter: loki
        urls:
          - "http://loki1:3100/loki/api/v1/push"
          - "http://loki2:3100/loki/api/v1/push"
          - "http://loki3:3100/loki/api/v1/push"
        meta:
          # loggate handlers accept metadata as well. Standard logging handlers do not!
          stage: dev
          ip: 192.168.1.10                
                  

    loggers:
        root:          
          level: INFO
          handlers:
            - stdout
            - stderr        
            - loki
        'urllib3.connectionpool': 
          level: WARNING

```

```python
import yaml
from loggate import setup_logging, get_logger


def get_yaml(filename):
    with open(filename, 'r+') as fd:
        return yaml.safe_load(fd)


schema = get_yaml('test.yaml')
setup_logging(profiles=schema.get('profiles'))

logger = get_logger('component')

logger.debug('Loading resources for the component')
logger.info('Initialize of the component')
logger.warning('The component is not ready')
```
The console output is the same as above, but now we send logs to Loki as well.

*Loki output:*

![loki output](https://github.com/calcite/loggate/raw/master/img/loki1.png)



# Description
## Methods
- `get_logger`
  - `name` - Return logger for this name. Empty name returns root logger.
  - `meta` - Metadata (dict), which are sent only by this logger.

- `getLogger` - only alias for `get_logger`
- `setup_logging` - init setup of application logging.
  - `profiles` - Profiles (dict) of logging profiles. When we do not set this parameter, application use predefined profile with log `INFO` level (this level can be set by parameter `level`). 
  - `default_profile` - name of the default profile (default: `default`)
  - `level` - This is special parameter for situation when  application use predefined profile (default `INFO`).  

## Filters
### Class `loggate.LowerLogLevelFilter`
This filters out all logs which are higher than `level`.
- `level` - log level

## Formatters
### Class `loggate.LogColorFormatter`
Colorized formatter for stdout/stderr.
- `fmt` - message format (default: `%(LEVEL_COLOR)s%(asctime)s\t [%(levelname)s] %(name)s:%(COLOR_RESET)s %(message)s`)
- `datefmt` - datetime format (default: `%Y-%m-%d %H:%M:%S`)
- `style` - style of templating (default: `%`). 
- `validate` - validate the input format (default: True)
- `INDENTATION_TRACEBACK` - default: `\t\t\t`
- `INDENTATION_METADATA` - default: `\t\t\t\t`
- `COLOR_DEBUG`, ..., `COLOR_CRITICAL` - set color of this levels (e.g. `\x1b[1;31m`, see [more colors](https://dev.to/ifenna__/adding-colors-to-bash-scripts-48g4)).
- `COLOR_METADATA` - set color metadata
- `COLOR_TRACEBACK` - set color of tracebacks
- `COLOR_...` - set custom color

### Class `loggate.loki.LokiLogFormatter`
This is special loki formatter, this converts log records to jsons.


## Handlers
### Class `loggate.loki.LokiHandler`
This handler send log records to Loki server. This is blocking implementation of handler.
It means, when we call log method (`debug`, ... `critical`) the message is sent in the same thread. We should use
this only for tiny scripts where other ways have a big overhead.
- `level` - This handler sends only log records with log level equal or higher than this (default: all = `logging.NOTSET`).
- `urls` - List of loki entrypoints.
- `strategy` - Deploy strategy (default: `random`).
  - `random` - At the beginning the handler choose random Loki server and others are fallbacks.
  - `fallbacks` - The handler uses the first Loki server and others are fallbacks.
  - `all` - The handler send the log record to all loki servers.
- `auth` - The Loki authentication, the list with two items (`username`, `password`).
- `timeout` - Timeout for one delivery try (default: 5s).
- `ssl_verify` - Enable ssl verify (default: True).
- `loki_tags` - the list of metadata keys, which are sent to Loki server as label (defailt: [`logger`, `level`]).
- `meta` - Metadata (dict), which are sent only by this handler.  

### Class `loggate.loki.LokiAsyncioHandler`
This is non-bloking extending of LokiHandler. We register an extra asyncio task for sending messages to the Loki server.
Parameters are the same as `loggate.loki.LokiHandler`. This handler uses `urllib.requests` module in default ([aiohttp](https://pypi.org/project/aiohttp/) as optional). 
Unfortunately `urllib.requests` module does not support asyncio, it means the sending itself is blocking.
The `loggate.loki.Loki AsyncioHandler` can use the optional dependency [aiohttp](https://pypi.org/project/aiohttp/) for non-bloking sending.

### Class `loggate.loki.LokiThreadHandler`
This is non-bloking extending of LokiHandler. We register and start an extra thread for sending messages to the Loki server.
Parameters are the same as `loggate.loki.LokiHandler`.

## Profiles
The structure of profiles (parameter `profiles` of `setup_logging`).

```yaml
<profile_name>:
  
  filters:
    <filter_name>:
      class: <filter_class>
      <filter_attribute_name>: <filter_attribute_value>
  
  formatters:
    <formatter_name>:
      class: <formatter_class>
      <formatter_attribute_name>: <formatter_attribute_value>
  
  handlers:
    <handler_name>:
      class: <handler_class>
      <handler_attribute_name>: <handler_attribute_value>

  loggers:
    <logger_name>|root:   # definition of root logger
      level: <log_level>
      handlers: 
        - <name_of_handler>|<definition_of_handler>
      disabled: True|False    # default: False
      propagate: True|False   # default: True
      meta: <logger_metadata>  
```
