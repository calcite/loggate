import importlib
import logging
import os
import sys

from mantra_logger.helper import get_level

_srcfile = os.path.normcase(logging.addLevelName.__code__.co_filename)


class LoggingException(Exception): pass
class LoggingProfileDoesNotExist(LoggingException): pass


def dynamic_import(class_name: str):
    if '.' not in class_name:
        return globals()[class_name]
    module, class_name = class_name.rsplit('.', 1)
    module = importlib.import_module(module)
    return module.__dict__[class_name]


class LogRecord(logging.LogRecord):
    def __init__(self, name, level, pathname, lineno, msg, args, exc_info,
                 func=None, sinfo=None, meta=None, **kwargs):
        super(LogRecord, self).__init__(
            name, level, pathname, lineno,
            msg, args, exc_info, func, sinfo, **kwargs
        )
        self.meta = meta if meta else {}


class Logger(logging.Logger):

    __root = None

    @classmethod
    def get_root(cls):
        if cls.__root is None:
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
                fn, lno, func, sinfo = self.findCaller(stack_info, stacklevel)
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
                                 exc_info, func, extra, sinfo, merge_meta,
                                 **kwargs)
        self.handle(record)


class RootLogger(Logger):
    pass


class Manager(logging.Manager):

    def __init__(self, rootnode):
        super(Manager, self).__init__(rootnode)
        self.meta = {}
        self.__profiles = {}
        self.__filters = {}
        self.__formatters = {}
        self.__handlers = {}

    def getLogger(self, name, meta=None):
        rv = super(Manager, self).getLogger(name)
        if meta:
            rv.meta = meta
        return rv

    def set_profiles(self, profiles) -> None:
        self.__profiles = profiles

    def __cleanup(self):
        pass

    def __get_handler_from_schema(self, attrs: dict):
        _class = attrs.pop('class', 'logging.Handler')
        _class = dynamic_import(_class)
        attr_level = attrs.pop('level', None)
        attr_formatter = attrs.pop('formatter', None)
        attr_filters = attrs.pop('filters', [])
        for key in attrs.keys():
            if attrs[key].startswith('ext://'):
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
        for handler in attrs.get('handlers', []):
            if isinstance(handler, dict):
                logger.addHandler(self.__get_handler_from_schema(handler))
            else:
                logger.addHandler(self.__handlers[handler])

    def activate_profile(self, profile_name: str,
                         only_update: bool = False) -> None:
        profile = self.__profiles.get(profile_name)
        if not profile:
            raise LoggingProfileDoesNotExist(
                f'Profile "{profile}" does not exist.')
        if not only_update:
            self.__cleanup()
        if profile.get('inherited'):
            self.activate_profile(profile.get('inherited'))

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
            handler = self.__get_handler_from_schema(attrs)
            handler.set_name(name)
            self.__handlers[name] = handler

        for name, attrs in profile.get('loggers', {}).items():
            if name == 'root':
                logger = self.root
            else:
                logger = super(Manager, self).getLogger(name)
            self.__setup_logger(logger, attrs)


def get_logger(name=None, meta=None) -> Logger:
    """
    Return a logger with the specified name, creating it if necessary.

    If no name is specified, return the root logger.
    """
    if not name or isinstance(name, str) and name == Logger.get_root().name:
        root = Logger.get_root()
        if meta:
            root.meta.update(meta)
        return root
    return Logger.manager.getLogger(name, meta)


def getLogger(name=None, meta=None) -> Logger:
    return get_logger(name, meta)


def setup_logging(profiles: dict, default_profile: str = 'default'):
    Logger.manager.set_profiles(profiles)
    Logger.manager.activate_profile(default_profile)



# def setup_logging(
#     app_name='root',
#     log_level=logging.INFO,
#     meta=None,
#     stdout=sys.stdout,
#     stderr=sys.stderr,
#     stderr_from_level=logging.WARNING,
#     loki_urls=None,
#     loki_auth=None,
#     loki_meta=None,
#     loki_tags=None,
# ) -> RootLogger:
#     """
#     One entrypoint for setup logging
#     :param app_name: str - application name -> name of root Logger
#     :param log_level str|int - publish logs from this level and higher
#     :param meta: dict - default meta
#     :param stdout: TextIOWrapper - if set, enable stdout
#     :param stderr: TextIOWrapper - if stdout set and this set, enable stderr
#     :param stderr_from_level: str|int - logs with this level and higher
#            forward to stderr
#     :param loki_urls: [str]|str - entrypoint or list entrypoints of loki
#     :param loki_auth: Tuple(str, str) - Loki authentication
#     :param loki_meta: dict - metadata append by loki handler
#     :param loki_tags: list - metadata which will be converted to loki tags
#     :return: RootLogger
#     """
#     root = Logger.get_root()
#     root.name = app_name
#     root.setLevel(log_level)
#     if meta:
#         Logger.manager.meta.update(meta)
#
#     if stdout:
#         std_formatter = ColorLogFormatter()
#         handler_stdout = logging.StreamHandler(stdout)
#         handler_stdout.setFormatter(std_formatter)
#         root.addHandler(handler_stdout)
#
#         if stderr:
#             handler_stdout.addFilter(LogFilter(logging.WARNING))
#             handler_stderr = logging.StreamHandler(stderr)
#             handler_stderr.setFormatter(std_formatter)
#             handler_stderr.setLevel(max(log_level, stderr_from_level))
#             root.addHandler(handler_stderr)
#
#     if loki_urls:
#         if isinstance(loki_urls, str):
#             loki_urls = [loki_urls]
#         handler_loki = LokiQueueHandler(
#             urls=loki_urls,
#             auth=loki_auth,
#             meta=loki_meta if loki_meta else {},
#             tags=loki_tags
#         )
#         handler_loki.set_name('loki')
#         handler_loki.setFormatter(LokiLogFormatter())
#         root.addHandler(handler_loki)
#
#     return root


Logger.manager = Manager(Logger.get_root())
Logger.manager.setLoggerClass(Logger)
Logger.manager.setLogRecordFactory(LogRecord)
