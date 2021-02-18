from pyporscheconnectapi.connection import Connection
import asyncio

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

    async def _spinner(self, url):
        while True:
            data = await self._connection.get(url)
            if data['status'] != 'IN_PROGRESS':
                break
            await asyncio.sleep(1)
        return data

    async def _lockUnlock(self, vin, pin, action, waitForConfirmation=True):
        progressResult = await self._connection.post(f"https://api.porsche.com/service-vehicle/remote-lock-unlock/{vin}/{action}", json={ 'pin': pin })
        if not waitForConfirmation: return progressResult
        result = await self._spinner(f"https://api.porsche.com/service-vehicle/remote-lock-unlock/{vin}/{progressResult['requestId']}/status")
        if(result['status'] == 'SUCCESS'):
            result = await self._connection.get(f"https://api.porsche.com/service-vehicle/remote-lock-unlock/{vin}/last-actions")
        return result

    async def _setClimate(self, vin, action, country = 'de', language = 'de', waitForConfirmation=True):
        progressResult = await self._connection.post(f"https://api.porsche.com/service-vehicle/{country.lower()}/{language.lower()}_{country.upper()}/e-mobility/{vin}/toggle-direct-climatisation/{action}", json={})
        if not waitForConfirmation: return progressResult
        result = await self._spinner(f"https://api.porsche.com/service-vehicle/se/sv_SE/e-mobility/{vin}/toggle-direct-climatisation/status/{progressResult['requestId']}")
        return result

    async def _setDirectCharge(self, vin, action, country = 'de', language = 'de', waitForConfirmation=True):
        progressResult = await self._connection.post(f"https://api.porsche.com/service-vehicle/{country.lower()}/{language.lower()}_{country.upper()}/e-mobility/J1/{vin}/toggle-direct-charging/{action}", json={})
        if not waitForConfirmation: return progressResult
        result = await self._spinner(f"https://api.porsche.com/service-vehicle/se/sv_SE/e-mobility/J1/{vin}/toggle-direct-charging/status/{progressResult['requestId']}")
        return result


    async def lock(self, vin, pin, waitForConfirmation=True):
        return await self._lockUnlock(vin, pin, 'lock', waitForConfirmation=waitForConfirmation)

    async def unlock(self, vin, pin, waitForConfirmation=True):
        return await self._lockUnlock(vin, pin, 'unlock', waitForConfirmation=waitForConfirmation)

    async def climateOn(self, vin, waitForConfirmation=True):
        return await self._setClimate(vin, 'true', waitForConfirmation=waitForConfirmation)

    async def climateOff(self, vin, waitForConfirmation=True):
        return await self._setClimate(vin,'false', waitForConfirmation=waitForConfirmation)

    async def directChargeOn(self, vin, waitForConfirmation=True):
        return await self._setDirectCharge(vin, 'true', waitForConfirmation=waitForConfirmation)

    async def directChargeOff(self, vin, waitForConfirmation=True):
        return await self._setDirectCharge(vin, 'true', waitForConfirmation=waitForConfirmation)

    async def getVehicles(self):
        vehicles = await self._connection.get("https://connect-portal.porsche.com/core/api/v3/de/de_DE/vehicles")
        return vehicles

    async def getStoredOverview(self, vin):
        data = await self._connection.get(f"https://api.porsche.com/service-vehicle/se/sv_SE/vehicle-data/{vin}/stored")
        return data

    async def getCurrentOverview(self, vin):
        progressResult = await self._connection.post(f"https://api.porsche.com/service-vehicle/se/sv_SE/vehicle-data/{vin}/current/request")
        spinnerResult = await self._spinner(f"https://api.porsche.com/service-vehicle/se/sv_SE/vehicle-data/{vin}/current/request/{progressResult['requestId']}/status")
        data = await self._connection.get(f"https://api.porsche.com/service-vehicle/se/sv_SE/vehicle-data/{vin}/current/request/{progressResult['requestId']}")
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






