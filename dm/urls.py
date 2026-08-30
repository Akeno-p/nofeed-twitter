from django.urls import path
from . import views

urlpatterns = [
    path("", views.dm_view, name="dm"),
]
