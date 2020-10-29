from django.contrib import admin

from common.admin import AssetAdminBase

from .forms import AudioAssetCreateForm
from .models import AudioAsset


class AudioAssetAdmin(AssetAdminBase):
    create_form = AudioAssetCreateForm
    add_fields = ('title', 'artist', 'album', 'source', 'file', 'url', 'status', 'uploader')
    change_fields = ('title', 'artist', 'album', 'file', 'duration', 'status', 'uploader', 'task_log_line')
    search_fields = ('title', 'artist', 'album')
    list_display = ('title', 'artist', 'album', 'uploader', 'duration', 'status')

admin.site.register(AudioAsset, AudioAssetAdmin)
