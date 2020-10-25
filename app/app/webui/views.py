import logging

from django.contrib import messages
from django.contrib.auth import login, views as auth_views
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import FormView, TemplateView

from common.models import User
from gcal.models import GoogleCalendarShowTimes

from .forms import FirstRunForm


logger = logging.getLogger(f'carb.{__name__}')


class FirstRunView(FormView):
    template_name = 'webui/form.html'
    form_class = FirstRunForm
    success_url = reverse_lazy('status')

    def dispatch(self, request, *args, **kwargs):
        # Only work if no user exists
        if User.objects.exists():
            return redirect('status')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'hide_nav': True,
            'form_description': "Welcome to Crazy Arms Radio Backend! Since no account has been created, you'll need "
                                'to create a new administrator and specify some settings below before proceeding.',
            'submit_text': 'Run Initial Setup',
            'title': 'Initial Setup',
        })
        return context


class StatusView(TemplateView):
    template_name = 'webui/status.html'

    def dispatch(self, request, *args, **kwargs):
        if not User.objects.exists():
            return redirect('first-run')
        elif not request.user.is_authenticated:
            return redirect('login')
        else:
            return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        context.update({
            'title': 'Server Status',
            'show_times_range_start': today - GoogleCalendarShowTimes.SYNC_RANGE_DAYS_MIN,
            'show_times_range_end': today + GoogleCalendarShowTimes.SYNC_RANGE_DAYS_MAX,
        })
        return context


class PasswordChangeView(auth_views.PasswordChangeView):
    success_url = reverse_lazy('status')
    template_name = 'webui/form.html'
    title = 'Change Password'

    def __init__(self):
        super().__init__(extra_context={'submit_text': 'Change Password',
                                        'form_description': 'Submit this form to change your password.'})

    def form_valid(self, form):
        messages.success(self.request, 'Your password was successfully changed')
        return super().form_valid(form)


def nginx_protected(request, module):
    if request.user.has_perm(f'common.view_{module}'):
        logger.info(f'allowing {request.user} access to module: {module}')
        response = HttpResponse()
        response['X-Accel-Redirect'] = f'/protected{request.get_full_path()}'
    else:
        response = HttpResponseForbidden()
    return response
