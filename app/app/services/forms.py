from django import forms

from .services import HarborService


class HarborCustomConfigForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for section_number in range(1, HarborService.CUSTOM_CONFIG_NUM_SECTIONS + 1):
            self.fields[f"section{section_number}"] = forms.CharField(widget=forms.Textarea, required=False)
