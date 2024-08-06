from queue import SimpleQueue, Empty


class ConfirmatrionQueue:
    def __init__(self, queue_size=0):
        self.__queue = SimpleQueue()
        self._in_process = []
        # Max size of queue; Limit for privileged message is 110% of this value.
        self._queue_size = queue_size
        self._queue_privileged_size = round(queue_size * 1.1)
        if self._queue_privileged_size > 0 and \
                self._queue_privileged_size == queue_size:
            self._queue_privileged_size += 2

    @property
    def max_size(self):
        return self._queue_size

    def put(self, item, privileged=False, block=True):
        qs = self._queue_privileged_size if privileged else self._queue_size
        if qs > 0 and self.qsize() >= qs:
            return False
        self.__queue.put(item, block=block)
        return True

    def put_nowait(self, item, privileged=False):
        return self.put(item, privileged=privileged, block=False)

    def gets(self, number: int = 1, block: bool = True,
             timeout: bool = None) -> list:
        if not self._in_process:
            for _ in range(number):
                try:
                    self._in_process.append(
                        self.__queue.get(
                            block=block,
                            timeout=timeout
                        ))
                except Empty:
                    break
        return self._in_process.copy()

    def confirm(self):
        self._in_process = []

    def qsize(self):
        return self.__queue.qsize() + len(self._in_process)
