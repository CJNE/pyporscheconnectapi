from pyporscheconnectapi.connection import Connection

class Client:
    """Client for Porsche Connect API."""

    def __init__(
        self,
        connection: Connection
    ) -> None:
        self._connection = connection


    def isTokenRefreshed(self):
        return self._connection.isTokenRefreshed

    async def getAllTokens(self):
        return await self._connection.getAllTokens()

    async def getVehicles(self):
        vehicles = await self._connection.get("https://connect-portal.porsche.com/core/api/v3/de/de_DE/vehicles")
        return vehicles

    async def getOverview(self, vin):
        data = await self._connection.get(f"https://api.porsche.com/service-vehicle/se/sv_SE/vehicle-data/{vin}/stored")
        return data

    async def getMaintenance(self, vin):
        data = await self._connection.get(f"https://api.porsche.com/predictive-maintenance/information/{vin}")
        return data

    async def getSummary(self, vin):
        data = await self._connection.get(f"https://api.porsche.com/service-vehicle/vehicle-summary/{vin}")
        return data

    async def getCapabilities(self, vin):
        data = await self._connection.get(f"https://api.porsche.com/service-vehicle/vcs/capabilities/{vin}")
        return data

    async def getPosition(self, vin):
        data = await self._connection.get(f"https://api.porsche.com/service-vehicle/car-finder/{vin}/position")
        return data

    async def getTheftAlerts(self, vin):
        data = await self._connection.get(f"https://api.porsche.com/service-vehicle/theft-alerts/{vin}/history")
        return data

    async def getSpeedAlerts(self, vin, country= 'DE', language = 'de'):
        data = await self._connection.get(f"https://api.porsche.com/service-vehicle/{country.lower()}/{language.lower()}_{country.upper()}/speed-alert/{vin}/alerts")
        return data

    async def getTripLongTerm(self, vin, country= 'DE', language = 'de'):
        data = await self._connection.get(f"https://api.porsche.com/service-vehicle/{country.lower()}/{language.lower()}_{country.upper()}/trips/{vin}/LONG_TERM/newest")
        return data

    async def getTripShortTerm(self, vin, country= 'DE', language = 'de'):
        data = await self._connection.get(f"https://api.porsche.com/service-vehicle/{country.lower()}/{language.lower()}_{country.upper()}/trips/{vin}/SHORT_TERM")
        return data

    async def getEmobility(self, vin, model = None, country= 'DE', language = 'de', timezone='Europe/Stockholm'):
        if model is None:
            data = await self.getCapabilities(vin)
            model = data['carModel']
        data = await self._connection.get(f"https://api.porsche.com/service-vehicle/{country.lower()}/{language.lower()}_{country.upper()}/e-mobility/{model}/{vin}?timezone={timezone}")
        return data






