"""Tests for the experimental off-grid output power sensor."""

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from modbus_connection import ModbusTimeoutError


async def test_off_grid_output_power_states(
    hass, extras_entry, mock_connection
) -> None:
    """Display raw FC04 samples and recover independently from invalid reads."""
    unit = mock_connection.return_value.for_unit.return_value
    reading = []

    async def read_input_registers(address, count):
        if address == 10230:
            assert count == 1
            if reading is None:
                raise ModbusTimeoutError("timeout")
            return reading
        return {
            10000: [1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            10015: [100],
            10156: [250],
            32775: [0],
        }[address]

    unit.read_input_registers.side_effect = read_input_registers
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    prefix = extras_entry.data["official_entry_id"]
    power_id = registry.async_get_entity_id(
        "sensor", extras_entry.domain, f"{prefix}_off_grid_output_power"
    )
    temperature_id = registry.async_get_entity_id(
        "sensor", extras_entry.domain, f"{prefix}_battery_temperature"
    )
    assert hass.states.get(power_id).state == STATE_UNAVAILABLE

    for sample, expected in [
        ([22], "22"),
        ([8], "8"),
        ([0], "0"),
        ([], STATE_UNAVAILABLE),
        (None, STATE_UNAVAILABLE),
        ([20], "20"),
    ]:
        reading = sample
        await extras_entry.runtime_data.async_refresh()
        assert hass.states.get(power_id).state == expected
        assert hass.states.get(temperature_id).state == "25.0"

    state = hass.states.get(power_id)
    assert state.name.endswith("Off-Grid Output Power")
    assert state.attributes["unit_of_measurement"] == "W"
    assert state.attributes["device_class"] == "power"
    assert state.attributes["state_class"] == "measurement"
    assert (
        registry.async_get(power_id).options["sensor"]["suggested_display_precision"]
        == 0
    )
    unit.read_holding_registers.assert_not_awaited()
    unit.write_register.assert_not_awaited()
    unit.write_registers.assert_not_awaited()
