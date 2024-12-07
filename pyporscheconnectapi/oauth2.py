#  SPDX-License-Identifier: Apache-2.0
import asyncio
import logging
import time
import httpx
import base64

from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from collections import namedtuple

from typing import Dict, Text

from .const import (
    AUTHORIZATION_SERVER,
    AUTHORIZATION_URL,
    CLIENT_ID,
    REDIRECT_URI,
    AUDIENCE,
    SCOPE,
    TOKEN_URL,
    TIMEOUT,
    USER_AGENT,
    X_CLIENT_ID,
)
from .exceptions import (
    PorscheCaptchaRequired,
    PorscheWrongCredentials,
    PorscheException,
)

_LOGGER = logging.getLogger(__name__)

Credentials = namedtuple("Credentials", ["email", "password"])
Captcha = namedtuple("Captcha", ["captcha_code", "state"])


class OAuth2Token(dict):
    """
    A simple wrapper around a dict to handle OAuth2 tokens. Provides a helper
    method to check if the token is expired.

    Originally based on: https://github.com/lepture/authlib/blob/master/authlib/oauth2/rfc6749/wrappers.py
    """

    def __init__(self, params: Dict):
        if params.get("expires_at"):
            self["expires_at"] = int(params["expires_at"])
        elif params.get("expires_in"):
            self.expires_at = params["expires_in"]
        super().__init__(params)

    def is_expired(self, leeway=60):
        expires_at = self.get("expires_at")
        if not expires_at:
            return None
        # small timedelta to consider token as expired before it actually expires
        expiration_threshold = expires_at - leeway
        return expiration_threshold < time.time()

    @property
    def expires_at(self):
        return self.get("expires_at")

    @property
    def access_token(self):
        return self.get("access_token")

    @property
    def refresh_token(self):
        return self.get("refresh_token")

    @expires_at.setter
    def expires_at(self, expires_in):
        self["expires_at"] = int(time.time()) + int(expires_in)


class OAuth2Client:
    """
    Utility class to handle OAuth2 authentication with Porsche Connect

    :param client: httpx.AsyncClient
    :param credentials: tuple of email, password
    :param leeway: time in seconds to consider token as expired before it actually expires
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        credentials: Credentials,
        captcha: Captcha,
        leeway: int = 60,
    ):
        self.client = client
        self.credentials = credentials
        self.captcha = captcha
        self.leeway = leeway
        self.headers = {"User-Agent": USER_AGENT, "X-Client-ID": X_CLIENT_ID}

    async def ensure_valid_token(self, token: OAuth2Token):
        """
        Ensure the access_token is valid, logging in or refreshing if necessary
        """
        token_is_expired = token.is_expired(self.leeway)
        if token_is_expired:
            token_data = await self.refresh_token(token.refresh_token)
            token.update(token_data)
            token.expires_at = token_data["expires_in"]
            _LOGGER.debug(f"Refreshed Access Token: {token.access_token}")
        if (
            token.access_token is None or token_is_expired is None
        ):  # no token, get a new one
            auth_code = await self.fetch_authorization_code()
            token_data = await self.fetch_access_token(auth_code)
            token.update(token_data)
            token.expires_at = token_data["expires_in"]
            _LOGGER.debug(f"New Access Token: {token.access_token}")

    async def fetch_authorization_code(self):
        """
        Fetch the authorization code from Porsche Connect

        Requires 1-4 requests (1 if already logged in, 4 if not):

        1. Initial request to /authorize to get the code
        2. If no code is returned, login with Identifier First flow:
            2a. POST to /u/login/identifier with email
            2b. POST to /u/login/password with password
        3. Resume the /authorize request with the resume path from the Identifier First flow

        :return: authorization code to be exchanged for an access token
        """
        if self.captcha.captcha_code is None:
            try:
                _LOGGER.debug(f"Fetching authorization code.")

                # first request to get the code
                params = await self.get_and_extract_location_params(
                    AUTHORIZATION_URL,
                    params={
                        "response_type": "code",
                        "client_id": CLIENT_ID,
                        "redirect_uri": REDIRECT_URI,
                        "audience": AUDIENCE,
                        "scope": SCOPE,
                        "state": "pyporscheconnectapi",
                    },
                )
                authorization_code = params.get("code", [None])[0]

                # if we already have a session with Auth, just use the code they return
                if authorization_code is not None:
                    _LOGGER.debug(f"Got authorization code: {authorization_code}")
                    return authorization_code

                # no existing Auth0 session, run through Identifier First flow
                _LOGGER.debug(
                    f"No existing auth0 session, running through identifier first flow."
                )

                resume_path = await self.login_with_identifier(params["state"][0])

                # completed the Identifier First flow, now resume the auth code request
                params = await self.get_and_extract_location_params(
                    f"https://{AUTHORIZATION_SERVER}{resume_path}"
                )
                authorization_code = params.get("code", [None])[0]
                _LOGGER.debug(f"Authorization code: {authorization_code}")

                return authorization_code

            except httpx.HTTPStatusError as exception_:
                raise PorscheException(exception_.response.status_code)
        else:
            try:
                resume_path = await self.login_with_identifier(self.captcha.state)
                params = await self.get_and_extract_location_params(
                    f"https://{AUTHORIZATION_SERVER}{resume_path}"
                )
                authorization_code = params.get("code", [None])[0]
                _LOGGER.debug(f"Authorization code: {authorization_code}")

                return authorization_code

            except httpx.HTTPStatusError as exception_:
                raise PorscheException(exception_.response.status_code)

    async def get_and_extract_location_params(self, url, params={}):
        """
        GET the URL and extract the params from the Location header

        :param url: URL to GET
        :param params: dict of query parameters
        :return: dict of query parameters from the Location header
        """
        resp = await self.client.get(
            url, params=params, timeout=TIMEOUT, headers=self.headers
        )
        if resp.status_code != 302:
            raise PorscheException("Could not fetch authorization code")

        location = resp.headers["Location"]
        return self._extract_params_from_url(location)

    def _extract_params_from_url(self, url):
        """
        Extract the query parameters from a URL

        :param url: URL to extract the query parameters from
        :return: dict of query parameters
        """
        return parse_qs(urlparse(url).query)

    async def login_with_identifier(self, state: Text):
        """
        Logs into the Identifier First flow

        Takes 2 steps:

        1. POST to /u/login/identifier with email
        2. POST to /u/login/password with password

        :param state: state parameter from the initial authorize request
        :return: URL to resume the auth code request
        """

        if self.captcha.captcha_code is None:
            # 1. /u/login/identifier w/ email

            _LOGGER.debug(f"Submitting e-mail address to auth endpoint.")

            data = {
                "state": state,
                "username": self.credentials.email,
                "js-available": True,
                "webauthn-available": False,
                "is-brave": False,
                "webauthn-platform-available": False,
                "action": "default",
            }

            url = f"https://{AUTHORIZATION_SERVER}/u/login/identifier"
            resp = await self.client.post(
                url,
                data=data,
                params={"state": state},
                timeout=TIMEOUT,
                headers=self.headers,
            )

            if resp.status_code == 401:
                raise PorscheWrongCredentials("Wrong credentials")

            # In case captcha verification is required, the response code is 400 and the captcha is provided as a svg image
            if resp.status_code == 400:
                _LOGGER.debug(f"Captcha required.")
                soup = BeautifulSoup(resp.text, "html.parser")
                captcha = str(soup.find("img", {"alt": "captcha"}))
                _LOGGER.debug(f"Parsed out SVG captcha: {captcha}")
                raise PorscheCaptchaRequired(captcha=captcha, state=state)
        else:
            # 1. /u/login/identifier w/ email

            _LOGGER.debug(
                f"Submitting e-mail address and captcha code {captcha} to auth endpoint."
            )

            data = {
                "state": state,
                "username": self.credentials.email,
                "captcha": self.captcha.captcha_code,
                "js-available": True,
                "webauthn-available": False,
                "is-brave": False,
                "webauthn-platform-available": False,
                "action": "default",
            }

            url = f"https://{AUTHORIZATION_SERVER}/u/login/identifier"
            resp = await self.client.post(
                url,
                data=data,
                params={"state": state},
                timeout=TIMEOUT,
                headers=self.headers,
            )

            if resp.status_code == 401:
                raise PorscheWrongCredentials("Wrong credentials")

            # In case captcha verification is required, the response code is 400 and the captcha is provided as a svg image
            if resp.status_code == 400:
                _LOGGER.debug(f"Captcha required again: {captcha}")
                soup = BeautifulSoup(resp.text, "html.parser")
                captcha = str(soup.find("img", {"alt": "captcha"}))
                _LOGGER.debug(f"Parsed out SVG captcha: {captcha}")
                raise PorscheCaptchaRequired(captcha=captcha, state=state)

        # 2. /u/login/password w/ password

        _LOGGER.debug(f"Submitting password to auth endpoint.")

        data = {
            "state": state,
            "username": self.credentials.email,
            "password": self.credentials.password,
            "action": "default",
        }

        url = f"https://{AUTHORIZATION_SERVER}/u/login/password"
        resp = await self.client.post(
            url,
            data=data,
            params={"state": state},
            timeout=TIMEOUT,
            headers=self.headers,
        )

        # In case of wrong password, the response code is 400 (Bad request)
        if resp.status_code == 400:
            _LOGGER.debug(f"Invalid credentials.")
            raise PorscheWrongCredentials("Wrong credentials")

        resume_url = resp.headers["Location"]
        _LOGGER.debug(f"Resume at {resume_url}")

        _LOGGER.debug("Sleeping 2.5s...")
        await asyncio.sleep(2.5)

        return resume_url

    async def fetch_access_token(self, authorization_code):
        """
        Exchanges the authorization code for an access token

        :param authorization_code: authorization code from the /authorize request
        :return: access token
        """
        data = {
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": REDIRECT_URI,
        }

        try:
            _LOGGER.debug(f"Exchanging the authorization code for an access token.")

            resp = await self.client.post(
                TOKEN_URL, data=data, timeout=TIMEOUT, headers=self.headers
            )
            resp.raise_for_status()
            token_data = resp.json()
            return token_data
        except httpx.HTTPStatusError as exception_:
            raise PorscheException(exception_.response.status_code)

    async def refresh_token(self, refresh_token):
        """
        Uses the provided refresh token to get a new access token

        :param refresh_token: refresh token
        :return: access token
        """
        data = {
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        try:
            _LOGGER.debug(f"Using the refresh token to get a new access token.")

            resp = await self.client.post(
                TOKEN_URL, data=data, timeout=TIMEOUT, headers=self.headers
            )
            resp.raise_for_status()
            token_data = resp.json()
            return token_data
        except httpx.HTTPStatusError as exception_:
            # 403 usually means the refresh token is invalid
            # clear the access token so the full login flow can happen again
            if exception_.response.status_code == 403:
                return {"access_token": None, "expires_in": 0}
            else:
                raise PorscheException(exception_.response.status_code)
