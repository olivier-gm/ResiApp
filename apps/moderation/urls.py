from django.urls import path

from . import views

app_name = "moderation"
urlpatterns = [path("", views.report, name="report")]
