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
from services.models import TrackLogEntry


logger = logging.getLogger(f'carb.{__name__}')


def api_view(method='POST'):
    def wrapped(view_func):
        @wraps(view_func)
        @csrf_exempt
        def view(request):
            if request.method == method and request.headers.get('X-CARB-Secret-Key') == settings.SECRET_KEY:
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

    if callable(method):
        view_func, method = method, 'POST'
        return wrapped(view_func)
    else:
        return wrapped


@api_view
def dj_auth(request, data):
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


@api_view(method='GET')
def next_track(request):
    response = {'has_asset': False}
    if config.AUTODJ_ENABLED:
        audio_asset = AudioAsset.get_next_for_autodj()
        if audio_asset:
            asset_uri = f'annotate:asset_id="{audio_asset.id}":file://{audio_asset.file.path}'
            response.update({'has_asset': True, 'asset_uri': asset_uri})
    return response


@api_view
def log_track(request, data):
    name = audio_asset = None
    audio_asset_id = data.get('asset_id')

    if audio_asset_id:
        try:
            audio_asset = AudioAsset.objects.get(id=audio_asset_id)
        except AudioAsset.DoesNotExist:
            pass
        else:
            name = str(audio_asset)

    if not name:
        name = ' - '.join(filter(None, (data.get(k) for k in ('artist', 'album', 'title')))) or AudioAsset.UNNAMED_TRACK

    TrackLogEntry.objects.create(name=name, active_source=data['active_source'], audio_asset=audio_asset)
    return {'status': 'ok'}
