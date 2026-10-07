"""Refresh button for the LokaleNET integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LokaleNetConfigEntry
from .entity import LokaleNetEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LokaleNetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        [LokaleNetRefreshButton(entry.runtime_data, "button", "refresh")]
    )


class LokaleNetRefreshButton(LokaleNetEntity, ButtonEntity):
    """Reads the portal now instead of waiting for the next poll."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
