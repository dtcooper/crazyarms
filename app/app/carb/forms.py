import datetime
import logging

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.text import normalize_newlines

from constance import admin as constance_admin, config

from .models import User, PrerecordedAsset
from .services import init_services
from .tasks import sync_google_calendar_api


CONSTANCE_FIELDS = ('STATION_NAME',)
CONSTANCE_ICECAST_PASSWORD_FIELDS = ('ICECAST_SOURCE_PASSWORD', 'ICECAST_RELAY_PASSWORD', 'ICECAST_ADMIN_PASSWORD')

logger = logging.getLogger(__name__)


class FirstRunForm(UserCreationForm):
    if settings.ICECAST_ENABLED:
        icecast_passwords = forms.CharField(
            label='Icecast Password', help_text='The password for Icecast (admin, source, relay)')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for config_name in CONSTANCE_FIELDS:
            default, help_text = settings.CONSTANCE_CONFIG[config_name]
            self.fields[config_name.lower()] = forms.CharField(
                label=config_name.replace('_', ' ').lower().capitalize(),
                help_text=help_text,
                initial=default,
            )

        self.order_fields(['station_name', 'username', 'password1', 'password2', 'icecast_passwords'])

    class Meta(UserCreationForm.Meta):
        model = User

    def save(self):
        user = super().save(commit=False)
        user.is_superuser = True
        user.is_staff = True
        user.save()

        for config_name in CONSTANCE_FIELDS:
            setattr(config, config_name, self.cleaned_data[config_name.lower()])

        if settings.ICECAST_ENABLED:
            for config_name in CONSTANCE_ICECAST_PASSWORD_FIELDS:
                setattr(config, config_name, self.cleaned_data['icecast_passwords'])
            config.ICECAST_ADMIN_EMAIL = user.email

        init_services(restart_services=True)

        return user


class AudioAssetCreateForm(forms.ModelForm):
    url = forms.URLField(label='External URL', required=False, help_text=mark_safe(
        'URL on an external service like SoundCloud, Mixcloud, YouTube, direct link, etc. If provided, it will be '
        'downloaded. (Complete list of supported services <a href="https://ytdl-org.github.io/youtube-dl/supported'
        'sites.html" target="_blank">here</a>.)'))
    url.widget.attrs.update({'class': 'vLargeTextField'})
    source = forms.ChoiceField(label='Source type', choices=(('file', 'Uploaded file'), ('url', 'External URL')),
                               initial='file')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].widget.attrs.update({'placeholder': "Leave empty to extract from file's metadata"})

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data['source'] == 'url':
            if not cleaned_data['url']:
                self.add_error('url', 'This field is required.')
                return


class PrerecordedAssetCreateForm(AudioAssetCreateForm):
    class Meta:
        model = PrerecordedAsset
        fields = '__all__'


class ConstanceForm(constance_admin.ConstanceForm):
    def save(self):
        # Modified from parent class in order to hook changes in groups (instead of one signal for each)
        changes = []

        for file_field in self.files:
            file = self.cleaned_data[file_field]
            self.cleaned_data[file_field] = default_storage.save(file.name, file)

        for name in settings.CONSTANCE_CONFIG:
            current = getattr(config, name)
            new = self.cleaned_data[name]

            if isinstance(new, str):
                new = normalize_newlines(new)

            if settings.USE_TZ and isinstance(current, datetime.datetime) and not timezone.is_aware(current):
                current = timezone.make_aware(current)

            if current != new:
                setattr(config, name, new)
                changes.append(name)

        if changes:
            self.process_config_changes(changes)

    def process_config_changes(self, changes):
        if any(change.startswith('GOOGLE_CALENDAR') for change in changes):
            logger.info("Got GOOGLE_CALENDAR_* config change. Re-sync'ing")
            sync_google_calendar_api()
        if any(change.startswith('ICECAST') for change in changes):
            init_services(services=('upstream', 'icecast',), restart_services=True)
