from django import forms
from django.contrib import admin, messages
from django.core.cache import cache
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.views.generic import FormView

from .services import init_services, HarborService


class HarborCustomConfigForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for section_number in range(1, HarborService.CUSTOM_CONFIG_NUM_SECTIONS + 1):
            self.fields[f'section{section_number}'] = forms.CharField(widget=forms.Textarea, required=False)


@admin.site.register_view(route='harbor-custom-config/', title='Liquidsoap Harbor Source Code')
class HarborCustomConfigAdminView(admin.site.AdminBaseContextMixin, FormView):
    form_class = HarborCustomConfigForm
    template_name = 'admin/services/harbor_custom_config.html'
    success_url = reverse_lazy('admin:harbor_custom_config')

    def get_initial(self):
        initial = super().get_initial()
        custom_config = cache.get('harbor-custom-config')
        if isinstance(custom_config, dict):
            initial.update(custom_config)
        return initial

    def form_valid(self, form):
        previous_custom_config = cache.get('harbor-custom-config')
        custom_config = form.cleaned_data
        if (
            previous_custom_config == custom_config
            or previous_custom_config is None and not any(custom_config.values())
        ):
            messages.warning(self.request, 'No change in Liquidsoap source code detected. Doing nothing.')

        else:
            cache.set('harbor-custom-config', custom_config, timeout=None)
            init_services(services=('harbor',), restart_services=True)
            messages.success(self.request, 'Liquidsoap source code changed. Harbor was restarted.')

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_with_code'] = render_to_string('services/harbor.liq', context={
            f'section{section_number}': mark_safe(f"</pre>{context['form'][f'section{section_number}']}<pre>")
            for section_number in range(1, HarborService.CUSTOM_CONFIG_NUM_SECTIONS + 1)
        })
        return context
