"""Tests for selecting and validating an existing official battery."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_SCAN_INTERVAL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from modbus_connection import IllegalDataAddressError

from custom_components.anker_solix_extras.const import (
    CONF_OFFICIAL_ENTRY_ID,
    DOMAIN,
    SOLARBANK_4_E5000_PRO,
)


async def test_no_official_batteries(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_official_batteries"


@pytest.mark.parametrize("interval", [None, 1, 15, 120, 86400])
async def test_choose_official_battery(
    hass, official_entry, interval, mock_connection
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    connection = mock_connection.return_value
    unit = connection.for_unit.return_value
    unit.read_input_registers.side_effect = lambda address, count: (
        [250] if address == 10156 else [0] * count
    )
    with patch(
        "custom_components.anker_solix_extras.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        user_input = {CONF_OFFICIAL_ENTRY_ID: official_entry.entry_id}
        if interval is not None:
            user_input[CONF_SCAN_INTERVAL] = interval
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == official_entry.title
    assert result["data"] == {CONF_OFFICIAL_ENTRY_ID: official_entry.entry_id}
    assert result["result"].unique_id == official_entry.entry_id
    assert result["result"].options == {CONF_SCAN_INTERVAL: interval or 10}
    connection.for_unit.assert_called_once_with(1)
    unit.read_input_registers.assert_any_await(10156, 1)
    unit.write_register.assert_not_awaited()
    unit.write_registers.assert_not_awaited()
    connection.close.assert_awaited_once()


@pytest.mark.parametrize(
    ("model", "address", "words", "sensor", "value"),
    [
        (SOLARBANK_4_E5000_PRO, 10015, [0], "battery_state_of_health", "0"),
        (
            "Anker SOLIX Solarbank Max AC",
            10022,
            [0, 42],
            "total_battery_charge_energy",
            "4.2",
        ),
    ],
)
async def test_setup_can_use_a_measurement_other_than_temperature(
    hass, official_entry, mock_connection, model, address, words, sensor, value
) -> None:
    """Apply the same partial-read rule when adding and loading the entry."""
    devices = dr.async_get(hass)
    device = next(iter(devices.devices))
    devices.async_update_device(device.id, model=model)
    unit = mock_connection.return_value.for_unit.return_value

    async def read_input_registers(requested_address, count):
        if requested_address != address:
            raise IllegalDataAddressError("not supported")
        assert count == len(words)
        return words

    unit.read_input_registers.side_effect = read_input_registers
    unit.read_holding_registers.side_effect = IllegalDataAddressError("not supported")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_OFFICIAL_ENTRY_ID: official_entry.entry_id},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    temperature_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{official_entry.entry_id}_battery_temperature"
    )
    sensor_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{official_entry.entry_id}_{sensor}"
    )
    assert hass.states.get(temperature_id).state == STATE_UNAVAILABLE
    assert hass.states.get(sensor_id).state == value
    unit.write_register.assert_not_awaited()
    unit.write_registers.assert_not_awaited()


async def test_duplicate_battery(hass, official_entry, extras_entry) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_OFFICIAL_ENTRY_ID: official_entry.entry_id},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_read_failure_keeps_form_open(
    hass, official_entry, mock_connection
) -> None:
    connection = mock_connection.return_value
    unit = connection.for_unit.return_value
    unit.read_input_registers.side_effect = IllegalDataAddressError("not supported")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_OFFICIAL_ENTRY_ID: official_entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_read_measurements"}
    connection.close.assert_awaited_once()


async def test_forged_source_id_is_not_used(hass, official_entry) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_OFFICIAL_ENTRY_ID: "missing-entry"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "battery_unavailable"}
