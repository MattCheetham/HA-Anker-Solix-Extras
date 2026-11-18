"""Constants for Anker SOLIX Extras."""

DOMAIN = "anker_solix_extras"
OFFICIAL_DOMAIN = "anker_solix_official"
CONF_OFFICIAL_ENTRY_ID = "official_entry_id"
DEFAULT_SCAN_INTERVAL = 60
BATTERY_TEMPERATURE_ADDRESS = 10156
BATTERY_SOH_ADDRESS = 10015
AC_POWER_ADDRESS = 10006
MODBUS_DEVICE_ID = 1
MODBUS_TIMEOUT = 5

SUPPORTED_MODELS = frozenset(
    {
        "Anker SOLIX Solarbank 4 E5000 Pro",
        "Anker SOLIX Solarbank Max",
        "Anker SOLIX Solarbank Max AC",
        "Anker SOLIX XE",
        "Anker SOLIX XE AC",
    }
)
