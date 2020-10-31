from django.contrib import admin

from common.admin import AssetAdminBase

from .forms import AudioAssetCreateForm
from .models import AudioAsset


class AudioAssetAdmin(AssetAdminBase):
    create_form = AudioAssetCreateForm


admin.site.register(AudioAsset, AudioAssetAdmin)
