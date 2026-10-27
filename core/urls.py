from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.machine_list, name="home"),
    path("machines/<int:pk>/", views.machine_detail, name="machine_detail"),
]
