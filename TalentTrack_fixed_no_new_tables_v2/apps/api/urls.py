from django.urls import re_path
from django.views.decorators.csrf import csrf_exempt

from apps.api.views import *

urlpatterns = [
	re_path("sales/((?P<pk>\d+)/)?", csrf_exempt(SalesView.as_view())),
]