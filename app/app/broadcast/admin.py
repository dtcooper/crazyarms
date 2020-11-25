from django.contrib import admin
from django.contrib import messages

from common.admin import AssetAdminBase

from .forms import BroadcastAssetCreateForm
from .models import BroadcastAsset, Broadcast


class BroadcastAssetAdmin(AssetAdminBase):
    create_form = BroadcastAssetCreateForm

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        # If it's the autocomplete view (from BroadcastAdmin), then filter by uploaded only
        if request.path.endswith('/autocomplete/'):
            queryset = queryset.filter(status=BroadcastAsset.Status.UPLOADED)

        return queryset, use_distinct


class BroadcastAdmin(admin.ModelAdmin):
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


admin.site.register(BroadcastAsset, BroadcastAssetAdmin)
admin.site.register(Broadcast, BroadcastAdmin)
