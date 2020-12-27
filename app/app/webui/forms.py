import datetime
import logging
import math
import re
from urllib.parse import parse_qs, urlparse

import requests

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.safestring import mark_safe

from constance import config
from django_select2.forms import ModelSelect2Widget

from autodj.models import AudioAsset, Playlist, Rotator, RotatorAsset, Stopset, StopsetRotator
from common.models import User, generate_random_string
from services import init_services

NUM_SAMPLE_CCMIXTER_ASSETS = 10 if settings.DEBUG else 75  # Less if running in DEBUG mode, faster testing

# Sample Data
ROTATOR_ASSETS_URL_PREFIX = "https://crazy-arms-sample.nyc3.digitaloceanspaces.com/rotator-assets/"
SAMPLE_ROTATOR_ASSETS_URLS = {
    ("id", "Sample Station IDs"): [f"{ROTATOR_ASSETS_URL_PREFIX}station-id-{n}.mp3" for n in range(1, 9)],
    ("ad", "Sample Advertisements"): [f"{ROTATOR_ASSETS_URL_PREFIX}ad-{n}.mp3" for n in range(1, 6)],
    ("psa", "Sample Public Service Announcements"): [f"{ROTATOR_ASSETS_URL_PREFIX}psa-{n}.mp3" for n in range(1, 4)],
}
CCMIXTER_API_URL = "http://ccmixter.org/api/query"
# Ask for a few month, since we only want ones with mp3s
CCMIXTER_API_PARAMS = {
    "sinced": "1 month ago",
    "sort": "rank",
    "f": "js",
    "limit": round(NUM_SAMPLE_CCMIXTER_ASSETS * 1.5),
}
SAMPLE_STOPSETS = (
    ("id", "ad", "psa", "ad", "id"),
    ("id", "ad", "id"),
    ("id", "ad", "ad", "id", "psa"),
)

logger = logging.getLogger(f"carb.{__name__}")


class FirstRunForm(UserCreationForm):
    if settings.ICECAST_ENABLED:
        icecast_admin_password = forms.CharField(
            label="Icecast Admin Password",
            help_text=mark_safe(
                "The password for the Icecast admin web page.<br>(WARNING: Stored as configuration in plain"
                " text, but only viewable by users with configuration permission, ie admins.)"
            ),
        )
    email = forms.EmailField(label="Email Address")
    generate_sample_assets = forms.BooleanField(
        label="Preload AutoDJ",
        required=False,
        widget=forms.Select(choices=((False, "No"), (True, "Yes"))),
        help_text=mark_safe(
            'Preload the AutoDJ with ADs, PSDs and station IDs from <a href="https://en.wikipedia.org/'
            f'wiki/BMIR" target="_blank">BMIR</a> and download {NUM_SAMPLE_CCMIXTER_ASSETS} of this '
            'month\'s most popular tracks from <a href="http://ccmixter.org/" target="_blank">ccMixter'
            "</a> to kick start your station or to try out Crazy Arms. (Creative Commons licensed)"
        ),
    )
    station_name = forms.CharField(label="Station Name", help_text="The name of your radio station.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.pop("autofocus", None)
        self.order_fields(
            (
                "station_name",
                "username",
                "email",
                "password1",
                "password2",
                "icecast_admin_password",
                "generate_sample_assets",
            )
        )

    class Meta(UserCreationForm.Meta):
        model = User

    @staticmethod
    def preload_sample_audio_assets(uploader):
        ccmixter_urls = []

        ccmixter_json = requests.get(CCMIXTER_API_URL, params=CCMIXTER_API_PARAMS).json()
        num_assets = 0
        for ccmixter_track in ccmixter_json:
            try:
                url = next(f["download_url"] for f in ccmixter_track["files"] if f["download_url"].endswith(".mp3"))
            except StopIteration:
                logger.warning(f'ccMixter track track {ccmixter_track["upload_name"]} has no mp3!')
            else:
                num_assets += 1
                ccmixter_urls.append(url)

                if num_assets >= NUM_SAMPLE_CCMIXTER_ASSETS:
                    break

        logger.info(f"Got {len(ccmixter_urls)} sample asset URLs from ccMixter")

        playlist = Playlist.objects.get_or_create(name="ccMixter Sample Music")[0]
        for url in ccmixter_urls:
            asset = AudioAsset(uploader=uploader)
            asset.run_download_after_save_url = url
            asset.save()
            asset.playlists.add(playlist)

        rotators = {}
        for (code, name), urls in SAMPLE_ROTATOR_ASSETS_URLS.items():
            rotators[code] = Rotator.objects.get_or_create(name=name)[0]
            for url in urls:
                asset = RotatorAsset(uploader=uploader)
                asset.run_download_after_save_url = url
                asset.save()
                asset.rotators.add(rotators[code])

        for n, stopset_rotators in enumerate(SAMPLE_STOPSETS, 1):
            stopset = Stopset.objects.get_or_create(name=f"Sample Stopset #{n}")[0]
            for rotator in stopset_rotators:
                StopsetRotator.objects.create(rotator=rotators[rotator], stopset=stopset)

    def save(self):
        user = super().save(commit=False)
        user.is_superuser = True
        user.email = self.cleaned_data["email"]
        user.save()

        config.STATION_NAME = self.cleaned_data["station_name"]

        if settings.ICECAST_ENABLED:
            config.ICECAST_ADMIN_EMAIL = user.email
            config.ICECAST_ADMIN_PASSWORD = self.cleaned_data["icecast_admin_password"]
            config.ICECAST_SOURCE_PASSWORD = generate_random_string(16)
            config.ICECAST_RELAY_PASSWORD = generate_random_string(16)

        if self.cleaned_data["generate_sample_assets"]:
            self.preload_sample_audio_assets(uploader=user)
            config.AUTODJ_STOPSETS_ENABLED = True

        init_services(restart_services=True)

        return user


class AutoDJRequestsForm(forms.Form):
    asset = forms.ModelChoiceField(
        queryset=AudioAsset.objects.filter(status=AudioAsset.Status.READY),
        widget=ModelSelect2Widget(
            model=AudioAsset,
            search_fields=("title__icontains", "album__icontains", "artist__icontains"),
            data_view="autodj_request_choices",
        ),
    )


class UserProfileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.is_superuser:
            # Make sure these fields are only editable by superusers
            for field_name in (
                "username",
                "email",
                "harbor_auth",
                "gcal_entry_grace_minutes",
                "gcal_exit_grace_minutes",
            ):
                field = self.fields[field_name]
                field.disabled = True
                field.help_text += " (Read-only. You'll need an administrator to update this for you.)"

        self.fields["timezone"].help_text = f'(Currently {date_format(timezone.localtime(), "SHORT_DATETIME_FORMAT")})'

        remove_grace_fields = self.instance.harbor_auth != User.HarborAuth.GOOGLE_CALENDAR
        if not config.GOOGLE_CALENDAR_ENABLED:
            self.fields["harbor_auth"].choices = list(
                filter(
                    lambda c: c[0] != User.HarborAuth.GOOGLE_CALENDAR,
                    User.HarborAuth.choices,
                )
            )
            remove_grace_fields = True

        if remove_grace_fields:
            del self.fields["gcal_entry_grace_minutes"]
            del self.fields["gcal_exit_grace_minutes"]

        if not self.instance.get_sftp_allowable_models():
            del self.fields["authorized_keys"]

        if settings.EMAIL_ENABLED and not self.instance.is_superuser:
            del self.fields["email"]
            self.fields["update_email"] = forms.EmailField(
                label="Email address",
                required=True,
                initial=self.instance.email,
                max_length=User._meta.get_field("email").max_length,
            )

        if AudioAsset not in self.instance.get_sftp_allowable_models():
            del self.fields["default_playlist"]

        self.order_fields(
            (
                "username",
                "email",
                "new_email",
                "timezone",
                "first_name",
                "last_name",
                "harbor_authdefault_playlist",
                "gcal_entry_grace_minutes",
                "gcal_exit_grace_minutes",
                "authorized_keys",
            )
        )

    def clean_update_email(self):
        email = self.cleaned_data["update_email"]
        if email != self.instance.email:
            if User.objects.filter(email=email).exists():
                raise forms.ValidationError("User with this Email address already exists.")
            return email
        return None

    class Meta:
        model = User
        fields = (
            "username",
            "timezone",
            "first_name",
            "last_name",
            "email",
            "default_playlist",
            "harbor_auth",
            "gcal_entry_grace_minutes",
            "gcal_exit_grace_minutes",
            "authorized_keys",
        )


class ZoomForm(forms.Form):
    TTL_RE = re.compile(r"^(?:(\d+):)?(\d+)$")
    MINUTE_STEP_AMOUNT = 15

    show_name = forms.CharField(
        label="Show Name",
        required=False,
        help_text="The name of your show for the stream's metadata. Can be left blank.",
    )
    zoom_room = forms.URLField(
        label="Room Link",
        help_text="Pasted from Zoom. Consult the Help Docs for more info.",
        widget=forms.TextInput(attrs={"placeholder": "https://zoom.us/j/91234567890?pwd=XYZ0XYZ0XYZ0XYZ0XYZ0XYZ0XYZ"}),
    )

    @staticmethod
    def pretty_seconds(seconds):
        minutes = int(seconds / 60)
        s = ""
        if minutes > 60:
            hours = minutes // 60
            minutes = minutes % 60
            s += f'{hours} hour{"s" if hours != 1 else ""}, '
        return f'{s}{minutes} minute{"s" if minutes != 1 else ""}'

    def __init__(
        self,
        user,
        now,
        zoom_is_running,
        currently_authorized,
        authorization_time_bound,
        *args,
        **kwargs,
    ):
        self.zoom_is_running = zoom_is_running
        self.currently_authorized = currently_authorized
        self.values = {}
        super().__init__(*args, **kwargs)

        choices = []
        initial = "default"
        self.values["max"] = config.ZOOM_MAX_SHOW_LENTH_MINUTES * 60

        if authorization_time_bound:
            grace = authorization_time_bound
            self.values["grace"] = self.values["max"] = math.ceil((grace - now).total_seconds())

            default = authorization_time_bound - datetime.timedelta(minutes=user.gcal_exit_grace_minutes)
            if default > now:
                choices.append(
                    (
                        "default",
                        f'Until {date_format(timezone.localtime(default), "SHORT_DATETIME_FORMAT")} (current '
                        "scheduled show)",
                    )
                )
                self.values["default"] = math.ceil((default - now).total_seconds())
            else:
                initial = "grace"

            choices.append(
                (
                    "grace",
                    f'Until {date_format(timezone.localtime(grace), "SHORT_DATETIME_FORMAT")} '
                    f"(current scheduled show, including {user.gcal_exit_grace_minutes} "
                    "minute grace period)",
                )
            )
        else:
            self.values["default"] = 60 * min(
                config.ZOOM_MAX_SHOW_LENTH_MINUTES,
                config.ZOOM_DEFAULT_SHOW_LENTH_MINUTES,
            )
            choices.append(
                (
                    "default",
                    f'{self.pretty_seconds(self.values["default"])} (default show length)',
                )
            )

        for seconds in range(
            self.MINUTE_STEP_AMOUNT * 60,
            self.values["max"],
            self.MINUTE_STEP_AMOUNT * 60,
        ):
            choices.append((seconds, self.pretty_seconds(seconds)))
        choices.append(("max", f'{self.pretty_seconds(self.values["max"])} (maximum show length)'))

        self.fields["ttl"] = forms.ChoiceField(
            label="Show Duration",
            choices=choices,
            initial=initial,
            help_text=(
                "If you're not totally sure, go for little longer than expected. You can always can come"
                " here and stop the show early with this form. Otherwise, your show might end too soon."
                f" (Timezone {user.timezone})"
            ),
        )
        self.order_fields(("show_name", "ttl", "zoom_room"))

    def clean_ttl(self):
        ttl = self.cleaned_data["ttl"]
        return int(ttl) if ttl.isdigit() else self.values[ttl]

    def clean_zoom_room(self):
        zoom_room = self.cleaned_data["zoom_room"]
        url = urlparse(zoom_room)
        meeting_id = url.path.rsplit("/", 1)[-1]
        if not meeting_id.isdigit():
            raise forms.ValidationError("Couldn't get Zoom Meeting ID from URL.")

        meeting_pwd = parse_qs(url.query).get("pwd", [""])[0]
        return (meeting_id, meeting_pwd)

    def clean(self):
        cleaned_data = super().clean()
        if not self.currently_authorized:
            raise forms.ValidationError("You are not currently authorized. Can't start a new show.")
        if self.zoom_is_running:
            raise forms.ValidationError("Zoom is currently running. Can't start a new show.")
        return cleaned_data
