# Zgłaszanie problemów bezpieczeństwa

## Jak zgłosić

**Nie zakładaj publicznego zgłoszenia.** Użyj
[prywatnego zgłoszenia podatności](https://github.com/TomaszSyc/ha-lokalenet/security/advisories/new)
— trafi wyłącznie do opiekuna repozytorium.

To projekt prowadzony po godzinach, więc nie obiecuję terminu odpowiedzi. Postaram się
odpisać w ciągu tygodnia.

## Czego dotyczy

Integracja trzyma **identyfikator i hasło do konta w portalu LokaleNET** i wysyła je
wyłącznie pod adres podany przy konfiguracji, zawsze przez HTTPS, nie podążając za
przekierowaniem poza ten adres. Zgłoszeń wartych uwagi szukałbym w:

- wycieku poświadczeń do logów, atrybutów encji, diagnostyki lub zgłoszeń błędów
- wysłaniu ich pod inny adres niż skonfigurowany portal
- wysłaniu do portalu czegokolwiek poza logowaniem, wylogowaniem i widokami do odczytu

## Czego nie dotyczy

Portal LokaleNET należy do firmy MMSoft i zarządców nieruchomości. **Podatności w samym
portalu zgłaszaj im, nie tutaj** — ten projekt tylko korzysta z tych samych zapytań, co
przeglądarka.

## Wspierane wersje

Poprawki wchodzą do najnowszego wydania. Starszych nie łatam.
