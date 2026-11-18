"""Backup reserve percentage for the existing official Anker device."""

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AnkerSolixExtrasConfigEntry
from .const import DOMAIN
from .coordinator import AnkerSolixExtrasCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnkerSolixExtrasConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the backup reserve percentage input."""
    async_add_entities([AnkerSolixBackupReservePercentage(entry.runtime_data)])


class AnkerSolixBackupReservePercentage(
    CoordinatorEntity[AnkerSolixExtrasCoordinator], NumberEntity
):
    """Set the battery's backup reserve in whole percentages."""

    _attr_has_entity_name = True
    entity_description = NumberEntityDescription(
        key="backup_reserve_soc",
        translation_key="backup_reserve_soc",
        icon="mdi:battery-lock",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.BOX,
    )

    def __init__(self, coordinator: AnkerSolixExtrasCoordinator) -> None:
        """Attach the number to the existing official device."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.official_entry_id}_backup_reserve_soc"
        self.device_entry = coordinator.device

    @property
    def available(self) -> bool:
        """Require a fresh reserve percentage even when reserve is off."""
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> int | None:
        """Return the battery's stored reserve percentage."""
        reserve = self.coordinator.data.backup_reserve
        return reserve.percentage if reserve is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Set a whole percentage after validating the service input."""
        if not 0 <= value <= 100 or value != int(value):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="reserve_invalid_percentage"
            )
        await self.coordinator.async_set_reserve_percentage(int(value))
