/*
 * Fuel Stations Map — Île-de-France
 * Plots EVERY station within your radius (from the
 * `sensor.*_stations_in_radius` entity's `stations` attribute) on a Leaflet
 * map, colour-coded by cheapest SP95 price, with your home marked. This shows
 * all stations — including ones that only sell SP98 (e.g. the Poissy
 * TotalEnergies / Maladrerie) — not just the nearest/cheapest sensors.
 *
 * Install:
 *   1. Copy this file into your HA  config/www/  folder
 *      (served at  /local/fuel-stations-map-card.js ).
 *   2. Settings → Dashboards → ⋮ → Resources → + Add Resource
 *      → URL  /local/fuel-stations-map-card.js , type JavaScript Module.
 *   3. Hard-refresh (Ctrl+Shift+R).
 *
 * Config:
 *   type: custom:fuel-stations-map-card
 *   entity: sensor.fuel_prices_ile_de_france_stations_in_radius   # required
 *   title: Stations dans le rayon        # optional
 *   height: 420                          # optional (px)
 *   fuel: sp95                           # optional: sp95 | sp98 (price shown/colour)
 */

const LEAFLET_CSS = "https://cdn.jsdelivr.net/npm/leaflet@1/dist/leaflet.css";
const LEAFLET_JS = "https://cdn.jsdelivr.net/npm/leaflet@1/dist/leaflet.js";

class FuelStationsMapCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("fuel-stations-map-card: 'entity' is required");
    }
    this._config = {
      title: "Stations dans le rayon",
      height: 420,
      fuel: "sp95",
      ...config,
    };
    this.attachShadow({ mode: "open" });
    this._map = null;
    this._markers = [];
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) {
      this._build();
      this._built = true;
    }
    this._update();
  }

  getCardSize() {
    return 6;
  }

  async _ensureLeaflet() {
    if (window.L) return;
    // CSS
    if (!document.querySelector(`link[href="${LEAFLET_CSS}"]`)) {
      const l = document.createElement("link");
      l.rel = "stylesheet";
      l.href = LEAFLET_CSS;
      document.head.appendChild(l);
    }
    // JS
    if (!window.__leafletLoading) {
      window.__leafletLoading = new Promise((res, rej) => {
        const s = document.createElement("script");
        s.src = LEAFLET_JS;
        s.onload = res;
        s.onerror = rej;
        document.head.appendChild(s);
      });
    }
    await window.__leafletLoading;
  }

  _build() {
    const c = this._config;
    this.shadowRoot.innerHTML = `
      <style>
        @import url("${LEAFLET_CSS}");
        ha-card { overflow: hidden; }
        .title { padding: 12px 16px 0; font-size: 1.05rem; font-weight: 600; }
        #map { width: 100%; height: ${c.height}px; margin-top: 8px; }
        .legend { padding: 6px 16px 12px; font-size: .75rem; color: var(--secondary-text-color,#777); }
      </style>
      <ha-card>
        <div class="title">${c.title}</div>
        <div id="map"></div>
        <div class="legend">● vert = moins cher · ● rouge = plus cher · 🏠 domicile · données: prix-carburants.gouv.fr</div>
      </ha-card>`;
    this._mapEl = this.shadowRoot.getElementById("map");
  }

  async _update() {
    const st = this._hass && this._hass.states[this._config.entity];
    if (!st || !st.attributes || !Array.isArray(st.attributes.stations)) return;
    const a = st.attributes;
    const stations = a.stations;
    const fuel = this._config.fuel === "sp98" ? "sp98" : "sp95";

    await this._ensureLeaflet();
    const L = window.L;
    if (!this._map) {
      const clat = a.home_latitude ?? 48.9289;
      const clon = a.home_longitude ?? 2.0486;
      this._map = L.map(this._mapEl).setView([clat, clon], 11);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "© OpenStreetMap",
      }).addTo(this._map);
      // home marker
      L.circleMarker([clat, clon], {
        radius: 8, color: "#1565C0", fillColor: "#2196F3", fillOpacity: 1, weight: 2,
      }).addTo(this._map).bindPopup("🏠 Domicile");
    }
    // clear old markers
    this._markers.forEach((m) => this._map.removeLayer(m));
    this._markers = [];

    // price range for colour scale (over selected fuel)
    const priced = stations.filter((s) => s[fuel] != null);
    const prices = priced.map((s) => s[fuel]);
    const min = Math.min(...prices), max = Math.max(...prices);
    const color = (p) => {
      if (p == null || max === min) return "#9e9e9e";
      const t = (p - min) / (max - min); // 0 cheapest → 1 priciest
      const r = Math.round(60 + t * 180), g = Math.round(180 - t * 140);
      return `rgb(${r},${g},60)`;
    };

    const bounds = [];
    stations.forEach((s) => {
      if (s.latitude == null || s.longitude == null) return;
      const p = s[fuel];
      const m = L.circleMarker([s.latitude, s.longitude], {
        radius: 7,
        color: "#333",
        weight: 1,
        fillColor: color(p),
        fillOpacity: 0.9,
      }).addTo(this._map);
      const label =
        `<b>${s.address || ""}</b><br>${s.postal_code || ""} ${s.city || ""}` +
        `<br>SP95: ${s.sp95 != null ? s.sp95.toFixed(3) + " €/L" : "—"}` +
        `<br>SP98: ${s.sp98 != null ? s.sp98.toFixed(3) + " €/L" : "—"}` +
        `<br>${s.distance_km != null ? s.distance_km + " km" : ""}`;
      m.bindPopup(label);
      this._markers.push(m);
      bounds.push([s.latitude, s.longitude]);
    });
    if (bounds.length) {
      try { this._map.fitBounds(bounds, { padding: [30, 30], maxZoom: 13 }); } catch (e) {}
    }
    setTimeout(() => this._map && this._map.invalidateSize(), 50);
  }
}

customElements.define("fuel-stations-map-card", FuelStationsMapCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "fuel-stations-map-card",
  name: "Fuel Stations Map (Île-de-France)",
  description: "Plots every station within your radius, colour-coded by price.",
});
