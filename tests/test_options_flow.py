"""Tests for configurable Modbus polling and safe application of options."""

from datetime import timedelta

import pytest
import voluptuous as vol
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.anker_solix_extras.const import CONF_OFFICIAL_ENTRY_ID, DOMAIN

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
    hass, official_entry, extras_entry, mock_client, freezer
) -> None:
    """Changing the interval replaces only Extras' transport and timer."""
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
    mock_client.return_value.close.assert_called()

    # Observe the new timer twice, before the old 60-second timer could fire.
    client = mock_client.return_value
    client.async_read_temperature.reset_mock()
    client.async_read_power.reset_mock()
    for expected in (1, 2):
        freezer.tick(timedelta(seconds=16))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert client.async_read_temperature.await_count == expected
        assert client.async_read_power.await_count == expected


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
