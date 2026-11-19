"""Tests for configurable Modbus polling and safe application of options."""

from datetime import timedelta
from unittest.mock import call

import pytest
import voluptuous as vol
from homeassistant.const import CONF_SCAN_INTERVAL, STATE_UNAVAILABLE
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from modbus_connection import IllegalDataAddressError

from custom_components.anker_solix_extras.const import (
    CONF_ENABLE_OFF_GRID_OUTPUT_POWER,
    CONF_OFFICIAL_ENTRY_ID,
    DOMAIN,
)

from .ha import async_fire_time_changed


@pytest.mark.parametrize("interval", [None, 1, 15, 120, 86400])
async def test_options_show_saved_interval(hass, extras_entry, interval) -> None:
    """Existing entries default to 60; configured entries show their saved value."""
    if interval is not None:
        hass.config_entries.async_update_entry(
            extras_entry, options={CONF_SCAN_INTERVAL: interval}
        )
    result = await hass.config_entries.options.async_init(extras_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {CONF_SCAN_INTERVAL: interval or 60}


@pytest.mark.parametrize("invalid", [0, -1, "abc", None, 1.5])
@pytest.mark.parametrize("flow_type", ["setup", "options"])
async def test_invalid_interval_rejected(
    hass, official_entry, extras_entry, invalid, flow_type
) -> None:
    """Do not persist invalid intervals or try connecting for invalid setup data."""
    if flow_type == "options":
        result = await hass.config_entries.options.async_init(extras_entry.entry_id)
    else:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    with pytest.raises(vol.Invalid):
        result["data_schema"](
            {
                CONF_SCAN_INTERVAL: invalid,
                **(
                    {CONF_OFFICIAL_ENTRY_ID: official_entry.entry_id}
                    if flow_type == "setup"
                    else {}
                ),
            }
        )
    assert extras_entry.options == {}


async def test_options_reload_extras_and_preserve_entities(
    hass, official_entry, extras_entry, mock_client, mock_connection, freezer
) -> None:
    """Changing the interval renews Extras' registration and polling timer."""
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    before = {
        entry.unique_id: (entry.entity_id, entry.device_id)
        for entry in er.async_entries_for_config_entry(
            er.async_get(hass), extras_entry.entry_id
        )
    }
    old_coordinator = extras_entry.runtime_data
    assert old_coordinator.update_interval == timedelta(seconds=60)
    source_data = dict(official_entry.data)

    result = await hass.config_entries.options.async_init(extras_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 15}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert extras_entry.options == {CONF_SCAN_INTERVAL: 15}
    assert extras_entry.runtime_data is not old_coordinator
    assert extras_entry.runtime_data.update_interval == timedelta(seconds=15)
    assert official_entry.data == source_data
    assert {
        entry.unique_id: (entry.entity_id, entry.device_id)
        for entry in er.async_entries_for_config_entry(
            er.async_get(hass), extras_entry.entry_id
        )
    } == before
    mock_connection.return_value.close.assert_awaited_once()

    # Observe the new timer twice, before the old 60-second timer could fire.
    client = mock_client.return_value
    client.async_read_temperature.reset_mock()
    client.async_read_status_and_power.reset_mock()
    for expected in (1, 2):
        freezer.tick(timedelta(seconds=16))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert client.async_read_temperature.await_count == expected
        assert client.async_read_status_and_power.await_count == expected


async def test_options_preserve_other_settings(hass, extras_entry, mock_client) -> None:
    """A polling change must not discard unrelated entry options."""
    hass.config_entries.async_update_entry(
        extras_entry, options={"other_setting": True}
    )
    result = await hass.config_entries.options.async_init(extras_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 120}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert extras_entry.options == {"other_setting": True, CONF_SCAN_INTERVAL: 120}


async def test_options_enable_and_disable_off_grid_power_on_another_model(
    hass, official_entry, extras_entry, mock_connection
) -> None:
    """Opt in by config entry, isolate unsupported reads, and stop polling on opt-out."""
    registry = dr.async_get(hass)
    device = next(iter(registry.devices))
    registry.async_update_device(device.id, model="Anker SOLIX Solarbank Max AC")
    unit = mock_connection.return_value.for_unit.return_value
    rejects_off_grid_read = True

    async def read_input_registers(address, count):
        if address == 10233:
            assert count == 2
            if rejects_off_grid_read:
                raise IllegalDataAddressError("not supported")
            return [0, 23]
        return {10000: [0] * 10, 10015: [100], 10156: [250], 32775: [0]}[address]

    unit.read_input_registers.side_effect = read_input_registers
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    entity_registry = er.async_get(hass)
    unique_id = f"{official_entry.entry_id}_off_grid_output_power"
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id) is None
    assert call(10233, 2) not in unit.read_input_registers.await_args_list

    result = await hass.config_entries.options.async_init(extras_entry.entry_id)
    assert result["data_schema"]({})[CONF_ENABLE_OFF_GRID_OUTPUT_POWER] is False
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SCAN_INTERVAL: 60, CONF_ENABLE_OFF_GRID_OUTPUT_POWER: True},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    unit.read_input_registers.assert_any_await(10233, 2)
    power_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_registry.async_get(power_id).device_id == device.id
    assert hass.states.get(power_id).state == STATE_UNAVAILABLE
    temperature_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{official_entry.entry_id}_battery_temperature"
    )
    assert hass.states.get(temperature_id).state == "25.0"

    rejects_off_grid_read = False
    await extras_entry.runtime_data.async_refresh()
    assert hass.states.get(power_id).state == "23"

    unit.read_input_registers.reset_mock()
    result = await hass.config_entries.options.async_init(extras_entry.entry_id)
    assert result["data_schema"]({})[CONF_ENABLE_OFF_GRID_OUTPUT_POWER] is True
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SCAN_INTERVAL: 60, CONF_ENABLE_OFF_GRID_OUTPUT_POWER: False},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert extras_entry.options[CONF_ENABLE_OFF_GRID_OUTPUT_POWER] is False
    assert call(10233, 2) not in unit.read_input_registers.await_args_list
    state = hass.states.get(power_id)
    assert state is None or state.state == STATE_UNAVAILABLE
    assert hass.states.get(temperature_id).state == "25.0"
    unit.write_register.assert_not_awaited()
    unit.write_registers.assert_not_awaited()
