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
        pre_save = {name: getattr(config, name) for name in settings.CONSTANCE_CONFIG}
        super().save()
        post_save = {name: getattr(config, name) for name in settings.CONSTANCE_CONFIG}
        config_changes = [name for name in settings.CONSTANCE_CONFIG if pre_save[name] != post_save[name]]
        if config_changes:
            self.process_config_changes(config_changes)

    def process_config_changes(self, changes):
        # TODO if we move this in ConstanceAdmin, we can send messages to the request
        if any(change.startswith('GOOGLE_CALENDAR') for change in changes):
            logger.info("Got GOOGLE_CALENDAR_* config change. Re-sync'ing")
            sync_google_calendar_api()
        if any(change.startswith('ICECAST') for change in changes):
            logger.info('Got ICECAST_* config change. Restarting upstream and icecast.')
            init_services(services=('upstream', 'icecast',), restart_services=True)
