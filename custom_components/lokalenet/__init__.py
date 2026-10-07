"""The LokaleNET integration: balance and charges from the MMSoft resident portal."""

from __future__ import annotations

from aiohttp import CookieJar
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import LokaleNetClient
from .const import CONF_URL
from .coordinator import LokaleNetConfigEntry, LokaleNetCoordinator, payment_store

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]


def create_client(
    hass: HomeAssistant, url: str, username: str, password: str
) -> LokaleNetClient:
    # A session of its own: the portal keeps the login in a cookie, and the shared session
    # would hand that cookie to every other integration talking to the same host.
    session = async_create_clientsession(hass, cookie_jar=CookieJar())
    return LokaleNetClient(session, url, username, password)


async def async_setup_entry(hass: HomeAssistant, entry: LokaleNetConfigEntry) -> bool:
    client = create_client(
        hass, entry.data[CONF_URL], entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )
    coordinator = LokaleNetCoordinator(hass, entry, client)
    await coordinator.async_restore()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LokaleNetConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: LokaleNetConfigEntry) -> None:
    await payment_store(hass, entry).async_remove()
