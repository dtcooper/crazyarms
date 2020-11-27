from django import forms
from django.core.exceptions import PermissionDenied
from django.contrib import admin, messages
from django.contrib.admin.helpers import AdminForm
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe

from constance import config

from common.admin import AssetAdminBase

from .forms import AudioAssetCreateForm, AudioAssetUploadForm, PlaylistActionForm
from .models import AudioAsset, Playlist


class PlaylistAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    fields = ('name', 'is_active', 'weight', 'audio_assets')
    list_display = ('name', 'is_active', 'weight', 'audio_assets_list_display')
    filter_horizontal = ('audio_assets',)

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if request.GET.get('_popup'):
            # A bit messy to include this in the popup window
            fields.remove('audio_assets')
        return fields

    def audio_assets_list_display(self, obj):
        return obj.audio_assets.count()
    audio_assets_list_display.short_description = 'Number of audio assets(s)'


class PlaylistInline(admin.StackedInline):
    model = Playlist.audio_assets.through
    can_delete = False
    verbose_name = 'playlist'
    verbose_name_plural = 'playlists'
    extra = 1


class AudioAssetAdmin(AssetAdminBase):
    inlines = (PlaylistInline,)
    action_form = PlaylistActionForm
    create_form = AudioAssetCreateForm
    # title gets swapped to include artist and album
    list_display = ('title', 'playlists_list_display', 'duration', 'status')
    actions = ('add_playlist_action', 'remove_playlist_action')
    list_filter = ('playlists',) + AssetAdminBase.list_filter

    def playlists_list_display(self, obj):
        return format_html_join(mark_safe(',<br>'), '{}', obj.playlists.values_list('name'))
    playlists_list_display.short_description = 'Playlist(s)'

    def add_playlist_action(self, request, queryset):
        playlist_id = request.POST.get('playlist')
        if playlist_id:
            playlist = Playlist.objects.get(id=playlist_id)
            for audio_asset in queryset:
                audio_asset.playlists.add(playlist)
            self.message_user(request, f'Audio assets were added to playlist {playlist.name}.', messages.SUCCESS)
        else:
            self.message_user(
                request, 'You must select a playlist to add audio assets to.', messages.WARNING)
    add_playlist_action.short_description = 'Add to playlist'

    def remove_playlist_action(self, request, queryset):
        playlist_id = request.POST.get('playlist')
        if playlist_id:
            playlist = Playlist.objects.get(id=playlist_id)
            for audio_asset in queryset:
                audio_asset.playlists.remove(playlist)
            self.message_user(request, f'Audio assets were removed from playlist {playlist.name}.', messages.SUCCESS)
        else:
            self.message_user(
                request, 'You must select a playlist to remove audio assets from.', messages.WARNING)
    remove_playlist_action.short_description = 'Remove from playlist'

    def get_urls(self):
        return [path('upload/', self.admin_site.admin_view(self.upload_view),
                name='autodj_audioasset_upload')] + super().get_urls()

    def has_add_permission(self, request):
        return config.AUTODJ_ENABLED and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return config.AUTODJ_ENABLED and super().has_change_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        return config.AUTODJ_ENABLED and super().has_delete_permission(request, obj=obj)

    def has_view_permission(self, request, obj=None):
        return config.AUTODJ_ENABLED and super().has_view_permission(request, obj=obj)

    def upload_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied

        if request.method == 'POST':
            form = AudioAssetUploadForm(request.POST, request.FILES)
            if form.is_valid():
                files = request.FILES.getlist('audios')
                audio_assets = []

                for file in files:
                    asset = AudioAsset(file=file)
                    audio_assets.append(asset)

                    try:
                        asset.clean()
                    except forms.ValidationError as validation_error:
                        for field, error_list in validation_error:
                            for error in error_list:
                                form.add_error('audios' if field == 'audio' else '__all__', error)

            # If no errors were added
            if form.is_valid():
                playlists = form.cleaned_data.get('playlists', [])

                for audio_asset in audio_assets:
                    audio_asset.uploader = request.user
                    audio_asset.save()
                    audio_asset.playlists.add(*playlists)

                self.message_user(request, f'Uploaded {len(audio_assets)} audio assets.', messages.SUCCESS)

                return redirect('admin:autodj_audioasset_changelist')
        else:
            form = AudioAssetUploadForm()

        opts = self.model._meta
        return TemplateResponse(request, 'admin/autodj/audioasset/upload.html', {
            'adminform': AdminForm(form, [(None, {'fields': form.base_fields})],
                                   self.get_prepopulated_fields(request)),
            'app_label': opts.app_label,
            'errors': form.errors.values(),
            'form': form,
            'opts': opts,
            'save_on_top': self.save_on_top,
            'title': 'Bulk Upload Audio Assets',
            **self.admin_site.each_context(request),
        })


admin.site.register(Playlist, PlaylistAdmin)
admin.site.register(AudioAsset, AudioAssetAdmin)
