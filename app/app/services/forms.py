from django import forms
from django.conf import settings

from constance import config

from .models import UpstreamServer
from .services import HarborService


class HarborCustomConfigForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for section_number in range(1, HarborService.CUSTOM_CONFIG_NUM_SECTIONS + 1):
            self.fields[f'section{section_number}'] = forms.CharField(widget=forms.Textarea, required=False)


class UpstreamServerForm(forms.ModelForm):
    local_icecast = forms.BooleanField(label='Check here prefill settings for local Icecast 2 server.', required=False)

    def __init__(self, data=None, *args, **kwargs):
        if data is not None and data.get('local_icecast'):
            data = data.copy()
            data.update({'hostname': 'icecast', 'protocol': 'http', 'port': '8000', 'username': 'source',
                         'password': config.ICECAST_SOURCE_PASSWORD})
        super().__init__(data, *args, **kwargs)

    class Meta:
        model = UpstreamServer
        fields = tuple(f.name for f in UpstreamServer._meta.fields)
        if settings.ICECAST_ENABLED:
            fields = ('local_icecast',) + fields
