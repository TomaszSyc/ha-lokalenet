"""Adding an account and logging in again."""

from __future__ import annotations

import pytest
from fake_portal import PASSWORD, USERNAME
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lokalenet.config_flow import account_id, normalise_url
from custom_components.lokalenet.const import CONF_URL, DOMAIN


@pytest.mark.parametrize(
    ("typed", "stored"),
    [
        ("mmsoft.example/lokale.php", "https://mmsoft.example/lokale.php"),
        ("  https://MMSOFT.example/lokale.php ", "https://mmsoft.example/lokale.php"),
        ("https://mmsoft.example:8443", "https://mmsoft.example:8443/"),
    ],
)
def test_address_in_one_form(typed: str, stored: str) -> None:
    assert normalise_url(typed) == stored


@pytest.mark.parametrize(
    ("typed", "error"),
    [
        ("http://mmsoft.example/lokale.php", "insecure_url"),
        ("https://jan:haslo@mmsoft.example/lokale.php", "invalid_url"),
        ("https://mmsoft.example/lokale.php?akcja=Saldo", "invalid_url"),
        ("https://", "invalid_url"),
    ],
)
def test_unusable_addresses(typed: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        normalise_url(typed)


async def _start(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def test_account_is_added(
    hass, enable_custom_integrations, portal, client_factory, monkeypatch
) -> None:
    # The form only takes https; the test portal is plain http on 127.0.0.1.
    import custom_components.lokalenet.config_flow as flow

    monkeypatch.setattr(flow, "normalise_url", lambda url: url)
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: portal.url, CONF_USERNAME: f" {USERNAME} ", CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    # Checking the login must not leave a session open on the portal.
    assert portal.forms[-1].get("akcja") == "Wylogowanie"


async def test_wrong_password_is_reported(
    hass, enable_custom_integrations, portal, client_factory, monkeypatch
) -> None:
    import custom_components.lokalenet.config_flow as flow

    monkeypatch.setattr(flow, "normalise_url", lambda url: url)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: portal.url, CONF_USERNAME: USERNAME, CONF_PASSWORD: "zle"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_http_address_is_refused(hass, enable_custom_integrations) -> None:
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "http://mmsoft.example/lokale.php",
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    assert result["errors"] == {CONF_URL: "insecure_url"}


async def test_reauth_stores_new_password(
    hass, enable_custom_integrations, portal, client_factory, entry
) -> None:
    entry.add_to_hass(hass)
    entry_data = dict(entry.data)
    entry_data[CONF_PASSWORD] = "stare"
    hass.config_entries.async_update_entry(entry, data=entry_data)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == PASSWORD


@pytest.fixture
def plain_http(monkeypatch) -> None:
    # The form only takes https; the test portals are plain http on 127.0.0.1.
    import custom_components.lokalenet.config_flow as flow

    monkeypatch.setattr(flow, "normalise_url", lambda url: url.strip())


async def test_reconfigure_moves_the_account_and_keeps_the_entities(
    hass,
    enable_custom_integrations,
    portal,
    other_portal,
    client_factory,
    entry,
    plain_http,
) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    before = {
        e.entity_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }

    # The administrator moved the portal and handed out a new identifier.
    other_portal.accounts = {"anna.testowa": "nowe-haslo"}
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: other_portal.url,
            CONF_USERNAME: "anna.testowa",
            CONF_PASSWORD: "nowe-haslo",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert entry.data[CONF_URL] == other_portal.url
    assert entry.data[CONF_USERNAME] == "anna.testowa"
    assert entry.unique_id.endswith(":anna.testowa")
    after = {
        e.entity_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    # Same entities under the same ids: dashboards keep working.
    assert after == before
    assert hass.states.get("sensor.lokalenet_balance").state == "75.5"
    assert any("Adm" in form for form in other_portal.forms)


async def test_reconfigure_rejects_a_wrong_password(
    hass, enable_custom_integrations, portal, client_factory, entry, plain_http
) -> None:
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: portal.url, CONF_USERNAME: USERNAME, CONF_PASSWORD: "zle"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_PASSWORD] == PASSWORD


async def test_reconfigure_onto_another_entry_is_refused(
    hass, enable_custom_integrations, portal, client_factory, entry, plain_http
) -> None:
    entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN,
        title="anna.testowa",
        unique_id=account_id(portal.url, "anna.testowa"),
        data={CONF_URL: portal.url, CONF_USERNAME: "anna.testowa", CONF_PASSWORD: "x"},
    )
    other.add_to_hass(hass)
    portal.accounts["anna.testowa"] = "x"
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: portal.url, CONF_USERNAME: "anna.testowa", CONF_PASSWORD: "x"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_configured"}
    assert entry.data[CONF_USERNAME] == USERNAME


async def test_unexpected_page_is_reported_as_unreachable(
    hass, enable_custom_integrations, portal, client_factory, plain_http
) -> None:
    portal.down_page = "<html><body>Przerwa techniczna</body></html>"
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: portal.url, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_same_account_twice_is_refused(
    hass, enable_custom_integrations, portal, client_factory, plain_http
) -> None:
    for username in (USERNAME, USERNAME.upper()):
        result = await _start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: portal.url, CONF_USERNAME: username, CONF_PASSWORD: PASSWORD},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
