import datetime
import logging

from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.shortcuts import redirect
from django.urls import path
from django.utils import timezone
from django.utils.text import normalize_newlines

from constance import admin as constance_admin, config

from .forms import PrerecordedAssetCreateForm
from .models import GoogleCalendarShow, PrerecordedAsset, PrerecordedBroadcast, User
from .services import init_services
from .tasks import sync_google_calendar_api


logger = logging.getLogger(__name__)


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

        cache.set('gcal:last-sync', 'currently running', timeout=None)
        sync_google_calendar_api()
        messages.add_message(request, messages.INFO,
                             "Google Calendar is currently being sync'd. Please refresh this page in a few moments.")
        return redirect('admin:carb_googlecalendarshow_changelist')

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {'last_sync': GoogleCalendarShow.get_last_sync()})

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
    add_fields = ('title', 'source', 'file', 'url', 'status', 'uploader')
    change_fields = ('title', 'file', 'duration', 'status', 'uploader', 'task_log_line')
    add_readonly_fields = ('uploader', 'status')
    change_readonly_field = add_readonly_fields + ('duration', 'file', 'task_log_line')
    search_fields = ('title',)
    list_display = ('title', 'uploader', 'duration', 'status')
    list_filter = (('uploader', admin.RelatedOnlyFieldListFilter),)

    class Media:
        js = ('js/asset_source.js',)

    def get_fields(self, request, obj=None):
        if obj is None:
            return self.add_fields
        else:
            fields = list(self.change_fields)
            # Remove these if they're falsey
            for field in ('file', 'duration', 'task_log_line'):
                if not getattr(obj, field):
                    fields.remove(field)
            return fields

    def get_readonly_fields(self, request, obj=None):
        return self.add_readonly_fields if obj is None else self.change_readonly_field

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = PrerecordedAssetCreateForm
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        download_url = None
        if not change:
            obj.uploader = request.user
            if form.cleaned_data['source'] == 'url':
                download_url = form.cleaned_data['url']
                obj.title = f'Downloading {download_url}'

        super().save_model(request, obj, form, change)

        if download_url:
            messages.add_message(request, messages.WARNING,
                                 f'The audio file is being downloaded from {download_url}. Please refresh the page or '
                                 'come back later to check on its progress.')
            obj.queue_download(url=download_url, set_title=form.cleaned_data['title'])


class PrerecordedBroadcastAdmin(admin.ModelAdmin):
    save_on_top = True
    fields = ('asset', 'scheduled_time', 'status')
    readonly_fields = ('status',)
    autocomplete_fields = ('asset',)

    def has_change_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        messages.add_message(request, messages.WARNING,
                             f'Your broadcast of {obj.asset.title} has been queued for {obj.scheduled_time}. Come back '
                             'at that time to check whether it was successfully played.')
        obj.queue()


class CarbConstanceForm(constance_admin.ConstanceForm):
    def save(self):
        # Modified from parent class in order to hook changes in groups (instead of one signal for each)
        changes = []

        for file_field in self.files:
            file = self.cleaned_data[file_field]
            self.cleaned_data[file_field] = default_storage.save(file.name, file)

        for name in settings.CONSTANCE_CONFIG:
            current = getattr(config, name)
            new = self.cleaned_data[name]

            if isinstance(new, str):
                new = normalize_newlines(new)

            if settings.USE_TZ and isinstance(current, datetime.datetime) and not timezone.is_aware(current):
                current = timezone.make_aware(current)

            if current != new:
                setattr(config, name, new)
                changes.append(name)

        if changes:
            self.process_config_changes(changes)

    def process_config_changes(self, changes):
        if any(change.startswith('GOOGLE_CALENDAR') for change in changes):
            sync_google_calendar_api()
        if any(change.startswith('ICECAST') for change in changes):
            init_services(services=('upstream', 'icecast',), restart_services=True)


class CarbConstanceAdmin(constance_admin.ConstanceAdmin):
    change_list_form = CarbConstanceForm


admin.site.unregister(Group)
admin.site.unregister([constance_admin.Config])
admin.site.register([constance_admin.Config], CarbConstanceAdmin)
admin.site.register(User, CarbUserAdmin)
admin.site.register(GoogleCalendarShow, GoogleCalendarShowAdmin)
admin.site.register(PrerecordedAsset, PrerecordedAssetAdmin)
admin.site.register(PrerecordedBroadcast, PrerecordedBroadcastAdmin)
