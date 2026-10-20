from datetime import date, timedelta
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


import pandas as pd  # noqa: E402

from . import importer, portfolio  # noqa: E402
from .models import Instrument, Transaction  # noqa: E402

HEADER = ("Id\tBogføringsdag\tHandelsdag\tValørdag\tDepot\tTransaktionstype\tVærdipapirer\tISIN\tAntal\t"
          "Kurs\tRente\tSamlede afgifter\tValuta\tBeløb\tValuta\tVekslingskurs")


def make_csv(rows):
    lines = [HEADER] + [
        f"{i}\t\t{d}\t\t1\t{t}\tVestas\tDK0061539921\t{q}\t{k}\t\t25\tDKK\t{b}\tDKK\t"
        for i, d, t, q, k, b in rows
    ]
    return "\r\n".join(lines).encode("utf-16")


@patch("stocks.importer.yf.Search", FakeSearch)
class ImportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("anna", password="pw")

    def test_parse_danish_numbers_and_ignores_other_types(self):
        raw = make_csv([(1, "2026-01-05", "KØBT", "10", "9,50", "-120,5"),
                        (2, "2026-01-06", "UDBYTTE", "10", "1", "5")])
        trades = importer.parse_csv(raw)
        self.assertEqual(len(trades), 1)
        self.assertEqual(str(trades[0]["price"]), "9.50")
        self.assertEqual(str(trades[0]["amount_dkk"]), "-120.5")

    def test_import_creates_holding_and_is_idempotent(self):
        raw = make_csv([(1, "2026-01-05", "KØBT", "10", "100", "-1025"),
                        (2, "2026-02-05", "KØBT", "10", "120", "-1225"),
                        (3, "2026-03-05", "SOLGT", "5", "130", "625")])
        first = importer.import_csv(self.user, raw)
        self.assertEqual(first["imported"], 3)
        h = self.user.holdings.get()
        self.assertEqual(h.symbol, "VWS.CO")
        self.assertEqual(float(h.quantity), 15.0)
        self.assertEqual(float(h.purchase_price), 110.0)  # snit uændret af salg
        second = importer.import_csv(self.user, raw)
        self.assertEqual((second["imported"], second["duplicates"]), (0, 3))
        self.assertEqual(Transaction.objects.count(), 3)

    def test_rejects_wrong_file(self):
        with self.assertRaises(importer.ImportError_):
            importer.parse_csv(b"a,b,c\n1,2,3")

    def test_import_endpoint(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.user)
        f = SimpleUploadedFile("x.csv", make_csv([(1, "2026-01-05", "KØBT", "1", "10", "-35")]))
        resp = self.client.post(reverse("import_api"), {"file": f})
        self.assertEqual(resp.json()["imported"], 1)


class HistoryTests(TestCase):
    def test_value_follows_quantity_over_time(self):
        user = get_user_model().objects.create_user("anna", password="pw")
        Instrument.objects.create(isin="DK0061539921", symbol="VWS.CO")
        d0 = date.today() - timedelta(days=14)
        Transaction.objects.create(user=user, nordnet_id="1", trade_date=d0, side="buy",
                                   isin="DK0061539921", quantity=10, price=100, amount_dkk=-1025)
        days = pd.bdate_range(d0 - timedelta(days=5), date.today())
        close = pd.Series(100.0, index=days)
        with patch("stocks.portfolio._fetch_close", return_value=(close, "DKK")):
            h = portfolio.build_history(user, "max")
        self.assertEqual(h["value"][0], 0.0 if pd.Timestamp(h["dates"][0]) < pd.Timestamp(d0) else 1000.0)
        self.assertEqual(h["value"][-1], 1000.0)
        self.assertEqual(h["invested"][-1], 1025.0)
