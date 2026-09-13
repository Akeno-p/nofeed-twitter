from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("do_login/", views.do_login, name="do_login"),
    path("two_factor_auth/", views.two_factor_auth_view, name="two_factor_auth"),
    path("two_factor_qrcode/", views.two_factor_qrcode_view, name="two_factor_qrcode"),
    path(
        "totp_setup/",
        views.totp_setup,
        name="totp_setup",
    ),
    path("totp_auth/", views.totp_auth, name="totp_auth"),
    path("twitter_auth/", views.twitter_auth_view, name="twitter_auth"),
    path("twitter_auth_start/", views.twitter_auth_start, name="twitter_auth_start"),
    path(
        "twitter_auth_callback/",
        views.twitter_auth_callback,
        name="twitter_auth_callback",
    ),
    path(
        "twitter_auth_error/", views.twitter_auth_error_view, name="twitter_auth_error"
    ),
]
