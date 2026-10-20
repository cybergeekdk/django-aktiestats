# Aktiestat

Django 6.1-projekt der viser live aktiestatistik (kurs, ændring, dagens høj/lav, volumen, markedsværdi m.m.) via Yahoo Finance (`yfinance`).

## Kom i gang

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Log ind på http://127.0.0.1:8000/ – siden opdaterer kurserne via AJAX hvert 15. sekund.
Søg en aktie frem, angiv antal (og evt. købskurs fra Nordnet), og den gemmes på din bruger.
Beholdninger kan også ses/redigeres i Django admin på `/admin/` (model "Beholdninger"). Opret flere brugere i admin for at give andre deres egen portefølje.

## API

Kræver login (session):

- `GET /api/quote/AAPL/` – statistik for ét symbol
- `GET /api/search/?q=vestas` – søg symboler på navn
- `GET /api/holdings/` – din portefølje med live kurs, værdi og gevinst/tab
- `POST /api/holdings/` – tilføj/opdatér `{symbol, name, quantity, purchase_price}`
- `DELETE /api/holdings/<id>/` – fjern en beholdning

Nordnet har intet offentligt API, så beholdninger indtastes manuelt. Danske aktier har suffikset `.CO` (fx `VWS.CO`). Kurser caches i 15 sek. (`QUOTE_CACHE_SECONDS`).

## Test

```bash
python manage.py test
```

Bemærk: Yahoo Finance er en uofficiel datakilde uden SLA – brug den til læring/prototyper.
