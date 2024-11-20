from typing import Optional


import logging
import datetime
import asyncio

from enum import Enum

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
        raise ValueError(f"'{value}' is not a valid {cls.__name__}")


class ExecutionState(StrEnum):
    """Enumeration of possible states of the execution of a remote service."""

    PERFORMED = "PERFORMED"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class Services:
    """Enumeration of possible services to be executed."""

    LIGHT_FLASH = "light-flash"
    VEHICLE_FINDER = "vehicle-finder"
    DOOR_LOCK = "door-lock"
    DOOR_UNLOCK = "door-unlock"
    HORN = "horn-blow"
    AIR_CONDITIONING = "climate-now"
    CHARGE_START = "start-charging"
    CHARGE_STOP = "stop-charging"
    CHARGING_SETTINGS = "CHARGING_SETTINGS"
    CHARGING_PROFILE = "CHARGING_PROFILE"


class RemoteServiceStatus:
    """Wraps the status of the execution of a remote service."""

    def __init__(self, response: dict, status_id: Optional[str] = None):
        """Construct a new object from a dict."""
        status = None
        if "status" in response:
            status = response.get("status", {}).get("result")

        self.state = ExecutionState(status or "UNKNOWN")
        self.details = response
        self.status_id = status_id


class RemoteServices:
    """Trigger remote services on a vehicle."""

    def __init__(self, vehicle: "PorscheVehicle"):
        self._vehicle = vehicle
        self._connection = vehicle.connection

    async def flash_indicators(
        self,
    ):
        _LOGGER.debug(f"Requesting vehicle {self._vehicle.vin} to flash indicators.")

        payload = {
            "key": "HONK_FLASH",
            "payload": {
                "mode": "FLASH",
                "spin": None,
            },
        }

        result = await self._send_command(payload)
        return result

    async def honk_and_flash_indicators(
        self,
    ):
        _LOGGER.debug(
            f"Requesting vehicle {self._vehicle.vin} to honk and flash indicators."
        )

        payload = {
            "key": "HONK_FLASH",
            "payload": {
                "mode": "HONK_AND_FLASH",
                "spin": None,
            },
        }

        result = await self._send_command(payload)
        return result

    async def climatise_on(
        self,
        targetTemperature: float = 293.15,
        frontLeft: bool = False,
        frontRight: bool = False,
        rearLeft: bool = False,
        rearRight: bool = False,
    ):
        _LOGGER.debug(f"Starting remote climatisation for {self._vehicle.vin}")

        payload = {
            "key": "REMOTE_CLIMATIZER_START",
            "payload": {
                "climateZonesEnabled": {
                    "frontLeft": frontLeft,
                    "frontRight": frontRight,
                    "rearLeft": rearLeft,
                    "rearRight": rearRight,
                },
                "targetTemperature": targetTemperature,
            },
        }

        result = await self._send_command(payload)
        return result

    async def climatise_off(
        self,
    ):
        _LOGGER.debug(f"Stopping remote climatisation for {self._vehicle.vin}")

        payload = {"key": "REMOTE_CLIMATIZER_STOP", "payload": {}}

        result = await self._send_command(payload)
        return result

    async def direct_charge_on(
        self,
    ):
        _LOGGER.debug(f"Enabling direct charging for {self._vehicle.vin}")

        payload = {"key": "DIRECT_CHARGING_START", "payload": {"spin": None}}

        result = await self._send_command(payload)
        return result

    async def direct_charge_off(
        self,
    ):
        _LOGGER.debug(f"Disabling direct charging for {self._vehicle.vin}")

        payload = {"key": "DIRECT_CHARGING_STOP", "payload": {"spin": None}}

        result = await self._send_command(payload)
        return result

    async def updateChargingProfile(
        self,
        profileId: int = None,
        minimumChargeLevel: int = None,
    ):
        chargingprofileslist = self._vehicle.data["CHARGING_PROFILES"]["list"]
        _LOGGER.debug(f"Charging profile list: {chargingprofileslist}")

        if profileId is None:
            profileId = self._vehicle.data["BATTERY_CHARGING_STATE"]["activeProfileId"]

        _LOGGER.debug(f"Active profile id: {profileId}")

        if minimumChargeLevel is not None:
            minimumChargeLevel = min(max(int(minimumChargeLevel), 25), 100)
            for i, item in enumerate(chargingprofileslist):
                if profileId == item["id"]:
                    item["minSoc"] = minimumChargeLevel
                    chargingprofileslist[i] = item

        return await self._updateChargingProfile(chargingprofileslist)

    async def _updateChargingProfile(
        self,
        chargingprofileslist,
    ):
        payload = {
            "key": "CHARGING_PROFILES_EDIT",
            "payload": {"list": chargingprofileslist},
        }
        _LOGGER.debug(f"Updating charging profile for {self._vehicle.vin}")

        result = await self._send_command(payload)
        return result

    async def _send_command(
        self,
        payload,
    ):
        _LOGGER.debug(f"Executing remote command with payload {payload}")

        response = await self._connection.post(
            f"/connect/v1/vehicles/{self._vehicle.vin}/commands",
            json=payload,
        )

        if response:
            status_id = response.get("status", {}).get("id")
            result_code = response.get("status", {}).get("result")
        else:
            raise RemoteServiceError(
                f"Did not receive response for remote service request"
            )

        _LOGGER.debug("Got result: %s (%s)", result_code, status_id)

        status = (
            await self._block_until_done(status_id)
            if status_id and result_code == "ACCEPTED"
            else RemoteServiceStatus(result_code)
        )

        if True:
            await asyncio.sleep(_POLLING_DELAY)
            await self._vehicle._update_data_for_vehicle()

        return status

    async def _block_until_done(self, status_id: str) -> RemoteServiceStatus:
        """Keep polling the server until we get a final answer.

        :raises TimeoutError: if there is no final answer before _POLLING_TIMEOUT
        """

        fail_after = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            seconds=_POLLING_TIMEOUT
        )
        while datetime.datetime.now(datetime.timezone.utc) < fail_after:
            await asyncio.sleep(_POLLING_DELAY)
            status = await self._get_remote_service_status(status_id)
            _LOGGER.debug("Current state of '%s' is: %s", status_id, status.state.value)
            if status.state == ExecutionState.ERROR:
                raise PorscheRemoteServiceError(
                    f"Remote service failed with state '{status.status.result}'"
                )
            if status.state not in [
                ExecutionState.UNKNOWN,
            ]:
                return status
        raise PorscheRemoteServiceError(
            f"Did not receive remote service result for '{event_id}' in {_POLLING_TIMEOUT} seconds. "
            f"Current state: {status.state.value}"
        )

    async def _get_remote_service_status(self, status_id: str) -> RemoteServiceStatus:
        """Return execution status of the last remote service that was triggered."""

        _LOGGER.debug("Getting remote service status for '%s'", status_id)
        status_msg = await self._connection.get(
            f"/connect/v1/vehicles/{self._vehicle.vin}/commands/{status_id}"
        )
        _LOGGER.debug("Got status message %s for '%s'", status_msg, status_id)
        return RemoteServiceStatus(status_msg, status_id=status_id)
