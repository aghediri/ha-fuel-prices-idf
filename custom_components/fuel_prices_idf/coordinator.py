"""DataUpdateCoordinator for Fuel Prices Île-de-France.

Fetches the current open-data snapshot for all Île-de-France stations from the
data.economie.gouv.fr Explore v2 API, then computes:
  * regional average SP95 / SP98,
  * the nearest station (to the configured home) selling each fuel,
  * the cheapest station within the configured radius for each fuel.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from math import asin, cos, radians, sin, sqrt

import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_BASE,
    FUELS,
    IDF_DEPARTMENTS,
    UPDATE_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    r = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return 2 * r * asin(sqrt(a))


class FuelPricesCoordinator(DataUpdateCoordinator):
    """Poll the open-data API and derive per-fuel station metrics."""

    def __init__(
        self,
        hass: HomeAssistant,
        home_lat: float,
        home_lon: float,
        radius_km: float,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="fuel_prices_idf",
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self._home_lat = home_lat
        self._home_lon = home_lon
        self._radius_km = radius_km
        self._session = async_get_clientsession(hass)

    def _build_url(self) -> str:
        where = " OR ".join(f'code_departement="{d}"' for d in IDF_DEPARTMENTS)
        select = (
            "id,adresse,ville,cp,code_departement,latitude,longitude,"
            "sp95_prix,sp98_prix,sp95_maj,sp98_maj"
        )
        from urllib.parse import urlencode

        qs = urlencode({"where": where, "select": select, "limit": 100, "offset": 0})
        return f"{API_BASE}?{qs}"

    async def _fetch_all(self) -> list[dict]:
        """Page through the API (100 rows/page) and return all IDF stations."""
        from urllib.parse import urlencode

        where = " OR ".join(f'code_departement="{d}"' for d in IDF_DEPARTMENTS)
        select = (
            "id,adresse,ville,cp,code_departement,latitude,longitude,"
            "sp95_prix,sp98_prix,sp95_maj,sp98_maj"
        )
        results: list[dict] = []
        offset = 0
        while True:
            qs = urlencode(
                {"where": where, "select": select, "limit": 100, "offset": offset}
            )
            url = f"{API_BASE}?{qs}"
            async with async_timeout.timeout(30):
                resp = await self._session.get(url)
                resp.raise_for_status()
                payload = await resp.json()
            batch = payload.get("results", [])
            results.extend(batch)
            total = payload.get("total_count", len(results))
            offset += 100
            if offset >= total or not batch or offset > 2000:
                break
        return results

    @staticmethod
    def _to_deg(raw) -> float | None:
        """Convert PTV_GEODECIMAL (value * 1e5) to WGS84 degrees."""
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return None
        if v == 0:
            return None
        # v2 API already returns decimal degrees for latitude/longitude.
        # Guard against the legacy *1e5 encoding just in case.
        if abs(v) > 180:
            v = v / 100000.0
        return v

    async def _async_update_data(self) -> dict:
        try:
            raw = await self._fetch_all()
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Error fetching fuel prices: {err}") from err

        stations: list[dict] = []
        for s in raw:
            lat = self._to_deg(s.get("latitude"))
            lon = self._to_deg(s.get("longitude"))
            if lat is None or lon is None:
                continue
            dist = _haversine_km(self._home_lat, self._home_lon, lat, lon)
            stations.append(
                {
                    "id": s.get("id"),
                    "address": s.get("adresse"),
                    "city": s.get("ville"),
                    "postal_code": s.get("cp"),
                    "department": s.get("code_departement"),
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    "distance_km": round(dist, 2),
                    "sp95": s.get("sp95_prix"),
                    "sp98": s.get("sp98_prix"),
                    "sp95_updated": s.get("sp95_maj"),
                    "sp98_updated": s.get("sp98_maj"),
                }
            )

        data: dict = {"station_count": len(stations)}

        for fuel in FUELS:
            priced = [st for st in stations if st.get(fuel)]
            # Regional average.
            if priced:
                data[f"avg_{fuel}"] = round(
                    sum(st[fuel] for st in priced) / len(priced), 3
                )
            else:
                data[f"avg_{fuel}"] = None

            # Nearest station selling this fuel.
            if priced:
                nearest = min(priced, key=lambda st: st["distance_km"])
                data[f"nearest_{fuel}"] = {
                    "price": nearest[fuel],
                    "distance_km": nearest["distance_km"],
                    "city": nearest["city"],
                    "address": nearest["address"],
                    "postal_code": nearest["postal_code"],
                    "latitude": nearest["latitude"],
                    "longitude": nearest["longitude"],
                    "updated": nearest.get(f"{fuel}_updated"),
                }
            else:
                data[f"nearest_{fuel}"] = None

            # Cheapest station within radius.
            in_radius = [st for st in priced if st["distance_km"] <= self._radius_km]
            if in_radius:
                cheapest = min(in_radius, key=lambda st: st[fuel])
                data[f"cheapest_{fuel}"] = {
                    "price": cheapest[fuel],
                    "distance_km": cheapest["distance_km"],
                    "city": cheapest["city"],
                    "address": cheapest["address"],
                    "postal_code": cheapest["postal_code"],
                    "latitude": cheapest["latitude"],
                    "longitude": cheapest["longitude"],
                    "updated": cheapest.get(f"{fuel}_updated"),
                }
            else:
                data[f"cheapest_{fuel}"] = None

        # Full list of stations within the radius (any fuel) — for a markers map.
        in_radius_all = [st for st in stations if st["distance_km"] <= self._radius_km]
        in_radius_all.sort(key=lambda st: st["distance_km"])
        data["stations_in_radius"] = [
            {
                "latitude": st["latitude"],
                "longitude": st["longitude"],
                "city": st["city"],
                "address": st["address"],
                "postal_code": st["postal_code"],
                "distance_km": st["distance_km"],
                "sp95": st.get("sp95"),
                "sp98": st.get("sp98"),
            }
            for st in in_radius_all
        ]
        data["stations_in_radius_count"] = len(in_radius_all)
        data["home_latitude"] = self._home_lat
        data["home_longitude"] = self._home_lon
        data["radius_km"] = self._radius_km

        return data
