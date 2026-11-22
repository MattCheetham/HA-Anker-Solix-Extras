"""Constants for Anker SOLIX Extras."""

DOMAIN = "anker_solix_extras"
OFFICIAL_DOMAIN = "anker_solix_official"
CONF_ENABLE_OFF_GRID_OUTPUT_POWER = "enable_off_grid_output_power"
CONF_ENABLE_PUBLISHED_REGISTERS = "enable_published_registers"
CONF_OFFICIAL_ENTRY_ID = "official_entry_id"
DEFAULT_SCAN_INTERVAL = 10
BATTERY_TEMPERATURE_ADDRESS = 10156
BATTERY_SOH_ADDRESS = 10015
PLANT_STATUS_ADDRESS = 10000
AC_POWER_ADDRESS = 10006
OFF_GRID_OUTPUT_POWER_ADDRESS = 10233
PLANT_STATUS_STATES = {1: "on_grid", 2: "off_grid", 3: "standby", 4: "fault"}
RESERVE_CAPABILITY_ADDRESS = 32775
RESERVE_ENABLE_CAPABILITY = 1 << 3
RESERVE_ENABLE_ADDRESS = 60003
MODBUS_DEVICE_ID = 1
SOLARBANK_4_E5000_PRO = "Anker SOLIX Solarbank 4 E5000 Pro"

PUBLISHED_REGISTER_MODELS = frozenset(
    {
        "Anker SOLIX Solarbank Max",
        "Anker SOLIX Solarbank Max AC",
        "Anker SOLIX XE",
        "Anker SOLIX XE AC",
    }
)
SUPPORTED_MODELS = PUBLISHED_REGISTER_MODELS | {SOLARBANK_4_E5000_PRO}

ENERGY_ADDRESSES = {
    "total_battery_charge_energy": 10022,
    "total_battery_discharge_energy": 10024,
    "total_load_energy": 10026,
    "total_grid_import_energy": 10030,
    "total_grid_export_energy": 10034,
}
POWER_LIMIT_ADDRESSES = {
    "rechargeable_power": 10036,
    "dischargeable_power": 10038,
}
PCS_COUNT_ADDRESSES = {"pcs_count": 10040, "available_pcs_count": 10041}
SYSTEM_TIME_ADDRESS = 10060
EXPORT_LIMIT_ENABLE_ADDRESS = 10074
EXPORT_LIMIT_ADDRESS = 10075
MAX_EXPORT_LIMIT = (1 << 31) - 1
