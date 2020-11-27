from common.forms import AudioAssetDownloadableCreateFormBase

from .models import BroadcastAsset


class BroadcastAssetCreateForm(AudioAssetDownloadableCreateFormBase):
    class Meta(AudioAssetDownloadableCreateFormBase.Meta):
        model = BroadcastAsset
