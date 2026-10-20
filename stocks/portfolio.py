"""Historisk porteføljeværdi (DKK) ud fra transaktioner og kursudvikling."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from django.core.cache import cache

from .models import Instrument

RANGES = {"1m": 31, "3m": 92, "6m": 183, "1y": 366, "max": None}
HISTORY_CACHE_SECONDS = 600


def _fetch_close(symbol: str, start: date):
    """Dagsslutkurser (Series indekseret på dato) og kursens valuta."""
    key = f"close:{symbol}:{start}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    ticker = yf.Ticker(symbol)
    hist = ticker.history(start=start.isoformat(), interval="1d", auto_adjust=False)
    if hist.empty:
        result = (pd.Series(dtype=float), "DKK")
    else:
        close = hist["Close"].copy()
        close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
        close = close[~close.index.duplicated(keep="last")]
        currency = (ticker.history_metadata or {}).get("currency", "DKK")
        if currency == "GBp":  # pence → pund
            close, currency = close / 100, "GBP"
        result = (close, currency)
    cache.set(key, result, HISTORY_CACHE_SECONDS)
    return result


def build_history(user, range_key: str = "1y") -> dict:
    today = date.today()
    txs = list(user.transactions.all())
    isins = {t.isin for t in txs}
    symbol_of = {i.isin: i.symbol for i in Instrument.objects.filter(isin__in=isins) if i.symbol}

    deltas: dict[str, list] = {}  # symbol -> [(dato, +/- antal)]
    for t in txs:
        sym = symbol_of.get(t.isin)
        if sym:
            deltas.setdefault(sym, []).append(
                (t.trade_date, t.quantity if t.side == "buy" else -t.quantity)
            )
    constant = {  # manuelt indtastede beholdninger uden transaktioner
        h.symbol: float(h.quantity)
        for h in user.holdings.all()
        if h.symbol not in deltas
    }
    symbols = sorted(set(deltas) | set(constant))
    if not symbols:
        return {"dates": [], "value": [], "invested": []}

    days = RANGES.get(range_key, 366)
    first = min((t.trade_date for t in txs), default=today - timedelta(days=366))
    start = first if days is None else max(first, today - timedelta(days=days))
    fetch_from = start - timedelta(days=10)  # buffer så vi kan forward-fille

    with ThreadPoolExecutor(max_workers=8) as pool:
        closes = dict(zip(symbols, pool.map(lambda s: _fetch_close(s, fetch_from), symbols)))
        currencies = {c for _, c in closes.values() if c != "DKK"}
        fx = dict(zip(currencies, pool.map(lambda c: _fetch_close(f"{c}DKK=X", fetch_from)[0], currencies)))

    idx = pd.bdate_range(start, today)
    total = pd.Series(0.0, index=idx)
    for sym in symbols:
        close, cur = closes[sym]
        if close.empty:
            continue
        price = close.reindex(close.index.union(idx)).ffill().reindex(idx)
        rate = 1.0
        if cur != "DKK":
            f = fx.get(cur)
            if f is None or f.empty:
                continue
            rate = f.reindex(f.index.union(idx)).ffill().bfill().reindex(idx)
        qty = pd.Series(constant.get(sym, 0.0), index=idx)
        for d, q in deltas.get(sym, []):
            qty[idx >= pd.Timestamp(d)] += float(q)
        total += (price * rate * qty).fillna(0.0)

    flows = pd.Series(0.0, index=idx)
    for t in txs:
        flows[idx >= pd.Timestamp(t.trade_date)] += -float(t.amount_dkk)

    return {
        "dates": [d.strftime("%Y-%m-%d") for d in idx],
        "value": [round(v, 2) for v in total],
        "invested": [round(v, 2) for v in flows] if txs else [],
    }
