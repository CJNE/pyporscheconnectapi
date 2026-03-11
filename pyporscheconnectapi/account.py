"""Accesses Porsche Connect account and retrieves connected vehicles."""

from __future__ import annotations

import logging

from .connection import Connection
from .vehicle import PorscheVehicle

_LOGGER = logging.getLogger(__name__)


def _normalize_engine(vehicle: dict) -> str:
    """Best-effort mapping of the portal vehicle payload to drivetrain type."""
    model_type = vehicle.get("modelType", {})
    if model_type.get("engine"):
        return model_type["engine"]
    description = str(vehicle.get("modelDescription", "")).lower()
    if description in {"macan", "taycan"}:
        return "BEV"
    return "COMBUSTION"


def _normalize_vehicle(vehicle: dict) -> dict:
    """Normalize the portal vehicle payload to the legacy library shape."""
    model_name = vehicle.get("modelDescription") or vehicle.get("modelName") or vehicle.get("vin", "Porsche")
    return {
        "vin": vehicle["vin"],
        "name": model_name,
        "modelName": model_name,
        "modelType": {
            "year": vehicle.get("modelYear") or vehicle.get("modelType", {}).get("year", "not available"),
            "engine": _normalize_engine(vehicle),
        },
        "systemInfo": vehicle.get("systemInfo", {}),
        "timestamp": vehicle.get("validFrom") or vehicle.get("timestamp"),
        "portalVehicle": vehicle,
    }


class PorscheConnectAccount:
    """Establishes a connection to a Porsche Connect account."""

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        token: dict | None = None,
        connection: Connection | None = None,
    ) -> None:
        """Initialize the account."""
        self.vehicles: list[PorscheVehicle] = []
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
                _LOGGER.debug("Got vehicle %s", vehicle)
                v = PorscheVehicle(
                    vin=vehicle["vin"],
                    data=_normalize_vehicle(vehicle),
                    status={},
                    connection=self.connection,
                )
                self.vehicles.append(v)

            self.token = self.connection.token

    async def get_vehicles(self, *, force_init: bool = False) -> list[PorscheVehicle]:
        """Retrieve available vehicles from API endpoints."""
        _LOGGER.debug("Retrieving vehicle list")

        if len(self.vehicles) == 0 or force_init:
            await self._init_vehicles()

        return self.vehicles

    async def get_vehicle(self, vin: str) -> PorscheVehicle | None:
        """Retrieve vehicle data from API endpoints."""
        if len(self.vehicles) == 0:
            await self._init_vehicles()
        filtered = [v for v in self.vehicles if v.vin == vin]
        if len(filtered) > 0:
            return filtered[0]
        return None
