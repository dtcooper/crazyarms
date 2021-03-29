import json
import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from constance import config

from autodj.models import AudioAsset, RotatorAsset
from common.models import User

from .tasks import SFTP_PATH_ASSET_CLASSES, process_sftp_upload

logger = logging.getLogger(f"crazyarms.{__name__}")


@method_decorator(csrf_exempt, name="dispatch")
class APIView(View):
    def dispatch(self, request):
        self.request_json = {}

        if request.headers.get("X-Crazyarms-Secret-Key") != settings.SECRET_KEY:
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
            raise Exception("View returned an invalid response")


class DJAuthAPIView(APIView):
    def post(self, request):
        response = {"authorized": False}
        user = non_logged_in_user = None

        if self.request_json["username"] == "!":
            try:
                user = User.objects.get(stream_key=self.request_json["password"].strip())
            except User.DoesNotExist:
                logger.info("dj auth requested by stream key: denied")
        else:
            username_password_tries = [
                (self.request_json["username"], self.request_json["password"]),
            ]

            # Allow username to be anything and password to be username:password or username-password
            for pw_split_char in (":", "-"):
                pw_split = self.request_json["password"].split(pw_split_char, 1)
                if len(pw_split) == 2:
                    username_password_tries.append(pw_split)

            for username, password in username_password_tries:
                user = authenticate(username=username, password=password)
                if user:
                    break
                else:
                    try:
                        case_insensitive_username_field = "{}__iexact".format(User.USERNAME_FIELD)
                        non_logged_in_user = User.objects.get(**{case_insensitive_username_field: username})
                    except User.DoesNotExist:
                        pass

        if user:
            # Log messages handled by currently_harbor_authorized()
            current_auth = user.currently_harbor_authorized()
            if current_auth.authorized:
                kickoff_time = None
                if current_auth.end:
                    kickoff_time = int(current_auth.end.timestamp())

                response.update(
                    {
                        "authorized": True,
                        "full_name": user.get_full_name(short=True),
                        "kickoff_time": kickoff_time,
                        "title": current_auth.title,
                        "user_id": user.id,
                        "username": user.username,
                    }
                )
        elif non_logged_in_user:
            logger.info(f"dj auth requested by {non_logged_in_user}: denied (incorrect password / inactive account)")
        else:
            logger.info(f"dj auth requested by {username}: denied (user does not exist)")

        return response


@method_decorator(csrf_exempt, name="dispatch")
class ValidateStreamKeyView(View):
    def post(self, request, *args, **kwargs):
        # nginx-rtmp expects a 2xx code to allow and a 4xx to deny
        stream_key = self.request.POST.get("name")
        if stream_key:
            try:
                user = User.objects.get(stream_key=stream_key)
            except User.DoesNotExist:
                pass
            else:
                if user.currently_harbor_authorized().authorized:
                    logger.info(f"rtmp auth by {user} auth: allowed")
                    return HttpResponse(status=200)

        logger.info("rtmp auth: denied")
        return HttpResponse(status=404)


class SFTPAuthView(APIView):
    RESTRICTED_DIR_PERMS = ("list", "download")
    # Don't allow creation of symlinks @ https://github.com/drakkan/sftpgo/blob/master/dataprovider/user.go
    ALLOWED_DIR_PERMS = (
        "list",
        "download",
        "upload",
        "overwrite",
        "delete",
        "rename",
        "create_dirs",
        "chmod",
        "chown",
        "chtimes",
    )
    SFTP_ASSET_CLASS_PATHS = {v: k for k, v in SFTP_PATH_ASSET_CLASSES.items()}

    def post(self, request):
        username, password, key = (
            self.request_json["username"],
            self.request_json["password"],
            self.request_json["key"],
        )
        non_logged_in_user = None
        user = authenticate(username=username, password=password)

        if user:
            auth_type = "password"
        else:
            try:
                case_insensitive_username_field = "{}__iexact".format(User.USERNAME_FIELD)
                non_logged_in_user = User.objects.get(**{case_insensitive_username_field: username})
            except User.DoesNotExist:
                pass
            else:
                if non_logged_in_user.is_active:
                    key_split = key.strip().split()

                    for authorized_key in non_logged_in_user.authorized_keys.strip().splitlines():
                        authorized_key_split = authorized_key.strip().split()
                        split_len = min(len(key_split), len(authorized_key_split))
                        if split_len >= 2 and key_split[:split_len] == authorized_key_split[:split_len]:
                            user = non_logged_in_user
                            auth_type = "ssh key"
                            break

        if user:
            allowed = user.get_sftp_allowable_models()

            if allowed:
                permissions = {"/": self.RESTRICTED_DIR_PERMS}
                if AudioAsset in allowed:
                    permissions = {"/": self.ALLOWED_DIR_PERMS}
                else:
                    permissions = {"/": self.RESTRICTED_DIR_PERMS}

                permissions.update({f"/{self.SFTP_ASSET_CLASS_PATHS[m]}/": self.ALLOWED_DIR_PERMS for m in allowed})
                logger.info(
                    f"sftp auth requested by {user}: {auth_type} accepted (uploads allowed: "
                    f"{[m._meta.verbose_name for m in allowed]})"
                )
                return {
                    "status": 1,
                    "username": str(user.id),
                    "permissions": permissions,
                    "quota_size": 0,
                }
            else:
                logger.info(f"sftp auth requested by {user}: denied ({auth_type} allowed but no permissions)")
        elif non_logged_in_user:
            logger.info(f"sftp auth requested by {non_logged_in_user}: denied (invalid credentials / inactive account)")
        else:
            logger.info(f"sftp auth requested by {username}: denied (user does not exist)")

        return {"status": 0}


class SFTPUploadView(APIView):
    def post(self, request):
        process_sftp_upload(self.request_json["path"])
        return 200


class NextTrackAPIView(APIView):
    def get(self, request):
        asset = None

        if config.AUTODJ_ENABLED:
            if config.AUTODJ_STOPSETS_ENABLED:
                # Will return None if we're not currently playing through a stopset
                asset = RotatorAsset.get_next_for_autodj()

            if not asset:
                asset = AudioAsset.get_next_for_autodj()

        if asset:
            return {"has_asset": True, "asset_uri": asset.liquidsoap_uri()}
        else:
            return {"has_asset": False}
