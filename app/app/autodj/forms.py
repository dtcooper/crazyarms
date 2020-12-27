from django import forms
from django.contrib.admin.helpers import ActionForm

from common.forms import AudioAssetCreateFormBase

from .models import AudioAsset, Playlist, Rotator, RotatorAsset


class PlaylistActionForm(ActionForm):
    playlist = forms.ModelChoiceField(
        Playlist.objects.all(),
        required=False,
        label=" ",
        empty_label="--- Playlist ---",
    )


class RotatorActionForm(ActionForm):
    rotator = forms.ModelChoiceField(Rotator.objects.all(), required=False, label=" ", empty_label="--- Rotator ---")


class AudioAssetCreateForm(AudioAssetCreateFormBase):
    class Meta(AudioAssetCreateFormBase.Meta):
        model = AudioAsset


class RotatorAssetCreateForm(AudioAssetCreateFormBase):
    class Meta(AudioAssetCreateFormBase.Meta):
        model = RotatorAsset
