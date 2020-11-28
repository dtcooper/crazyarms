import datetime
import random
import re
import string
from urllib.parse import parse_qs, urlparse

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.safestring import mark_safe

from constance import config

from common.models import User
from services import init_services

from .tasks import preload_sample_audio_assets, preload_sample_stopsets, NUM_SAMPLE_ASSETS


class FirstRunForm(UserCreationForm):
    if settings.ICECAST_ENABLED:
        icecast_admin_password = forms.CharField(label='Icecast Admin Password', help_text=mark_safe(
            'The password for the Icecast admin web page.<br>(WARNING: Stored as configuration in plain text, but '
            'only viewable by users with configuration permission, ie admins.)'))
    email = forms.EmailField(label='Email Address')
    generate_sample_assets = forms.BooleanField(
        label='Preload AutoDJ', required=False,
        widget=forms.Select(choices=((False, 'No'), (True, 'Yes (this may take a while)'))),
        help_text=mark_safe('Preload AutoDJ with ADs, PSDs and station IDs from <a href="https://en.wikipedia.org/wiki/'
                            f'BMIR" target="_blank">BMIR</a> and download {NUM_SAMPLE_ASSETS} of this month\'s most '
                            'popular tracks from <a href="http://ccmixter.org/" target="_blank">ccMixter</a> to kick '
                            'start your station or demo Crazy Arms Radio Backend. (Creative Commons licensed)'))
    station_name = forms.CharField(label='Station Name', help_text='The name of your radio station.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(['station_name', 'username', 'email', 'password1', 'password2', 'icecast_passwords'])

    class Meta(UserCreationForm.Meta):
        model = User

    @staticmethod
    def random_password():
        return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16))

    def save(self):
        user = super().save(commit=False)
        user.is_superuser = True
        user.email = self.cleaned_data['email']
        user.save()

        config.STATION_NAME = self.cleaned_data['station_name']

        if settings.ICECAST_ENABLED:
            config.ICECAST_ADMIN_EMAIL = user.email
            config.ICECAST_ADMIN_PASSWORD = self.cleaned_data['icecast_admin_password']
            config.ICECAST_SOURCE_PASSWORD = self.random_password()
            config.ICECAST_RELAY_PASSWORD = self.random_password()

        if self.cleaned_data['generate_sample_assets']:
            preload_sample_audio_assets(uploader=user)
            preload_sample_stopsets(uploader=user)

        init_services(restart_services=True)

        return user


class UserProfileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.is_superuser:
            # Make sure these fields are only editable by superusers
            for field_name in ('username', 'email', 'harbor_auth'):
                field = self.fields[field_name]
                field.disabled = True
                field.help_text = 'Read-only. Please ask an administrator to update.'

        self.fields['timezone'].help_text = f'Currently {date_format(timezone.localtime(), "SHORT_DATETIME_FORMAT")}'

        if not config.GOOGLE_CALENDAR_ENABLED:
            self.fields['harbor_auth'].choices = list(filter(
                lambda c: c[0] != User.HarborAuth.GOOGLE_CALENDAR, User.HarborAuth.choices))

    class Meta:
        model = User
        fields = ('username', 'timezone', 'first_name', 'last_name', 'email', 'harbor_auth')


class ZoomForm(forms.Form):
    TTL_RE = re.compile(r'^(?:(\d+):)?(\d+)$')
    MAX_SHOW_LENGTH_HOURS = 4

    show_name = forms.CharField(label='Show Name', required=False,
                                help_text="The name of your show for the stream's metadata. Can be left blank.")
    ttl = forms.CharField(label='Show Length', help_text=mark_safe(
        # Use dropdown with choices. Make util/template filter to convert seconds to a pretty duration
        # and use that in zoom.html
        'In <code>HH:MM</code> or<code>HH</code> format, ie <code>2:00</code> or <code>2</code> for two hours.'),
        widget=forms.TextInput(attrs={'placeholder': '2:00'}))
    zoom_room = forms.URLField(label='Room Link', help_text='Pasted from Zoom. See broadcasting instructions above.',
                               widget=forms.TextInput(attrs={
                                   'placeholder': 'https://zoom.us/j/91234567890?pwd=XYZ0XYZ0XYZ0XYZ0XYZ0XYZ0XYZ'}))

    def __init__(self, user, zoom_is_running, room_env, *args, **kwargs):
        self.user = user
        self.zoom_is_running = zoom_is_running
        self.room_env = room_env
        super().__init__(*args, **kwargs)

    def clean_ttl(self):
        ttl = self.cleaned_data['ttl']
        match = self.TTL_RE.search(ttl)
        if match:
            hours, minutes = match.group(1), match.group(2)
            if not hours:
                hours, minutes = minutes, '0'
            hours, minutes = int(hours), int(minutes)
            if minutes >= 60:
                raise forms.ValidationError(f'Invalid number of minutes ({minutes}). Must be between 00 and 59.')

            show_length = datetime.timedelta(hours=hours, minutes=minutes)
            if show_length > datetime.timedelta(hours=self.MAX_SHOW_LENGTH_HOURS):
                raise forms.ValidationError(f'Show can be at maximum {self.MAX_SHOW_LENGTH_HOURS} hours.')

            return int(show_length.total_seconds())
        else:
            raise forms.ValidationError('Invalid show length.')

    def clean_zoom_room(self):
        zoom_room = self.cleaned_data['zoom_room']
        url = urlparse(zoom_room)
        meeting_id = url.path.rsplit('/', 1)[-1]
        if not meeting_id.isdigit():
            raise forms.ValidationError("Couldn't get Zoom Meeting ID from URL.")

        meeting_pwd = parse_qs(url.query).get('pwd', [''])[0]
        return (meeting_id, meeting_pwd)

    def clean(self):
        if self.zoom_is_running:
            raise forms.ValidationError("Zoom is currently running. Can't start a new show.")
        return self.cleaned_data
