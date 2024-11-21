#  SPDX-License-Identifier: Apache-2.0
"""
Python Package for controlling Porsche Connect API.

"""

import logging
import asyncio
from typing import Text

import httpx
from .oauth2 import OAuth2Token, OAuth2Client, Credentials
from .const import API_BASE_URL, TIMEOUT, USER_AGENT, X_CLIENT_ID, CLIENT_ID

from typing import Optional

from .exceptions import PorscheException

_LOGGER = logging.getLogger(__name__)


async def log_request(request):
    _LOGGER.debug(f"Request headers: {request.headers}")
    _LOGGER.debug(f"Request method - url: {request.method} {request.url}")
    _LOGGER.debug(f"Request body: {request.content}")


class Connection:
    """
    Handles authentication and connecting to the Porsche Connect API

    :param email: Porsche Connect email
    :param password: Porsche Connect password
    :param asyncClient: httpx.AsyncClient or None
    :param token: token dict - should be a dict with access_token, refresh_token, expires_at, etc as root params
    :param leeway: time in seconds to consider token as expired before it actually expires
    """

    def __init__(
        self,
        email: Optional[Text] = None,
        password: Optional[Text] = None,
        asyncClient=httpx.AsyncClient(),
        token={},
        leeway: int = 60,
    ) -> None:
        self.asyncClient = asyncClient
        self.token_lock = asyncio.Lock()

        self.token = OAuth2Token(token)

        self.headers = {"User-Agent": USER_AGENT, "X-Client-ID": X_CLIENT_ID}
        # if self.asyncClient is None:
        #     self.asyncClient = httpx.AsyncClient(
        #         base_url=API_BASE_URL,
        #         headers={"User-Agent": USER_AGENT, "X-Client-ID": X_CLIENT_ID},
        #         event_hooks={"request": [log_request]},
        #         verify=False,
        #         timeout=TIMEOUT,
        #     )
        # elif isinstance(self.asyncClient, httpx.AsyncClient):
        #     self.asyncClient.base_url = API_BASE_URL
        #     self.asyncClient.headers.update(
        #         {"User-Agent": USER_AGENT, "X-Client-ID": CLIENT_ID}
        #     )
        #     self.asyncClient.event_hooks["request"] = [log_request]
        # else:
        #     raise TypeError("asyncClient must be an instance of httpx.AsyncClient")

        self.oauth2_client = OAuth2Client(
            self.asyncClient, Credentials(email, password), leeway
        )

    async def getToken(self):
        async with self.token_lock:
            await self.oauth2_client.ensure_valid_token(self.token)
        return self.token

    async def get(self, url, params=None):
        return await self.request("GET", url, params=params)

    async def post(self, url, data=None, json=None):
        return await self.request("POST", url, data=data, json=json)

    async def put(self, url, data=None, json=None):
        return await self.request("PUT", url, data=data, json=json)

    async def delete(self, url, data=None, json=None):
        return await self.request("DELETE", url, data=data, json=json)

    async def request(self, method, url, **kwargs):
        try:
            async with self.token_lock:
                await self.oauth2_client.ensure_valid_token(self.token)
            resp = await self.asyncClient.request(
                method,
                f"{API_BASE_URL}/{url}",
                headers=self.headers
                | {"Authorization": f"Bearer {self.token.access_token}"},
                timeout=TIMEOUT,
                **kwargs,
            )
            resp.raise_for_status()  # A common error seem to be: httpx.HTTPStatusError: Server error '504 Gateway Time-out'
            return resp.json()
        except httpx.HTTPStatusError as exception_:
            raise PorscheException(exception_.response.status_code)

    async def close(self):
        """Close the asyncClient connection"""
        await self.asyncClient.aclose()
