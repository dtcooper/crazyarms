import datetime
import logging

from django import forms
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.text import normalize_newlines
from django.utils.safestring import mark_safe

from constance import admin as constance_admin, config

from services import init_services
from gcal.tasks import sync_google_calendar_api


logger = logging.getLogger(f'carb.{__name__}')


class AudioAssetCreateFormBase(forms.ModelForm):
    url = forms.URLField(label='External URL', required=False, help_text=mark_safe(
        'URL on an external service like SoundCloud, Mixcloud, YouTube, direct link, etc. If provided, it will be '
        'downloaded. (Complete list of supported services <a href="https://ytdl-org.github.io/youtube-dl/supported'
        'sites.html" target="_blank">here</a>.)'))
    url.widget.attrs.update({'class': 'vLargeTextField'})
    source = forms.ChoiceField(label='Source type', choices=(('file', 'Uploaded file'), ('url', 'External URL')),
                               initial='file')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].widget.attrs.update({'placeholder': "Leave empty to extract from file's metadata",
                                                  'class': 'vLargeTextField'})

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data['source'] == 'url':
            if not cleaned_data['url']:
                self.add_error('url', 'This field is required.')
                return


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
            logger.info('Got ICECAST_* config change. Restarting upstream and icecast.')
            init_services(services=('upstream', 'icecast',), restart_services=True)
