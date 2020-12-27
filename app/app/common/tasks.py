import datetime
import json
import logging
import os
import shlex
import shutil
import subprocess
import time

import pytz

from django.core.cache import cache
from django.core.files import File
from django.core.management import call_command
from django.utils import timezone

from constance import config
from huey.contrib import djhuey

from carb import constants

YOUTUBE_DL_PKG = "youtube-dl"
YOUTUBE_DL_CMD = "youtube-dl"
YOUTUBE_DL_TITLE_FIELD_MAPPINGS = {
    "album": ("album",),
    "artist": ("artist", "creator", "uploader", "uploader_id"),
    "title": ("track", "title"),
}
PROCESSING_TEMP_PREFIX = "/tmp/asset-processing"

logger = logging.getLogger(f"carb.{__name__}")


def once_at_startup(crontab):
    needs_to_run = True

    def startup_crontab(*args, **kwargs):
        nonlocal needs_to_run
        if needs_to_run:
            needs_to_run = False
            return True
        else:
            return crontab(*args, **kwargs)

    return startup_crontab


def local_daily_task(hour, minute=0, sunday_only=False):
    def test(datetime_utc):
        datetime_local = timezone.localtime(pytz.utc.localize(datetime_utc))
        return (
            datetime_local.hour == hour
            and datetime_local.minute == minute
            and (not sunday_only or datetime_local.weekday() == 6)
        )

    return test


def install_youtube_dl():
    if not (cache.get(constants.CACHE_KEY_YTDL_UP2DATE) and shutil.which(YOUTUBE_DL_CMD)):
        logger.info("updating youtube-dl...")
        subprocess.run(
            ["pip", "install", "--no-cache-dir", "--upgrade", YOUTUBE_DL_PKG],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cache.set(constants.CACHE_KEY_YTDL_UP2DATE, True, timeout=60 * 60 * 23)
        logger.info("youtube-dl up to date!")


@djhuey.periodic_task(priority=2, validate_datetime=once_at_startup(local_daily_task(hour=4)))
def youtube_dl_daily_update():
    install_youtube_dl()


@djhuey.periodic_task(priority=2, validate_datetime=local_daily_task(hour=4, minute=30))
def remove_unused_media_files_daily():
    logger.info("purging unused media files")
    call_command(
        "cleanup_unused_media",
        remove_empty_dirs=True,
        minimum_file_age=5 * 60,
        interactive=False,
        # Make sure won't remove constance files, we _could_ probably generate this list problematically
        exclude=list(
            filter(
                None,
                (
                    config.UPSTREAM_FAILSAFE_AUDIO_FILE,
                    config.HARBOR_FAILSAFE_AUDIO_FILE,
                    config.HARBOR_SWOOSH_AUDIO_FILE,
                ),
            )
        ),
    )


def mark_asset_failed(asset, title):
    logger.error(title)
    asset.refresh_from_db()
    asset.file = asset.fingerprint = None
    for field in asset.TITLE_FIELDS:
        setattr(asset, field, "")
    asset.title = title
    asset.status = asset.Status.FAILED
    asset.duration = datetime.timedelta(0)
    asset.save()


@djhuey.db_task(priority=1, context=True, retries=3, retry_delay=5)
def asset_download_external_url(asset, url, title="", task=None):
    asset.refresh_from_db()
    asset.status = asset.Status.PROCESSING
    asset.save()

    try:
        args = [
            YOUTUBE_DL_CMD,
            "--newline",
            "--extract-audio",
            "--no-playlist",
            "--max-downloads",
            "1",
            "--no-continue",
            "--audio-format",
            config.ASSET_ENCODING,
            "--exec",
            "echo {}",
            "--socket-timeout",
            "10",
            "--output",
            f"{PROCESSING_TEMP_PREFIX}/%(title)s.%(ext)s",
        ]
        if config.ASSET_ENCODING != "flac":
            args += ["--audio-quality", config.ASSET_BITRATE]

        args += ["--", url]
        logger.info(f"youtube-dl: running: {shlex.join(args)}")
        os.makedirs(PROCESSING_TEMP_PREFIX, exist_ok=True)
        cmd = subprocess.Popen(args, stdout=subprocess.PIPE, text=True)

        # log progress to cache for UI + logger
        last_log_time = 0.0
        for log_line in cmd.stdout:
            log_line = log_line.removesuffix("\n")
            if not log_line.startswith("[download]") or (time.time() - last_log_time >= 0.5):
                logger.info(f"youtube-dl: {log_line}")
                asset.set_task_log_line(f"[external download] {log_line}")
                last_log_time = time.time()

        return_code = cmd.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, cmd)

        if os.path.exists(log_line):
            try:
                asset.refresh_from_db()
                asset.file_basename = os.path.basename(log_line)
                asset.file.save(
                    f"external/{asset.file_basename}",
                    File(open(log_line, "rb")),
                    save=False,
                )
                asset.title = title
                asset.clean()
                asset.save()
                logger.info(f"youtube-dl: {url} successfully downloaded to {log_line}")

            finally:
                os.remove(log_line)

        else:
            raise Exception(f"youtube-dl reported downloaded file {log_line!r}, but it does not exist!")

        # If file doesn't contain metadata for one of the title fields, try to get it from youtube-dl
        if not all(getattr(asset.metadata, field) for field in asset.TITLE_FIELDS):
            args = [YOUTUBE_DL_CMD, "--dump-json", "--no-playlist", "--max-downloads", "1", "--", url]
            logger.info(f"Some metadata missing from file, using youtube-dl to set it, running: {shlex.join(args)}")
            cmd = subprocess.run(args, capture_output=True)
            if cmd.returncode == 0:
                json_data = json.loads(cmd.stdout)
                for field in asset.TITLE_FIELDS:
                    if not getattr(asset, field):
                        setattr(
                            asset,
                            field,
                            # The first youtube-dl field that matches the list YOUTUBE_DL_TITLE_FIELD_MAPPINGS or blank
                            next(
                                (
                                    json_data.get(ytdl_field)
                                    for ytdl_field in YOUTUBE_DL_TITLE_FIELD_MAPPINGS[field]
                                    if json_data.get(ytdl_field)
                                ),
                                "",
                            ),
                        )

                if asset.is_dirty():
                    asset.save()
            else:
                logger.info("youtube-dl failed to get metadata. Skipping that step.")

    except Exception:
        if task is None or task.retries == 0:
            mark_asset_failed(asset, f"Failed to download to {url}")

        raise


@djhuey.db_task(priority=1, context=True, retries=3, retry_delay=5)
def asset_convert_to_acceptable_format(asset, task=None):
    asset.refresh_from_db()
    asset.status = asset.Status.PROCESSING
    asset.save()

    try:
        new_ext = config.ASSET_ENCODING
        if new_ext == "vorbis":  # Rename youtube-dl to ffmpeg format: vorbis -> ogg
            new_ext = "ogg"

        infile = asset.local_filename
        outfile = f"{PROCESSING_TEMP_PREFIX}/{os.path.splitext(os.path.basename(asset.local_filename))[0]}.{new_ext}"
        args = ["ffmpeg", "-hide_banner", "-y", "-i", infile, "-map", "0:a:0"]
        if config.ASSET_ENCODING != "flac":
            args.extend(["-b:a", config.ASSET_BITRATE.lower()])  # Rename youtube-dl to ffmpeg format: K -> k
        args.extend(["--", outfile])

        os.makedirs(PROCESSING_TEMP_PREFIX, exist_ok=True)
        cmd = subprocess.Popen(args, stderr=subprocess.PIPE, text=True)

        last_log_time = 0.0
        for log_line in cmd.stderr:
            log_line = log_line.removesuffix("\n")
            if time.time() - last_log_time >= 0.5:
                logger.info(f"ffmpeg: {log_line}")
                asset.set_task_log_line(f"[{config.ASSET_ENCODING} conversion] {log_line}")
                last_log_time = time.time()

        return_code = cmd.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, cmd)

        if os.path.exists(outfile):
            logger.info(f"ffmpeg converted {infile} to {outfile}.")

            try:
                # Keep imported/ prefix
                filename = f"converted/{os.path.basename(outfile)}"
                if "imported/" in infile:
                    filename = f"imported/{filename}"

                asset.refresh_from_db()
                asset.file.save(filename, File(open(outfile, "rb")), save=False)
                asset.clear_metadata_cache()
                asset.clean(allow_conversion=False)  # Avoids infinite loop
                asset.save()

            finally:
                os.remove(outfile)  # django-cleanup removes infile for us

        else:
            logger.warning(f"ffmpeg (conversion) returned {cmd.returncode} (or converted {outfile} doesn't exist)")

    except Exception:
        if task is None or task.retries == 0:
            mark_asset_failed(
                asset,
                f"Failed to convert to {config.ASSET_ENCODING}: {asset.file_basename}",
            )

        raise
