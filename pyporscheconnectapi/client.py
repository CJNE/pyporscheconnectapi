from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.exceptions import WrongCredentials
from hashlib import sha512

import asyncio
import datetime
import logging
import uuid

from .const import MEASUREMENTS, COMMANDS

_LOGGER = logging.getLogger(__name__)


class Client:
    """Client for Porsche Connect API."""

    def __init__(
        self,
        connection: Connection,
    ) -> None:
        self._connection = connection

    async def getToken(self):
        return await self._connection.getToken()

    async def getVehicles(self):
        vehicles = await self._connection.get(
            f"https://api.ppa.porsche.com/app/connect/v1/vehicles"
        )
        return vehicles

    async def getCapabilities(self, vin):
        measurements = "mf=" + "&mf=".join(MEASUREMENTS)
        commands = "&cf=" + "&cf=".join(COMMANDS)

        data = await self._connection.get(
            f"https://api.ppa.porsche.com/app/connect/v1/vehicles/{vin}?{measurements+commands}"
        )
        return data

    async def getStoredOverview(self, vin):
        measurements = "mf=" + "&mf=".join(MEASUREMENTS)

        data = await self._connection.get(
            f"https://api.ppa.porsche.com/app/connect/v1/vehicles/{vin}?{measurements}"
        )
        return data

    async def getCurrentOverview(self, vin):
        measurements = "mf=" + "&mf=".join(MEASUREMENTS)
        id = str(uuid.uuid4())
        wakeup = "&wakeUpJob=" + id

        data = await self._connection.get(
            f"https://api.ppa.porsche.com/app/connect/v1/vehicles/{vin}?{measurements+wakeup}"
        )
        return data

    async def updateChargingProfile(
        self,
        vin,
        profileId: int,
        minimumChargeLevel: int = None,
    ):
        measurements = (await self.getStoredOverview(vin))["measurements"]
        chargingprofiles = (
            [e for e in measurements if e["key"] == "CHARGING_PROFILES"]
        )[0]["value"]
        chargingprofileslist = chargingprofiles["list"]

        if profileId is None:
            profileId = chargingprofiles["activeProfileId"]

        if minimumChargeLevel is not None:
            minimumChargeLevel = min(max(int(minimumChargeLevel), 25), 100)
            chargingprofileslist
            for i, item in enumerate(chargingprofileslist):
                if profileId == item["id"]:
                    item["minSoc"] = minimumChargeLevel
                    chargingprofileslist[i] = item

        return await self._updateChargingProfile(vin, chargingprofileslist)

    async def _updateChargingProfile(
        self,
        vin,
        chargingprofileslist,
    ):

        profile = {
            "key": "CHARGING_PROFILES_EDIT",
            "payload": {"list": chargingprofileslist},
        }
        print(profile)

        result = await self._connection.post(
            f"https://api.ppa.porsche.com/app/connect/v1/vehicles/{vin}/commands",
            json=profile,
        )

        print(result)
        return result
