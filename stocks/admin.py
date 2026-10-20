from django.contrib import admin

from .models import Holding


@admin.register(Holding)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "user", "quantity", "purchase_price", "created")
    list_filter = ("user",)
    search_fields = ("symbol", "name", "user__username")
