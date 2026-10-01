"""Historical backfill of daily SP95 / SP98 regional averages.

Parses the yearly open-data archive (ZIP of a single large XML) from
donnees.roulez-eco.fr, computes the daily mean SP95 and SP98 price across all
Île-de-France stations, and injects the series as Home Assistant *external
statistics*. This gives the `statistics-graph` Lovelace card months of history
immediately after install, instead of waiting for the sensors to accumulate it.

External statistics are keyed under the domain (e.g. ``fuel_prices_idf:avg_sp95``)
and are independent of the live sensor entities, so re-running is idempotent
(``async_add_external_statistics`` upserts by start time).
"""
from __future__ import annotations

import io
import logging
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import async_timeout
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
)
from homeassistant.const import UnitOfVolume  # noqa: F401  (kept for reference)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, IDF_DEPARTMENTS

_LOGGER = logging.getLogger(__name__)

ARCHIVE_URL = "https://donnees.roulez-eco.fr/opendata/annee/{year}"
CURRENCY_EUR_PER_L = "€/L"

# External statistic ids (must be "<domain>:<object_id>").
STAT_IDS = {
    "sp95": f"{DOMAIN}:avg_sp95",
    "sp98": f"{DOMAIN}:avg_sp98",
}


async def async_backfill_statistics(hass: HomeAssistant, year: int) -> dict[str, int]:
    """Download, parse and import one year's daily averages. Returns counts."""
    session = async_get_clientsession(hass)
    url = ARCHIVE_URL.format(year=year)
    _LOGGER.info("Fuel Prices IDF: downloading yearly archive %s", url)

    async with async_timeout.timeout(180):
        resp = await session.get(url)
        resp.raise_for_status()
        raw = await resp.read()

    # Parsing a ~300MB XML is CPU-bound — run it in the executor.
    daily = await hass.async_add_executor_job(_parse_archive, raw)

    counts: dict[str, int] = {}
    for fuel, series in daily.items():
        stat_id = STAT_IDS[fuel]
        metadata = StatisticMetaData(
            has_mean=True,
            has_sum=False,
            name=f"Average {fuel.upper()} (Île-de-France)",
            source=DOMAIN,
            statistic_id=stat_id,
            unit_of_measurement=CURRENCY_EUR_PER_L,
        )
        stats: list[StatisticData] = []
        for day in sorted(series):
            vals = series[day]
            mean = sum(vals) / len(vals)
            start = datetime(
                day.year, day.month, day.day, 0, 0, tzinfo=timezone.utc
            )
            stats.append(
                StatisticData(
                    start=start,
                    mean=round(mean, 3),
                    min=round(min(vals), 3),
                    max=round(max(vals), 3),
                )
            )
        if stats:
            async_add_external_statistics(hass, metadata, stats)
            counts[fuel] = len(stats)
            _LOGGER.info(
                "Fuel Prices IDF: imported %d daily points for %s", len(stats), fuel
            )
    return counts


def _parse_archive(raw: bytes) -> dict[str, dict]:
    """Stream-parse the archive XML -> {fuel: {date: [prices...]}} for IDF."""
    idf_prefixes = tuple(IDF_DEPARTMENTS)
    # fuel -> date(date) -> list of prices (we keep per-day values to derive mean/min/max)
    daily: dict[str, dict] = {"sp95": defaultdict(list), "sp98": defaultdict(list)}

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as fh:
            for event, elem in ET.iterparse(fh, events=("end",)):
                if elem.tag != "pdv":
                    continue
                cp = elem.get("cp", "") or ""
                if cp[:2] in idf_prefixes:
                    for prix in elem.findall("prix"):
                        nom = prix.get("nom", "")
                        key = {"SP95": "sp95", "SP98": "sp98"}.get(nom)
                        if not key:
                            continue
                        maj = prix.get("maj", "")
                        val = prix.get("valeur", "")
                        if not (maj and val):
                            continue
                        try:
                            v = float(val)
                        except ValueError:
                            continue
                        if v > 10:  # legacy cents encoding (e.g. 1799 -> 1.799)
                            v = v / 1000.0
                        day_str = maj[:10].replace("/", "-")
                        try:
                            d = datetime.strptime(day_str, "%Y-%m-%d").date()
                        except ValueError:
                            continue
                        daily[key][d].append(v)
                elem.clear()
    return daily
