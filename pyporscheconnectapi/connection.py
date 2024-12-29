#  SPDX-License-Identifier: Apache-2.0
"""Python Package for controlling Porsche Connect API."""

from __future__ import annotations

import asyncio
import logging

import httpx

from .const import API_BASE_URL, TIMEOUT, USER_AGENT, X_CLIENT_ID
from .exceptions import PorscheExceptionError
from .oauth2 import Captcha, Credentials, OAuth2Client, OAuth2Token

_LOGGER = logging.getLogger(__name__)


async def log_request(request):
    """Provide formatting for http logging."""
    _LOGGER.debug("Request headers: %s", request.headers)
    _LOGGER.debug("Request method - url: %s %s", request.method, request.url)
    _LOGGER.debug("Request body: %s", request.content)


class Connection:
    """Handles authentication and connecting to the Porsche Connect API.

    :param email: Porsche Connect email
    :param password: Porsche Connect password
    :param asyncClient: httpx.AsyncClient or None
    :param token: token dict - should be a dict with access_token, refresh_token, expires_at, etc as root params
    :param leeway: time in seconds to consider token as expired before it actually expires
    """

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        captcha_code: str | None = None,
        state: str | None = None,
        async_client=httpx.AsyncClient(),
        token=None,
        leeway: int = 60,
    ) -> None:
        """Initialise the connection to the Porsche Connect API."""
        if token is None:
            token = {}
        self.asyncClient = async_client
        self.token_lock = asyncio.Lock()

        self.token = OAuth2Token(token)

        self.headers = {"User-Agent": USER_AGENT, "X-Client-ID": X_CLIENT_ID}

        self.oauth2_client = OAuth2Client(
            self.asyncClient,
            Credentials(email, password),
            Captcha(captcha_code, state),
            leeway,
        )

    async def get_token(self):
        """Return the authentication token."""
        async with self.token_lock:
            await self.oauth2_client.ensure_valid_token(self.token)
        return self.token

    async def get(self, url, params=None):
        """Make a GET request to the Porsche Connect API."""
        return await self.request("GET", url, params=params)

    async def post(self, url, data=None, json=None):
        """Make a POST request to the Porsche Connect API."""
        return await self.request("POST", url, data=data, json=json)

    async def put(self, url, data=None, json=None):
        """Make a PUT request to the Porsche Connect API."""
        return await self.request("PUT", url, data=data, json=json)

    async def delete(self, url, data=None, json=None):
        """Make a DELETE request to the Porsche Connect API."""
        return await self.request("DELETE", url, data=data, json=json)

    async def request(self, method, url, **kwargs):
        """Create a request to the Porsche Connect API."""
        try:
            async with self.token_lock:
                await self.oauth2_client.ensure_valid_token(self.token)
            resp = await self.asyncClient.request(
                method,
                f"{API_BASE_URL}/{url}",
                headers=self.headers | {"Authorization": f"Bearer {self.token.access_token}"},
                timeout=TIMEOUT,
                **kwargs,
            )
            resp.raise_for_status()  # A common error seem to be: httpx.HTTPStatusError: Server error '504 Gateway Time-out'
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise PorscheExceptionError(exc.response.status_code) from exc

    async def close(self):
        """Close the asyncClient connection."""
        await self.asyncClient.aclose()
