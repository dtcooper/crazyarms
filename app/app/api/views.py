import logging
import json
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

from constance import config

from autodj.models import AudioAsset
from common.models import User


logger = logging.getLogger(f'carb.{__name__}')


def api_view(methods=('POST',)):
    def wrapped(view_func):
        @wraps(view_func)
        @csrf_exempt
        def view(request):
            if request.method in methods and request.headers.get('X-CARB-Secret-Key') == settings.SECRET_KEY:
                if request.method == 'POST':
                    data = json.loads(request.body.decode('utf-8'))
                    response = view_func(request, data)
                else:
                    response = view_func(request)

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
    response = {'authorized': False}
    user = authenticate(username=username, password=password)
    if user is None:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            logger.info(f'auth requested by {username}: denied (user does not exist)')
        else:
            logger.info(f'auth requested by {username}: denied (incorrect password)')
    else:
        if user.currently_harbor_authorized():
            response.update({'authorized': True, 'full_name': user.get_full_name(), 'user_id': user.id})
    return response


@api_view(methods=('GET',))
def next_track(request):
    response = {'has_track': False}
    if config.AUTODJ_ENABLED:
        audio_asset = AudioAsset.get_next_for_autodj()
        if audio_asset:
            response.update({'has_track': True, 'track_uri': f'file://{audio_asset.file.path}'})
    return response
