import logging

from django.contrib import admin, messages
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

from .models import GCalShow
from .tasks import sync_gcal_api

logger = logging.getLogger(f"carb.{__name__}")


class GCalShowAdmin(admin.ModelAdmin):
    save_on_top = True
    search_fields = ("title",)
    fields = ("title_non_blank", "users", "start", "end")
    list_display = ("title_non_blank", "start", "end")
    date_hierarchy = "start"
    list_filter = (("users", admin.RelatedOnlyFieldListFilter),)

    def get_urls(self):
        return [
            path("sync/", self.admin_site.admin_view(self.sync_view), name="gcal_gcalshow_sync")
        ] + super().get_urls()

    def title_non_blank(self, obj):
        return obj.title or "Untitled Event"

    title_non_blank.short_description = "Title"
    title_non_blank.admin_order_field = ("title",)

    def sync_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied

        cache.set(constants.CACHE_KEY_GCAL_LAST_SYNC, "currently running", timeout=None)
        sync_gcal_api()
        messages.info(request, "Google Calendar is currently being sync'd. Please refresh this page in a few moments.")
        return redirect("admin:gcal_gcalshow_changelist")

    def changelist_view(self, request, extra_context=None):
        now = timezone.now()
        extra_context = {
            "last_sync": GCalShow.get_last_sync(),
            "SYNC_RANGE_MIN_DAYS": GCalShow.SYNC_RANGE_MIN.days,
            "SYNC_RANGE_MAX_DAYS": GCalShow.SYNC_RANGE_MAX.days,
            "sync_range_start": now - GCalShow.SYNC_RANGE_MIN,
            "sync_range_end": now + GCalShow.SYNC_RANGE_MAX,
            **(extra_context or {}),
        }
        return super().changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return config.GOOGLE_CALENDAR_ENABLED


admin.site.register(GCalShow, GCalShowAdmin)
