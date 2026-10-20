from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from . import services


class FakeTicker:
    def __init__(self, symbol):
        self.fast_info = {
            "last_price": 110.0, "previous_close": 100.0, "currency": "USD",
            "open": 101.0, "day_high": 111.0, "day_low": 99.0,
            "last_volume": 1000, "market_cap": 5e9, "year_high": 150.0,
            "year_low": 80.0, "fifty_day_average": 105.0,
        }


@patch("stocks.services.yf.Ticker", FakeTicker)
class QuoteTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_change_is_computed(self):
        q = services.get_quote("aapl")
        self.assertEqual(q["symbol"], "AAPL")
        self.assertEqual(q["change"], 10.0)
        self.assertEqual(q["change_percent"], 10.0)

    def test_api_returns_json(self):
        resp = self.client.get(reverse("quote_api", args=["AAPL"]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["price"], 110.0)

    def test_index_renders(self):
        self.assertEqual(self.client.get(reverse("index")).status_code, 200)
