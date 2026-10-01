"""Config flow for Fuel Prices Île-de-France."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS_KM,
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
    DEFAULT_NAME,
    DEFAULT_RADIUS_KM,
    DOMAIN,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "location",
                default={
                    "latitude": defaults.get(CONF_LATITUDE, DEFAULT_LATITUDE),
                    "longitude": defaults.get(CONF_LONGITUDE, DEFAULT_LONGITUDE),
                    "radius": 0,
                },
            ): LocationSelector(),
            vol.Required(
                CONF_RADIUS_KM,
                default=defaults.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1, max=100, step=1, mode=NumberSelectorMode.BOX,
                    unit_of_measurement="km",
                )
            ),
        }
    )


def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
    loc = user_input.pop("location", {}) or {}
    return {
        CONF_LATITUDE: loc.get("latitude", DEFAULT_LATITUDE),
        CONF_LONGITUDE: loc.get("longitude", DEFAULT_LONGITUDE),
        CONF_RADIUS_KM: user_input.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM),
    }


class FuelPricesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            data = _flatten(dict(user_input))
            await self.async_set_unique_id(
                f"{data[CONF_LATITUDE]:.4f}_{data[CONF_LONGITUDE]:.4f}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=DEFAULT_NAME, data={CONF_NAME: DEFAULT_NAME, **data}
            )
        return self.async_show_form(step_id="user", data_schema=_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return FuelPricesOptionsFlow(entry)


class FuelPricesOptionsFlow(OptionsFlow):
    """Allow editing the home location and radius after setup."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=_flatten(dict(user_input)))
        current = {**self._entry.data, **self._entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(current))
