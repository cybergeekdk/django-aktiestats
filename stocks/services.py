"""Henter live aktiestatistik fra Yahoo Finance via yfinance."""
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.cache import cache
import yfinance as yf


class QuoteError(Exception):
    pass


def _num(value):
    """Gør numpy/pandas-tal til almindelige floats (JSON-venlige)."""
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def get_quote(symbol: str) -> dict:
    """Returnér live statistik for ét ticker-symbol (fx AAPL, NOVO-B.CO)."""
    symbol = symbol.strip().upper()
    if not symbol:
        raise QuoteError("Intet symbol angivet")

    cache_key = f"quote:{symbol}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        fast = yf.Ticker(symbol).fast_info
        price = _num(fast["last_price"])
        prev_close = _num(fast["previous_close"])
        data = {
            "symbol": symbol,
            "price": price,
            "currency": fast["currency"],
            "previous_close": prev_close,
            "open": _num(fast["open"]),
            "day_high": _num(fast["day_high"]),
            "day_low": _num(fast["day_low"]),
            "volume": _num(fast["last_volume"]),
            "market_cap": _num(fast["market_cap"]),
            "year_high": _num(fast["year_high"]),
            "year_low": _num(fast["year_low"]),
            "fifty_day_average": _num(fast["fifty_day_average"]),
        }
    except Exception as exc:
        raise QuoteError(f"Kunne ikke hente data for {symbol}") from exc

    if data["price"] is None:
        raise QuoteError(f"Ukendt symbol: {symbol}")

    if prev_close:
        data["change"] = round(price - prev_close, 4)
        data["change_percent"] = round((price - prev_close) / prev_close * 100, 2)
    else:
        data["change"] = data["change_percent"] = None

    cache.set(cache_key, data, settings.QUOTE_CACHE_SECONDS)
    return data


def get_quotes(symbols: list[str]) -> dict:
    """Hent flere symboler parallelt; fejl pr. symbol returneres i stedet for at fejle alt."""
    symbols = [s.strip().upper() for s in symbols if s.strip()]

    def safe(symbol):
        try:
            return get_quote(symbol)
        except QuoteError as exc:
            return {"error": str(exc)}

    if not symbols:
        return {}
    with ThreadPoolExecutor(max_workers=min(8, len(symbols))) as pool:
        return dict(zip(symbols, pool.map(safe, symbols)))


def search_symbols(query: str, limit: int = 8) -> list[dict]:
    """Søg aktier/ETF'er på navn eller ticker (fx 'vestas' -> VWS.CO)."""
    query = query.strip()
    if len(query) < 2:
        return []
    try:
        hits = yf.Search(query, max_results=limit, news_count=0).quotes
    except Exception as exc:
        raise QuoteError("Søgningen fejlede") from exc
    return [
        {
            "symbol": h["symbol"],
            "name": h.get("longname") or h.get("shortname") or h["symbol"],
            "exchange": h.get("exchDisp", ""),
        }
        for h in hits
        if h.get("quoteType") in ("EQUITY", "ETF", "INDEX", "MUTUALFUND")
    ]
