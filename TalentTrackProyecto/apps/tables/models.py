from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.


class ModelChoices(models.TextChoices):
	SALES = 'SALES', _('Sales')
	
class PageItems(models.Model):
	parent = models.CharField(max_length=255, choices=ModelChoices.choices)
	items_per_page = models.IntegerField(default=25)
	
class HideShowFilter(models.Model):
	parent = models.CharField(max_length=255, choices=ModelChoices.choices)
	key = models.CharField(max_length=255)
	value = models.BooleanField(default=False)

	def __str__(self):
		return self.key

class ModelFilter(models.Model):
	parent = models.CharField(max_length=255, choices=ModelChoices.choices)
	key = models.CharField(max_length=255)
	value = models.CharField(max_length=255)

	def __str__(self):
		return self.key