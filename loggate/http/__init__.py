import abc
from typing import Optional, Tuple


class HttpApiCallInterface(abc.ABC):
    """
    This is only class Interface for Api call.
    """

    @abc.abstractmethod
    def __init__(self, auth: Optional[Tuple[str, str]] = None,
                 timeout: int = None, ssl_verify=True):
        pass

    @abc.abstractmethod
    def send_json(self, url: str, data: dict, method='POST') -> (int, str):
        pass
