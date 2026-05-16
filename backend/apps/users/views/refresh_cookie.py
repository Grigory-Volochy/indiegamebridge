"""Auth-related view - Refresh Cookie."""

from django.conf import settings
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.cookies import set_jwt_cookies


@method_decorator(csrf_protect, name="dispatch")
class RefreshCookieView(APIView):
    """Reads refresh token from its path-scoped cookie, issues a new access
    cookie (and rotated refresh cookie). Body stays empty - the frontend
    never touches tokens directly."""

    permission_classes = [AllowAny]

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if not raw_refresh:
            raise InvalidToken("No refresh cookie present.")

        try:
            refresh = RefreshToken(raw_refresh)
        except TokenError as exc:
            raise InvalidToken(str(exc)) from exc

        access_token = str(refresh.access_token)
        rotated_refresh = None
        if settings.SIMPLE_JWT.get("ROTATE_REFRESH_TOKENS"):
            if settings.SIMPLE_JWT.get("BLACKLIST_AFTER_ROTATION"):
                try:
                    refresh.blacklist()
                except AttributeError:
                    pass
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            rotated_refresh = str(refresh)

        response = Response(status=status.HTTP_204_NO_CONTENT)
        set_jwt_cookies(response, access_token, rotated_refresh)
        return response
