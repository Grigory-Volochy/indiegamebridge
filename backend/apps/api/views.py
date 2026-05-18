from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.pages.models import CachedPage


class CachedPageContentView(APIView):
    """Public read-only endpoint that returns the JSON payload of a cached page by key."""

    def get(self, request, key):
        page_parts = {
            p.key: p
            for p in CachedPage.objects.filter(key__in=[key, "page_header", "page_footer"])
        }
        page = page_parts.get(key)
        if page is None:
            raise Http404

        header = page_parts.get("page_header")
        footer = page_parts.get("page_footer")
        page.content["header_content"] = header.content if header else None
        page.content["footer_content"] = footer.content if footer else None

        return Response(page.content)
