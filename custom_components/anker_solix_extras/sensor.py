"""Additional sensors attached to an existing official Anker device."""

from datetime import UTC, datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AnkerSolixExtrasConfigEntry
from .const import (
    ENERGY_ADDRESSES,
    PCS_COUNT_ADDRESSES,
    PLANT_STATUS_STATES,
    SYSTEM_TIME_ADDRESS,
)
from .coordinator import AnkerSolixExtrasCoordinator
from .entity import PublishedRegisterEntity

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

BATTERY_STATE_OF_HEALTH = SensorEntityDescription(
    key="battery_state_of_health",
    translation_key="battery_state_of_health",
    icon="mdi:battery-heart",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,
    suggested_display_precision=0,
)


OFF_GRID_OUTPUT_POWER = SensorEntityDescription(
    key="off_grid_output_power",
    translation_key="off_grid_output_power",
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfPower.WATT,
    suggested_display_precision=0,
)


PLANT_STATUS = SensorEntityDescription(
    key="plant_status",
    translation_key="plant_status",
    device_class=SensorDeviceClass.ENUM,
    options=list(PLANT_STATUS_STATES.values()),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnkerSolixExtrasConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add additional measurement entities."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        AnkerSolixBatteryTemperature(coordinator),
        AnkerSolixBatteryHeatingPower(coordinator),
        AnkerSolixBatteryStateOfHealth(coordinator),
        AnkerSolixPlantStatus(coordinator),
    ]
    if coordinator.off_grid_output_power_enabled:
        entities.append(AnkerSolixOffGridOutputPower(coordinator))
    if coordinator.published_registers_enabled:
        entities.extend(
            AnkerSolixPublishedSensor(coordinator, key, address)
            for key, address in (ENERGY_ADDRESSES | PCS_COUNT_ADDRESSES).items()
        )
        entities.append(
            AnkerSolixPublishedSensor(coordinator, "system_time", SYSTEM_TIME_ADDRESS)
        )
    async_add_entities(entities)


class AnkerSolixPublishedSensor(PublishedRegisterEntity, SensorEntity):
    """Expose a published energy counter, PCS count, or timestamp."""

    def __init__(
        self, coordinator: AnkerSolixExtrasCoordinator, key: str, address: int
    ) -> None:
        """Assign sensor metadata based on the register's measurement."""
        if key in ENERGY_ADDRESSES:
            self.entity_description = SensorEntityDescription(
                key=key,
                translation_key=key,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                state_class=SensorStateClass.TOTAL_INCREASING,
                suggested_display_precision=1,
            )
        else:
            self.entity_description = SensorEntityDescription(
                key=key,
                translation_key=key,
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_registry_enabled_default=False,
                device_class=(
                    SensorDeviceClass.TIMESTAMP
                    if address == SYSTEM_TIME_ADDRESS
                    else None
                ),
            )
        super().__init__(coordinator, address)

    @property
    def native_value(self) -> datetime | float | int | None:
        """Convert the raw register value to the sensor's native representation."""
        value = self._register_value if self.available else None
        if value is None:
            return None
        if self._address == SYSTEM_TIME_ADDRESS:
            return datetime.fromtimestamp(value, UTC)
        if self.entity_description.key in ENERGY_ADDRESSES:
            return value / 10
        return value


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


class AnkerSolixBatteryStateOfHealth(
    CoordinatorEntity[AnkerSolixExtrasCoordinator], SensorEntity
):
    """Report the combined state of health of the battery system."""

    _attr_has_entity_name = True
    entity_description = BATTERY_STATE_OF_HEALTH

    def __init__(self, coordinator: AnkerSolixExtrasCoordinator) -> None:
        """Attach to the existing official device."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.official_entry_id}_battery_state_of_health"
        )
        self.device_entry = coordinator.device

    @property
    def available(self) -> bool:
        """Require a fresh state of health reading."""
        return super().available and self.coordinator.data.state_of_health is not None

    @property
    def native_value(self) -> int | None:
        """Return the percentage reported by the battery system."""
        return self.coordinator.data.state_of_health if self.available else None


class AnkerSolixPlantStatus(
    CoordinatorEntity[AnkerSolixExtrasCoordinator], SensorEntity
):
    """Display the operating status reported by the plant."""

    _attr_has_entity_name = True
    entity_description = PLANT_STATUS

    def __init__(self, coordinator: AnkerSolixExtrasCoordinator) -> None:
        """Attach to the existing official device."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.official_entry_id}_plant_status"
        self.device_entry = coordinator.device

    @property
    def available(self) -> bool:
        """Require a recognized status from the current update."""
        return super().available and self.coordinator.data.plant_status is not None

    @property
    def native_value(self) -> str | None:
        """Return the current operating status."""
        return self.coordinator.data.plant_status if self.available else None


class AnkerSolixOffGridOutputPower(
    CoordinatorEntity[AnkerSolixExtrasCoordinator], SensorEntity
):
    """Expose the experimental output reading on the official battery device."""

    _attr_has_entity_name = True
    entity_description = OFF_GRID_OUTPUT_POWER

    def __init__(self, coordinator: AnkerSolixExtrasCoordinator) -> None:
        """Attach to the existing official device."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.official_entry_id}_off_grid_output_power"
        self.device_entry = coordinator.device

    @property
    def available(self) -> bool:
        """Require a fresh off-grid output reading."""
        return (
            super().available
            and self.coordinator.data.off_grid_output_power is not None
        )

    @property
    def native_value(self) -> int | None:
        """Return the reported active power in watts."""
        return self.coordinator.data.off_grid_output_power if self.available else None
