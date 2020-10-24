import logging

from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import path
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.utils.html import escape, format_html_join
from django.utils.safestring import mark_safe

from constance import admin as constance_admin, config

from .forms import ConstanceForm, PrerecordedAssetCreateForm
from .models import GoogleCalendarShowTimes, PrerecordedAsset, PrerecordedBroadcast, User
from .tasks import sync_google_calendar_api


logger = logging.getLogger(__name__)


class HarborAuthListFilter(admin.SimpleListFilter):
    title = User._meta.get_field('harbor_auth').verbose_name
    parameter_name = 'harbor_auth'

    def lookups(self, request, model_admin):
        if config.GOOGLE_CALENDAR_ENABLED:
            return User.HarborAuth.choices
        else:
            return list(filter(lambda c: c[0] != User.HarborAuth.GOOGLE_CALENDAR, User.HarborAuth.choices))

    def queryset(self, request, queryset):
        if self.value():
            if not config.GOOGLE_CALENDAR_ENABLED and self.value() == User.HarborAuth.ALWAYS:
                return queryset.filter(harbor_auth__in=(User.HarborAuth.ALWAYS, User.HarborAuth.GOOGLE_CALENDAR))
            else:
                return queryset.filter(harbor_auth=self.value())


class CarbUserAdmin(UserAdmin):
    save_on_top = True
    add_form_template = None
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Personal info', {'fields': (('first_name', 'last_name'),)}),
        ('Permissions', {'fields': ('harbor_auth', ('google_calender_entry_grace_minutes',
                                    'google_calender_exit_grace_minutes'), 'is_active', 'is_staff', 'is_superuser',
                                    'groups')}),
        ('Important dates', {'fields': ('last_login', 'date_joined', 'modified')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'harbor_auth_list', 'is_staff')
    list_filter = (HarborAuthListFilter, 'is_superuser', 'is_active', 'groups')
    readonly_fields = ('last_login', 'date_joined', 'modified')
    add_fieldsets = (
        (None, {'fields': ('username', 'email', 'password1', 'password2')}),
        ('Personal info', {'fields': (('first_name', 'last_name'),)}),
        ('Permissions', {'fields': ('harbor_auth', ('google_calender_entry_grace_minutes',
                                    'google_calender_exit_grace_minutes'), 'is_staff', 'is_superuser', 'groups')}),
    )

    class Media:
        js = ('js/harbor_auth_google_calendar.js',)

    def harbor_auth_list(self, obj):
        if obj.harbor_auth == User.HarborAuth.GOOGLE_CALENDAR:
            if config.GOOGLE_CALENDAR_ENABLED:
                return (f'{obj.get_harbor_auth_display()} ({obj.google_calender_entry_grace_minutes} mins early entry, '
                        f'{obj.google_calender_exit_grace_minutes} mins late exit)')
            else:
                return User.HarborAuth.ALWAYS.label
        else:
            return obj.get_harbor_auth_display()
    harbor_auth_list.short_description = User._meta.get_field('harbor_auth').verbose_name
    harbor_auth_list.admin_order_field = 'harbor_auth'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not config.GOOGLE_CALENDAR_ENABLED:
            harbor_auth_field = form.base_fields['harbor_auth']
            harbor_auth_field.choices = list(filter(lambda c: c[0] != User.HarborAuth.GOOGLE_CALENDAR,
                                                    harbor_auth_field.choices))
        return form


class GoogleCalendarShowTimesAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('user', 'num_shows')
    fields = ('user', 'shows')
    readonly_fields = ('shows',)
    list_filter = (('user', admin.RelatedOnlyFieldListFilter),)

    class ShowsField:
        def __init__(self, include_individual_shows=True):
            self.include_individual_shows = include_individual_shows

        def __call__(self, obj):
            num_shows = len(obj.show_times)
            s = f'{num_shows} show{"s" if num_shows != 1 else ""}'
            if self.include_individual_shows and obj.show_times:
                s = mark_safe(escape(s))
                s += mark_safe('\n<ol>\n')
                s += format_html_join(
                    '\n',
                    '<li>{} - {}</li>',
                    ((
                        date_format(timezone.localtime(t.lower), 'SHORT_DATETIME_FORMAT'),
                        date_format(timezone.localtime(t.upper), 'SHORT_DATETIME_FORMAT'),
                     )
                     for t in obj.show_times),
                )
                s += mark_safe('\n</ol>')
            return s

        @cached_property
        def short_description(self):
            now = timezone.now()
            show_times_range_start = date_format(now - GoogleCalendarShowTimes.SYNC_RANGE_DAYS_MIN, 'SHORT_DATE_FORMAT')
            show_times_range_end = date_format(now + GoogleCalendarShowTimes.SYNC_RANGE_DAYS_MAX, 'SHORT_DATE_FORMAT')
            return f'show(s) from {show_times_range_start} to {show_times_range_end}'

    @cached_property
    def shows(self):
        return self.ShowsField()

    @cached_property
    def num_shows(self):
        return self.ShowsField(include_individual_shows=False)

    def get_urls(self):
        return [path('sync/', self.admin_site.admin_view(self.sync_view),
                name='carb_googlecalendarshowtimes_sync')] + super().get_urls()

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
        return redirect('admin:carb_googlecalendarshowtimes_changelist')

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {'last_sync': GoogleCalendarShowTimes.get_last_sync()})

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


class ConstanceAdmin(constance_admin.ConstanceAdmin):
    change_list_form = ConstanceForm


admin.site.unregister(Group)
admin.site.unregister([constance_admin.Config])
admin.site.register([constance_admin.Config], ConstanceAdmin)
admin.site.register(User, CarbUserAdmin)
admin.site.register(GoogleCalendarShowTimes, GoogleCalendarShowTimesAdmin)
admin.site.register(PrerecordedAsset, PrerecordedAssetAdmin)
admin.site.register(PrerecordedBroadcast, PrerecordedBroadcastAdmin)
