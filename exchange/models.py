from django.db import models


class Order(models.Model):
    sell_currency = models.CharField(max_length=10)
    buy_currency = models.CharField(max_length=10)
    amount = models.FloatField()
    rate = models.FloatField()
    result = models.FloatField()
    planned_for = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount} {self.sell_currency} -> {self.buy_currency}"
