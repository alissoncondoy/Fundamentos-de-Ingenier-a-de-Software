from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    # Root -> TalentTrack
    path("", RedirectView.as_view(url="/talenttrack/", permanent=False)),
    # Browsers often request /favicon.ico regardless of <link rel="icon">.
    # Redirect it to our static favicon to avoid noisy 404s in development.
    path("favicon.ico", RedirectView.as_view(url="/static/assets/img/brand/favicon.png", permanent=False)),
    path("talenttrack/", include("apps.talenttrack.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
