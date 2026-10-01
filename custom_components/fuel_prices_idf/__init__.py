"""The Fuel Prices Île-de-France integration."""
from __future__ import annotations

from datetime import datetime

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS_KM,
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
    DEFAULT_RADIUS_KM,
    DOMAIN,
)
from .coordinator import FuelPricesCoordinator
from .statistics_backfill import async_backfill_statistics

PLATFORMS: list[Platform] = [Platform.SENSOR]

SERVICE_BACKFILL = "backfill_statistics"
ATTR_YEAR = "year"
_BACKFILL_DONE = "backfill_done"


def _avg_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, str]:
    """Resolve the live avg SP95/SP98 sensor entity_ids from the registry.

    Backfilled statistics are imported INTO these entity_ids so history and
    live data form one continuous series. Keyed by fuel: {"sp95": ..., "sp98": ...}.
    """
    reg = er.async_get(hass)
    out: dict[str, str] = {}
    for fuel in ("sp95", "sp98"):
        unique_id = f"{entry.entry_id}_avg_{fuel}"
        ent = reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        if ent:
            out[fuel] = ent
    return out


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fuel Prices IDF from a config entry."""
    data = {**entry.data, **entry.options}
    coordinator = FuelPricesCoordinator(
        hass,
        home_lat=data.get(CONF_LATITUDE, DEFAULT_LATITUDE),
        home_lon=data.get(CONF_LONGITUDE, DEFAULT_LONGITUDE),
        radius_km=data.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _async_register_services(hass)

    # Auto-backfill the current year once per config entry (non-blocking).
    if not entry.data.get(_BACKFILL_DONE):

        async def _initial_backfill() -> None:
            try:
                entity_ids = _avg_entity_ids(hass, entry)
                if not entity_ids:
                    return
                await async_backfill_statistics(
                    hass, datetime.now().year, entity_ids
                )
                hass.config_entries.async_update_entry(
                    entry, data={**entry.data, _BACKFILL_DONE: True}
                )
            except Exception:  # noqa: BLE001
                # Backfill is best-effort; the live sensors still work without it.
                pass

        entry.async_create_background_task(
            hass, _initial_backfill(), "fuel_prices_idf_backfill"
        )

    return True


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the backfill service once."""
    if hass.services.has_service(DOMAIN, SERVICE_BACKFILL):
        return

    async def _handle_backfill(call: ServiceCall) -> None:
        year = call.data.get(ATTR_YEAR, datetime.now().year)
        # Backfill every configured entry's avg sensors.
        for entry in hass.config_entries.async_entries(DOMAIN):
            entity_ids = _avg_entity_ids(hass, entry)
            if entity_ids:
                await async_backfill_statistics(hass, int(year), entity_ids)

    hass.services.async_register(
        DOMAIN,
        SERVICE_BACKFILL,
        _handle_backfill,
        schema=vol.Schema(
            {vol.Optional(ATTR_YEAR): vol.All(vol.Coerce(int), vol.Range(min=2007, max=2100))}
        ),
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_BACKFILL)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
