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
from urllib.parse import urlunparse, urlencode
from collections import namedtuple
from typing import Dict, Text
from bs4 import BeautifulSoup

import aiohttp

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

AUTHORIZATION_SERVER = "identity.porsche.com"
REDIRECT_URI = "https://my.porsche.com/"
AUDIENCE = "https://api.porsche.com"
CLIENT_ID = "UYsK00My6bCqJdbQhTQ0PbWmcSdIAMig"
SCOPE="openid profile email pid:user_profile.addresses:read pid:user_profile.birthdate:read pid:user_profile.dealers:read pid:user_profile.emails:read pid:user_profile.locale:read pid:user_profile.name:read pid:user_profile.phones:read pid:user_profile.porscheid:read pid:user_profile.vehicles:read pid:user_profile.vehicles:register"

class Connection:
    """Connection to Porsche Connect API."""

    def __init__(
        self,
        email: Text = None,
        password: Text = None,
        websession: aiohttp.ClientSession = None,
        language: Text = "de",
        country: Text = "DE",
        tokens=None,
    ) -> None:
        """Initialize connection object."""
        self.porscheApplications = {
            "api": {
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "prefix": "https://api.porsche.com",
            },
        }

        self.isTokenRefreshed = False
        self.tokens = tokens or {}
        self.email = email
        self.password = password
        self.websession = websession
        self._isLoggedIn = False
        self.country = country
        self.language = language
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
            "ui_locales": self.language + "-" + self.country,
            "audience": AUDIENCE,
            "scope": SCOPE,
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

        async with self.websession.get(url, allow_redirects=False) as resp:
            location = resp.headers["Location"]
            params = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
            _LOGGER.debug(params)
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
            headers={"Content-Type": "application/x-www-form-urlencoded"},
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
                _LOGGER.debug(html_body)
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
            headers={"Content-Type": "application/x-www-form-urlencoded"},
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

    async def getAllTokens(self):
        now = calendar.timegm(datetime.datetime.now().timetuple())
        for applicationKey in self.porscheApplications:
            application = self.porscheApplications[applicationKey]
            _LOGGER.debug(f"Get token for app {applicationKey}")
            token = self.tokens.get(application["client_id"], None)
            if token is None or token["expiration"] < now:
                token = await self._requestToken(application)
                self.tokens[application["client_id"]] = token
        self.isTokenRefreshed = False
        return self.tokens

    async def _requestToken(self, application: Dict, wasExpired=False):
        if not self._isLoggedIn or wasExpired:
            await self._login()

        _LOGGER.debug("POST to access token endpoint...")
        auth_url = f"https://{AUTHORIZATION_SERVER}/oauth/token"
        auth_body = {
            "client_id": application["client_id"],
            "grant_type": "authorization_code",
            "code": self.auth_state["code"],
            "redirect_uri": REDIRECT_URI,
        }
        _LOGGER.debug(auth_body)
        _LOGGER.debug(
            "Requesting access token for client id %s", application["client_id"]
        )
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
            self.isTokenRefreshed = True
            return token

    async def get(self, url, params=None):
        try:
            application = self._applicationForURL(url)
            headers = await self._createhead(application)
            async with self.websession.get(url, params=params, headers=headers) as resp:
                return await resp.json()
        except aiohttp.ClientResponseError as exception_:
            raise PorscheException(exception_.status)

    async def post(self, url, data=None, json=None):
        try:
            application = self._applicationForURL(url)
            headers = await self._createhead(application)
            async with self.websession.post(
                url, data=data, json=json, headers=headers
            ) as resp:
                return await resp.json()
        except aiohttp.ClientResponseError as exception_:
            raise PorscheException(exception_.status)

    async def put(self, url, data=None, json=None):
        try:
            application = self._applicationForURL(url)
            headers = await self._createhead(application)
            async with self.websession.put(
                url, data=data, json=json, headers=headers
            ) as resp:
                return await resp.json()
        except aiohttp.ClientResponseError as exception_:
            raise PorscheException(exception_.status)

    async def delete(self, url, data=None, json=None):
        try:
            application = self._applicationForURL(url)
            headers = await self._createhead(application)
            async with self.websession.delete(
                url, data=data, json=json, headers=headers
            ) as resp:
                return await resp.json()
        except aiohttp.ClientResponseError as exception_:
            raise PorscheException(exception_.status)

    def _applicationForURL(self, url):
        for key in self.porscheApplications:
            app = self.porscheApplications[key]
            if url.startswith(app["prefix"]):
                return app
        # else return None
        return None

    async def _createhead(self, application):
        # If no application matched the request URL then no auth headers are added
        if application is None:
            return {}
        now = calendar.timegm(datetime.datetime.now().timetuple())
        token = self.tokens.get(application["client_id"], None)
        if token is None or token["expiration"] < now:
            token = await self._requestToken(
                application, wasExpired=(token is not None)
            )
            self.tokens[application["client_id"]] = token
        head = {
            "Authorization": f"Bearer {token['access_token']}",
            "origin": "https://my.porsche.com",
            "apikey": application.get("api_key", token["apikey"]),
            "x-vrs-url-country": self.country.lower(),
            "x-vrs-url-language": f"{self.language.lower()}_{self.country.upper()}",
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
