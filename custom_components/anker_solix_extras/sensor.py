"""Additional sensors attached to an existing official Anker device."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower, UnitOfTemperature
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

BATTERY_HEATING_POWER = SensorEntityDescription(
    key="battery_heating_power",
    translation_key="battery_heating_power",
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfPower.WATT,
    suggested_display_precision=0,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnkerSolixExtrasConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add additional measurement entities."""
    async_add_entities(
        [
            AnkerSolixBatteryTemperature(entry.runtime_data),
            AnkerSolixBatteryHeatingPower(entry.runtime_data),
        ]
    )


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
    def available(self) -> bool:
        """Keep temperature available independently of the power reading."""
        return super().available and self.coordinator.data.temperature is not None

    @property
    def native_value(self) -> float | None:
        """Return the scaled measurement; failed updates mark it unavailable."""
        return self.coordinator.data.temperature if self.available else None


class AnkerSolixBatteryHeatingPower(
    CoordinatorEntity[AnkerSolixExtrasCoordinator], SensorEntity
):
    """Estimated heating power while the battery absorbs AC power."""

    _attr_has_entity_name = True
    entity_description = BATTERY_HEATING_POWER

    def __init__(self, coordinator: AnkerSolixExtrasCoordinator) -> None:
        """Attach to the official device without modifying it."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.official_entry_id}_battery_heating_power"
        self.device_entry = coordinator.device

    @property
    def available(self) -> bool:
        """Require fresh power readings, independently of temperature."""
        return super().available and self.coordinator.data.power is not None

    @property
    def native_value(self) -> int | None:
        """Return the nonnegative estimate, never a substitute for a failed read."""
        if self.available:
            return self.coordinator.data.power.heating_power
        return None

    @property
    def extra_state_attributes(self) -> dict[str, int] | None:
        """Expose the signed source readings used for the estimate."""
        if self.available:
            power = self.coordinator.data.power
            return {"ac_power": power.ac_power, "battery_power": power.battery_power}
        return None
