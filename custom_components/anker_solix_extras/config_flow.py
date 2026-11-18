"""Configure Extras by selecting a supported official battery."""

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .client import AnkerSolixExtrasClient, TemperatureReadError
from .const import CONF_OFFICIAL_ENTRY_ID, DOMAIN
from .source import async_get_batteries, async_get_battery


class AnkerSolixExtrasConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create one Extras entry per official battery."""

    VERSION = 1

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
                client = AnkerSolixExtrasClient(battery.host, battery.port)
                try:
                    await client.async_read_temperature()
                except TemperatureReadError:
                    errors["base"] = "cannot_read_temperature"
                else:
                    return self.async_create_entry(
                        title=battery.entry.title,
                        data={CONF_OFFICIAL_ENTRY_ID: official_entry_id},
                    )
                finally:
                    client.close()

        batteries = async_get_batteries(self.hass)
        if not batteries:
            return self.async_abort(reason="no_official_batteries")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
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
