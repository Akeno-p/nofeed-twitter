from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("do_login/", views.do_login, name="do_login"),
    path("two_factor_auth/", views.two_factor_auth_view, name="two_factor_auth"),
]
