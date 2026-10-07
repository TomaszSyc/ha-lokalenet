"""A stand-in LokaleNET portal serving invented data in the real portal's markup."""

from __future__ import annotations

from urllib.parse import parse_qsl

from aiohttp import web

USERNAME = "jan.testowy"
PASSWORD = "haslo-testowe"
PATH = "/lokale.php"
# An old address of the portal on the same host, moved permanently to PATH.
OLD_PATH = "/stary.php"
ENCODING = "iso-8859-2"

SESSION_COOKIE = "PHPSESSID"


def _page(body: str, logged_in: bool) -> str:
    menu = (
        "<a href=\"javascript:akcja('Saldo',100)\">Saldo</a>"
        "<a href=\"javascript:akcja('Wylogowanie',0)\">WYLOGOWANIE</a>"
        if logged_in
        else '<input name="Adm" type="text"><input name="Pas" type="password">'
    )
    return (
        '<!DOCTYPE html><html><head><meta http-equiv="Content-Type" '
        'content="text/html; charset=iso-8859-2"></head><body>'
        f'<form name="FmLog" method="POST">{menu}</form>'
        f'<main><article id="odczyty">{body}</article></main></body></html>'
    )


def _ledger_row(
    booked: str, due: str, kind: str, doc: str, charge: str, paid: str
) -> str:
    return (
        f'<tr><th nowrap style="text-align: center;">{booked}</th>'
        f'<td nowrap style="text-align: center;">{due}</td>'
        f'<td nowrap style="text-align: left;">{kind}</td>'
        f'<td nowrap style="text-align: left;">{doc}</td>'
        f'<td style="text-align: right;">{charge}</td>'
        f'<td style="text-align: right;">{paid}</td></tr>'
    )


def january_balance_page() -> str:
    """The ledger after the new year: nothing paid yet, so no payment to show."""
    rows = _ledger_row(
        "2031-01-01", "", "Bilans otwarcia", "Nowy rok", "75,50", " "
    ) + _ledger_row(
        "2031-01-01", "2031-01-15", "Naliczona zaliczka", "I.2031", "200,00", " "
    )
    return balance_page(rows=rows, total="275,50 zł")


def balance_page(
    label: str = "Zaległość", total: str = "75,50 zł", rows: str | None = None
) -> str:
    rows = rows or "".join(
        [
            _ledger_row("2030-01-01", "", "Bilans otwarcia", "Nowy rok", " ", "12,00"),
            _ledger_row(
                "2030-01-01",
                "2030-01-15",
                "Naliczona zaliczka",
                "I.2030",
                "200,00",
                " ",
            ),
            (
                '<tr><th> </th><td> </td><td colspan="2">Opłata za styczeń</td>'
                '<td colspan="2"> </td></tr>'
            ),
            _ledger_row("2030-01-20", "2030-01-14", "Bank przyjął", "", " ", "136,50"),
            _ledger_row(
                "2030-02-01",
                "2030-02-15",
                "Naliczona zaliczka",
                "II.2030",
                "200,00",
                " ",
            ),
            _ledger_row(
                "2030-02-18", "2030-02-12", "Bank przyjął", "", " ", "1 200,00"
            ),
            _ledger_row(
                "2030-03-01",
                "2030-03-15",
                "Naliczona zaliczka",
                "III.2030",
                "200,00",
                " ",
            ),
        ]
    )
    return (
        "<h1>Saldo | Rok bieżący</h1>"
        "<h3>Data ostatniego wprowadzonego wyciągu bankowego: 2030-02-20</h3>"
        '<table class="table"><thead><tr><th>Data dok</th><th>Data zapł</th>'
        "<th>Symbol</th><th>Dokument</th><th>Do zapł.</th><th>Wpłaty</th></tr></thead>"
        f"<tbody>{rows}</tbody>"
        '<tfoot><tr><td><b>Razem</b></td><td colspan="2"><b>-</b></td>'
        f'<td style="text-align: right;"><b>{label}</b></td>'
        f'<td colspan="2" style="text-align: right;" nowrap><b>{total}</b></td></tr></tfoot>'
        "</table>"
    )


def _settlement(
    name: str, start: str, end: str, costs: str, adv: str, label: str, res: str
) -> str:
    return (
        f'<table class="table"><thead><tr><th colspan="8">{name}</th></tr></thead><tbody>'
        '<tr><td colspan="8">Koszty utrzymania</td></tr>'
        f"<tr><td>Rozliczenie za okres {start} do {end}</td><td>1</td><td>Lok.</td><td>*</td>"
        f"<td>{costs}</td><td>=</td><td></td><td>{costs} zł</td></tr>"
        f'<tr><td colspan="5"><b>Koszty poniesione</b></td><td>=</td><td></td><td><b>{costs} zł</b></td></tr>'
        f'<tr><td colspan="5"><b>Zaliczki naliczone</b></td><td>=</td><td></td><td><b>{adv} zł</b></td></tr>'
        f'</tbody><tfoot><tr><td colspan="5"><b>{label}</b></td><td>=</td><td></td>'
        f"<td><b>{res} zł</b></td></tr></tfoot></table>"
    )


def charges_page() -> str:
    return (
        "<h2>Miesięczna stawka</h2><h3>Lokal testowy</h3>"
        '<table class="table"><thead><tr><th>Opłaty</th><th colspan="7"> </th></tr></thead><tbody>'
        '<tr><td style="height:0px;"> </td><td colspan="7"> </td></tr>'
        '<tr><td colspan="8"><b>Fundusz eksploatacyjny</b></td></tr>'
        "<tr><td>Eksploatacja</td><td>1</td><td>Lok.</td><td>*</td><td>150,00</td>"
        "<td>=</td><td></td><td>150,00 zł</td></tr>"
        "<tr><td>Fundusz remontowy</td><td>50</td><td>m2</td><td>*</td><td>1,00</td>"
        "<td>=</td><td></td><td>50,00 zł</td></tr>"
        '</tbody><tfoot><tr><td colspan="5"><b>Razem </b></td><td>=</td><td></td>'
        "<td><b>200,00 zł</b></td></tr></tfoot></table>"
        "<h2>Rozliczenia</h2><h3>Lokal testowy</h3>"
        + _settlement(
            "Rozliczenie II 2029",
            "2029-07-01",
            "2029-12-31",
            "1 300,00",
            "1 200,00",
            "Razem do zapłaty z rozliczenia",
            "100,00",
        )
        + _settlement(
            "Rozliczenie I 2029",
            "2029-01-01",
            "2029-06-30",
            "1 150,00",
            "1 200,00",
            "Razem nadpłata z rozliczenia",
            "50,00",
        )
    )


def empty_list_page(title: str) -> str:
    return f"<h1>{title}</h1>"


def notices_page() -> str:
    return (
        '<h1>Informacje</h1><table class="table"><tbody>'
        "<tr><td>2030-02-01</td><td>Przegląd kominiarski</td></tr>"
        "<tr><td>2030-02-10</td><td>Wymiana wodomierzy</td></tr>"
        "</tbody></table>"
    )


class FakePortal:
    """Serves the login form and the read-only views; records every form it gets."""

    def __init__(self) -> None:
        self.base = ""
        self.forms: list[dict[str, str]] = []
        self.accounts = {USERNAME: PASSWORD}
        self.balance = balance_page()
        self.charges = charges_page()
        self.notices = notices_page()
        self.votes = empty_list_page("Głosowania")
        self.fail_status: int | None = None
        # A page that is neither the login form nor a logged-in page, served for everything:
        # a maintenance notice, or a wrong address that still answers 200.
        self.down_page: str | None = None
        # Views before which the portal forgets the session, once each.
        self.drop_session_before: list[str] = []
        # Where to send every request, with what status, instead of answering it.
        self.redirect: tuple[int, str] | None = None
        self._sessions: set[str] = set()
        self._next = 0

    @property
    def url(self) -> str:
        return f"{self.base}{PATH}"

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_route("*", PATH, self._handle)
        app.router.add_route("*", OLD_PATH, self._moved)
        return app

    def _reply(self, body: str, logged_in: bool, session: str) -> web.Response:
        response = web.Response(
            body=_page(body, logged_in).encode(ENCODING),
            content_type="text/html",
            charset=ENCODING,
        )
        response.set_cookie(SESSION_COOKIE, session)
        return response

    async def _moved(self, request: web.Request) -> web.Response:
        return web.Response(status=308, headers={"Location": PATH})

    async def _handle(self, request: web.Request) -> web.Response:
        if self.fail_status:
            return web.Response(status=self.fail_status)
        if self.redirect:
            status, location = self.redirect
            return web.Response(status=status, headers={"Location": location})
        if self.down_page is not None:
            self.forms.append({"down": request.method})
            return web.Response(
                body=self.down_page.encode(ENCODING), content_type="text/html"
            )
        session = request.cookies.get(SESSION_COOKIE)
        if not session:
            self._next += 1
            session = f"s{self._next}"
        if request.method == "GET":
            return self._reply("<h1>Logowanie</h1>", False, session)

        raw = await request.read()
        form = dict(
            parse_qsl(raw.decode("ascii"), keep_blank_values=True, encoding=ENCODING)
        )
        self.forms.append(form)
        if "Adm" in form:
            if self.accounts.get(form["Adm"]) == form["Pas"]:
                self._sessions.add(session)
                return self._reply("<h1>Informacje</h1>", True, session)
            return self._reply("<h1>Logowanie</h1>", False, session)
        if form.get("akcja") in self.drop_session_before:
            self.drop_session_before.remove(form["akcja"])
            self._sessions.discard(session)
        if session not in self._sessions:
            return self._reply("<h1>Logowanie</h1>", False, session)
        views = {
            "Saldo": self.balance,
            "Naliczenie": self.charges,
            "Informacje": self.notices,
            "Uchwaly": self.votes,
        }
        if form.get("akcja") == "Wylogowanie":
            self._sessions.discard(session)
            return self._reply("<h1>Logowanie</h1>", False, session)
        return self._reply(views.get(form.get("akcja"), "<h1>?</h1>"), True, session)
