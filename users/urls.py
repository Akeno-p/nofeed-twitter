from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("do_login/", views.do_login, name="do_login"),
    path("two_factor_auth/", views.two_factor_auth_view, name="two_factor_auth"),
    path("two_factor_qrcode/", views.two_factor_qrcode_view, name="two_factor_qrcode"),
    path(
        "verify_two_factor_code/",
        views.verify_two_factor_code,
        name="verify_two_factor_code",
    ),
]
