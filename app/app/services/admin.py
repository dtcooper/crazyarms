from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.cache import cache
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.views.generic import FormView

from carb import constants

from .forms import HarborCustomConfigForm, UpstreamServerForm
from .models import UpstreamServer
from .services import init_services, HarborService


@admin.site.register_view(route='harbor-custom-config/', app_label='services', title='Liquidsoap Harbor Source Code')
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
            init_services(services=('harbor',), restart_services=True)
            messages.success(self.request, 'Liquidsoap source code changed. Harbor was restarted.')

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        harbor_liq_context = {'settings': settings}
        harbor_liq_context.update({
            f'section{section_number}': mark_safe(f"</pre>{context['form'][f'section{section_number}']}<pre>")
            for section_number in range(1, HarborService.CUSTOM_CONFIG_NUM_SECTIONS + 1)
        })
        context['form_with_code'] = render_to_string('services/harbor.liq', context=harbor_liq_context)
        return context


class UpstreamServerAdmin(admin.ModelAdmin):
    form = UpstreamServerForm

    class Media:
        js = ('admin/js/server_type.js',)


admin.site.register(UpstreamServer, UpstreamServerAdmin)
