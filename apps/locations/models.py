from django.conf import settings
from django.db import models


class FederalEntity(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]
        verbose_name = "entidad federal"

    def __str__(self):
        return self.name


class Locality(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    state = models.ForeignKey(FederalEntity, on_delete=models.PROTECT, related_name="localities")
    aliases = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "ciudad o localidad"

    def __str__(self):
        return f"{self.name}, {self.state.name}"


class Zone(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    locality = models.ForeignKey(Locality, on_delete=models.PROTECT, related_name="zones")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class LocationRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    state = models.ForeignKey(FederalEntity, on_delete=models.PROTECT)
    name = models.CharField(max_length=150)
    notes = models.TextField(blank=True, max_length=1000)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
