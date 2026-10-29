from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Prepara el grupo Moderadores con permisos limitados."

    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name="Moderadores")
        rules = {
            "listings": ["view_listing", "moderate_listing", "view_listingimage", "view_listingtransition"],
            "moderation": ["view_report", "change_report", "view_reportaccess"],
            "locations": ["view_locationrequest", "change_locationrequest"],
        }
        for app, codes in rules.items():
            group.permissions.add(*Permission.objects.filter(content_type__app_label=app, codename__in=codes))
        self.stdout.write(
            "Grupo Moderadores preparado. Asigna is_staff y el grupo a cuentas de personal autorizadas."
        )
