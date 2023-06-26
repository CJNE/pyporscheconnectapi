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
import hashlib
import os
import re
import urllib.parse
from typing import Dict, Text
from bs4 import BeautifulSoup

import aiohttp

try:
    from rich import print
except ImportError:
    pass

from .exceptions import WrongCredentials, PorscheException

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

AUTHORIZATION_SERVER="identity.porsche.com"
REDIRECT_URI="https://my.porsche.com/"
AUDIENCE="https://api.porsche.com"
TENANT="porsche-production"
COUNTRY="de"
LANGUAGE="de_DE"
CLIENT_ID="UYsK00My6bCqJdbQhTQ0PbWmcSdIAMig"



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
                "prefix": "https://api.porsche.com/core/api/",
            },
            "profile": {
                "client_id": CLIENT_ID,
                "api_key": "QPw3VOLAMfI7r0nmRY8ELq4RzZpZeXEE",
                "redirect_uri": REDIRECT_URI,
                "prefix": "https://api.porsche.com/profiles",
            },
            # "auth": {
            #     "client_id": "4mPO3OE5Srjb1iaUGWsbqKBvvesya8oA",
            #     "redirect_uri": "https://my.porsche.com/core/de/de_DE/",
            #     "prefix": "https://login.porsche.com",
            # },
            "carcontrol": {
                #"client_id": "Ux8WmyzsOAGGmvmWnW7GLEjIILHEztAs",
                "client_id": CLIENT_ID,
                "redirect_uri": "https://my.porsche.com/myservices/auth/auth.html",
                "prefix": "https://api.porsche.com/",
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
        _LOGGER.debug("Start authentication, get initial state from auth server")
        # Do not follow redirect
        start_login_url = f"https://{AUTHORIZATION_SERVER}/authorize?response_type=code&client_id={CLIENT_ID}&code_challenge_method=S256&redirect_uri={REDIRECT_URI}&ui_locales=de-DE&audience={AUDIENCE}&scope=openid"
        async with self.websession.get(start_login_url, allow_redirects=False) as resp:
            location = resp.headers["Location"]
            params = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
            _LOGGER.debug(params)
            have_code = params.get('code', None)
            if have_code is not None:
                _LOGGER.debug("We already have a code in session, skip login")
                self.auth_state['code'] = have_code
                return
            self.auth_state["state"] = params["state"][0]
            self.auth_state["client"] = params["client"][0]
        _LOGGER.debug(self.auth_state)


        # Post auth data
        _LOGGER.debug("POST authentication details....")
        auth_body = {
                "sec": "high",
                "username": self.email,
                "password": self.password,
                "code_challenge_method": "S256",
                "redirect_uri": REDIRECT_URI,
                "ui_locales": "de-DE",
                "audience": AUDIENCE,
                "client_id": CLIENT_ID,
                "connection": "Username-Password-Authentication",
                "state": self.auth_state["state"],
                "tenant": TENANT,
                "response_type": "code"
                }
        auth_url = f"https://{AUTHORIZATION_SERVER}/usernamepassword/login"
        verify_body = {} 
        async with self.websession.post(auth_url, headers={"Content-Type": "application/x-www-form-urlencoded"}, data=auth_body, max_redirects=30) as resp:
            # In case of wrong credentials there is a state param in the redirect url

            if resp.status == 401:
                message = await resp.json()
                raise WrongCredentials(message.get('message', message.get('description', 'Unknown error')))

            html_body = await resp.text()

            _LOGGER.debug(resp.status)
            _LOGGER.debug(html_body)

            soup = BeautifulSoup(html_body,features="html.parser")
            hidden_tags = soup.find_all("input", type="hidden")
            for tag in hidden_tags:
                verify_body[tag.attrs['name']] = tag.attrs['value']
            _LOGGER.debug(verify_body)

        # Follow callback
        _LOGGER.debug("POST authentication verification...")
        auth_url = f"https://{AUTHORIZATION_SERVER}/login/callback"
        resume_url = ""
        async with self.websession.post(auth_url, headers={"Content-Type": "application/x-www-form-urlencoded"}, data=verify_body, allow_redirects=False) as resp:
            resume_url = resp.headers['Location']
            _LOGGER.debug(f"Resume at {resume_url}")

        _LOGGER.debug("Sleeping 2.5s...")
        await asyncio.sleep(2.5)

        # Resume auth
        auth_url = f"https://{{AUTHORIZATION_SERVER}}{resume_url}"
        async with self.websession.get(start_login_url, allow_redirects=False) as resp:
            location = resp.headers["Location"]
            params = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
            _LOGGER.debug(params)
            self.auth_state["code"] = params["code"][0]
            _LOGGER.debug(f"Got code {self.auth_state['code']}")

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


        _LOGGER.debug("POST to acces token endpoint...")
        auth_url = f"https://{AUTHORIZATION_SERVER}/oauth/token"
        auth_body = {
                "client_id": application['client_id'],
                "grant_type": "authorization_code",
                "code": self.auth_state['code'],
                "redirect_uri": REDIRECT_URI
                }
        _LOGGER.debug(auth_body)
        _LOGGER.debug( "Requesting access token for client id %s", application["client_id"])
        now = calendar.timegm(datetime.datetime.now().timetuple())
        async with self.websession.post(auth_url, headers={"Content-Type": "application/x-www-form-urlencoded"}, data=auth_body, max_redirects=30) as resp:
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
