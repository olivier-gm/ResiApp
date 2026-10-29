import uuid

from django import forms
from django.utils import timezone


class MessageForm(forms.Form):
    body = forms.CharField(
        label="Mensaje",
        min_length=5,
        max_length=3000,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Cuéntale qué vivienda buscas o pregunta por sus condiciones.",
            }
        ),
    )
    client_token = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)


class VisitForm(forms.Form):
    scheduled_at = forms.DateTimeField(
        label="Fecha y hora (Venezuela)",
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
    )

    def clean_scheduled_at(self):
        value = self.cleaned_data["scheduled_at"]
        if value <= timezone.now():
            raise forms.ValidationError("Elige una fecha futura.")
        return value


class VisitResponseForm(forms.Form):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    action = forms.ChoiceField(
        choices=[
            ("accept", "Confirmar"),
            ("reject", "Rechazar"),
            ("cancel", "Cancelar"),
            ("reschedule", "Proponer otro horario"),
        ]
    )
    scheduled_at = forms.DateTimeField(
        label="Nuevo horario (solo al reprogramar)",
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
    )

    def clean(self):
        data = super().clean()
        if data.get("action") == "reschedule":
            value = data.get("scheduled_at")
            if not value or value <= timezone.now():
                self.add_error("scheduled_at", "Elige una fecha futura para la nueva propuesta.")
        return data
