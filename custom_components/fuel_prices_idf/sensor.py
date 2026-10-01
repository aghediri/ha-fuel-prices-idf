"""Sensor platform for Fuel Prices Île-de-France."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import FuelPricesCoordinator

CURRENCY_EUR_PER_L = "€/L"


@dataclass(frozen=True, kw_only=True)
class FuelSensorDescription(SensorEntityDescription):
    """Describes a fuel-price sensor and how to read it from coordinator data."""

    value_fn: Callable[[dict], float | None] = lambda d: None
    attrs_fn: Callable[[dict], dict] = lambda d: {}


def _station_value(key: str):
    return lambda d: (d.get(key) or {}).get("price") if d.get(key) else None


def _station_attrs(key: str):
    def _fn(d: dict) -> dict:
        st = d.get(key)
        if not st:
            return {}
        return {
            "distance_km": st.get("distance_km"),
            "city": st.get("city"),
            "address": st.get("address"),
            "postal_code": st.get("postal_code"),
            "latitude": st.get("latitude"),
            "longitude": st.get("longitude"),
            "last_price_update": st.get("updated"),
        }

    return _fn


SENSORS: tuple[FuelSensorDescription, ...] = (
    # Regional averages.
    FuelSensorDescription(
        key="avg_sp95",
        translation_key="avg_sp95",
        name="Average SP95 (Île-de-France)",
        icon="mdi:gas-station",
        native_unit_of_measurement=CURRENCY_EUR_PER_L,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda d: d.get("avg_sp95"),
    ),
    FuelSensorDescription(
        key="avg_sp98",
        translation_key="avg_sp98",
        name="Average SP98 (Île-de-France)",
        icon="mdi:gas-station",
        native_unit_of_measurement=CURRENCY_EUR_PER_L,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda d: d.get("avg_sp98"),
    ),
    # Nearest station.
    FuelSensorDescription(
        key="nearest_sp95",
        translation_key="nearest_sp95",
        name="Nearest SP95",
        icon="mdi:map-marker-radius",
        native_unit_of_measurement=CURRENCY_EUR_PER_L,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=_station_value("nearest_sp95"),
        attrs_fn=_station_attrs("nearest_sp95"),
    ),
    FuelSensorDescription(
        key="nearest_sp98",
        translation_key="nearest_sp98",
        name="Nearest SP98",
        icon="mdi:map-marker-radius",
        native_unit_of_measurement=CURRENCY_EUR_PER_L,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=_station_value("nearest_sp98"),
        attrs_fn=_station_attrs("nearest_sp98"),
    ),
    # Cheapest station within radius.
    FuelSensorDescription(
        key="cheapest_sp95",
        translation_key="cheapest_sp95",
        name="Cheapest SP95 (within radius)",
        icon="mdi:cash-multiple",
        native_unit_of_measurement=CURRENCY_EUR_PER_L,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=_station_value("cheapest_sp95"),
        attrs_fn=_station_attrs("cheapest_sp95"),
    ),
    FuelSensorDescription(
        key="cheapest_sp98",
        translation_key="cheapest_sp98",
        name="Cheapest SP98 (within radius)",
        icon="mdi:cash-multiple",
        native_unit_of_measurement=CURRENCY_EUR_PER_L,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=_station_value("cheapest_sp98"),
        attrs_fn=_station_attrs("cheapest_sp98"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fuel price sensors."""
    coordinator: FuelPricesCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        FuelPriceSensor(coordinator, entry, desc) for desc in SENSORS
    ]
    entities.append(StationsInRadiusSensor(coordinator, entry))
    async_add_entities(entities)


class FuelPriceSensor(CoordinatorEntity[FuelPricesCoordinator], SensorEntity):
    """A single fuel-price sensor."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    entity_description: FuelSensorDescription

    def __init__(
        self,
        coordinator: FuelPricesCoordinator,
        entry: ConfigEntry,
        description: FuelSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Fuel Prices Île-de-France",
            manufacturer="prix-carburants.gouv.fr",
            model="Open Data v2",
            entry_type="service",
        )

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {}
        attrs = dict(self.entity_description.attrs_fn(self.coordinator.data))
        attrs["station_count"] = self.coordinator.data.get("station_count")
        return attrs


class StationsInRadiusSensor(CoordinatorEntity[FuelPricesCoordinator], SensorEntity):
    """Sensor whose state is the number of stations within the radius and whose
    attributes carry the full list (lat/lon/price per station) for a markers map."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:map-marker-multiple"
    _attr_translation_key = "stations_in_radius"
    _attr_name = "Stations in radius"

    def __init__(
        self,
        coordinator: FuelPricesCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_stations_in_radius"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Fuel Prices Île-de-France",
            manufacturer="prix-carburants.gouv.fr",
            model="Open Data v2",
            entry_type="service",
        )

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("stations_in_radius_count")

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {}
        return {
            "home_latitude": self.coordinator.data.get("home_latitude"),
            "home_longitude": self.coordinator.data.get("home_longitude"),
            "radius_km": self.coordinator.data.get("radius_km"),
            "stations": self.coordinator.data.get("stations_in_radius", []),
        }
