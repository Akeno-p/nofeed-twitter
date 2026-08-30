from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("users/", include("users.urls")),
    path("tweets/", include("tweets.urls")),
    path("dm/", include("dm.urls")),
    path("api_usage/", include("api_usage.urls")),
]
