from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from .models import Locality, LocationRequest, Zone


@require_GET
def localities(request):
    state = request.GET.get("state", "")
    items = Locality.objects.filter(state_id=state) if state.isdigit() else Locality.objects.none()
    return render(request, "locations/options.html", {"items": items, "label": "Ciudad/localidad"})


@require_GET
def zones(request):
    locality = request.GET.get("locality", "")
    items = Zone.objects.filter(locality_id=locality) if locality.isdigit() else Zone.objects.none()
    return render(request, "locations/options.html", {"items": items, "label": "Zona"})


class RequestForm(forms.ModelForm):
    class Meta:
        model = LocationRequest
        fields = ["state", "name", "notes"]
        labels = {"state": "Estado", "name": "Ciudad/localidad faltante", "notes": "Información adicional"}


@login_required
def request_location(request):
    form = RequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.user = request.user
        record.save()
        messages.success(request, "Recibimos tu solicitud. Revisaremos la ubicación antes de incorporarla.")
        return redirect("home")
    return render(request, "locations/request.html", {"form": form})
