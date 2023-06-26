from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.exceptions import WrongCredentials
from hashlib import sha512

import asyncio
import datetime
import logging

_LOGGER = logging.getLogger(__name__)


class Client:
    """Client for Porsche Connect API."""

    def __init__(
        self,
        connection: Connection,
        country="de",
        language="de",
        timezone="Europe/Stockholm",
    ) -> None:
        self._connection = connection
        self.country = country
        self.language = language
        self.timezone = timezone
        self.locale_str = f"{country.lower()}/{language.lower()}_{country.upper()}"

    def isTokenRefreshed(self):
        return self._connection.isTokenRefreshed

    async def getAllTokens(self):
        return await self._connection.getAllTokens()

    async def _spinner(self, url):
        for iteration in range(120):
            data = await self._connection.get(url)
            if "status" in data and data["status"] != "IN_PROGRESS":
                break
            elif "actionState" in data and data["actionState"] != "IN_PROGRESS":
                break
            await asyncio.sleep(1)
        return data

    async def _lockUnlock(self, vin, pin, action, waitForConfirmation=True):
        if pin is not None:
            challengeResult = await self._connection.get(
                f"https://api.porsche.com/service-vehicle/remote-lock-unlock/{vin}/{action}"
            )

            challenge = challengeResult.get("challenge")
            token = challengeResult.get("securityToken")
            pinhash = sha512(bytes.fromhex(pin+challenge)).hexdigest().upper()
            payload = {"challenge": challenge, "securityPinHash": pinhash, "securityToken": token}
        else:
            payload = {}

        progressResult = await self._connection.post(
            f"https://api.porsche.com/service-vehicle/remote-lock-unlock/{vin}/{action}",
            json=payload,
        )

        error = progressResult.get("pcckErrorKey", None)
        if error == "INCORRECT":
            raise WrongCredentials("PIN code was incorrect")
        elif error == "LOCKED_60_MINUTES":
            raise WrongCredentials("Too many failed attempts, locked 60 minutes")
        if not waitForConfirmation:
            return progressResult
        result = await self._spinner(
            f"https://api.porsche.com/service-vehicle/remote-lock-unlock/{vin}/{progressResult['requestId']}/status"
        )
        if result["status"] == "SUCCESS":
            result = await self._connection.get(
                f"https://api.porsche.com/service-vehicle/remote-lock-unlock/{vin}/last-actions"
            )
        return result

    async def _setClimate(self, vin, action, waitForConfirmation=True):
        progressResult = await self._connection.post(
            f"https://api.porsche.com/e-mobility/{self.locale_str}/{vin}/toggle-direct-climatisation/{action}",
            json={},
        )
        if not waitForConfirmation:
            return progressResult
        result = await self._spinner(
            f"https://api.porsche.com/e-mobility/{self.locale_str}/{vin}/toggle-direct-climatisation/status/{progressResult['requestId']}"
        )
        return result

    async def _setDirectCharge(
        self,
        vin,
        action,
        model=None,
        waitForConfirmation=True,
    ):
        if model is None:
            data = await self.getCapabilities(vin)
            model = data["carModel"]
        progressResult = await self._connection.post(
            f"https://api.porsche.com/e-mobility/{self.locale_str}/{model}/{vin}/toggle-direct-charging/{action}",
            json={},
        )
        if not waitForConfirmation:
            return progressResult
        result = await self._spinner(
            f"https://api.porsche.com/e-mobility/{self.locale_str}/{model}/{vin}/toggle-direct-charging/status/{progressResult['requestId']}"
        )
        return result

    async def _setHonkAndFlash(self, vin, waitForConfirmation=True):
        progressResult = await self._connection.post(
            f"https://api.porsche.com/service-vehicle/honk-and-flash/{vin}/honk-and-flash",
            json={},
        )
        if not waitForConfirmation:
            return progressResult
        result = await self._spinner(
            f"https://api.porsche.com/service-vehicle/honk-and-flash/{vin}/{progressResult['id']}/status"
        )
        return result

    async def _setFlash(self, vin, waitForConfirmation=True):
        progressResult = await self._connection.post(
            f"https://api.porsche.com/service-vehicle/honk-and-flash/{vin}/flash",
            json={},
        )
        if not waitForConfirmation:
            return progressResult
        result = await self._spinner(
            f"https://api.porsche.com/service-vehicle/honk-and-flash/{vin}/{progressResult['id']}/status"
        )
        return result

    async def _addTimer(self, vin, timer, model=None, waitForConfirmation=True):
        """Add new charge & climate timer"""
        if model is None:
            data = await self.getCapabilities(vin)
            model = data["carModel"]
        progressResult = await self._connection.post(
            f"https://api.porsche.com/e-mobility/{self.locale_str}/{model}/{vin}/timer",
            json=timer,
        )
        if not waitForConfirmation:
            return progressResult
        result = await self._spinner(
            f"https://api.porsche.com/e-mobility/{self.locale_str}/{model}/{vin}/action-status/{progressResult['actionId']}?hasDX1=false"
        )
        return result

    async def _updateChargingProfile(
        self,
        vin,
        model=None,
        profile=None,
        waitForConfirmation=True,
    ):
        if model is None:
            data = await self.getCapabilities(vin)
            model = data["carModel"]

        progressResult = await self._connection.put(
            f"https://api.porsche.com/e-mobility/{self.locale_str}/{model}/{vin}/profile",
            json=profile,
        )
        if not waitForConfirmation:
            return progressResult
        result = await self._spinner(
            f"https://api.porsche.com/e-mobility/{self.locale_str}/{model}/{vin}/action-status/{progressResult['actionId']}?hasDX1=false"
        )
        return result

    async def _updateTimer(
        self,
        vin,
        timer,
        timerID="1",
        model=None,
        waitForConfirmation=True,
    ):
        if model is None:
            data = await self.getCapabilities(vin)
            model = data["carModel"]
        """Update existing charge & climate timer"""
        timer.update({"timerID": timerID})
        progressResult = await self._connection.put(
            f"https://api.porsche.com/e-mobility/{self.locale_str}/{model}/{vin}/timer",
            json=timer,
        )
        if not waitForConfirmation:
            return progressResult
        result = await self._spinner(
            f"https://api.porsche.com/e-mobility/{self.locale_str}/{model}/{vin}/action-status/{progressResult['actionId']}?hasDX1=false"
        )
        return result

    async def _deleteTimer(
        self, vin, timerID="1", model=None, waitForConfirmation=True
    ):
        if model is None:
            data = await self.getCapabilities(vin)
            model = data["carModel"]
        """Delete existing charge & climate timer"""
        progressResult = await self._connection.delete(
            f"https://api.porsche.com/e-mobility/{self.locale_str}/{model}/{vin}/timer/{timerID}"
        )
        if not waitForConfirmation:
            return progressResult
        result = await self._spinner(
            f"https://api.porsche.com/e-mobility/{self.locale_str}/{model}/{vin}/action-status/{progressResult['actionId']}?hasDX1=false"
        )
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
        charge_level = min(max(int(target_charge), 0), 100)
        return {"chargeOption": charge, "targetChargeLevel": charge_level}

    def _formatTimerTime(self, time, repeat_days=[]):
        """Format time/date settings for timer
        Parameters:
        time (datetime): Target departure date/time as datetime object
        repeat_days (list of integers): Which days to repeat on, if any, 0=Monday)
        """

        # FIXME: There's something missing here for creation of repeating timers
        # Hard to debug b/c the website also isn't letting me right now (app is fine)
        # Format seems to work for updating timers
        if len(repeat_days):
            frequency = "CYCLIC"
        else:
            frequency = "SINGLE"
        repeat_dict = {
            "MONDAY": False,
            "TUESDAY": False,
            "WEDNESDAY": False,
            "THURSDAY": False,
            "FRIDAY": False,
            "SATURDAY": False,
            "SUNDAY": False,
        }
        for i in repeat_days:
            if i == 0:
                repeat_dict["MONDAY"] = True
            elif i == 1:
                repeat_dict["TUESDAY"] = True
            elif i == 2:
                repeat_dict["WEDNESDAY"] = True
            elif i == 3:
                repeat_dict["THURSDAY"] = True
            elif i == 4:
                repeat_dict["FRIDAY"] = True
            elif i == 5:
                repeat_dict["SATURDAY"] = True
            elif i == 6:
                repeat_dict["SUNDAY"] = True

        return {
            "departureDateTime": time.isoformat(),
            "frequency": frequency,
            "weekDays": repeat_dict,
        }

    async def newTimer(
        self,
        vin,
        time,
        active=False,
        charge=False,
        target_charge=10,
        climate=False,
        repeat_days=[],
        model=None,
        waitForConfirmation=True,
    ):
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
        return await self._addTimer(
            vin, full_timer, model, waitForConfirmation=waitForConfirmation
        )

    async def updateChargingProfile(
        self,
        vin,
        model,
        profileId: int,
        minimumChargeLevel: int = None,
        long: float = None,
        lat: float = None,
        profileActive: bool = None,
        waitForConfirmation=True,
    ):
        emobility = (await self.getEmobility(vin, model=model))["chargingProfiles"][
            "profiles"
        ]
        profile = {item["profileId"]: item for item in emobility}[profileId]

        if minimumChargeLevel is not None:
            minimumChargeLevel = min(max(int(minimumChargeLevel), 25), 100)
            profile["chargingOptions"]["minimumChargeLevel"] = minimumChargeLevel

        if profileActive is not None:
            profile["profileActive"] = profileActive

        if long is not None:
            profile["position"]["longitude"] = long

        if lat is not None:
            profile["position"]["latitude"] = lat

        return await self._updateChargingProfile(
            vin, model, profile, waitForConfirmation=waitForConfirmation
        )

    async def updateTimer(
        self,
        vin,
        time,
        timerID="1",
        active=False,
        charge=False,
        target_charge=10,
        climate=False,
        repeat_days=[],
        model=None,
        waitForConfirmation=True,
    ):
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
        return await self._updateTimer(
            vin, full_timer, timerID, model, waitForConfirmation=waitForConfirmation
        )

    async def deleteTimer(self, vin, timerID="1", model=None, waitForConfirmation=True):
        """Delete an existing timer on the vehicle
        Parameters:
        vin (string): Vehicle VIN
        timerId (string): Target timer (numeric string)
        """
        return await self._deleteTimer(
            vin, timerID, model, waitForConfirmation=waitForConfirmation
        )

    async def lock(self, vin, waitForConfirmation=True):
        return await self._lockUnlock(
            vin, None, "quick-lock", waitForConfirmation=waitForConfirmation
        )

    async def unlock(self, vin, pin, waitForConfirmation=True):
        return await self._lockUnlock(
            vin, pin, "security-pin/unlock", waitForConfirmation=waitForConfirmation
        )

    async def climateOn(self, vin, waitForConfirmation=True):
        return await self._setClimate(
            vin, "true", waitForConfirmation=waitForConfirmation
        )

    async def climateOff(self, vin, waitForConfirmation=True):
        return await self._setClimate(
            vin, "false", waitForConfirmation=waitForConfirmation
        )

    async def directChargeOn(self, vin, model=None, waitForConfirmation=True):
        return await self._setDirectCharge(
            vin, "true", model, waitForConfirmation=waitForConfirmation
        )

    async def directChargeOff(self, vin, model=None, waitForConfirmation=True):
        return await self._setDirectCharge(
            vin, "false", model, waitForConfirmation=waitForConfirmation
        )

    async def honkAndFlash(self, vin, waitForConfirmation=True):
        return await self._setHonkAndFlash(vin, waitForConfirmation=waitForConfirmation)

    async def flash(self, vin, waitForConfirmation=True):
        return await self._setFlash(vin, waitForConfirmation=waitForConfirmation)

    async def getPermissions(self, vin):
        return await self._connection.get(
            f"https://api.porsche.com/core/api/v2/se/sv_SE/vehicles/{vin}/permissions"
        )

    async def isAllowed(self, vin):
        perms = await self.getPermissions(vin)
        print(perms)
        allowed = False
        reason = ""
        if perms["userIsActive"] and perms["userRoleStatus"] == "ENABLED":
            service_status = await self._connection.get(
                f"https://api.porsche.com/core/api/v4/de/de_DE/services?{vin}"
            )
            print(service_status)
            reason = service_status.get(
                "STATUS", service_status.get("disabledReason", "")
            )
            mydata = await self._connection.get(
                f"https://api.porsche.com/profiles/mydata?country={self.country}"
            )
            _LOGGER.debug(mydata)
            for vehicle in mydata["vehicles"]:
                print(vehicle)
                if vehicle["vin"] == vin:
                    if vehicle["confirmed"] and vehicle["pcc"]:
                        allowed = True
                        break
        return_value = {"allowed": allowed, "reason": reason}
        return return_value

    async def getVehicles(self):
        vehicles = await self._connection.get(
            f"https://api.porsche.com/core/api/v3/{self.locale_str}/vehicles"
        )
        return vehicles

    async def getStoredOverview(self, vin):
        data = await self._connection.get(
            f"https://api.porsche.com/service-vehicle/{self.locale_str}/vehicle-data/{vin}/stored"
        )
        return data

    async def getCurrentOverview(self, vin):
        progressResult = await self._connection.post(
            f"https://api.porsche.com/service-vehicle/{self.locale_str}/vehicle-data/{vin}/current/request"
        )
        spinnerResult = await self._spinner(
            f"https://api.porsche.com/service-vehicle/{self.locale_str}/vehicle-data/{vin}/current/request/{progressResult['requestId']}/status"
        )
        data = await self._connection.get(
            f"https://api.porsche.com/service-vehicle/{self.locale_str}/vehicle-data/{vin}/current/request/{progressResult['requestId']}"
        )
        return data

    async def getMaintenance(self, vin):
        data = await self._connection.get(
            f"https://api.porsche.com/predictive-maintenance/information/{vin}"
        )
        return data

    async def getSummary(self, vin):
        data = await self._connection.get(
            f"https://api.porsche.com/service-vehicle/vehicle-summary/{vin}"
        )
        return data

    async def getServices(self, vin):
        data = await self._connection.get(
            f"https://api.porsche.com/service-vehicle/service-access/{vin}/details"
        )
        # Find out if we're in privacy mode
        is_privacy = data['vehicleServiceEnabledMap']['VSR'] == 'DISABLED'
        data["privacyMode"] = is_privacy
        return data

    async def getCapabilities(self, vin):
        data = await self._connection.get(
            f"https://api.porsche.com/service-vehicle/vcs/capabilities/{vin}"
        )
        return data

    async def getPosition(self, vin):
        data = await self._connection.get(
            f"https://api.porsche.com/service-vehicle/car-finder/{vin}/position"
        )
        return data

    async def getTheftAlerts(self, vin):
        data = await self._connection.get(
            f"https://api.porsche.com/service-vehicle/theft-alerts/{vin}/history"
        )
        return data

    async def getSpeedAlerts(self, vin):
        data = await self._connection.get(
            f"https://api.porsche.com/service-vehicle/{self.locale_str}/speed-alert/{vin}/alerts"
        )
        return data

    async def getTripLongTerm(self, vin):
        data = await self._connection.get(
            f"https://api.porsche.com/service-vehicle/{self.locale_str}/trips/{vin}/LONG_TERM/newest"
        )
        return data

    async def getTripShortTerm(self, vin):
        data = await self._connection.get(
            f"https://api.porsche.com/service-vehicle/{self.locale_str}/trips/{vin}/SHORT_TERM"
        )
        return data

    async def getEmobility(
        self,
        vin,
        model=None,
    ):
        if model is None:
            data = await self.getCapabilities(vin)
            model = data["carModel"]
        data = await self._connection.get(
            f"https://api.porsche.com/e-mobility/{self.locale_str}/{model}/{vin}?timezone={self.timezone}"
        )
        return data
