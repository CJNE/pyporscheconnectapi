from typing import Dict


class PorscheVehicle:
    """Representation of a Porsche vehicle"""

    def __init__(
        self,
        vin: str = None,
        data: Dict = None,
        status: Dict = None
    ) -> None:
        self.data = data
        self.status = status

    @property
    def vin(self) -> str:
        """Get the VIN (vehicle identification number) of the vehicle."""
        return self.data["vin"]

    @property
    def has_electric_drivetrain(self) -> bool:
        """Return True if vehicle is equipped with a high voltage battery.
        """
        return (self.data["modelType"]["engine"] == "BEV" or self.data["modelType"]["engine"] == "HEV")
