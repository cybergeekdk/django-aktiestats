"""Henter live aktiestatistik fra Yahoo Finance via yfinance."""
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
    """Hent flere symboler; fejl pr. symbol returneres i stedet for at fejle alt."""
    result = {}
    for symbol in symbols:
        try:
            result[symbol.strip().upper()] = get_quote(symbol)
        except QuoteError as exc:
            result[symbol.strip().upper()] = {"error": str(exc)}
    return result
