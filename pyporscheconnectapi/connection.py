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

import aiohttp
from yarl import URL

from .exceptions import IncompleteCredentials, PorscheException

_LOGGER = logging.getLogger(__name__)


class Connection:
    """Connection to Porsche Connect API."""

    def __init__(
        self,
        email: Text = None,
        password: Text = None,
        websession: aiohttp.ClientSession = None,
        access_token: Text = None,
        refresh_token: Text = None,
        id_token: Text = None,
        expiration: int = 0,
    ) -> None:
        """Initialize connection object."""
        self.user_agent: Text = "Android REL 4.4.4; en_US"
        self.client_id: Text = "TZ4Vf5wnKeipJxvatJ60lPHYEzqZ4WNp"
        self.porscheCookiedomain: Text = "https://login.porsche.com"
        self.porscheLogin: Text = "https://login.porsche.com/auth/de/de_DE"
        self.porscheLoginAuth: Text = "https://login.porsche.com/auth/api/v1/de/de_DE/public/login"
        self.porscheAPIClientID: Text = "TZ4Vf5wnKeipJxvatJ60lPHYEzqZ4WNp"
        self.porscheAPIRedirectURI: Text = "https://my-static02.porsche.com/static/cms/auth.html"
        self.porscheAPIAuth: Text = "https://login.porsche.com/as/authorization.oauth2"
        self.porscheAPIToken: Text = "https://login.porsche.com/as/token.oauth2"
        self.porscheAPI: Text = "https://connect-portal.porsche.com/core/api/v3/de/de_DE"

        self.expiration: int = expiration
        self.access_token = access_token
        self.email = email
        self.password = password
        self.head = None
        self.refresh_token = refresh_token
        self.websession = websession
        self.token_refreshed = False
        if self.websession == None:
            self.websession = aiohttp.ClientSession()
        if self.access_token:
            self.__sethead(access_token=self.access_token, expiration=self.expiration)
            _LOGGER.debug("Connecting with existing access token")


    async def authFlow(self):
        now = calendar.timegm(datetime.datetime.now().timetuple())
        if now > self.expiration:

            _LOGGER.debug("Start authentication, get initial state from login page....")
            async with self.websession.get(self.porscheLogin) as resp:
                cookies = self.websession.cookie_jar.filter_cookies(self.porscheCookiedomain)
                #sec = cookies['sec'].value
                #resume = cookes['resume'].value
                #state = cookies['state'].value
                #thirdPartyId = cookies['thirdPartyId'].value
                sec = ''
                resume = ''
                state = ''
                thirdPartyId = ''


            login_data = { 'sec': sec, 'resume': resume, 'thirdPartyId': thirdPartyId, 'state': state, 'username':
                    self.email, 'password': self.password, 'keeploggedin': 'false' }

            _LOGGER.debug("POST authentication details....")
            async with self.websession.post(self.porscheLoginAuth,  data=login_data, max_redirects=30) as resp:
                _LOGGER.debug("Login AUTH Headers %s", resp.headers)

            code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8')
            code_verifier = re.sub('[^a-zA-Z0-9]+', '', code_verifier)

            code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
            code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
            code_challenge = code_challenge.replace('=', '')

            auth_data = { 'scope': 'openid', 'response_type': 'code', 'access_type': 'offline', 'prompt': 'none',
                    'client_id': self.porscheAPIClientID, 'redirect_uri': self.porscheAPIRedirectURI,
                    'code_challenge': code_challenge, 'code_challenge_method': 'S256' }

            async with self.websession.get(self.porscheAPIAuth, params=auth_data) as resp:
                last_location = resp.history[len(resp.history) - 1].headers['Location']
                query = urllib.parse.urlparse(last_location).query
                redirect_params = urllib.parse.parse_qs(query)
                auth_code = redirect_params['code'][0]
                _LOGGER.debug("Code %s", auth_code)

            auth_token_data = { 'grant_type': 'authorization_code', 'client_id': self.porscheAPIClientID,
                    'redirect_uri': self.porscheAPIRedirectURI, 'code': auth_code, 'prompt': 'none',
                    'code_verifier': code_verifier }
            _LOGGER.debug("Data %s", auth_token_data)

            async with self.websession.post(self.porscheAPIToken, data=auth_token_data) as resp:
                token_data = await resp.json()
                _LOGGER.debug('Token data %s', token_data)
                self.id_token = token_data['id_token']
                self.__sethead(
                    access_token=token_data["access_token"], expires_in=token_data["expires_in"]
                )

            #self.refresh_token = auth["refresh_token"]
            #self.token_refreshed = True

    async def get(self, url, params = None):
        try:
            await self.authFlow()
            async with self.websession.get(url, params=params, headers=self.head) as resp:
                return await resp.json()
        except aiohttp.ClientResponseError as exception_:
            raise PorscheException(exception_.status)

    async def post(self, url, data=None):
        try:
            await self.authFlow()
            async with self.websession.post(url, data=data, headers=self.head) as resp:
                return await resp.json()
        except aiohttp.ClientResponseError as exception_:
            raise PorscheException(exception_.status)

    def __sethead(
        self, access_token: Text, expires_in: int = 1800, expiration: int = 0
    ):
        """Set HTTP header."""
        self.access_token = access_token
        if expiration > 0:
            self.expiration = expiration
        else:
            now = calendar.timegm(datetime.datetime.now().timetuple())
            self.expiration = now + expires_in
        self.head = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": self.user_agent,
        }
    async def close(self):
        await self.websession.close()

