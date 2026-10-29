from django.urls import path

from . import views

app_name = "listings"
urlpatterns = [
    path("alquileres/", views.search, {"operation": "rent"}, name="rentals"),
    path("ventas/", views.search, {"operation": "sale"}, name="sales"),
    path("panel/publicaciones/", views.dashboard, name="dashboard"),
    path("panel/publicaciones/nueva/", views.edit, name="new"),
    path("panel/publicaciones/<uuid:pk>/editar/", views.edit, name="edit"),
    path("panel/publicaciones/<uuid:pk>/estado/", views.change_state, name="state"),
    path("panel/publicaciones/<uuid:pk>/fotos/", views.upload, name="upload"),
    path("panel/fotos/<uuid:pk>/eliminar/", views.delete_image, name="delete_image"),
    path("panel/fotos/<uuid:pk>/orden/", views.reorder_image, name="reorder_image"),
    path("media/fotos/<uuid:pk>/<str:variant>/", views.image, name="image"),
    path("inmuebles/<uuid:pk>/favorito/", views.favorite, name="favorite"),
    path("panel/favoritos/", views.favorites, name="favorites"),
    path("inmuebles/<uuid:pk>/<slug:slug>/", views.detail, name="detail"),
]
