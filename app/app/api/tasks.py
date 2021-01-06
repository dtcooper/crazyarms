import logging
import os
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File

from huey.contrib import djhuey

from autodj.models import AudioAsset, Playlist, RotatorAsset
from broadcast.models import BroadcastAsset
from common.models import User

logger = logging.getLogger(f"crazyarms.{__name__}")

SFTP_PATH_ASSET_CLASSES = {
    "audio-assets": AudioAsset,
    "scheduled-broadcast-assets": BroadcastAsset,
    "rotator-assets": RotatorAsset,
}
SFTP_PATH_RE = re.compile(
    fr"^{re.escape(settings.SFTP_UPLOADS_ROOT)}(?P<user_id>[^/]+)/"
    fr'(?:(?P<asset_type>{"|".join(re.escape(p) for p in SFTP_PATH_ASSET_CLASSES.keys())})/)?'
    r"(?:(?P<first_folder_name>[^/]+)/)?.+$"
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
                    logger.warning(f"sftp upload skipped {type_name} by {uploader} {sftp_path}: validation error: {e}")
                else:
                    asset.save()
                    logger.info(f"sftp upload of {type_name} by {uploader} successfully processed: {sftp_path}")

                # Create a playlist if that's what a user wants (only for AudioAssets)
                if isinstance(asset, AudioAsset) and uploader.sftp_playlists_by_folder:
                    folder = match["first_folder_name"]
                    if folder:
                        playlist_name = " ".join(folder.strip().split())  # normalize whitespace
                        playlist = Playlist.objects.filter(name__iexact=playlist_name).first()
                        if playlist:
                            logger.info(f"sftp upload by {uploader} used playlist {playlist.name}")
                        else:
                            logger.info(
                                f"sftp upload by {uploader} used playlist folder, creating playlist {playlist_name}"
                            )
                            playlist = Playlist.objects.create(name=playlist_name)

                        asset.playlists.add(playlist)
            else:
                logger.warning(f"sftp upload can't process, regular expression failed to match: {sftp_path}")

        finally:
            os.remove(sftp_path)
    else:
        logger.error(f"sftp update can't process, path doesn't exist / isn't a file: {sftp_path}")
