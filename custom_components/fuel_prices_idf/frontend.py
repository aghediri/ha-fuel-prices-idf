"""Serve and register the custom Lovelace card bundled with the integration."""
from __future__ import annotations

import logging
import os

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

URL_BASE = "/fuel_prices_idf"
CARD_FILENAME = "fuel-prices-idf-card.js"
CARD_URL = f"{URL_BASE}/{CARD_FILENAME}"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Expose the www/ folder and auto-register the card as a Lovelace resource."""
    www_dir = os.path.join(os.path.dirname(__file__), "www")

    await hass.http.async_register_static_paths(
        [StaticPathConfig(URL_BASE, www_dir, cache_headers=False)]
    )

    # Auto-register the JS module resource if Lovelace is in storage mode.
    try:
        lovelace = hass.data.get("lovelace")
        resources = getattr(lovelace, "resources", None) if lovelace else None
        if resources is None:
            return
        if not resources.loaded:
            await resources.async_load()
            resources.loaded = True
        already = any(
            (item.get("url") or "").startswith(CARD_URL)
            for item in resources.async_items()
        )
        if not already:
            await resources.async_create_item(
                {"res_type": "module", "url": f"{CARD_URL}?v=1.0.0"}
            )
            _LOGGER.info("Fuel Prices IDF: registered Lovelace card resource")
    except Exception as err:  # noqa: BLE001
        # YAML-mode dashboards (or older cores) must add the resource manually;
        # the README documents this. Serving the static path still works.
        _LOGGER.debug("Could not auto-register card resource: %s", err)
