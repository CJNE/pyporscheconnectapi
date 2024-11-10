from typing import Dict
import logging
import json  # only for formatting debug output

from pyporscheconnectapi.remote_services import RemoteServices

_LOGGER = logging.getLogger(__name__)

BASE_DATA = ["vin", "modelName", "customName", "modelType", "systemInfo", "timestamp"]


class PorscheVehicle:
    """Representation of a Porsche vehicle"""

    def __init__(
        self,
        vin: str = None,
        data: Dict = None,
        status: Dict = None,
        connection: None = None,
    ) -> None:
        self.connection = connection
        self.data = data
        self.remote_services = RemoteServices(self)
        self.status = status

    @property
    def vin(self) -> str:
        """Get the VIN (vehicle identification number) of the vehicle."""
        return self.data["vin"]

    @property
    def has_electric_drivetrain(self) -> bool:
        """Return True if vehicle is equipped with a high voltage battery."""
        return (
            self.data["modelType"]["engine"] == "BEV"
            or self.data["modelType"]["engine"] == "HEV"
        )

    @property
    def charging_target(self) -> bool:
        """Return target state of charge (SoC) for high voltage battery."""

        if self.data.get("CHARGING_PROFILES"):
            charging_profiles = self.data["CHARGING_PROFILES"]["list"]
            active_charging_profile_id = self.data["BATTERY_CHARGING_STATE"][
                "activeProfileId"
            ]

            active_charging_profile = next(
                (p for p in charging_profiles if p["id"] == active_charging_profile_id),
                None,
            )
            _LOGGER.debug(f"Active charging profile is: {active_charging_profile}")
            return active_charging_profile.get("minSoc")
        else:
            return None

    async def _update_data_for_vehicle(self):
        vin = self.vin
        bdata = {}
        mdata = {}
        vdata = {}

        try:
            _LOGGER.debug(f"Getting status for vehicle {self.vin}")
            vdata = self.status
        except PorscheException as err:
            _LOGGER.error(
                "Could not get current overview, error communicating with API: '%s",
                err.message,
            )

        if "vin" in vdata:
            _LOGGER.debug(
                "Vehicle data dict for %s is now: %s",
                vin,
                json.dumps(vdata, indent=2),
            )

            if "customName" not in vdata:
                vdata["customName"] = ""

            bdata = dict((k, vdata[k]) for k in BASE_DATA)

            _LOGGER.debug(
                "Got base data for vehicle '%s': %s",
                vin,
                json.dumps(bdata, indent=2),
            )

            if "measurements" in vdata:
                tdata = [
                    m for m in vdata["measurements"] if m["status"]["isEnabled"] == True
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
                    # For some strange reason, the minSoC attribute if this does not react on changes, so we override it here in the meanwhile
                    mdata["CHARGING_SUMMARY"]["chargingProfile"][
                        "minSoC"
                    ] = self.charging_target

            else:
                _LOGGER.debug("Measurement data missing for vehicle '%s", vin)
                _LOGGER.debug(
                    "Payload for current overview query was: %s",
                    json.dumps(vdata, indent=2),
                )

        else:
            _LOGGER.debug("Base data missing for vehicle '%s", vin)
            _LOGGER.debug(
                "Payload for current overview query was: %s",
                json.dumps(vdata, indent=2),
            )

        self.data = self.data | bdata | mdata
        # return bdata | mdata
