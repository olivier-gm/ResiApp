from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from apps.locations.models import FederalEntity, Locality, Zone

from .models import Amenity, Listing


class ListingForm(forms.ModelForm):
    state = forms.ModelChoiceField(label="Estado", queryset=FederalEntity.objects.all(), required=False)

    class Meta:
        model = Listing
        fields = [
            "title",
            "operation",
            "property_type",
            "description",
            "state",
            "locality",
            "zone",
            "exact_address",
            "amount",
            "currency",
            "area",
            "bedrooms",
            "bathrooms",
            "parking",
            "furnished",
            "pets_allowed",
            "amenities",
            "deposit",
            "advance",
            "minimum_months",
            "available_from",
            "included_expenses",
            "additional_costs",
            "house_rules",
            "negotiable",
            "documentation",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "available_from": forms.DateInput(attrs={"type": "date"}),
            "amenities": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["locality"].queryset = Locality.objects.none()
        self.fields["zone"].queryset = Zone.objects.none()
        state_id = (
            self.data.get("state")
            if self.is_bound
            else (self.instance.locality.state_id if self.instance.locality_id else None)
        )
        locality_id = self.data.get("locality") if self.is_bound else self.instance.locality_id
        try:
            if state_id:
                self.fields["locality"].queryset = Locality.objects.filter(
                    state_id=int(state_id)
                ).select_related("state")
            if locality_id:
                self.fields["zone"].queryset = Zone.objects.filter(locality_id=int(locality_id))
        except TypeError, ValueError:
            pass
        if not self.is_bound and self.instance.locality_id:
            self.initial["state"] = self.instance.locality.state_id
        self.fields["state"].widget.attrs.update({"data-location-state": ""})
        self.fields["locality"].widget.attrs.update({"data-location-locality": ""})
        self.fields["zone"].widget.attrs.update({"data-location-zone": ""})

    def clean(self):
        data = super().clean()
        if data.get("locality") and data.get("state") != data["locality"].state:
            self.add_error("locality", "La ciudad no pertenece al estado elegido.")
        if data.get("operation") == Listing.Operation.SALE:
            for name in ("deposit", "advance", "minimum_months", "available_from"):
                data[name] = None
            for name in ("included_expenses", "house_rules"):
                data[name] = ""
        return data


class SearchForm(forms.Form):
    q = forms.CharField(label="Buscar", required=False, max_length=150)
    state = forms.ModelChoiceField(label="Estado", queryset=FederalEntity.objects.all(), required=False)
    locality = forms.ModelChoiceField(label="Ciudad", queryset=Locality.objects.none(), required=False)
    zone = forms.ModelChoiceField(label="Zona", queryset=Zone.objects.none(), required=False)
    property_type = forms.ChoiceField(
        label="Tipo",
        choices=[("", "Todos los tipos"), *Listing.PropertyType.choices],
        required=False,
    )
    currency = forms.ChoiceField(
        label="Moneda",
        choices=[("", "Todas"), ("USD", "USD"), ("VES", "VES")],
        required=False,
    )
    minimum = forms.DecimalField(
        label="Desde",
        min_value=Decimal("0"),
        max_value=Decimal("999999999999"),
        decimal_places=2,
        required=False,
    )
    maximum = forms.DecimalField(
        label="Hasta",
        min_value=Decimal("0"),
        max_value=Decimal("999999999999"),
        decimal_places=2,
        required=False,
    )
    bedrooms = forms.IntegerField(label="Dormitorios desde", min_value=0, max_value=100, required=False)
    bathrooms = forms.IntegerField(label="Baños desde", min_value=0, max_value=100, required=False)
    parking = forms.IntegerField(label="Estacionamientos desde", min_value=0, max_value=100, required=False)
    furnished = forms.ChoiceField(
        label="Amueblado",
        choices=[("", "Sin preferencia"), ("yes", "Sí"), ("no", "No")],
        required=False,
    )
    pets_allowed = forms.ChoiceField(
        label="Mascotas",
        choices=[("", "Sin preferencia"), ("yes", "Sí"), ("no", "No")],
        required=False,
    )
    amenities = forms.ModelMultipleChoiceField(
        label="Servicios",
        queryset=Amenity.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    order = forms.ChoiceField(
        label="Ordenar",
        choices=[
            ("recent", "Más recientes"),
            ("price_up", "Menor precio"),
            ("price_down", "Mayor precio"),
        ],
        initial="recent",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["state"].widget.attrs["data-location-state"] = ""
        self.fields["locality"].widget.attrs["data-location-locality"] = ""
        self.fields["zone"].widget.attrs["data-location-zone"] = ""
        state_id = self.data.get("state")
        locality_id = self.data.get("locality")
        zone_id = self.data.get("zone")
        try:
            if state_id:
                self.fields["locality"].queryset = Locality.objects.filter(
                    state_id=int(state_id)
                ).select_related("state")
            if locality_id:
                self.fields["zone"].queryset = Zone.objects.filter(locality_id=int(locality_id))
                if not state_id:
                    self.fields["locality"].queryset = Locality.objects.filter(
                        pk=int(locality_id)
                    ).select_related("state")
            elif zone_id:
                self.fields["zone"].queryset = Zone.objects.filter(pk=int(zone_id))
        except TypeError, ValueError:
            self.fields["locality"].queryset = Locality.objects.none()
            self.fields["zone"].queryset = Zone.objects.none()

    def clean(self):
        data = super().clean()
        if (
            data.get("minimum") is not None
            or data.get("maximum") is not None
            or data.get("order") in ("price_up", "price_down")
        ) and not data.get("currency"):
            self.add_error("currency", "Elige una moneda para filtrar u ordenar por precio.")
        if (
            data.get("minimum") is not None
            and data.get("maximum") is not None
            and data["minimum"] > data["maximum"]
        ):
            self.add_error("maximum", "El máximo debe ser mayor o igual al mínimo.")
        if data.get("locality") and data.get("state") and data["locality"].state_id != data["state"].pk:
            self.add_error("locality", "La ciudad no pertenece al estado elegido.")
        if data.get("zone") and data.get("locality") and data["zone"].locality_id != data["locality"].pk:
            self.add_error("zone", "La zona no pertenece a la ciudad elegida.")
        return data


class ImageUploadForm(forms.Form):
    image = forms.FileField(label="Foto (JPEG, PNG o WebP)")
    alt = forms.CharField(label="Descripción de la foto", max_length=180, required=False)

    def clean_image(self):
        image = self.cleaned_data["image"]
        if image.size > 8 * 1024 * 1024:
            raise ValidationError("La foto no puede superar 8 MB.")
        return image
