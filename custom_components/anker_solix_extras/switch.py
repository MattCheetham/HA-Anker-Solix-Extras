"""Backup reserve switch for the existing official Anker device."""

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AnkerSolixExtrasConfigEntry
from .const import EXPORT_LIMIT_ENABLE_ADDRESS
from .coordinator import AnkerSolixExtrasCoordinator
from .entity import PublishedRegisterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnkerSolixExtrasConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the backup reserve switch."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = [AnkerSolixBackupReserveSwitch(coordinator)]
    if coordinator.published_registers_enabled:
        entities.append(AnkerSolixExportLimitSwitch(coordinator))
    async_add_entities(entities)


class AnkerSolixExportLimitSwitch(PublishedRegisterEntity, SwitchEntity):
    """Enable or disable the device's export limit."""

    _attr_entity_registry_enabled_default = False
    entity_description = SwitchEntityDescription(
        key="export_limit_enabled", translation_key="export_limit_enabled"
    )

    def __init__(self, coordinator: AnkerSolixExtrasCoordinator) -> None:
        """Bind to the export limit enable flag."""
        super().__init__(coordinator, EXPORT_LIMIT_ENABLE_ADDRESS)

    @property
    def is_on(self) -> bool | None:
        """Return the reported enable flag."""
        value = self._register_value
        return bool(value) if value is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the export limit."""
        await self.coordinator.async_set_export_limit_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the export limit."""
        await self.coordinator.async_set_export_limit_enabled(False)


class AnkerSolixBackupReserveSwitch(
    CoordinatorEntity[AnkerSolixExtrasCoordinator], SwitchEntity
):
    """Enable or disable the battery's backup reserve."""

    _attr_has_entity_name = True
    entity_description = SwitchEntityDescription(
        key="backup_reserve",
        translation_key="backup_reserve",
        icon="mdi:battery-lock",
    )

    def __init__(self, coordinator: AnkerSolixExtrasCoordinator) -> None:
        """Attach the switch to the existing official device."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.official_entry_id}_backup_reserve"
        self.device_entry = coordinator.device

    @property
    def available(self) -> bool:
        """Require a fresh reserve reading and switch capability."""
        return super().available and self.is_on is not None

    @property
    def is_on(self) -> bool | None:
        """Return the battery's reported reserve enable flag."""
        return self.coordinator.data.backup_reserve

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable backup reserve."""
        await self.coordinator.async_set_reserve_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable backup reserve."""
        await self.coordinator.async_set_reserve_enabled(False)
