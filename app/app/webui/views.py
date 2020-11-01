import logging
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import format_html
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, TemplateView, UpdateView

from django_redis import get_redis_connection
from huey.contrib.djhuey import lock_task
from huey.exceptions import TaskLockedException

from common.models import User
from gcal.models import GoogleCalendarShowTimes
from services.liquidsoap import harbor
from services.services import ZoomService

from .forms import FirstRunForm, UserProfileForm


logger = logging.getLogger(f'carb.{__name__}')


class FirstRunView(SuccessMessageMixin, FormView):
    template_name = 'webui/form.html'
    form_class = FirstRunForm
    success_url = reverse_lazy('status')
    success_message = ('Crazy Arms Radio Backend has successfully been setup! You can change any of '
                       'the settings that you chose in the admin section.')

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
            'station_name_override': 'Crazy Arms Radio Backend',
            'hide_nav': True,
            'form_description': "Welcome to Crazy Arms Radio Backend! Since no account has been created, you'll need "
                                'to create a new administrator and specify some settings below before proceeding.',
            'submit_text': 'Run Initial Setup',
            'title': 'Initial Setup',
        })
        return context


class StatusView(LoginRequiredMixin, TemplateView):
    template_name = 'webui/status.html'

    def dispatch(self, request, *args, **kwargs):
        if not User.objects.exists():
            return redirect('first_run')
        else:
            return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        today = timezone.now().date()
        user = self.request.user
        now_pretty = date_format(timezone.localtime(), "SHORT_DATETIME_FORMAT")

        redis = get_redis_connection()
        liquidsoap_status = redis.get('liquidsoap:status')
        return {
            **super().get_context_data(**kwargs),
            'title': 'Server Status',
            'show_times_range_start': today - GoogleCalendarShowTimes.SYNC_RANGE_DAYS_MIN,
            'show_times_range_end': today + GoogleCalendarShowTimes.SYNC_RANGE_DAYS_MAX,
            'liquidsoap_status': json.loads(liquidsoap_status) if liquidsoap_status else False,
            'user_info': (
                ('Username', user.username),
                ('Contact', f'"{user.get_full_name()}" <{user.email}>'),
                ('Harbor Authorization', user.harbor_auth_pretty()),
                ('Timezone', f'{user.get_timezone_display()} (currently {now_pretty})'),
            ),
            'server_info': (
                ('Liquidsoap Version', harbor.version),
            ),
        }


class ZoomView(LoginRequiredMixin, TemplateView):
    template_name = 'webui/zoom.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = ZoomService()

    def dispatch(self, request, *args, **kwargs):
        if not settings.ZOOM_ENABLED:
            return redirect('status')
        else:
            return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        try:
            with lock_task('zoom-view-lock'):
                if self.service.is_zoom_running():
                    self.service.supervisorctl('stop', 'zoom')
                else:
                    self.service.supervisorctl('start', 'zoom')
        except TaskLockedException:
            messages.warning(request, 'Another user using at this time. Please try again later.')

        return self.get(request)

    def get_context_data(self, **kwargs):
        # TODO do this a little more reliably
        return {
            **super().get_context_data(**kwargs),
            'title': 'Zoom Broadcasting',
            'is_running': self.service.is_zoom_running(),
        }


class UserProfileView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    form_class = UserProfileForm
    success_message = 'Your user profile was successfully updated.'
    success_url = reverse_lazy('status')
    template_name = 'webui/form.html'

    def get_object(self, **kwargs):
        return self.request.user

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'title': 'Edit Your User Profile',
            'submit_text': 'Update User Profile',
            'form_description': format_html(
                'Update your user profile below. <a href="{}">Click here</a> to change your password.',
                reverse('password_change'))
        }


class PasswordChangeView(SuccessMessageMixin, auth_views.PasswordChangeView):
    success_url = reverse_lazy('status')
    template_name = 'webui/form.html'
    title = 'Change Your Password'
    success_message = 'Your password was successfully changed'

    def __init__(self):
        super().__init__(extra_context={'submit_text': 'Change Password'})


@csrf_exempt
def nginx_protected(request, module):
    if module == 'sse':
        has_perm = request.user.is_authenticated
    else:
        has_perm = request.user.has_perm(f'common.view_{module}')

    if has_perm:
        logger.info(f'allowing {request.user} access to module: {module}')
        response = HttpResponse()
        response['X-Accel-Redirect'] = f'/protected{request.get_full_path()}'
    else:
        response = HttpResponseForbidden()
    return response
