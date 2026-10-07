# LokaleNET (MMSoft) for Home Assistant

Reads your account in [LokaleNET](https://mmsoft.com.pl/lokale.php), the resident portal that
housing communities and property administrators run on MMSoft's *Lokale* software.

The integration only reads the portal. It never pays, votes or files a request.

## Entities

Entity ids are fixed and do not depend on the identifier or the UI language, so dashboards can
be written before the account is added. A second account gets the usual `_2` suffix.

| Entity | Meaning |
|---|---|
| `sensor.lokalenet_balance` | Positive is money owed, negative is an overpayment |
| `sensor.lokalenet_amount_due` | What is left to pay now; attribute `due_date` |
| `sensor.lokalenet_due_date` | Due date of the latest charge |
| `sensor.lokalenet_monthly_charge` | Current monthly charge; attributes `items` (its lines) and `monthly_charges` (charged per month, `YYYY-MM`) |
| `sensor.lokalenet_last_payment` | The most recent payment the administrator booked; attributes `paid_on`, `booked_on` |
| `sensor.lokalenet_last_payment_date` | When it was paid (the booking date if the portal does not say) |
| `sensor.lokalenet_last_settlement` | Result of the latest settlement; positive means you pay more, negative is an overpayment. Attributes `name`, `period_start`, `period_end`, `costs`, `advances` |
| `sensor.lokalenet_notices` | Entries in the portal's notices view |
| `sensor.lokalenet_votes` | Resolutions listed in the portal's votes view, open or not |
| `sensor.lokalenet_statement_date` | Date of the latest bank statement the administrator imported |
| `button.lokalenet_refresh` | Reads the portal right away |

With more than one premises on the account, the balance and the monthly charge are the totals
of all of them.

The portal's ledger covers the current year only. The last payment is therefore remembered
between refreshes and restarts, so it does not disappear on 1 January; `monthly_charges` does
start over with the new year.

The portal is read every 6 hours. Each refresh logs in, reads four views and logs out again.

## Installation

Add this repository to HACS as a custom repository (or copy `custom_components/lokalenet` into
your Home Assistant `custom_components` folder), restart, then add **LokaleNET** under
*Settings → Devices & services*. Use the identifier and password from your administrator.

A new portal address or identifier is changed with *Reconfigure* on the integration; the
entities keep their ids.

## Diagnostics

Downloaded diagnostics contain counts only (ledger rows, charge lines, settlements, notices,
votes) and the portal address. Amounts, dates, the identifier and the password are left out.

---|---|
| Balance | Positive is money owed, negative is an overpayment |
| Amount due | What is left to pay now, with the due date of the latest charge as an attribute |
| Payment due date | Due date of the latest charge |
| Monthly charge | Current monthly charge, its lines as an attribute |
| Last payment / Last payment date | The most recent payment the administrator booked |
| Last settlement | Result of the latest settlement; positive means you pay more, negative is an overpayment |
| Notices / Votes | Entries in the portal's notices and votes views |
| Last bank statement | Date of the latest bank statement the administrator imported |

The portal is read every 6 hours; the *Refresh* button reads it right away. Each refresh logs in,
reads four views and logs out again.

## Installation

Copy `custom_components/lokalenet` into your Home Assistant `custom_components` folder (or add this
repository to HACS as a custom repository), restart, then add **LokaleNET** under
*Settings → Devices & services*. Use the identifier and password from your administrator.

---

Integracja do Home Assistant dla portalu mieszkańca LokaleNET (MMSoft): saldo, kwota i termin
płatności, opłata miesięczna, ostatnia wpłata i ostatnie rozliczenie. Tylko odczyt.
