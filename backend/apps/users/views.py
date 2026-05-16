"""Auth-related views: OAuth finalize, me, logout, token refresh."""

from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.contrib.auth import logout as django_logout
from django.http import HttpResponseRedirect
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.cookies import clear_jwt_cookies, set_jwt_cookies


def _safe_next_url(raw: str | None) -> str:
    """Only allow same-origin redirects back to the configured frontend."""
    frontend = settings.FRONTEND_URL.rstrip("/")
    if not raw:
        return frontend + "/"
    candidate = urljoin(frontend + "/", raw)
    if urlparse(candidate).netloc != urlparse(frontend).netloc:
        return frontend + "/"
    return candidate


@method_decorator(ensure_csrf_cookie, name="dispatch")
class OAuthFinalizeView(APIView):
    """Lands here after allauth completes the social-login dance.

    At this point allauth has authenticated the user via Django session.
    We mint a JWT pair, set them as HttpOnly cookies, flush the session
    (so JWT is the single source of truth post-login), and redirect to
    the frontend. ensure_csrf_cookie populates csrftoken so the frontend
    can echo it on subsequent state-changing requests (logout, refresh).

    SessionAuthentication is required here (and only here) - the project's
    default DRF auth class is JWT-cookie-only, but at this exact step the
    JWT doesn't exist yet; the allauth session is the only credential.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return HttpResponseRedirect(_safe_next_url("/login"))

        refresh = RefreshToken.for_user(request.user)
        next_url = _safe_next_url(request.GET.get("next"))
        response = HttpResponseRedirect(next_url)
        set_jwt_cookies(response, str(refresh.access_token), str(refresh))
        django_logout(request)
        return response


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    """Returns the current user. Side-effect: ensures the csrftoken cookie
    is populated so the frontend can echo it on subsequent state-changing
    requests (logout, refresh)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "display_name": user.get_full_name() or user.username,
                "email": user.email or "",
            }
        )


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
