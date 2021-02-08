#  SPDX-License-Identifier: Apache-2.0
"""
Python Package for controlling Porsche Connect API.

"""
import logging

_LOGGER = logging.getLogger(__name__)


class PorscheException(Exception):
    """Class of Porsche API exceptions."""

    def __init__(self, code, *args, **kwargs):
        """Initialize exceptions for the Porsche API."""
        self.message = ""
        super().__init__(*args, **kwargs)
        self.code = code
        if isinstance(code, str):
            self.message = self.code
            return
        if self.code == 401:
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


class WrongCredentials(PorscheException):
    """Class of exceptions for incomplete credentials."""

    pass


