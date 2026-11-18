"""Additional sensors attached to an existing official Anker device."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AnkerSolixExtrasConfigEntry
from .coordinator import AnkerSolixExtrasCoordinator

BATTERY_TEMPERATURE = SensorEntityDescription(
    key="battery_temperature",
    translation_key="battery_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    suggested_display_precision=0,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnkerSolixExtrasConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add only the extra temperature entity."""
    async_add_entities([AnkerSolixBatteryTemperature(entry.runtime_data)])


class AnkerSolixBatteryTemperature(
    CoordinatorEntity[AnkerSolixExtrasCoordinator], SensorEntity
):
    """A read-only temperature entity owned by Extras on the official device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AnkerSolixExtrasCoordinator) -> None:
        """Attach the existing device directly, without registering another one."""
        super().__init__(coordinator)
        self.entity_description = BATTERY_TEMPERATURE
        self._attr_unique_id = f"{coordinator.official_entry_id}_battery_temperature"
        # An empty device_info preserves this device entry in HA's entity platform.
        self.device_entry = coordinator.device

    @property
    def native_value(self) -> float | None:
        """Return the scaled measurement; failed updates mark it unavailable."""
        return self.coordinator.data if self.coordinator.last_update_success else None
