import copy
import importlib
import logging
import os
import sys

from loggate.helper import get_level

_srcfile = os.path.normcase(logging.addLevelName.__code__.co_filename)

DEFAULT_PROFILE = {
    'default': {
        'filters': {
            'warning': {
                'class': 'loggate.LowerLogLevelFilter',
                'level': logging.WARNING
            }
        },
        'formatters': {
            'colored': {
                'class': 'loggate.LogColorFormatter'
            }
        },
        'handlers': {
            'stdout': {
                'class': 'logging.StreamHandler',
                'stream': 'ext://sys.stdout',
                'formatter': 'colored',
                'filters': ['warning'],
            },
            'stderr': {
                'class': 'logging.StreamHandler',
                'stream': 'ext://sys.stderr',
                'formatter': 'colored',
                'level': logging.WARNING
            }
        },
        'loggers': {
            'root': {
                'handlers': ['stdout', 'stderr'],
                'level': logging.INFO
            }
        }
    }
}


class LoggingException(Exception): pass                     # noqa: E701
class LoggingProfileDoesNotExist(LoggingException): pass    # noqa: E701


def dynamic_import(class_name: str):
    """
    Method for import & return required class.
    :param class_name: str (e.g. module1.module2.ClassA)
    :return: class
    """
    if '.' not in class_name:
        return globals()[class_name]
    module, class_name = class_name.rsplit('.', 1)
    module = importlib.import_module(module)
    return module.__dict__[class_name]


class LogRecord(logging.LogRecord):
    """
    Overwrite original logging.LogRecord.
    :param meta: dict - metadata parameter
    """
    def __init__(self, name, level, pathname, lineno, msg, args, exc_info,
                 func=None, sinfo=None, meta=None, **kwargs):
        super(LogRecord, self).__init__(
            name, level, pathname, lineno,
            msg, args, exc_info, func, sinfo, **kwargs
        )
        self.meta = meta if meta else {}

    def __copy__(self):
        cp = type(self)(level=self.levelno, **self.__dict__)
        cp.__dict__.update(self.__dict__)
        return cp


class Logger(logging.Logger):
    """
    Overwrite original logging.Logger.
    added support for metadata
    """
    __root = None

    @classmethod
    def get_root(cls, recreate: bool = False):
        if cls.__root is None or recreate:
            cls.__root = RootLogger("root", level=logging.WARNING)
        return cls.__root

    def __init__(self, name, level=logging.NOTSET, meta=None):
        super(Logger, self).__init__(name, level)
        self.meta = meta if meta else {}

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info,
                   func=None, extra=None, sinfo=None, meta=None, **kwargs):
        """
        A factory method which can be overridden in subclasses to create
        specialized LogRecords.
        """
        rv = LogRecord(name, level, fn, lno, msg, args, exc_info, func, sinfo,
                       meta, **kwargs)
        if extra is not None:
            for key in extra:
                if (key in ["message", "asctime"]) or (key in rv.__dict__):
                    raise KeyError("Attempt to overwrite %r in LogRecord" % key)
                rv.__dict__[key] = extra[key]
        return rv

    def _log(self, level, msg, args, exc_info=None, extra=None,
             stack_info=False, stacklevel=1, meta=None, **kwargs):
        """
        Low-level logging routine which creates a LogRecord and then calls
        all the handlers of this logger to handle the record.
        """
        sinfo = None
        if _srcfile:
            # IronPython doesn't track Python frames, so findCaller raises an
            # exception on some versions of IronPython. We trap it here so that
            # IronPython can use logging.
            try:
                if sys.version_info.minor < 8:
                    fn, lno, func, sinfo = self.findCaller(stack_info)
                else:
                    fn, lno, func, sinfo = self.findCaller(stack_info,
                                                           stacklevel)
            except ValueError:  # pragma: no cover
                fn, lno, func = "(unknown file)", 0, "(unknown function)"
        else:  # pragma: no cover
            fn, lno, func = "(unknown file)", 0, "(unknown function)"
        if exc_info:
            if isinstance(exc_info, BaseException):
                exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
            elif not isinstance(exc_info, tuple):
                exc_info = sys.exc_info()
        merge_meta = self.manager.meta.copy()
        merge_meta.update(self.meta)
        if meta:
            merge_meta.update(meta)
        record = self.makeRecord(self.name, level, fn, lno, msg, args,
                                 exc_info, func, extra, sinfo, meta=merge_meta,
                                 **kwargs)
        self.handle(record)

    def callHandlers(self, record):
        """
        """
        c = self
        found = 0
        while c:
            for hdlr in c.handlers:
                found = found + 1
                if record.levelno >= hdlr.level:
                    hdlr.handle(copy.copy(record))
            if not c.propagate:
                c = None  # break out
            else:
                c = c.parent
        if (found == 0):
            if logging.lastResort:
                if record.levelno >= logging.lastResort.level:
                    logging.lastResort.handle(record)
            elif logging.raiseExceptions and \
                    not self.manager.emittedNoHandlerWarning:
                sys.stderr.write("No handlers could be found for logger"
                                 " \"%s\"\n" % self.name)
                self.manager.emittedNoHandlerWarning = True


class RootLogger(Logger):
    pass


class Manager(logging.Manager):
    """
    Overwrite original logging.Manager.
    added support for metadata + profiles
    """

    def __init__(self, rootnode):
        super(Manager, self).__init__(rootnode)
        self.meta = {}
        self.__profiles = {}
        self.__filters = {}
        self.__formatters = {}
        self.__handlers = {}
        self.__current_profile_name = None

    def getLogger(self, name: str, meta: dict = None) -> Logger:
        """
        We can update logger metadata by optional parameter meta.
        :param name: str - name of logger
        :param meta: dict - metadata
        :return: Logger
        """
        rv = super(Manager, self).getLogger(name)
        if meta:
            rv.meta = meta
        return rv

    def set_profiles(self, profiles: dict) -> None:
        """
        Setup profiles structure.
        :param profiles: dict
        """
        self.__profiles = profiles

    def __cleanup(self, disable_existing_loggers=False):
        logging._acquireLock()
        try:
            self.meta = {}
            self.__filters = {}
            self.__formatters = {}
            for handler in self.__handlers.values():
                handler.flush()
                handler.close()
            self.__handlers = {}
            if disable_existing_loggers:
                self.loggerDict = {}
            else:
                for logger in self.loggerDict.values():
                    if not isinstance(logger, logging.PlaceHolder):
                        logger.setLevel(logging.NOTSET)
                        logger.propagate = True
                        logger.disabled = False
                        logger.handlers = []
        finally:
            logging._releaseLock()
        # self.loggerDict.clear()
        # self.root = Logger.get_root(recreate=True)

    def __create_handler_from_schema(self, attrs: dict):
        _class = attrs.pop('class', 'logging.Handler')
        _class = dynamic_import(_class)
        attr_level = attrs.pop('level', None)
        attr_formatter = attrs.pop('formatter', None)
        attr_filters = attrs.pop('filters', [])
        for key in attrs.keys():
            if isinstance(attrs[key], str) and attrs[key].startswith('ext://'):
                attrs[key] = dynamic_import(attrs[key][6:])
        handler = _class(**attrs)
        if attr_level:
            handler.setLevel(get_level(attr_level))
        if attr_formatter:
            if isinstance(attr_formatter, str):
                # reference to formatter
                handler.setFormatter(self.__formatters[attr_formatter])
            else:
                # one shot formatter
                _formatter_class = \
                    attr_formatter.pop('class', 'logging.Formatter')
                _formatter_class = dynamic_import(_formatter_class)
                handler.setFormatter(_formatter_class(**attr_formatter))
        for attr_filter in attr_filters:
            if isinstance(attr_filter, str):
                # reference to filter
                handler.addFilter(self.__filters[attr_filter])
            else:
                # one shot formatter
                _filter_class = \
                    attr_formatter.pop('class', 'logging.Filter')
                _filter_class = dynamic_import(_filter_class)
                handler.addFilter(_filter_class(**attr_filter))
        return handler

    def __setup_logger(self, logger, attrs):
        if 'level' in attrs:
            logger.setLevel(get_level(attrs.get('level')))
        if attrs.get('disabled', False):
            logger.disabled = True
        if not attrs.get('propagate', True):
            logger.propagate = False
        meta = attrs.get('meta')
        if meta:
            logger.meta = meta
        for handler in attrs.get('handlers', []):
            if isinstance(handler, dict):
                logger.addHandler(self.__create_handler_from_schema(handler))
            else:
                logger.addHandler(self.__handlers[handler])

    def activate_profile(self, profile_name: str) -> None:
        """
        Switch login profile
        :param profile_name: str - profile name
        :param cleanup: bool - remove previous configuration
        """
        profile = self.__profiles.get(profile_name)
        if not profile:
            raise LoggingProfileDoesNotExist(
                f'Profile "{profile_name}" does not exist.')
        profile = copy.deepcopy(profile)
        parent_profile_name = profile.get('inherited')
        if parent_profile_name:
            self.activate_profile(parent_profile_name, False)

        self.__cleanup(profile.get('disable_existing_loggers', False))
        # Filters
        for name, attrs in profile.get('filters', {}).items():
            _class = attrs.pop('class', 'logging.Filter')
            _class = dynamic_import(_class)
            self.__filters[name] = _class(**attrs)

        # Formatters
        for name, attrs in profile.get('formatters', {}).items():
            _class = attrs.pop('class', 'logging.Formatter')
            _class = dynamic_import(_class)
            self.__formatters[name] = _class(**attrs)

        # Handlers
        for name, attrs in profile.get('handlers', {}).items():
            handler = self.__create_handler_from_schema(attrs)
            handler.set_name(name)
            self.__handlers[name] = handler

        for name, attrs in profile.get('loggers', {}).items():
            if name == 'root':
                logger = self.root
            else:
                logger = super(Manager, self).getLogger(name)
            self.__setup_logger(logger, attrs)


def get_logger(name: str = None, meta: dict = None) -> Logger:
    """
    Wrapper of Logger.manager.getLogger
    """
    if not name or isinstance(name, str) and name == Logger.get_root().name:
        root = Logger.get_root()
        if meta:
            root.meta.update(meta)
        return root
    return Logger.manager.getLogger(name, meta)


def getLogger(name: str = None, meta: dict = None) -> Logger:
    """
    Wrapper of Logger.manager.getLogger
    """
    return get_logger(name, meta)


def setup_logging(profiles: dict = None, default_profile: str = 'default',
                  level=None):
    """
       Wrapper of Logger.manager.set_profiles + activate default_profile
       :param profiles: dict - profile structure (more in README)
       :param default_profile: str - name of default profile
       :param level: int|str - if profiles is not set, we can set logging level
                               of DEFAULT_PROFILE
    """
    if not profiles and level:
        DEFAULT_PROFILE['default']['loggers']['root']['level'] = \
            get_level(level)
    if isinstance(profiles, dict) and 'profiles' in profiles:
        profiles = profiles.get('profiles')
    Logger.manager.set_profiles(profiles if profiles else DEFAULT_PROFILE)
    Logger.manager.activate_profile(default_profile)


Logger.manager = Manager(Logger.get_root())
Logger.manager.setLoggerClass(Logger)
Logger.manager.setLogRecordFactory(LogRecord)
logging.Logger.manager = Logger.manager
