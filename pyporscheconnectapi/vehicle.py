from typing import Dict

from pyporscheconnectapi.remote_services import RemoteServices


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
        return self.data["CHARGING_SUMMARY"]["chargingProfile"]["minSoC"]
