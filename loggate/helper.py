import asyncio
from logging import DEBUG, INFO, WARNING, ERROR, FATAL, CRITICAL, NOTSET
from queue import Empty

nameToLevel = {
    'CRITICAL': CRITICAL,
    'FATAL': FATAL,
    'ERROR': ERROR,
    'WARN': WARNING,
    'WARNING': WARNING,
    'INFO': INFO,
    'DEBUG': DEBUG,
    'NOTSET': NOTSET,
}


def get_level(level):
    if isinstance(level, str):
        return nameToLevel.get(level)
    return level


class AsyncioQueueListener(object):
    """
    This class implements an asyncio listener which watches for
    LogRecords being added to a queue, removes them and passes them to a
    list of handlers for processing.
    """

    def __init__(self, queue, *handlers, respect_handler_level=False):
        self.queue = queue
        self.handlers = handlers
        self.__stop = False
        self.respect_handler_level = respect_handler_level

    def start(self):
        self.__stop = False
        asyncio.get_event_loop().create_task(self._monitor())

    async def handle(self, record):
        for handler in self.handlers:
            if not self.respect_handler_level:
                process = True
            else:
                process = record.levelno >= handler.level
            if process:
                await handler.handle(record)

    async def _monitor(self):
        q = self.queue
        has_task_done = hasattr(q, 'task_done')
        while not self.__stop:
            try:
                record = self.queue.get(False)
                await self.handle(record)
                if has_task_done:
                    q.task_done()
            except Empty:
                await asyncio.sleep(0.1)

    def stop(self):
        self.__stop = True
