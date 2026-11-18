"""Constants for Anker SOLIX Extras."""

from datetime import timedelta

DOMAIN = "anker_solix_extras"
OFFICIAL_DOMAIN = "anker_solix_official"
CONF_OFFICIAL_ENTRY_ID = "official_entry_id"
UPDATE_INTERVAL = timedelta(seconds=60)
BATTERY_TEMPERATURE_ADDRESS = 10156
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
