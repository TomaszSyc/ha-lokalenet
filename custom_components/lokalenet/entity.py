"""Base entity for the LokaleNET integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LokaleNetCoordinator


class LokaleNetEntity(CoordinatorEntity[LokaleNetCoordinator]):
    """An entity of one resident account."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: LokaleNetCoordinator, platform: str, key: str
    ) -> None:
        super().__init__(coordinator)
        # Ids that do not depend on the login or the UI language, so dashboards can name them
        # before the account is added. A second account gets the usual numeric suffix.
        self.entity_id = f"{platform}.{DOMAIN}_{key}"
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"LokaleNET {entry.title}",
            manufacturer="MMSoft",
            model="LokaleNET",
            entry_type=DeviceEntryType.SERVICE,
        )
