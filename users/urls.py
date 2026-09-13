from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("do_login/", views.do_login, name="do_login"),
    path("totp_setup/", views.totp_setup_view, name="totp_setup"),
    path(
        "totp_setup_verify/",
        views.totp_setup_verify,
        name="totp_setup_verify",
    ),
    path("totp_auth/", views.totp_auth_view, name="totp_auth"),
    path("totp_auth_verify/", views.totp_auth_verify, name="totp_auth_verify"),
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
