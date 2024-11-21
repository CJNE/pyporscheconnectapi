from dataclasses import InitVar, dataclass, field

from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.vehicle import PorscheVehicle

import logging

from typing import List, Optional


_LOGGER = logging.getLogger(__name__)


class PorscheConnectAccount:
    def __init__(
        self,
        username="",
        password="",
        token={},
        connection: Optional[Connection] = None,
    ):
        self.vehicles: List[PorscheVehicle] = []
        self.token = token
        if connection is None:
            self.connection = Connection(username, password, token=token)
        else:
            self.connection = connection

    async def _init_vehicles(self) -> None:
        """Initialize vehicles from API endpoint."""
        _LOGGER.debug("Building vehicle list")

        if self.connection is not None:

            vehicle_list = await self.connection.get("/connect/v1/vehicles")

            for vehicle in vehicle_list:
                _LOGGER.debug(f"Got vehicle {vehicle}")
                v = PorscheVehicle(
                    vin=vehicle["vin"],
                    data=vehicle,
                    status={},
                    connection=self.connection,
                )
                await v.get_stored_overview()
                self.vehicles.append(v)

            self.token = self.connection.token

    async def get_vehicles(self, force_init: bool = False) -> List[PorscheVehicle]:
        """Retrieve vehicle data from API endpoints."""

        _LOGGER.debug("Retrieving vehicle list")

        if len(self.vehicles) == 0 or force_init:
            await self._init_vehicles()

        return self.vehicles

    async def get_vehicle(self, vin: str) -> Optional[PorscheVehicle]:
        if len(self.vehicles) == 0:
            await self._init_vehicles()
        filtered = [v for v in self.vehicles if v.vin == vin]
        if len(filtered) > 0:
            return filtered[0]
        return None
