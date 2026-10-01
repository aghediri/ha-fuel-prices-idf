/*
 * Fuel Prices Île-de-France — custom Lovelace card
 * A self-contained card (no build step) that renders the SP95/SP98 regional
 * averages plus the nearest and cheapest stations with distance + address.
 *
 * Install:
 *   1. Copy this file into your HA  config/www/  folder
 *      (so it is served at  /local/fuel-prices-idf-card.js ).
 *   2. Settings → Dashboards → ⋮ → Resources → + Add Resource
 *      → URL  /local/fuel-prices-idf-card.js , type JavaScript Module.
 *   3. Hard-refresh the browser (Ctrl+Shift+R).
 *
 * Minimal config:
 *   type: custom:fuel-prices-idf-card
 * Optional overrides (defaults shown):
 *   title: Fuel Prices — Île-de-France
 *   avg_sp95: sensor.fuel_prices_ile_de_france_average_sp95_ile_de_france
 *   avg_sp98: sensor.fuel_prices_ile_de_france_average_sp98_ile_de_france
 *   nearest_sp95: sensor.fuel_prices_ile_de_france_nearest_sp95
 *   nearest_sp98: sensor.fuel_prices_ile_de_france_nearest_sp98
 *   cheapest_sp95: sensor.fuel_prices_ile_de_france_cheapest_sp95_within_radius
 *   cheapest_sp98: sensor.fuel_prices_ile_de_france_cheapest_sp98_within_radius
 */

const DEFAULTS = {
  title: "Fuel Prices — Île-de-France",
  avg_sp95: "sensor.fuel_prices_ile_de_france_average_sp95_ile_de_france",
  avg_sp98: "sensor.fuel_prices_ile_de_france_average_sp98_ile_de_france",
  nearest_sp95: "sensor.fuel_prices_ile_de_france_nearest_sp95",
  nearest_sp98: "sensor.fuel_prices_ile_de_france_nearest_sp98",
  cheapest_sp95: "sensor.fuel_prices_ile_de_france_cheapest_sp95_within_radius",
  cheapest_sp98: "sensor.fuel_prices_ile_de_france_cheapest_sp98_within_radius",
};

class FuelPricesIdfCard extends HTMLElement {
  setConfig(config) {
    this._config = { ...DEFAULTS, ...(config || {}) };
    this._root = this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  _num(entity) {
    const s = this._hass && this._hass.states[entity];
    if (!s || s.state === "unknown" || s.state === "unavailable") return null;
    const v = parseFloat(s.state);
    return isNaN(v) ? null : v;
  }

  _attr(entity, key) {
    const s = this._hass && this._hass.states[entity];
    return s && s.attributes ? s.attributes[key] : undefined;
  }

  _price(v) {
    return v == null ? "—" : v.toFixed(3) + " €/L";
  }

  _mapsUrl(entity) {
    const lat = this._attr(entity, "latitude");
    const lon = this._attr(entity, "longitude");
    if (lat == null || lon == null) return null;
    return `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;
  }

  _stationLine(entity) {
    const city = this._attr(entity, "city");
    const addr = this._attr(entity, "address");
    const dist = this._attr(entity, "distance_km");
    const parts = [];
    if (addr) parts.push(addr);
    if (city) parts.push(city);
    let line = parts.join(", ");
    if (dist != null) line += `${line ? " · " : ""}${dist} km`;
    return line || "No station data";
  }

  _render() {
    if (!this._hass) return;
    const c = this._config;

    const avg95 = this._num(c.avg_sp95);
    const avg98 = this._num(c.avg_sp98);

    const cell = (label, entity, variant) => {
      const price = this._num(entity);
      const sub = this._stationLine(entity);
      const url = this._mapsUrl(entity);
      const linkOpen = url ? `<a href="${url}" target="_blank" rel="noopener">` : "<span>";
      const linkClose = url ? "</a>" : "</span>";
      return `
        <div class="cell ${variant}">
          <div class="cell-label">${label}</div>
          <div class="cell-price">${this._price(price)}</div>
          <div class="cell-sub">${linkOpen}${sub}${linkClose}</div>
        </div>`;
    };

    const updated =
      this._attr(c.nearest_sp95, "last_price_update") ||
      this._attr(c.nearest_sp98, "last_price_update") ||
      "";
    const count = this._attr(c.nearest_sp95, "station_count") || "";

    this._root.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 16px; }
        .title { font-size: 1.1rem; font-weight: 600; margin-bottom: 12px; }
        .avg-row { display: flex; gap: 12px; margin-bottom: 16px; }
        .avg {
          flex: 1; border-radius: 12px; padding: 12px 14px;
          background: var(--primary-color, #03a9f4);
          color: var(--text-primary-color, #fff);
        }
        .avg.b { background: var(--accent-color, #ff9800); }
        .avg .k { font-size: .75rem; opacity: .85; letter-spacing: .04em; text-transform: uppercase; }
        .avg .v { font-size: 1.6rem; font-weight: 700; margin-top: 2px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .cell {
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 10px; padding: 10px 12px;
          background: var(--card-background-color, #fff);
        }
        .cell-label { font-size: .72rem; text-transform: uppercase; letter-spacing: .04em;
          color: var(--secondary-text-color, #727272); }
        .cell-price { font-size: 1.25rem; font-weight: 700; margin: 2px 0;
          color: var(--primary-text-color, #212121); }
        .cell.cheap .cell-price { color: var(--success-color, #43a047); }
        .cell-sub { font-size: .8rem; color: var(--secondary-text-color, #727272); }
        .cell-sub a { color: var(--primary-color, #03a9f4); text-decoration: none; }
        .cell-sub a:hover { text-decoration: underline; }
        .footer { margin-top: 12px; font-size: .72rem; color: var(--secondary-text-color, #9e9e9e); }
      </style>
      <ha-card>
        <div class="title">${c.title}</div>
        <div class="avg-row">
          <div class="avg a"><div class="k">Avg SP95 · IDF</div><div class="v">${this._price(avg95)}</div></div>
          <div class="avg b"><div class="k">Avg SP98 · IDF</div><div class="v">${this._price(avg98)}</div></div>
        </div>
        <div class="grid">
          ${cell("Nearest SP95", c.nearest_sp95, "near")}
          ${cell("Nearest SP98", c.nearest_sp98, "near")}
          ${cell("Cheapest SP95", c.cheapest_sp95, "cheap")}
          ${cell("Cheapest SP98", c.cheapest_sp98, "cheap")}
        </div>
        <div class="footer">
          ${count ? `${count} stations` : ""}${count && updated ? " · " : ""}${updated ? `updated ${new Date(updated).toLocaleString()}` : ""}
          · Data: prix-carburants.gouv.fr
        </div>
      </ha-card>`;
  }
}

customElements.define("fuel-prices-idf-card", FuelPricesIdfCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "fuel-prices-idf-card",
  name: "Fuel Prices Île-de-France Card",
  description: "SP95/SP98 regional averages, nearest and cheapest stations.",
  preview: true,
});
