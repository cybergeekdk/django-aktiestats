from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from . import services
from .models import Holding


class FakeTicker:
    def __init__(self, symbol):
        self.fast_info = {
            "last_price": 110.0, "previous_close": 100.0, "currency": "USD",
            "open": 101.0, "day_high": 111.0, "day_low": 99.0,
            "last_volume": 1000, "market_cap": 5e9, "year_high": 150.0,
            "year_low": 80.0, "fifty_day_average": 105.0,
        }


class FakeSearch:
    def __init__(self, q, **kw):
        self.quotes = [
            {"symbol": "VWS.CO", "longname": "Vestas", "exchDisp": "Copenhagen", "quoteType": "EQUITY"},
            {"symbol": "X=F", "shortname": "Future", "quoteType": "FUTURE"},
        ]


@patch("stocks.services.yf.Search", FakeSearch)
@patch("stocks.services.yf.Ticker", FakeTicker)
class StockTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user("anna", password="pw")
        self.other = User.objects.create_user("bo", password="pw")

    def test_change_is_computed(self):
        q = services.get_quote("aapl")
        self.assertEqual(q["change"], 10.0)
        self.assertEqual(q["change_percent"], 10.0)

    def test_pages_and_api_require_login(self):
        self.assertEqual(self.client.get(reverse("index")).status_code, 302)
        self.assertEqual(self.client.get(reverse("holdings_api")).status_code, 401)

    def test_search_filters_non_equities(self):
        self.client.force_login(self.user)
        results = self.client.get(reverse("search_api"), {"q": "vestas"}).json()["results"]
        self.assertEqual([r["symbol"] for r in results], ["VWS.CO"])

    def test_add_list_delete_holding_with_profit(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("holdings_api"),
            {"symbol": "vws.co", "name": "Vestas", "quantity": "10", "purchase_price": "100"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        h = resp.json()["holdings"][0]
        self.assertEqual(h["symbol"], "VWS.CO")
        self.assertEqual(h["profit"], 100.0)
        pk = h["id"]
        self.assertEqual(self.client.delete(reverse("holding_detail_api", args=[pk])).status_code, 200)
        self.assertEqual(Holding.objects.count(), 0)

    def test_users_cannot_touch_each_others_holdings(self):
        h = Holding.objects.create(user=self.other, symbol="AAPL", quantity=1)
        self.client.force_login(self.user)
        self.assertEqual(self.client.delete(reverse("holding_detail_api", args=[h.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("holdings_api")).json()["holdings"], [])

    def test_invalid_input_rejected(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("holdings_api"), {"symbol": "A", "quantity": "-1"}, content_type="application/json")
        self.assertEqual(resp.status_code, 400)
