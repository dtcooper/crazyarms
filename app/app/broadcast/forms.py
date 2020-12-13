from common.forms import AudioAssetCreateFormBase

from .models import BroadcastAsset


class BroadcastAssetCreateForm(AudioAssetCreateFormBase):
    class Meta(AudioAssetCreateFormBase.Meta):
        model = BroadcastAsset
