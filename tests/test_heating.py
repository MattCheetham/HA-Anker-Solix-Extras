"""Tests for heating estimates and their Home Assistant entities."""

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.anker_solix_extras.binary_sensor import (
    AnkerSolixBatteryHeatingActive,
)
from custom_components.anker_solix_extras.client import (
    PowerReadError,
    TemperatureReadError,
)
from custom_components.anker_solix_extras.const import DOMAIN, SUPPORTED_MODELS
from custom_components.anker_solix_extras.models import BatteryPower
from custom_components.anker_solix_extras.sensor import AnkerSolixBatteryHeatingPower


def get_entities(hass, extras_entry):
    """Index Extras entities by measurement, independently of naming or order."""
    entries = er.async_entries_for_config_entry(
        er.async_get(hass), extras_entry.entry_id
    )
    prefix = f"{extras_entry.data['official_entry_id']}_"
    return {entry.unique_id.removeprefix(prefix): entry for entry in entries}


@pytest.mark.parametrize(
    ("ac", "battery", "expected"),
    [
        (-2450, -2210, 240),
        (-1000, -1000, 0),
        (-2210, -2450, 0),
        (-1, 0, 1),
        (-1000, -999, 1),
        (0, 100, 0),
        (1000, 1200, 0),
        (1000, -1000, 0),
        (-1000, 100, 1100),
    ],
)
def test_heating_estimate(ac, battery, expected) -> None:
    """Use signed values, gate on AC absorption, and clamp negative differences."""
    assert BatteryPower(ac_power=ac, battery_power=battery).heating_power == expected


@pytest.mark.parametrize("model", sorted(SUPPORTED_MODELS))
async def test_heating_entities_share_official_device(
    hass, official_entry, extras_entry, mock_client, model
) -> None:
    """All supported profiles gain both entities without a second device."""
    device = next(iter(dr.async_get(hass).devices))
    dr.async_get(hass).async_update_device(device.id, model=model)
    devices_before = {item.id for item in dr.async_get(hass).devices}
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    entities = get_entities(hass, extras_entry)
    assert set(entities) == {
        "battery_temperature",
        "battery_heating_power",
        "battery_heating_active",
    }
    for key, entity in entities.items():
        assert entity.device_id == device.id
        assert entity.platform == DOMAIN
        assert entity.unique_id == f"{official_entry.entry_id}_{key}"
    assert {item.id for item in dr.async_get(hass).devices} == devices_before
    assert (
        dr.async_get(hass).async_get(device.id).config_entry_id
        == official_entry.entry_id
    )

    power = entities["battery_heating_power"]
    state = hass.states.get(power.entity_id)
    assert state.state == "240"
    assert state.name.endswith("Battery heating power")
    assert state.attributes["unit_of_measurement"] == "W"
    assert state.attributes["device_class"] == "power"
    assert state.attributes["state_class"] == "measurement"
    assert state.attributes["ac_power"] == -2450
    assert state.attributes["battery_power"] == -2210
    assert power.options["sensor"]["suggested_display_precision"] == 0
    active = hass.states.get(entities["battery_heating_active"].entity_id)
    assert active.state == "on"
    assert active.name.endswith("Battery heating active")
    assert active.attributes["device_class"] == "heat"
    assert "unit_of_measurement" not in active.attributes


async def test_heating_updates_and_independent_failures(
    hass, extras_entry, mock_client
) -> None:
    """Clear stale data on partial failures and recover both heating entities."""
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    entities = get_entities(hass, extras_entry)
    client = mock_client.return_value

    async def check(temperature, power, active):
        await extras_entry.runtime_data.async_refresh()
        assert (
            hass.states.get(entities["battery_temperature"].entity_id).state
            == temperature
        )
        state = hass.states.get(entities["battery_heating_power"].entity_id)
        assert state.state == power
        assert (
            hass.states.get(entities["battery_heating_active"].entity_id).state
            == active
        )
        if power == STATE_UNAVAILABLE:
            assert "ac_power" not in state.attributes
            assert "battery_power" not in state.attributes

    client.async_read_power.return_value = BatteryPower(-1000, -1000)
    await check("25.0", "0", "off")
    client.async_read_power.return_value = BatteryPower(-1000, -999)
    await check("25.0", "1", "on")
    client.async_read_power.side_effect = PowerReadError("rejected")
    await check("25.0", STATE_UNAVAILABLE, STATE_UNAVAILABLE)
    # Entity accessors must also return unknown, even when read outside HA's
    # normal state-writing path (which skips values for unavailable entities).
    power_entity = AnkerSolixBatteryHeatingPower(extras_entry.runtime_data)
    active_entity = AnkerSolixBatteryHeatingActive(extras_entry.runtime_data)
    assert power_entity.native_value is None
    assert power_entity.extra_state_attributes is None
    assert active_entity.is_on is None
    client.async_read_power.side_effect = None
    client.async_read_temperature.side_effect = TemperatureReadError("rejected")
    await check(STATE_UNAVAILABLE, "1", "on")
    client.async_read_power.side_effect = PowerReadError("offline")
    await check(STATE_UNAVAILABLE, STATE_UNAVAILABLE, STATE_UNAVAILABLE)
    client.async_read_temperature.side_effect = None
    client.async_read_power.side_effect = None
    client.async_read_power.return_value = BatteryPower(100, 200)
    await check("25.0", "0", "off")


@pytest.mark.parametrize("failed", ["temperature", "power"])
async def test_setup_with_one_measurement_unavailable(
    hass, extras_entry, mock_client, failed
) -> None:
    """An existing entry loads even if only one measurement can be read."""
    client = mock_client.return_value
    if failed == "temperature":
        client.async_read_temperature.side_effect = TemperatureReadError("rejected")
    else:
        client.async_read_power.side_effect = PowerReadError("rejected")
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    entities = get_entities(hass, extras_entry)
    assert len(entities) == 3
    assert extras_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(entities["battery_temperature"].entity_id).state == (
        STATE_UNAVAILABLE if failed == "temperature" else "25.0"
    )
    assert hass.states.get(entities["battery_heating_power"].entity_id).state == (
        STATE_UNAVAILABLE if failed == "power" else "240"
    )


async def test_all_entities_survive_reload_and_remove_safely(
    hass, official_entry, extras_entry, mock_client
) -> None:
    """Preserve stable IDs on reload and remove only Extras entities."""
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    before = get_entities(hass, extras_entry)
    assert await hass.config_entries.async_reload(extras_entry.entry_id)
    await hass.async_block_till_done()
    after = get_entities(hass, extras_entry)
    assert {
        key: (entry.entity_id, entry.device_id, entry.unique_id)
        for key, entry in before.items()
    } == {
        key: (entry.entity_id, entry.device_id, entry.unique_id)
        for key, entry in after.items()
    }
    assert await hass.config_entries.async_remove(extras_entry.entry_id)
    await hass.async_block_till_done()
    for entry in after.values():
        assert er.async_get(hass).async_get(entry.entity_id) is None
        assert hass.states.get(entry.entity_id) is None
        assert dr.async_get(hass).async_get(entry.device_id) is not None
    assert official_entry.state is ConfigEntryState.LOADED


async def test_power_not_read_when_official_entry_unloaded(
    hass, official_entry, extras_entry, mock_client
) -> None:
    """A missing source invalidates every entity without further Modbus reads."""
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    entities = get_entities(hass, extras_entry)
    assert await hass.config_entries.async_unload(official_entry.entry_id)
    client = mock_client.return_value
    client.async_read_power.reset_mock()
    client.async_read_temperature.reset_mock()
    await extras_entry.runtime_data.async_refresh()
    client.async_read_power.assert_not_awaited()
    client.async_read_temperature.assert_not_awaited()
    for entry in entities.values():
        assert hass.states.get(entry.entity_id).state == STATE_UNAVAILABLE
    assert await hass.config_entries.async_setup(official_entry.entry_id)
    await extras_entry.runtime_data.async_refresh()
    assert hass.states.get(entities["battery_heating_power"].entity_id).state == "240"
    assert hass.states.get(entities["battery_heating_active"].entity_id).state == "on"


async def test_upgrade_preserves_existing_temperature_entity(
    hass, extras_entry, mock_client
) -> None:
    """An existing temperature registry entry is reused when heating is added."""
    registry = er.async_get(hass)
    original = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{extras_entry.data['official_entry_id']}_battery_temperature",
        config_entry=extras_entry,
        suggested_object_id="my_existing_temperature",
    )
    registry.async_update_entity(original.entity_id, name="My temperature")
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    entities = get_entities(hass, extras_entry)
    assert entities["battery_temperature"].entity_id == original.entity_id
    assert entities["battery_temperature"].name == "My temperature"
    assert len(entities) == 3


async def test_sources_update_when_estimate_is_unchanged(
    hass, extras_entry, mock_client
) -> None:
    """Refresh source attributes even when the resulting heating stays constant."""
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    entity = get_entities(hass, extras_entry)["battery_heating_power"]
    mock_client.return_value.async_read_power.return_value = BatteryPower(-1240, -1000)
    await extras_entry.runtime_data.async_refresh()
    state = hass.states.get(entity.entity_id)
    assert state.state == "240"
    assert state.attributes["ac_power"] == -1240
    assert state.attributes["battery_power"] == -1000
