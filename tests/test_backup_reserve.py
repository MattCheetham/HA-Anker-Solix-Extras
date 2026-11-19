"""Exercise the backup reserve switch through Home Assistant services."""

from unittest.mock import call

import pytest
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.anker_solix_extras.client import (
    BackupReserveError,
    RegisterWriteError,
)
from custom_components.anker_solix_extras.const import DOMAIN, OFFICIAL_DOMAIN


@pytest.fixture
async def reserve_switch(hass, extras_entry, mock_client):
    """Load the reserve switch on the existing device."""
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    entities = er.async_entries_for_config_entry(
        er.async_get(hass), extras_entry.entry_id
    )
    assert not any(entity.domain == "number" for entity in entities)
    return next(entity for entity in entities if entity.domain == "switch")


async def test_reserve_actions_confirm_state_and_share_the_official_device(
    hass, extras_entry, mock_client, reserve_switch
) -> None:
    assert reserve_switch.device_id == extras_entry.runtime_data.device.id
    assert hass.states.get(reserve_switch.entity_id).state == STATE_OFF

    client = mock_client.return_value

    async def write_register(address, value):
        assert address == 60003
        client.async_read_backup_reserve.return_value = bool(value)

    client.async_write_register.side_effect = write_register
    client.async_write_register.assert_not_awaited()

    target = {"entity_id": reserve_switch.entity_id}
    await hass.services.async_call("switch", "turn_on", target, blocking=True)
    assert hass.states.get(reserve_switch.entity_id).state == STATE_ON
    await hass.services.async_call("switch", "turn_off", target, blocking=True)
    assert hass.states.get(reserve_switch.entity_id).state == STATE_OFF
    assert client.async_write_register.await_args_list == [
        call(60003, 1),
        call(60003, 0),
    ]


async def test_upgrade_removes_only_the_legacy_extras_number(
    hass, extras_entry, official_entry, mock_client
) -> None:
    assert extras_entry.minor_version == 1
    registry = er.async_get(hass)
    unique_id = f"{official_entry.entry_id}_backup_reserve_soc"
    legacy = registry.async_get_or_create(
        "number", DOMAIN, unique_id, config_entry=extras_entry
    )
    official = registry.async_get_or_create(
        "number", OFFICIAL_DOMAIN, unique_id, config_entry=official_entry
    )
    switch = registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{official_entry.entry_id}_backup_reserve",
        config_entry=extras_entry,
        suggested_object_id="my_backup_reserve",
    )
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    assert extras_entry.minor_version == 2
    assert registry.async_get(legacy.entity_id) is None
    assert registry.async_get(official.entity_id) == official
    assert hass.states.get(switch.entity_id).state == STATE_OFF
    mock_client.return_value.async_write_register.assert_not_awaited()


async def test_switch_checks_fresh_capability(
    hass, mock_client, reserve_switch
) -> None:
    client = mock_client.return_value
    client.async_read_backup_reserve.return_value = None
    switch = reserve_switch.entity_id
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": switch}, blocking=True
        )
    assert error.value.translation_key == "reserve_unavailable"
    assert hass.states.get(switch).state == STATE_UNAVAILABLE
    client.async_write_register.assert_not_awaited()


async def test_readback_mismatch_does_not_publish_requested_value(
    hass, mock_client, reserve_switch
) -> None:
    switch = reserve_switch.entity_id
    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": switch}, blocking=True
        )
    assert error.value.translation_key == "reserve_write_failed"
    mock_client.return_value.async_write_register.assert_awaited_once_with(60003, 1)
    assert hass.states.get(switch).state == STATE_OFF


async def test_register_write_failure_reports_control_error(
    hass, mock_client, reserve_switch
) -> None:
    client = mock_client.return_value
    client.async_write_register.side_effect = RegisterWriteError("write failed")
    switch = reserve_switch.entity_id
    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": switch}, blocking=True
        )
    assert error.value.translation_key == "reserve_write_failed"
    assert hass.states.get(switch).state == STATE_UNAVAILABLE


async def test_failed_reserve_reads_leave_measurements_available(
    hass, extras_entry, mock_client, reserve_switch
) -> None:
    client = mock_client.return_value
    client.async_read_backup_reserve.side_effect = BackupReserveError("offline")
    await extras_entry.runtime_data.async_refresh()
    assert hass.states.get(reserve_switch.entity_id).state == STATE_UNAVAILABLE
    assert extras_entry.runtime_data.data.temperature == 25
    assert extras_entry.runtime_data.last_update_success

    client.async_read_backup_reserve.side_effect = None
    await extras_entry.runtime_data.async_refresh()
    assert hass.states.get(reserve_switch.entity_id).state == STATE_OFF
