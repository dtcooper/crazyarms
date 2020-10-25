import json
import logging
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, views as auth_views
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, TemplateView


from .forms import FirstRunForm
from .models import GoogleCalendarShowTimes, User


logger = logging.getLogger(__name__)


class StatusView(TemplateView):
    template_name = 'status.html'

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
            'show_times': self.request.user.get_show_times(),
        })
        return context


class FirstRunView(FormView):
    template_name = 'first_run.html'
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
        context.update({'hidenav': True})
        return context


def harbor_api_view(methods=['POST']):
    def wrapped(view_func):
        @wraps(view_func)
        @csrf_exempt
        def view(request):
            if request.method in methods and request.headers.get('X-CARB-Secret-Key') == settings.SECRET_KEY:
                data = json.loads(request.body.decode('utf-8')) if request.method == 'POST' else None
                response = view_func(request, data)
                if isinstance(response, dict):
                    return JsonResponse(response)
                else:
                    return response
            else:
                return HttpResponseForbidden()
        return view

    if callable(methods):
        view_func, methods = methods, ['POST']
        return wrapped(view_func)
    else:
        return wrapped


@harbor_api_view
def harbor_auth(request, data):
    user = authenticate(username=data['username'], password=data['password'])
    return {'authorized': user is not None and user.currently_harbor_authorized()}


def nginx_protected(request, module):
    if not request.user.is_authenticated:
        return HttpResponseForbidden()

    response = HttpResponse()
    response['X-Accel-Redirect'] = f'/protected{request.get_full_path()}'
    return response


class PasswordChangeView(auth_views.PasswordChangeView):
    success_url = reverse_lazy('status')
    template_name = 'auth_form.html'
    title = 'Change Password'

    def __init__(self):
        super().__init__(extra_context={'submit_text': 'Change Password'})

    def form_valid(self, form):
        messages.success(self.request, 'Your password was successfully changed')
        return super().form_valid(form)
