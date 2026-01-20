from django.db import models

# Create your models here.
        
# Don't remove this mark
### ### Below code is Generated ### ###

from django.db import models

class RefundedChoices(models.TextChoices):
	YES = 'YES', 'Yes'
	NO = 'NO', 'No'

class CurrencyChoices(models.TextChoices):
	USD = 'USD', 'USD'
	EUR = 'EUR', 'EUR'
	
class Sales(models.Model):
	ID = models.AutoField(primary_key=True)
	Product = models.TextField(blank=True, null=True)
	BuyerEmail = models.EmailField(blank=True, null=True)
	PurchaseDate = models.DateField(blank=True, null=True)
	Country = models.TextField(blank=True, null=True)
	Price = models.FloatField(blank=True, null=True)
	Refunded = models.CharField(max_length=20, choices=RefundedChoices.choices, default=RefundedChoices.NO)
	Currency = models.CharField(max_length=10, choices=CurrencyChoices.choices, default=CurrencyChoices.USD)
	Quantity = models.IntegerField(blank=True, null=True)