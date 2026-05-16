"""Auth-related view - Logout."""

from django.conf import settings
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.cookies import clear_jwt_cookies


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    """Blacklists the refresh token and clears both cookies.

    JWTs are "stateless verification, stateful revocation" - the blacklist is
    the stateful piece. An access token already issued remains valid until its
    short TTL expires; that's the standard trade-off.

    DRF defaults views to csrf_exempt (token auth doesn't need CSRF). Cookie
    auth does, so we re-enable csrf_protect explicitly here.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass  # already expired or blacklisted - clearing cookies is still correct
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_jwt_cookies(response)
        return response
