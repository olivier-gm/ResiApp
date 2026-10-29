from django.urls import path

from . import views

app_name = "inquiries"
urlpatterns = [
    path("panel/consultas/", views.inbox, name="inbox"),
    path("inmuebles/<uuid:listing_id>/consultar/", views.create, name="start"),
    path("inmuebles/<uuid:listing_id>/consultar/", views.create, name="create"),
    path("panel/consultas/<uuid:pk>/", views.thread, name="thread"),
    path("panel/consultas/<uuid:pk>/visitas/", views.visit_create, name="visit_create"),
    path("panel/visitas/<uuid:pk>/responder/", views.visit_respond, name="visit_respond"),
    path("panel/consultas/<uuid:pk>/bloquear/", views.block, name="block"),
    path("panel/consultas/<uuid:pk>/desbloquear/", views.unblock, name="unblock"),
    path("panel/consultas/<uuid:pk>/leer/", views.mark_read, name="mark_read"),
]
