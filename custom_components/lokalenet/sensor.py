"""Sensors for the LokaleNET integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import LokaleNetData
from .coordinator import LokaleNetConfigEntry
from .entity import LokaleNetEntity

PARALLEL_UPDATES = 0

CURRENCY = "PLN"


@dataclass(frozen=True, kw_only=True)
class LokaleNetSensorDescription(SensorEntityDescription):
    value_fn: Callable[[LokaleNetData], float | int | date | None]
    attrs_fn: Callable[[LokaleNetData], dict[str, Any]] | None = None


def _money(**kwargs: Any) -> dict[str, Any]:
    return {
        "device_class": SensorDeviceClass.MONETARY,
        "native_unit_of_measurement": CURRENCY,
        "suggested_display_precision": 2,
        **kwargs,
    }


def _last_payment_attrs(data: LokaleNetData) -> dict[str, Any]:
    payment = data.last_payment
    if payment is None:
        return {}
    return {"paid_on": payment.due, "booked_on": payment.booked}


def _due_attrs(data: LokaleNetData) -> dict[str, Any]:
    charge = data.last_charge
    return {"due_date": charge.due if charge else None}


def _charge_attrs(data: LokaleNetData) -> dict[str, Any]:
    return {
        "items": {item.name: item.amount for item in data.charge_items},
        "monthly_charges": data.monthly_charges,
    }


def _settlement_attrs(data: LokaleNetData) -> dict[str, Any]:
    settlement = data.last_settlement
    if settlement is None:
        return {}
    return {
        "name": settlement.name,
        "period_start": settlement.period_start,
        "period_end": settlement.period_end,
        "costs": settlement.costs,
        "advances": settlement.advances,
    }


SENSORS: tuple[LokaleNetSensorDescription, ...] = (
    LokaleNetSensorDescription(
        key="balance",
        value_fn=lambda data: data.balance,
        **_money(),
    ),
    LokaleNetSensorDescription(
        key="amount_due",
        value_fn=lambda data: data.amount_due,
        attrs_fn=_due_attrs,
        **_money(),
    ),
    LokaleNetSensorDescription(
        key="due_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda data: data.last_charge.due if data.last_charge else None,
    ),
    LokaleNetSensorDescription(
        key="monthly_charge",
        value_fn=lambda data: data.monthly_charge,
        attrs_fn=_charge_attrs,
        **_money(),
    ),
    LokaleNetSensorDescription(
        key="last_payment",
        value_fn=lambda data: data.last_payment.payment if data.last_payment else None,
        attrs_fn=_last_payment_attrs,
        **_money(),
    ),
    LokaleNetSensorDescription(
        key="last_payment_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda data: data.last_payment_date,
    ),
    LokaleNetSensorDescription(
        key="last_settlement",
        value_fn=lambda data: (
            data.last_settlement.result if data.last_settlement else None
        ),
        attrs_fn=_settlement_attrs,
        **_money(),
    ),
    LokaleNetSensorDescription(
        key="notices",
        value_fn=lambda data: data.notices,
    ),
    LokaleNetSensorDescription(
        key="votes",
        value_fn=lambda data: data.votes,
    ),
    LokaleNetSensorDescription(
        key="statement_date",
        device_class=SensorDeviceClass.DATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.statement_date,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LokaleNetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        LokaleNetSensor(coordinator, description) for description in SENSORS
    )


class LokaleNetSensor(LokaleNetEntity, SensorEntity):
    """A value read from the portal."""

    entity_description: LokaleNetSensorDescription

    def __init__(self, coordinator, description: LokaleNetSensorDescription) -> None:
        super().__init__(coordinator, "sensor", description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | date | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
