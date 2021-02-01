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
        tokens = {}
    ) -> None:
        """Initialize connection object."""
        self.porscheCookiedomain: Text = "https://login.porsche.com"
        self.porscheLogin: Text = "https://login.porsche.com/auth/de/de_DE"
        self.porscheLoginAuth: Text = "https://login.porsche.com/auth/api/v1/de/de_DE/public/login"
        self.porscheAPIAuth: Text = "https://login.porsche.com/as/authorization.oauth2"
        self.porscheAPIToken: Text = "https://login.porsche.com/as/token.oauth2"
        self.porscheAPI: Text = "https://connect-portal.porsche.com/core/api/v3/de/de_DE"
        self.porscheApplications = {
                'portal': {
                    'client_id': 'TZ4Vf5wnKeipJxvatJ60lPHYEzqZ4WNp', 
                    'redirect_uri': 'https://my-static02.porsche.com/static/cms/auth.html',
                    'prefix': 'https://connect-portal.porsche.com/core/api/v3/'
                    },
                'carcontrol': { 
                    'client_id': 'gZLSI7ThXFB4d2ld9t8Cx2DBRvGr1zN2',
                    'redirect_uri':  'https://connect-portal.porsche.com/myservices/auth/auth.html',
                    'prefix': 'https://api.porsche.com/service-vehicle/'
                    }
                }

        self.tokens = tokens
        self.email = email
        self.password = password
        self.websession = websession
        self._isLoggedIn = False
        if self.websession == None:
            self.websession = aiohttp.ClientSession()


    async def _login(self):
        _LOGGER.debug("Start authentication, get initial state from login page....")
        async with self.websession.get(self.porscheLogin) as resp:
            cookies = self.websession.cookie_jar.filter_cookies(self.porscheCookiedomain)
            sec = ''
            resume = ''
            state = ''
            thirdPartyId = ''

        login_data = { 'sec': sec, 'resume': resume, 'thirdPartyId': thirdPartyId, 'state': state, 'username':
                self.email, 'password': self.password, 'keeploggedin': 'false' }

        _LOGGER.debug("POST authentication details....")
        async with self.websession.post(self.porscheLoginAuth,  data=login_data, max_redirects=30) as resp:
            _LOGGER.debug("Login AUTH Headers %s", resp.headers)
        self._isLoggedIn = True


    async def _requestToken(self, application: Dict):
        if not self._isLoggedIn:
            await self._login()

        _LOGGER.debug("Requesting access token for client id %s", application['client_id'])

        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8')
        code_verifier = re.sub('[^a-zA-Z0-9]+', '', code_verifier)

        code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
        code_challenge = code_challenge.replace('=', '')

        auth_data = { 
                'scope': 'openid',
                'response_type': 'code',
                'access_type': 'offline',
                'prompt': 'none',
                'client_id': application['client_id'],
                'redirect_uri': application['redirect_uri'],
                'code_challenge': code_challenge,
                'code_challenge_method': 'S256'
                }

        async with self.websession.get(self.porscheAPIAuth, params=auth_data) as resp:
            last_location = resp.history[len(resp.history) - 1].headers['Location']
            query = urllib.parse.urlparse(last_location).query
            redirect_params = urllib.parse.parse_qs(query)
            auth_code = redirect_params['code'][0]
            _LOGGER.debug("Code %s", auth_code)

        auth_token_data = {
                'grant_type': 'authorization_code', 
                'client_id': application['client_id'],
                'redirect_uri': application['redirect_uri'],
                'code': auth_code,
                'prompt': 'none',
                'code_verifier': code_verifier
                }
        _LOGGER.debug("Data %s", auth_token_data)

        now = calendar.timegm(datetime.datetime.now().timetuple())
        async with self.websession.post(self.porscheAPIToken, data=auth_token_data) as resp:
            token_data = await resp.json()
            jwt = self.jwt_payload_decode(token_data['id_token'])
            token = token_data
            token['expiration'] = now + token_data['expires_in']
            token['decoded_token'] = jwt
            token['apikey'] = jwt['aud']
            _LOGGER.debug('Token: %s', token)
            return token

    async def get(self, url, params = None):
        try:
            application = self._applicationForURL(url)
            headers = await self._createhead(application)
            async with self.websession.get(url, params=params, headers=headers) as resp:
                return await resp.json()
        except aiohttp.ClientResponseError as exception_:
            raise PorscheException(exception_.status)

    async def post(self, url, data=None):
        try:
            application = self._applicationForURL(url)
            headers = await self._createhead(application)
            async with self.websession.post(url, data=data, headers=headers) as resp:
                return await resp.json()
        except aiohttp.ClientResponseError as exception_:
            raise PorscheException(exception_.status)

    def _applicationForURL(self, url):
       for key in self.porscheApplications:
           app = self.porscheApplications[key]
           if url.startswith(app['prefix']): 
               return app
       # else raise an exception
       raise f"Unsupported URL prefix {url}"

    async def _createhead(self, application):
        now = calendar.timegm(datetime.datetime.now().timetuple())
        token = self.tokens.get(application['client_id'], None)
        if token is None or token['expiration'] < now:
            token = await self._requestToken(application)
            self.tokens[application['client_id']] = token
        head = {
            "Authorization": f"Bearer {token['access_token']}",
            "apikey": token['apikey']
            }
        return head

    def _b64_decode(self, data):
        data += '=' * (4 - len(data) % 4)
        return base64.b64decode(data).decode('utf-8')

    def jwt_payload_decode(self, jwt):
        _, payload, _ = jwt.split('.')
        return json.loads(self._b64_decode(payload))

    async def close(self):
        await self.websession.close()

