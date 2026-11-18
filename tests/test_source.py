"""Tests for official battery discovery through public registries."""

import pytest
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.helpers import device_registry as dr

from custom_components.anker_solix_extras.const import OFFICIAL_DOMAIN, SUPPORTED_MODELS
from custom_components.anker_solix_extras.source import (
    async_get_batteries,
    async_get_battery,
)


@pytest.mark.parametrize("model", sorted(SUPPORTED_MODELS))
async def test_supported_models(hass, official_entry, model) -> None:
    registry = dr.async_get(hass)
    device = registry.async_get_device_by_identifier(
        (OFFICIAL_DOMAIN, official_entry.entry_id), official_entry.entry_id
    )
    registry.async_update_device(device.id, model=model)
    battery = async_get_battery(hass, official_entry.entry_id)
    assert battery.device.id == device.id
    assert battery.host == "192.0.2.10"
    assert battery.port == 502
    assert async_get_batteries(hass) == [battery]


async def test_unsupported_device_is_not_offered(hass, official_entry) -> None:
    registry = dr.async_get(hass)
    device = registry.async_get_device_by_identifier(
        (OFFICIAL_DOMAIN, official_entry.entry_id), official_entry.entry_id
    )
    registry.async_update_device(device.id, model="Anker SOLIX Smart Plug Gen 2")
    assert async_get_battery(hass, official_entry.entry_id) is None
    assert async_get_batteries(hass) == []


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"ip_address": ""},
        {"ip_address": "192.0.2.10", "port": True},
        {"ip_address": "192.0.2.10", "port": 0},
    ],
)
async def test_invalid_connection_data(hass, official_entry, data) -> None:
    hass.config_entries.async_update_entry(official_entry, data=data)
    assert async_get_battery(hass, official_entry.entry_id) is None


async def test_disabled_entry_is_not_offered(hass, official_entry) -> None:
    await hass.config_entries.async_set_disabled_by(
        official_entry.entry_id, ConfigEntryDisabler.USER
    )
    assert async_get_batteries(hass) == []


async def test_unknown_entry(hass) -> None:
    assert async_get_battery(hass, "missing-entry") is None
