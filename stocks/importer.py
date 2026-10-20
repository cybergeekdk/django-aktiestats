"""Import af Nordnets transaktions-CSV (tabulatorsepareret, ofte UTF-16)."""
import csv
import hashlib
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction as db_transaction

import yfinance as yf

from .models import Holding, Instrument, Transaction

BUY_TYPES = {"KØBT", "KØB"}
SELL_TYPES = {"SOLGT", "SALG"}


class ImportError_(Exception):
    pass


def _decode(raw: bytes) -> str:
    for enc in ("utf-16", "utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
        except UnicodeError:
            continue
        if "Transaktionstype" in text:
            return text
    raise ImportError_("Filen ligner ikke en Nordnet-transaktionsfil (mangler 'Transaktionstype').")


def _num(value: str) -> Decimal:
    value = (value or "").strip().replace("\xa0", "").replace(" ", "")
    if not value:
        return Decimal(0)
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    try:
        return Decimal(value)
    except InvalidOperation:
        raise ImportError_(f"Kunne ikke læse tal: {value!r}")


def parse_csv(raw: bytes) -> list[dict]:
    """Returnér køb/salg fra filen som ordbøger. Øvrige transaktionstyper ignoreres."""
    text = _decode(raw)
    delimiter = "\t" if "\t" in text.splitlines()[0] else ";"
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = next(reader)
    # 'Valuta' optræder flere gange; første er kursens valuta, anden er beløbets
    col = {}
    for i, name in enumerate(header):
        col.setdefault(name.strip(), i)
    needed = ["Handelsdag", "Transaktionstype", "ISIN", "Antal", "Kurs", "Beløb"]
    missing = [n for n in needed if n not in col]
    if missing:
        raise ImportError_(f"Manglende kolonner: {', '.join(missing)}")

    def get(row, name):
        i = col.get(name)
        return row[i].strip() if i is not None and i < len(row) else ""

    trades = []
    for row in reader:
        if not row:
            continue
        ttype = get(row, "Transaktionstype").upper()
        side = Transaction.BUY if ttype in BUY_TYPES else Transaction.SELL if ttype in SELL_TYPES else None
        if not side or not get(row, "ISIN"):
            continue
        nid = get(row, "Id") or hashlib.sha1("|".join(row).encode()).hexdigest()[:20]
        try:
            trade_date = date.fromisoformat(get(row, "Handelsdag"))
        except ValueError:
            raise ImportError_(f"Ugyldig dato: {get(row, 'Handelsdag')!r}")
        trades.append({
            "nordnet_id": nid,
            "trade_date": trade_date,
            "side": side,
            "isin": get(row, "ISIN"),
            "name": get(row, "Værdipapirer")[:200],
            "quantity": abs(_num(get(row, "Antal"))),
            "price": _num(get(row, "Kurs")),
            "price_currency": "",
            "amount_dkk": _num(get(row, "Beløb")),
            "fee_dkk": _num(get(row, "Samlede afgifter")),
        })
    return trades


def resolve_isin(isin: str, name: str = "") -> Instrument:
    """Find (og husk) Yahoo-ticker for en ISIN. Tom symbol hvis ikke fundet."""
    inst, created = Instrument.objects.get_or_create(isin=isin, defaults={"name": name})
    if inst.symbol:
        return inst
    try:
        hits = yf.Search(isin, max_results=5, news_count=0).quotes
    except Exception:
        hits = []
    for h in hits:
        if h.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND"):
            inst.symbol = h["symbol"]
            inst.name = h.get("longname") or h.get("shortname") or name
            inst.save()
            break
    return inst


def sync_holdings(user) -> list[str]:
    """Genberegn beholdninger ud fra transaktioner (gennemsnitlig anskaffelseskurs).

    Returnerer ISIN'er uden kendt ticker.
    """
    unresolved = []
    by_isin: dict[str, list[Transaction]] = {}
    for t in user.transactions.order_by("trade_date", "id"):
        by_isin.setdefault(t.isin, []).append(t)

    for isin, txs in by_isin.items():
        inst = resolve_isin(isin, txs[0].name)
        if not inst.symbol:
            unresolved.append(f"{isin} ({txs[0].name})")
            continue
        qty = cost = Decimal(0)
        for t in txs:
            if t.side == Transaction.BUY:
                qty += t.quantity
                cost += t.quantity * t.price
            elif qty > 0:
                sold = min(t.quantity, qty)
                cost -= cost * sold / qty
                qty -= sold
        if qty > 0:
            Holding.objects.update_or_create(
                user=user, symbol=inst.symbol,
                defaults={"name": inst.name or txs[0].name, "quantity": qty,
                          "purchase_price": (cost / qty).quantize(Decimal("0.0001"))},
            )
        else:
            Holding.objects.filter(user=user, symbol=inst.symbol).delete()
    return unresolved


@db_transaction.atomic
def import_csv(user, raw: bytes) -> dict:
    trades = parse_csv(raw)
    existing = set(user.transactions.values_list("nordnet_id", flat=True))
    new = [Transaction(user=user, **t) for t in trades if t["nordnet_id"] not in existing]
    Transaction.objects.bulk_create(new)
    unresolved = sync_holdings(user)
    return {
        "found": len(trades),
        "imported": len(new),
        "duplicates": len(trades) - len(new),
        "unresolved": unresolved,
    }
