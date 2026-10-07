"""Parsing the portal's pages and talking to it."""

from __future__ import annotations

from datetime import date

import pytest
from fake_portal import (
    OLD_PATH,
    PASSWORD,
    PATH,
    USERNAME,
    balance_page,
    charges_page,
    empty_list_page,
    notices_page,
)

from custom_components.lokalenet.api import (
    LokaleNetAuthError,
    LokaleNetClient,
    LokaleNetConnectionError,
    LokaleNetData,
    LokaleNetParseError,
    Transaction,
    parse_amount,
    parse_balance,
    parse_charges,
    parse_count,
)


def _wrap(body: str) -> str:
    return f'<main><article id="odczyty">{body}</article></main>'


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("143,45", 143.45),
        ("1 234,56 zł", 1234.56),
        ("1\xa0234,56 zł", 1234.56),
        ("-19,82", -19.82),
        (" ", None),
        ("", None),
        ("-", None),
        # A typographic minus is still a minus.
        ("\u221219,82", -19.82),
        # A trailing minus, the way some ledgers write a credit.
        ("19,82-", -19.82),
        # Dots as thousands separators when the decimals follow a comma.
        ("1.234,56", 1234.56),
        ("143.45", 143.45),
        # Only the amount itself: the unit's digit is not part of it.
        ("12,00 zł / m2", 12.0),
        ("\u2009-\u20091\u202f234,56 zł", -1234.56),
    ],
)
def test_amounts_as_the_portal_writes_them(text: str, value: float | None) -> None:
    assert parse_amount(text) == value


def test_balance_owed() -> None:
    balance, statement, rows = parse_balance(_wrap(balance_page()))
    assert balance == 75.5
    assert statement == date(2030, 2, 20)
    # The description row under a charge is not a ledger entry.
    assert len(rows) == 6
    assert rows[1].due == date(2030, 1, 15)
    assert rows[4].payment == 1200.0


def test_overpayment_is_negative() -> None:
    balance, _, _ = parse_balance(_wrap(balance_page("Nadpłata", "40,00 zł")))
    assert balance == -40.0


def test_balance_without_total_is_a_parse_error() -> None:
    with pytest.raises(LokaleNetParseError):
        parse_balance(_wrap("<h1>Saldo</h1><table><tbody></tbody></table>"))


def test_page_without_content_is_a_parse_error() -> None:
    with pytest.raises(LokaleNetParseError):
        parse_balance("<html><body>maintenance</body></html>")


def test_charges_and_settlements() -> None:
    monthly, items, settlements = parse_charges(_wrap(charges_page()))
    assert monthly == 200.0
    assert [(i.name, i.amount) for i in items] == [
        ("Eksploatacja", 150.0),
        ("Fundusz remontowy", 50.0),
    ]
    assert len(settlements) == 2
    newest, older = settlements
    assert newest.name == "Rozliczenie II 2029"
    assert newest.period_start == date(2029, 7, 1)
    assert newest.period_end == date(2029, 12, 31)
    assert newest.costs == 1300.0
    assert newest.advances == 1200.0
    assert newest.result == 100.0
    # An overpayment comes back to the resident, so it carries the sign of a credit.
    assert older.result == -50.0


def test_balance_of_every_premises_is_added_up() -> None:
    # One table per premises: a flat that owes and a garage with an overpayment.
    page = _wrap(balance_page() + balance_page("Nadpłata", "40,00 zł"))
    balance, _, rows = parse_balance(page)
    assert balance == 35.5
    assert len(rows) == 12


def test_settlement_heading_with_attributes_and_spaces() -> None:
    page = charges_page().replace(
        "<h2>Rozliczenia</h2>", '<h2 class="naglowek"> Rozliczenia </H2>'
    )
    monthly, items, settlements = parse_charges(_wrap(page))
    assert monthly == 200.0
    assert len(items) == 2
    assert len(settlements) == 2


def test_monthly_charge_of_several_premises_is_rounded() -> None:
    first = charges_page().split("<h2>Rozliczenia</h2>")[0]
    second = first.replace("200,00 zł", "0,10 zł").replace("150,00 zł", "0,10 zł")
    third = first.replace("200,00 zł", "0,20 zł").replace("150,00 zł", "0,20 zł")
    monthly, _, _ = parse_charges(_wrap(second + third))
    assert monthly == 0.3


def test_entries_of_every_list_are_counted() -> None:
    assert parse_count(_wrap(notices_page() + notices_page())) == 4


def test_payment_without_payment_date_is_dated_by_booking() -> None:
    paid = Transaction(date(2030, 1, 20), None, "Bank przyjął", "", None, 100.0)
    data = LokaleNetData(balance=0.0, statement_date=None, transactions=[paid])
    assert data.last_payment_date == date(2030, 1, 20)


def test_refund_is_not_a_payment() -> None:
    paid = Transaction(
        date(2030, 1, 20), date(2030, 1, 19), "Bank przyjął", "", None, 100.0
    )
    refund = Transaction(date(2030, 2, 5), date(2030, 2, 5), "Zwrot", "", None, -40.0)
    data = LokaleNetData(balance=0.0, statement_date=None, transactions=[paid, refund])
    assert data.last_payment == paid


def test_earlier_payment_stands_in_for_an_empty_ledger() -> None:
    earlier = Transaction(
        date(2030, 12, 20), date(2030, 12, 19), "Bank przyjął", "", None, 200.0
    )
    data = LokaleNetData(balance=0.0, statement_date=None, earlier_payment=earlier)
    assert data.last_payment == earlier


def test_empty_list_counts_zero() -> None:
    assert parse_count(_wrap(empty_list_page("Głosowania"))) == 0


async def test_fetch_reads_every_view_and_logs_out(portal, http_session) -> None:
    client = LokaleNetClient(http_session, portal.url, USERNAME, PASSWORD)
    data = await client.fetch()

    assert data.balance == 75.5
    assert data.amount_due == 75.5
    assert data.last_charge.due == date(2030, 3, 15)
    # The opening balance is carried over, not paid.
    assert data.last_payment.payment == 1200.0
    assert data.last_payment.due == date(2030, 2, 12)
    assert data.monthly_charge == 200.0
    assert data.last_settlement.result == 100.0
    assert data.notices == 2
    assert data.votes == 0

    actions = [form.get("akcja") for form in portal.forms if "Adm" not in form]
    assert actions == ["Saldo", "Naliczenie", "Informacje", "Uchwaly", "Wylogowanie"]
    # The balance view without descriptions: those carry the payer's account number.
    assert portal.forms[1]["Szczeg"] == "3"


async def test_charges_by_month(portal, http_session) -> None:
    portal.balance = balance_page()
    data = await LokaleNetClient(http_session, portal.url, USERNAME, PASSWORD).fetch()
    # The opening balance on 1 January is carried over, not charged.
    assert data.monthly_charges == {
        "2030-01": 200.0,
        "2030-02": 200.0,
        "2030-03": 200.0,
    }


async def test_nothing_but_views_is_ever_sent(portal, http_session) -> None:
    client = LokaleNetClient(http_session, portal.url, USERNAME, PASSWORD)
    await client.fetch()
    sent = {form.get("akcja") for form in portal.forms if "Adm" not in form}
    assert sent <= {"Saldo", "Naliczenie", "Informacje", "Uchwaly", "Wylogowanie"}


async def test_overpayment_means_nothing_due(portal, http_session) -> None:
    portal.balance = balance_page("Nadpłata", "40,00 zł")
    data = await LokaleNetClient(http_session, portal.url, USERNAME, PASSWORD).fetch()
    assert data.balance == -40.0
    assert data.amount_due == 0.0


async def test_wrong_password(portal, http_session) -> None:
    client = LokaleNetClient(http_session, portal.url, USERNAME, "zle")
    with pytest.raises(LokaleNetAuthError):
        await client.validate()


async def test_http_error(portal, http_session) -> None:
    portal.fail_status = 503
    client = LokaleNetClient(http_session, portal.url, USERNAME, PASSWORD)
    with pytest.raises(LokaleNetConnectionError):
        await client.fetch()


async def test_logs_out_even_when_a_page_breaks(portal, http_session) -> None:
    # An empty content section, the way the portal answers a view it cannot show.
    portal.charges = ""
    client = LokaleNetClient(http_session, portal.url, USERNAME, PASSWORD)
    with pytest.raises(LokaleNetParseError):
        await client.fetch()
    assert portal.forms[-1].get("akcja") == "Wylogowanie"


async def test_unexpected_page_at_login_is_not_a_wrong_password(
    portal, http_session
) -> None:
    # Without the login form there is nothing to say the password was wrong; asking for it
    # again would stop all refreshes until someone typed it.
    portal.down_page = "<html><body><h1>Przerwa techniczna</h1></body></html>"
    client = LokaleNetClient(http_session, portal.url, USERNAME, PASSWORD)
    with pytest.raises(LokaleNetConnectionError):
        await client.validate()


async def test_login_form_again_means_wrong_password(portal, http_session) -> None:
    client = LokaleNetClient(http_session, portal.url, USERNAME, "zle")
    with pytest.raises(LokaleNetAuthError):
        await client.fetch()


async def test_session_lost_midway_logs_in_again(portal, http_session) -> None:
    portal.drop_session_before = ["Informacje"]
    data = await LokaleNetClient(http_session, portal.url, USERNAME, PASSWORD).fetch()
    # Read from the views, not from the login page that came back instead.
    assert data.notices == 2
    logins = [form for form in portal.forms if "Adm" in form]
    assert len(logins) == 2


async def test_session_lost_twice_is_an_error(portal, http_session) -> None:
    portal.drop_session_before = ["Informacje", "Saldo"]
    client = LokaleNetClient(http_session, portal.url, USERNAME, PASSWORD)
    with pytest.raises(LokaleNetConnectionError):
        await client.fetch()


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
async def test_password_never_follows_a_redirect_elsewhere(
    portal, other_portal, http_session, status
) -> None:
    portal.redirect = (status, other_portal.url)
    client = LokaleNetClient(http_session, portal.url, USERNAME, PASSWORD)
    with pytest.raises(LokaleNetConnectionError):
        await client.fetch()
    assert other_portal.forms == []


async def test_redirect_within_the_portal_is_followed(portal, http_session) -> None:
    # An address the administrator moved on the same host keeps working.
    client = LokaleNetClient(
        http_session, portal.url.replace(PATH, OLD_PATH), USERNAME, PASSWORD
    )
    data = await client.fetch()
    assert data.balance == 75.5
