"""Heating activity attached to an existing official Anker device."""

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AnkerSolixExtrasConfigEntry
from .coordinator import AnkerSolixExtrasCoordinator

BATTERY_HEATING_ACTIVE = BinarySensorEntityDescription(
    key="battery_heating_active",
    translation_key="battery_heating_active",
    icon="mdi:radiator",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnkerSolixExtrasConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the estimated heating activity entity."""
    async_add_entities([AnkerSolixBatteryHeatingActive(entry.runtime_data)])


class AnkerSolixBatteryHeatingActive(
    CoordinatorEntity[AnkerSolixExtrasCoordinator], BinarySensorEntity
):
    """Indicate whether the heating power estimate is greater than zero."""

    _attr_has_entity_name = True
    entity_description = BATTERY_HEATING_ACTIVE

    def __init__(self, coordinator: AnkerSolixExtrasCoordinator) -> None:
        """Attach to the official device without modifying it."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.official_entry_id}_battery_heating_active"
        self.device_entry = coordinator.device

    @property
    def available(self) -> bool:
        """Unknown power must not be reported as inactive heating."""
        return super().available and self.coordinator.data.power is not None

    @property
    def is_on(self) -> bool | None:
        """Use the same fresh estimate as the heating power sensor."""
        if self.available:
            return self.coordinator.data.power.heating_power > 0
        return None
