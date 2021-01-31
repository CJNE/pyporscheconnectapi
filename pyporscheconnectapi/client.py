from pyporscheconnectapi.connection import Connection

class Client:
    """Client for Porsche Connect API."""

    def __init__(
        self,
        connection: Connection
    ) -> None:
        self._connection = connection


    async def getVehicles(self):
        vehicles = await self._connection.get("https://connect-portal.porsche.com/core/api/v3/de/de_DE/vehicles",
                application='portal')
        return vehicles





