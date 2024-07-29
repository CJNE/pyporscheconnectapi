#  SPDX-License-Identifier: Apache-2.0
"""
Python Package for controlling Porsche Connect API.

"""
import asyncio
import calendar
import datetime
import json
import logging
import time
import base64
import os
import urllib
import uuid

from urllib.parse import urlunparse, urlencode
from collections import namedtuple
from typing import Dict, Text

import aiohttp

from .const import *

try:
    from rich import print
except ImportError:
    pass

from .exceptions import CaptchaRequired, WrongCredentials, PorscheException

_LOGGER = logging.getLogger(__name__)


async def on_request_start(session, trace_config_ctx, params):
    _LOGGER.debug("Starting request")
    _LOGGER.debug(params)


async def on_request_end(session, trace_config_ctx, params):
    _LOGGER.debug("Ending request")
    _LOGGER.debug(params)


trace_config = aiohttp.TraceConfig()
trace_config.on_request_start.append(on_request_start)
trace_config.on_request_end.append(on_request_end)


class Connection:
    """Connection to Porsche Connect API."""

    def __init__(
        self,
        email: Text = None,
        password: Text = None,
        websession: aiohttp.ClientSession = None,
        x_client_id: Text = None,
        token=None,
    ) -> None:
        """Initialize connection object."""

        self.token = token or None
        self.email = email
        self.password = password
        self.x_client_id = "41843fb4-691d-4970-85c7-2673e8ecef40"
        self.websession = websession
        self._isLoggedIn = False
        self.auth_state = {}

        if self.websession is None:
            self.websession = aiohttp.ClientSession(trace_configs=[trace_config])
        _LOGGER.debug("New connection prepared")

    async def _login(self):
        Components = namedtuple(
            typename="Components",
            field_names=["scheme", "netloc", "url", "params", "query", "fragment"],
        )

        # 1. Get initial state

        _LOGGER.debug("Start authentication, get initial state from auth server")

        query_params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "audience": AUDIENCE,
            "scope": SCOPE,
        }

        headers = {
            "User-Agent": USER_AGENT,
        }

        url = urlunparse(
            Components(
                scheme="https",
                netloc=AUTHORIZATION_SERVER,
                url="/authorize",
                params="",
                query=urlencode(query_params),
                fragment="",
            )
        )

        async with self.websession.get(
            url, headers=headers, allow_redirects=False
        ) as resp:
            location = resp.headers["Location"]
            params = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
            have_code = params.get("code", None)

            if have_code is not None:
                _LOGGER.debug("We already have a code in session, skip login")
                self.auth_state["code"] = have_code
                return

            self.auth_state["state"] = params["state"][0]
        _LOGGER.debug(self.auth_state)

        # 2. Post username

        _LOGGER.debug("POST username")

        query_params = {
            "state": self.auth_state["state"],
        }

        url = urlunparse(
            Components(
                scheme="https",
                netloc=AUTHORIZATION_SERVER,
                url="/u/login/identifier",
                params="",
                query=urlencode(query_params),
                fragment="",
            )
        )

        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        auth_body = {
            "state": self.auth_state["state"],
            "username": self.email,
            "js-available": True,
            "webauthn-available": False,
            "is-brave": False,
            "webauthn-platform-available": False,
            "action": "default",
        }

        async with self.websession.post(
            url,
            headers=headers,
            data=auth_body,
            max_redirects=30,
        ) as resp:

            # In case of wrong credentials there is a state param in the redirect url
            if resp.status == 401:
                message = await resp.json()
                raise WrongCredentials(
                    message.get("message", message.get("description", "Unknown error"))
                )

            # In case captcha verification is required, the response code is 400 and the captcha is provided as a svg image
            if resp.status == 400:
                html_body = await resp.text()
                raise CaptchaRequired("Captcha required")

            _LOGGER.debug(resp)

        # 3. Post password

        _LOGGER.debug("POST password")

        query_params = {
            "state": self.auth_state["state"],
        }

        url = urlunparse(
            Components(
                scheme="https",
                netloc=AUTHORIZATION_SERVER,
                url="/u/login/password",
                params="",
                query=urlencode(query_params),
                fragment="",
            )
        )

        auth_body = {
            "state": self.auth_state["state"],
            "username": self.email,
            "password": self.password,
            "action": "default",
        }

        async with self.websession.post(
            url,
            headers=headers,
            data=auth_body,
            allow_redirects=False,
        ) as resp:

            # In case of wrong credentials there is a state param in the redirect url
            if resp.status == 401:
                message = await resp.json()
                raise WrongCredentials(
                    message.get("message", message.get("description", "Unknown error"))
                )

            _LOGGER.debug(resp)

            resume_url = resp.headers["Location"]
            _LOGGER.debug(f"Resume at {resume_url}")

        _LOGGER.debug("Sleeping 2.5s...")
        await asyncio.sleep(2.5)

        # 4. Resume auth to get authorization code

        url = urlunparse(
            Components(
                scheme="https",
                netloc=AUTHORIZATION_SERVER,
                url=resume_url,
                params="",
                query="",
                fragment="",
            )
        )

        async with self.websession.get(url, allow_redirects=False) as resp:
            location = resp.headers["Location"]
            params = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
            _LOGGER.debug(params)
            self.auth_state["code"] = params["code"][0]
            _LOGGER.debug(f"Got authorization code {self.auth_state['code']}")

        _LOGGER.debug("Sleeping 2.5s...")
        await asyncio.sleep(2.5)

        self._isLoggedIn = True
        return True

    async def getToken(self):
        now = calendar.timegm(datetime.datetime.now().timetuple())
        _LOGGER.debug(f"Get token")
        token = self.token
        if token is None:
            token = await self._requestToken()
            self.token = token

        if token["expiration"] < now:
            token = await self._refreshToken()
            self.token = token

        return self.token

    async def _requestToken(self):
        if not self._isLoggedIn:
            await self._login()

        _LOGGER.debug("POST to access token endpoint:")
        auth_url = f"https://{AUTHORIZATION_SERVER}/oauth/token"
        auth_body = {
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": self.auth_state["code"],
            "redirect_uri": REDIRECT_URI,
        }
        _LOGGER.debug(auth_body)
        _LOGGER.debug("Requesting access token for client id %s", CLIENT_ID)
        now = calendar.timegm(datetime.datetime.now().timetuple())
        async with self.websession.post(
            auth_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=auth_body,
            max_redirects=30,
        ) as resp:
            _LOGGER.debug(f"Response status {resp.status}")
            token_data = await resp.json()
            _LOGGER.debug(token_data)
            jwt = self.jwt_payload_decode(token_data["access_token"])
            token = token_data
            token["expiration"] = now + token_data.get("exp", 3600)
            token["decoded_token"] = jwt
            token["apikey"] = jwt["azp"]
            _LOGGER.debug("Token: %s", token)
            return token

    async def _refreshToken(self):
        _LOGGER.debug("POST to refresh token endpoint:")
        auth_url = f"https://{AUTHORIZATION_SERVER}/oauth/token"
        auth_body = {
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": self.token["refresh_token"],
        }
        _LOGGER.debug(auth_body)
        _LOGGER.debug(
            "Requesting access token using refresh token for client id %s", CLIENT_ID
        )
        now = calendar.timegm(datetime.datetime.now().timetuple())
        async with self.websession.post(
            auth_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=auth_body,
            max_redirects=30,
        ) as resp:
            _LOGGER.debug(f"Response status {resp.status}")
            if resp.status == 200:
                _LOGGER.debug(f"Refresh ok")
                token_data = await resp.json()
                _LOGGER.debug(token_data)
                jwt = self.jwt_payload_decode(token_data["access_token"])
                token = token_data
                token["expiration"] = now + token_data.get("exp", 3600)
                token["decoded_token"] = jwt
                token["apikey"] = jwt["azp"]
                _LOGGER.debug("Token: %s", token)
            else:
                _LOGGER.debug(f"Refresh rejected, restarting authentication flow")
                self._isLoggedIn = False
                token = await self._requestToken()
            return token

    async def get(self, url, params=None):
        try:
            headers = await self._createhead()
            async with self.websession.get(url, params=params, headers=headers) as resp:
                return await resp.json()
        except aiohttp.ClientResponseError as exception_:
            raise PorscheException(exception_.status)

    async def post(self, url, data=None, json=None):
        try:
            headers = await self._createhead()
            async with self.websession.post(
                url, data=data, json=json, headers=headers
            ) as resp:
                return await resp.json()
        except aiohttp.ClientResponseError as exception_:
            raise PorscheException(exception_.status)

    async def put(self, url, data=None, json=None):
        try:
            headers = await self._createhead()
            async with self.websession.put(
                url, data=data, json=json, headers=headers
            ) as resp:
                return await resp.json()
        except aiohttp.ClientResponseError as exception_:
            raise PorscheException(exception_.status)

    async def delete(self, url, data=None, json=None):
        try:
            headers = await self._createhead()
            async with self.websession.delete(
                url, data=data, json=json, headers=headers
            ) as resp:
                return await resp.json()
        except aiohttp.ClientResponseError as exception_:
            raise PorscheException(exception_.status)

    async def _createhead(self):
        now = calendar.timegm(datetime.datetime.now().timetuple())
        token = self.token
        if token is None:
            token = await self._requestToken()
            self.token = token
        if token["expiration"] < now:
            token = await self._refreshToken()
            self.token = token
        xid = str(uuid.uuid4()).upper()
        head = {
            "Authorization": f"Bearer {token['access_token']}",
            "X-Client-ID": self.x_client_id,
            "User-Agent": USER_AGENT,
            "X-Request-ID": xid,
            "X-Trace-ID": xid,
        }
        return head

    def _b64_decode(self, data):
        data += "=" * (4 - len(data) % 4)
        return base64.b64decode(data).decode("utf-8")

    def jwt_payload_decode(self, jwt):
        _, payload, _ = jwt.split(".")
        return json.loads(self._b64_decode(payload))

    async def close(self):
        await self.websession.close()
