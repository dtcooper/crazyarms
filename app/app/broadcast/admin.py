from django.contrib import admin, messages
from django.utils import timezone
from django.utils.formats import date_format

from constance import config

from autodj.models import AudioAsset, RotatorAsset
from common.admin import AudioAssetAdminBase, DiskUsageChangelistAdminMixin, asset_conversion_action

from .forms import BroadcastAssetCreateForm
from .models import Broadcast, BroadcastAsset


class BroadcastInline(admin.TabularInline):
    model = Broadcast
    extra = 0
    add_fields = ("scheduled_time",)
    change_fields = ("scheduled_time", "status", "creator")
    readonly_fields = ("status", "creator")

    def get_fields(self, request, obj=None):
        return self.add_fields if obj is None else self.change_fields

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return obj is None or obj.status == obj.Status.READY


def message_broadcast_added(request, broadcast):
    scheduled_time = date_format(timezone.localtime(broadcast.scheduled_time), "SHORT_DATETIME_FORMAT")
    messages.warning(
        request,
        f"Your broadcast of {broadcast.asset.title} has been queued for {scheduled_time}. "
        "Come back at that time to check whether it was successfully played.",
    )


class BroadcastAssetAdmin(DiskUsageChangelistAdminMixin, AudioAssetAdminBase):
    non_popup_inlines = (BroadcastInline,)
    create_form = BroadcastAssetCreateForm

    def get_actions(self, request):
        actions = super().get_actions(request)
        if config.AUTODJ_ENABLED and request.user.has_perm("autodj.change_audioasset"):
            action = asset_conversion_action(BroadcastAsset, AudioAsset)
            actions["convert_to_audio_asset"] = (action, "convert_to_audio_asset", action.short_description)
            if config.AUTODJ_STOPSETS_ENABLED:
                action = asset_conversion_action(BroadcastAsset, RotatorAsset)
                actions["convert_to_rotator_asset"] = (action, "convert_to_rotator_asset", action.short_description)
        return actions

    def get_inlines(self, request, obj=None):
        return () if request.GET.get("_popup") else self.non_popup_inlines

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        # If it's the autocomplete view (from BroadcastAdmin), then filter by uploaded only
        if request.path.endswith("/autocomplete/"):
            queryset = queryset.filter(status=BroadcastAsset.Status.READY)

        return queryset, use_distinct

    def save_related(self, request, form, formsets, change):
        # TODO this is wacky and overwrites everything!
        existed_before = set(form.instance.broadcasts.all())
        super().save_related(request, form, formsets, change)
        newly_created = set(form.instance.broadcasts.all()) - existed_before
        for broadcast in newly_created:
            message_broadcast_added(request, broadcast)
            broadcast.creator = request.user
            broadcast.save()


class BroadcastAdmin(DiskUsageChangelistAdminMixin, admin.ModelAdmin):
    add_fields = ("scheduled_time", "asset")
    autocomplete_fields = ("asset",)
    date_hierarchy = "scheduled_time"
    list_display = change_fields = ("scheduled_time", "asset", "status", "creator")
    list_filter = ("status",)
    save_on_top = True

    def get_fields(self, request, obj=None):
        return self.add_fields if obj is None else self.change_fields

    def has_change_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.creator = request.user
        super().save_model(request, obj, form, change)
        message_broadcast_added(request, obj)


admin.site.register(BroadcastAsset, BroadcastAssetAdmin)
admin.site.register(Broadcast, BroadcastAdmin)
