from django.conf import settings
from django.db import models


class Holding(models.Model):
    """En aktiebeholdning (fx købt via Nordnet) tilhørende en bruger."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="holdings"
    )
    symbol = models.CharField("Symbol", max_length=32)
    name = models.CharField("Navn", max_length=200, blank=True)
    quantity = models.DecimalField("Antal", max_digits=14, decimal_places=4)
    purchase_price = models.DecimalField(
        "Købskurs (pr. aktie)", max_digits=14, decimal_places=4, null=True, blank=True
    )
    notes = models.CharField("Note", max_length=200, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["symbol"]
        constraints = [
            models.UniqueConstraint(fields=["user", "symbol"], name="unique_user_symbol")
        ]
        verbose_name = "beholdning"
        verbose_name_plural = "beholdninger"

    def save(self, *args, **kwargs):
        self.symbol = self.symbol.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} – {self.symbol} ({self.quantity})"
