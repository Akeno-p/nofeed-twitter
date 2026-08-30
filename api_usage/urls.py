from django.urls import path
from . import views

urlpatterns = [
    path("", views.api_usage_view, name="api_usage"),
]
