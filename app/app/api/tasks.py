import logging
import re
import os

from django.conf import settings
from django.core.files import File
from django.core.exceptions import ValidationError

from huey.contrib import djhuey

from autodj.models import AudioAsset, RotatorAsset
from broadcast.models import BroadcastAsset


logger = logging.getLogger(f'carb.{__name__}')

SFTP_PATH_ASSET_CLASSES = {
    'audio-assets': AudioAsset,
    'scheduled-broadcast-assets': BroadcastAsset,
    'rotator-assets': RotatorAsset,
}
SFTP_PATH_RE = re.compile(fr'^{re.escape(settings.SFTP_UPLOADS_ROOT)}(?P<user_id>[^/]+)/'
                          fr'(?:(?P<asset_type>{"|".join(re.escape(p) for p in SFTP_PATH_ASSET_CLASSES.keys())})/)?.+$')


@djhuey.task(priority=1)
def process_sftp_upload(sftp_path):
    logger.info(f'processing sftp upload: {sftp_path}')

    if os.path.isfile(sftp_path) and not os.path.islink(sftp_path):
        try:
            match = SFTP_PATH_RE.search(sftp_path)
            if match:
                match = match.groupdict()
                asset_cls = SFTP_PATH_ASSET_CLASSES.get(match['asset_type']) or AudioAsset
                type_name = asset_cls._meta.verbose_name
                asset = asset_cls(uploader_id=match['user_id'], file_basename=os.path.basename(sftp_path))
                asset.file.save(f'uploads/{asset.file_basename}', File(open(sftp_path, 'rb')), save=False)

                try:
                    asset.clean()
                except ValidationError as e:
                    logger.warning(f'sftp upload skipped {type_name} {sftp_path}: validation error: {e}')
                else:
                    asset.save()
                    logger.info(f'sftp upload of {type_name} successfully processed: {sftp_path}')
            else:
                logger.warning(f"sftp upload can't process, regular expression failed to match: {sftp_path}")

        finally:
            os.remove(sftp_path)
    else:
        logger.error(f"sftp update can't process, path doesn't exist / isn't a file: {sftp_path}")
