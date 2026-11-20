"""Verify the documented register entities through the real HA setup."""

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from modbus_connection import IllegalDataAddressError

from custom_components.anker_solix_extras.const import DOMAIN


async def test_published_registers(
    hass, extras_entry, official_entry, mock_connection, monkeypatch
) -> None:
    """Read independently and confirm explicit writes on supported models."""
    devices = dr.async_get(hass)
    device = next(iter(devices.devices))
    devices.async_update_device(device.id, model="Anker SOLIX Solarbank Max AC")
    unit = mock_connection.return_value.for_unit.return_value
    inputs = {
        10000: [1] + [0] * 9,
        10015: [100],
        10022: [0x8000, 3],
        10024: [0, 123],
        10026: [0, 0],
        10030: [0, 45],
        10034: [0, 67],
        10040: [2],
        10041: [1],
        10156: [250],
        32775: [0],
    }
    settings = {10060: [0x6553, 0xF100], 10074: [0], 10075: [0, 250]}

    def read(registers, address, count):
        if address not in registers:
            raise IllegalDataAddressError("Unsupported register")
        assert len(registers[address]) == count
        return registers[address]

    unit.read_input_registers.side_effect = lambda address, count: read(
        inputs, address, count
    )
    unit.read_holding_registers.side_effect = lambda address, count: read(
        settings, address, count
    )
    unit.write_register.side_effect = lambda address, value: settings.update(
        {address: [value]}
    )
    unit.write_registers.side_effect = lambda address, words: settings.update(
        {address: words}
    )

    assert await hass.config_entries.async_setup(extras_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)

    def entity_id(platform, key):
        return registry.async_get_entity_id(
            platform, DOMAIN, f"{official_entry.entry_id}_{key}"
        )

    expected = {
        "total_battery_charge_energy": "214748365.1",
        "total_battery_discharge_energy": "12.3",
        "total_load_energy": "0.0",
        "total_grid_import_energy": "4.5",
        "total_grid_export_energy": "6.7",
        "pcs_count": "2",
        "available_pcs_count": "1",
        "system_time": "2023-11-14T22:13:20+00:00",
    }
    for key, value in expected.items():
        sensor = entity_id("sensor", key)
        assert registry.async_get(sensor).device_id == device.id
        assert hass.states.get(sensor).state == value
    controls = {}
    for platform, key in (
        ("button", "sync_system_time"),
        ("switch", "export_limit_enabled"),
        ("number", "export_limit"),
    ):
        entry = registry.async_get(entity_id(platform, key))
        assert entry.device_id == device.id
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        controls[platform] = entry.entity_id
        registry.async_update_entity(entry.entity_id, disabled_by=None)

    assert await hass.config_entries.async_reload(extras_entry.entry_id)
    await hass.async_block_till_done()
    unit.write_register.assert_not_awaited()
    unit.write_registers.assert_not_awaited()
    coordinator = extras_entry.runtime_data

    inputs.pop(10024)
    await coordinator.async_refresh()
    assert (
        hass.states.get(entity_id("sensor", "total_battery_discharge_energy")).state
        == STATE_UNAVAILABLE
    )
    assert hass.states.get(entity_id("sensor", "pcs_count")).state == "2"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": controls["switch"]}, blocking=True
    )
    unit.write_register.assert_awaited_once_with(10074, 1)
    assert coordinator.data.published_values[10074] == 1
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": controls["number"], "value": 65786},
        blocking=True,
    )
    unit.write_registers.assert_awaited_once_with(10075, [1, 250])
    assert coordinator.data.published_values[10075] == 65786

    monkeypatch.setattr(
        "custom_components.anker_solix_extras.coordinator.time", lambda: 1700000001
    )
    await hass.services.async_call(
        "button", "press", {"entity_id": controls["button"]}, blocking=True
    )
    unit.write_registers.assert_awaited_with(10060, [0x6553, 0xF101])

    unit.write_registers.reset_mock()
    with pytest.raises(ServiceValidationError):
        await coordinator.async_set_export_limit(1.5)
    settings.pop(10075)
    with pytest.raises(ServiceValidationError):
        await coordinator.async_set_export_limit(100)
    unit.write_registers.assert_not_awaited()
    assert 10075 not in coordinator.data.published_values

    unit.write_register.side_effect = None
    with pytest.raises(HomeAssistantError):
        await coordinator.async_set_export_limit_enabled(False)
    assert coordinator.data.published_values[10074] == 1
