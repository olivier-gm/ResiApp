from django import forms

from .models import Report


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "details"]
        widgets = {"details": forms.Textarea(attrs={"rows": 5})}

    def clean_details(self):
        value = self.cleaned_data["details"].strip()
        if len(value) < 10:
            raise forms.ValidationError("Describe lo ocurrido con al menos 10 caracteres.")
        return value


class ReportAdminForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["status", "resolution"]

    def clean(self):
        data = super().clean()
        if (
            data.get("status") in [Report.Status.RESOLVED, Report.Status.DISMISSED]
            and not data.get("resolution", "").strip()
        ):
            self.add_error("resolution", "Explica el motivo antes de cerrar la denuncia.")
        return data
