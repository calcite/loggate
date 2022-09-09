import logging
import os
import sys

from mantra_logger.loki.formatters import LokiLogFormatter
from mantra_logger.loki.handlers import LokiQueueHandler
from mantra_logger.std.formatters import StdLogFormatter

_srcfile = os.path.normcase(logging.addLevelName.__code__.co_filename)


class LogRecord(logging.LogRecord):
    def __init__(self, name, level, pathname, lineno, msg, args, exc_info,
                 func=None, sinfo=None, tags=None, **kwargs):
        super(LogRecord, self).__init__(
            name, level, pathname, lineno,
            msg, args, exc_info, func, sinfo, **kwargs
        )
        self.tags = tags if tags else {}


class Logger(logging.Logger):

    __root = None

    @classmethod
    def get_root(cls):
        if cls.__root is None:
            cls.__root = RootLogger("root", level=logging.WARNING)
        return cls.__root

    def __init__(self, name, level=logging.NOTSET, tags=None):
        super(Logger, self).__init__(name, level)
        self.tags = tags if tags else {}

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info,
                   func=None, extra=None, sinfo=None, tags=None, **kwargs):
        """
        A factory method which can be overridden in subclasses to create
        specialized LogRecords.
        """
        rv = LogRecord(name, level, fn, lno, msg, args, exc_info, func, sinfo,
                       tags, **kwargs)
        if extra is not None:
            for key in extra:
                if (key in ["message", "asctime"]) or (key in rv.__dict__):
                    raise KeyError("Attempt to overwrite %r in LogRecord" % key)
                rv.__dict__[key] = extra[key]
        return rv

    def _log(self, level, msg, args, exc_info=None, extra=None,
             stack_info=False, stacklevel=1, tags=None, **kwargs):
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
        merge_tags = self.manager.tags.copy()
        merge_tags.update(self.tags)
        if tags:
            merge_tags.update(tags)
        record = self.makeRecord(self.name, level, fn, lno, msg, args,
                                 exc_info, func, extra, sinfo, merge_tags,
                                 **kwargs)
        self.handle(record)


class RootLogger(Logger):
    pass


class LogFilter(logging.Filter):
    def __init__(self, level):
        self.level = level

    def filter(self, record):
        return record.levelno < self.level


class Manager(logging.Manager):

    def __init__(self, rootnode):
        super(Manager, self).__init__(rootnode)
        self.tags = {}

    def getLogger(self, name, tags=None):
        rv = super(Manager, self).getLogger(name)
        if tags:
            rv.tags = tags
        return rv


def get_logger(name=None, tags=None) -> Logger:
    """
    Return a logger with the specified name, creating it if necessary.

    If no name is specified, return the root logger.
    """
    if not name or isinstance(name, str) and name == Logger.get_root().name:
        root = Logger.get_root()
        if tags:
            root.tags.update(tags)
        return root
    return Logger.manager.getLogger(name, tags)


def getLogger(name=None, tags=None) -> Logger:
    return get_logger(name, tags)


def setup_logging(
    app_name='root',
    log_level=logging.INFO,
    tags=None,
    stdout=sys.stdout,
    stderr=sys.stderr,
    stderr_from_level=logging.WARNING,
    loki_urls=None,
    loki_auth=None,
    loki_tags=None,
) -> RootLogger:
    """
    One entrypoint for setup logging
    :param app_name: str - application name -> name of root Logger
    :param log_level str|int - publish logs from this level and higher
    :param tags: dict - default tags
    :param stdout: TextIOWrapper - if set, enable stdout
    :param stderr: TextIOWrapper - if stdout set and this set, enable stderr
    :param stderr_from_level: str|int - logs with this level and higher
           forward to stderr
    :param loki_urls: [str]|str - entrypoint or list entrypoints of loki
    :param loki_auth: Tuple(str, str) - Loki authentication
    :param loki_tags: dict - tags append by loki handler
    :return: RootLogger
    """
    root = Logger.get_root()
    root.name = app_name
    root.setLevel(log_level)
    if tags:
        Logger.manager.tags.update(tags)

    if stdout:
        std_formatter = StdLogFormatter()
        handler_stdout = logging.StreamHandler(stdout)
        handler_stdout.setFormatter(std_formatter)
        root.addHandler(handler_stdout)

        if stderr:
            handler_stdout.addFilter(LogFilter(logging.WARNING))
            handler_stderr = logging.StreamHandler(stderr)
            handler_stderr.setFormatter(std_formatter)
            handler_stderr.setLevel(max(log_level, stderr_from_level))
            root.addHandler(handler_stderr)

    if loki_urls:
        if isinstance(loki_urls, str):
            loki_urls = [loki_urls]
        handler_loki = LokiQueueHandler(
            urls=loki_urls,
            auth=loki_auth,
            tags=loki_tags if loki_tags else {})
        handler_loki.set_name('loki')
        handler_loki.setFormatter(LokiLogFormatter())
        root.addHandler(handler_loki)

    return root


Logger.manager = Manager(Logger.get_root())
Logger.manager.setLoggerClass(Logger)
Logger.manager.setLogRecordFactory(LogRecord)
