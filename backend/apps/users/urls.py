from django.urls import path

from apps.users.views import LogoutView, MeView, OAuthFinalizeView, RefreshCookieView


urlpatterns = [
    path("me/", MeView.as_view(), name="auth-me"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("token/refresh/", RefreshCookieView.as_view(), name="auth-token-refresh"),
    path("finalize-login/", OAuthFinalizeView.as_view(), name="auth-finalize-login"),
]
