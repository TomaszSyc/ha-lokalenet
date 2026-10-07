"""Polling coordinator for the LokaleNET integration."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    LokaleNetAuthError,
    LokaleNetClient,
    LokaleNetConnectionError,
    LokaleNetData,
    LokaleNetParseError,
    Transaction,
)
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type LokaleNetConfigEntry = ConfigEntry[LokaleNetCoordinator]

STORAGE_VERSION = 1


def payment_store(hass: HomeAssistant, entry: ConfigEntry) -> Store[dict[str, Any]]:
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")


def _to_json(payment: Transaction) -> dict[str, Any]:
    return {
        key: value.isoformat() if isinstance(value, date) else value
        for key, value in asdict(payment).items()
    }


def _from_json(stored: dict[str, Any]) -> Transaction:
    return Transaction(
        booked=date.fromisoformat(stored["booked"]),
        due=date.fromisoformat(stored["due"]) if stored["due"] else None,
        kind=stored["kind"],
        document=stored["document"],
        charge=stored["charge"],
        payment=stored["payment"],
    )


class LokaleNetCoordinator(DataUpdateCoordinator[LokaleNetData]):
    """Fetches the whole account in one go."""

    config_entry: LokaleNetConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: LokaleNetConfigEntry, client: LokaleNetClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self._store = payment_store(hass, entry)
        self._kept_payment: Transaction | None = None

    async def async_restore(self) -> None:
        """Load the payment kept from earlier refreshes, before the first one."""
        stored = await self._store.async_load()
        if stored and stored.get("last_payment"):
            self._kept_payment = _from_json(stored["last_payment"])

    async def _async_update_data(self) -> LokaleNetData:
        data = await self._fetch()
        data.earlier_payment = self._kept_payment
        newest = data.last_payment_in_ledger
        if newest is not None and newest != self._kept_payment:
            self._kept_payment = newest
            await self._store.async_save({"last_payment": _to_json(newest)})
        return data

    async def _fetch(self) -> LokaleNetData:
        try:
            return await self.client.fetch()
        except LokaleNetAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except LokaleNetConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except LokaleNetParseError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="parse_failed",
                translation_placeholders={"error": str(err)},
            ) from err
