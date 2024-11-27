from typing import Dict, List
import logging
import re
import json  # only for formatting debug output
import uuid
from typing import Optional
from datetime import datetime

from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.remote_services import RemoteServices
from pyporscheconnectapi.exceptions import PorscheException

from .const import MEASUREMENTS, COMMANDS, TRIP_STATISTICS, TIRE_PRESSURE_TOLERANCE

_LOGGER = logging.getLogger(__name__)

BASE_DATA = ["vin", "modelName", "customName", "modelType", "systemInfo", "timestamp"]


class PorscheVehicle:
    """Representation of a Porsche vehicle"""

    def __init__(
        self,
        connection: Connection,
        vin: Optional[str] = None,
        data: Dict = {},
        status: Dict = {},
        capabilities: Dict = {},
        trip_statistics: Dict = {},
        picture_locations: Dict = {},
    ) -> None:
        self.connection = connection
        self.data = data
        self.remote_services = RemoteServices(self)
        self.status = status
        self.capabilities = capabilities
        self.trip_statistics = trip_statistics
        self.picture_locations = picture_locations

    def get_data(self) -> Dict:
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
    def has_remote_services(self) -> bool:
        """Return true if remote services are available."""
        return self.data.get("REMOTE_ACCESS_AUTHORIZATION", {}).get("isEnabled") == True

    @property
    def has_electric_drivetrain(self) -> bool:
        """Return True if vehicle is equipped with a high voltage battery."""
        return (
            self.data["modelType"]["engine"] == "BEV"
            or self.data["modelType"]["engine"] == "PHEV"
        )

    @property
    def main_battery_level(self) -> int:
        """Return the main battery level (TODO: for non-BEV it should use the 12V battery level if available?)"""
        level = 0
        if not self.has_ice_drivetrain:
            level = self.data.get('BATTERY_LEVEL', {}).get('percent', 0)
        return level

    @property
    def has_ice_drivetrain(self) -> bool:
        """Return True if vehicle has an internal combustion engine."""
        return (
            self.data["modelType"]["engine"] == "PHEV"
            or self.data["modelType"]["engine"] == "COMBUSTION"
        )

    @property
    def has_remote_climatisation(self) -> bool:
        """Return True if vehicle has remote climatisation ability."""
        return self.data.__contains__("CLIMATIZER_STATE")

    @property
    def has_direct_charge(self) -> bool:
        """Return True if vehicle has direct charge ability."""
        return self.data.get("BATTERY_CHARGING_STATE", "").__contains__(
            "directChargingState"
        )

    @property
    def direct_charge_on(self) -> bool:
        """Return True if direct charging is enabled."""
        return (
            self.data.get("BATTERY_CHARGING_STATE", {}).get("directChargingState")
            == "ENABLED_ON"
        )

    @property
    def privacy_mode(self) -> bool:
        """Return True if privacy mode is on."""
        return self.data.get("GLOBAL_PRIVACY_MODE", {}).get("isEnabled")

    @property
    def remote_climatise_on(self) -> bool:
        """Return True if remote climatisation is on."""
        return self.data.get("CLIMATIZER_STATE", {}).get("isOn")

    @property
    def vehicle_locked(self) -> bool:
        """Return True if vehicle is locked."""
        return self.data.get("LOCK_STATE_VEHICLE", {}).get("isLocked") == True

    @property
    def vehicle_closed(self) -> bool:
        """Return True if all doors and lids are closed."""
        return not bool(
            sum(
                [
                    self.data[key]["isOpen"]
                    for key in self.data
                    if key.startswith("OPEN_STATE_")
                ]
            )
        )

    @property
    def doors_and_lids(self) -> bool:
        """Return list of all doors and lids and their status."""
        dl = [
            {key: "Open" if self.data[key]["isOpen"] == True else "Closed"}
            for key in self.data
            if key.startswith("OPEN_STATE_")
        ]
        return dict(map(dict.popitem, dl))

    @property
    def tire_pressure_status(self) -> bool:
        """Return true if tire pressure is within the tolerances."""
        tire_pressure_status = self.data.get("TIRE_PRESSURE")
        return (
            not sorted(
                map(
                    abs,
                    [
                        tire_pressure_status[key]["differenceBar"]
                        for key in tire_pressure_status
                        if key.endswith("Tire")
                    ],
                )
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
    def charging_target(self) -> Optional[bool]:
        """Return target state of charge (SoC) for high voltage battery."""

        if self.data.get("CHARGING_PROFILES"):
            charging_profiles = self.data["CHARGING_PROFILES"]["list"]
            active_charging_profile_id = self.data["BATTERY_CHARGING_STATE"].get("activeProfileId", None)

            if active_charging_profile_id is None:
                return None

            active_charging_profile = next(
                (p for p in charging_profiles if p["id"] == active_charging_profile_id),
                None,
            )
            _LOGGER.debug(f"Active charging profile is: {active_charging_profile}")
            if active_charging_profile is not None:
                return active_charging_profile.get("minSoc")
        return None

    @property 
    def location_updated_at(self) -> datetime:
        datetime_str = self.data.get("GPS_LOCATION", {}).get("lastModified")
        datetime_object = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%SZ')
        return datetime_object


    @property
    def location(self) -> tuple[Optional[int], Optional[int], Optional[int]]:
        """Get the location of the vehicle."""

        loc = self.data.get("GPS_LOCATION", {}).get("location")
        heading = self.data.get("GPS_LOCATION", {}).get("direction")
        if loc and re.match(r"[\.0-9]+,[\.0-9]+", loc):
            lat, lon = loc.split(",")
        else:
            lat, lon = None, None

        return (lat, lon, heading)

    async def get_stored_overview(self):
        measurements = "mf=" + "&mf=".join(MEASUREMENTS)

        try:
            _LOGGER.debug(f"Getting stored status for vehicle {self.vin}")
            self.status = await self.connection.get(
                f"/connect/v1/vehicles/{self.vin}?{measurements}"
            )
            self._update_vehicle_data()
        except PorscheException as err:
            _LOGGER.error(
                "Could not get stored overview, error communicating with API: '%s",
                err.message,
            )

    async def get_current_overview(self):
        measurements = "mf=" + "&mf=".join(MEASUREMENTS)
        id = str(uuid.uuid4())
        wakeup = "&wakeUpJob=" + id

        try:
            _LOGGER.debug(f"Getting current status for vehicle {self.vin}")
            self.status = await self.connection.get(
                f"/connect/v1/vehicles/{self.vin}?{measurements+wakeup}"
            )
            self._update_vehicle_data()
        except PorscheException as err:
            _LOGGER.error(
                "Could not get current overview, error communicating with API: '%s",
                err.message,
            )

    async def get_capabilities(self):
        measurements = "mf=" + "&mf=".join(MEASUREMENTS)
        commands = "&cf=" + "&cf=".join(COMMANDS)

        try:
            _LOGGER.debug(f"Getting capabilities for vehicle {self.vin}")
            self.capabilities = await self.connection.get(
                f"/connect/v1/vehicles/{self.vin}?{measurements+commands}"
            )
        except PorscheException as err:
            _LOGGER.error(
                "Could not get capabilities, error communicating with API: '%s",
                err.message,
            )

    async def get_trip_statistics(self):
        measurements = "mf=" + "&mf=".join(TRIP_STATISTICS)

        try:
            _LOGGER.debug(f"Getting trip statistics for vehicle {self.vin}")
            self.trip_statistics = await self.connection.get(
                f"/connect/v1/vehicles/{self.vin}?{measurements}"
            )
        except PorscheException as err:
            _LOGGER.error(
                "Could not get capabilities, error communicating with API: '%s",
                err.message,
            )

    async def get_picture_locations(self):
        try:
            _LOGGER.debug(f"Getting picture urls for vehicle {self.vin}")
            resp = await self.connection.get(
                f"/connect/v1/vehicles/{self.vin}/pictures"
            )
            for p in resp:
                self.picture_locations[p["view"]] = p["url"]
        except PorscheException as err:
            _LOGGER.error(
                "Could not get capabilities, error communicating with API: '%s",
                err.message,
            )

    def __repr__(self):
        return f"Vehicle({self.vin!r}, drivetrain={self.data.get('modelType', {}).get('engine')!r}, has_porsche_connect={self.has_porsche_connect!r})"

    def _update_vehicle_data(self):
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

            bdata = dict((k, self.status[k]) for k in BASE_DATA)

            bdata["name"] = (
                bdata["customName"] if "customName" in bdata else bdata["modelName"]
            )

            _LOGGER.debug(
                "Got base data for vehicle '%s': %s",
                vin,
                json.dumps(bdata, indent=2),
            )

            if "measurements" in self.status:
                tdata = [
                    m for m in self.status["measurements"] if m["status"]["isEnabled"]
                ]

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
                        mdata["BATTERY_CHARGING_STATE"]["chargingRate"] = (
                            mdata["BATTERY_CHARGING_STATE"]["chargingRate"] * 60
                        )
                    else:
                        # Charging is currently not ongoing, but we should still feed some data to the sensor
                        mdata["BATTERY_CHARGING_STATE"]["chargingRate"] = 0

                    if "chargingPower" not in mdata["BATTERY_CHARGING_STATE"]:
                        # Charging is currently not ongoing, but we should still feed some data to the sensor
                        mdata["BATTERY_CHARGING_STATE"]["chargingPower"] = 0

                if "CHARGING_SUMMARY" in mdata:
                    # For some strange reason, the minSoC attribute in this dict does not react on changes, so we create a shadow of it which we update as required and use that for the sensor instead
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
        # return bdata | mdata
