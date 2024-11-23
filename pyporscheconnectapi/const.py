""" Client configuration constants """

AUTHORIZATION_SERVER = "identity.porsche.com"
REDIRECT_URI = "my-porsche-app://auth0/callback"
AUDIENCE = "https://api.porsche.com"
CLIENT_ID = "XhygisuebbrqQ80byOuU5VncxLIm8E6H"
X_CLIENT_ID = "41843fb4-691d-4970-85c7-2673e8ecef40"
USER_AGENT = "pyporscheconnectapi/0.2.0"
# USER_AGENT = "de.porsche.one/11.24.14+301 (ios)"
SCOPE = "openid profile email offline_access mbb ssodb badge vin dealers cars charging manageCharging plugAndCharge climatisation manageClimatisation pid:user_profile.porscheid:read pid:user_profile.name:read pid:user_profile.vehicles:read pid:user_profile.dealers:read pid:user_profile.emails:read pid:user_profile.phones:read pid:user_profile.addresses:read pid:user_profile.birthdate:read pid:user_profile.locale:read pid:user_profile.legal:read"
API_BASE_URL = "https://api.ppa.porsche.com/app"
AUTHORIZATION_URL = f"https://{AUTHORIZATION_SERVER}/authorize"
TOKEN_URL = f"https://{AUTHORIZATION_SERVER}/oauth/token"
TIMEOUT = 90

""" Vehicle properties """

MEASUREMENTS = [
    "ACV_STATE",
    "ALARM_STATE",
    "BATTERY_CHARGING_STATE",
    "BATTERY_LEVEL",
    "BLEID_DDADATA",
    "CHARGING_PROFILES",
    "CHARGING_SUMMARY",
    "CLIMATIZER_STATE",
    "DEPARTURES",
    "E_RANGE",
    "FUEL_LEVEL",
    "FUEL_RESERVE",
    "GLOBAL_PRIVACY_MODE",
    "GPS_LOCATION",
    "HEATING_STATE",
    "INTERMEDIATE_SERVICE_RANGE",
    "INTERMEDIATE_SERVICE_TIME",
    "LOCK_STATE_VEHICLE",
    "MAIN_SERVICE_RANGE",
    "MAIN_SERVICE_TIME",
    "MILEAGE",
    "OIL_LEVEL_CURRENT",
    "OIL_LEVEL_MAX",
    "OIL_LEVEL_MIN_WARNING",
    "OIL_SERVICE_RANGE",
    "OIL_SERVICE_TIME",
    "OPEN_STATE_CHARGE_FLAP_LEFT",  #
    "OPEN_STATE_CHARGE_FLAP_RIGHT",  #
    "OPEN_STATE_DOOR_FRONT_LEFT",
    "OPEN_STATE_DOOR_FRONT_RIGHT",
    "OPEN_STATE_DOOR_REAR_LEFT",
    "OPEN_STATE_DOOR_REAR_RIGHT",
    "OPEN_STATE_LID_FRONT",
    "OPEN_STATE_LID_REAR",
    "OPEN_STATE_SERVICE_FLAP",
    "OPEN_STATE_SPOILER",
    "OPEN_STATE_SUNROOF",
    "OPEN_STATE_TOP",
    "OPEN_STATE_WINDOW_FRONT_LEFT",
    "OPEN_STATE_WINDOW_FRONT_RIGHT",
    "OPEN_STATE_WINDOW_REAR_LEFT",
    "OPEN_STATE_WINDOW_REAR_RIGHT",
    "PAIRING_CODE",
    "PARKING_BRAKE",
    "PARKING_LIGHT",
    "PRED_PRECON_LOCATION_EXCEPTIONS",
    "PRED_PRECON_USER_SETTINGS",
    "RANGE",
    "REMOTE_ACCESS_AUTHORIZATION",
    "SERVICE_PREDICTIONS",
    "THEFT_STATE",
    "TIMERS",
    "VTS_MODES",
]

COMMANDS = [
    "BLEID_AGREEMENT_GIVE",
    "BLEID_AGREEMENT_REVOKE",
    "BLEID_DEVICEKEY_UPLOAD",
    "B_CALL_TRIGGER",
    "CHARGING_PROFILES_EDIT",
    "CHARGING_SETTINGS_AUTOPLUG_EDIT",
    "CHARGING_SETTINGS_BATTERYCAREMODE_EDIT",
    "CHARGING_SETTINGS_CERTIFICATES_RESET",
    "CHARGING_SETTINGS_EDIT",
    "CHARGING_STOP",
    "CS_C2P_IN_VEHICLE_INFOTAINMENT",
    "CS_DESTINATION_SYNC",
    "CS_PCM_ACCOUNT_SERVICES",
    "CS_PCM_CALENDAR",
    "CS_PILOTED_PARKING",
    "CS_VIDEOSTREAMING_VOUCHER",
    "DEPARTURES_EDIT",
    "DIRECT_CHARGING_START",
    "DIRECT_CHARGING_STOP",
    "HONK_FLASH",
    "LOCK",
    "PRED_PRECON_LOCATION_EXCEPTION_EDIT",
    "PRED_PRECON_USER_SETTINGS_EDIT",
    "REMOTE_ACV_START",
    "REMOTE_ACV_STOP",
    "REMOTE_CLIMATIZER_START",
    "REMOTE_CLIMATIZER_STOP",
    "REMOTE_HEATING_START",
    "REMOTE_HEATING_STOP",
    "ROUTE_CALCULATE",
    "SERVICE_PREDICTIONS_VISIBILITY_EDIT",
    "SPIN_CHALLENGE",
    "TIMERS_DISABLE",
    "TIMERS_EDIT",
    "UNLOCK",
]

TRIP_STATISTICS = [
    "TRIP_STATISTICS_CYCLIC",
    "TRIP_STATISTICS_LONG_TERM",
    "TRIP_STATISTICS_LONG_TERM_HISTORY",
    "TRIP_STATISTICS_SHORT_TERM_HISTORY",
    "TRIP_STATISTICS_CYCLIC_HISTORY",
    "TRIP_STATISTICS_SHORT_TERM",
]
