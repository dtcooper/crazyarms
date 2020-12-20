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

from autodj.models import AudioAsset, RotatorAsset
from common.models import User

from .tasks import process_sftp_upload


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
        username_password_tries = [
            (self.request_json['username'], self.request_json['password']),
        ]

        # Allow username to be anything and password to be username:password or username-password
        for pw_split_char in (':', '-'):
            pw_split = self.request_json['password'].split(pw_split_char, 1)
            if len(pw_split) == 2:
                username_password_tries.append(pw_split)

        response = {'authorized': False}

        for username, password in username_password_tries:
            user = authenticate(username=username, password=password)
            if user is None:
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    logger.info(f'dj auth requested by {username}: denied (user does not exist)')
                else:
                    logger.info(f'dj auth requested by {username}: denied (incorrect password)')
            else:
                authorized = user.currently_harbor_authorized()
                if authorized:
                    kickoff_time = None
                    if isinstance(authorized, datetime.datetime):
                        kickoff_time = int(authorized.timestamp())
                    response.update({'authorized': True, 'full_name': user.get_full_name(),
                                    'user_id': user.id, 'kickoff_time': kickoff_time})
                break

        return response


class SFTPAuthView(APIView):
    def post(self, request):
        username, password = self.request_json['username'], self.request_json['password']
        user = authenticate(username=username, password=password)

        if user:
            permissions = []
            if config.AUTODJ_ENABLED and user.has_perm('autodj.change_audioasset'):
                permissions.append('audio-assets')
                if config.AUTODJ_STOPSETS_ENABLED:
                    permissions.append('rotator-assets')
            if user.has_perm('broadcast.change_broadcast'):
                permissions.append('scheduled-broadcast-assets')

            if permissions:
                logger.info(f'sftp auth requested by {user}: allowed (directory perms: {permissions})')
                permissions = {f'/{perm}/': ['*'] for perm in permissions}
                permissions['/'] = ['list', 'download']
                return {'status': 1, 'username': str(user.id), 'permissions': permissions, 'quota_size': 0}
            else:
                logger.info(f'sftp auth requested by {user}: denied (no permissions)')
        else:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                logger.info(f'sftp auth requested by {username}: denied (user does not exist)')
            else:
                logger.info(f'sftp auth requested by {username}: denied (incorrect password)')

        return {'status': 0}


class SFTPUploadView(APIView):
    def post(self, request):
        process_sftp_upload(self.request_json['path'])
        return 200


class NextTrackAPIView(APIView):
    def get(self, request):
        response = {'has_asset': False}
        asset = annotations = None

        if config.AUTODJ_ENABLED:
            if config.AUTODJ_STOPSETS_ENABLED:
                # Will return None if we're not currently playing through a stopset
                asset = RotatorAsset.get_next_for_autodj()
                if asset:
                    annotations = {'rotator_asset_id': str(asset.id)}

            if not asset:
                asset = AudioAsset.get_next_for_autodj()
                if asset:
                    annotations = {'audio_asset_id': str(asset.id)}

        if asset:
            annotations.update({
                # Escape " and \, as well as normalize whitespace for liquidsoap
                field: ' '.join(getattr(asset, field).split()).replace('\\', '\\\\').replace('"', '\\"')
                for field in asset.TITLE_FIELDS if getattr(asset, field)})
            annotations = ','.join(f'{key}="{value}"' for key, value in annotations.items())
            response.update({'has_asset': True, 'asset_uri': f'annotate:{annotations}:file://{asset.file.path}'})

        return response
