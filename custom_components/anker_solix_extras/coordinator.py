"""Coordinate measurements and the backup reserve switch."""

import logging
from asyncio import Lock
from dataclasses import replace
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import (
    AnkerSolixExtrasClient,
    BackupReserveError,
    OffGridOutputPowerReadError,
    PowerReadError,
    RegisterWriteError,
    StateOfHealthReadError,
    TemperatureReadError,
)
from .const import (
    CONF_ENABLE_OFF_GRID_OUTPUT_POWER,
    CONF_OFFICIAL_ENTRY_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    RESERVE_ENABLE_ADDRESS,
    SOLARBANK_4_E5000_PRO,
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
        self.off_grid_output_power_enabled = (
            battery.device.model == SOLARBANK_4_E5000_PRO
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
            return await self._async_read_measurements(self._client)

    async def _async_read_measurements(
        self, client: AnkerSolixExtrasClient
    ) -> BatteryMeasurements:
        """Read independently available groups of battery values."""
        temperature = None
        power = None
        plant_status = None
        state_of_health = None
        off_grid_output_power = None
        backup_reserve = None
        try:
            temperature = await client.async_read_temperature()
        except TemperatureReadError as err:
            _LOGGER.debug("Temperature read failed: %s", err)
        try:
            plant_status, power = await client.async_read_status_and_power()
        except PowerReadError as err:
            _LOGGER.debug("Plant status and power read failed: %s", err)
        try:
            state_of_health = await client.async_read_state_of_health()
        except StateOfHealthReadError as err:
            _LOGGER.debug("State of health read failed: %s", err)
        if self.off_grid_output_power_enabled:
            try:
                off_grid_output_power = await client.async_read_off_grid_output_power()
            except OffGridOutputPowerReadError as err:
                _LOGGER.debug("Off-grid output power read failed: %s", err)
        try:
            backup_reserve = await client.async_read_backup_reserve()
        except BackupReserveError as err:
            _LOGGER.debug("Backup reserve read failed: %s", err)
        if all(
            reading is None
            for reading in (
                temperature,
                power,
                state_of_health,
                off_grid_output_power,
                backup_reserve,
            )
        ):
            raise UpdateFailed("Unable to read any battery measurements")
        return BatteryMeasurements(
            temperature=temperature,
            power=power,
            plant_status=plant_status,
            state_of_health=state_of_health,
            backup_reserve=backup_reserve,
            off_grid_output_power=off_grid_output_power,
        )

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
            self.async_set_updated_data(replace(self.data, backup_reserve=reserve))

    async def async_shutdown(self) -> None:
        """Drain Extras I/O before Home Assistant releases the unit."""
        if self._stopping:
            return
        self._stopping = True
        await super().async_shutdown()
        async with self._io_lock:
            pass
