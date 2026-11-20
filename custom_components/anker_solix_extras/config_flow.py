"""Configure Extras by selecting a supported official battery."""

from typing import Any

import voluptuous as vol
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .client import AnkerSolixExtrasClient, TemperatureReadError
from .const import (
    CONF_ENABLE_OFF_GRID_OUTPUT_POWER,
    CONF_ENABLE_PUBLISHED_REGISTERS,
    CONF_OFFICIAL_ENTRY_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MODBUS_DEVICE_ID,
    PUBLISHED_REGISTER_MODELS,
    SOLARBANK_4_E5000_PRO,
)
from .source import async_get_batteries, async_get_battery


def _polling_schema(default: int = DEFAULT_SCAN_INTERVAL) -> vol.Schema:
    """Configure a positive polling interval in whole seconds."""
    return vol.Schema(
        {
            vol.Required(CONF_SCAN_INTERVAL, default=default): vol.All(
                int, vol.Range(min=1)
            )
        }
    )


class AnkerSolixExtrasConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create one Extras entry per official battery."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AnkerSolixExtrasOptionsFlow:
        """Allow settings changes without recreating the integration entry."""
        return AnkerSolixExtrasOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select an official battery and validate the additional register."""
        errors: dict[str, str] = {}
        if user_input is not None:
            official_entry_id = user_input[CONF_OFFICIAL_ENTRY_ID]
            await self.async_set_unique_id(official_entry_id)
            self._abort_if_unique_id_configured()
            battery = async_get_battery(self.hass, official_entry_id)
            if battery is None:
                errors["base"] = "battery_unavailable"
            else:
                try:
                    async with async_get_temporary_unit(
                        self.hass, battery.modbus_params, MODBUS_DEVICE_ID
                    ) as unit:
                        await AnkerSolixExtrasClient(unit).async_read_temperature()
                except HomeAssistantError, TemperatureReadError:
                    errors["base"] = "cannot_read_temperature"
                else:
                    return self.async_create_entry(
                        title=battery.entry.title,
                        data={CONF_OFFICIAL_ENTRY_ID: official_entry_id},
                        options={
                            CONF_SCAN_INTERVAL: user_input.get(
                                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                            )
                        },
                    )

        batteries = async_get_batteries(self.hass)
        if not batteries:
            return self.async_abort(reason="no_official_batteries")

        return self.async_show_form(
            step_id="user",
            data_schema=_polling_schema().extend(
                {
                    vol.Required(CONF_OFFICIAL_ENTRY_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=battery.entry.entry_id,
                                    label=battery.entry.title,
                                )
                                for battery in batteries
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            errors=errors,
        )


class AnkerSolixExtrasOptionsFlow(OptionsFlowWithReload):
    """Change Extras settings and reload only this integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the polling interval and available experimental features."""
        options = self.config_entry.options
        if user_input is not None:
            return self.async_create_entry(data={**options, **user_input})

        schema = _polling_schema(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        battery = async_get_battery(
            self.hass, self.config_entry.data[CONF_OFFICIAL_ENTRY_ID]
        )
        if battery is not None and battery.device.model != SOLARBANK_4_E5000_PRO:
            schema = schema.extend(
                {
                    vol.Optional(
                        CONF_ENABLE_OFF_GRID_OUTPUT_POWER,
                        default=options.get(CONF_ENABLE_OFF_GRID_OUTPUT_POWER, False),
                    ): selector.BooleanSelector()
                }
            )
        if (
            battery is not None
            and battery.device.model not in PUBLISHED_REGISTER_MODELS
        ):
            schema = schema.extend(
                {
                    vol.Optional(
                        CONF_ENABLE_PUBLISHED_REGISTERS,
                        default=options.get(CONF_ENABLE_PUBLISHED_REGISTERS, False),
                    ): selector.BooleanSelector()
                }
            )
        return self.async_show_form(step_id="init", data_schema=schema)
