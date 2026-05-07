from django.urls import path

from apps.api.views import CachedPageContentView


urlpatterns = [
    path("pages/<slug:key>/", CachedPageContentView.as_view(), name="cached-page-content"),
]
