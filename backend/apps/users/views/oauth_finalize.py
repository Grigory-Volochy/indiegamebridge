"""Auth-related view - OAuth Finalize."""

from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.contrib.auth import logout as django_logout
from django.http import HttpResponseRedirect
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.cookies import clear_jwt_cookies, set_jwt_cookies
from apps.users.views.opt_out import perform_opt_out


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
    Two branches:

    * default - mint a JWT pair, set HttpOnly cookies, flush the session
      (so JWT is the single source of truth post-login), redirect to the
      frontend.
    * action=optout - read the Twitch UID via allauth's SocialAccount,
      record the opt-out, flush the session, skip JWT entirely, and
      redirect to the opt-out success view. Same OAuth entry point as
      login - just a different terminal step.

    ensure_csrf_cookie populates csrftoken so the frontend can echo it on
    subsequent state-changing requests (logout, refresh).

    SessionAuthentication is required here (and only here) - the project's
    default DRF auth class is JWT-cookie-only, but at this exact step the
    JWT doesn't exist yet; the allauth session is the only credential.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return HttpResponseRedirect(_safe_next_url("/login"))

        next_url = _safe_next_url(request.GET.get("next"))

        if request.GET.get("action") == "optout":
            perform_opt_out(request.user)
            response = HttpResponseRedirect(next_url)
            django_logout(request)
            clear_jwt_cookies(response)
            return response

        refresh = RefreshToken.for_user(request.user)
        response = HttpResponseRedirect(next_url)
        set_jwt_cookies(response, str(refresh.access_token), str(refresh))
        django_logout(request)
        return response
