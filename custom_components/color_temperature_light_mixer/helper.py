"""Utility functions and classes for computing the light brightness and temperature."""

from dataclasses import dataclass
from enum import StrEnum, auto
import logging
import math

from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    rgbww_to_color_temperature,
)

_LOGGER = logging.getLogger(__name__)
BRIGHTNESS_RANGE = (1, 255)


class MixingMode(StrEnum):
    """User-facing mix mode for the virtual CCT light."""

    COLOR_TEMPERATURE = "color_temperature"
    """100% brightness is the maximum achievable at the requested kelvin."""
    BRIGHTNESS = "brightness"
    """100% brightness is both channels full; kelvin may shift at high brightness."""


class BrightnessTemperaturePriority(StrEnum):
    """Enum that indicates what to prefer in the computation of the target brightness required to (temperature, brightness) target tuple."""

    BRIGHTNESS = auto()
    """Maintain the target brightness, at the expense of the temperature"""
    TEMPERATURE = auto()
    """Maintain the target temperature, at the expense of the brightness"""
    MIXED = auto()
    """Try to target a mix of both temperature and brightness"""


@dataclass
class TurnOnSettings:
    """Options to pass to the light to be turned on."""

    entity_id: str
    common_data: dict[str, int]
    brightness: int | None = None


@dataclass
class TemperatureCalculator:
    """Class for computing the temperature of two combined lights of different temperature, depending on their brightness level."""

    warm_brightness: int
    """Brightness of the warm light in the range 1...255"""
    warm_temperature_kelvin: int
    """Temperature of the warm light in kelvin"""
    cold_brightness: int
    """Brightness of the cold light in the range 1...255"""
    cold_temperature_kelvin: int
    """Temperature of the cold light in kelvin"""

    def current_temperature(self) -> int:
        """Compute the current combined temperature."""

        combined_temperature, _ = rgbww_to_color_temperature(
            (0, 0, 0, self.cold_brightness, self.warm_brightness),
            self.warm_temperature_kelvin,
            self.cold_temperature_kelvin,
        )

        # Clamp the computed temperature between the min and maximum supported temperatures
        return max(
            self.warm_temperature_kelvin,
            min(self.cold_temperature_kelvin, combined_temperature),
        )


@dataclass
class BrightnessCalculator:
    """Class that given a target temperature and target, computes the brightness of the two combined lights."""

    warm_temperature_kelvin: int
    """Temperature of the warm light in kelvin"""
    cold_temperature_kelvin: int
    """Temperature of the cold light in kelvin"""

    target_temperature_kelvin: int
    """Target temperature in kelvin to reach"""
    target_brightness: int
    """Target brightness to reach in the range 1...255"""

    priority: BrightnessTemperaturePriority = BrightnessTemperaturePriority.MIXED
    """Govern the behavior when we we want to reach a brightness and temperature outside the admissable range"""

    mixing_mode: MixingMode = MixingMode.COLOR_TEMPERATURE
    """User-facing mix: max-at-CCT vs both-channels-full."""

    def compute_brightnesses(self) -> tuple[int, int]:
        """Compute the warm and cold light brightness required to reach the target temperature.

        Returns:
            (warm, cold) brightness in range 0-255

        """

        _LOGGER.debug(
            "Computing brightness for temp: %d, bright: %d, priority: %s, mode: %s",
            self.target_temperature_kelvin,
            self.target_brightness,
            self.priority.name,
            self.mixing_mode,
        )

        if self.mixing_mode == MixingMode.COLOR_TEMPERATURE:
            return self._compute_max_at_cct()

        # Convert ot mired to operate on a linear temperature space
        target_temperature_mired = color_temperature_kelvin_to_mired(
            self.target_temperature_kelvin
        )
        warm_temperature_mired = color_temperature_kelvin_to_mired(
            self.warm_temperature_kelvin
        )
        cold_temperature_mired = color_temperature_kelvin_to_mired(
            self.cold_temperature_kelvin
        )

        # These functions are obtained by inverting the one defined in the util module `rgbww_to_color_temperature()`
        cold_brightness, warm_brightness = self._decompose_brightnesses(
            target_temperature_mired,
            self.target_brightness,
            warm_temperature_mired,
            cold_temperature_mired,
        )

        # Compute the half-point between the range of possible temperatures
        half_temperature_mired = (warm_temperature_mired + cold_temperature_mired) / 2

        # Flag that takes into account if the target temperature is in the first or second half of the temperature range
        is_temp_in_second_half = target_temperature_mired > half_temperature_mired

        if is_temp_in_second_half and warm_brightness > BRIGHTNESS_RANGE[1]:
            # If the computed warm brightness is greater than the achievable brightness, mirror the temperature against the x=target_temperature_mired line,
            # obtaining the specular case than the one condition below
            mirrored_temperature_mired = (
                2 * half_temperature_mired - target_temperature_mired
            )
            cold_brightness, warm_brightness = self._target_outside_range(
                mirrored_temperature_mired,
                warm_temperature_mired,
                cold_temperature_mired,
            )
        elif cold_brightness > BRIGHTNESS_RANGE[1]:
            # If the cold brightness is greater than the achievable brightness, scale it back to an acceptable range,
            # depending on the priority between brightness and temperature
            warm_brightness, cold_brightness = self._target_outside_range(
                target_temperature_mired, warm_temperature_mired, cold_temperature_mired
            )

        # Clamp brightness to acceptable ranges
        warm_brightness = min(warm_brightness, BRIGHTNESS_RANGE[1])
        cold_brightness = min(cold_brightness, BRIGHTNESS_RANGE[1])
        return warm_brightness, cold_brightness

    def _compute_max_at_cct(self) -> tuple[int, int]:
        """Keep kelvin exact; 100% is the brightest mix possible at that kelvin.

        At the warm extreme this is WW full / CW off (reported as 100%).
        At mixed kelvin both channels can still reach full.
        """
        # Use continuous mireds so 2700K and 2702K (HA floor rounding) stay on the WW rail.
        target_temperature_mired = 1_000_000.0 / self.target_temperature_kelvin
        warm_temperature_mired = 1_000_000.0 / self.warm_temperature_kelvin
        cold_temperature_mired = 1_000_000.0 / self.cold_temperature_kelvin
        span = cold_temperature_mired - warm_temperature_mired
        if span == 0:
            return min(self.target_brightness, BRIGHTNESS_RANGE[1]), 0

        cold_ratio = (target_temperature_mired - warm_temperature_mired) / span
        warm_ratio = 1 - cold_ratio
        cold_ratio = min(max(cold_ratio, 0.0), 1.0)
        warm_ratio = min(max(warm_ratio, 0.0), 1.0)
        higher = max(cold_ratio, warm_ratio, 1e-9)

        target = min(max(int(self.target_brightness), 0), BRIGHTNESS_RANGE[1])
        cold_brightness = round(target * cold_ratio / higher)
        warm_brightness = round(target * warm_ratio / higher)

        _LOGGER.debug(
            "Max-at-CCT brightness, c: %d, w: %d (ratios c=%.3f w=%.3f)",
            cold_brightness,
            warm_brightness,
            cold_ratio,
            warm_ratio,
        )
        return (
            min(max(warm_brightness, 0), BRIGHTNESS_RANGE[1]),
            min(max(cold_brightness, 0), BRIGHTNESS_RANGE[1]),
        )

    def _target_outside_range(
        self, target_temperature_mired, warm_temperature_mired, cold_temperature_mired
    ) -> tuple[int, int]:
        """Compute ad adjusted brightness and temperature when outside the achievable range.

        Given a target_temperature outside the achievable range, compute a new target_temperature or target_brightness depending on the configured BrightnessTemperaturePriority.
        """
        match self.priority:
            case BrightnessTemperaturePriority.BRIGHTNESS:
                # Find the horizontal projection of the point (target_temp, target_brightness) on the hyperbolic curve
                new_target_brightness = self.target_brightness
                new_target_temperature_mired = (
                    (2 * self.target_brightness * warm_temperature_mired)
                    + BRIGHTNESS_RANGE[1] * cold_temperature_mired
                    - BRIGHTNESS_RANGE[1] * warm_temperature_mired
                ) / (2 * self.target_brightness)

                _LOGGER.debug(
                    "Computed new target_temperature: %d", new_target_temperature_mired
                )

            case BrightnessTemperaturePriority.TEMPERATURE:
                # Find the vertical projection of the point (target_temp, target_brightness) on the hyperbolic curve
                new_target_temperature_mired = target_temperature_mired
                new_target_brightness = (
                    BRIGHTNESS_RANGE[1]
                    * (cold_temperature_mired - warm_temperature_mired)
                    / (2 * (target_temperature_mired - warm_temperature_mired))
                )
                _LOGGER.debug(
                    "Computed new target_brightness: %d", new_target_brightness
                )

            case BrightnessTemperaturePriority.MIXED:
                new_target_temperature_mired, new_target_brightness = (
                    self._find_closest_achievable_target(
                        target_temperature_mired,
                        warm_temperature_mired,
                        cold_temperature_mired,
                    )
                )
                _LOGGER.debug(
                    "Computed new target_temperature: %d, target_brightness: %d",
                    new_target_temperature_mired,
                    new_target_brightness,
                )

        cold_brightness, warm_brightness = self._decompose_brightnesses(
            target_temperature_mired=new_target_temperature_mired,
            target_brightness=new_target_brightness,
            warm_temperature_mired=warm_temperature_mired,
            cold_temperature_mired=cold_temperature_mired,
        )
        return warm_brightness, cold_brightness

    def _decompose_brightnesses(
        self,
        target_temperature_mired,
        target_brightness,
        warm_temperature_mired,
        cold_temperature_mired,
    ):
        """Compute the warm and cold brightnesses required to reach the target temperature and brightness combo."""

        cold_brightness = round(
            (2 * target_brightness)
            * (target_temperature_mired - warm_temperature_mired)
            / (cold_temperature_mired - warm_temperature_mired)
        )
        warm_brightness = round(
            (2 * target_brightness)
            * (cold_temperature_mired - target_temperature_mired)
            / (cold_temperature_mired - warm_temperature_mired)
        )

        _LOGGER.debug(
            "Computed brightness, c: %d, w: %d", cold_brightness, warm_brightness
        )

        return cold_brightness, warm_brightness

    def _find_closest_achievable_target(
        self,
        target_temperature_mired: int,
        warm_temperature_mired: int,
        cold_temperature_mired: int,
    ):
        def brightness_value(temp):
            """Compute the combined brightness given a temperature."""
            return int(
                BRIGHTNESS_RANGE[1]
                * (cold_temperature_mired - warm_temperature_mired)
                / (2 * (temp - warm_temperature_mired))
            )

        half_temperature_mired = int(
            (warm_temperature_mired + cold_temperature_mired) / 2
        )

        # Init variables
        closest_temperature_mired, best_distance = cold_temperature_mired, math.inf

        # Distance between target point and hyperbolic curve of achievable brightness targets
        for x in range(cold_temperature_mired, half_temperature_mired):
            d = (target_temperature_mired - x) ** 2 + (
                self.target_brightness - brightness_value(x)
            ) ** 2
            if d < best_distance:
                closest_temperature_mired, best_distance = x, d

        return closest_temperature_mired, brightness_value(closest_temperature_mired)
