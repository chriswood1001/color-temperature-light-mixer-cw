"""Config and options flow for Color Temperature Light Mixer CW."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_COLD_LIGHT,
    CONF_COLD_LIGHT_TEMPERATURE_KELVIN,
    CONF_DEFAULT_COLD_LIGHT_TEMPERATURE,
    CONF_DEFAULT_WARM_LIGHT_TEMPERATURE,
    CONF_PRIORITY,
    CONF_WARM_LIGHT,
    CONF_WARM_LIGHT_TEMPERATURE_KELVIN,
    DEFAULT_PRIORITY,
    DOMAIN,
    PRIORITY_BRIGHTNESS,
    PRIORITY_COLOR_TEMPERATURE,
    PRIORITY_SELECTOR,
    entry_priority,
    is_capitalized,
    merged_config,
)

_LOGGER = logging.getLogger(__name__)

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_WARM_LIGHT): selector.EntitySelector(
            {"domain": LIGHT_DOMAIN}
        ),
        vol.Required(
            CONF_WARM_LIGHT_TEMPERATURE_KELVIN,
            default=CONF_DEFAULT_WARM_LIGHT_TEMPERATURE,
        ): cv.positive_int,
        vol.Required(CONF_COLD_LIGHT): selector.EntitySelector(
            {"domain": LIGHT_DOMAIN}
        ),
        vol.Required(
            CONF_COLD_LIGHT_TEMPERATURE_KELVIN,
            default=CONF_DEFAULT_COLD_LIGHT_TEMPERATURE,
        ): cv.positive_int,
        vol.Required(CONF_PRIORITY, default=DEFAULT_PRIORITY): PRIORITY_SELECTOR,
    }
)

# Same light fields as the original mixer, plus priority. Used by Configure.
OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_WARM_LIGHT): selector.EntitySelector(
            {"domain": LIGHT_DOMAIN}
        ),
        vol.Required(CONF_WARM_LIGHT_TEMPERATURE_KELVIN): cv.positive_int,
        vol.Required(CONF_COLD_LIGHT): selector.EntitySelector(
            {"domain": LIGHT_DOMAIN}
        ),
        vol.Required(CONF_COLD_LIGHT_TEMPERATURE_KELVIN): cv.positive_int,
        vol.Required(CONF_PRIORITY): PRIORITY_SELECTOR,
    }
)


def _normalize_mixer_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Coerce kelvin to int and clamp priority."""
    data = dict(user_input)
    for key in (
        CONF_WARM_LIGHT_TEMPERATURE_KELVIN,
        CONF_COLD_LIGHT_TEMPERATURE_KELVIN,
    ):
        if key in data:
            data[key] = int(data[key])
    priority = data.get(CONF_PRIORITY, DEFAULT_PRIORITY)
    if priority not in (PRIORITY_COLOR_TEMPERATURE, PRIORITY_BRIGHTNESS):
        data[CONF_PRIORITY] = DEFAULT_PRIORITY
    return data


class CCTVirtuaLightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for CCT Virtual Light."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input and not is_capitalized(str(user_input[CONF_NAME])):
            _LOGGER.debug("Name is not capitalized")
            errors[CONF_NAME] = "Name must start with a capital letter"

        if user_input is not None and not errors:
            user_input = _normalize_mixer_input(user_input)
            priority = user_input.pop(CONF_PRIORITY, DEFAULT_PRIORITY)
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
                options={CONF_PRIORITY: priority},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change WW/CW entities, kelvin, and priority without deleting the device."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            user_input = _normalize_mixer_input(user_input)
            priority = user_input.pop(CONF_PRIORITY, DEFAULT_PRIORITY)
            data = {**entry.data, **user_input}
            return self.async_update_reload_and_abort(
                entry,
                data=data,
                options={CONF_PRIORITY: priority},
            )

        current = merged_config(entry)
        current[CONF_PRIORITY] = entry_priority(entry)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, current),
        )

    async def async_step_import(
        self,
        user_input: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle configuration by YAML file."""
        await self.async_set_unique_id(user_input[CONF_NAME])
        data = self.hass.data.setdefault(DOMAIN, {})
        data.setdefault("__yaml__", set()).add(self.unique_id)

        user_input = _normalize_mixer_input(user_input)
        priority = user_input.pop(CONF_PRIORITY, DEFAULT_PRIORITY)

        for existing in self._async_current_entries():
            if existing.unique_id == self.unique_id:
                _LOGGER.debug("Updating existing config entry")
                self.hass.config_entries.async_update_entry(
                    existing, data=user_input, options={CONF_PRIORITY: priority}
                )
                self._abort_if_unique_id_configured()

        _LOGGER.debug("Creating a new config entry")
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data=user_input,
            options={CONF_PRIORITY: priority},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Configure WW/CW entities, kelvin range, and mix priority."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the original mixer fields plus priority."""
        if user_input is not None:
            user_input = _normalize_mixer_input(user_input)
            return self.async_create_entry(title="", data=user_input)

        current = merged_config(self.config_entry)
        current[CONF_PRIORITY] = entry_priority(self.config_entry)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, current),
        )
