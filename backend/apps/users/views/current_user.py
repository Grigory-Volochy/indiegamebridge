"""Auth-related view - Current User."""

from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from allauth.socialaccount.models import SocialAccount

from apps.users.models import TwitchExclusion


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CurrentUserView(APIView):
    """Returns the current user. Side-effect: ensures the csrftoken cookie
    is populated so the frontend can echo it on subsequent state-changing
    requests (logout, refresh)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        social_account = SocialAccount.objects.filter(user=user, provider="twitch").first()
        twitch_id = social_account.uid if social_account else 0
        is_twitch_excluded = False
        if twitch_id:
            is_twitch_excluded = TwitchExclusion.objects.filter(twitch_id=twitch_id).exists()

        return Response(
            {
                "twitch_id": twitch_id,
                "username": user.username,
                "display_name": user.get_full_name() or user.username,
                "email": user.email or "",
                "is_twitch_excluded": is_twitch_excluded
            }
        )
