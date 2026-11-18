"""Discover batteries through public Home Assistant registries."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from modbus_connection import ModbusTcpParams

from .const import OFFICIAL_DOMAIN, SUPPORTED_MODELS


@dataclass(frozen=True, slots=True)
class OfficialBattery:
    """An official config entry and its already registered battery."""

    entry: ConfigEntry
    device: dr.DeviceEntry
    host: str
    port: int

    @property
    def modbus_params(self) -> ModbusTcpParams:
        """Use the source endpoint with Home Assistant's shared TCP defaults."""
        return ModbusTcpParams(host=self.host, port=self.port)


@callback
def async_get_battery(hass: HomeAssistant, entry_id: str) -> OfficialBattery | None:
    """Resolve a loaded, enabled official battery without changing its entry."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if (
        entry is None
        or entry.domain != OFFICIAL_DOMAIN
        or entry.disabled_by is not None
        or entry.state is not ConfigEntryState.LOADED
    ):
        return None

    host = entry.data.get("ip_address")
    port = entry.data.get("port", 502)
    if not isinstance(host, str) or not host.strip():
        return None
    if type(port) is not int or not 1 <= port <= 65535:
        return None

    device = dr.async_get(hass).async_get_device_by_identifier(
        (OFFICIAL_DOMAIN, entry.entry_id), entry.entry_id
    )
    if device is None or device.disabled or device.model not in SUPPORTED_MODELS:
        return None

    return OfficialBattery(entry, device, host, port)


@callback
def async_get_batteries(hass: HomeAssistant) -> list[OfficialBattery]:
    """List supported batteries that are ready for an Extras entry."""
    return [
        battery
        for entry in hass.config_entries.async_entries(OFFICIAL_DOMAIN)
        if (battery := async_get_battery(hass, entry.entry_id)) is not None
    ]
