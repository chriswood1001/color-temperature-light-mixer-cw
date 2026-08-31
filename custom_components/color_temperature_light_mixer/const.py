"""Constants for color temperature light mixer CW."""

from logging import Logger, getLogger

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_COLOR_TEMP_KELVIN,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

LOGGER: Logger = getLogger(__package__)

NAME = "Color Temperature Light Mixer CW"
DOMAIN = "color_temperature_light_mixer"

BRIGHTNESS_SENSOR_NAME = "Restored brightness"
TEMPERATURE_SENSOR_NAME = "Restored temperature"

DISPATCHER_SIGNAL_TURN_OFF = f"{DOMAIN}_turn_off"

# Configuration
CONF_WARM_LIGHT = f"warm_light_{CONF_ENTITY_ID}"
CONF_WARM_LIGHT_TEMPERATURE_KELVIN = f"warm_light_{ATTR_COLOR_TEMP_KELVIN}"
CONF_COLD_LIGHT = f"cold_light_{CONF_ENTITY_ID}"
CONF_COLD_LIGHT_TEMPERATURE_KELVIN = f"cold_light_{ATTR_COLOR_TEMP_KELVIN}"
CONF_PRIORITY = "priority"

PRIORITY_COLOR_TEMPERATURE = "color_temperature"
PRIORITY_BRIGHTNESS = "brightness"
DEFAULT_PRIORITY = PRIORITY_COLOR_TEMPERATURE

CONF_DEFAULT_WARM_LIGHT_TEMPERATURE = 3000
CONF_DEFAULT_COLD_LIGHT_TEMPERATURE = 6000

PRIORITY_SELECTOR = selector.selector(
    {
        "select": {
            "options": [
                {
                    "value": PRIORITY_COLOR_TEMPERATURE,
                    "label": "Prioritize color temperature",
                },
                {
                    "value": PRIORITY_BRIGHTNESS,
                    "label": "Prioritize brightness",
                },
            ],
            "mode": "dropdown",
        }
    }
)


def is_capitalized(value: str) -> bool:
    """Check if the word is capitalized."""
    return value[0].isupper()


def merged_config(entry) -> dict:
    """Config data with options overlaid (Configure form updates options)."""
    return {**entry.data, **entry.options}


def entry_priority(entry) -> str:
    """Return the configured mix priority, defaulting to color temperature."""
    value = merged_config(entry).get(CONF_PRIORITY, DEFAULT_PRIORITY)
    if value not in (PRIORITY_COLOR_TEMPERATURE, PRIORITY_BRIGHTNESS):
        return DEFAULT_PRIORITY
    return value


_DOMAIN_SCHEMA = {
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_WARM_LIGHT): selector.EntitySelector({"domain": LIGHT_DOMAIN}),
    vol.Required(
        CONF_WARM_LIGHT_TEMPERATURE_KELVIN,
        description={"suggested_value": CONF_DEFAULT_WARM_LIGHT_TEMPERATURE},
    ): cv.positive_int,
    vol.Required(CONF_COLD_LIGHT): selector.EntitySelector({"domain": LIGHT_DOMAIN}),
    vol.Required(
        CONF_COLD_LIGHT_TEMPERATURE_KELVIN,
        description={"suggested_value": CONF_DEFAULT_COLD_LIGHT_TEMPERATURE},
    ): cv.positive_int,
    vol.Optional(CONF_PRIORITY, default=DEFAULT_PRIORITY): vol.In(
        [PRIORITY_COLOR_TEMPERATURE, PRIORITY_BRIGHTNESS]
    ),
}
"""Schema of each CCT virtual light"""
