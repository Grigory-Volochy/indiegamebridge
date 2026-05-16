from django.urls import path

from apps.users.views import (
    CurrentUserView,
    LogoutView,
    OAuthFinalizeView,
    OptOutView,
    RefreshCookieView,
)


urlpatterns = [
    path("currentuser/", CurrentUserView.as_view(), name="auth-current-user"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("optout/", OptOutView.as_view(), name="auth-opt-out"),
    path("token/refresh/", RefreshCookieView.as_view(), name="auth-token-refresh"),
    path("finalize-login/", OAuthFinalizeView.as_view(), name="auth-finalize-login"),
]
