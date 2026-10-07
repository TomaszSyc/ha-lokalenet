"""Fixtures serving the stand-in portal. The portal itself is in fake_portal.py."""

from __future__ import annotations

import aiohttp
import pytest
from aiohttp import web
from fake_portal import PASSWORD, USERNAME, FakePortal
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lokalenet.api import LokaleNetClient
from custom_components.lokalenet.const import CONF_URL, DOMAIN


async def _serve(fake: FakePortal) -> web.AppRunner:
    runner = web.AppRunner(fake.app())
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    fake.base = f"http://127.0.0.1:{runner.addresses[0][1]}"
    return runner


@pytest.fixture
async def portal(socket_enabled) -> FakePortal:
    # socket_enabled lifts the HA test plugin's socket block for this test only;
    # connections stay limited to 127.0.0.1.
    fake = FakePortal()
    runner = await _serve(fake)
    yield fake
    await runner.cleanup()


@pytest.fixture
async def other_portal(socket_enabled) -> FakePortal:
    """A second origin, on another port: somewhere a redirect must not take the password."""
    fake = FakePortal()
    runner = await _serve(fake)
    yield fake
    await runner.cleanup()


@pytest.fixture
async def http_session() -> aiohttp.ClientSession:
    # unsafe=True only because the test server is an IP address; the integration's own
    # jar refuses cookies from bare IPs.
    session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
    yield session
    await session.close()


@pytest.fixture
def client_factory(http_session, monkeypatch):
    """Make the integration build its clients on the test session."""

    def factory(hass, url, username, password):
        return LokaleNetClient(http_session, url, username, password)

    import custom_components.lokalenet as integration
    import custom_components.lokalenet.config_flow as flow

    monkeypatch.setattr(integration, "create_client", factory)
    monkeypatch.setattr(flow, "create_client", factory)
    return factory


@pytest.fixture
def entry(portal: FakePortal) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title=USERNAME,
        unique_id=f"127.0.0.1:{USERNAME}",
        data={CONF_URL: portal.url, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
