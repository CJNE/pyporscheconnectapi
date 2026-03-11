#  SPDX-License-Identifier: Apache-2.0
"""Python Package for controlling Porsche Connect API."""

from __future__ import annotations

import asyncio
import logging
import uuid

import httpx

from .const import API_BASE_URL, DCGW_BASE_URL, TIMEOUT, USER_AGENT, X_CLIENT_ID
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
        cookies: list[dict] | None = None,
        code_verifier: str | None = None,
        token=None,
        leeway: int = 60,
    ) -> None:
        """Initialise the connection to the Porsche Connect API."""
        if token is None:
            token = {}
        self.asyncClient = async_client
        self.token_lock = asyncio.Lock()
        self.country_code = "de"
        self.language_code = "de_DE"

        if cookies:
            for cookie in cookies:
                self.asyncClient.cookies.set(
                    cookie["name"],
                    cookie["value"],
                    domain=cookie.get("domain"),
                    path=cookie.get("path", "/"),
                )

        self.token = OAuth2Token(token)

        self.headers = {
            "User-Agent": USER_AGENT,
            "X-Client-ID": X_CLIENT_ID,
            "Accept-Language": "de-DE",
            "Origin": "https://security.porsche.com",
            "Referer": "https://security.porsche.com/",
        }

        self.oauth2_client = OAuth2Client(
            self.asyncClient,
            Credentials(email, password),
            Captcha(captcha_code, state),
            code_verifier,
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

    async def portal_get(self, url, params=None):
        """Make a GET request to the Porsche DCGW portal API."""
        return await self.absolute_request("GET", f"{DCGW_BASE_URL}{url}", params=params)

    async def get_portal_config(self):
        """Fetch and cache portal localization/config data."""
        config = await self.portal_get(f"/core/config/v1/{self.country_code}/{self.country_code}/")
        localization = config.get("localization", {})
        self.country_code = str(localization.get("countryCode", self.country_code)).lower()
        self.language_code = localization.get("languageCode", self.language_code)
        return config

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
        return await self.absolute_request(method, f"{API_BASE_URL}{url}", **kwargs)

    async def absolute_request(self, method, url, **kwargs):
        """Create a request to an absolute Porsche API URL."""
        try:
            async with self.token_lock:
                await self.oauth2_client.ensure_valid_token(self.token)
            headers = self.headers | {
                "Authorization": f"Bearer {self.token.access_token}",
                "X-TRACE-ID": f"PCCK-PORTAL-{uuid.uuid4()}",
            }
            resp = await self.asyncClient.request(
                method,
                url,
                headers=headers,
                timeout=TIMEOUT,
                **kwargs,
            )
            resp.raise_for_status()  # A common error seem to be: httpx.HTTPStatusError: Server error '504 Gateway Time-out'
            return resp.json()
        except httpx.HTTPStatusError as exc:
            response_text = exc.response.text[:1000] if exc.response.text else None
            raise PorscheExceptionError(
                exc.response.status_code,
                response_body=response_text,
                request_url=str(exc.request.url),
            ) from exc

    async def close(self):
        """Close the asyncClient connection."""
        await self.asyncClient.aclose()
