"""Exercise the backup reserve controls through Home Assistant services."""

from dataclasses import replace
from unittest.mock import call

import pytest
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.anker_solix_extras.client import (
    BackupReserveError,
    RegisterWriteError,
)


@pytest.fixture
async def reserve_entities(hass, extras_entry, mock_client):
    """Load the two controls on the existing device."""
    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    entities = er.async_entries_for_config_entry(
        er.async_get(hass), extras_entry.entry_id
    )
    return {
        entity.domain: entity
        for entity in entities
        if entity.domain in {"switch", "number"}
    }


async def test_reserve_actions_confirm_state_and_share_the_official_device(
    hass, extras_entry, mock_client, reserve_entities
) -> None:
    switch = reserve_entities["switch"]
    number = reserve_entities["number"]
    assert switch.device_id == number.device_id == extras_entry.runtime_data.device.id
    assert hass.states.get(switch.entity_id).state == STATE_OFF
    initial = hass.states.get(number.entity_id)
    assert float(initial.state) == 7
    assert initial.attributes["unit_of_measurement"] == "%"
    assert (
        initial.attributes["min"],
        initial.attributes["max"],
        initial.attributes["step"],
    ) == (0, 100, 1)

    client = mock_client.return_value

    async def write_register(address, value):
        reserve = client.async_read_backup_reserve.return_value
        if address == 60003:
            client.async_read_backup_reserve.return_value = replace(
                reserve, enabled=bool(value)
            )
        else:
            assert address == 60002
            client.async_read_backup_reserve.return_value = replace(
                reserve, percentage=value
            )

    client.async_write_register.side_effect = write_register
    client.async_write_register.assert_not_awaited()

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": switch.entity_id}, blocking=True
    )
    assert hass.states.get(switch.entity_id).state == STATE_ON
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": number.entity_id, "value": 19},
        blocking=True,
    )
    assert float(hass.states.get(number.entity_id).state) == 19
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": switch.entity_id}, blocking=True
    )
    assert hass.states.get(switch.entity_id).state == STATE_OFF
    assert float(hass.states.get(number.entity_id).state) == 19
    assert client.async_write_register.await_args_list == [
        call(60003, 1),
        call(60002, 19),
        call(60003, 0),
    ]


async def test_percentage_write_checks_fresh_enable_state(
    hass, extras_entry, mock_client, reserve_entities
) -> None:
    client = mock_client.return_value
    disabled = client.async_read_backup_reserve.return_value
    client.async_read_backup_reserve.return_value = replace(disabled, enabled=True)
    await extras_entry.runtime_data.async_refresh()
    assert hass.states.get(reserve_entities["switch"].entity_id).state == STATE_ON

    # Simulate someone turning reserve off in the app between polls.
    client.async_read_backup_reserve.return_value = disabled
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": reserve_entities["number"].entity_id, "value": 30},
            blocking=True,
        )
    assert error.value.translation_key == "reserve_disabled"
    assert hass.states.get(reserve_entities["switch"].entity_id).state == STATE_OFF
    client.async_write_register.assert_not_awaited()


async def test_fractional_percentage_never_reaches_modbus(
    hass, mock_client, reserve_entities
) -> None:
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": reserve_entities["number"].entity_id, "value": 25.5},
            blocking=True,
        )
    assert error.value.translation_key == "reserve_invalid_percentage"
    mock_client.return_value.async_write_register.assert_not_awaited()


async def test_switch_checks_fresh_capability(
    hass, mock_client, reserve_entities
) -> None:
    client = mock_client.return_value
    client.async_read_backup_reserve.return_value = None
    switch = reserve_entities["switch"].entity_id
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": switch}, blocking=True
        )
    assert error.value.translation_key == "reserve_unavailable"
    assert hass.states.get(switch).state == STATE_UNAVAILABLE
    client.async_write_register.assert_not_awaited()


async def test_readback_mismatch_does_not_publish_requested_value(
    hass, mock_client, reserve_entities
) -> None:
    switch = reserve_entities["switch"].entity_id
    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": switch}, blocking=True
        )
    assert error.value.translation_key == "reserve_write_failed"
    mock_client.return_value.async_write_register.assert_awaited_once_with(60003, 1)
    assert hass.states.get(switch).state == STATE_OFF


async def test_register_write_failure_reports_control_error(
    hass, mock_client, reserve_entities
) -> None:
    client = mock_client.return_value
    client.async_write_register.side_effect = RegisterWriteError("write failed")
    switch = reserve_entities["switch"].entity_id
    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": switch}, blocking=True
        )
    assert error.value.translation_key == "reserve_write_failed"
    assert hass.states.get(switch).state == STATE_UNAVAILABLE


async def test_failed_reserve_reads_leave_measurements_available(
    hass, extras_entry, mock_client, reserve_entities
) -> None:
    client = mock_client.return_value
    client.async_read_backup_reserve.side_effect = BackupReserveError("offline")
    await extras_entry.runtime_data.async_refresh()
    for entity in reserve_entities.values():
        assert hass.states.get(entity.entity_id).state == STATE_UNAVAILABLE
    assert extras_entry.runtime_data.data.temperature == 25
    assert extras_entry.runtime_data.last_update_success

    client.async_read_backup_reserve.side_effect = None
    await extras_entry.runtime_data.async_refresh()
    assert hass.states.get(reserve_entities["switch"].entity_id).state == STATE_OFF
