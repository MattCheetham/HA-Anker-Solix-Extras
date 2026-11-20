"""Export power limit setpoint for Anker SOLIX Extras."""

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnkerSolixExtrasConfigEntry
from .const import EXPORT_LIMIT_ADDRESS, MAX_EXPORT_LIMIT
from .coordinator import AnkerSolixExtrasCoordinator
from .entity import PublishedRegisterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnkerSolixExtrasConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the export power setpoint for models in the protocol document."""
    if entry.runtime_data.published_registers_enabled:
        async_add_entities([AnkerSolixExportLimit(entry.runtime_data)])


class AnkerSolixExportLimit(PublishedRegisterEntity, NumberEntity):
    """Read and set the export limit in whole watts."""

    _attr_entity_registry_enabled_default = False
    entity_description = NumberEntityDescription(
        key="export_limit",
        translation_key="export_limit",
        device_class=NumberDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=MAX_EXPORT_LIMIT,
        native_step=1,
        mode=NumberMode.BOX,
    )

    def __init__(self, coordinator: AnkerSolixExtrasCoordinator) -> None:
        """Bind to the export limit setpoint."""
        super().__init__(coordinator, EXPORT_LIMIT_ADDRESS)

    @property
    def native_value(self) -> int | None:
        """Return the reported setpoint."""
        return self._register_value

    async def async_set_native_value(self, value: float) -> None:
        """Set the export limit."""
        await self.coordinator.async_set_export_limit(value)
