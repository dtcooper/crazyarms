from django.contrib import admin
from django.contrib import messages
from django.utils import timezone
from django.utils.formats import date_format


from common.admin import AudioAssetAdminBase

from .forms import BroadcastAssetCreateForm
from .models import BroadcastAsset, Broadcast


class BroadcastInline(admin.TabularInline):
    model = Broadcast
    extra = 1
    verbose_name_plural = 'scheduled broadcast'
    add_fields = ('scheduled_time',)
    change_fields = ('scheduled_time', 'status')
    readonly_fields = ('status',)

    def get_fields(self, request, obj=None):
        return self.add_fields if obj is None else self.change_fields

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return obj is None or obj.status == obj.Status.READY


def message_broadcast_added(request, broadcast):
    scheduled_time = date_format(timezone.localtime(broadcast.scheduled_time), 'SHORT_DATETIME_FORMAT')
    messages.warning(request, f'Your broadcast of {broadcast.asset.title} has been queued for {scheduled_time}. '
                              'Come back at that time to check whether it was successfully played.')


class BroadcastAssetAdmin(AudioAssetAdminBase):
    non_popup_inlines = (BroadcastInline,)
    create_form = BroadcastAssetCreateForm

    def get_inlines(self, request, obj=None):
        return () if request.GET.get('_popup') else self.non_popup_inlines

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        # If it's the autocomplete view (from BroadcastAdmin), then filter by uploaded only
        if request.path.endswith('/autocomplete/'):
            queryset = queryset.filter(status=BroadcastAsset.Status.READY)

        return queryset, use_distinct

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        for broadcast in form.instance.broadcasts.all():
            message_broadcast_added(request, broadcast)


class BroadcastAdmin(admin.ModelAdmin):
    save_on_top = True
    add_fields = ('scheduled_time', 'asset')
    change_fields = ('scheduled_time', 'asset', 'status')
    autocomplete_fields = ('asset',)
    list_display = ('scheduled_time', 'asset', 'status')
    list_filter = ('status',)
    date_hierarchy = 'scheduled_time'

    def get_fields(self, request, obj=None):
        return self.add_fields if obj is None else self.change_fields

    def has_change_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        message_broadcast_added(request, obj)


admin.site.register(BroadcastAsset, BroadcastAssetAdmin)
admin.site.register(Broadcast, BroadcastAdmin)
