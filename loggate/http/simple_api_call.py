import base64
import json
import ssl
import socket
import urllib.request
from typing import Optional, Tuple

from loggate.http import HttpApiCallInterface


class SimpleApiCall(HttpApiCallInterface):
    """
    This is the simplest way how we can do API call without any other
    dependencies.
    """

    def __init__(self, auth: Optional[Tuple[str, str]] = None,
                 timeout: int = None, ssl_verify=True):
        self.timeout = int(timeout) if timeout else 10
        # auth
        self.__auth = None
        if auth:
            self.__auth = base64.b64encode(f'{auth[0]}:{auth[1]}'
                                           .encode('utf8')).decode()
        self.ctx = ssl.create_default_context()
        if not ssl_verify:
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    def send_json(self, url: str, data: dict, method='POST') -> (int, str):
        json_data = json.dumps(data).encode('utf-8')
        request = urllib.request.Request(url, data=json_data, method=method)
        request.add_header('Content-Type', 'application/json; charset=utf-8')
        request.add_header('Content-Length', len(json_data))
        if self.__auth:
            request.add_header("Authorization", "Basic %s" % self.__auth)
        try:
            resp = urllib.request.urlopen(
                request,
                timeout=self.timeout,
                context=self.ctx
            )
            return resp.status, resp.read().decode()
        except urllib.error.HTTPError as ex:
            return ex.status, ex.read().decode()
        except socket.timeout:
            return 1000, "Timeout"
        except Exception as ex:
            return None, "Unknown error: {0}".format(ex)
