"""DRF authentication class that accepts JWT from a cookie OR Authorization header.

The cookie path is what the Next.js SSR frontend uses (browsers can't attach
Authorization headers to SSR fetches, but cookies forward through Next
rewrites). The bearer-header path is left in for future native/mobile clients
that hit the same endpoints.
"""

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication


class JWTCookieAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            return super().authenticate(request)

        raw_token = request.COOKIES.get(settings.JWT_ACCESS_COOKIE_NAME)
        if not raw_token:
            return None

        validated_token = self.get_validated_token(raw_token)
        return (self.get_user(validated_token), validated_token)
