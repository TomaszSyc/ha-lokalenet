"""Client for the LokaleNET resident portal by MMSoft.

The portal has no API: every page is server-rendered HTML in ISO-8859-2, and every view is
reached by POSTing the menu form (`akcja` + `Szczeg`) back to the same address. Only views
are read here -- nothing that pays, votes or files a request is ever sent.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlencode

import aiohttp
from yarl import URL

_LOGGER = logging.getLogger(__name__)

ENCODING = "iso-8859-2"
TIMEOUT = aiohttp.ClientTimeout(total=30)

# Balance view without descriptions: the descriptive variant repeats the sender's bank
# account number on every payment, which there is no reason to download at all.
BALANCE_VIEW = {"akcja": "Saldo", "Szczeg": "3", "Opcja": "0"}
CHARGES_VIEW = {"akcja": "Naliczenie", "Szczeg": "0"}
NOTICES_VIEW = {"akcja": "Informacje", "Szczeg": "0"}
VOTES_VIEW = {"akcja": "Uchwaly", "Szczeg": "0"}
LOGOUT = {"akcja": "Wylogowanie", "Szczeg": "0"}

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# One amount: digits with spaces or dots between groups, a decimal part, and a minus in
# front or -- the way some ledgers write a credit -- behind it.
_AMOUNT = re.compile(r"(-\s*)?(\d(?:[\d.,]|\s(?=\d))*)(\s*-)?")
_SETTLEMENTS_HEADING = re.compile(r"<h2\b[^>]*>\s*Rozliczenia\s*</h2>", re.IGNORECASE)
_LOGIN_FORM = re.compile(r"""name=["']?Pas\b""", re.IGNORECASE)

_REDIRECTS = frozenset({301, 302, 303, 307, 308})
_MAX_REDIRECTS = 5


class LokaleNetError(Exception):
    """Base error."""


class LokaleNetAuthError(LokaleNetError):
    """The portal refused the identifier or password."""


class LokaleNetConnectionError(LokaleNetError):
    """The portal could not be reached or answered with an HTTP error."""


class LokaleNetParseError(LokaleNetError):
    """A page no longer looks the way the parser expects."""


class _SessionLost(LokaleNetError):
    """A view came back as the login page: the portal forgot the session midway."""


@dataclass(frozen=True)
class Transaction:
    """One row of the balance ledger."""

    booked: date
    due: date | None
    kind: str
    document: str
    charge: float | None
    payment: float | None


@dataclass(frozen=True)
class Settlement:
    """A periodic settlement of advance payments against real costs."""

    name: str
    period_start: date | None
    period_end: date | None
    costs: float | None
    advances: float | None
    # Positive means the resident pays more, negative means an overpayment returned.
    result: float


@dataclass(frozen=True)
class ChargeItem:
    """One line of the monthly charge."""

    name: str
    amount: float


@dataclass
class LokaleNetData:
    """Everything read in one refresh."""

    # Positive is money owed, negative is an overpayment.
    balance: float
    statement_date: date | None
    transactions: list[Transaction] = field(default_factory=list)
    monthly_charge: float | None = None
    charge_items: list[ChargeItem] = field(default_factory=list)
    settlements: list[Settlement] = field(default_factory=list)
    notices: int = 0
    votes: int = 0
    # The newest payment seen in an earlier refresh. The ledger only covers the current
    # year, so in January it often has no payment at all.
    earlier_payment: Transaction | None = None

    @property
    def amount_due(self) -> float:
        """What is left to pay now; an overpayment means nothing is due."""
        return max(self.balance, 0.0)

    @property
    def last_payment_in_ledger(self) -> Transaction | None:
        # A negative payment is money returned to the resident, not paid by them.
        payments = [
            t
            for t in self.transactions
            if t.payment and t.payment > 0 and t.kind.lower() != "bilans otwarcia"
        ]
        return max(payments, key=lambda t: t.booked) if payments else None

    @property
    def last_payment(self) -> Transaction | None:
        return self.last_payment_in_ledger or self.earlier_payment

    @property
    def last_payment_date(self) -> date | None:
        """When it was paid; the booking date when the portal leaves that column empty."""
        payment = self.last_payment
        return (payment.due or payment.booked) if payment else None

    @property
    def last_charge(self) -> Transaction | None:
        charges = [t for t in self.transactions if t.charge and t.due is not None]
        charges = [t for t in charges if "naliczon" in t.kind.lower()]
        return max(charges, key=lambda t: t.booked) if charges else None

    @property
    def monthly_charges(self) -> dict[str, float]:
        """What was charged in each month of the ledger, settlement corrections included.

        Keyed 'YYYY-MM' by the booking date; the opening balance is carried over from the
        previous year, not charged, so it is left out.
        """
        months: dict[str, float] = {}
        for t in self.transactions:
            if t.charge is None or t.kind.lower() == "bilans otwarcia":
                continue
            key = t.booked.strftime("%Y-%m")
            months[key] = round(months.get(key, 0.0) + t.charge, 2)
        return dict(sorted(months.items()))

    @property
    def last_settlement(self) -> Settlement | None:
        # The portal lists settlements newest first.
        return self.settlements[0] if self.settlements else None


def parse_amount(text: str) -> float | None:
    """'1 234,56 zł' -> 1234.56; empty cells come back as None."""
    match = _AMOUNT.search(text.replace("\u2212", "-"))
    if not match:
        return None
    number = re.sub(r"\s", "", match.group(2))
    if "," in number:
        number = number.replace(".", "").replace(",", ".")
    try:
        value = float(number)
    except ValueError:
        return None
    return -value if match.group(1) or match.group(3) else value


def parse_date(text: str) -> date | None:
    match = _DATE.search(text)
    return date.fromisoformat(match.group()) if match else None


def _text(fragment: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(plain)).strip()


def _rows(fragment: str) -> list[list[str]]:
    rows = []
    for row in re.findall(
        r"<tr\b[^>]*>(.*?)</tr>", fragment, flags=re.DOTALL | re.IGNORECASE
    ):
        cells = re.findall(
            r"<t[hd]\b[^>]*>(.*?)</t[hd]>", row, flags=re.DOTALL | re.IGNORECASE
        )
        rows.append([_text(cell) for cell in cells])
    return rows


def _sections(page: str, tag: str) -> list[str]:
    return re.findall(
        rf"<{tag}\b[^>]*>(.*?)</{tag}>", page, flags=re.DOTALL | re.IGNORECASE
    )


def _section(page: str, tag: str) -> str:
    found = _sections(page, tag)
    return found[0] if found else ""


def _tables(page: str) -> list[str]:
    return re.findall(r"<table\b.*?</table>", page, flags=re.DOTALL | re.IGNORECASE)


def _article(page: str) -> str:
    article = _section(page, "article")
    if not article:
        raise LokaleNetParseError("page has no content section")
    return article


def is_logged_in(page: str) -> bool:
    return "akcja('Wylogowanie'" in page


def is_login_form(page: str) -> bool:
    return bool(_LOGIN_FORM.search(page))


def parse_balance(page: str) -> tuple[float, date | None, list[Transaction]]:
    """Balance, date of the last imported bank statement, and the ledger rows."""
    article = _article(page)
    statement = re.search(r"wyci\w+ bankowego:\s*(\d{4}-\d{2}-\d{2})", _text(article))
    statement_date = date.fromisoformat(statement.group(1)) if statement else None

    # One table per premises when the account has more than one, each with its own total.
    feet = [rows for rows in map(_rows, _sections(article, "tfoot")) if rows]
    if not feet:
        raise LokaleNetParseError("balance total not found")
    balance = 0.0
    for foot in feet:
        total = foot[-1]
        amount = parse_amount(total[-1])
        if amount is None:
            raise LokaleNetParseError("balance total is not a number")
        label = " ".join(total[:-1]).lower()
        if "nadp" in label:
            amount = -abs(amount)
        elif "zaleg" not in label and amount:
            _LOGGER.debug("Unrecognised balance label %r, treating it as owed", label)
        balance += amount

    transactions = []
    rows = [row for body in _sections(article, "tbody") for row in _rows(body)]
    for cells in rows:
        if len(cells) != 6 or not _DATE.fullmatch(cells[0]):
            continue
        transactions.append(
            Transaction(
                booked=date.fromisoformat(cells[0]),
                due=parse_date(cells[1]),
                kind=cells[2],
                document=cells[3],
                charge=parse_amount(cells[4]),
                payment=parse_amount(cells[5]),
            )
        )
    return round(balance, 2), statement_date, transactions


def parse_charges(page: str) -> tuple[float | None, list[ChargeItem], list[Settlement]]:
    """Monthly charge with its lines, and the settlements listed below it."""
    article = _article(page)
    head, *rest = _SETTLEMENTS_HEADING.split(article, maxsplit=1)

    monthly = None
    items = []
    for table in _tables(head):
        for cells in _rows(_section(table, "tbody")):
            if len(cells) == 8 and (amount := parse_amount(cells[-1])) is not None:
                items.append(ChargeItem(name=cells[0], amount=amount))
        foot = _rows(_section(table, "tfoot"))
        if foot and (total := parse_amount(foot[-1][-1])) is not None:
            monthly = round((monthly or 0.0) + total, 2)

    settlements = []
    for table in _tables(rest[0] if rest else ""):
        name = _text(_section(table, "thead"))
        period_start = period_end = costs = advances = None
        for cells in _rows(_section(table, "tbody")):
            first = cells[0].lower() if cells else ""
            if first.startswith("rozliczenie za okres"):
                dates = _DATE.findall(cells[0])
                if len(dates) == 2:
                    period_start, period_end = (date.fromisoformat(d) for d in dates)
            elif first.startswith("koszty poniesione"):
                costs = parse_amount(cells[-1])
            elif first.startswith("zaliczki naliczone"):
                advances = parse_amount(cells[-1])
        foot = _rows(_section(table, "tfoot"))
        if not foot or (result := parse_amount(foot[-1][-1])) is None:
            continue
        if "nadp" in foot[-1][0].lower():
            result = -abs(result)
        settlements.append(
            Settlement(name, period_start, period_end, costs, advances, result)
        )
    return monthly, items, settlements


def parse_count(page: str) -> int:
    """Entries listed in a notices or votes view; an empty view has no table rows."""
    article = _article(page)
    return sum(
        1 for body in _sections(article, "tbody") for cells in _rows(body) if any(cells)
    )


class LokaleNetClient:
    """Reads one resident account."""

    def __init__(
        self, session: aiohttp.ClientSession, url: str, login: str, password: str
    ) -> None:
        self._session = session
        self._url = URL(url)
        self._login = login
        self._password = password

    async def _post(self, form: dict[str, str]) -> str:
        body = urlencode(form, encoding=ENCODING)
        return await self._request(
            "POST",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    async def _request(self, method: str, **kwargs) -> str:
        """One request, following redirects only within the portal's origin.

        aiohttp would re-send the body of a 307/308 wherever it points, another host
        included -- and for the login that body is the password.
        """
        target = self._url
        for _ in range(_MAX_REDIRECTS + 1):
            if target.origin() != self._url.origin():
                raise LokaleNetConnectionError(
                    f"refused to follow a redirect away from the portal, to {target.origin()}"
                )
            try:
                async with self._session.request(
                    method, target, timeout=TIMEOUT, allow_redirects=False, **kwargs
                ) as response:
                    location = response.headers.get("Location")
                    if response.status in _REDIRECTS and location:
                        if response.status in (301, 302, 303):
                            method, kwargs = "GET", {}
                        target = target.join(URL(location))
                        continue
                    response.raise_for_status()
                    raw = await response.read()
            except (aiohttp.ClientError, TimeoutError) as err:
                raise LokaleNetConnectionError(str(err) or type(err).__name__) from err
            return raw.decode(ENCODING, errors="replace")
        raise LokaleNetConnectionError("the portal redirected too many times")

    async def _log_in(self) -> None:
        await self._request("GET")
        page = await self._post(
            {
                "Jezyk": "",
                "Jaklog": "0",
                "Adm": self._login,
                "Pas": self._password,
                "Key": "",
            }
        )
        if is_logged_in(page):
            return
        if is_login_form(page):
            raise LokaleNetAuthError("login refused")
        # A maintenance notice or a wrong address: nothing says the password was wrong.
        raise LokaleNetConnectionError("the portal answered with an unexpected page")

    async def _view(self, form: dict[str, str]) -> str:
        page = await self._post(form)
        if not is_logged_in(page):
            raise _SessionLost
        return page

    async def validate(self) -> None:
        """Log in and straight out again, to check the credentials."""
        await self._log_in()
        await self._log_out()

    async def _log_out(self) -> None:
        try:
            await self._post(LOGOUT)
        except LokaleNetConnectionError:
            _LOGGER.debug("Logout failed, the portal session will expire on its own")

    async def fetch(self) -> LokaleNetData:
        try:
            return await self._fetch_once()
        except _SessionLost:
            _LOGGER.debug("The portal ended the session midway, logging in again")
        try:
            return await self._fetch_once()
        except _SessionLost as err:
            raise LokaleNetConnectionError(
                "the portal keeps ending the session"
            ) from err

    async def _fetch_once(self) -> LokaleNetData:
        await self._log_in()
        try:
            balance, statement_date, transactions = parse_balance(
                await self._view(BALANCE_VIEW)
            )
            monthly, items, settlements = parse_charges(await self._view(CHARGES_VIEW))
            notices = parse_count(await self._view(NOTICES_VIEW))
            votes = parse_count(await self._view(VOTES_VIEW))
        finally:
            await self._log_out()
        return LokaleNetData(
            balance=balance,
            statement_date=statement_date,
            transactions=transactions,
            monthly_charge=monthly,
            charge_items=items,
            settlements=settlements,
            notices=notices,
            votes=votes,
        )
