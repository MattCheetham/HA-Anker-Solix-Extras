"""Coordinate measurements and backup reserve controls."""

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
    PowerReadError,
    StateOfHealthReadError,
    TemperatureReadError,
)
from .const import CONF_OFFICIAL_ENTRY_ID, DEFAULT_SCAN_INTERVAL, DOMAIN
from .models import BackupReserve, BatteryMeasurements
from .source import OfficialBattery, async_get_battery

_LOGGER = logging.getLogger(__name__)


class AnkerSolixExtrasCoordinator(DataUpdateCoordinator[BatteryMeasurements]):
    """Poll additional registers at a modest interval."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, battery: OfficialBattery
    ) -> None:
        """Initialize the coordinator and its independently owned connection."""
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
        self._address = (battery.host, battery.port)
        self._client = AnkerSolixExtrasClient(*self._address)
        self._io_lock = Lock()
        self._stopping = False

    def _get_client(self) -> AnkerSolixExtrasClient:
        """Resolve the linked device and its current address before I/O."""
        if self._stopping:
            raise UpdateFailed("Extras is shutting down")
        battery = async_get_battery(self.hass, self.official_entry_id)
        if battery is None or battery.device.id != self.device.id:
            self._client.close()
            raise UpdateFailed("The linked official battery is unavailable")

        address = (battery.host, battery.port)
        if address != self._address:
            self._client.close()
            self._address = address
            self._client = AnkerSolixExtrasClient(*address)
        return self._client

    async def _async_update_data(self) -> BatteryMeasurements:
        """Poll without interleaving a reserve write or closing its connection."""
        async with self._io_lock:
            return await self._async_read_measurements(self._get_client())

    async def _async_read_measurements(
        self, client: AnkerSolixExtrasClient
    ) -> BatteryMeasurements:
        """Read independently available groups of battery values."""
        temperature = None
        power = None
        state_of_health = None
        backup_reserve = None
        try:
            temperature = await client.async_read_temperature()
        except TemperatureReadError as err:
            _LOGGER.debug("Temperature read failed: %s", err)
        try:
            power = await client.async_read_power()
        except PowerReadError as err:
            _LOGGER.debug("Power read failed: %s", err)
        try:
            state_of_health = await client.async_read_state_of_health()
        except StateOfHealthReadError as err:
            _LOGGER.debug("State of health read failed: %s", err)
        try:
            backup_reserve = await client.async_read_backup_reserve()
        except BackupReserveError as err:
            _LOGGER.debug("Backup reserve read failed: %s", err)
        if all(
            reading is None
            for reading in (temperature, power, state_of_health, backup_reserve)
        ):
            raise UpdateFailed("Unable to read any battery measurements")
        return BatteryMeasurements(
            temperature=temperature,
            power=power,
            state_of_health=state_of_health,
            backup_reserve=backup_reserve,
        )

    async def async_set_reserve_enabled(self, enabled: bool) -> None:
        """Turn backup reserve on or off."""
        await self._async_set_backup_reserve(enabled=enabled)

    async def async_set_reserve_percentage(self, percentage: int) -> None:
        """Set the backup reserve percentage while reserve is enabled."""
        await self._async_set_backup_reserve(percentage=percentage)

    async def _async_set_backup_reserve(
        self, *, enabled: bool | None = None, percentage: int | None = None
    ) -> None:
        """Check current capability and state, then write and confirm one setting."""
        async with self._io_lock:
            try:
                client = self._get_client()
                current = await client.async_read_backup_reserve()
                if current is None or (
                    not current.switch_supported
                    if enabled is not None
                    else current.percentage is None
                ):
                    self._publish_backup_reserve(current)
                    raise ServiceValidationError(
                        translation_domain=DOMAIN, translation_key="reserve_unavailable"
                    )
                if percentage is not None and not current.enabled:
                    self._publish_backup_reserve(current)
                    raise ServiceValidationError(
                        translation_domain=DOMAIN, translation_key="reserve_disabled"
                    )
                if enabled is not None:
                    await client.async_write_reserve_enabled(enabled)
                elif percentage is not None:
                    await client.async_write_reserve_percentage(percentage)
                updated = await client.async_read_backup_reserve()
            except UpdateFailed as err:
                self._publish_backup_reserve(None)
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="reserve_unavailable"
                ) from err
            except BackupReserveError as err:
                self._publish_backup_reserve(None)
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="reserve_write_failed"
                ) from err

            self._publish_backup_reserve(updated)
            if updated is None or (
                (not updated.switch_supported or updated.enabled != enabled)
                if enabled is not None
                else updated.percentage != percentage
            ):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="reserve_write_failed"
                )

    def _publish_backup_reserve(self, reserve: BackupReserve | None) -> None:
        """Refresh the controls without reviving stale sensor readings."""
        if self.last_update_success:
            self.async_set_updated_data(replace(self.data, backup_reserve=reserve))

    async def async_shutdown(self) -> None:
        """Stop polling and close the Extras connection."""
        self._stopping = True
        await super().async_shutdown()
        async with self._io_lock:
            self._client.close()
