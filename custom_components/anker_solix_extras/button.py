"""Explicit battery clock synchronization for Anker SOLIX Extras."""

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnkerSolixExtrasConfigEntry
from .const import SYSTEM_TIME_ADDRESS
from .coordinator import AnkerSolixExtrasCoordinator
from .entity import PublishedRegisterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnkerSolixExtrasConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the clock sync button for models in the protocol document."""
    if entry.runtime_data.published_registers_enabled:
        async_add_entities([AnkerSolixSyncSystemTime(entry.runtime_data)])


class AnkerSolixSyncSystemTime(PublishedRegisterEntity, ButtonEntity):
    """Synchronize the battery clock on demand."""

    _attr_entity_registry_enabled_default = False
    entity_description = ButtonEntityDescription(
        key="sync_system_time",
        translation_key="sync_system_time",
        icon="mdi:clock-check",
    )

    def __init__(self, coordinator: AnkerSolixExtrasCoordinator) -> None:
        """Bind to the battery clock."""
        super().__init__(coordinator, SYSTEM_TIME_ADDRESS)

    async def async_press(self) -> None:
        """Write Home Assistant's current time to the battery."""
        await self.coordinator.async_sync_system_time()
