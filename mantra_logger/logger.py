import logging
import os
import sys

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
        record = self.makeRecord(self.name, level, fn, lno, msg, args,
                                 exc_info, func, extra, sinfo, tags, **kwargs)
        self.handle(record)


class RootLogger(Logger):
    pass


class Manager(logging.Manager):

    def getLogger(self, name, tags=None):
        rv = super(Manager, self).getLogger(name)
        if tags:
            rv.tags = tags
        return rv


root = RootLogger(None, level=logging.WARNING)
Logger.root = root
Logger.manager = Manager(Logger.root)
Logger.manager.setLoggerClass(Logger)
Logger.manager.setLogRecordFactory(LogRecord)


def getLogger(name=None, tags=None):
    """
    Return a logger with the specified name, creating it if necessary.

    If no name is specified, return the root logger.
    """
    if not name or isinstance(name, str) and name == root.name:
        return root
    return Logger.manager.getLogger(name, tags)
