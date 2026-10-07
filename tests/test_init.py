"""Setting the integration up and the entities it creates."""

from __future__ import annotations

from fake_portal import january_balance_page
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD
from homeassistant.helpers import entity_registry as er

from custom_components.lokalenet.const import DOMAIN
from custom_components.lokalenet.diagnostics import async_get_config_entry_diagnostics


def _state(hass, key: str):
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"127.0.0.1:jan.testowy_{key}"
    )
    assert entity_id, key
    return hass.states.get(entity_id)


async def test_sensors(
    hass, enable_custom_integrations, portal, client_factory, entry
) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert _state(hass, "balance").state == "75.5"
    assert _state(hass, "amount_due").state == "75.5"
    assert _state(hass, "amount_due").attributes["due_date"].isoformat() == "2030-03-15"
    assert _state(hass, "due_date").state == "2030-03-15"
    assert _state(hass, "monthly_charge").state == "200.0"
    assert _state(hass, "monthly_charge").attributes["items"] == {
        "Eksploatacja": 150.0,
        "Fundusz remontowy": 50.0,
    }
    assert (
        _state(hass, "monthly_charge").attributes["monthly_charges"]["2030-02"] == 200.0
    )
    assert _state(hass, "last_payment").state == "1200.0"
    assert _state(hass, "last_payment_date").state == "2030-02-12"
    assert _state(hass, "last_settlement").state == "100.0"
    assert _state(hass, "last_settlement").attributes["name"] == "Rozliczenie II 2029"
    assert _state(hass, "notices").state == "2"
    assert _state(hass, "votes").state == "0"
    assert _state(hass, "statement_date").state == "2030-02-20"
    assert _state(hass, "balance").attributes["unit_of_measurement"] == "PLN"
    # Fixed ids, so dashboards can be written before the account exists.
    assert hass.states.get("sensor.lokalenet_amount_due").state == "75.5"
    assert hass.states.get("button.lokalenet_refresh")


async def test_wrong_password_starts_reauth(
    hass, enable_custom_integrations, portal, client_factory, entry
) -> None:
    data = dict(entry.data)
    data[CONF_PASSWORD] = "zle"
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, data=data)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]


async def test_portal_down_retries(
    hass, enable_custom_integrations, portal, client_factory, entry
) -> None:
    portal.fail_status = 502
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_diagnostics_hold_no_amounts(
    hass, enable_custom_integrations, portal, client_factory, entry
) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diag)
    assert "haslo-testowe" not in text
    assert "jan.testowy" not in text
    for amount in ("75.5", "1200", "200.0", "2030-"):
        assert amount not in text
    assert diag["data"]["transactions"] == 6


async def test_unload(
    hass, enable_custom_integrations, portal, client_factory, entry
) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_last_payment_survives_the_new_year(
    hass, enable_custom_integrations, portal, client_factory, entry
) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The ledger only shows the current year: after 1 January the payment is not in it.
    portal.balance = january_balance_page()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, "balance").state == "275.5"
    assert _state(hass, "last_payment").state == "1200.0"
    assert _state(hass, "last_payment_date").state == "2030-02-12"

    # A restart in January must not forget it either.
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _state(hass, "last_payment").state == "1200.0"
    assert _state(hass, "last_payment_date").state == "2030-02-12"


async def test_removing_the_account_forgets_the_payment(
    hass, enable_custom_integrations, portal, client_factory, entry, hass_storage
) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert f"{DOMAIN}.{entry.entry_id}" in hass_storage

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert f"{DOMAIN}.{entry.entry_id}" not in hass_storage
