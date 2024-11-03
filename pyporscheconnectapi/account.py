
from dataclasses import InitVar, dataclass, field

from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.client import Client
from pyporscheconnectapi.vehicle import PorscheVehicle

import logging

from typing import List, Dict


_LOGGER = logging.getLogger(__name__)


@dataclass
class PorscheConnectAccount:
    username: str
    password: InitVar[str]
    token: Dict = None
    connection: Connection = None
    vehicles: List[PorscheVehicle] = field(default_factory=list, init=False)

    def __post_init__(self, password):
        """Initialize the account."""
        
        if self.token is None:
            self.token = {}
        
        if self.connection is None:
            self.connection = Connection(self.username, password, token=self.token)


    async def _init_vehicles(self) -> None:
        """Initialize vehicles from API endpoint."""
        _LOGGER.debug("Building vehicle list")
        client = Client(self.connection)

        vehicle_list = await client.getVehicles()
        
        for vehicle in vehicle_list:
            _LOGGER.debug(f"Got vehicle {vehicle}")
            status = await client.getStoredOverview(vin=vehicle["vin"])
            _LOGGER.debug(f"Setting vehicle status {status}")
            self.vehicles.append(PorscheVehicle(vin=vehicle["vin"], data=vehicle, status=status, connection=self.connection))
            
        self.token = self.connection.token                


    async def get_vehicles(self, force_init: bool = False) -> None:
        """Retrieve vehicle data from API endpoints."""

        _LOGGER.debug("Retrieving vehicle list")

        if len(self.vehicles) == 0 or force_init:
            await self._init_vehicles()

        return self.vehicles

