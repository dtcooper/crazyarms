from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import path

from constance import config

from .forms import PrerecordedAssetCreateForm
from .models import GoogleCalendarShow, PrerecordedAsset, PrerecordedBroadcast, User
from .tasks import sync_google_calendar_api


class CarbUserAdmin(UserAdmin):
    save_on_top = True
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Personal info', {'fields': (('first_name', 'last_name'),)}),
        ('Permissions', {'fields': ('harbor_auth', 'is_active', 'is_staff', 'is_superuser', 'groups')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'harbor_auth', 'is_superuser')
    list_filter = ('is_superuser', 'is_active', 'groups')
    readonly_fields = ('last_login', 'date_joined')
    add_fieldsets = (
        (None, {'fields': ('username', 'email', 'password1', 'password2')}),
        ('Personal info', {'fields': (('first_name', 'last_name'),)}),
        ('Permissions', {'fields': ('harbor_auth', 'is_staff', 'is_superuser', 'groups')}),
    )


class GoogleCalendarShowAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('title', 'start', 'end', 'users_list')
    fields = ('title', 'start', 'end', 'users_list')
    list_filter = (('users', admin.RelatedOnlyFieldListFilter), 'start')
    date_hierarchy = 'start'

    def get_urls(self):
        return [path('sync/', self.admin_site.admin_view(self.sync_view),
                name='carb_googlecalendarshow_sync')] + super().get_urls()

    def users_list(self, obj):
        return ', '.join(obj.users.order_by('username').values_list('username', flat=True)) or None
    users_list.short_description = 'User(s)'

    def sync_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied

        sync_google_calendar_api()
        messages.add_message(request, messages.INFO,
                             "Google Calendar is currently being sync'd. Please refresh this page in a few moments.")
        return redirect('admin:carb_googlecalendarshow_changelist')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return config.GOOGLE_CALENDAR_ENABLED


class PrerecordedAssetAdmin(admin.ModelAdmin):
    save_on_top = True
    add_fields = ('title', 'source', 'file', 'url', 'file_status', 'uploader')
    change_fields = ('title', 'file', 'duration', 'file_status', 'uploader')
    add_readonly_fields = ('uploader', 'file_status')
    change_readonly_field = add_readonly_fields + ('duration', 'file', 'task_log_line')
    search_fields = ('title',)
    list_display = ('title', 'uploader', 'duration', 'file_status')
    list_filter = (('uploader', admin.RelatedOnlyFieldListFilter),)

    class Media:
        js = ('js/asset_source.js',)

    def get_fields(self, request, obj=None):
        if obj is None:
            return self.add_fields
        elif obj.task_log_line:
            return self.change_fields + ('task_log_line',)
        else:
            return self.change_fields

    def get_readonly_fields(self, request, obj=None):
        return self.add_readonly_fields if obj is None else self.change_readonly_field

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = PrerecordedAssetCreateForm
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploader = request.user
            is_external = form.cleaned_data['source'] == 'url'
            if is_external:
                url = form.cleaned_data['url']
                obj.file_status = PrerecordedAsset.FileStatus.PENDING
                obj.title = f'Downloading {url}'
            else:
                obj.file_status = PrerecordedAsset.FileStatus.UPLOADED

        super().save_model(request, obj, form, change)

        if not change and is_external:
            messages.add_message(request, messages.WARNING,
                                 f'The audio file is being downloaded from {url}. Please refresh the page or come back '
                                 'later to check on its progress.')
            obj.queue_download(url=url, title=form.cleaned_data['title'])


class PrerecordedBroadcastAdmin(admin.ModelAdmin):
    save_on_top = True
    fields = ('asset', 'scheduled_time', 'play_status')
    readonly_fields = ('play_status',)
    autocomplete_fields = ('asset',)

    def has_change_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        messages.add_message(request, messages.WARNING,
                             f'Your broadcast of {obj.asset.title} has been queued for {obj.scheduled_time}. Come back '
                             'at that time to check whether it was successfully played.')
        obj.queue()


admin.site.unregister(Group)
admin.site.register(User, CarbUserAdmin)
admin.site.register(GoogleCalendarShow, GoogleCalendarShowAdmin)
admin.site.register(PrerecordedAsset, PrerecordedAssetAdmin)
admin.site.register(PrerecordedBroadcast, PrerecordedBroadcastAdmin)
