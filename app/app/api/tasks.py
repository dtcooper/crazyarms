import logging
import os
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File

from huey.contrib import djhuey

from autodj.models import AudioAsset, RotatorAsset
from broadcast.models import BroadcastAsset
from common.models import User

logger = logging.getLogger(f"carb.{__name__}")

SFTP_PATH_ASSET_CLASSES = {
    "audio-assets": AudioAsset,
    "scheduled-broadcast-assets": BroadcastAsset,
    "rotator-assets": RotatorAsset,
}
SFTP_PATH_RE = re.compile(
    fr"^{re.escape(settings.SFTP_UPLOADS_ROOT)}(?P<user_id>[^/]+)/"
    fr'(?:(?P<asset_type>{"|".join(re.escape(p) for p in SFTP_PATH_ASSET_CLASSES.keys())})/)?.+$'
)


@djhuey.task(priority=1)
def process_sftp_upload(sftp_path):
    logger.info(f"processing sftp upload: {sftp_path}")

    if os.path.isfile(sftp_path) and not os.path.islink(sftp_path):
        try:
            match = SFTP_PATH_RE.search(sftp_path)
            if match:
                match = match.groupdict()

                uploader = User.objects.get(id=match["user_id"])
                asset_cls = SFTP_PATH_ASSET_CLASSES.get(match["asset_type"]) or AudioAsset
                asset = asset_cls(uploader=uploader, file_basename=os.path.basename(sftp_path))
                asset.file.save(
                    f"uploads/{asset.file_basename}",
                    File(open(sftp_path, "rb")),
                    save=False,
                )

                type_name = asset_cls._meta.verbose_name
                try:
                    asset.clean()
                except ValidationError as e:
                    logger.warning(f"sftp upload skipped {type_name} {sftp_path}: validation error: {e}")
                else:
                    asset.save()
                    logger.info(f"sftp upload of {type_name} successfully processed: {sftp_path}")

                if isinstance(asset, AudioAsset) and uploader.default_playlist:
                    asset.playlists.add(uploader.default_playlist)
            else:
                logger.warning(f"sftp upload can't process, regular expression failed to match: {sftp_path}")

        finally:
            os.remove(sftp_path)
    else:
        logger.error(f"sftp update can't process, path doesn't exist / isn't a file: {sftp_path}")
