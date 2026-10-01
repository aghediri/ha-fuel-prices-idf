# Fuel Prices Île-de-France — Home Assistant integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/aghediri/ha-fuel-prices-idf/actions/workflows/validate.yml/badge.svg)](https://github.com/aghediri/ha-fuel-prices-idf/actions/workflows/validate.yml)

Tracks **SP95** and **SP98** petrol prices across **Île-de-France** using the official
French open data feed (`data.economie.gouv.fr`, Licence Ouverte). It exposes the daily
**regional average**, the **nearest** station to your home selling each fuel, and the
**cheapest** station within a configurable radius.

No API key, no account — the open-data API is free and refreshes every ~10 minutes.
This integration polls it every 30 minutes.

## Sensors

| Entity | Description | State | Key attributes |
|---|---|---|---|
| `sensor.average_sp95_ile_de_france` | Mean SP95 price across all open IDF stations | €/L | `station_count` |
| `sensor.average_sp98_ile_de_france` | Mean SP98 price across all open IDF stations | €/L | `station_count` |
| `sensor.nearest_sp95` | Price at the nearest station selling SP95 | €/L | `distance_km`, `city`, `address`, `postal_code`, `latitude`, `longitude`, `last_price_update` |
| `sensor.nearest_sp98` | Price at the nearest station selling SP98 | €/L | *(same as above)* |
| `sensor.cheapest_sp95_within_radius` | Lowest SP95 price within your radius | €/L | *(same as above)* |
| `sensor.cheapest_sp98_within_radius` | Lowest SP98 price within your radius | €/L | *(same as above)* |

Prices are in **euros per litre** with 3-decimal precision. Each station sensor carries
`latitude`/`longitude` so you can drop it straight onto a `map` card.

## Installation (HACS)

1. In Home Assistant, go to **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/aghediri/ha-fuel-prices-idf` with category **Integration**.
3. Search for **Fuel Prices Île-de-France**, install, and **restart** Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration → Fuel Prices Île-de-France**.
5. Set your **home location** on the map (defaults to Poissy) and a **search radius** (km).

### Manual installation
Copy `custom_components/fuel_prices_idf/` into your Home Assistant `config/custom_components/`
folder and restart.

## Configuration

Everything is configured from the UI (config flow). You can change the home location and
radius later via **Settings → Devices & Services → Fuel Prices Île-de-France → Configure**.

| Option | Default | Notes |
|---|---|---|
| Home location | 48.9289, 2.0486 (Poissy) | Used for distance / nearest / cheapest-in-radius |
| Search radius (km) | 15 | Scope of the "cheapest" sensors |

## Lovelace examples

### Price overview (entities card)
```yaml
type: entities
title: Fuel prices — Île-de-France
entities:
  - entity: sensor.average_sp95_ile_de_france
  - entity: sensor.average_sp98_ile_de_france
  - type: section
    label: Nearest to home
  - entity: sensor.nearest_sp95
    secondary_info: last-changed
  - entity: sensor.nearest_sp98
  - type: section
    label: Cheapest within radius
  - entity: sensor.cheapest_sp95_within_radius
  - entity: sensor.cheapest_sp98_within_radius
```

### Daily average trend (history / statistics)
Because the averages use `state_class: measurement`, Home Assistant records long-term
statistics automatically. Chart the daily variation with:
```yaml
type: statistics-graph
title: Daily average SP95 / SP98
period: day
stat_types:
  - mean
  - min
  - max
entities:
  - sensor.average_sp95_ile_de_france
  - sensor.average_sp98_ile_de_france
```

> **Tip — populated on day one.** On first setup the integration automatically
> backfills the current year's **daily SP95/SP98 averages** from the open-data
> archive (see *Historical backfill* below), so the `statistics-graph` card has
> months of history immediately. To chart the backfilled series directly, point
> the card at the external statistics ids `fuel_prices_idf:avg_sp95` and
> `fuel_prices_idf:avg_sp98`.

Or a quick rolling view:
```yaml
type: history-graph
hours_to_show: 720
entities:
  - sensor.average_sp95_ile_de_france
  - sensor.average_sp98_ile_de_france
```

### Cheapest station on a map
```yaml
type: map
title: Cheapest SP95 nearby
entities:
  - entity: sensor.cheapest_sp95_within_radius
  - entity: sensor.nearest_sp95
```

### "Should I fill up?" template (optional)
Add a binary flag that turns on when the nearest station beats the regional average:
```yaml
template:
  - binary_sensor:
      - name: "SP95 cheaper nearby"
        state: >
          {{ states('sensor.nearest_sp95') | float(0)
            < states('sensor.average_sp95_ile_de_france') | float(0) }}
```

## Custom Lovelace card

The integration bundles a self-contained custom card (no build step) showing the
SP95/SP98 regional averages plus the nearest and cheapest stations with distance,
address and a click-through to Google Maps.

It is served automatically at `/fuel_prices_idf/fuel-prices-idf-card.js`, and on
**storage-mode** dashboards the resource is **registered for you** on setup. If you
use **YAML-mode** Lovelace, add the resource manually:
```yaml
# configuration.yaml (or your lovelace: resources block)
lovelace:
  resources:
    - url: /fuel_prices_idf/fuel-prices-idf-card.js
      type: module
```

Then add the card:
```yaml
type: custom:fuel-prices-idf-card
# everything below is optional — these are the defaults:
title: Fuel Prices — Île-de-France
avg_sp95: sensor.average_sp95_ile_de_france
avg_sp98: sensor.average_sp98_ile_de_france
nearest_sp95: sensor.nearest_sp95
nearest_sp98: sensor.nearest_sp98
cheapest_sp95: sensor.cheapest_sp95_within_radius
cheapest_sp98: sensor.cheapest_sp98_within_radius
```
The card is theme-aware (uses your HA theme variables) and appears in the card
picker as **“Fuel Prices Île-de-France Card”**.

## Historical backfill

So the daily-average trend isn't empty on day one, the integration imports the
**current year's daily SP95/SP98 averages** as Home Assistant *long-term statistics*,
parsed from the official yearly open-data archive
(`https://donnees.roulez-eco.fr/opendata/annee/<year>`). This runs **automatically
once** on first setup (in the background — the live sensors are available immediately).

The data is stored as external statistics under:
- `fuel_prices_idf:avg_sp95`
- `fuel_prices_idf:avg_sp98`

Chart them in a `statistics-graph` card (period `day`, stat types mean/min/max).

### Backfill earlier years
Call the service for any year back to 2007 (safe to re-run — it upserts):
```yaml
service: fuel_prices_idf.backfill_statistics
data:
  year: 2025
```
> The archive is a large (~300 MB uncompressed) XML; a backfill takes a minute or
> two and parses on a background executor so it won't block Home Assistant.

## Data source & licence

Data from the French government fuel-price open data service, redistributed under the
**Licence Ouverte / Open Licence**:
- Dataset: *Prix des carburants en France — flux instantané v2*
- Portal: <https://data.economie.gouv.fr/explore/dataset/prix-des-carburants-en-france-flux-instantane-v2/>
- Official site: <https://www.prix-carburants.gouv.fr/rubrique/opendata/>

Station **brand/name** are intentionally not published in the open data; sensors identify
stations by **address + city + postal code**.

## License

MIT © aghediri
