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


class Instrument(models.Model):
    """Kobling fra ISIN (Nordnet) til Yahoo-ticker. Kan rettes i admin."""

    isin = models.CharField("ISIN", max_length=12, unique=True)
    symbol = models.CharField("Yahoo-symbol", max_length=32, blank=True)
    name = models.CharField("Navn", max_length=200, blank=True)

    class Meta:
        verbose_name = "værdipapir"
        verbose_name_plural = "værdipapirer"

    def __str__(self):
        return f"{self.isin} → {self.symbol or '?'}"


class Transaction(models.Model):
    """Et køb eller salg importeret fra Nordnet."""

    BUY, SELL = "buy", "sell"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions"
    )
    nordnet_id = models.CharField(max_length=64)
    trade_date = models.DateField("Handelsdag")
    side = models.CharField(max_length=4, choices=[(BUY, "Køb"), (SELL, "Salg")])
    isin = models.CharField(max_length=12)
    name = models.CharField(max_length=200, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    price = models.DecimalField("Kurs", max_digits=16, decimal_places=6)
    price_currency = models.CharField(max_length=3, blank=True)  # filen oplyser ikke kursens valuta
    amount_dkk = models.DecimalField("Beløb (DKK)", max_digits=16, decimal_places=2)
    fee_dkk = models.DecimalField("Afgifter (DKK)", max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["trade_date", "id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "nordnet_id"], name="unique_user_nordnet_id")
        ]
        verbose_name = "transaktion"
        verbose_name_plural = "transaktioner"

    def __str__(self):
        return f"{self.trade_date} {self.side} {self.quantity} {self.name or self.isin}"
