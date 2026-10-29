from django.urls import path

from . import views

app_name = "notifications"
urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("<int:pk>/leer/", views.mark_read, name="mark_read"),
]
