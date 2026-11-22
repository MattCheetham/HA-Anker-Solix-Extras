"""Coordinate measurements and battery controls."""

import logging
from asyncio import Lock
from dataclasses import replace
from datetime import timedelta
from time import monotonic, time

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import (
    AnkerSolixExtrasClient,
    BackupReserveError,
    RegisterReadError,
    RegisterWriteError,
)
from .const import (
    CONF_ENABLE_OFF_GRID_OUTPUT_POWER,
    CONF_ENABLE_PUBLISHED_REGISTERS,
    CONF_OFFICIAL_ENTRY_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EXPORT_LIMIT_ADDRESS,
    EXPORT_LIMIT_ENABLE_ADDRESS,
    MAX_EXPORT_LIMIT,
    RESERVE_ENABLE_ADDRESS,
    SYSTEM_TIME_ADDRESS,
)
from .measurements import (
    PUBLISHED_SETTINGS,
    async_read_measurements,
    async_read_published_setting,
    published_input_registers,
)
from .models import BatteryMeasurements
from .source import OfficialBattery, async_get_battery

_LOGGER = logging.getLogger(__name__)


class AnkerSolixExtrasCoordinator(DataUpdateCoordinator[BatteryMeasurements]):
    """Poll additional registers at a modest interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        battery: OfficialBattery,
        client: AnkerSolixExtrasClient,
    ) -> None:
        """Initialize the coordinator for the entry's registered Modbus unit."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
            always_update=False,
        )
        self.official_entry_id: str = entry.data[CONF_OFFICIAL_ENTRY_ID]
        self.device = battery.device
        self.published_registers_enabled = (
            battery.supports_published_registers
            or entry.options.get(CONF_ENABLE_PUBLISHED_REGISTERS, False)
        )
        self.pcs_count_addresses = battery.pcs_count_addresses
        self._published_inputs = (
            published_input_registers(self.pcs_count_addresses)
            if self.published_registers_enabled
            else None
        )
        self.off_grid_output_power_enabled = (
            battery.enables_off_grid_output_by_default
            or entry.options.get(CONF_ENABLE_OFF_GRID_OUTPUT_POWER, False)
        )
        self._params = battery.modbus_params
        self._client = client
        self._io_lock = Lock()
        self._stopping = False

    def _check_linked_battery(self) -> None:
        """Ensure the linked battery still matches the registered Modbus unit."""
        if self._stopping:
            raise UpdateFailed("Extras is shutting down")
        battery = async_get_battery(self.hass, self.official_entry_id)
        if (
            battery is None
            or battery.device.id != self.device.id
            or battery.modbus_params != self._params
        ):
            raise UpdateFailed("The linked official battery is unavailable")

    async def _async_update_data(self) -> BatteryMeasurements:
        """Poll without interleaving a control operation."""
        async with self._io_lock:
            self._check_linked_battery()
            return await async_read_measurements(
                self._client,
                off_grid_output_power_enabled=self.off_grid_output_power_enabled,
                published_inputs=self._published_inputs,
                # Entities subscribe only after the first refresh.
                published_addresses=(
                    None if self.data is None else set(self.async_contexts())
                ),
            )

    async def async_set_export_limit_enabled(self, enabled: bool) -> None:
        """Set the export limit flag on the linked battery."""
        await self._async_set_published_setting(
            EXPORT_LIMIT_ENABLE_ADDRESS, int(enabled)
        )

    async def async_set_export_limit(self, watts: float) -> None:
        """Set the export limit in whole watts."""
        if not 0 <= watts <= MAX_EXPORT_LIMIT or watts != int(watts):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_export_limit"
            )
        await self._async_set_published_setting(EXPORT_LIMIT_ADDRESS, int(watts))

    async def async_sync_system_time(self) -> None:
        """Set the battery clock to the current Home Assistant time on request."""
        await self._async_set_published_setting(SYSTEM_TIME_ADDRESS)

    async def _async_set_published_setting(
        self, address: int, value: int | None = None
    ) -> None:
        """Check model and fresh state, then serialize the write and readback."""
        async with self._io_lock:
            try:
                self._check_linked_battery()
                if not self.published_registers_enabled:
                    raise RegisterReadError("Published registers are disabled")
                await async_read_published_setting(self._client, address)
                self._check_linked_battery()
            except (UpdateFailed, RegisterReadError) as err:
                self._publish_setting(address, None)
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="setting_unavailable"
                ) from err

            syncing_clock = address == SYSTEM_TIME_ADDRESS
            if syncing_clock:
                value = int(time())
            assert value is not None
            started = monotonic()
            try:
                if PUBLISHED_SETTINGS[address][0] == 1:
                    await self._client.async_write_register(address, value)
                else:
                    await self._client.async_write_registers(
                        address, [value >> 16, value & 0xFFFF]
                    )
                updated = await async_read_published_setting(self._client, address)
            except (RegisterReadError, RegisterWriteError) as err:
                self._publish_setting(address, None)
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="setting_write_failed"
                ) from err

            self._publish_setting(address, updated)
            tolerance = int(monotonic() - started) + 1 if syncing_clock else 0
            if not value <= updated <= value + tolerance:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="setting_write_failed"
                )

    def _publish_setting(self, address: int, value: int | None) -> None:
        """Publish confirmed settings without reviving stale measurements."""
        if self.last_update_success:
            values = self.data.published_values.copy()
            if value is None:
                values.pop(address, None)
            else:
                values[address] = value
            self._publish_control_update(replace(self.data, published_values=values))

    async def async_set_reserve_enabled(self, enabled: bool) -> None:
        """Check the switch capability and state, then write and confirm."""
        async with self._io_lock:
            try:
                self._check_linked_battery()
                client = self._client
                if await client.async_read_backup_reserve() is None:
                    self._publish_backup_reserve(None)
                    raise ServiceValidationError(
                        translation_domain=DOMAIN, translation_key="reserve_unavailable"
                    )
                self._check_linked_battery()
                await client.async_write_register(RESERVE_ENABLE_ADDRESS, int(enabled))
                updated = await client.async_read_backup_reserve()
            except UpdateFailed as err:
                self._publish_backup_reserve(None)
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="reserve_unavailable"
                ) from err
            except (BackupReserveError, RegisterWriteError) as err:
                self._publish_backup_reserve(None)
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="reserve_write_failed"
                ) from err

            self._publish_backup_reserve(updated)
            if updated != enabled:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="reserve_write_failed"
                )

    def _publish_backup_reserve(self, reserve: bool | None) -> None:
        """Refresh the switch without reviving stale sensor readings."""
        if self.last_update_success:
            self._publish_control_update(replace(self.data, backup_reserve=reserve))

    def _publish_control_update(self, data: BatteryMeasurements) -> None:
        """Notify entities of a changed readback while keeping the poll scheduled."""
        if data != self.data:
            self.data = data
            self.async_update_listeners()

    async def async_shutdown(self) -> None:
        """Drain Extras I/O before Home Assistant releases the unit."""
        if self._stopping:
            return
        self._stopping = True
        await super().async_shutdown()
        async with self._io_lock:
            pass
