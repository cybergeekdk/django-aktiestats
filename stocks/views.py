from django.http import JsonResponse
from django.shortcuts import render

from .services import QuoteError, get_quote, get_quotes

DEFAULT_SYMBOLS = ["AAPL", "MSFT", "NVDA", "NOVO-B.CO", "^OMXC25"]


def index(request):
    return render(request, "stocks/index.html", {"symbols": DEFAULT_SYMBOLS})


def quote_api(request, symbol):
    try:
        return JsonResponse(get_quote(symbol))
    except QuoteError as exc:
        return JsonResponse({"error": str(exc)}, status=404)


def quotes_api(request):
    raw = request.GET.get("symbols", ",".join(DEFAULT_SYMBOLS))
    symbols = [s for s in raw.split(",") if s.strip()][:25]
    return JsonResponse(get_quotes(symbols))
