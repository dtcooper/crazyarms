from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm

from constance import config

from .services import init_services


CONSTANCE_FIELDS = ('STATION_NAME', 'ICECAST_ENABLED')
CONSTANCE_ICECAST_PASSWORD_FIELDS = ('ICECAST_SOURCE_PASSWORD', 'ICECAST_RELAY_PASSWORD', 'ICECAST_ADMIN_PASSWORD')


class FirstRunForm(UserCreationForm):
    icecast_passwords = forms.CharField(
        label='Icecast Password', help_text='The password for Icecast (admin, source, relay)')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for config_name in CONSTANCE_FIELDS:
            default, help_text = settings.CONSTANCE_CONFIG[config_name]
            kwargs = {
                'label': config_name.replace('_', ' ').lower().capitalize(),
                'help_text': help_text,
                'initial': default,
            }
            if isinstance(default, str):
                field = forms.CharField(**kwargs)
            elif isinstance(default, bool):
                field = forms.BooleanField(
                    required=False, widget=forms.Select(choices=((True, 'Enabled'), (False, 'Disabled'))), **kwargs)

            self.fields[config_name.lower()] = field

        self.order_fields(['username', 'password1', 'password2', 'station_name', 'icecast_enabled',
                           'icecast_passwords'])

    def save(self):
        user = super().save(commit=False)
        user.is_superuser = True
        user.is_staff = True
        user.save()

        for config_name in CONSTANCE_FIELDS:
            setattr(config, config_name, self.cleaned_data[config_name.lower()])

        for config_name in CONSTANCE_ICECAST_PASSWORD_FIELDS:
            setattr(config, config_name, self.cleaned_data['icecast_passwords'])

        init_services(restart_services=True)

        return user
