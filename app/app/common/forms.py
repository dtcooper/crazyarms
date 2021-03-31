import logging

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.safestring import mark_safe

from constance import config
from constance.admin import ConstanceForm

from gcal.tasks import sync_gcal_api
from services import init_services

logger = logging.getLogger(f"crazyarms.{__name__}")


class AudioAssetCreateFormBase(forms.ModelForm):
    url = forms.URLField(
        label="External URL",
        required=False,
        help_text=mark_safe(
            "URL on an external service like SoundCloud, Mixcloud, YouTube, direct link, etc. If provided, it"
            " will be downloaded. (Complete list of supported services <a"
            ' href="https://ytdl-org.github.io/youtube-dl/supportedsites.html" target="_blank">here</a>.)'
        ),
    )
    url.widget.attrs.update({"class": "vLargeTextField"})
    source = forms.ChoiceField(
        label="Source type",
        choices=(("file", "Uploaded file"), ("url", "External URL")),
        initial="file",
    )

    class Meta:
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self._meta.model.TITLE_FIELDS:
            self.fields[field].widget.attrs.update(
                {
                    "placeholder": "Leave empty to extract from file's metadata",
                    "class": "vLargeTextField",
                }
            )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data["source"] == "url":
            if not cleaned_data.get("url"):
                self.add_error("url", "This field is required.")
        else:
            if not cleaned_data.get("file"):
                self.add_error("file", "This field is required.")

    def save(self, commit=True):
        asset = super().save(commit=False)
        if self.cleaned_data["source"] == "url":
            asset.run_download_after_save_url = self.cleaned_data["url"]
        if commit:
            asset.save()
        return asset


class ProcessConfigChangesConstanceForm(ConstanceForm):
    def save(self):
        pre_save = {name: getattr(config, name) for name in settings.CONSTANCE_CONFIG}
        super().save()
        post_save = {name: getattr(config, name) for name in settings.CONSTANCE_CONFIG}
        config_changes = [name for name in settings.CONSTANCE_CONFIG if pre_save[name] != post_save[name]]
        if config_changes:
            self.process_config_changes(config_changes)

    def process_config_changes(self, changes):
        # TODO if we move this in ConstanceAdmin's save_model(), we can send messages to the request
        if any(change.startswith("GOOGLE_CALENDAR_") for change in changes):
            logger.info("Got GOOGLE_CALENDAR_* config change. Re-sync'ing")
            sync_gcal_api()
        if any(change.startswith("ICECAST_") for change in changes):
            logger.info("Got ICECAST_* config change. Restarting icecast.")
            init_services(services="icecast")
        if any(change.startswith("HARBOR_") for change in changes) or "AUTODJ_ENABLED" in changes:
            logger.info("Got HARBOR_* or AUTODJ_ENABLED config change. Restarting harbor.")
            init_services(services="harbor", subservices="harbor")
        if "ICECAST_SOURCE_PASSWORD" in changes:
            logger.info(
                "Got ICECAST_SOURCE_PASSWORD config change. Setting local-icecast/local-icecast-test upstream password."
            )
            init_services(services="upstream", subservices=("local-icecast", "local-icecast-test"))
        if any(change.startswith("UPSTREAM_") for change in changes) or "HARBOR_TEST_ENABLED" in changes:
            logger.info("Got UPSTREAM_* or HARBOR_TEST_ENABLED config change. Restarting upstreams.")
            init_services(services="upstream", restart_services=True)


class EmailUserCreationForm(UserCreationForm):
    send_email = forms.BooleanField(
        label="Send welcome email to new user",
        required=False,
        help_text=(
            "Check this box to send the user an email notifying them of their new "
            "account, allowing them to set their password. The link will be good "
            "for 14 days."
        ),
    )


class EmailUserChangeForm(UserChangeForm):
    send_email = forms.BooleanField(
        label="Send password change email to user",
        required=False,
        help_text=(
            "Check this box and save the form to send the user an email, allowing "
            "them to change the password for their account. The link will be good "
            "for 14 days."
        ),
    )
