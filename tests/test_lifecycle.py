"""Integration tests for shared device association and safe cleanup."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.components.modbus import async_get_unit
from homeassistant.components.modbus.connection import async_get_connection_info
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from modbus_connection import ModbusTcpParams

from custom_components.anker_solix_extras.client import (
    BackupReserveError,
    OffGridOutputPowerReadError,
    PowerReadError,
    StateOfHealthReadError,
    TemperatureReadError,
)
from custom_components.anker_solix_extras.const import DOMAIN, OFFICIAL_DOMAIN

from .ha import async_fire_time_changed


def get_temperature(hass, extras_entry):
    """Find the extra entity by its owning config entry."""
    entities = er.async_entries_for_config_entry(
        er.async_get(hass), extras_entry.entry_id
    )
    assert len(entities) == 7
    return next(
        entity
        for entity in entities
        if entity.unique_id.endswith("_battery_temperature")
    )


async def test_sensor_attaches_to_official_device(
    hass, official_entry, extras_entry, mock_client
) -> None:
    devices_before = {device.id for device in dr.async_get(hass).devices}
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()

    entity = get_temperature(hass, extras_entry)
    source_device = dr.async_get(hass).async_get_device_by_identifier(
        (OFFICIAL_DOMAIN, official_entry.entry_id), official_entry.entry_id
    )
    assert entity.platform == DOMAIN
    assert entity.device_id == source_device.id
    assert source_device.config_entry_id == official_entry.entry_id
    assert {device.id for device in dr.async_get(hass).devices} == devices_before
    state = hass.states.get(entity.entity_id)
    assert state.state == "25.0"
    assert state.name.endswith("Battery Temperature")
    assert state.attributes["unit_of_measurement"] == "°C"
    assert state.attributes["device_class"] == "temperature"
    assert state.attributes["state_class"] == "measurement"
    assert extras_entry.runtime_data.update_interval.total_seconds() == 60
    assert (
        er.async_get(hass)
        .async_get(entity.entity_id)
        .options["sensor"]["suggested_display_precision"]
        == 0
    )


async def test_unload_keeps_official_device_and_entities(
    hass, official_entry, extras_entry, mock_client
) -> None:
    registry = dr.async_get(hass)
    device = registry.async_get_device_by_identifier(
        (OFFICIAL_DOMAIN, official_entry.entry_id), official_entry.entry_id
    )
    original = er.async_get(hass).async_get_or_create(
        "sensor",
        OFFICIAL_DOMAIN,
        "official-soc",
        config_entry=official_entry,
        device_id=device.id,
        original_name="State of charge",
    )
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(extras_entry.entry_id)
    await hass.async_block_till_done()
    assert not async_get_connection_info(hass)
    assert registry.async_get(device.id) is not None
    assert er.async_get(hass).async_get(original.entity_id) == original
    assert official_entry.state is ConfigEntryState.LOADED


async def test_removing_extras_keeps_official_device(
    hass, official_entry, extras_entry, mock_client
) -> None:
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    entity = get_temperature(hass, extras_entry)
    assert await hass.config_entries.async_remove(extras_entry.entry_id)
    await hass.async_block_till_done()
    assert dr.async_get(hass).async_get(entity.device_id) is not None
    assert (
        hass.config_entries.async_get_entry(official_entry.entry_id) == official_entry
    )
    assert er.async_get(hass).async_get(entity.entity_id) is None


async def test_reload_preserves_entity_and_device(
    hass, extras_entry, mock_client
) -> None:
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    before = get_temperature(hass, extras_entry)
    assert await hass.config_entries.async_reload(extras_entry.entry_id)
    await hass.async_block_till_done()
    after = get_temperature(hass, extras_entry)
    assert (after.entity_id, after.device_id) == (before.entity_id, before.device_id)
    connections = async_get_connection_info(hass)
    assert len(connections) == 1
    assert connections[0].units == {extras_entry.entry_id: [1]}


async def test_read_failure_marks_sensor_unavailable_and_recovers(
    hass, extras_entry, mock_client
) -> None:
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    entity = get_temperature(hass, extras_entry)
    mock_client.return_value.async_read_temperature.side_effect = TemperatureReadError(
        "offline"
    )
    await extras_entry.runtime_data.async_refresh()
    assert hass.states.get(entity.entity_id).state == STATE_UNAVAILABLE
    mock_client.return_value.async_read_temperature.side_effect = None
    mock_client.return_value.async_read_temperature.return_value = 26.0
    await extras_entry.runtime_data.async_refresh()
    assert hass.states.get(entity.entity_id).state == "26.0"


async def test_setup_failure_closes_extras_connection(
    hass, extras_entry, mock_client
) -> None:
    mock_client.return_value.async_read_backup_reserve.side_effect = BackupReserveError(
        "offline"
    )
    mock_client.return_value.async_read_status_and_power.side_effect = PowerReadError(
        "offline"
    )
    mock_client.return_value.async_read_state_of_health.side_effect = (
        StateOfHealthReadError("offline")
    )
    mock_client.return_value.async_read_off_grid_output_power.side_effect = (
        OffGridOutputPowerReadError("offline")
    )
    mock_client.return_value.async_read_temperature.side_effect = TemperatureReadError(
        "offline"
    )
    assert not await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    assert extras_entry.state is ConfigEntryState.SETUP_RETRY
    assert not async_get_connection_info(hass)


async def test_address_change_reconnects_without_changing_source(
    hass, official_entry, extras_entry, mock_client, mock_connection
) -> None:
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    hass.config_entries.async_update_entry(
        official_entry, data={"ip_address": "192.0.2.20", "port": 1502}
    )
    await hass.async_block_till_done()
    mock_connection.assert_called_with(ModbusTcpParams(host="192.0.2.20", port=1502))
    connections = async_get_connection_info(hass)
    assert len(connections) == 1
    assert connections[0].endpoint == ("tcp", "192.0.2.20", 1502)
    assert connections[0].units == {extras_entry.entry_id: [1]}
    assert official_entry.data == {"ip_address": "192.0.2.20", "port": 1502}


async def test_source_removal_does_not_create_a_replacement_device(
    hass, official_entry, extras_entry, mock_client
) -> None:
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    entity = get_temperature(hass, extras_entry)
    assert await hass.config_entries.async_remove(official_entry.entry_id)
    await hass.async_block_till_done()
    assert not dr.async_get(hass).devices
    assert (
        hass.states.get(entity.entity_id) is None
        or hass.states.get(entity.entity_id).state == STATE_UNAVAILABLE
    )
    assert extras_entry.state is ConfigEntryState.SETUP_RETRY


async def test_address_change_while_source_unloaded_recovers_on_retry(
    hass, official_entry, extras_entry, mock_client, freezer
) -> None:
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    before = get_temperature(hass, extras_entry)
    assert await hass.config_entries.async_unload(official_entry.entry_id)
    hass.config_entries.async_update_entry(
        official_entry, data={"ip_address": "192.0.2.20", "port": 1502}
    )
    await hass.async_block_till_done()
    assert extras_entry.state is ConfigEntryState.SETUP_RETRY
    assert not async_get_connection_info(hass)

    assert await hass.config_entries.async_setup(official_entry.entry_id)
    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    after = get_temperature(hass, extras_entry)
    assert extras_entry.state is ConfigEntryState.LOADED
    assert (after.entity_id, after.device_id) == (before.entity_id, before.device_id)
    assert async_get_connection_info(hass)[0].endpoint == ("tcp", "192.0.2.20", 1502)


async def test_unload_failure_keeps_connection_open(
    hass, extras_entry, mock_client
) -> None:
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    with patch.object(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=False)
    ):
        assert not await hass.config_entries.async_unload(extras_entry.entry_id)
    assert async_get_connection_info(hass)[0].units == {extras_entry.entry_id: [1]}


async def test_unload_keeps_other_consumer_on_shared_connection(
    hass, extras_entry, official_entry, mock_client, mock_connection
) -> None:
    params = ModbusTcpParams(host="192.0.2.10", port=502)
    peer_unit = async_get_unit(hass, official_entry, params, 1)
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    mock_client.assert_called_once_with(peer_unit)
    mock_connection.assert_called_once_with(params)
    connections = async_get_connection_info(hass)
    assert len(connections) == 1
    assert connections[0].units == {
        extras_entry.entry_id: [1],
        official_entry.entry_id: [1],
    }

    assert await hass.config_entries.async_unload(extras_entry.entry_id)
    assert async_get_connection_info(hass)[0].units == {official_entry.entry_id: [1]}
    mock_connection.return_value.close.assert_not_awaited()

    assert await hass.config_entries.async_unload(official_entry.entry_id)
    assert not async_get_connection_info(hass)
    mock_connection.return_value.close.assert_awaited_once()


async def test_official_unload_stops_reads_and_recovers_after_setup(
    hass, official_entry, extras_entry, mock_client
) -> None:
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    entity = get_temperature(hass, extras_entry)
    assert await hass.config_entries.async_unload(official_entry.entry_id)
    mock_client.return_value.async_read_temperature.reset_mock()

    await extras_entry.runtime_data.async_refresh()
    mock_client.return_value.async_read_temperature.assert_not_awaited()
    assert hass.states.get(entity.entity_id).state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_setup(official_entry.entry_id)
    await extras_entry.runtime_data.async_refresh()
    assert hass.states.get(entity.entity_id).state == "25.0"


async def test_missing_official_entry_defers_setup_without_connecting(
    hass, extras_entry, official_entry, mock_client
) -> None:
    assert await hass.config_entries.async_remove(official_entry.entry_id)
    assert not await hass.config_entries.async_setup(extras_entry.entry_id)
    assert extras_entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.assert_not_called()
