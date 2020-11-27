from django import forms
from django.contrib.admin.helpers import ActionForm

from common.forms import AudioAssetCreateFormBase

from .models import AudioAsset, Playlist


class PlaylistActionForm(ActionForm):
    playlist = forms.ModelChoiceField(Playlist.objects.all(), required=False, label=' ', empty_label='--- Playlist ---')


class AudioAssetCreateForm(AudioAssetCreateFormBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        title_attrs = self.fields['title'].widget.attrs
        self.fields['artist'].widget.attrs.update(title_attrs)
        self.fields['album'].widget.attrs.update(title_attrs)

    class Meta:
        model = AudioAsset
        fields = '__all__'


class AudioAssetUploadForm(forms.Form):
    audios = forms.FileField(
        widget=forms.FileInput(attrs={'multiple': True}), required=True, label='Audio files',
        help_text='Select multiple audio files to upload using Shift, CMD, and/or Alt in the dialog.')

    def __init__(self, *args, **kwargs):
        if Playlist.objects.exists():
            # Needs to be in base_fields because of the way AudioAssetAdmin.upload_view() passes context to template
            self.base_fields['playlists'] = forms.ModelMultipleChoiceField(
                Playlist.objects.all(), required=False, widget=forms.CheckboxSelectMultiple(),
                label='Playlist(s)', help_text="Optionally select playlists to these audio assets to. If you don't "
                'select a playlist, this asset will not be scheduled for playout by the AutoDJ')
        super().__init__(*args, **kwargs)
