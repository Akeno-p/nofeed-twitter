from django.urls import path

from . import views

urlpatterns = [
    path("", views.dm_view, name="dm"),
    path("save_all_dms", views.save_all_dms, name="save_all_dms"),
]
