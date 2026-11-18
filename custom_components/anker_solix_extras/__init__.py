"""Anker SOLIX Extras: additional entities for the official integration."""

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import device_registry as dr

from .client import AnkerSolixExtrasClient
from .const import CONF_OFFICIAL_ENTRY_ID, MODBUS_DEVICE_ID
from .coordinator import AnkerSolixExtrasCoordinator
from .source import async_get_battery

type AnkerSolixExtrasConfigEntry = ConfigEntry[AnkerSolixExtrasCoordinator]

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.NUMBER]


async def async_setup_entry(
    hass: HomeAssistant, entry: AnkerSolixExtrasConfigEntry
) -> bool:
    """Set up Extras for an existing official battery."""
    battery = async_get_battery(hass, entry.data[CONF_OFFICIAL_ENTRY_ID])
    if battery is None:
        raise ConfigEntryNotReady("The linked official battery is not ready")

    try:
        unit = async_get_unit(hass, entry, battery.modbus_params, MODBUS_DEVICE_ID)
    except HomeAssistantError as err:
        raise ConfigEntryError(
            f"Unable to register the battery's Modbus connection: {err}"
        ) from err

    coordinator = AnkerSolixExtrasCoordinator(
        hass, entry, battery, AnkerSolixExtrasClient(unit)
    )

    async def async_source_updated(
        hass: HomeAssistant, source_entry: ConfigEntry
    ) -> None:
        """Rebind the shared unit when the source endpoint changes."""
        current = async_get_battery(hass, source_entry.entry_id)
        if current is None or current.modbus_params != battery.modbus_params:
            hass.config_entries.async_schedule_reload(entry.entry_id)
        else:
            await coordinator.async_request_refresh()

    entry.async_on_unload(battery.entry.add_update_listener(async_source_updated))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_device_updated(
        event: Event[dr.EventDeviceRegistryUpdatedData],
    ) -> None:
        """Reload Extras if its linked device was removed or changed."""
        if event.data["device_id"] == coordinator.device.id:
            await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(
        hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, async_device_updated)
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AnkerSolixExtrasConfigEntry
) -> bool:
    """Unload Extras entities without modifying the official device."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_shutdown()
    return True
