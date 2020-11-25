import datetime
import logging
import json

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from constance import config

from autodj.models import AudioAsset
from common.models import User


logger = logging.getLogger(f'carb.{__name__}')


@method_decorator(csrf_exempt, name='dispatch')
class APIView(View):
    def dispatch(self, request):
        self.request_json = {}

        if request.headers.get('X-CARB-Secret-Key') != settings.SECRET_KEY:
            return HttpResponseForbidden()

        if request.body:
            try:
                self.request_json = json.loads(request.body)
            except json.JSONDecodeError:
                return HttpResponseBadRequest()

        response = super().dispatch(request)

        if isinstance(response, HttpResponse):
            return response
        elif isinstance(response, dict):
            return JsonResponse(response)
        elif isinstance(response, int):
            return HttpResponse(status=response)
        else:
            raise Exception('View returned an invalid response')


class DJAuthAPIView(APIView):
    def post(self, request):
        username, password = self.request_json['username'], self.request_json['password']
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
            authorized = user.currently_harbor_authorized()
            if authorized:
                kickoff_time = None
                if isinstance(authorized, datetime.datetime):
                    kickoff_time = int(authorized.timestamp())
                response.update({'authorized': True, 'full_name': user.get_full_name(),
                                 'user_id': user.id, 'kickoff_time': kickoff_time})
        return response


class NextTrackAPIView(APIView):
    def get(self, request):
        response = {'has_asset': False}
        if config.AUTODJ_ENABLED:
            audio_asset = AudioAsset.get_next_for_autodj()
            if audio_asset:
                asset_uri = f'annotate:audio_asset_id="{audio_asset.id}":file://{audio_asset.file.path}'
                response.update({'has_audio_asset': True, 'audio_asset_uri': asset_uri})
        return response
