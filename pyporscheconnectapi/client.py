from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.exceptions import WrongCredentials

import asyncio
import datetime
import logging
_LOGGER = logging.getLogger(__name__)

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
            if 'status' in data and data['status'] != 'IN_PROGRESS':
                break
            elif 'actionState' in data and data['actionState'] != 'IN_PROGRESS':
                break
            await asyncio.sleep(1)
        return data

    async def _lockUnlock(self, vin, pin, action, waitForConfirmation=True):
        progressResult = await self._connection.post(f"https://api.porsche.com/service-vehicle/remote-lock-unlock/{vin}/{action}", json={ 'pin': pin })
        error = progressResult.get('pcckErrorKey', None)
        if error == 'INCORRECT':
            raise WrongCredentials("PIN code was incorrect")
        elif error == 'LOCKED_60_MINUTES':
            raise WrongCredentials("Too many failed attempts, locked 60 minutes")
        if not waitForConfirmation: return progressResult
        result = await self._spinner(f"https://api.porsche.com/service-vehicle/remote-lock-unlock/{vin}/{progressResult['requestId']}/status")
        if(result['status'] == 'SUCCESS'):
            result = await self._connection.get(f"https://api.porsche.com/service-vehicle/remote-lock-unlock/{vin}/last-actions")
        return result

    async def _setClimate(self, vin, action, country = 'de', language = 'de', waitForConfirmation=True):
        progressResult = await self._connection.post(f"https://api.porsche.com/e-mobility/{country.lower()}/{language.lower()}_{country.upper()}/{vin}/toggle-direct-climatisation/{action}", json={})
        if not waitForConfirmation: return progressResult
        result = await self._spinner(f"https://api.porsche.com/e-mobility/se/sv_SE/{vin}/toggle-direct-climatisation/status/{progressResult['requestId']}")
        return result

    async def _setDirectCharge(self, vin, action, model=None, country = 'de', language = 'de', waitForConfirmation=True):
        if model is None:
            data = await self.getCapabilities(vin)
            model = data['carModel']
        progressResult = await self._connection.post(f"https://api.porsche.com/e-mobility/{country.lower()}/{language.lower()}_{country.upper()}/{model}/{vin}/toggle-direct-charging/{action}", json={})
        if not waitForConfirmation: return progressResult
        result = await self._spinner(f"https://api.porsche.com/e-mobility/se/sv_SE/{model}/{vin}/toggle-direct-charging/status/{progressResult['requestId']}")
        return result

    async def _setHonkAndFlash(self, vin, waitForConfirmation=True):
        progressResult = await self._connection.post(f"https://api.porsche.com/service-vehicle/honk-and-flash/{vin}/honk-and-flash", json={})
        if not waitForConfirmation: return progressResult
        result = await self._spinner(f"https://api.porsche.com/service-vehicle/honk-and-flash/{vin}/{progressResult['id']}/status")
        return result

    async def _setFlash(self, vin, waitForConfirmation=True):
        progressResult = await self._connection.post(f"https://api.porsche.com/service-vehicle/honk-and-flash/{vin}/flash", json={})
        if not waitForConfirmation: return progressResult
        result = await self._spinner(f"https://api.porsche.com/service-vehicle/honk-and-flash/{vin}/{progressResult['id']}/status")
        return result

    async def _addTimer(self, vin, timer, country = 'de', language = 'de', waitForConfirmation=True):
        """Add new charge & climate timer"""
        progressResult = await self._connection.post(f"https://api.porsche.com/e-mobility/{country.lower()}/{language.lower()}_{country.upper()}/J1/{vin}/timer", json=timer)
        if not waitForConfirmation: return progressResult
        result = await self._spinner(f"https://api.porsche.com/e-mobility/{country.lower()}/{language.lower()}_{country.upper()}/J1/{vin}/action-status/{progressResult['actionId']}")
        return result

    async def _updateTimer(self, vin, timer, timerID='1', country = 'de', language = 'de', waitForConfirmation=True):
        """Update existing charge & climate timer"""
        timer.update({"timerID":timerID})
        progressResult = await self._connection.put(f"https://api.porsche.com/e-mobility/{country.lower()}/{language.lower()}_{country.upper()}/J1/{vin}/timer", json=timer)
        if not waitForConfirmation: return progressResult
        result = await self._spinner(f"https://api.porsche.com/e-mobility/{country.lower()}/{language.lower()}_{country.upper()}/J1/{vin}/action-status/{progressResult['actionId']}")
        return result

    async def _deleteTimer(self, vin, timerID='1', country = 'de', language = 'de', waitForConfirmation=True):
        """Delete existing charge & climate timer"""
        progressResult = await self._connection.delete(f"https://api.porsche.com/e-mobility/{country.lower()}/{language.lower()}_{country.upper()}/J1/{vin}/timer/{timerID}")
        if not waitForConfirmation: return progressResult
        result = await self._spinner(f"https://api.porsche.com/e-mobility/{country.lower()}/{language.lower()}_{country.upper()}/J1/{vin}/action-status/{progressResult['actionId']}")
        return result

    def _formatTimer(self, active, charge_settings, climate, time_date):
        """Format combined payload for charge & climate timer"""
        payload = {"active": active, "climatised": climate}
        payload.update(charge_settings)
        payload.update(time_date)
        return payload

    def _formatChargeTimer(self, charge=False, target_charge=10):
        """Format payload for charge timer
        Parameters:
        charge (bool): Enable charging?
        target_charge (0-100): Target charge level
        """
        charge_level = min(max(int(target_charge),0),100)
        return {"chargeOption": charge, "targetChargeLevel": charge_level}

    def _formatTimerTime(self, time, repeat_days=[]):
        """Format time/date settings for timer
        Parameters:
        time (datetime): Target departure date/time as datetime object
        repeat_days (list of integers): Which days to repeat on, if any, 0=Monday)
        """

        #FIXME: There's something missing here for creation of repeating timers
        # Hard to debug b/c the website also isn't letting me right now (app is fine)
        # Format seems to work for updating timers
        if len(repeat_days):
            frequency = "CYCLIC"
        else:
            frequency = "SINGLE"
        repeat_dict = {"MONDAY": False, "TUESDAY": False, "WEDNESDAY": False, "THURSDAY": False, "FRIDAY": False,\
                "SATURDAY": False, "SUNDAY": False}
        for i in repeat_days:
            if i==0: repeat_dict["MONDAY"] = True
            elif i==1: repeat_dict["TUESDAY"] = True
            elif i==2: repeat_dict["WEDNESDAY"] = True
            elif i==3: repeat_dict["THURSDAY"] = True
            elif i==4: repeat_dict["FRIDAY"] = True
            elif i==5: repeat_dict["SATURDAY"] = True
            elif i==6: repeat_dict["SUNDAY"] = True

        return {"departureDateTime": time.isoformat(), "frequency": frequency, "weekDays": repeat_dict}

    async def newTimer(self, vin, time, active=False, charge=False, target_charge=10,\
            climate=False, repeat_days=[], waitForConfirmation=True):
        """Create a new timer on the vehicle
        Parameters:
        vin (string): Vehicle VIN
        time (datetime): Target departure date/time as datetime object
        active (bool): Timer should be active upon creation?
        charge (bool): Enable charging?
        target_charge (0-100): Target charge level
        climate (bool): Precondition cabin?
        repeat_days (list of integers): Which days to repeat on, if any, 0=Monday)

        FIXME: Creation of repeating timers isn't working, see _formatTimerTime
        """
        timer_time = self._formatTimerTime(time, repeat_days)
        charge_timer = self._formatChargeTimer(charge, target_charge)
        full_timer = self._formatTimer(active, charge_timer, climate, timer_time)
        return await self._addTimer(vin, full_timer, waitForConfirmation=waitForConfirmation)

    async def updateTimer(self, vin, time, timerID='1', active=False, charge=False, target_charge=10,\
            climate=False, repeat_days=[], waitForConfirmation=True):
        """Update an existing timer on the vehicle
        Parameters:
        vin (string): Vehicle VIN
        time (datetime): Target departure date/time as datetime object
        timerId (string): Target timer (numeric string)
        active (bool): Timer should be active upon creation?
        charge (bool): Enable charging?
        target_charge (0-100): Target charge level
        climate (bool): Precondition cabin?
        repeat_days (list of integers): Which days to repeat on, if any, 0=Monday)
        """
        timer_time = self._formatTimerTime(time, repeat_days)
        charge_timer = self._formatChargeTimer(charge, target_charge)
        full_timer = self._formatTimer(active, charge_timer, climate, timer_time)
        return await self._updateTimer(vin, full_timer, timerID, waitForConfirmation=waitForConfirmation)

    async def deleteTimer(self, vin, timerID='1', waitForConfirmation=True):
        """Delete an existing timer on the vehicle
        Parameters:
        vin (string): Vehicle VIN
        timerId (string): Target timer (numeric string)
        """
        return await self._deleteTimer(vin, timerID, waitForConfirmation=waitForConfirmation)

    async def lock(self, vin, waitForConfirmation=True):
        return await self._lockUnlock(vin, None, 'lock', waitForConfirmation=waitForConfirmation)

    async def unlock(self, vin, pin, waitForConfirmation=True):
        return await self._lockUnlock(vin, pin, 'unlock', waitForConfirmation=waitForConfirmation)

    async def climateOn(self, vin, waitForConfirmation=True):
        return await self._setClimate(vin, 'true', waitForConfirmation=waitForConfirmation)

    async def climateOff(self, vin, waitForConfirmation=True):
        return await self._setClimate(vin,'false', waitForConfirmation=waitForConfirmation)

    async def directChargeOn(self, vin, model=None, waitForConfirmation=True):
        return await self._setDirectCharge(vin, 'true', model, waitForConfirmation=waitForConfirmation)

    async def directChargeOff(self, vin, model=None, waitForConfirmation=True):
        return await self._setDirectCharge(vin, 'false', model, waitForConfirmation=waitForConfirmation)

    async def honkAndFlash(self, vin, waitForConfirmation=True):
        return await self._setHonkAndFlash(vin, waitForConfirmation=waitForConfirmation)

    async def flash(self, vin, waitForConfirmation=True):
        return await self._setFlash(vin, waitForConfirmation=waitForConfirmation)

    async def getVehicles(self):
        vehicles = await self._connection.get("https://api.porsche.com/core/api/v3/se/sv_SE/vehicles")
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

    async def getServices(self, vin):
        data = await self._connection.get(f"https://api.porsche.com/service-vehicle/service-access/{vin}/details")
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
        data = await self._connection.get(f"https://api.porsche.com/e-mobility/{country.lower()}/{language.lower()}_{country.upper()}/{model}/{vin}?timezone={timezone}")
        return data






