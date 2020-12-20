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

SFTP_PATH_RE = re.compile(fr'^{re.escape(settings.SFTP_UPLOADS_ROOT)}(?P<user_id>[^/]+)/(?P<asset_type>[^/]+)/.+$')
SFTP_PATH_ASSET_CLASSES = {
    'audio-assets': AudioAsset,
    'scheduled-broadcast-assets': BroadcastAsset,
    'rotator-assets': RotatorAsset,
}


@djhuey.task()
def process_sftp_upload(sftp_path):
    logger.info(f'processing sftp upload: {sftp_path}')

    if os.path.isfile(sftp_path) and not os.path.islink(sftp_path):
        try:
            match = SFTP_PATH_RE.search(sftp_path).groupdict()
            asset_cls = SFTP_PATH_ASSET_CLASSES[match['asset_type']]
            asset = asset_cls(uploader_id=match['user_id'], file_basename=os.path.basename(sftp_path))
            asset.file.save(f'uploads/{asset.file_basename}', File(open(sftp_path, 'rb')), save=False)

            try:
                asset.clean()
            except ValidationError as e:
                logger.warning(f'skipping sftp upload of {sftp_path}: validation error: {e.message}')
            else:
                asset.save()
                logger.info(f'sftp upload successfully processed: {sftp_path}')

        finally:
            os.remove(sftp_path)
    else:
        logger.error(f"can't process sftp upload, path doesn't exist / isn't a file: {sftp_path}")
