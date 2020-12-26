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

from common.admin import AudioAssetAdminBase

from .forms import (AudioAssetCreateForm, AudioAssetUploadForm, PlaylistActionForm,
                    RotatorActionForm, RotatorAssetCreateForm)
from .models import AudioAsset, Playlist, Rotator, RotatorAsset, Stopset, StopsetRotator


class RemoveFilterHorizontalFromPopupMixin:
    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if request.GET.get('_popup'):
            for field_name in self.filter_horizontal:
                fields.remove(field_name)
        return fields


class AutoDJModelAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return config.AUTODJ_ENABLED and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return config.AUTODJ_ENABLED and super().has_change_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        return config.AUTODJ_ENABLED and super().has_delete_permission(request, obj=obj)

    def has_view_permission(self, request, obj=None):
        return config.AUTODJ_ENABLED and super().has_view_permission(request, obj=obj)


class AutoDJStopsetRelatedAdmin(AutoDJModelAdmin):
    def has_add_permission(self, request):
        return config.AUTODJ_STOPSETS_ENABLED and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return config.AUTODJ_STOPSETS_ENABLED and super().has_change_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        return config.AUTODJ_STOPSETS_ENABLED and super().has_delete_permission(request, obj=obj)

    def has_view_permission(self, request, obj=None):
        return config.AUTODJ_STOPSETS_ENABLED and super().has_view_permission(request, obj=obj)


class PlaylistAdmin(RemoveFilterHorizontalFromPopupMixin, AutoDJModelAdmin):
    actions = ('set_active_action', 'set_inactive_action')
    search_fields = ('name',)
    fields = ('name', 'is_active', 'weight', 'audio_assets')
    list_display = ('name', 'is_active', 'weight', 'audio_assets_list_display')
    filter_horizontal = ('audio_assets',)

    def set_active_action(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, 'Playlists marked as active.', messages.SUCCESS)
    set_active_action.short_description = 'Activate selected playlists'

    def set_inactive_action(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, 'Playlists marked as inactive.', messages.SUCCESS)
    set_inactive_action.short_description = 'Deactivate selected playlists'

    def has_add_permission(self, request):
        return config.AUTODJ_PLAYLISTS_ENABLED and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return config.AUTODJ_PLAYLISTS_ENABLED and super().has_change_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        return config.AUTODJ_PLAYLISTS_ENABLED and super().has_delete_permission(request, obj=obj)

    def has_view_permission(self, request, obj=None):
        return config.AUTODJ_PLAYLISTS_ENABLED and super().has_view_permission(request, obj=obj)

    def audio_assets_list_display(self, obj):
        return obj.audio_assets.count()
    audio_assets_list_display.short_description = 'Number of audio assets(s)'


class PlaylistInline(admin.StackedInline):
    model = Playlist.audio_assets.through
    verbose_name = 'playlist'
    verbose_name_plural = 'playlists'
    extra = 1


class AudioAssetAdmin(AudioAssetAdminBase, AutoDJModelAdmin):
    playlist_inlines = (PlaylistInline,)
    playlist_actions = ('add_playlist_action', 'remove_playlist_action')
    playlist_action_form = PlaylistActionForm
    create_form = AudioAssetCreateForm
    # title gets swapped to include artist and album
    list_display = ('title', 'created', 'playlists_list_display', 'duration', 'status')
    list_filter = ('playlists',) + AudioAssetAdminBase.list_filter

    @property
    def action_form(self):
        return self.playlist_action_form if config.AUTODJ_PLAYLISTS_ENABLED else super().action_form

    @property
    def actions(self):
        return self.playlist_actions if config.AUTODJ_PLAYLISTS_ENABLED else super().actions

    def get_list_display(self, request):
        list_display = list(super().get_list_display(request))
        if not config.AUTODJ_PLAYLISTS_ENABLED:
            list_display.remove('playlists_list_display')
        return list_display

    def get_list_filter(self, request):
        list_filter = list(self.list_filter)
        if not config.AUTODJ_PLAYLISTS_ENABLED:
            list_filter.remove('playlists')
        return list_filter

    def get_inlines(self, request, obj):
        return self.playlist_inlines if config.AUTODJ_PLAYLISTS_ENABLED else super().inlines

    def playlists_list_display(self, obj):
        return format_html_join(mark_safe(',<br>'), '{}', obj.playlists.values_list('name')) or None
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


class RotatorAdmin(RemoveFilterHorizontalFromPopupMixin, AutoDJStopsetRelatedAdmin):
    fields = ('name', 'rotator_assets')
    filter_horizontal = ('rotator_assets',)
    list_display = ('name', 'rotator_assets_list_display')

    def rotator_assets_list_display(self, obj):
        return obj.rotator_assets.count()
    rotator_assets_list_display.short_description = 'Number of rotator assets(s)'


class RotatorInline(admin.StackedInline):
    model = Rotator.rotator_assets.through
    verbose_name = 'rotator'
    verbose_name_plural = 'rotators'
    extra = 1


class RotatorAssetAdmin(AudioAssetAdminBase, AutoDJStopsetRelatedAdmin):
    inlines = [RotatorInline]
    action_form = RotatorActionForm
    actions = ('add_rotator_action', 'remove_rotator_action')
    create_form = RotatorAssetCreateForm
    search_fields = ('title',)
    list_display = ('title', 'created', 'rotators_list_display', 'duration', 'status')
    list_filter = ('rotators',) + AudioAssetAdminBase.list_filter

    # TODO bulk upload view abstracted from AudioAssets

    def rotators_list_display(self, obj):
        return format_html_join(mark_safe(',<br>'), '{}', obj.rotators.values_list('name')) or None
    rotators_list_display.short_description = 'Rotators(s)'

    def add_rotator_action(self, request, queryset):
        rotator_id = request.POST.get('rotator')
        if rotator_id:
            rotator = Rotator.objects.get(id=rotator_id)
            for rotator_asset in queryset:
                rotator_asset.rotators.add(rotator)
            self.message_user(request, f'Rotator assets were added to rotator {rotator.name}.', messages.SUCCESS)
        else:
            self.message_user(
                request, 'You must select a rotator to add rotator assets to.', messages.WARNING)
    add_rotator_action.short_description = 'Add to rotator'

    def remove_rotator_action(self, request, queryset):
        rotator_id = request.POST.get('rotator')
        if rotator_id:
            rotator = Rotator.objects.get(id=rotator_id)
            for rotator_asset in queryset:
                rotator_asset.rotators.remove(rotator)
            self.message_user(request, f'Rotator assets were removed from rotator {rotator.name}.', messages.SUCCESS)
        else:
            self.message_user(
                request, 'You must select a rotator to remove rotator assets from.', messages.WARNING)
    remove_rotator_action.short_description = 'Delete from rotator'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploader = request.user
        super().save_model(request, obj, form, change)


class StopsetRotatorInline(admin.TabularInline):
    min_num = 1
    extra = 0
    model = StopsetRotator
    verbose_name = 'rotator entry'
    verbose_name_plural = 'rotator entries'

    def get_formset(self, request, obj, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        widget = formset.form.base_fields['rotator'].widget
        widget.can_add_related = widget.can_change_related = False
        return formset


class StopsetAdmin(AutoDJStopsetRelatedAdmin):
    actions = ('set_active_action', 'set_inactive_action')
    inlines = (StopsetRotatorInline,)
    search_fields = ('name',)
    fields = ('name', 'is_active', 'weight')
    list_display = ('name', 'stopset_rotators_list_display', 'is_active', 'weight')

    def set_active_action(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, 'Stop sets marked as active.', messages.SUCCESS)
    set_active_action.short_description = 'Activate selected stop sets'

    def set_inactive_action(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, 'Stop sets marked as inactive.', messages.SUCCESS)
    set_inactive_action.short_description = 'Deactivate selected stop sets'

    def stopset_rotators_list_display(self, obj):
        rotators = StopsetRotator.objects.filter(stopset=obj).values_list('rotator__name', flat=True)
        return format_html_join(mark_safe('<br>'), '{}. {}', enumerate(rotators, 1)) or None
    stopset_rotators_list_display.short_description = 'Rotators(s)'


admin.site.register(Playlist, PlaylistAdmin)
admin.site.register(AudioAsset, AudioAssetAdmin)
admin.site.register(Rotator, RotatorAdmin)
admin.site.register(RotatorAsset, RotatorAssetAdmin)
admin.site.register(Stopset, StopsetAdmin)
