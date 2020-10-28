from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm

from constance import config

from common.models import User
from services import init_services


CONSTANCE_FIELDS = ('STATION_NAME',)
CONSTANCE_ICECAST_PASSWORD_FIELDS = ('ICECAST_SOURCE_PASSWORD', 'ICECAST_RELAY_PASSWORD', 'ICECAST_ADMIN_PASSWORD')


class FirstRunForm(UserCreationForm):
    if settings.ICECAST_ENABLED:
        icecast_passwords = forms.CharField(
            label='Icecast Password', help_text='The password for Icecast (admin, source, relay).')
    email = forms.EmailField(label='Email Address')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for config_name in CONSTANCE_FIELDS:
            default, help_text = settings.CONSTANCE_CONFIG[config_name]
            self.fields[config_name.lower()] = forms.CharField(
                label=config_name.replace('_', ' ').lower().capitalize(),
                help_text=help_text,
                initial=default,
            )

        self.order_fields(['station_name', 'username', 'email', 'password1', 'password2', 'icecast_passwords'])

    class Meta(UserCreationForm.Meta):
        model = User

    def save(self):
        user = super().save(commit=False)
        user.is_superuser = True
        user.is_staff = True
        user.email = self.cleaned_data['email']
        user.save()

        for config_name in CONSTANCE_FIELDS:
            setattr(config, config_name, self.cleaned_data[config_name.lower()])

        if settings.ICECAST_ENABLED:
            for config_name in CONSTANCE_ICECAST_PASSWORD_FIELDS:
                setattr(config, config_name, self.cleaned_data['icecast_passwords'])
            config.ICECAST_ADMIN_EMAIL = user.email

        init_services(restart_services=True)

        return user


class UserProfileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].disabled = True
        self.fields['username'].help_text = ''

    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'timezone')
