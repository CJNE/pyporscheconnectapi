"""Authentication token management for Porsche Connect API."""

#  SPDX-License-Identifier: Apache-2.0
import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import time
from typing import NamedTuple
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .const import (
    AUDIENCE,
    AUTHORIZATION_SERVER,
    AUTHORIZATION_URL,
    CLIENT_ID,
    REDIRECT_URI,
    SCOPE,
    TIMEOUT,
    TOKEN_URL,
    USER_AGENT,
    X_CLIENT_ID,
)
from .exceptions import (
    PorscheCaptchaRequiredError,
    PorscheExceptionError,
    PorscheWrongCredentialsError,
)

_LOGGER = logging.getLogger(__name__)


class Credentials(NamedTuple):
    """Store credentials for the Porsche Connect API."""

    email: str
    password: str


class Captcha(NamedTuple):
    """Store captcha data for the Porsche Connect API."""

    captcha_code: str
    state: str


class OAuth2Token(dict):
    """A simple wrapper around a dict to handle OAuth2 tokens.

    Provides a helper method to check if the token is expired.
    Originally based on: https://github.com/lepture/authlib/blob/master/authlib/oauth2/rfc6749/wrappers.py
    """

    def __init__(self, params: dict):
        """Initialise the oauth2 token."""
        if params.get("expires_at"):
            self["expires_at"] = int(params["expires_at"])
        elif params.get("expires_in"):
            self.expires_at = params["expires_in"]
        super().__init__(params)

    def is_expired(self, leeway=60):
        """Return true if the access token has expired."""
        expires_at = self.get("expires_at")
        if not expires_at:
            return None
        # small timedelta to consider token as expired before it actually expires
        expiration_threshold = expires_at - leeway
        return expiration_threshold < time.time()

    @property
    def expires_at(self):
        """Return the expiration time stamp of the access token."""
        return self.get("expires_at")

    @property
    def access_token(self):
        """Return the access token."""
        return self.get("access_token")

    @property
    def refresh_token(self):
        """Return the refresh token."""
        return self.get("refresh_token")

    @expires_at.setter
    def expires_at(self, expires_in):
        self["expires_at"] = int(time.time()) + int(expires_in)


class OAuth2Client:
    """Utility class to handle OAuth2 authentication with Porsche Connect.

    :param client: httpx.AsyncClient
    :param credentials: tuple of email, password
    :param leeway: time in seconds to consider token as expired before it actually expires
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        credentials: Credentials,
        captcha: Captcha,
        code_verifier: str | None = None,
        leeway: int = 60,
    ):
        """Initialise the oauth2 client."""
        self.client = client
        self.credentials = credentials
        self.captcha = captcha
        self.leeway = leeway
        self.code_verifier = code_verifier
        self.headers = {"User-Agent": USER_AGENT, "X-Client-ID": X_CLIENT_ID}

    def _generate_pkce_verifier(self) -> str:
        """Generate an Auth0-compatible PKCE verifier."""
        return base64.urlsafe_b64encode(os.urandom(64)).rstrip(b"=").decode("ascii")

    def _build_pkce_challenge(self, verifier: str) -> str:
        """Generate a S256 code challenge from the verifier."""
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def _extract_universal_login_context(self, html: str) -> dict | None:
        """Extract Auth0 universal login context from inline base64 JSON."""
        match = re.search(r'atob\("([A-Za-z0-9+/=]+)"\)', html)
        if not match:
            return None

        try:
            payload = base64.b64decode(match.group(1))
            return json.loads(payload.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            return None

    def _extract_captcha_from_login_html(self, html: str) -> str | None:
        """Extract captcha image data from Porsche/Auth0 login HTML.

        Older pages exposed the captcha as a regular <img alt="captcha">. The
        current Porsche login page embeds the full login context as a base64
        payload in `window.universal_login_context`, including
        `screen.captcha.image`.
        """
        soup = BeautifulSoup(html, "html.parser")
        captcha_img = soup.find("img", {"alt": "captcha"})
        if captcha_img and captcha_img.get("src"):
            return captcha_img["src"]

        context = self._extract_universal_login_context(html)
        if context is None:
            return None

        return context.get("screen", {}).get("captcha", {}).get("image")

    async def ensure_valid_token(self, token: OAuth2Token):
        """Ensure the access_token is valid, logging in or refreshing if necessary."""
        token_is_expired = token.is_expired(self.leeway)
        if token_is_expired:
            token_data = await self.refresh_token(token.refresh_token)
            token.update(token_data)
            token.expires_at = token_data["expires_in"]
            _LOGGER.debug("Refreshed Access Token: %s", token.access_token)
        if token.access_token is None or token_is_expired is None:  # no token, get a new one
            auth_code = await self.fetch_authorization_code()
            token_data = await self.fetch_access_token(auth_code)
            token.update(token_data)
            token.expires_at = token_data["expires_in"]
            _LOGGER.debug("New Access Token: %s", token.access_token)

    async def fetch_authorization_code(self):
        """Fetch the authorization code from Porsche Connect.

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
                _LOGGER.debug("Fetching authorization code.")

                # first request to get the code
                self.code_verifier = self._generate_pkce_verifier()
                params = await self.get_and_extract_location_params(
                    AUTHORIZATION_URL,
                    params={
                        "response_type": "code",
                        "client_id": CLIENT_ID,
                        "redirect_uri": REDIRECT_URI,
                        "audience": AUDIENCE,
                        "scope": SCOPE,
                        "response_mode": "query",
                        "code_challenge": self._build_pkce_challenge(self.code_verifier),
                        "code_challenge_method": "S256",
                        "state": "pyporscheconnectapi",
                    },
                )
                authorization_code = params.get("code", [None])[0]

                # if we already have a session with Auth, just use the code they return
                if authorization_code is not None:
                    _LOGGER.debug("Got authorization code: %s", authorization_code)
                    return authorization_code

                # no existing Auth0 session, run through Identifier First flow
                _LOGGER.debug(
                    "No existing auth0 session, running through identifier first flow.",
                )

                resume_path = await self.login_with_identifier(params["state"][0])

                # completed the Identifier First flow, now resume the auth code request
                authorization_code = await self.resume_authorization_code_flow(
                    self._resolve_resume_url(resume_path),
                )

            except httpx.HTTPStatusError as exc:
                raise PorscheExceptionError(exc.response.status_code) from exc

            else:
                _LOGGER.debug("Authorization code: %s", authorization_code)
                return authorization_code

        else:
            try:
                if self.code_verifier is None:
                    self.code_verifier = self._generate_pkce_verifier()
                resume_path = await self.login_with_identifier(self.captcha.state)
                authorization_code = await self.resume_authorization_code_flow(
                    self._resolve_resume_url(resume_path),
                )

            except httpx.HTTPStatusError as exc:
                raise PorscheExceptionError(exc.response.status_code) from exc

            else:
                _LOGGER.debug("Authorization code: %s", authorization_code)
                return authorization_code

    async def get_and_extract_location_params(self, url, params=None):
        """GET the URL and extract the params from the Location header.

        :param url: URL to GET
        :param params: dict of query parameters
        :return: dict of query parameters from the Location header
        """
        if params is None:
            params = {}
        resp = await self.client.get(
            url,
            params=self._merge_query_params(url, params),
            timeout=TIMEOUT,
            headers=self.headers,
        )
        if resp.status_code != 302:
            msg = "Could not fetch authorization code"
            raise PorscheExceptionError(msg)

        location = resp.headers["Location"]
        return self._extract_params_from_url(location)

    def _extract_params_from_url(self, url):
        """Extract the query parameters from a URL.

        :param url: URL to extract the query parameters from
        :return: dict of query parameters
        """
        return parse_qs(urlparse(url).query)

    def _merge_query_params(self, url: str, params: dict[str, str]) -> dict[str, str]:
        """Merge query parameters into a new dictionary with the existing query parameters of a URL."""
        parsed_url = urlparse(url)
        query = parse_qs(parsed_url.query)
        new_query = {k: v[0] for k, v in query.items()}
        new_query.update(params)
        return new_query

    def _resolve_resume_url(self, resume_path: str) -> str:
        """Resolve resume targets returned by Porsche/Auth0."""
        if resume_path.startswith("http://") or resume_path.startswith("https://"):
            return resume_path
        return f"https://{AUTHORIZATION_SERVER}{resume_path}"

    async def _skip_passkey_enrollment(self, url: str, html: str | None = None) -> str:
        """Skip optional Auth0/Porsche passkey enrollment."""
        if html is None:
            resp = await self.client.get(
                url,
                timeout=TIMEOUT,
                headers=self.headers,
                follow_redirects=False,
            )
            resp.raise_for_status()
            html = resp.text

        context = self._extract_universal_login_context(html)
        if context is None:
            msg = "PASSKEY_ENROLLMENT_CONTEXT_MISSING"
            raise PorscheExceptionError(msg)

        transaction_state = context.get("transaction", {}).get("state")
        if not transaction_state:
            msg = "PASSKEY_ENROLLMENT_STATE_MISSING"
            raise PorscheExceptionError(msg)

        submitted_form_data = context.get("untrustedData", {}).get("submittedFormData") or {}
        data = dict(submitted_form_data)
        data.update(
            {
                "state": transaction_state,
                "action": "abort-passkey-enrollment",
                "acul-sdk": "@auth0/auth0-acul-js@1.2.0",
            },
        )

        resp = await self.client.post(
            url,
            data=data,
            timeout=TIMEOUT,
            headers=self.headers,
            follow_redirects=False,
        )
        if resp.status_code not in (302, 303):
            msg = "PASSKEY_ENROLLMENT_SKIP_FAILED"
            raise PorscheExceptionError(msg)

        return urljoin(url, resp.headers["Location"])

    async def resume_authorization_code_flow(self, url: str) -> str:
        """Follow Auth0 redirects until the final authorization code is returned."""
        current_url = url

        for _ in range(10):
            parsed = urlparse(current_url)
            code = parse_qs(parsed.query).get("code", [None])[0]
            if code is not None:
                return code

            resp = await self.client.get(
                current_url,
                timeout=TIMEOUT,
                headers=self.headers,
                follow_redirects=False,
            )

            if resp.status_code in (302, 303, 307, 308):
                location = urljoin(str(resp.url), resp.headers["Location"])
                parsed = urlparse(location)
                code = parse_qs(parsed.query).get("code", [None])[0]
                if code is not None:
                    return code
                if "/u/passkey-enrollment" in parsed.path:
                    current_url = await self._skip_passkey_enrollment(location)
                    continue
                current_url = location
                continue

            if resp.status_code == 200 and "/u/passkey-enrollment" in resp.url.path:
                current_url = await self._skip_passkey_enrollment(str(resp.url), resp.text)
                continue

            # Porsche may bounce back to the SPA root after login. At this point the
            # Auth0 session is established, so a fresh /authorize request should now
            # yield the final authorization code.
            if resp.status_code == 200 and resp.url.host == "my.porsche.com":
                params = await self.get_and_extract_location_params(
                    AUTHORIZATION_URL,
                    params={
                        "response_type": "code",
                        "client_id": CLIENT_ID,
                        "redirect_uri": REDIRECT_URI,
                        "audience": AUDIENCE,
                        "scope": SCOPE,
                        "response_mode": "query",
                        "code_challenge": self._build_pkce_challenge(self.code_verifier),
                        "code_challenge_method": "S256",
                        "state": "pyporscheconnectapi",
                    },
                )
                code = params.get("code", [None])[0]
                if code is not None:
                    return code
                msg = "AUTHORIZATION_CODE_MISSING_AFTER_PORTAL_RESUME"
                raise PorscheExceptionError(msg)

            msg = "Could not fetch authorization code"
            raise PorscheExceptionError(msg)

        msg = "AUTHORIZATION_CODE_REDIRECT_LOOP"
        raise PorscheExceptionError(msg)

    async def login_with_identifier(self, state: str):
        """Log into the Identifier First flow.

        Takes 2 steps:

        1. POST to /u/login/identifier with email
        2. POST to /u/login/password with password

        :param state: state parameter from the initial authorize request
        :return: URL to resume the auth code request
        """
        # 1. /u/login/identifier w/ email (and captcha code)

        data = {
            "state": state,
            "username": self.credentials.email,
            "js-available": True,
            "webauthn-available": False,
            "is-brave": False,
            "webauthn-platform-available": False,
            "action": "default",
        }

        if self.captcha.captcha_code is None:
            _LOGGER.debug("Submitting e-mail address to auth endpoint.")
        else:
            data.update({"captcha": self.captcha.captcha_code})
            _LOGGER.debug(
                "Submitting e-mail address and captcha code %s to auth endpoint.",
                self.captcha.captcha_code,
            )

        url = f"https://{AUTHORIZATION_SERVER}/u/login/identifier"
        resp = await self.client.post(
            url,
            data=data,
            params={"state": state},
            timeout=TIMEOUT,
            headers=self.headers,
        )

        if resp.status_code == 401:
            msg = "Wrong credentials"
            raise PorscheWrongCredentialsError(msg)

        # In case captcha verification is required, the response code is 400 and the captcha is provided as a svg image
        if resp.status_code == 400:
            _LOGGER.debug("Captcha required.")
            captcha_img = self._extract_captcha_from_login_html(resp.text)
            if captcha_img is None:
                msg = "CAPTCHA_REQUIRED_BUT_NOT_PARSEABLE"
                raise PorscheExceptionError(msg)
            _LOGGER.debug("Parsed out SVG captcha: %s", captcha_img)
            raise PorscheCaptchaRequiredError(captcha=captcha_img, state=state)

        # 2. /u/login/password w/ password

        _LOGGER.debug("Submitting password to auth endpoint.")

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
            _LOGGER.debug("Invalid credentials.")
            msg = "Wrong credentials"
            raise PorscheWrongCredentialsError(msg)

        resume_url = resp.headers["Location"]
        _LOGGER.debug("Resume at %s:", resume_url)

        _LOGGER.debug("Sleeping 2.5s...")
        await asyncio.sleep(2.5)

        return resume_url

    async def fetch_access_token(self, authorization_code):
        """Exchanges the authorization code for an access token.

        :param authorization_code: authorization code from the /authorize request
        :return: access token
        """
        data = {
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": REDIRECT_URI,
        }
        if self.code_verifier is not None:
            data["code_verifier"] = self.code_verifier

        try:
            _LOGGER.debug("Exchanging the authorization code for an access token.")

            resp = await self.client.post(
                TOKEN_URL,
                data=data,
                timeout=TIMEOUT,
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            _LOGGER.debug("Token exchange failed: %s", exc.response.text)
            raise PorscheExceptionError(exc.response.status_code) from exc

    async def refresh_token(self, refresh_token):
        """Use the provided refresh token to get a new access token.

        :param refresh_token: refresh token
        :return: access token
        """
        data = {
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        try:
            _LOGGER.debug("Using the refresh token to get a new access token.")

            resp = await self.client.post(
                TOKEN_URL,
                data=data,
                timeout=TIMEOUT,
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            # 403 usually means the refresh token is invalid
            # clear the access token so the full login flow can happen again
            if exc.response.status_code == 403:
                return {"access_token": None, "expires_in": 0}
            raise PorscheExceptionError(exc.response.status_code) from exc
