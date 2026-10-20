from django.contrib import admin

from .models import Holding


@admin.register(Holding)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "user", "quantity", "purchase_price", "created")
    list_filter = ("user",)
    search_fields = ("symbol", "name", "user__username")


from .models import Instrument, Transaction  # noqa: E402


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("isin", "symbol", "name")
    search_fields = ("isin", "symbol", "name")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("trade_date", "user", "side", "name", "quantity", "price", "amount_dkk")
    list_filter = ("user", "side")
    search_fields = ("name", "isin")
    date_hierarchy = "trade_date"
