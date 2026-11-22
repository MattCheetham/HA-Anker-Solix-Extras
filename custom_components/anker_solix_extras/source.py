"""Discover batteries through public Home Assistant registries."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from modbus_connection import ModbusTcpParams

from .const import (
    OFFICIAL_DOMAIN,
    PCS_COUNT_ADDRESSES,
    PUBLISHED_REGISTER_MODELS,
    SOLARBANK_4_E5000_PRO,
    SUPPORTED_MODELS,
)


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

    @property
    def supports_published_registers(self) -> bool:
        """Return whether the model is listed in Anker's register documentation."""
        return self.device.model in PUBLISHED_REGISTER_MODELS

    @property
    def enables_off_grid_output_by_default(self) -> bool:
        """Return whether to add off-grid output power by default."""
        return self.device.model == SOLARBANK_4_E5000_PRO

    @property
    def pcs_count_addresses(self) -> dict[str, int]:
        """Return PCS count registers offered for this battery model."""
        addresses = PCS_COUNT_ADDRESSES.copy()
        if self.device.model == SOLARBANK_4_E5000_PRO:
            addresses.pop("available_pcs_count")
        return addresses


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
