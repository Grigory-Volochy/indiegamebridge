"""Auth-related view - Opt Out (authenticated POST)."""

from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.cookies import clear_jwt_cookies
from apps.users.models import TwitchExclusion


def perform_opt_out(user) -> bool | None:
    """Resolve the user's Twitch ID via allauth's SocialAccount and record the
    opt-out in TwitchExclusion. Returns True if a new exclusion was created,
    False if the user was already opted out, or None if no Twitch account is
    linked. Idempotent: re-clicking does not refresh optout_at.

    Future work: also erase user-owned data outside the exclusion record.
    """
    social = SocialAccount.objects.filter(user=user, provider="twitch").first()
    if social is None:
        print("opt out requested but no twitch social account linked")
        return None

    _, is_new_opt_out = TwitchExclusion.objects.get_or_create(twitch_id=social.uid)
    return is_new_opt_out


@method_decorator(csrf_protect, name="dispatch")
class OptOutView(APIView):
    """Opt-out endpoint for users already authenticated via JWT cookie.
    Records the opt-out, blacklists the refresh token, and clears cookies so
    the next page load renders the logged-out state."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        perform_opt_out(user=request.user)
        raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass  # already expired or blacklisted - clearing cookies is still correct

        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_jwt_cookies(response)
        return response
