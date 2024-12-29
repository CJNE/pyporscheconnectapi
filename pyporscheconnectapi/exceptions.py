#  SPDX-License-Identifier: Apache-2.0
"""Exceptions used for Porsche Connect API."""

import logging

_LOGGER = logging.getLogger(__name__)


class PorscheExceptionError(Exception):
    """Class of Porsche API exceptions."""

    def __init__(self, code=None, *args, **kwargs) -> None:
        """Initialize exceptions for the Porsche API."""
        self.message = ""
        super().__init__(*args, **kwargs)
        if code is not None:
            self.code = code
            if isinstance(code, str):
                self.message = self.code
                return
            if self.code == 400:
                self.message = "BAD_REQUEST"
            elif self.code == 401:
                self.message = "UNAUTHORIZED"
            elif self.code == 404:
                self.message = "NOT_FOUND"
            elif self.code == 405:
                self.message = "MOBILE_ACCESS_DISABLED"
            elif self.code == 408:
                self.message = "VEHICLE_UNAVAILABLE"
            elif self.code == 423:
                self.message = "ACCOUNT_LOCKED"
            elif self.code == 429:
                self.message = "TOO_MANY_REQUESTS"
            elif self.code == 500:
                self.message = "SERVER_ERROR"
            elif self.code == 503:
                self.message = "SERVICE_MAINTENANCE"
            elif self.code == 504:
                self.message = "UPSTREAM_TIMEOUT"
            elif self.code > 299:
                self.message = f"UNKNOWN_ERROR_{self.code}"


class PorscheWrongCredentialsError(PorscheExceptionError):
    """Class of exceptions for incomplete credentials."""


class PorscheCaptchaRequiredError(PorscheExceptionError):
    """Class of exception when captcha verification is required."""

    captcha: str = None
    state: str = None

    def __init__(self, captcha=None, state=None):
        """Initialize the captcha exception."""
        if captcha is not None and state is not None:
            _LOGGER.info("Initialising captcha exception: %s, %s", captcha, state)
            self.captcha = captcha
            self.state = state

        super().__init__(captcha, state)


class PorscheRemoteServiceError(PorscheExceptionError):
    """Error when executing remote services."""
