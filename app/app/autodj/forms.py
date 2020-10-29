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
