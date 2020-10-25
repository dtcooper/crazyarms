from common.forms import AudioAssetCreateFormBase

from .models import BroadcastAsset


class BroadcastAssetCreateForm(AudioAssetCreateFormBase):
    class Meta:
        model = BroadcastAsset
        fields = '__all__'
