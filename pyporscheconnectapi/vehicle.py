"""Models the state of a Porsche Connect vehicle."""

from __future__ import annotations

import datetime
import json  # only for formatting debug output
import logging
import re
import uuid

from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.exceptions import PorscheExceptionError
from pyporscheconnectapi.remote_services import RemoteServices

from .const import COMMANDS, MEASUREMENTS, TIRE_PRESSURE_TOLERANCE, TRIP_STATISTICS

_LOGGER = logging.getLogger(__name__)

BASE_DATA = ["vin", "modelName", "customName", "modelType", "systemInfo", "timestamp"]


class PorscheVehicle:
    """Representation of a Porsche Connect vehicle."""

    def __init__(
        self,
        connection: Connection,
        vin: str | None = None,
        data: dict | None = None,
        status: dict | None = None,
        capabilities: dict | None = None,
        trip_statistics: dict | None = None,
        picture_locations: dict | None = None,
    ) -> None:
        """Initialise the Porsche Vehicle."""
        if picture_locations is None:
            picture_locations = {}
        if trip_statistics is None:
            trip_statistics = {}
        if capabilities is None:
            capabilities = {}
        if status is None:
            status = {}
        if data is None:
            data = {}
        if vin is None:
            vin = ""
        self.connection = connection
        self.data = data
        self.remote_services = RemoteServices(self)
        self.status = status
        self.capabilities = capabilities
        self.trip_statistics = trip_statistics
        self.picture_locations = picture_locations

    def get_data(self) -> dict:
        """Get all vechicle data."""
        return self.data

    @property
    def vin(self) -> str:
        """Get the VIN (vehicle identification number) of the vehicle."""
        return self.data.get("vin", "not available")

    @property
    def model_name(self) -> str:
        """Get the model name of the vehicle."""
        return self.data.get("modelName", "not available")

    @property
    def model_year(self) -> str:
        """Get the model year of the vehicle."""
        return self.data.get("modelType", {}).get("year", "not available")

    @property
    def has_porsche_connect(self) -> bool:
        """Should return true if porsche connect subscription is active. Todo."""
        return True

    @property
    def connected(self) -> bool:
        """Returns true if the vechicle is on-line."""
        return self.data.get("connect", "not available")

    @property
    def has_remote_services(self) -> bool:
        """Return true if remote services are available."""
        return self.data.get("REMOTE_ACCESS_AUTHORIZATION", {}).get("isEnabled") is True

    @property
    def has_electric_drivetrain(self) -> bool:
        """Return True if vehicle is equipped with a high voltage battery."""
        return self.data["modelType"]["engine"] == "BEV" or self.data["modelType"]["engine"] == "PHEV"

    @property
    def main_battery_level(self) -> int:
        """Return the main battery level (TODO: for non-BEV it should use the 12V battery level if available?)."""
        level = 0
        if not self.has_ice_drivetrain:
            level = self.data.get("BATTERY_LEVEL", {}).get("percent", 0)
        return level

    @property
    def has_ice_drivetrain(self) -> bool:
        """Return True if vehicle has an internal combustion engine."""
        return self.data["modelType"]["engine"] == "PHEV" or self.data["modelType"]["engine"] == "COMBUSTION"

    @property
    def has_remote_climatisation(self) -> bool:
        """Return True if vehicle has remote climatisation ability."""
        return self.data.__contains__("CLIMATIZER_STATE")

    @property
    def has_direct_charge(self) -> bool:
        """Return True if vehicle has direct charge ability."""
        return self.data.get("BATTERY_CHARGING_STATE", "").__contains__(
            "directChargingState",
        )

    @property
    def direct_charge_on(self) -> bool:
        """Return True if direct charging is enabled."""
        return self.data.get("BATTERY_CHARGING_STATE", {}).get("directChargingState") == "ENABLED_ON"

    @property
    def privacy_mode(self) -> bool:
        """Return True if privacy mode is on."""
        return self.data.get("GLOBAL_PRIVACY_MODE", {}).get("isEnabled")

    @property
    def remote_climatise_on(self) -> bool:
        """Return True if remote climatisation is on."""
        _LOGGER.debug("Remote climatisation is: %s", self.data.get("CLIMATIZER_STATE", {}).get("isOn"))

        return self.data.get("CLIMATIZER_STATE", {}).get("isOn")

    @property
    def vehicle_locked(self) -> bool:
        """Return True if vehicle is locked."""
        return self.data.get("LOCK_STATE_VEHICLE", {}).get("isLocked") is True

    @property
    def vehicle_closed(self) -> bool:
        """Return True if all doors and lids are closed."""
        return not bool(
            sum(
                [self.data[key]["isOpen"] for key in self.data if key.startswith("OPEN_STATE_")],
            ),
        )

    @property
    def doors_and_lids(self) -> bool:
        """Return list of all doors and lids and their status."""
        dl = [{key: "Open" if self.data[key]["isOpen"] is True else "Closed"} for key in self.data if key.startswith("OPEN_STATE_")]
        return dict(map(dict.popitem, dl))

    @property
    def tire_pressure_status(self) -> bool:
        """Return true if tire pressure is within the tolerances."""
        tire_pressure_status = self.data.get("TIRE_PRESSURE")
        return (
            not sorted(
                map(
                    abs,
                    [tire_pressure_status[key]["differenceBar"] for key in tire_pressure_status if key.endswith("Tire")],
                ),
            )[-1]
            > TIRE_PRESSURE_TOLERANCE
        )

    @property
    def tire_pressures(self) -> bool:
        """Return a dict containing tire pressure readings."""
        return self.data.get("TIRE_PRESSURE")

    @property
    def has_tire_pressure_monitoring(self) -> bool:
        """Return True if vehicle has tire pressure monitoring."""
        return self.data.get("TIRE_PRESSURE") is not None

    @property
    def charging_target(self) -> bool | None:
        """Return target state of charge (SoC) for high voltage battery."""
        if self.data.get("CHARGING_PROFILES"):
            charging_profiles = self.data["CHARGING_PROFILES"]["list"]
            active_charging_profile_id = self.data["BATTERY_CHARGING_STATE"].get(
                "activeProfileId",
                None,
            )

            if active_charging_profile_id is None:
                return None

            active_charging_profile = next(
                (p for p in charging_profiles if p["id"] == active_charging_profile_id),
                None,
            )
            _LOGGER.debug("Active charging profile is: %s", active_charging_profile)
            if active_charging_profile is not None:
                return active_charging_profile.get("minSoc")
        return None

    @property
    def location_updated_at(self) -> datetime:
        """Return time stamp of latest location update."""
        datetime_str = self.data.get("GPS_LOCATION", {}).get("lastModified")
        if datetime_str:
            return datetime.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ").astimezone(datetime.timezone.utc)
        return None

    @property
    def location(self) -> tuple[float | None, float | None, int | None]:
        """Get the location of the vehicle."""
        loc = self.data.get("GPS_LOCATION", {}).get("location")
        heading = self.data.get("GPS_LOCATION", {}).get("direction")
        if loc and re.match(r"[\-\.0-9]+,[\-\.0-9]+", loc):
            lat, lon = map(float, loc.split(","))
        else:
            lat, lon = None, None

        return (lat, lon, heading)

    async def get_stored_overview(self) -> None:
        """Return stored vechicle status overview."""
        measurements = "mf=" + "&mf=".join(MEASUREMENTS)

        try:
            _LOGGER.debug("Getting stored status for vehicle %s", self.vin)
            self.status = await self.connection.get(
                f"/connect/v1/vehicles/{self.vin}?{measurements}",
            )
            self._update_vehicle_data()
        except PorscheExceptionError as err:
            _LOGGER.exception(
                "Could not get stored overview, error communicating with API: '%s",
                err.message,
            )

    async def get_current_overview(self) -> None:
        """Return vehicle current status overview."""
        measurements = "mf=" + "&mf=".join(MEASUREMENTS)
        wakeup = "&wakeUpJob=" + str(uuid.uuid4())

        try:
            _LOGGER.debug("Getting current status for vehicle %s", self.vin)
            self.status = await self.connection.get(
                f"/connect/v1/vehicles/{self.vin}?{measurements+wakeup}",
            )
            self._update_vehicle_data()
        except PorscheExceptionError as err:
            _LOGGER.exception(
                "Could not get current overview, error communicating with API: '%s",
                err.message,
            )

    async def get_capabilities(self) -> None:
        """Return vehicle capabilities."""
        measurements = "mf=" + "&mf=".join(MEASUREMENTS)
        commands = "&cf=" + "&cf=".join(COMMANDS)

        try:
            _LOGGER.debug("Getting capabilities for vehicle %s", self.vin)
            self.capabilities = await self.connection.get(
                f"/connect/v1/vehicles/{self.vin}?{measurements+commands}",
            )
        except PorscheExceptionError as err:
            _LOGGER.exception(
                "Could not get capabilities, error communicating with API: %s",
                err.message,
            )

    async def get_trip_statistics(self) -> None:
        """Return trip statistics for vehicle as a dict."""
        measurements = "mf=" + "&mf=".join(TRIP_STATISTICS)

        try:
            _LOGGER.debug("Getting trip statistics for vehicle %s", self.vin)
            self.trip_statistics = await self.connection.get(
                f"/connect/v1/vehicles/{self.vin}?{measurements}",
            )
        except PorscheExceptionError as err:
            _LOGGER.exception(
                "Could not get capabilities, error communicating with API: %s",
                err.message,
            )

    async def get_picture_locations(self) -> None:
        """Return list of uri's to vechicle pictures."""
        try:
            _LOGGER.debug("Getting picture urls for vehicle %s", self.vin)
            resp = await self.connection.get(
                f"/connect/v1/vehicles/{self.vin}/pictures",
            )
            for p in resp:
                self.picture_locations[p["view"]] = p["url"]
        except PorscheExceptionError as err:
            _LOGGER.exception(
                "Could not get capabilities, error communicating with API: %s",
                err.message,
            )

    def __repr__(self) -> str:
        """Return a printable representation of the Porsche Connect Vehicle object."""
        return f"Vehicle({self.vin!r}, drivetrain={self.data.get('modelType', {}).get('engine')!r}, has_porsche_connect={self.has_porsche_connect!r})"

    def _update_vehicle_data(self) -> None:
        vin = self.vin
        bdata = {}
        mdata = {}

        if "vin" in self.status:
            _LOGGER.debug(
                "Vehicle status dict for %s is now: %s",
                vin,
                json.dumps(self.status, indent=2),
            )

            if "customName" not in self.status:
                self.status["customName"] = ""

            bdata = {k: self.status[k] for k in BASE_DATA}

            bdata["name"] = bdata["customName"] if "customName" in bdata else bdata["modelName"]

            _LOGGER.debug(
                "Got base data for vehicle '%s': %s",
                vin,
                json.dumps(bdata, indent=2),
            )

            if "measurements" in self.status:
                tdata = [m for m in self.status["measurements"] if m["status"]["isEnabled"]]

                for m in tdata:
                    mdata[m["key"]] = m["value"]
                _LOGGER.debug(
                    "Got measurement data for vehicle '%s': %s",
                    vin,
                    json.dumps(mdata, indent=2),
                )

                # Here we do some measurements translations to make them accessible

                if "BATTERY_CHARGING_STATE" in mdata:
                    if "chargingRate" in mdata["BATTERY_CHARGING_STATE"]:
                        # Convert charging rate from km/min to km/h
                        mdata["BATTERY_CHARGING_STATE"]["chargingRate"] = mdata["BATTERY_CHARGING_STATE"]["chargingRate"] * 60
                    else:
                        # Charging is currently not ongoing, but we should still feed some data to the sensor
                        mdata["BATTERY_CHARGING_STATE"]["chargingRate"] = 0

                    if "chargingPower" not in mdata["BATTERY_CHARGING_STATE"]:
                        # Charging is currently not ongoing, but we should still feed some data to the sensor
                        mdata["BATTERY_CHARGING_STATE"]["chargingPower"] = 0

                if "CHARGING_SUMMARY" in mdata:
                    # For some strange reason, the minSoC attribute in this dict does not react on changes,
                    # so we create a shadow of it which we update as required and use that for the sensor instead
                    if mdata["CHARGING_SUMMARY"].get("mode") == "DIRECT":
                        minsoc = 100
                    elif mdata["CHARGING_SUMMARY"].get("chargingProfile"):
                        minsoc = self.charging_target
                    else:
                        _LOGGER.debug("Unable to find minSoC for vehicle '%s", vin)
                        # What should it fall back to?
                        minsoc = 80

                    mdata["CHARGING_SUMMARY"]["minSoC"] = minsoc

            else:
                _LOGGER.debug("Measurement data missing for vehicle '%s", vin)
                _LOGGER.debug(
                    "Payload for current overview query was: %s",
                    json.dumps(self.status, indent=2),
                )

        else:
            _LOGGER.debug("Base data missing for vehicle '%s", vin)
            _LOGGER.debug(
                "Payload for current overview query was: %s",
                json.dumps(self.status, indent=2),
            )

        self.data = self.data | bdata | mdata
