"""Diagnostics for the LokaleNET integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import LokaleNetConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, "title", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LokaleNetConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data.data
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        # Counts and shapes only: amounts and dates describe somebody's finances and are
        # not needed to tell whether the parser still understands the pages.
        "data": {
            "transactions": len(data.transactions),
            "charge_items": len(data.charge_items),
            "settlements": len(data.settlements),
            "has_statement_date": data.statement_date is not None,
            "has_last_payment": data.last_payment is not None,
            "has_last_charge": data.last_charge is not None,
            "notices": data.notices,
            "votes": data.votes,
            "settlement_fields": [
                sorted(k for k, v in asdict(s).items() if v is not None)
                for s in data.settlements
            ],
        }
        if data
        else None,
    }
