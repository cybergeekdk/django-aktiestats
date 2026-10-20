# Aktiestat

Django 6.1-projekt der viser live aktiestatistik (kurs, ændring, dagens høj/lav, volumen, markedsværdi m.m.) via Yahoo Finance (`yfinance`).

## Kom i gang

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Åbn http://127.0.0.1:8000/ – tabellen opdateres hvert 15. sekund.

## API

- `GET /api/quote/AAPL/` – statistik for ét symbol
- `GET /api/quotes/?symbols=AAPL,NOVO-B.CO` – flere symboler på én gang

Danske aktier har suffikset `.CO` (fx `VWS.CO`). Kurser caches i 15 sek. (`QUOTE_CACHE_SECONDS`).

## Test

```bash
python manage.py test
```

Bemærk: Yahoo Finance er en uofficiel datakilde uden SLA – brug den til læring/prototyper.
