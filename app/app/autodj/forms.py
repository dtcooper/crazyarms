from django import forms

from common.forms import AudioAssetCreateFormBase

from .models import AudioAsset


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
