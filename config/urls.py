from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="login", permanent=False)),
    path("admin/", admin.site.urls),
    path("users/", include("users.urls")),
    path("tweets/", include("tweets.urls")),
    path("dm/", include("dm.urls")),
    path("api_usage/", include("api_usage.urls")),
]
