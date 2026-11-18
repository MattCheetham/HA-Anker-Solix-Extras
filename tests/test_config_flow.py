"""Tests for selecting and validating an existing official battery."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from modbus_connection import IllegalDataAddressError

from custom_components.anker_solix_extras.const import CONF_OFFICIAL_ENTRY_ID, DOMAIN


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
    unit.read_input_registers.return_value = [250]
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
    assert result["result"].options == {CONF_SCAN_INTERVAL: interval or 60}
    connection.for_unit.assert_called_once_with(1)
    unit.read_input_registers.assert_awaited_once_with(10156, 1)
    unit.write_register.assert_not_awaited()
    connection.close.assert_awaited_once()


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
    assert result["errors"] == {"base": "cannot_read_temperature"}
    connection.close.assert_awaited_once()


async def test_forged_source_id_is_not_used(hass, official_entry) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_OFFICIAL_ENTRY_ID: "missing-entry"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "battery_unavailable"}
