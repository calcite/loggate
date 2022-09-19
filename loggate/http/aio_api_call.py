import base64
import ssl

import aiohttp

from typing import Optional, Tuple

from loggate.http import HttpApiCallInterface


class AIOApiCall(HttpApiCallInterface):
    """
    This is the simplest way how we can do API call without any other
    dependencies.
    """

    def __init__(self, auth: Optional[Tuple[str, str]] = None,
                 timeout: int = None, ssl_verify=True):
        self.__timeout = timeout = aiohttp.ClientTimeout(
            total=int(timeout) if timeout else 5
        )

        self.headers = {
            'Content-Type': 'application/json; charset=utf-8'
        }
        if auth:
            auth64 = base64.b64encode(f'{auth[0]}:{auth[1]}'
                                      .encode('utf8')).decode()
            self.headers['Authorization'] = f'Basic {auth64}'
        self.ctx = ssl.create_default_context()
        if not ssl_verify:
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    async def send_json(self, url: str, data: dict,
                        method='POST') -> (int, str):
        """
        This makes asyncio request to server
        """
        async with aiohttp.ClientSession(timeout=self.__timeout,
                                         headers=self.headers) as session:
            if method == 'POST':
                fce = session.post
            elif method == 'GET':
                fce = session.get
            else:
                return 0, "The method is not supported"
            async with fce(url, json=data, ssl=self.ctx) as resp:
                return resp.status, await resp.text()
