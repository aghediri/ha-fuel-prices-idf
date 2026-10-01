"""Constants for the Fuel Prices Île-de-France integration."""
from __future__ import annotations

DOMAIN = "fuel_prices_idf"

# data.economie.gouv.fr Explore v2.1 API — "flux instantané v2" dataset
# (updated every ~10 minutes, columnar, filterable). No API key required.
API_BASE = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "prix-des-carburants-en-france-flux-instantane-v2/records"
)

# Île-de-France departments.
IDF_DEPARTMENTS = ["75", "77", "78", "91", "92", "93", "94", "95"]

# Fuels we track. Keys map to the dataset columns sp95_prix / sp98_prix.
FUELS = ["sp95", "sp98"]

# Config entry keys.
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_RADIUS_KM = "radius_km"
CONF_NAME = "name"

# Defaults — Poissy home (2 rue du Pont Ancien).
DEFAULT_NAME = "Fuel Prices IDF"
DEFAULT_LATITUDE = 48.9289
DEFAULT_LONGITUDE = 2.0486
DEFAULT_RADIUS_KM = 15.0

# Poll interval (minutes). API refreshes every ~10 min; 30 is polite.
UPDATE_INTERVAL_MINUTES = 30

ATTRIBUTION = "Data: prix-carburants.gouv.fr / data.economie.gouv.fr (Licence Ouverte)"
