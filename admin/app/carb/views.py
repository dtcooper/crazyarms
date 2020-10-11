import json
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import urlencode
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, TemplateView

from .forms import FirstRunForm


class StatusView(TemplateView):
    template_name = 'status.html'

    def dispatch(self, request, *args, **kwargs):
        if not User.objects.exists():
            return redirect('first-run')
        elif not request.user.is_authenticated:
            return redirect(f'{reverse("admin:login")}?{urlencode({"next": reverse("status")})}')
        else:
            return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'title': 'Server Status'})
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
    return {'allowed': user is not None}
