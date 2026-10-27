from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.machine_list, name="home"),
    path("machines/<int:pk>/", views.machine_detail, name="machine_detail"),
    path("machines/<int:machine_pk>/entries/new/", views.log_entry_create, name="log_entry_create"),
    path("entries/<int:pk>/", views.log_entry_detail, name="log_entry_detail"),
    path("entries/<int:pk>/edit/", views.log_entry_amend, name="log_entry_amend"),
]
