import datetime
from io import StringIO
import json
import logging
import shlex

from dotenv import dotenv_values
from huey.exceptions import TaskLockedException

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, ListView, TemplateView, UpdateView

from constance import config
from django_redis import get_redis_connection
from huey.contrib import djhuey

from carb import constants
from common.models import User
from services.liquidsoap import harbor
from services.models import PlayoutLogEntry
from services.services import ZoomService

from .forms import FirstRunForm, UserProfileForm, ZoomForm
from .tasks import stop_zoom_broadcast


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
        status = harbor.status(safe=True)
        return {**super().get_context_data(**kwargs),
                'title': 'Stream Status (Realtime)', 'liquidsoap_status': json.loads(status) if status else None}


class BanListView(PermissionRequiredMixin, TemplateView):
    template_name = 'webui/ban_list.html'
    permission_required = 'common.can_boot'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bans = []
        for key in cache.keys(f'{constants.CACHE_KEY_HARBOR_BAN_PREFIX}*'):
            user_id = key.removeprefix(constants.CACHE_KEY_HARBOR_BAN_PREFIX)
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
            else:
                seconds_left = cache.ttl(key)
                banned_until = timezone.localtime() + datetime.timedelta(seconds=seconds_left)
                bans.append((
                    # Reverse sort by seconds left
                    -seconds_left, user.get_full_name(), user_id, date_format(banned_until, 'DATETIME_FORMAT')))

        context['bans'] = sorted(bans)
        return {**super().get_context_data(**kwargs), 'title': 'DJ Ban List', 'bans': sorted(bans)}

    def post(self, request):
        user = get_object_or_404(User, id=request.POST.get('user_id'))
        cache.delete(f'{constants.CACHE_KEY_HARBOR_BAN_PREFIX}{user.id}')
        messages.success(request, f'The ban on {user.get_full_name()} has been lifted.')
        return redirect('banlist')


class ZoomView(LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'webui/zoom.html'
    form_class = ZoomForm
    success_url = reverse_lazy('zoom')
    success_message = ('A Zoom broadcast has been succesfully started. (If applicable, please admit the '
                       'Broadcast Bot into your room.)')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis = get_redis_connection()
        self.room_env = self.redis.get(constants.REDIS_KEY_ROOM_INFO)
        self.room_ttl = max(self.redis.ttl(constants.REDIS_KEY_ROOM_INFO), 0)

        if self.room_env:
            self.room_env = dotenv_values(stream=StringIO(self.room_env.decode('utf-8')))
        else:
            self.room_env = {}

        self.zoom_user = None
        self.service = ZoomService()

    def dispatch(self, request, *args, **kwargs):
        if not settings.ZOOM_ENABLED:
            return redirect('status')

        try:
            self.zoom_user = User.objects.get(id=self.room_env.get('MEETING_USER_ID'))
        except User.DoesNotExist:
            pass

        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def zoom_is_running_cached(self):
        return self.service.is_zoom_running()

    def post(self, request):
        try:
            with djhuey.lock_task('zoom-edit-lock'):
                if request.POST.get('stop_zoom'):
                    if request.user.is_superuser or self.zoom_user == self.request.user:
                        task_id = self.room_env.get('STOP_TASK_ID')
                        if task_id:
                            djhuey.revoke_by_id(task_id)
                        stop_zoom_broadcast.call_local()
                        messages.add_message(request, messages.INFO, 'Zoom broadcast was stopped.')
                        return redirect('zoom')
                return super().post(request)
        except TaskLockedException:
            messages.add_message(request, messages.WARNING,
                                 'Zoom action blocked. Multiple users editing configuration. Please try again.')
            return redirect('zoom')

    def get_form_kwargs(self):
        return {'user': self.request.user, 'zoom_is_running': self.zoom_is_running_cached,
                'room_env': self.room_env, **super().get_form_kwargs()}

    def form_valid(self, form):
        logger.info(f'User {self.request.user} starting Zoom show')
        meeting_id, meeting_pwd = form.cleaned_data['zoom_room']

        stop_task = stop_zoom_broadcast.schedule(delay=form.cleaned_data['ttl'])
        room_env = {'MEETING_ID': meeting_id, 'MEETING_USER_ID': str(self.request.user.id),
                    'MEETING_USERNAME': self.request.user.username, 'MEETING_PWD': meeting_pwd,
                    'STOP_TASK_ID': stop_task.id}
        # A bit jenky, but the zoom-runner.sh script evals this
        room_env_str = ''.join(f'{key}={shlex.quote(value)}\n' for key, value in room_env.items())

        harbor.zoom_metadata(json.dumps(form.cleaned_data['show_name'] or 'Live Broadcast'))

        self.redis.set(constants.REDIS_KEY_ROOM_INFO, room_env_str, ex=form.cleaned_data['ttl'])
        self.service.supervisorctl('restart', 'zoom-runner')

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        # TODO: Enforce harbor auth windows better
        current_auth = self.request.user.currently_harbor_authorized(should_log=False)
        return {
            **super().get_context_data(**kwargs),
            'authorization_time_bound': current_auth if isinstance(current_auth, datetime.datetime) else None,
            'currently_authorized': bool(current_auth),
            # convert TTL to an end time.
            'room_ttl_hours': self.room_ttl // (60 * 60) if self.room_ttl else None,
            'room_ttl_minutes': (self.room_ttl % (60 * 60)) // 60 if self.room_ttl else None,
            'submit_text': 'Start Zoom Broadcast Now',
            'title': 'Zoom Broadcasting',
            'zoom_is_running': self.zoom_is_running_cached,
            'zoom_belongs_to_current_user': self.zoom_user == self.request.user,
            'zoom_user': self.zoom_user,
        }


class UserProfileView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    form_class = UserProfileForm
    success_message = 'Your user profile was successfully updated.'
    success_url = reverse_lazy('user_profile')
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


class GCalView(LoginRequiredMixin, TemplateView):
    template_name = 'webui/gcal.html'

    def dispatch(self, *args, **kwargs):
        if not config.GOOGLE_CALENDAR_ENABLED:
            return redirect('status')
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'title': 'My Scheduled Shows'}


class PasswordChangeView(SuccessMessageMixin, auth_views.PasswordChangeView):
    success_url = reverse_lazy('status')
    template_name = 'webui/form.html'
    title = 'Change Your Password'
    success_message = 'Your password was successfully changed'

    def __init__(self):
        super().__init__(extra_context={'submit_text': 'Change Password'})


def status_boot(request):
    # TODO: refactor me to class-based
    # TODO: log when bans are MADE and LIFTED
    if request.method == 'POST':
        # Get pretty copy from front-end because why not?
        user_id, time, ban_text = request.POST.get('user_id'), request.POST.get('time'), request.POST.get('text')
        response = "You don't have permission to do that."

        if user_id is None or time is None:
            response = 'Malformed request.'

        # Has permission to do operation
        elif (time == 'permanent' and request.user.is_superuser) or request.user.has_perm('common.can_boot'):
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                response = 'User does not exist.'

            else:
                # Only superuser can perma-ban
                if time == 'permanent' and request.user.is_superuser:
                    user.harbor_auth = User.HarborAuth.NEVER
                    user.save()
                    harbor.dj_harbor__stop()
                    response = (f'{user.get_full_name()} banned permanently. To undo, go the admin site and '
                                'change their harbor authorization.')
                else:
                    try:
                        # XXX Covers case where user asks for "perm" (permanent), since ValueError is thrown
                        time = int(time)
                    except ValueError:
                        pass
                    else:
                        if time > 0:
                            cache.set(f'{constants.CACHE_KEY_HARBOR_BAN_PREFIX}{user.id}', True, timeout=time)
                            harbor.dj_harbor__stop()
                            response = (f'{user.get_full_name()} banned for {ban_text}. To undo, visit the DJ Ban List '
                                        'page')

        return HttpResponse(response, content_type='text/plain')
    else:
        return HttpResponseNotAllowed(('POST',))


def status_skip(request):
    if request.method == 'POST':
        status = harbor.status()
        if status is None:
            response = 'Invalid response from harbor'
        else:
            response = "You don't have permission to do that."
            skippable_sources = status['skippable_sources']
            if request.user.has_perm('broadcast.change_broadcast'):
                source_id = request.POST.get('id')
                if source_id is None:
                    response = 'Malformed request.'
                elif source_id not in skippable_sources:
                    response = f'{source_id} not a skippable source.'
                else:
                    source_name = request.POST.get('name', 'Unknown')
                    getattr(harbor, f'{source_id}.skip')()
                    response = f'You successfully skipped the current track on {source_name}.'
        return HttpResponse(response, content_type='text/plain')
    else:
        return HttpResponseNotAllowed(('POST',))


class PlayoutLogView(LoginRequiredMixin, ListView):
    MAX_ENTRIES = 250
    template_name = 'webui/playout_log.html'
    queryset = PlayoutLogEntry.objects.order_by('-created')[:MAX_ENTRIES]

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs),
                'title': 'Playout Log', 'MAX_ENTRIES': self.MAX_ENTRIES}


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
