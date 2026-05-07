from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.pages.models import CachedPage


class CachedPageContentView(APIView):
    """Public read-only endpoint that returns the JSON payload of a cached page by key."""

    def get(self, request, key):
        page = get_object_or_404(CachedPage, key=key)
        return Response(page.content)
