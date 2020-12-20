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
from broadcast.models import BroadcastAsset
from common.models import User

from .tasks import process_sftp_upload, SFTP_PATH_ASSET_CLASSES


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
    RESTRICTED_DIR_PERMS = ('list', 'download')
    # Don't allow creation of symlinks @ https://github.com/drakkan/sftpgo/blob/master/dataprovider/user.go
    ALLOWED_DIR_PERMS = ('list', 'download', 'upload', 'overwrite', 'delete', 'rename',
                         'create_dirs', 'chmod', 'chown', 'chtimes')
    SFTP_ASSET_CLASS_PATHS = {v: k for k, v in SFTP_PATH_ASSET_CLASSES.items()}

    def post(self, request):
        username, password, key = self.request_json['username'], self.request_json['password'], self.request_json['key']
        non_logged_in_user = None
        user = authenticate(username=username, password=password)

        if user:
            auth_type = 'password'
        else:
            try:
                non_logged_in_user = User.objects.get(username=username)
            except User.DoesNotExist:
                pass
            else:
                key_split = key.strip().split()

                for authorized_key in non_logged_in_user.authorized_keys.strip().splitlines():
                    authorized_key_split = authorized_key.strip().split()
                    split_len = min(len(key_split), len(authorized_key_split))
                    if split_len >= 2 and key_split[:split_len] == authorized_key_split[:split_len]:
                        user = non_logged_in_user
                        auth_type = 'ssh key'
                        break

        if user:
            dir_perms = []
            permissions = {'/': self.RESTRICTED_DIR_PERMS}
            if config.AUTODJ_ENABLED and user.has_perm('autodj.change_audioasset'):
                dir_perms.append(self.SFTP_ASSET_CLASS_PATHS[AudioAsset])
                permissions = {'/': self.ALLOWED_DIR_PERMS}
                if config.AUTODJ_STOPSETS_ENABLED:
                    dir_perms.append(self.SFTP_ASSET_CLASS_PATHS[RotatorAsset])
            if user.has_perm('broadcast.change_broadcast'):
                dir_perms.append(self.SFTP_ASSET_CLASS_PATHS[BroadcastAsset])

            if dir_perms:
                logger.info(f'sftp auth requested by {user}: {auth_type} accepted (directory perms: {dir_perms})')
                permissions.update({f'/{perm}/': self.ALLOWED_DIR_PERMS for perm in dir_perms})
                return {'status': 1, 'username': str(user.id), 'permissions': permissions, 'quota_size': 0}
            else:
                logger.info(f'sftp auth requested by {user}: denied ({auth_type} allowed but no permissions)')
        elif non_logged_in_user:
            logger.info(f'sftp auth requested by {username}: denied (invalid credentials)')
        else:
            logger.info(f'sftp auth requested by {username}: denied (user does not exist)')

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
