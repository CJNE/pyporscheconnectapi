
from typing import Optional


import logging
_LOGGER = logging.getLogger(__name__)


class ExecutionState():
    """Enumeration of possible states of the execution of a remote service."""

    INITIATED = "INITIATED"
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    EXECUTED = "EXECUTED"
    ERROR = "ERROR"
    IGNORED = "IGNORED"
    UNKNOWN = "UNKNOWN"


class Services():
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

    def __init__(self, response: dict, event_id: Optional[str] = None):
        """Construct a new object from a dict."""
        status = None
        if "eventStatus" in response:
            status = response.get("eventStatus")

        self.state = ExecutionState(status or "UNKNOWN")
        self.details = response
        self.event_id = event_id



class RemoteServices:
    """Trigger remote services on a vehicle."""

    def __init__(self, vehicle: "PorscheVehicle"):
        self._vehicle = vehicle
        self._connection = vehicle.connection

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

        profile = {
            "key": "CHARGING_PROFILES_EDIT",
            "payload": {"list": chargingprofileslist},
        }
        _LOGGER.debug(f"Updating charging profile for {self._vehicle.vin}")

        result = await self._connection.post(
            f"/connect/v1/vehicles/{self._vehicle.vin}/commands",
            json=profile,
        )

        _LOGGER.debug(result)

        return result
