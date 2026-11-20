"""Shared behavior for entities backed by individual published registers."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AnkerSolixExtrasCoordinator


class PublishedRegisterEntity(CoordinatorEntity[AnkerSolixExtrasCoordinator]):
    """Attach a published register entity to the official battery device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AnkerSolixExtrasCoordinator, address: int) -> None:
        """Bind the entity to its register without changing the device registry."""
        super().__init__(coordinator)
        self._address = address
        self._attr_unique_id = (
            f"{coordinator.official_entry_id}_{self.entity_description.key}"
        )
        self.device_entry = coordinator.device

    @property
    def available(self) -> bool:
        """Require a fresh reading for this register."""
        return super().available and self._register_value is not None

    @property
    def _register_value(self) -> int | None:
        return self.coordinator.data.published_values.get(self._address)
