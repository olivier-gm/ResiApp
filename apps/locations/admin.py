from django.contrib import admin

from .models import FederalEntity, Locality, LocationRequest, Zone


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    search_fields = ["name", "aliases", "code"]
    list_filter = ["state"]
    list_display = ["name", "state", "code"]


admin.site.register([FederalEntity, Zone, LocationRequest])
