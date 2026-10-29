from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.core import views
from apps.core.sitemaps import ListingSitemap
from apps.locations import views as locations

admin.site.site_header = "ResiVe · Administración"
admin.site.site_title = "ResiVe"
admin.site.index_title = "Publicaciones y operación"
urlpatterns = [
    path("", views.home, name="home"),
    path("", include("apps.inquiries.urls")),
    path("", include("apps.listings.urls")),
    path("cuenta/", include("apps.accounts.urls")),
    path("panel/notificaciones/", include("apps.notifications.urls")),
    path("reportes/", include("apps.moderation.urls")),
    path("ubicaciones/ciudades/", locations.localities, name="localities"),
    path("ubicaciones/zonas/", locations.zones, name="zones"),
    path("ubicaciones/solicitar/", locations.request_location, name="location-request"),
    path("informacion/<slug:page>/", views.legal, name="legal"),
    path("healthz/", views.health, name="health"),
    path("robots.txt", views.robots),
    path("sitemap.xml", sitemap, {"sitemaps": {"listings": ListingSitemap}}, name="sitemap"),
    path("admin/", admin.site.urls),
]
