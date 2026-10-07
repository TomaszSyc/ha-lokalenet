# Współtworzenie

Integrację sprawdzałem na jednym koncie w portalu LokaleNET, a zarządcy mogą prowadzić
w nim różne widoki. Najbardziej pomaga więc raport od innego zarządcy, także wtedy, gdy
wszystko działa.

## Zgłoszenia

- **Inny zarządca**: jak integracja działa na koncie u innego zarządcy niż testowany
- **Błąd**: coś nie działa; dołącz wersje integracji i Home Assistanta oraz logi
- **Propozycja**: pomysł na rozszerzenie

Problemu bezpieczeństwa nie opisuj publicznie. Jak go zgłosić, mówi
[SECURITY.md](SECURITY.md).

## Zanim coś wkleisz

Zgłoszenia są publiczne, a ich treść od razu trafia do powiadomień, więc późniejsza edycja
jej nie cofnie. Nie wklejaj identyfikatora, hasła, adresu lokalu, numeru rachunku, nazwy
wspólnoty, sald ani kwot. W logach zamień je na zmyślone wartości, np. `12345678`.

Diagnostykę integracji (Ustawienia → Urządzenia i usługi → LokaleNET → ⋮ → Pobierz
diagnostykę) możesz dołączyć w całości. Są w niej tylko liczby wierszy i adres portalu,
bez kwot, dat, identyfikatora i hasła.

## Zmiany w kodzie

Przy większej zmianie najpierw załóż propozycję, żeby nie pisać czegoś, czego nie przyjmę.

Testy importują integrację wobec przypiętej wersji Home Assistanta, która wymaga Pythona
3.14:

```bash
pip install -r requirements-dev.txt
pre-commit install
ruff check . && ruff format --check .
pytest tests/ -q
```

`pre-commit install` włącza też gitleaks i sprawdzenie prywatnej listy zakazanych
wartości ze zmiennej `LOKALENET_DENYLIST` albo pliku `~/.config/lokalenet/denylist`
— to plik spoza repozytorium, bo taka lista nie może w nim leżeć. Bez niego ten drugi
hak nic nie blokuje.

Testy nie łączą się z prawdziwym portalem. Logowanie i odczyt widoków sprawdza podstawiony
portal z `tests/fake_portal.py`, uruchamiany na `127.0.0.1`. Jeśli zmiana opiera się na
jakimś zachowaniu portalu, najpierw odtwórz je tam. Każda zmiana zachowania potrzebuje
testu, który bez niej nie przechodzi.

- Podnieś wersję w `custom_components/lokalenet/manifest.json`, rośnie z każdym commitem.
- Teksty interfejsu są w `strings.json`, `translations/en.json` i `translations/pl.json`
  i muszą się zgadzać.
- Opis commita to jedna linia po angielsku z prefiksem, np. `fix:`, `feat:`, `docs:`.

## Założenia, których nie zmieniam

- Integracja tylko czyta. Nie przyjmę niczego, co płaci, głosuje albo składa wniosek.
- Widok salda z opisami nie jest pobierany, bo zawiera numer rachunku wpłacającego.
- Identyfikator i hasło podaje się tylko w konfiguracji integracji. Trafiają wyłącznie do
  wskazanego portalu, zawsze przez HTTPS, i nie mogą pojawić się w logach, atrybutach
  encji ani diagnostyce.
- Portal jest odpytywany co 6 godzin. Zarządcy wprowadzają wyciągi bankowe najwyżej kilka
  razy w tygodniu, więc częstsze logowanie nic nie daje.

## Kodeks postępowania

Obowiązuje [Contributor Covenant 2.1](CODE_OF_CONDUCT.md) w angielskim oryginale.
Oficjalnego tłumaczenia na polski nie ma.
