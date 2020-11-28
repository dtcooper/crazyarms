import datetime
import json

import pytz

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.templatetags.admin_list import _boolean_icon
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.cache import cache
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.views.generic import FormView, TemplateView

from constance import config

from carb import constants

from .forms import HarborCustomConfigForm
from .liquidsoap import upstream
from .models import PlayoutLogEntry, UpstreamServer
from .services import init_services, HarborService, SERVICES


@admin.site.register_view(route='harbor-custom-config/', title='Liquidsoap harbor source code')
class HarborCustomConfigAdminView(admin.site.AdminBaseContextMixin, PermissionRequiredMixin, FormView):
    form_class = HarborCustomConfigForm
    template_name = 'admin/services/harbor_custom_config.html'
    success_url = reverse_lazy('admin:harbor_custom_config')
    permission_required = 'common.change_liquidsoap'

    def get_initial(self):
        initial = super().get_initial()
        custom_config = cache.get(constants.CACHE_KEY_HARBOR_CONFIG_CONTEXT)
        if isinstance(custom_config, dict):
            initial.update(custom_config)
        return initial

    def form_valid(self, form):
        previous_custom_config = cache.get(constants.CACHE_KEY_HARBOR_CONFIG_CONTEXT)
        custom_config = form.cleaned_data
        if (
            previous_custom_config == custom_config
            or previous_custom_config is None and not any(custom_config.values())
        ):
            messages.warning(self.request, 'No change in Liquidsoap source code detected. Doing nothing.')

        else:
            cache.set(constants.CACHE_KEY_HARBOR_CONFIG_CONTEXT, custom_config, timeout=None)
            init_services(services='harbor', restart_specific_services='harbor')
            messages.success(self.request, 'Liquidsoap source code changed. Harbor was restarted.')

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        harbor_liq_context = {'settings': settings, 'config': config}
        harbor_liq_context.update({
            f'section{section_number}': mark_safe(f"</pre>{context['form'][f'section{section_number}']}<pre>")
            for section_number in range(1, HarborService.CUSTOM_CONFIG_NUM_SECTIONS + 1)
        })
        context['form_with_code'] = render_to_string('services/harbor.liq', context=harbor_liq_context)
        return context


@admin.site.register_view(route='service-status/', title='Service status')
class ServiceStatusAdminView(admin.site.AdminBaseContextMixin, TemplateView):
    template_name = 'admin/services/service_status.html'

    def post(self, request):
        if request.user.is_superuser:
            service, specific_service = request.POST.get('restart').split()
            init_services(service, restart_specific_services=specific_service)
        return redirect('admin:service_status')

    def get_context_data(self, **kwargs):
        services = []

        for service_name, service_cls in SERVICES.items():
            service = service_cls()
            if service.supervisor_enabled:
                status = service.supervisorctl('status', 'all')
                services.append([service_name] + list(status.split(None, 1)))

        return {**super().get_context_data(**kwargs), 'services': services}


class UpstreamServerAdmin(admin.ModelAdmin):
    list_display = ('name', '__str__', 'is_online')
    exclude = ('telnet_port',)

    def is_online(self, obj):
        connected = False
        message = 'Error: upstream failed to start (see upstream logs)'
        status = upstream(obj).status(safe=True)
        if status:
            status = json.loads(status)
            connected = status['online']
            if connected:
                uptime = timezone.now() - pytz.utc.localize(datetime.datetime.utcfromtimestamp(status['start_time']))
                uptime = uptime - datetime.timedelta(microseconds=uptime.microseconds)  # remove microseconds
                message = f'Uptime: {uptime}'
            else:
                message = f'Error: {status["error"]}'
        return format_html(f'{_boolean_icon(connected)} &mdash; {{}}', message)
    is_online.short_description = mark_safe('Currently Online?')

    def has_change_permission(self, request, obj=None):
        if obj is not None and settings.ICECAST_ENABLED and obj.name == 'local-icecast':
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and settings.ICECAST_ENABLED and obj.name == 'local-icecast':
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        saved = super().save_model(request, obj, form, change)
        init_services('upstream', restart_specific_services=obj.name)
        return saved

    def delete_model(self, request, obj):
        deleted = super().delete_model(request, obj)
        init_services('upstream', restart_services=False)
        return deleted

    def delete_queryset(self, request, queryset):
        deleted = super().delete_queryset(request, queryset)
        init_services('upstream', restart_services=False)
        return deleted


class PlayoutLogEntryAdmin(admin.ModelAdmin):
    list_display = ('created', 'event_type', 'description', 'active_source')
    search_fields = ('description', 'active_source')
    list_filter = ('event_type',)
    date_hierarchy = 'created'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj=obj)


admin.site.register(UpstreamServer, UpstreamServerAdmin)
admin.site.register(PlayoutLogEntry, PlayoutLogEntryAdmin)
