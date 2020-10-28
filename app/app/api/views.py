import logging
import json
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

from common.models import User


logger = logging.getLogger(f'carb.{__name__}')


def api_view(methods=['POST']):
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


@api_view
def auth(request, data):
    username, password = data['username'], data['password']
    user = authenticate(username=username, password=password)
    if user is None:
        authorized = False
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            logger.info(f'auth requested by {username}: denied (user does not exist)')
        else:
            logger.info(f'auth requested by {username}: denied (incorrect password)')
    else:
        authorized = user.currently_harbor_authorized()
    return {'authorized': authorized}
