"""Tests for selecting and validating an existing official battery."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.anker_solix_extras.client import TemperatureReadError
from custom_components.anker_solix_extras.const import CONF_OFFICIAL_ENTRY_ID, DOMAIN


async def test_no_official_batteries(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_official_batteries"


async def test_choose_official_battery(hass, official_entry) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with (
        patch(
            "custom_components.anker_solix_extras.config_flow.AnkerSolixExtrasClient",
            autospec=True,
        ) as factory,
        patch(
            "custom_components.anker_solix_extras.async_setup_entry",
            AsyncMock(return_value=True),
        ),
    ):
        factory.return_value.async_read_temperature = AsyncMock(return_value=25.0)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OFFICIAL_ENTRY_ID: official_entry.entry_id}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == official_entry.title
    assert result["data"] == {CONF_OFFICIAL_ENTRY_ID: official_entry.entry_id}
    assert result["result"].unique_id == official_entry.entry_id
    factory.assert_called_once_with("192.0.2.10", 502)
    factory.return_value.close.assert_called_once()


async def test_duplicate_battery(hass, official_entry, extras_entry) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_OFFICIAL_ENTRY_ID: official_entry.entry_id},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_read_failure_keeps_form_open(hass, official_entry) -> None:
    with patch(
        "custom_components.anker_solix_extras.config_flow.AnkerSolixExtrasClient",
        autospec=True,
    ) as factory:
        factory.return_value.async_read_temperature = AsyncMock(
            side_effect=TemperatureReadError("not implemented")
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_OFFICIAL_ENTRY_ID: official_entry.entry_id},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_read_temperature"}
    factory.return_value.close.assert_called_once()


async def test_forged_source_id_is_not_used(hass, official_entry) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_OFFICIAL_ENTRY_ID: "missing-entry"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "battery_unavailable"}
