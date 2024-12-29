"""Trigger remote services on a vehicle."""

from __future__ import annotations

import asyncio
import datetime
import logging
from enum import Enum
from hashlib import sha512
from typing import TYPE_CHECKING

from .exceptions import PorscheRemoteServiceError

if TYPE_CHECKING:
    from .vehicle import PorscheVehicle
_LOGGER = logging.getLogger(__name__)

#: time in seconds between receiving status and polling for update
_POLLING_DELAY = 1

#: maximum number of seconds to wait for the server to return a positive answer
_POLLING_TIMEOUT = 240


class StrEnum(str, Enum):
    """A string enumeration of type `(str, Enum)`. All members are compared via `upper()`. Defaults to UNKNOWN."""

    @classmethod
    def _missing_(cls, value):
        has_unknown = False
        for member in cls:
            if member.value.upper() == "UNKNOWN":
                has_unknown = True
            if member.value.upper() == value.upper():
                return member
        if has_unknown:
            _LOGGER.warning("'%s' is not a valid '%s'", value, cls.__name__)
            return cls.UNKNOWN
        msg = f"'{value}' is not a valid {cls.__name__}"
        raise ValueError(msg)


class ExecutionState(StrEnum):
    """Enumeration of possible states of the execution of a remote service."""

    PERFORMED = "PERFORMED"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class RemoteServiceStatus:
    """Wraps the status of the execution of a remote service."""

    def __init__(self, response: dict, status_id: str | None = None) -> None:
        """Construct a new object from a dict."""
        status = None
        if "status" in response:
            status = response.get("status", {}).get("result")

        self.status = status
        self.state = ExecutionState(status or "UNKNOWN")
        self.details = response
        self.status_id = status_id


class RemoteServices:
    """Trigger remote services on a vehicle."""

    def __init__(self, vehicle: PorscheVehicle):
        """Initialise the Remote Services on a Porsche Connect vehicle."""
        self._vehicle = vehicle
        self._connection = vehicle.connection

    async def flash_indicators(
        self,
    ):
        """Remote service for flashing the indicators briefly."""
        _LOGGER.debug("Requesting vehicle %s to flash indicators.", self._vehicle.vin)

        payload = {
            "key": "HONK_FLASH",
            "payload": {
                "mode": "FLASH",
                "spin": None,
            },
        }

        return await self._send_command(payload)

    async def honk_and_flash_indicators(
        self,
    ):
        """Remote service for honking and flashing the indicators briefly."""
        _LOGGER.debug(
            "Requesting vehicle %s to honk and flash indicators.",
            self._vehicle.vin,
        )

        payload = {
            "key": "HONK_FLASH",
            "payload": {
                "mode": "HONK_AND_FLASH",
                "spin": None,
            },
        }

        return await self._send_command(payload)

    async def climatise_on(
        self,
        *,
        target_temperature: float = 293.15,
        front_left: bool = False,
        front_right: bool = False,
        rear_left: bool = False,
        rear_right: bool = False,
    ):
        """Remote service for turning climatisation on."""
        _LOGGER.debug("Starting remote climatisation for %s", self._vehicle.vin)

        payload = {
            "key": "REMOTE_CLIMATIZER_START",
            "payload": {
                "climateZonesEnabled": {
                    "frontLeft": front_left,
                    "frontRight": front_right,
                    "rearLeft": rear_left,
                    "rearRight": rear_right,
                },
                "targetTemperature": target_temperature,
            },
        }

        return await self._send_command(payload)

    async def climatise_off(
        self,
    ):
        """Remote service for turning climatisation off."""
        _LOGGER.debug("Stopping remote climatisation for %s", self._vehicle.vin)

        payload = {"key": "REMOTE_CLIMATIZER_STOP", "payload": {}}

        return await self._send_command(payload)

    async def direct_charge_on(
        self,
    ):
        """Remote service for turning direct charging on."""
        _LOGGER.debug("Enabling direct charging for %s", self._vehicle.vin)

        payload = {"key": "DIRECT_CHARGING_START", "payload": {"spin": None}}

        return await self._send_command(payload)

    async def direct_charge_off(
        self,
    ):
        """Remote service for turning direct charging off."""
        _LOGGER.debug("Disabling direct charging for %s", self._vehicle.vin)
        payload = {"key": "DIRECT_CHARGING_STOP", "payload": {"spin": None}}
        return await self._send_command(payload)

    async def lock_vehicle(
        self,
    ):
        """Remote service for locking a vehicle."""
        _LOGGER.debug("Locking vehicle %s", self._vehicle.vin)
        payload = {"key": "LOCK", "payload": {"spin": None}}
        return await self._send_command(payload)

    async def unlock_vehicle(
        self,
        pin,
    ):
        """Remote service for unlocking a vehicle."""
        _LOGGER.debug("Unlocking vehicle %s", self._vehicle.vin)

        challenge = await self._get_challenge()

        if challenge:
            pinhash = sha512(bytes.fromhex(pin + challenge)).hexdigest().upper()

            payload = {
                "key": "UNLOCK",
                "payload": {"spin": {"challenge": challenge, "hash": pinhash}},
            }

            return await self._send_command(payload)
        return None

    async def update_charging_profile(
        self,
        profile_id: int | None = None,
        minimum_charge_level: int | None = None,
    ):
        """Remote service for altering a charging profile."""
        chargingprofileslist = self._vehicle.data["CHARGING_PROFILES"]["list"]
        _LOGGER.debug("Charging profile list: %s", chargingprofileslist)

        if profile_id is None:
            profile_id = self._vehicle.data["BATTERY_CHARGING_STATE"]["activeProfileId"]

        _LOGGER.debug("Active profile id: %s", profile_id)

        if minimum_charge_level is not None:
            minimum_charge_level = min(max(int(minimum_charge_level), 25), 100)
            for i, item in enumerate(chargingprofileslist):
                if profile_id == item["id"]:
                    item["minSoc"] = minimum_charge_level
                    chargingprofileslist[i] = item

        return await self._update_charging_profile(chargingprofileslist)

    async def _get_challenge(
        self,
    ):
        payload = {"key": "SPIN_CHALLENGE", "payload": {"spin": None}}

        _LOGGER.debug("Requesting challenge for %s", self._vehicle.vin)

        response = await self._connection.post(
            f"/connect/v1/vehicles/{self._vehicle.vin}/commands",
            json=payload,
        )

        return response.get("data", {}).get("challenge")

    async def _update_charging_profile(
        self,
        chargingprofileslist,
    ):
        payload = {
            "key": "CHARGING_PROFILES_EDIT",
            "payload": {"list": chargingprofileslist},
        }
        _LOGGER.debug("Updating charging profile for %s.", self._vehicle.vin)

        return await self._send_command(payload)

    async def _send_command(
        self,
        payload,
    ):
        _LOGGER.debug("Executing remote command with payload %s", payload)

        response = await self._connection.post(
            f"/connect/v1/vehicles/{self._vehicle.vin}/commands",
            json=payload,
        )

        if response:
            status_id = response.get("status", {}).get("id")
            result_code = response.get("status", {}).get("result")
        else:
            msg = "Did not receive response for remote service request"
            raise PorscheRemoteServiceError(
                msg,
            )

        _LOGGER.debug("Got result: %s (%s)", result_code, status_id)

        status = await self._block_until_done(status_id) if status_id and result_code == "ACCEPTED" else RemoteServiceStatus(result_code)

        await asyncio.sleep(_POLLING_DELAY)
        await self._vehicle.get_stored_overview()

        return status

    async def _block_until_done(self, status_id: str) -> RemoteServiceStatus:
        """Keep polling the server until we get a final answer.

        :raises TimeoutError: if there is no final answer before _POLLING_TIMEOUT
        """
        fail_after = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
            seconds=_POLLING_TIMEOUT,
        )
        status = None
        while datetime.datetime.now(datetime.UTC) < fail_after:
            await asyncio.sleep(_POLLING_DELAY)
            status = await self._get_remote_service_status(status_id)
            _LOGGER.debug("Current state of '%s' is: %s", status_id, status.state.value)
            if status.state == ExecutionState.ERROR:
                msg = f"Remote service failed with state '{status.details}'"
                raise PorscheRemoteServiceError(
                    msg,
                )
            if status.state not in [
                ExecutionState.UNKNOWN,
            ]:
                return status
        current_state = "Unknown"
        if status is not None:
            current_state = status.state.value
        msg = f"Did not receive remote service result for '{status_id}' in {_POLLING_TIMEOUT} seconds. Current state: {current_state}"
        raise PorscheRemoteServiceError(
            msg,
        )

    async def _get_remote_service_status(self, status_id: str) -> RemoteServiceStatus:
        """Return execution status of the last remote service that was triggered."""
        _LOGGER.debug("Getting remote service status for '%s'", status_id)
        status_msg = await self._connection.get(
            f"/connect/v1/vehicles/{self._vehicle.vin}/commands/{status_id}",
        )
        _LOGGER.debug("Got status message %s for '%s'", status_msg, status_id)
        return RemoteServiceStatus(status_msg, status_id=status_id)
