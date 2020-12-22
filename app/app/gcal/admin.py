import logging

from django.contrib import admin
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import path
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.utils.html import escape, format_html_join
from django.utils.safestring import mark_safe

from constance import config

from carb import constants

from .models import GoogleCalendarShowTimes
from .tasks import sync_google_calendar_api


logger = logging.getLogger(f'carb.{__name__}')


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
                        date_format(timezone.localtime(lower), 'SHORT_DATETIME_FORMAT'),
                        date_format(timezone.localtime(upper), 'SHORT_DATETIME_FORMAT'),
                     )
                     for lower, upper in obj.show_times),
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
                name='gcal_googlecalendarshowtimes_sync')] + super().get_urls()

    def users_list(self, obj):
        return ', '.join(obj.users.order_by('username').values_list('username', flat=True)) or None
    users_list.short_description = 'User(s)'

    def sync_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied

        cache.set(constants.CACHE_KEY_GCAL_LAST_SYNC, 'currently running', timeout=None)
        sync_google_calendar_api()
        messages.add_message(request, messages.INFO,
                             "Google Calendar is currently being sync'd. Please refresh this page in a few moments.")
        return redirect('admin:gcal_googlecalendarshowtimes_changelist')

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


admin.site.register(GoogleCalendarShowTimes, GoogleCalendarShowTimesAdmin)
