"""Anker SOLIX Extras: additional entities for the official integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONF_OFFICIAL_ENTRY_ID
from .coordinator import AnkerSolixExtrasCoordinator
from .source import async_get_battery

type AnkerSolixExtrasConfigEntry = ConfigEntry[AnkerSolixExtrasCoordinator]

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: AnkerSolixExtrasConfigEntry
) -> bool:
    """Set up Extras for an existing official battery."""
    battery = async_get_battery(hass, entry.data[CONF_OFFICIAL_ENTRY_ID])
    if battery is None:
        raise ConfigEntryNotReady("The linked official battery is not ready")

    coordinator = AnkerSolixExtrasCoordinator(hass, entry, battery)
    entry.async_on_unload(coordinator.async_shutdown)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_source_updated(
        hass: HomeAssistant, source_entry: ConfigEntry
    ) -> None:
        """Refresh after source configuration changes; do not reload the source."""
        await coordinator.async_request_refresh()

    async def async_device_updated(
        event: Event[dr.EventDeviceRegistryUpdatedData],
    ) -> None:
        """Reload Extras if its linked device was removed or changed."""
        if event.data["device_id"] == coordinator.device.id:
            await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(battery.entry.add_update_listener(async_source_updated))
    entry.async_on_unload(
        hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, async_device_updated)
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AnkerSolixExtrasConfigEntry
) -> bool:
    """Unload Extras entities without modifying the official device."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
