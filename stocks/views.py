import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ProfileForm
from .importer import ImportError_, import_csv
from .models import Holding
from .portfolio import RANGES, build_history
from .services import QuoteError, get_quote, get_quotes, search_symbols


def _api_login_required(view):
    """Som login_required, men svarer med JSON 401 i stedet for redirect."""

    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Ikke logget ind"}, status=401)
        return view(request, *args, **kwargs)

    return wrapper


@login_required
def index(request):
    return render(request, "stocks/index.html")


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profilen er gemt.")
        return redirect("profile")
    return render(request, "stocks/profile.html", {
        "form": form,
        "holding_count": request.user.holdings.count(),
        "transaction_count": request.user.transactions.count(),
    })


@_api_login_required
def quote_api(request, symbol):
    try:
        return JsonResponse(get_quote(symbol))
    except QuoteError as exc:
        return JsonResponse({"error": str(exc)}, status=404)


@_api_login_required
def search_api(request):
    try:
        return JsonResponse({"results": search_symbols(request.GET.get("q", ""))})
    except QuoteError as exc:
        return JsonResponse({"error": str(exc)}, status=502)


def _holding_json(h, quote):
    out = {
        "id": h.id,
        "symbol": h.symbol,
        "name": h.name,
        "quantity": float(h.quantity),
        "purchase_price": float(h.purchase_price) if h.purchase_price is not None else None,
        "quote": quote,
    }
    price = quote.get("price")
    if price is not None:
        out["value"] = round(price * out["quantity"], 2)
        if out["purchase_price"] is not None:
            out["profit"] = round((price - out["purchase_price"]) * out["quantity"], 2)
            cost = out["purchase_price"] * out["quantity"]
            out["profit_percent"] = round(out["profit"] / cost * 100, 2) if cost else None
    return out


@_api_login_required
@require_http_methods(["GET", "POST"])
def holdings_api(request):
    if request.method == "POST":
        try:
            body = json.loads(request.body)
            symbol = str(body["symbol"]).strip().upper()
            quantity = Decimal(str(body["quantity"]))
            price = body.get("purchase_price")
            price = Decimal(str(price)) if price not in (None, "") else None
        except (ValueError, KeyError, InvalidOperation, json.JSONDecodeError):
            return JsonResponse({"error": "Ugyldigt input"}, status=400)
        if not symbol or quantity <= 0 or (price is not None and price < 0):
            return JsonResponse({"error": "Ugyldigt input"}, status=400)
        Holding.objects.update_or_create(
            user=request.user,
            symbol=symbol,
            defaults={
                "name": str(body.get("name", ""))[:200],
                "quantity": quantity,
                "purchase_price": price,
            },
        )

    holdings = list(request.user.holdings.all())
    quotes = get_quotes([h.symbol for h in holdings])
    return JsonResponse(
        {"holdings": [_holding_json(h, quotes.get(h.symbol, {})) for h in holdings]},
        status=201 if request.method == "POST" else 200,
    )


@_api_login_required
@require_http_methods(["DELETE"])
def holding_detail_api(request, pk):
    get_object_or_404(Holding, pk=pk, user=request.user).delete()
    return JsonResponse({"ok": True})


@_api_login_required
@require_http_methods(["POST"])
def import_api(request):
    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": "Ingen fil valgt"}, status=400)
    if upload.size > 5 * 1024 * 1024:
        return JsonResponse({"error": "Filen er for stor"}, status=400)
    try:
        summary = import_csv(request.user, upload.read())
    except ImportError_ as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(summary)


@_api_login_required
def history_api(request):
    range_key = request.GET.get("range", "1y")
    if range_key not in RANGES:
        return JsonResponse({"error": "Ugyldigt interval"}, status=400)
    key = f"history:{request.user.pk}:{range_key}"
    data = cache.get(key)
    if data is None:
        data = build_history(request.user, range_key)
        cache.set(key, data, 300)
    return JsonResponse(data)
